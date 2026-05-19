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
_SITEMAP_TTL = 86400  # 24h
# 24h ao inves de 1h: counts/shards mudam pouco (depende de novos
# fornecedores aparecerem em tce_pb_despesa). Reduz exposicao a queries
# pesadas pos-restart do cruza-web (cache em memoria limpo) — Google
# Search Console reportou "Couldn't fetch" quando o primeiro hit pos-
# restart batia em GROUP BY de ~16M rows.
#
# Plus o COUNT/PAGINATED agora usam mv_empresa_municipio_pagantes
# (instantaneo) em vez de GROUP BY live — TTL longo eh seguranca extra.
_SITEMAP_CACHE: dict[str, Any] = {
    "index": {"ts": 0.0, "xml": ""},
    "cidades": {"ts": 0.0, "xml": ""},
    "empresas": {},  # {shard_n: {"ts": ..., "xml": ...}}
    "empresas_municipios": {},  # {shard_n: {"ts": ..., "xml": ...}}
    "licitacoes": {},  # {shard_n: {"ts": ..., "xml": ...}}
    "cidade_resumo": {"ts": 0.0, "xml": ""},
}

# ─── Persistencia em web_cache (L2 cache) ───
# Resolve "Couldn't fetch" reportado no GSC pos-restart do cruza-web:
# o _SITEMAP_CACHE acima eh in-memory (L1) e nao sobrevive a restart;
# primeiro hit pos-restart pagava ~20s de build live (8-9MB XML por shard),
# que GSC marca como timeout. Agora cache eh 2-camadas:
#
#   L1 = _SITEMAP_CACHE (in-memory, 24h TTL, fast lookup)
#   L2 = web_cache table (PG, sem TTL, sobrevive restart)
#   L3 = build live (fallback)
#
# Naming convention das keys L2 (em web_cache.municipio column):
#   '<scope>-urlset'        -> sitemap unico (sem shards)
#   '<scope>-shard:N'       -> shard N de sitemap shardado
#
# Mapping L1 (bucket names acima) -> L2 (keys em web_cache):
#   _SITEMAP_CACHE["index"]                  -> [L1 apenas, nao em L2 *]
#   _SITEMAP_CACHE["cidades"]                -> "cidades-urlset"
#   _SITEMAP_CACHE["empresas"][N]            -> "empresas-shard:N"
#   _SITEMAP_CACHE["empresas_municipios"][N] -> "empresas-municipios-shard:N"
#   _SITEMAP_CACHE["licitacoes"][N]          -> "licitacoes-shard:N"
#   _SITEMAP_CACHE["cidade_resumo"]          -> "cidade-resumo-urlset"
#
# (*) root-index NAO eh persistido em L2 porque (a) build eh barato
# (<50ms, sem queries pesadas) e (b) o XML reflete as flags
# SITEMAP_INCLUDE_* ATUAIS do processo runtime — cachear flags=1 do
# warmer e servir pra processo com flags=0 seria cache poisoning.
# (HIGH GPT-5.5 round 4 PR #85.)
#
# Warmer (`web/warm_cache.py:_warm_sitemaps_phase`) pre-popula todos os
# entries L2 ao fim do warm cycle. invalidate_cache_keys=SITEMAP_XML
# em deploy.yml limpa L2 (forca re-geracao no proximo warm).
_SITEMAP_CACHE_QUERY_ID = "SITEMAP_XML"


