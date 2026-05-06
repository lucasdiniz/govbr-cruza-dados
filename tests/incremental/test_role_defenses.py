"""Phase 1a tests — defesa em camadas (DB role permissions).

Testa que etl_incremental role NÃO pode:
- TRUNCATE/DROP/DELETE em targets PB
- UPDATE/DELETE direto em audit tables
- CREATE em schema public

Testa que etl_incremental role PODE:
- SELECT em audit tables
- INSERT em targets via UPSERT
- CREATE/DROP em etl_staging
- INSERT em DLQ
- EXECUTE etl_admin SECURITY DEFINER functions

Usa SQLSTATE codes (não message strings) para ser locale-independent.
"""

from __future__ import annotations

import pytest
from .conftest import expect_pg_error


# SQLSTATE constants
INSUFFICIENT_PRIVILEGE = "42501"
RAISE_EXCEPTION = "P0001"  # RAISE EXCEPTION em plpgsql


# ─── Defesas P1 NÃO-DESTRUTIVO ─────────────────────────────────────────────────

def test_etl_role_cannot_truncate_targets(etl_conn):
    with etl_conn.cursor() as cur:
        with expect_pg_error(sqlstate=INSUFFICIENT_PRIVILEGE):
            cur.execute("TRUNCATE tce_pb_despesa")


def test_etl_role_cannot_truncate_pb_targets(etl_conn):
    with etl_conn.cursor() as cur:
        with expect_pg_error(sqlstate=INSUFFICIENT_PRIVILEGE):
            cur.execute("TRUNCATE pb_pagamento")


def test_etl_role_cannot_drop_targets(etl_conn):
    with etl_conn.cursor() as cur:
        # DROP exige ser owner — etl_incremental não é
        with expect_pg_error(sqlstate=INSUFFICIENT_PRIVILEGE):
            cur.execute("DROP TABLE tce_pb_despesa")


def test_etl_role_cannot_delete_from_targets(etl_conn):
    with etl_conn.cursor() as cur:
        with expect_pg_error(sqlstate=INSUFFICIENT_PRIVILEGE):
            cur.execute("DELETE FROM tce_pb_despesa WHERE 1=0")


def test_etl_role_cannot_delete_from_pb_targets(etl_conn):
    with etl_conn.cursor() as cur:
        with expect_pg_error(sqlstate=INSUFFICIENT_PRIVILEGE):
            cur.execute("DELETE FROM pb_pagamento WHERE 1=0")


# ─── Audit table immutability ──────────────────────────────────────────────────

def test_etl_role_cannot_update_etl_run_log(etl_conn):
    with etl_conn.cursor() as cur:
        with expect_pg_error(sqlstate=INSUFFICIENT_PRIVILEGE):
            cur.execute("UPDATE etl_run_log SET status='success' WHERE 1=0")


def test_etl_role_cannot_update_etl_watermark(etl_conn):
    with etl_conn.cursor() as cur:
        with expect_pg_error(sqlstate=INSUFFICIENT_PRIVILEGE):
            cur.execute("UPDATE etl_watermark SET last_value='x' WHERE 1=0")


def test_etl_role_cannot_update_etl_phase_log(etl_conn):
    with etl_conn.cursor() as cur:
        with expect_pg_error(sqlstate=INSUFFICIENT_PRIVILEGE):
            cur.execute("UPDATE etl_phase_log SET status='success' WHERE 1=0")


def test_etl_role_cannot_delete_etl_run_log(etl_conn):
    with etl_conn.cursor() as cur:
        with expect_pg_error(sqlstate=INSUFFICIENT_PRIVILEGE):
            cur.execute("DELETE FROM etl_run_log WHERE 1=0")


def test_etl_role_cannot_delete_dlq(etl_conn):
    """DLQ tem INSERT grant mas não DELETE → falha na permissão (antes do trigger)."""
    with etl_conn.cursor() as cur:
        with expect_pg_error(sqlstate=INSUFFICIENT_PRIVILEGE):
            cur.execute("DELETE FROM etl_rejected_rows WHERE 1=0")


def test_etl_role_cannot_delete_download_log(etl_conn):
    """download_log tem SELECT only para etl_incremental."""
    with etl_conn.cursor() as cur:
        with expect_pg_error(sqlstate=INSUFFICIENT_PRIVILEGE):
            cur.execute("DELETE FROM etl_download_log WHERE 1=0")


# ─── Schema permissions ────────────────────────────────────────────────────────

def test_etl_role_cannot_create_in_public(etl_conn):
    with etl_conn.cursor() as cur:
        with expect_pg_error(sqlstate=INSUFFICIENT_PRIVILEGE):
            cur.execute("CREATE TABLE _etl_evil (a int)")


def test_etl_role_can_create_in_etl_staging(etl_conn):
    """Cleanup explícito — ok porque é dono da própria tabela em etl_staging."""
    with etl_conn.cursor() as cur:
        cur.execute("CREATE TABLE etl_staging._stg_smoke_test (a int)")
        cur.execute("DROP TABLE etl_staging._stg_smoke_test")
    etl_conn.commit()


def test_etl_role_search_path_locked(etl_conn):
    """search_path inclui public, etl_staging, pg_catalog."""
    with etl_conn.cursor() as cur:
        cur.execute("SHOW search_path")
        path = cur.fetchone()[0]
    assert "etl_staging" in path
    assert "public" in path


# ─── Read access ───────────────────────────────────────────────────────────────

def test_etl_role_can_select_audit_tables(etl_conn):
    """SELECT funciona em todas audit tables."""
    with etl_conn.cursor() as cur:
        for tbl in [
            "etl_watermark", "etl_run_log", "etl_phase_log",
            "etl_rejected_rows", "etl_download_log",
        ]:
            cur.execute(f"SELECT count(*) FROM {tbl}")
            assert cur.fetchone()[0] >= 0


# ─── INSERT access ─────────────────────────────────────────────────────────────

def test_etl_role_can_insert_into_targets(etl_conn):
    """INSERT em target funciona; rollback (etl_incremental não tem DELETE)."""
    with etl_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO tce_pb_despesa (municipio) VALUES ('TEST_PHASE_1A')"
        )
    etl_conn.rollback()


def test_etl_role_can_insert_into_dlq(etl_conn):
    """INSERT direto em DLQ funciona (autocommit pattern)."""
    with etl_conn.cursor() as cur:
        cur.execute(
            """INSERT INTO etl_rejected_rows
               (run_id, source, table_name, file_path, line_number, raw_line_hash, reason)
               VALUES (%s, 'tce_pb', 'tce_pb_despesa', 'foo.csv', 1, %s, 'col_count_mismatch')""",
            ("00000000-0000-0000-0000-000000000099", "hash_test_p1a"),
        )
    etl_conn.rollback()
