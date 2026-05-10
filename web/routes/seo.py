"""Rotas de SEO: /robots.txt e /sitemap.xml."""
from __future__ import annotations

import logging
import os
import re
import secrets
import time
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response

from web import db


router = APIRouter()
_log = logging.getLogger("transparencia.seo")


# IndexNow keys: 8-128 chars URL-safe. Pre-compilado pra rejeitar
# paths nao-key sem comparacao (defesa contra probing).
_INDEXNOW_KEY_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{8,128}$")


# Cache em memória pra sitemap (gera lista de municípios uma vez por hora).
_SITEMAP_CACHE: dict[str, Any] = {"ts": 0.0, "xml": ""}
_SITEMAP_TTL = 3600  # 1h


def _site_origin(request: Request) -> str:
    """Origem efetiva (https://transparenciapb.org). Confia no nginx
    forward (X-Forwarded-Proto/Host) com fallback pro request.url."""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


@router.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt(request: Request) -> PlainTextResponse:
    origin = _site_origin(request)
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "# API endpoints (sem conteudo indexavel)\n"
        "Disallow: /api/\n"
        "# Open Graph images dinamicas (servidas em /og/cidade/<slug>.png)\n"
        "# Indexar so via og:image meta tag (cada pagina /search/cidade ja referencia).\n"
        "Disallow: /og/\n"
        "# Service worker — nao deve aparecer em buscas.\n"
        "Disallow: /sw.js\n"
        "\n"
        f"Sitemap: {origin}/sitemap.xml\n"
    )
    return PlainTextResponse(
        body,
        headers={"Cache-Control": "public, max-age=3600"},
    )


def _municipios_pb() -> list[tuple[str, str]]:
    """Lista municipios PB ordenada por total_pago desc (mesma logica
    do warm_cache pra alinhar prioridade). Retorna [(nome_canonico, slug), ...].

    Reutiliza nomes do mv_municipio_pb_risco e o slug helper de
    web.utils.slug pra garantir que sitemap, links no HTML e rota
    /cidade/<slug> usam a MESMA forma canonica.
    """
    sql = """
        SELECT r.municipio
        FROM mv_municipio_pb_risco r
        LEFT JOIN mv_municipio_pb_mapa m ON m.municipio = r.municipio
        WHERE r.municipio IS NOT NULL
        ORDER BY COALESCE(m.total_pago_pj, 0) DESC, r.municipio
    """
    try:
        from web.utils.slug import municipio_slug
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(sql)
                out: list[tuple[str, str]] = []
                seen: set[str] = set()
                for (mun,) in cur.fetchall():
                    slug = municipio_slug(mun)
                    if not slug or slug in seen:
                        continue
                    seen.add(slug)
                    out.append((str(mun), slug))
                return out
    except Exception:
        _log.exception("Falha ao listar municipios PB pro sitemap")
        return []


def _empresas_pb() -> list[tuple[str, str]]:
    """Lista empresas qualificadas (heuristica em web.queries.empresa).
    Retorna [(razao_social, cnpj_completo), ...]. Cnpj eh string de 14
    digitos numericos puros (forma canonica usada pela rota /empresa/{cnpj}).
    """
    from web.queries.empresa import EMPRESAS_QUALIFICADAS_PARA_SITEMAP

    try:
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(EMPRESAS_QUALIFICADAS_PARA_SITEMAP)
                out: list[tuple[str, str]] = []
                seen: set[str] = set()
                for razao, cnpj_completo in cur.fetchall():
                    if not cnpj_completo:
                        continue
                    cnpj_str = str(cnpj_completo).strip()
                    if len(cnpj_str) != 14 or not cnpj_str.isdigit():
                        continue
                    if cnpj_str in seen:
                        continue
                    seen.add(cnpj_str)
                    out.append((str(razao or ""), cnpj_str))
                return out
    except Exception:
        _log.exception("Falha ao listar empresas PB pro sitemap")
        return []