def _sitemap_pg_read(key: str) -> str | None:
    """Tenta ler XML do web_cache (L2). Retorna None em falha/ausencia.

    NOTA: db.read_web_cache retorna sentinel CACHE_ERROR em DB error
    (PR #181) que eh iteravel e desempacota como ([], []). Nesse caso
    `rows[0]` levanta IndexError implicitamente nao — `rows and rows[0]`
    eh False, retornamos None. Resultado: DB error vira "cache miss",
    rota cai em L3 (build live). Tradeoff aceitavel — alternativa seria
    503 explicito mas sitemaps publicos nao deveriam retornar 503.
    """
    cached = db.read_web_cache(_SITEMAP_CACHE_QUERY_ID, key)
    # Trata CACHE_ERROR (DB error) e None (cache miss) igualmente: None.
    if cached is None or cached is db.CACHE_ERROR:
        return None
    _cols, rows = cached
    if rows and rows[0] and isinstance(rows[0][0], str):
        return rows[0][0]
    return None


def _sitemap_pg_write(key: str, xml: str) -> bool:
    """Persiste XML no web_cache (L2). Retorna True em sucesso, False em erro.

    IMPORTANTE: caller deve verificar o retorno. Falha aqui significa que
    a rota servindo o sitemap vai precisar rebuilder live no proximo hit —
    degradacao aceitavel, nao site-down.

    L1 (_SITEMAP_CACHE in-memory) eh atualizado pelo caller (rota), nao
    aqui — quem chama isto ja tem acesso ao XML pra escrever em ambos.
    """
    try:
        import json as _json
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO web_cache (query_id, municipio, columns, rows, row_count, updated_at)
                    VALUES (%s, %s, %s, %s, %s, now())
                    ON CONFLICT (query_id, municipio)
                    DO UPDATE SET columns = EXCLUDED.columns,
                                  rows = EXCLUDED.rows,
                                  row_count = EXCLUDED.row_count,
                                  updated_at = now()
                    """,
                    (
                        _SITEMAP_CACHE_QUERY_ID,
                        key,
                        _json.dumps(["xml"]),
                        _json.dumps([[xml]]),
                        1,
                    ),
                )
        return True
    except Exception:
        _log.exception("Falha ao persistir sitemap '%s' no web_cache", key)
        return False


# Tamanho de cada shard de empresas. Limite do protocolo eh 50K URLs por
# arquivo; 49K deixa folga pra evitar overflow se o filtro mudar.
EMPRESA_SHARD_SIZE = 49000

# Tamanho de shard de licitacoes (mesmo limite do empresa).
LICITACAO_SHARD_SIZE = 49000


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
        ("/caso/socorro-gadelha", "0.8", "monthly"),
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


def _empresas_municipios_qualificadas_count() -> int:
    """Total de pares (empresa, municipio) que vao pro sitemap. Usado pra
    calcular num_shards do /sitemap-empresas-municipios-{n}.xml.

    Cache em memoria (1h) via _SITEMAP_CACHE['empresas_municipios_count'].
    """
    cached = _SITEMAP_CACHE.get("empresas_municipios_count")
    now = time.time()
    if cached and (now - cached["ts"] < _SITEMAP_TTL):
        return int(cached["value"])

    from web.queries.empresa import EMPRESAS_MUNICIPIOS_QUALIFICADAS_COUNT

    try:
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(EMPRESAS_MUNICIPIOS_QUALIFICADAS_COUNT)
                row = cur.fetchone()
                count = int(row[0]) if row else 0
        _SITEMAP_CACHE["empresas_municipios_count"] = {"ts": now, "value": count}
        return count
    except Exception:
        _log.exception("Falha ao contar pares (empresa, municipio) pro sitemap")
        return 0


def _empresas_municipios_paginated(shard_n: int, shard_size: int) -> list[tuple[str, str, str]]:
    """Retorna pares (cnpj_completo, municipio_nome, slug) do shard N
    (1-indexed). Aplica municipio_slug() aqui pra evitar SQL fancy.
    """
    from web.queries.empresa import EMPRESAS_MUNICIPIOS_QUALIFICADAS_PAGINATED
    from web.utils.slug import municipio_slug as _slug_of

    if shard_n < 1:
        return []
    offset = (shard_n - 1) * shard_size
    try:
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    EMPRESAS_MUNICIPIOS_QUALIFICADAS_PAGINATED,
                    {"limit": shard_size, "offset": offset},
                )
                out: list[tuple[str, str, str]] = []
                seen: set[tuple[str, str]] = set()
                for cnpj_completo, municipio, _total in cur.fetchall():
                    if not cnpj_completo or not municipio:
                        continue
                    cnpj_str = str(cnpj_completo).strip()
                    if len(cnpj_str) != 14 or not cnpj_str.isdigit():
                        continue
                    mun = str(municipio).strip()
                    if not mun:
                        continue
                    slug = _slug_of(mun)
                    if not slug:
                        continue
                    key = (cnpj_str, slug)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append((cnpj_str, mun, slug))
                return out
    except Exception:
        _log.exception("Falha ao carregar shard %d de empresas-municipios", shard_n)
        return []


def _build_empresas_municipios_shard_sitemap(origin: str, shard_n: int) -> str:
    """urlset com /empresa/<cnpj>/<slug> pra pares do shard N (1-indexed).
    Cacheado em _SITEMAP_CACHE['empresas_municipios'][shard_n]."""
    lastmod = _lastmod_iso()
    parts: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>',
                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    pares = _empresas_municipios_paginated(shard_n, EMPRESA_SHARD_SIZE)
    for cnpj_completo, _mun_nome, slug in pares:
        loc = f"{origin}/empresa/{cnpj_completo}/{slug}"
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

        # Pares (empresa, municipio) — variantes /empresa/<cnpj>/<slug>.
        total_mun = _empresas_municipios_qualificadas_count()
        if total_mun > 0:
            num_shards_mun = math.ceil(total_mun / EMPRESA_SHARD_SIZE)
            for n in range(1, num_shards_mun + 1):
                parts.append("  <sitemap>")
                parts.append(f"    <loc>{xml_escape(origin)}/sitemap-empresas-municipios-{n}.xml</loc>")
                parts.append(f"    <lastmod>{lastmod}</lastmod>")
                parts.append("  </sitemap>")

    # Sub-sitemaps de licitacoes (gated por env flag separado).
    if os.environ.get("SITEMAP_INCLUDE_LICITACOES", "0") == "1":
        total_lic = _licitacoes_qualificadas_count()
        if total_lic > 0:
            num_shards_lic = math.ceil(total_lic / LICITACAO_SHARD_SIZE)
            for n in range(1, num_shards_lic + 1):
                parts.append("  <sitemap>")
                parts.append(f"    <loc>{xml_escape(origin)}/sitemap-licitacoes-{n}.xml</loc>")
                parts.append(f"    <lastmod>{lastmod}</lastmod>")
                parts.append("  </sitemap>")

    # Sub-sitemap unico de cidade-resumo mensal (gated por env flag separado).
    # Sem sharding: ~14k URLs cabem em 1 urlset (limite protocolo: 50k).
    if os.environ.get("SITEMAP_INCLUDE_CIDADE_RESUMO", "0") == "1":
        parts.append("  <sitemap>")
        parts.append(f"    <loc>{xml_escape(origin)}/sitemap-cidade-resumo.xml</loc>")
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
    # L1: in-memory cache
    cached = _SITEMAP_CACHE["index"]
    if cached["xml"] and (now - cached["ts"] < _SITEMAP_TTL):
        return Response(
            content=cached["xml"],
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    # NOTA: root-index NAO usa L2 (web_cache) por dois motivos:
    #
    # 1. _build_sitemap_index eh barato (<50ms — apenas string concat de
    #    URLs dos sub-sitemaps, sem queries pesadas). Diferente dos shards
    #    que carregam 8-9MB de XML, o index nao tem o problema de cold
    #    timeout que motivou o L2 cache em primeiro lugar.
    #
    # 2. O XML do index reflete as flags SITEMAP_INCLUDE_EMPRESAS/
    #    LICITACOES/CIDADE_RESUMO ATUAIS do processo cruza-web. Cachear em
    #    L2 (escrito com todas as flags=1 pelo warmer pra pre-gerar)
    #    faria a rota servir um index com families que o processo runtime
    #    tem desabilitadas via drop-in systemd — cache poisoning entre
    #    warmer flags e route flags. (HIGH GPT-5.5 round 4 PR #85.)
    #
    # L1 in-memory continua ativo com anti-cache parcial (is_complete
    # check abaixo) que respeita flags. L3 build live cobre cold start.

    xml = _build_sitemap_index(origin)
    # Anti-cache parcial: nao cachear sitemap-index quando uma flag
    # de tipo esta ligada mas o tipo NAO esta listado no XML (signal de
    # que cache de licitacoes/empresas/resumo ainda nao foi populado).
    # Sem isso, primeiro hit pos-deploy com flag=1 + warm em curso
    # cacheia sitemap vazio por 24h → Google nao descobre paginas.
    # (P2 GPT 5.5 round 2 PR #108.)
    flag_emp = os.environ.get("SITEMAP_INCLUDE_EMPRESAS", "0") == "1"
    flag_lic = os.environ.get("SITEMAP_INCLUDE_LICITACOES", "0") == "1"
    flag_res = os.environ.get("SITEMAP_INCLUDE_CIDADE_RESUMO", "0") == "1"
    has_empresa = "/sitemap-empresas-" in xml
    has_lic = "/sitemap-licitacoes-" in xml
    has_res = "/sitemap-cidade-resumo.xml" in xml
    is_complete = (
        (not flag_emp or has_empresa)
        and (not flag_lic or has_lic)
        and (not flag_res or has_res)
    )
    if is_complete:
        _SITEMAP_CACHE["index"] = {"ts": now, "xml": xml}
        # L2 NAO escrita aqui (vide comentario acima — root-index nunca em L2).
    else:
        _log.warning(
            "Sitemap-index parcial (flags emp=%s lic=%s res=%s; has emp=%s lic=%s res=%s) — nao cacheando",
            flag_emp, flag_lic, flag_res, has_empresa, has_lic, has_res,
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
    # L1: in-memory cache
    cached = _SITEMAP_CACHE["cidades"]
    if cached["xml"] and (now - cached["ts"] < _SITEMAP_TTL):
        return Response(
            content=cached["xml"],
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    # L2: web_cache (PG)
    pg_xml = _sitemap_pg_read("cidades-urlset")
    if pg_xml:
        _SITEMAP_CACHE["cidades"] = {"ts": now, "xml": pg_xml}
        return Response(
            content=pg_xml,
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    # L3: build live
    xml = _build_cidades_sitemap(origin)
    cidades_n = xml.count("/cidade/")
    if cidades_n >= 100:
        _SITEMAP_CACHE["cidades"] = {"ts": now, "xml": xml}
        # L2 nao escrita aqui — risco de cache poisoning via Host header.
        # Warmer (SITE_ORIGIN env canonico) eh quem popula L2.
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


@router.get("/sitemap-empresas-{shard_n:int}.xml")
async def sitemap_empresas_shard_xml(request: Request, shard_n: int) -> Response:
    """Sub-sitemap shard de empresas. shard_n eh 1-indexed.

    Path converter `int` (FastAPI/Starlette) garante que so digitos puros
    casam — `municipios-1` cai pro handler especifico abaixo, nao aqui.
    Sem isso, /sitemap-empresas-municipios-1.xml seria capturado por essa
    rota com shard_n="municipios-1" e retornaria 404 silenciosamente,
    quebrando todas as URLs municipios-scoped no sitemap. (P1 do GPT-5.5
    review do PR #62.)

    Validacao adicional: 1-9999 via regex. Shard past-end (alem do numero
    real de shards atualmente) retorna 410 Gone — sinaliza ao Google que
    o sub-sitemap nao existe mais, removendo do indice mais rapido que
    urlset vazio (que aparece como "Tag XML ausente" em Search Console
    quando a MV encolhe — ex: pos cleanup de PR #165, ADR-0009).

    Sem buffer: `_empresas_qualificadas_count()` le da mesma fonte que o
    sitemap-index (`_build_sitemap_index` em linha ~417), ambos usam o
    mesmo cache TTL de 24h. Se index lista shards 1..N, count tambem
    devolve N — sem janela de inconsistencia que justifique buffer.
    Buffer +1 (sugestao inicial) deixava o primeiro shard past-end
    ainda retornando urlset vazio 200, reproduzindo o bug exato em
    `max_shard+1`. (HIGH GPT 5.5 review PR #167.)

    Cache 24h por shard em _SITEMAP_CACHE['empresas'][n].
    """
    if shard_n < 1 or shard_n > 9999:
        raise HTTPException(status_code=404)
    n = shard_n

    # Past-end detection: shard alem do numero real atual = 410 Gone.
    # Count ja cacheado 24h (_empresas_qualificadas_count usa _SITEMAP_TTL).
    total = _empresas_qualificadas_count()
    if total > 0:
        max_shard = math.ceil(total / EMPRESA_SHARD_SIZE)
        if n > max_shard:
            raise HTTPException(status_code=410)

    origin = _site_origin(request)
    now = time.time()
    # L1: in-memory cache
    shard_cache = _SITEMAP_CACHE["empresas"].get(n)
    if shard_cache and shard_cache.get("xml") and (now - shard_cache["ts"] < _SITEMAP_TTL):
        return Response(
            content=shard_cache["xml"],
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    # L2: web_cache (PG) — sobrevive restart
    pg_xml = _sitemap_pg_read(f"empresas-shard:{n}")
    if pg_xml:
        _SITEMAP_CACHE["empresas"][n] = {"ts": now, "xml": pg_xml}
        return Response(
            content=pg_xml,
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    # L3: build live
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
        # L2 nao escrita aqui — risco de cache poisoning via Host header.
        # Warmer (SITE_ORIGIN env canonico) eh quem popula L2.
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


# Pattern: /sitemap-empresas-municipios-{n}.xml onde n = inteiro 1..num_shards
_EMPRESAS_MUN_SHARD_RE = re.compile(r"^[1-9]\d{0,3}$")


@router.get("/sitemap-empresas-municipios-{shard_n:int}.xml")
async def sitemap_empresas_municipios_shard_xml(request: Request, shard_n: int) -> Response:
    """Sub-sitemap shard das URLs /empresa/<cnpj>/<slug>. Mesma logica do
    shard /sitemap-empresas-{n}.xml: regex 1-9999, past-end retorna 410
    Gone (era urlset vazio antes do fix do encolhimento MV, ver PR #165
    + ADR-0009). Cache 24h por shard.

    Path converter `int` evita conflito com a rota irma (sem isso ambas
    competem pelo mesmo path). Vide P1 do GPT-5.5 review."""
    if shard_n < 1 or shard_n > 9999:
        raise HTTPException(status_code=404)
    n = shard_n

    # Past-end detection (mesmo padrao de sitemap-empresas-N, sem buffer).
    total = _empresas_municipios_qualificadas_count()
    if total > 0:
        max_shard = math.ceil(total / EMPRESA_SHARD_SIZE)
        if n > max_shard:
            raise HTTPException(status_code=410)

    origin = _site_origin(request)
    now = time.time()
    # L1: in-memory cache
    shard_cache = _SITEMAP_CACHE["empresas_municipios"].get(n)
    if shard_cache and shard_cache.get("xml") and (now - shard_cache["ts"] < _SITEMAP_TTL):
        return Response(
            content=shard_cache["xml"],
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    # L2: web_cache (PG)
    pg_xml = _sitemap_pg_read(f"empresas-municipios-shard:{n}")
    if pg_xml:
        _SITEMAP_CACHE["empresas_municipios"][n] = {"ts": now, "xml": pg_xml}
        return Response(
            content=pg_xml,
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    # L3: build live
    xml = _build_empresas_municipios_shard_sitemap(origin, n)
    urls_n = xml.count("/empresa/")
    if urls_n > 0:
        _SITEMAP_CACHE["empresas_municipios"][n] = {"ts": now, "xml": xml}
        # L2 nao escrita aqui (vide comentario em sitemap_empresas_shard_xml).
    elif n == 1:
        _log.warning(
            "Sitemap-empresas-municipios shard 1 vazio — nao cacheando "
            "(DB pode ter falhado)"
        )
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ─────────────────────────────────────────────────────────────────────────
# Licitacoes — /sitemap-licitacoes-<n>.xml + helpers
# ─────────────────────────────────────────────────────────────────────────


def _licitacoes_qualificadas_count() -> int:
    """Conta licitacoes em web_cache (sitemap reflete o que esta cacheado).

    Antes contava de LICITACOES_QUALIFICADAS_COUNT direto da fonte; agora
    le de web_cache pra que num_shards bata com o que _licitacoes_paginated
    retorna. (P1 GPT 5.5 PR #108.)

    Anti-cache parcial: nao cachear count=0 quando flag esta ligada — pode
    ser cache miss transitorio durante warm (P2 GPT 5.5 round 2).
    """
    cached = _SITEMAP_CACHE.get("licitacoes_count")
    now = time.time()
    if cached and (now - cached["ts"] < _SITEMAP_TTL):
        return int(cached["value"])
    try:
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM web_cache WHERE query_id = 'LICITACAO_PERFIL'"
                )
                row = cur.fetchone()
                count = int(row[0]) if row else 0
        # So cacheia count se != 0 OU se a flag esta desligada.
        flag_on = os.environ.get("SITEMAP_INCLUDE_LICITACOES", "0") == "1"
        if count > 0 or not flag_on:
            _SITEMAP_CACHE["licitacoes_count"] = {"ts": now, "value": count}
        else:
            _log.warning(
                "_licitacoes_qualificadas_count = 0 com flag ligada — nao cacheando "
                "(provavelmente warm em curso)"
            )
        return count
    except Exception:
        _log.exception("Falha ao contar licitacoes em web_cache")
        return 0


def _licitacoes_paginated(shard_n: int, shard_size: int) -> list[tuple[str, int, str, str, str, str]]:
    """Retorna 6-tupla pro shard N a partir do que esta cacheado em web_cache.

    LE DE web_cache (NAO do qualifying set) — garante que cada URL do sitemap
    tem cache populado, evitando 503 mass-publish. Coverage gate eh sanity
    check no deploy, mas o sitemap eh estritamente o que existe na cache.
    (P1 GPT 5.5 review PR #108.)

    Cache key formato: "<mun_slug>:<ano>:<ug_slug>:<mod_num_slug>".
    """
    if shard_n < 1:
        return []
    offset = (shard_n - 1) * shard_size
    try:
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT municipio
                    FROM web_cache
                    WHERE query_id = 'LICITACAO_PERFIL'
                    ORDER BY municipio
                    LIMIT %s OFFSET %s
                    """,
                    (shard_size, offset),
                )
                out: list[tuple[str, int, str, str, str, str]] = []
                for (cache_key,) in cur.fetchall():
                    if not cache_key:
                        continue
                    parts = str(cache_key).split(":", 3)
                    if len(parts) != 4:
                        continue
                    mun_slug, ano_s, ug_slug, mod_num_slug = parts
                    try:
                        ano_int = int(ano_s)
                    except ValueError:
                        continue
                    out.append((mun_slug, ano_int, ug_slug, mod_num_slug, "", ""))
                return out
    except Exception:
        _log.exception("Falha ao carregar shard %d de licitacoes do web_cache", shard_n)
        return []


def _build_licitacoes_shard_sitemap(origin: str, shard_n: int) -> str:
    """urlset com /licitacao/<mun>/<ano>/<ug>/<modnum> pro shard N."""
    lastmod = _lastmod_iso()
    parts: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>',
                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lics = _licitacoes_paginated(shard_n, LICITACAO_SHARD_SIZE)
    for mun_slug, ano, ug_slug, mod_num_slug, _mun_nome, _ug_nome in lics:
        loc = f"{origin}/licitacao/{mun_slug}/{ano}/{ug_slug}/{mod_num_slug}"
        parts.append("  <url>")
        parts.append(f"    <loc>{xml_escape(loc)}</loc>")
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append("    <changefreq>monthly</changefreq>")
        parts.append("    <priority>0.5</priority>")
        parts.append("  </url>")
    parts.append("</urlset>")
    return "\n".join(parts)


@router.get("/sitemap-licitacoes-{shard_n:int}.xml")
async def sitemap_licitacoes_shard_xml(request: Request, shard_n: int) -> Response:
    """Sub-sitemap shard de licitacoes. 1-indexed. Past-end retorna urlset
    vazio (mesmo padrao /sitemap-empresas-N.xml pre-PR #167).

    Sem fix de 410 Gone aplicado aqui — `_licitacoes_qualificadas_count()`
    le de web_cache (`query_id = 'LICITACAO_PERFIL'`), valor que oscila
    durante warm. Count cacheado por 24h enquanto warm popula gradualmente
    (50k -> 350k) faria 410 spurious em shards 4-7 que ainda virao a ser
    populados. (HIGH Opus 4.7 review PR #167.) urlset vazio HTTP 200 e
    seguro durante warm — Google retentara apos warm completar e index
    refletir count final. Encolhimento da MV de licitacoes nao foi
    observado historicamente (ao contrario de empresas/empresas-municipios
    pos-cleanup de PR #165)."""
    if shard_n < 1 or shard_n > 9999:
        raise HTTPException(status_code=404)
    origin = _site_origin(request)
    now = time.time()
    # L1: in-memory cache
    shard_cache = _SITEMAP_CACHE["licitacoes"].get(shard_n)
    if shard_cache and shard_cache.get("xml") and (now - shard_cache["ts"] < _SITEMAP_TTL):
        return Response(
            content=shard_cache["xml"],
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    # L2: web_cache (PG) — adicionado no rebase 2026-05-19 (issue HIGH GPT 5.5
    # PR #85 round 3: sem L2, /sitemap-licitacoes-N.xml ainda pagaria build
    # live pos-restart embora cache exista pra outros sitemaps).
    pg_xml = _sitemap_pg_read(f"licitacoes-shard:{shard_n}")
    if pg_xml:
        _SITEMAP_CACHE["licitacoes"][shard_n] = {"ts": now, "xml": pg_xml}
        return Response(
            content=pg_xml,
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    # L3: build live
    xml = _build_licitacoes_shard_sitemap(origin, shard_n)
    urls_n = xml.count("/licitacao/")
    if urls_n > 0:
        _SITEMAP_CACHE["licitacoes"][shard_n] = {"ts": now, "xml": xml}
        # L2 nao escrita aqui (cache poisoning guard).
    elif shard_n == 1:
        _log.warning("Sitemap-licitacoes shard 1 vazio — nao cacheando")
    return Response(
        content=xml,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


# ─────────────────────────────────────────────────────────────────────────
# Cidade resumo mensal — /sitemap-cidade-resumo.xml (urlset unico, ~14k URLs)
# ─────────────────────────────────────────────────────────────────────────


def _cidade_resumo_qualificados() -> list[tuple[str, int, int]]:
    """Retorna (mun_slug, ano, mes) pra cada entrada em web_cache.

    LE DE web_cache (NAO do qualifying SQL) — garante que cada URL no
    sitemap tem cache populado. (P1 GPT 5.5 PR #108.)
    Cache key formato: "<mun_slug>:<yyyy>-<mm>". Retornamos mun_slug
    diretamente (nao precisa de slug_to_municipio).

    Anti-cache parcial: nao cachear lista vazia quando flag esta ligada.
    """
    cached = _SITEMAP_CACHE.get("cidade_resumo_list")
    now = time.time()
    if cached and (now - cached["ts"] < _SITEMAP_TTL):
        return list(cached["value"])
    try:
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT municipio FROM web_cache WHERE query_id = 'CIDADE_RESUMO_MENSAL'"
                )
                out: list[tuple[str, int, int]] = []
                for (cache_key,) in cur.fetchall():
                    if not cache_key:
                        continue
                    parts = str(cache_key).split(":", 1)
                    if len(parts) != 2:
                        continue
                    mun_slug, yyyymm = parts
                    if len(yyyymm) != 7 or yyyymm[4] != "-":
                        continue
                    try:
                        yyyy = int(yyyymm[:4])
                        mm = int(yyyymm[5:7])
                    except ValueError:
                        continue
                    out.append((mun_slug, yyyy, mm))
        flag_on = os.environ.get("SITEMAP_INCLUDE_CIDADE_RESUMO", "0") == "1"
        if out or not flag_on:
            _SITEMAP_CACHE["cidade_resumo_list"] = {"ts": now, "value": out}
        else:
            _log.warning(
                "_cidade_resumo_qualificados vazio com flag ligada — nao cacheando"
            )
        return out
    except Exception:
        _log.exception("Falha ao listar cidade-resumo em web_cache")
        return []


def _build_cidade_resumo_sitemap(origin: str) -> str:
    """urlset com /cidade/<mun_slug>/<yyyy>-<mm> pra cada entry em cache."""
    lastmod = _lastmod_iso()
    parts: list[str] = ['<?xml version="1.0" encoding="UTF-8"?>',
                        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for mun_slug, ano, mes in _cidade_resumo_qualificados():
        if not mun_slug:
            continue
        loc = f"{origin}/cidade/{mun_slug}/{ano:04d}-{mes:02d}"
        parts.append("  <url>")
        parts.append(f"    <loc>{xml_escape(loc)}</loc>")
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
        parts.append("    <changefreq>monthly</changefreq>")
        parts.append("    <priority>0.6</priority>")
        parts.append("  </url>")
    parts.append("</urlset>")
    return "\n".join(parts)


@router.get("/sitemap-cidade-resumo.xml")
async def sitemap_cidade_resumo_xml(request: Request) -> Response:
    """Sub-sitemap unico com todas as cidade-mes paginas (~14k URLs)."""
    origin = _site_origin(request)
    now = time.time()
    # L1: in-memory cache
    cached = _SITEMAP_CACHE["cidade_resumo"]
    if cached["xml"] and (now - cached["ts"] < _SITEMAP_TTL):
        return Response(
            content=cached["xml"],
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    # L2: web_cache (PG) — adicionado no rebase 2026-05-19.
    pg_xml = _sitemap_pg_read("cidade-resumo-urlset")
    if pg_xml:
        _SITEMAP_CACHE["cidade_resumo"] = {"ts": now, "xml": pg_xml}
        return Response(
            content=pg_xml,
            media_type="application/xml",
            headers={"Cache-Control": "public, max-age=3600"},
        )
    # L3: build live
    xml = _build_cidade_resumo_sitemap(origin)
    urls_n = xml.count("/cidade/")
    if urls_n > 0:
        _SITEMAP_CACHE["cidade_resumo"] = {"ts": now, "xml": xml}
        # L2 nao escrita aqui (cache poisoning guard).
    else:
        _log.warning("Sitemap-cidade-resumo vazio — nao cacheando")
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
