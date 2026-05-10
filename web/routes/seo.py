"""Rotas de SEO: /robots.txt, /sitemap.xml e shards.

Sitemap-index pattern: /sitemap.xml e um INDEX que aponta pra
sub-sitemaps (urlsets paginados). Suporta volume sem hit no limite
de 50K URLs por arquivo do protocolo sitemap.org:

    /sitemap.xml                    <- sitemapindex (lista de sub-sitemaps)
      ├─ /sitemap-cidades.xml       <- urlset (static + cidades)
      ├─ /sitemap-empresas-1.xml    <- urlset (empresas 1-49000)
      ├─ /sitemap-empresas-2.xml    <- urlset (empresas 49001-98000)
      └─ ...

Empresas so listadas quando SITEMAP_INCLUDE_EMPRESAS=1 (drop-in systemd
gerenciado pelo deploy.yml).
"""
from __future__ import annotations

import logging
import math
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


# Cache em memoria pra cada urlset/index (1h TTL). Cada shard e cacheado
# separadamente — restart do cruza-web limpa tudo, primeira request rebuilda.
_SITEMAP_TTL = 3600  # 1h
_SITEMAP_CACHE: dict[str, Any] = {
    "index": {"ts": 0.0, "xml": ""},
    "cidades": {"ts": 0.0, "xml": ""},
    "empresas": {},  # {shard_n: {"ts": ..., "xml": ...}}
}

# Tamanho de cada shard de empresas. Limite do protocolo eh 50K URLs por
# arquivo; 49K deixa folga pra evitar overflow se o filtro mudar.
EMPRESA_SHARD_SIZE = 49000


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


def _empresas_qualificadas_count() -> int:
    """Total de empresas que vao pro sitemap (sem filtros, todas com matriz
    cadastrada). Usado pra calcular num_shards no sitemap-index.

    Cache em memoria (1h) via _SITEMAP_CACHE['empresas_count']. Restart
    do cruza-web limpa.
    """
    cached = _SITEMAP_CACHE.get("empresas_count")
    now = time.time()
    if cached and (now - cached["ts"] < _SITEMAP_TTL):
        return int(cached["value"])

    from web.queries.empresa import EMPRESAS_QUALIFICADAS_COUNT

    try:
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(EMPRESAS_QUALIFICADAS_COUNT)
                row = cur.fetchone()
                count = int(row[0]) if row else 0
        _SITEMAP_CACHE["empresas_count"] = {"ts": now, "value": count}
        return count
    except Exception:
        _log.exception("Falha ao contar empresas pro sitemap")
        return 0


def _empresas_pb_paginated(shard_n: int, shard_size: int) -> list[tuple[str, str]]:
    """Retorna empresas do shard N (1-indexed). LIMIT/OFFSET na query.

    shard_size = EMPRESA_SHARD_SIZE. Pra shard 1, OFFSET=0; shard 2,
    OFFSET=shard_size; etc. ORDER BY estavel garante que mesma posicao
    no warmer e no sitemap referem mesma empresa.
    """
    from web.queries.empresa import EMPRESAS_QUALIFICADAS_PAGINATED

    if shard_n < 1:
        return []
    offset = (shard_n - 1) * shard_size
    try:
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    EMPRESAS_QUALIFICADAS_PAGINATED,
                    {"limit": shard_size, "offset": offset},
                )
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
        _log.exception("Falha ao carregar shard %d de empresas", shard_n)
        return []