def _lastmod_iso() -> str:
    """Data ISO (YYYY-MM-DD) usada como <lastmod> nas paginas de cidade.

    Reflete a data de refresh dos dados (DATA_REFRESH_DATE_ISO env var,
    setada por main.py). Quando os dados sao atualizados, novo deploy
    com env var atualizada -> sitemap muda -> crawlers recrawl."""
    val = os.environ.get("DATA_REFRESH_DATE", "").strip()
    if val:
        return val
    # Fallback pro mesmo computo do main.py (hora local GMT-3)
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%d")


def _build_sitemap_xml(origin: str) -> str:
    """Gera <urlset> com homepage + paginas estaticas + paginas /search/cidade
    pra cada municipio PB. Usa <lastmod> = data de refresh dos dados pra
    sinalizar a Google quando paginas precisam ser recrawladas."""
    lastmod = _lastmod_iso()
    parts: list[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    parts.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')

    # Paginas estaticas com prioridades manuais
    static_pages = [
        ("/", "1.0", "daily"),
        ("/mapa", "0.9", "daily"),
        ("/sobre", "0.6", "monthly"),
        ("/glossario", "0.5", "monthly"),
        ("/contato", "0.4", "yearly"),
    ]
    for path, prio, freq in static_pages:
        parts.append("  <url>")
        parts.append(f"    <loc>{xml_escape(origin)}{xml_escape(path)}</loc>")
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append(f"    <changefreq>{freq}</changefreq>")
        parts.append(f"    <priority>{prio}</priority>")
        parts.append("  </url>")

    # Pagina /cidade/<slug> pra cada municipio PB. URLs amigaveis: substituem
    # /search/cidade?q=... no sitemap. /search permanece funcional via 301.
    municipios = _municipios_pb()
    for _muni, slug in municipios:
        loc = f"{origin}/cidade/{slug}"
        parts.append("  <url>")
        parts.append(f"    <loc>{xml_escape(loc)}</loc>")
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append("    <changefreq>weekly</changefreq>")
        parts.append("    <priority>0.7</priority>")
        parts.append("  </url>")

    # Pagina /empresa/<cnpj> pra cada empresa qualificada (filtro em
    # web.queries.empresa.EMPRESAS_QUALIFICADAS_PARA_SITEMAP). URL canonica
    # usa 14 digitos numericos puros (sem mascara).
    empresas = _empresas_pb()
    for _razao, cnpj_completo in empresas:
        loc = f"{origin}/empresa/{cnpj_completo}"
        parts.append("  <url>")
        parts.append(f"    <loc>{xml_escape(loc)}</loc>")
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append("    <changefreq>weekly</changefreq>")
        parts.append("    <priority>0.5</priority>")
        parts.append("  </url>")

    parts.append("</urlset>")
    return "\n".join(parts)


@router.get("/sitemap.xml")
async def sitemap_xml(request: Request) -> Response:
    """Sitemap dinamico cached por 1h.

    Importante: NAO cacheamos sitemap parcial (sem URLs de cidade ou
    empresa) — caso contrario, uma falha transitoria de DB no primeiro
    hit pos-restart serviria por 1h um sitemap incompleto a Google/IndexNow.
    Em build parcial, servimos o resultado mas mantemos cache invalido
    para a proxima request tentar de novo.

    Heuristica de completude:
    - Sitemap completo tem static (5) + cidades (~223) + empresas (>=1).
    - Threshold combina: precisa de >= 100 cidades E >= 1 empresa.
    - Se DB de empresas falhar mas cidades estao OK, recusa cache (a
      proxima request reativa _empresas_pb).
    """
    origin = _site_origin(request)
    now = time.time()
    if _SITEMAP_CACHE["xml"] and (now - _SITEMAP_CACHE["ts"] < _SITEMAP_TTL):
        xml = _SITEMAP_CACHE["xml"]
    else:
        xml = _build_sitemap_xml(origin)
        cidades_n = xml.count("/cidade/")
        empresas_n = xml.count("/empresa/")
        # Bookmark de completude: cidades >= 100 (entre 223 PB, threshold
        # generoso pra sobreviver a flapping) E pelo menos 1 empresa
        # qualificada. Se filtro de qualificacao algum dia retornar 0
        # legitimamente, este check vira "nao cacheia, mas /sitemap.xml
        # continua servindo build novo a cada request" — penalty aceitavel.
        is_complete = cidades_n >= 100 and empresas_n >= 1
        if is_complete:
            _SITEMAP_CACHE["xml"] = xml
            _SITEMAP_CACHE["ts"] = now
        else:
            _log.warning(
                "Sitemap parcial gerado (cidades=%d, empresas=%d) — nao "
                "cacheando, proxima request tentara recarregar do DB",
                cidades_n,
                empresas_n,
            )
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ─────────────────────────────────────────────────────────────────────────
# IndexNow (https://www.indexnow.org/)
#
# Protocolo aberto suportado por Bing, Yandex, Yahoo, Seznam, Naver. Permite
# notificar mudancas de URL sem depender de crawler periodico (acelera
# indexacao de novas paginas/cidades de poucos dias pra horas).
#
# Como funciona:
#   1. Geramos um "key" (string opaca de 8-128 chars) e armazenamos em env
#      var INDEXNOW_KEY. O mesmo key tambem precisa estar acessivel via HTTP
#      em /<key>.txt no nosso dominio (rota abaixo) — isso prova que o site
#      eh nosso.
#   2. Submetemos URLs via POST a https://api.indexnow.org/indexnow ou GET
#      a https://www.bing.com/indexnow?url=...&key=...
#   3. IndexNow propaga pro Bing, Yandex, etc.
#
# Setup (no .env / ENV_FILE secret):
#   INDEXNOW_KEY=<gerar via `python -c "import secrets; print(secrets.token_urlsafe(32))"`>
#
# Uso manual (apos deploy de conteudo novo): chamar
#   python -m web.indexnow_submit
# (ou triggar via admin endpoint se desejado).
# ─────────────────────────────────────────────────────────────────────────


@router.get("/{key}.txt", response_class=PlainTextResponse)
async def indexnow_key_file(key: str) -> PlainTextResponse:
    """Serve o arquivo de verificacao do IndexNow em /<key>.txt.

    IndexNow exige que GET /<key>.txt retorne EXATAMENTE o key como
    body texto. Sem isso, motores de busca rejeitam as submissoes.

    Esta rota tambem captura qualquer outro `.txt` no root (ex:
    /humans.txt, /security.txt) que ainda nao temos. Pra esses,
    HTTPException(404) cai no handler global @app.exception_handler(404)
    em main.py:522, que renderiza errors/404.html (UX consistente).

    Defesa em profundidade:
    - Validacao de regex no key recebido: rejeitamos paths que nao
      poderiam ser IndexNow keys (8-128 chars URL-safe). Reduz superficie
      de probing.
    - Compare timing-safe via secrets.compare_digest: defesa contra
      timing attacks que poderiam revelar caracteres da key (impacto baixo
      ja que vazar a key apenas permite que 3rd party submeta URLs do
      nosso dominio, mas e uma boa pratica barata).
    """
    expected = os.environ.get("INDEXNOW_KEY", "").strip()
    if not expected:
        raise HTTPException(status_code=404)
    # IndexNow keys sao 8-128 chars URL-safe (alfanumerico + - + _).
    # Qualquer coisa fora disso: 404 sem nem comparar.
    if not _INDEXNOW_KEY_PATTERN.fullmatch(key):
        raise HTTPException(status_code=404)
    if not secrets.compare_digest(key, expected):
        raise HTTPException(status_code=404)
    return PlainTextResponse(
        expected,
        headers={"Cache-Control": "public, max-age=86400"},
    )
