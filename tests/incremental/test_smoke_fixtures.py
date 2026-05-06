"""Smoke test: valida que fixtures e DB local estão prontos."""

from __future__ import annotations


def test_schema_ready_fixture_works(schema_ready):
    """Smoke: schema_ready fixture só passa se migrations aplicadas."""
    pass


def test_govbr_conn_can_query(govbr_conn):
    """govbr role pode fazer SELECT em audit table."""
    with govbr_conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM etl_run_log")
        assert cur.fetchone()[0] >= 0


def test_etl_role_exists_and_logs_in(etl_conn):
    """etl_incremental role conecta com sucesso."""
    with etl_conn.cursor() as cur:
        cur.execute("SELECT current_user")
        assert cur.fetchone()[0] == "etl_incremental"


def test_run_id_fixture_creates_and_cleans_up(run_id, govbr_autocommit_conn):
    """Fixture run_id cria run válida; cleanup acontece após teste."""
    assert run_id is not None
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute("SELECT status FROM etl_run_log WHERE run_id = %s", (str(run_id),))
        row = cur.fetchone()
        assert row is not None
        assert row[0] == "running"
