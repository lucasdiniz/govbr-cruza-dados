"""Helpers de slug pra URLs amigaveis de municipio.

Geram e resolvem slugs como "joao-pessoa", "santa-rita", "campina-grande".
Cache em memoria mapeia slug -> nome canonico (com acento) consultando
mv_municipio_pb_risco. TTL 1h: nome canonico nao muda na pratica, mas
permite recovery se cache fica stale apos refresh de dados.

Uso:
    from web.utils.slug import municipio_slug, slug_to_municipio, SlugLookupError

    municipio_slug("Joao Pessoa")            # "joao-pessoa"
    slug_to_municipio("joao-pessoa")         # "Joao Pessoa" (canonico)
    slug_to_municipio("nao-existe")          # None
    # Levanta SlugLookupError quando cache vazio + DB indisponivel.
"""
from __future__ import annotations

import logging
import re
import threading
import time
import unicodedata

from web import db


_log = logging.getLogger("transparencia.slug")


class SlugLookupError(RuntimeError):
    """Cache vazio + impossivel consultar o DB. Sinaliza erro de
    infraestrutura (deve virar HTTP 503), nao slug inexistente (404)."""


# Cache thread-safe: slug -> nome canonico. Carregado on-demand.
_LOCK = threading.Lock()
_CACHE: dict[str, str] = {}
_CACHE_TS: float = 0.0
_CACHE_TTL = 3600  # 1h

# Regex pra colapsar runs de hifens/whitespace em um unico "-"
_DASH_RUN = re.compile(r"[-\s]+")
# Caracteres permitidos no slug final (alfanumericos ASCII + hifen)
_NON_SLUG = re.compile(r"[^a-z0-9-]+")


def municipio_slug(name: str) -> str:
    """Converte nome de municipio em slug URL-safe.

    >>> municipio_slug("Joao Pessoa")
    'joao-pessoa'
    >>> municipio_slug("Sao Joao do Rio do Peixe")
    'sao-joao-do-rio-do-peixe'
    >>> municipio_slug("D'Avila")
    'davila'
    >>> municipio_slug("  Espacos   demais  ")
    'espacos-demais'
    """
    if not name:
        return ""
    # NFKD strip de acentos
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    n = n.lower()
    # Espacos viram hifens, multi viram um so
    n = _DASH_RUN.sub("-", n)
    # Drop caracteres nao-slug (apostrofes, parenteses, etc.)
    n = _NON_SLUG.sub("", n)
    # Trim hifens das pontas
    return n.strip("-")


def _load_cache() -> dict[str, str]:
    """Carrega slug -> nome canonico do banco.

    Levanta a excecao original do psycopg2/db em erro de DB — caller
    decide se ignora (stale cache) ou propaga (cold start).

    ORDER BY municipio garante determinismo em colisoes (extremamente
    improvaveis em PB, mas defensivo). Logamos warning quando 2 municipios
    diferentes geram o mesmo slug pra detectar bugs de dados na MV.
    """
    sql = """
        SELECT municipio FROM mv_municipio_pb_risco
        WHERE municipio IS NOT NULL
        ORDER BY municipio
    """
    cache: dict[str, str] = {}
    with db.get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)
            for (mun,) in cur.fetchall():
                if not mun:
                    continue
                slug = municipio_slug(mun)
                if not slug:
                    continue
                if slug in cache and cache[slug] != mun:
                    _log.warning(
                        "Slug colision: %r mapeia tanto para %r quanto para %r — "
                        "mantendo %r (ordem alfabetica). Verifique mv_municipio_pb_risco.",
                        slug, cache[slug], mun, cache[slug],
                    )
                    continue
                cache[slug] = str(mun)
    return cache


