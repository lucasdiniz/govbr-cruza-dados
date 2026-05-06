"""pytest fixtures para tests do ETL incremental.

Roles:
- govbr (superuser local): cleanup, INSERT em audit tables direto se necessário
- etl_incremental: simula identidade real do ETL em produção (defesa em camadas)

DSN configurável via env vars TEST_GOVBR_DSN / TEST_ETL_DSN.
Default: kong1029 password compartilhada por govbr/postgres no DB local.
"""

from __future__ import annotations

import os
from contextlib import contextmanager

import psycopg2
import pytest


GOVBR_DSN = os.environ.get(
    "TEST_GOVBR_DSN",
    "host=localhost port=5432 dbname=govbr user=govbr password=kong1029",
)
ETL_DSN = os.environ.get(
    "TEST_ETL_DSN",
    "host=localhost port=5432 dbname=govbr user=etl_incremental password=etl_incremental_dev",
)


def _new_conn(dsn: str, autocommit: bool = False):
    conn = psycopg2.connect(dsn)
    conn.set_client_encoding("UTF8")
    conn.autocommit = autocommit
    return conn


@pytest.fixture(scope="session")
def schema_ready():
    """Verifica que migrations 22-29 foram aplicadas. Skip session inteira se não."""
    conn = _new_conn(GOVBR_DSN, autocommit=True)
    try:
        with conn.cursor() as cur:
            required = [
                "etl_watermark", "etl_run_log", "etl_phase_log",
                "etl_rejected_rows", "etl_download_log",
            ]
            for tbl in required:
                cur.execute("SELECT to_regclass(%s)", (tbl,))
                if cur.fetchone()[0] is None:
                    pytest.skip(f"Migration not applied: {tbl} missing")
            cur.execute(
                "SELECT count(*) FROM pg_namespace WHERE nspname IN ('etl_admin', 'etl_staging')"
            )
            if cur.fetchone()[0] < 2:
                pytest.skip("Schemas etl_admin/etl_staging missing")
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname='etl_incremental'")
            if cur.fetchone() is None:
                pytest.skip("Role etl_incremental missing")
    finally:
        conn.close()


@pytest.fixture
def govbr_conn(schema_ready):
    """Connection superuser para setup/teardown e queries privilegiadas."""
    conn = _new_conn(GOVBR_DSN, autocommit=False)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def govbr_autocommit_conn(schema_ready):
    """Connection superuser autocommit para cleanup e operações DDL."""
    conn = _new_conn(GOVBR_DSN, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def etl_conn(schema_ready):
    """Connection com role etl_incremental — simula identidade real do ETL."""
    conn = _new_conn(ETL_DSN, autocommit=False)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()


@pytest.fixture
def etl_autocommit_conn(schema_ready):
    """Connection etl_incremental autocommit (DLQ pattern)."""
    conn = _new_conn(ETL_DSN, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def run_id(govbr_autocommit_conn):
    """Cria uma run via etl_admin.start_run e cleanup ao fim."""
    rid = None
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.start_run('incremental', %s, NULL)",
            (f"pytest:{os.getpid()}",),
        )
        rid = cur.fetchone()[0]
    yield rid
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute("DELETE FROM etl_phase_log WHERE run_id = %s", (str(rid),))
        cur.execute("DELETE FROM etl_run_log WHERE run_id = %s", (str(rid),))


@pytest.fixture
def cleanup_test_source(govbr_autocommit_conn):
    """
    Yields callable que registra (source, table) para cleanup ao fim.
    """
    registered: list[tuple[str, str]] = []

    def _register(source: str, table: str):
        registered.append((source, table))

    yield _register

    for src, tbl in registered:
        try:
            with govbr_autocommit_conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM etl_phase_log WHERE source = %s AND table_name = %s",
                    (src, tbl),
                )
                cur.execute(
                    "DELETE FROM etl_watermark WHERE source = %s AND table_name = %s",
                    (src, tbl),
                )
                cur.execute(
                    "DELETE FROM etl_rejected_rows WHERE source = %s AND table_name = %s",
                    (src, tbl),
                )
                cur.execute(
                    "DELETE FROM etl_download_log WHERE source = %s AND table_name = %s",
                    (src, tbl),
                )
        except psycopg2.Error:
            pass


@contextmanager
def expect_pg_error(error_substring: str = None, *, sqlstate: str = None):
    """Context manager: assert que o bloco levanta psycopg2.Error.

    Usar `sqlstate` (preferido — locale-independent) OU `error_substring`.
    SQLSTATE codes comuns:
      42501 = insufficient_privilege (permission denied / must be owner)
      P0001 = raise_exception (RAISE EXCEPTION em plpgsql)
      23514 = check_violation
      23505 = unique_violation
    """
    try:
        yield
        raise AssertionError(
            f"Expected psycopg2.Error (sqlstate={sqlstate}, substring={error_substring})"
        )
    except psycopg2.Error as e:
        if sqlstate is not None:
            actual = getattr(e, "pgcode", None)
            if actual != sqlstate:
                raise AssertionError(
                    f"Expected SQLSTATE {sqlstate} but got {actual}: {e}"
                ) from e
        elif error_substring is not None:
            msg = str(e)
            if error_substring not in msg:
                raise AssertionError(
                    f"Expected error containing '{error_substring}' but got: {msg}"
                ) from e
