"""Rotas de SEO: /robots.txt e /sitemap.xml."""
from __future__ import annotations

import logging
import os
import time
from typing import Any
from xml.sax.saxutils import escape as xml_escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response

from web import db


router = APIRouter()
_log = logging.getLogger("transparencia.seo")


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


def _municipios_pb() -> list[str]:
    """Lista municípios PB ordenada por total_pago desc (mesma logica
    do warm_cache pra alinhar prioridade). Retorna lista vazia em erro."""
    sql = """
        SELECT r.municipio
        FROM mv_municipio_pb_risco r
        LEFT JOIN mv_municipio_pb_mapa m ON m.municipio = r.municipio
        WHERE r.municipio IS NOT NULL
        ORDER BY COALESCE(m.total_pago_pj, 0) DESC, r.municipio
    """
    try:
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(sql)
                return [row[0] for row in cur.fetchall()]
    except Exception:
        _log.exception("Falha ao listar municipios PB pro sitemap")
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

    # Pagina /search/cidade pra cada municipio PB
    municipios = _municipios_pb()
    for muni in municipios:
        # Rota real eh /search/cidade?q=<NOME> (web/routes/cidade.py:629).
        # _parse_municipio_uf assume PB sempre quando UF nao esta no string.
        from urllib.parse import quote
        encoded = quote(muni, safe="")
        loc = f"{origin}/search/cidade?q={encoded}"
        parts.append("  <url>")
        parts.append(f"    <loc>{xml_escape(loc)}</loc>")
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append("    <changefreq>weekly</changefreq>")
        parts.append("    <priority>0.7</priority>")
        parts.append("  </url>")

    parts.append("</urlset>")
    return "\n".join(parts)


@router.get("/sitemap.xml")
async def sitemap_xml(request: Request) -> Response:
    """Sitemap dinamico cached por 1h."""
    origin = _site_origin(request)
    now = time.time()
    if _SITEMAP_CACHE["xml"] and (now - _SITEMAP_CACHE["ts"] < _SITEMAP_TTL):
        xml = _SITEMAP_CACHE["xml"]
    else:
        xml = _build_sitemap_xml(origin)
        _SITEMAP_CACHE["xml"] = xml
        _SITEMAP_CACHE["ts"] = now
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
    raise HTTPException(404) entrega o 404 templated normal."""
    expected = os.environ.get("INDEXNOW_KEY", "").strip()
    if not expected or key != expected:
        raise HTTPException(status_code=404)
    return PlainTextResponse(
        expected,
        headers={"Cache-Control": "public, max-age=86400"},
    )