def _ensure_cache() -> dict[str, str]:
    """Carrega ou recarrega o cache se TTL expirou. Thread-safe.

    Politica:
    - Cache fresco (TTL nao expirou) -> retorna sem ir ao DB.
    - Cache expirado mas existe -> tenta recarregar; em erro, mantem stale
      (nao penaliza usuario por refresh transitoriamente falho).
    - Cache vazio + DB falha -> levanta SlugLookupError (cold start).
    """
    global _CACHE, _CACHE_TS
    now = time.time()
    if _CACHE and (now - _CACHE_TS) < _CACHE_TTL:
        return _CACHE
    with _LOCK:
        # Re-check apos acquire (outro thread pode ter recarregado)
        if _CACHE and (time.time() - _CACHE_TS) < _CACHE_TTL:
            return _CACHE
        try:
            new_cache = _load_cache()
        except Exception as exc:
            if _CACHE:
                # Stale-while-error: serve cache antigo, loga warning
                _log.warning(
                    "Falha ao recarregar slug cache (%s) — servindo cache antigo (%d entradas)",
                    exc, len(_CACHE),
                )
                return _CACHE
            # Cold start sem cache: erro de infra -> caller deve dar 503
            _log.exception("Falha ao carregar slug cache (cold start, sem fallback)")
            raise SlugLookupError(str(exc)) from exc
        if new_cache:
            _CACHE = new_cache
            _CACHE_TS = time.time()
            _log.info("Slug cache carregado: %d municipios", len(new_cache))
        return _CACHE


def slug_to_municipio(slug: str) -> str | None:
    """Resolve slug -> nome canonico. None se slug nao existe.

    Lookup tolerante: chamadores podem passar 'Joao-Pessoa', 'joao-pessoa',
    'joão-pessoa' indistintamente — todos sao normalizados pra forma
    canonica antes do lookup.

    Levanta SlugLookupError quando cache vazio + DB indisponivel (caller
    deve responder HTTP 503, nao 404).
    """
    if not slug:
        return None
    norm = municipio_slug(slug)
    if not norm:
        return None
    cache = _ensure_cache()
    return cache.get(norm)


def invalidate_cache() -> None:
    """Forca recarga no proximo lookup. Util pra testes / pos-refresh de dados."""
    global _CACHE, _CACHE_TS
    with _LOCK:
        _CACHE = {}
        _CACHE_TS = 0.0


def all_municipios_slugged() -> dict[str, str]:
    """Retorna copia do cache atual: slug -> nome canonico.

    Para uso em sitemap (precisa enumerar todas as cidades + slug).
    Levanta SlugLookupError no cold start sem fallback.
    """
    return dict(_ensure_cache())


# ─────────────────────────────────────────────────────────────────────────
# Helpers pra paginas de transacao publica (/licitacao, /cidade/<slug>/<yyyy-mm>)
# ─────────────────────────────────────────────────────────────────────────


_YYYY_MM_RE = re.compile(r"^(?P<yyyy>\d{4})-(?P<mm>\d{2})$")


def numero_slug(numero: str) -> str:
    """Slug pra numero_licitacao / numero_empenho: lowercase, dedup hifens.

    TCE-PB tem formatos variados: '001/2025', '2025NE000282', '00028-2025',
    'PP 001/2024'. Normalizamos canonicamente pra string URL-safe.

    >>> numero_slug('001/2025')
    '001-2025'
    >>> numero_slug('PP 001/2024')
    'pp-001-2024'
    >>> numero_slug('2025NE000282')
    '2025ne000282'
    """
    if not numero:
        return ""
    s = str(numero).lower().strip()
    # Remove acentos (raro mas defensive)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    # Tudo nao-alfanumerico vira hifen
    s = re.sub(r"[^a-z0-9]+", "-", s)
    # Dedupe hifens
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def parse_yyyymm(s: str) -> tuple[int, int] | None:
    """Parse '<yyyy>-<mm>' com bounds 2018-2099 / 01-12.

    Retorna (yyyy, mm) int ou None se invalido. Usado pela rota
    /cidade/<slug>/<yyyy>-<mm> e pela parsing de mes em sitemap.

    >>> parse_yyyymm('2024-03')
    (2024, 3)
    >>> parse_yyyymm('2030-12')
    (2030, 12)
    >>> parse_yyyymm('2024-13')
    >>> parse_yyyymm('99-03')
    >>> parse_yyyymm('2024-3')
    """
    if not s:
        return None
    m = _YYYY_MM_RE.fullmatch(str(s).strip())
    if not m:
        return None
    yyyy = int(m.group("yyyy"))
    mm = int(m.group("mm"))
    if not (2018 <= yyyy <= 2099):
        return None
    if not (1 <= mm <= 12):
        return None
    return yyyy, mm


def format_yyyymm(yyyy: int, mm: int) -> str:
    """Format inverso pro path canonico.

    >>> format_yyyymm(2024, 3)
    '2024-03'
    """
    return f"{yyyy:04d}-{mm:02d}"