def _empresas_pb() -> list[tuple[str, str]]:
    """LEGACY: lista TODAS empresas em uma chamada. Usado pelo warmer
    (web/warm_cache.py:_get_qualifying_empresas) que ja eh single-shot.

    NAO use no sitemap — use _empresas_pb_paginated com sharding.
    Retorna [(razao_social, cnpj_completo), ...].
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


def _build_static_pages_xml(origin: str, lastmod: str) -> list[str]:
    """Retorna list de <url> blocks pra paginas estaticas. Usado pelo
    sitemap-cidades (que combina static + cidades em um arquivo)."""
    parts: list[str] = []
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
    return parts


def _build_cidades_sitemap(origin: str) -> str:
    """urlset com paginas estaticas + /cidade/<slug>. Sub-sitemap referenciado
    pelo /sitemap.xml index. Cacheado em _SITEMAP_CACHE['cidades']."""
    lastmod = _lastmod_iso()
    parts: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>',
                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    parts.extend(_build_static_pages_xml(origin, lastmod))
    municipios = _municipios_pb()
    for _muni, slug in municipios:
        loc = f"{origin}/cidade/{slug}"
        parts.append("  <url>")
        parts.append(f"    <loc>{xml_escape(loc)}</loc>")
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append("    <changefreq>weekly</changefreq>")
        parts.append("    <priority>0.7</priority>")
        parts.append("  </url>")
    parts.append("</urlset>")
    return "\n".join(parts)


def _build_empresas_shard_sitemap(origin: str, shard_n: int) -> str:
    """urlset com /empresa/<cnpj> pra empresas do shard N (1-indexed).
    LIMIT EMPRESA_SHARD_SIZE OFFSET (n-1)*EMPRESA_SHARD_SIZE.
    Cacheado em _SITEMAP_CACHE['empresas'][shard_n]."""
    lastmod = _lastmod_iso()
    parts: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>',
                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    empresas = _empresas_pb_paginated(shard_n, EMPRESA_SHARD_SIZE)
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


def _build_sitemap_index(origin: str) -> str:
    """sitemapindex que aponta pra /sitemap-cidades.xml + N
    /sitemap-empresas-{n}.xml. Empresas so sao listadas se
    SITEMAP_INCLUDE_EMPRESAS=1.

    Numero de shards = ceil(qualifying_count / EMPRESA_SHARD_SIZE).
    """
    lastmod = _lastmod_iso()
    parts: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>',
                        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    # Sub-sitemap das cidades
    parts.append("  <sitemap>")
    parts.append(f"    <loc>{xml_escape(origin)}/sitemap-cidades.xml</loc>")
    parts.append(f"    <lastmod>{lastmod}</lastmod>")
    parts.append("  </sitemap>")

    # Sub-sitemaps de empresas (so se flag ativada).
    if os.environ.get("SITEMAP_INCLUDE_EMPRESAS", "0") == "1":
        total = _empresas_qualificadas_count()
        if total > 0:
            num_shards = math.ceil(total / EMPRESA_SHARD_SIZE)
            for n in range(1, num_shards + 1):
                parts.append("  <sitemap>")
                parts.append(f"    <loc>{xml_escape(origin)}/sitemap-empresas-{n}.xml</loc>")
                parts.append(f"    <lastmod>{lastmod}</lastmod>")
                parts.append("  </sitemap>")

    parts.append("</sitemapindex>")
    return "\n".join(parts)


@router.get("/sitemap.xml")
async def sitemap_xml(request: Request) -> Response:
    """Sitemap-INDEX raiz. Aponta pra sub-sitemaps que contem URLs.

    Cache 1h em _SITEMAP_CACHE['index']. Restart limpa.

    Heuristica de completude (anti-cache parcial):
    - Cidades sub-sitemap sempre presente.
    - Empresas shards (>= 1) so quando flag SITEMAP_INCLUDE_EMPRESAS=1
      E mv_empresa_pb tem rows.
    - Se flag ON mas empresas count = 0 (DB falhou ou MV vazia),
      recusamos cache pra proxima request reativar.
    """
    origin = _site_origin(request)
    now = time.time()
    cached = _SITEMAP_CACHE["index"]
    if cached["xml"] and (now - cached["ts"] < _SITEMAP_TTL):
        return Response(
            content=cached["xml"],
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )

    xml = _build_sitemap_index(origin)
    flag_on = os.environ.get("SITEMAP_INCLUDE_EMPRESAS", "0") == "1"
    has_empresa_shards = "/sitemap-empresas-" in xml
    is_complete = (not flag_on) or has_empresa_shards
    if is_complete:
        _SITEMAP_CACHE["index"] = {"ts": now, "xml": xml}
    else:
        _log.warning(
            "Sitemap-index parcial (flag_empresas=%s mas sem shards) — "
            "nao cacheando",
            flag_on,
        )
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/sitemap-cidades.xml")
async def sitemap_cidades_xml(request: Request) -> Response:
    """Sub-sitemap: paginas estaticas + /cidade/<slug>. Cacheado 1h."""
    origin = _site_origin(request)
    now = time.time()
    cached = _SITEMAP_CACHE["cidades"]
    if cached["xml"] and (now - cached["ts"] < _SITEMAP_TTL):
        xml = cached["xml"]
    else:
        xml = _build_cidades_sitemap(origin)
        cidades_n = xml.count("/cidade/")
        if cidades_n >= 100:
            _SITEMAP_CACHE["cidades"] = {"ts": now, "xml": xml}
        else:
            _log.warning(
                "Sitemap-cidades parcial (cidades=%d) — nao cacheando",
                cidades_n,
            )
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# Pattern: /sitemap-empresas-{n}.xml onde n = inteiro 1..num_shards
_EMPRESAS_SHARD_RE = re.compile(r"^[1-9]\d{0,3}$")


@router.get("/sitemap-empresas-{shard_n}.xml")
async def sitemap_empresas_shard_xml(request: Request, shard_n: str) -> Response:
    """Sub-sitemap shard de empresas. shard_n eh 1-indexed.

    Validacao defensiva: regex 1-9999. Shards inexistentes (alem do
    numero de shards atual) retornam urlset vazio (200 valido) — Google
    tolera, e evita 404 transitorio se sitemap-index aponta pra shard
    que ainda nao foi cacheado.

    Cache 1h por shard em _SITEMAP_CACHE['empresas'][n].
    """
    if not _EMPRESAS_SHARD_RE.match(shard_n):
        raise HTTPException(status_code=404)
    n = int(shard_n)

    origin = _site_origin(request)
    now = time.time()
    shard_cache = _SITEMAP_CACHE["empresas"].get(n)
    if shard_cache and shard_cache.get("xml") and (now - shard_cache["ts"] < _SITEMAP_TTL):
        xml = shard_cache["xml"]
    else:
        xml = _build_empresas_shard_sitemap(origin, n)
        urls_n = xml.count("/empresa/")
        # NUNCA cachear shard vazio. Cenario: MV cresce de 143K pra 200K
        # entre 2 requests. Shard 4 (antes past-end, vazio) agora tem
        # ~49K URLs reais. Se cacheamos vazio, Google lê 0 URLs por ate
        # 1h apos crescimento — perde ~49K paginas indexaveis. Query past-
        # end com OFFSET alto eh barata (LIMIT 49000 + index hit) entao
        # rebuilda em ~ms. (P2 do Opus 4.7 review do PR #60.)
        if urls_n > 0:
            _SITEMAP_CACHE["empresas"][n] = {"ts": now, "xml": xml}
        elif n == 1:
            _log.warning(
                "Sitemap-empresas shard 1 vazio — nao cacheando "
                "(DB pode ter falhado)"
            )
        # else (n > 1, vazio): nao cacheia, mas serve urlset vazio agora.
        # Proxima request rebuilda — se MV cresceu, vai retornar URLs.
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
