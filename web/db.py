"""Pool de conexoes e helpers de execucao para o frontend."""

from __future__ import annotations

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


def read_web_cache(query_id: str, municipio: str) -> tuple[list[str], list[tuple]] | None:
    """Le resultado pre-processado de web_cache. Retorna None se nao existir."""
    try:
        with get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT columns, rows FROM web_cache WHERE query_id = %s AND municipio = %s",
                    (query_id, municipio),
                )
                row = cur.fetchone()
                if row:
                    cols = row[0] if isinstance(row[0], list) else []
                    rows = [tuple(r) for r in row[1]] if isinstance(row[1], list) else []
                    return cols, rows
    except Exception:
        pass
    return None
