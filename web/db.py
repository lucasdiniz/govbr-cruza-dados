"""Pool de conexoes e helpers de execucao para o frontend."""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any

import psycopg2
from psycopg2 import Error as PsycopgError
from psycopg2.pool import ThreadedConnectionPool

from etl.config import DSN
from web.config import POOL_MIN, POOL_MAX, CACHE_TTL

_pool: ThreadedConnectionPool | None = None
_cache: dict[str, tuple[float, Any]] = {}


def init_pool():
    global _pool
    _pool = ThreadedConnectionPool(POOL_MIN, POOL_MAX, DSN)


def close_pool():
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None


@contextmanager
def get_conn():
    if _pool is None:
        raise RuntimeError("Connection pool not initialized")
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


def execute_query(
    sql: str,
    params: dict | None = None,
    timeout_sec: int = 15,
) -> tuple[list[str], list[tuple]]:
    """Executa query com timeout. Retorna (colunas, rows)."""
    with get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            try:
                cur.execute(f"SET statement_timeout = '{timeout_sec * 1000}'")
                cur.execute(sql, params)
                cols = [d[0] for d in cur.description] if cur.description else []
                rows = cur.fetchall() if cur.description else []
                return cols, rows
            finally:
                try:
                    cur.execute("RESET statement_timeout")
                except PsycopgError:
                    conn.rollback()


def invalidate_cache(prefix: str | None = None) -> None:
    """Limpa o cache inteiro ou apenas chaves com prefixo."""
    if prefix is None:
        _cache.clear()
        return
    for key in list(_cache):
        if key.startswith(prefix):
            del _cache[key]


def cached_query(
    key: str,
    sql: str,
    params: dict | None = None,
    timeout_sec: int = 15,
    ttl: int = CACHE_TTL,
) -> tuple[list[str], list[tuple]]:
    """Execute query com cache in-memory por TTL."""
    now = time.time()
    if key in _cache:
        ts, result = _cache[key]
        if now - ts < ttl:
            return result
    result = execute_query(sql, params, timeout_sec)
    _cache[key] = (now, result)
    return result


class _CacheError:
    """Sentinel singleton retornado por read_web_cache quando lookup falha
    por erro de DB/conexao (pool exhausted, statement_timeout, conn error,
    JSON corrompido).

    Diferenciar erro de "row ausente" e crucial para a rota /empresa/<cnpj>
    decidir entre 410 Gone (URL permanentemente removida — row ausente
    pos-cleanup) e 503 Service Unavailable (erro transiente — qualifying
    empresa pode estar com cache temporariamente inacessivel).

    Sem este sentinel, `read_web_cache` retornava None para ambos os casos
    e a rota tratava DB error como cache miss permanente, marcando URLs
    legitimas como 410 Gone durante pool exhaustion / restart / failover.
    (HIGH bug identificado em revisao paralela Opus 4.7-high + GPT-5.5
    do PR #181.)

    Backward compat: callers legados em cidade.py/licitacao.py/warm_cache.py
    fazem `if cached is not None: cols, rows = cached`. Para nao quebra-los
    com TypeError no unpack, `_CacheError` e iteravel e desempacota como
    `([], [])` — caem naturalmente no path existente de "cache miss
    vazio -> 503". Callers que querem distinguir erro vs miss permanente
    (rotas empresa.py) checam `is CACHE_ERROR` ANTES do unpack.
    """
    __slots__ = ()
    def __repr__(self) -> str:
        return "<CacheError>"
    def __iter__(self):
        # Permite `cols, rows = CACHE_ERROR` -> ([], []) sem quebrar
        # callers legados. Equivalente semanticamente a "cache miss" para
        # quem nao distingue erro de miss permanente.
        yield []
        yield []
    def __bool__(self) -> bool:
        # `if cached:` treat as falsy (cache miss equivalente para legados).
        return False


CACHE_ERROR = _CacheError()


def read_web_cache(query_id: str, municipio: str, periodo: str = "") -> tuple[list[str], list[tuple]] | _CacheError | None:
    """Le resultado pre-processado de web_cache.

    Retorna:
    - `tuple[cols, rows]` se entry existe (rows pode estar vazia para soft-miss).
    - `None` se row genuinamente ausente (cache miss permanente).
    - `CACHE_ERROR` (sentinel) se lookup falhou por erro de DB/conexao.

    O caller deve diferenciar None (miss permanente -> 410 Gone) de
    CACHE_ERROR (transiente -> 503 Retry-After). Antes desta mudanca,
    bare `except Exception: pass; return None` tornava DB errors
    indistinguiveis de cache miss; rotas /empresa retornavam 410 em
    ambos os casos, marcando URLs legitimas como permanentemente
    removidas durante incidentes transientes do DB.

    periodo: prefixo temporal (ex: 'ANO'). Se informado, busca '{periodo}:{query_id}'.
    """
    effective_qid = f"{periodo}:{query_id}" if periodo else query_id
    try:
        with get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT columns, rows FROM web_cache WHERE query_id = %s AND municipio = %s",
                    (effective_qid, municipio),
                )
                row = cur.fetchone()
                if row:
                    cols = row[0] if isinstance(row[0], list) else []
                    rows = [tuple(r) for r in row[1]] if isinstance(row[1], list) else []
                    return cols, rows
    except Exception as e:
        # Log com WARNING (visivel em journalctl) — antes era silencioso
        # via `pass`, dificultando diagnostico de incidentes.
        logging.getLogger("transparencia.db").warning(
            "read_web_cache DB error for %s:%s — %s: %s",
            effective_qid, municipio, type(e).__name__, e,
        )
        return CACHE_ERROR
    return None
