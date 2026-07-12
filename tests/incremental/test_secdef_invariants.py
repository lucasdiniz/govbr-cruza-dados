"""Phase 1a tests — SECURITY DEFINER functions em etl_admin.

Valida invariantes:
- search_path locked em todas funções (R6 BLOCKING fix — security)
- start_run / heartbeat_run / finish_run lifecycle correto
- set_watermark: type-aware monotonicity, idempotent via bucket_token, fence check
- reset_watermark: requires reason + approver
- Triggers de imutabilidade em etl_watermark.bootstrap_*
- etl_phase_log e etl_run_log immutability
- DLQ partition setup
"""

from __future__ import annotations

import uuid

import pytest
from .conftest import expect_pg_error


# SQLSTATE
RAISE_EXCEPTION = "P0001"
CHECK_VIOLATION = "23514"


# ─── search_path locked (R6 BLOCKING) ─────────────────────────────────────────

def test_security_definer_functions_have_locked_search_path(govbr_conn):
    """Toda função SECURITY DEFINER em etl_admin trava o search_path."""
    with govbr_conn.cursor() as cur:
        cur.execute(
            """
            SELECT p.proname,
                   array_to_string(p.proconfig, ',') AS cfg
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'etl_admin'
              AND p.prosecdef
            ORDER BY p.proname
            """
        )
        rows = cur.fetchall()
    assert len(rows) >= 13, f"Expected >=13 etl_admin functions, got {len(rows)}"
    missing = [r[0] for r in rows if not r[1] or "search_path" not in r[1]]
    assert not missing, f"Functions without locked search_path: {missing}"


# ─── start_run / lifecycle ─────────────────────────────────────────────────────

def test_start_run_creates_running_row(govbr_autocommit_conn):
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.start_run('incremental', 'pytest:start_run', NULL)"
        )
        rid = cur.fetchone()[0]
        cur.execute(
            "SELECT mode, status, triggered_by FROM etl_run_log WHERE run_id = %s",
            (str(rid),),
        )
        row = cur.fetchone()
        assert row == ("incremental", "running", "pytest:start_run")
        cur.execute("DELETE FROM etl_run_log WHERE run_id = %s", (str(rid),))


def test_start_run_rejects_invalid_mode(govbr_autocommit_conn):
    with govbr_autocommit_conn.cursor() as cur:
        with expect_pg_error(sqlstate=RAISE_EXCEPTION):
            cur.execute("SELECT etl_admin.start_run('invalid_mode', 'p', NULL)")


def test_finish_run_rejects_invalid_status(run_id, govbr_autocommit_conn):
    with govbr_autocommit_conn.cursor() as cur:
        with expect_pg_error(sqlstate=RAISE_EXCEPTION):
            cur.execute(
                "SELECT etl_admin.finish_run(%s, 'totally_invalid', NULL)",
                (str(run_id),),
            )


def test_finish_run_rejects_invalid_transition(govbr_autocommit_conn):
    """success → success is NOT valid (terminal status reached)."""
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.start_run('incremental', 'pytest:transition', NULL)"
        )
        rid = cur.fetchone()[0]
        cur.execute("SELECT etl_admin.finish_run(%s, 'success', NULL)", (str(rid),))
        # Now try finish again — should fail
        with expect_pg_error(sqlstate=RAISE_EXCEPTION):
            cur.execute(
                "SELECT etl_admin.finish_run(%s, 'failed', NULL)", (str(rid),)
            )
        cur.execute("DELETE FROM etl_run_log WHERE run_id = %s", (str(rid),))


def test_heartbeat_run_returns_true_for_running(run_id, govbr_autocommit_conn):
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute("SELECT etl_admin.heartbeat_run(%s)", (str(run_id),))
        assert cur.fetchone()[0] is True


def test_heartbeat_run_returns_false_for_finished(govbr_autocommit_conn):
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.start_run('incremental', 'pytest:hb_finish', NULL)"
        )
        rid = cur.fetchone()[0]
        cur.execute("SELECT etl_admin.finish_run(%s, 'success', NULL)", (str(rid),))
        cur.execute("SELECT etl_admin.heartbeat_run(%s)", (str(rid),))
        assert cur.fetchone()[0] is False
        cur.execute("DELETE FROM etl_run_log WHERE run_id = %s", (str(rid),))


def test_abort_stale_runs_marks_old_runs(govbr_autocommit_conn):
    """Stale run (last_heartbeat antigo) é marcada como aborted."""
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.start_run('incremental', 'pytest:stale', NULL)"
        )
        rid = cur.fetchone()[0]
        # Setar AMBOS started_at e last_heartbeat antigos (CHECK requer hb >= start)
        cur.execute(
            """UPDATE etl_run_log
               SET started_at = now() - INTERVAL '20 minutes',
                   last_heartbeat = now() - INTERVAL '10 minutes'
               WHERE run_id = %s""",
            (str(rid),),
        )
        cur.execute("SELECT etl_admin.abort_stale_runs(5)")
        count = cur.fetchone()[0]
        assert count >= 1
        cur.execute(
            "SELECT status FROM etl_run_log WHERE run_id = %s", (str(rid),)
        )
        assert cur.fetchone()[0] == "aborted"
        cur.execute("DELETE FROM etl_run_log WHERE run_id = %s", (str(rid),))


# ─── set_watermark: monotonicity + idempotency + fence ────────────────────────

def test_set_watermark_first_advance_returns_true(
    run_id, govbr_autocommit_conn, cleanup_test_source
):
    cleanup_test_source("test_set_wm", "tbl1")
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            """SELECT etl_admin.set_watermark(
                %s, 'test_set_wm', 'tbl1',
                %s, '2024', 'integer', '2024', 100
            )""",
            (str(run_id), str(uuid.uuid4())),
        )
        assert cur.fetchone()[0] is True


def test_set_watermark_idempotent_via_bucket_token(
    run_id, govbr_autocommit_conn, cleanup_test_source
):
    cleanup_test_source("test_idem", "tbl1")
    token = str(uuid.uuid4())
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.set_watermark(%s, 'test_idem', 'tbl1', %s, '2024', 'integer', '2024', 100)",
            (str(run_id), token),
        )
        assert cur.fetchone()[0] is True
        # Retry com mesmo token — NO-OP
        cur.execute(
            "SELECT etl_admin.set_watermark(%s, 'test_idem', 'tbl1', %s, '2025', 'integer', '2025', 200)",
            (str(run_id), token),
        )
        assert cur.fetchone()[0] is False


def test_set_watermark_type_aware_integer_no_lex(
    run_id, govbr_autocommit_conn, cleanup_test_source
):
    """'10' > '2025' lex-string seria True; integer-aware deve ser False."""
    cleanup_test_source("test_int", "tbl1")
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.set_watermark(%s, 'test_int', 'tbl1', %s, '2025', 'integer', '2025', 100)",
            (str(run_id), str(uuid.uuid4())),
        )
        assert cur.fetchone()[0] is True
        # Tentar retroceder pra '10' (que é lex > '2025' mas integer < 2025)
        cur.execute(
            "SELECT etl_admin.set_watermark(%s, 'test_int', 'tbl1', %s, '10', 'integer', '10', 50)",
            (str(run_id), str(uuid.uuid4())),
        )
        assert cur.fetchone()[0] is False


def test_set_watermark_type_aware_timestamp(
    run_id, govbr_autocommit_conn, cleanup_test_source
):
    cleanup_test_source("test_ts", "tbl1")
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.set_watermark(%s, 'test_ts', 'tbl1', %s, %s, 'timestamp', %s, 100)",
            (str(run_id), str(uuid.uuid4()),
             "2025-03-15 10:00:00+00", "2025-03-15 10:00:00+00"),
        )
        assert cur.fetchone()[0] is True
        # Earlier timestamp — should NOT advance
        cur.execute(
            "SELECT etl_admin.set_watermark(%s, 'test_ts', 'tbl1', %s, %s, 'timestamp', %s, 100)",
            (str(run_id), str(uuid.uuid4()),
             "2024-01-01 00:00:00+00", "2024-01-01 00:00:00+00"),
        )
        assert cur.fetchone()[0] is False


def test_set_watermark_fence_rejects_non_running_run(
    govbr_autocommit_conn, cleanup_test_source
):
    """set_watermark em run finished → exception (fence)."""
    cleanup_test_source("test_fence", "tbl1")
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.start_run('incremental', 'pytest:fence', NULL)"
        )
        rid = cur.fetchone()[0]
        cur.execute("SELECT etl_admin.finish_run(%s, 'success', NULL)", (str(rid),))
        with expect_pg_error(sqlstate=RAISE_EXCEPTION):
            cur.execute(
                "SELECT etl_admin.set_watermark(%s, 'test_fence', 'tbl1', %s, '2024', 'integer', '2024', 100)",
                (str(rid), str(uuid.uuid4())),
            )
        cur.execute("DELETE FROM etl_run_log WHERE run_id = %s", (str(rid),))


def test_set_watermark_invalid_watermark_type(
    run_id, govbr_autocommit_conn, cleanup_test_source
):
    cleanup_test_source("test_invalid_wt", "tbl1")
    with govbr_autocommit_conn.cursor() as cur:
        with expect_pg_error(sqlstate=RAISE_EXCEPTION):
            cur.execute(
                "SELECT etl_admin.set_watermark(%s, 'test_invalid_wt', 'tbl1', %s, '2024', 'BOGUS', '2024', 100)",
                (str(run_id), str(uuid.uuid4())),
            )


# ─── reset_watermark ──────────────────────────────────────────────────────────

def test_reset_watermark_requires_long_reason(
    govbr_autocommit_conn, cleanup_test_source
):
    cleanup_test_source("test_reset", "tbl1")
    with govbr_autocommit_conn.cursor() as cur:
        # Setup: criar watermark
        cur.execute(
            "INSERT INTO etl_watermark (source, table_name, last_value, watermark_type) VALUES ('test_reset', 'tbl1', '500', 'integer')"
        )
        # Reason muito curto
        with expect_pg_error(sqlstate=RAISE_EXCEPTION):
            cur.execute(
                "SELECT etl_admin.reset_watermark('test_reset', 'tbl1', '100', 'short', 'admin')"
            )


def test_reset_watermark_valid_creates_audit_row(
    govbr_autocommit_conn, cleanup_test_source
):
    cleanup_test_source("test_reset_ok", "tbl1")
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO etl_watermark (source, table_name, last_value, watermark_type) VALUES ('test_reset_ok', 'tbl1', '500', 'integer')"
        )
        cur.execute(
            "SELECT etl_admin.reset_watermark('test_reset_ok', 'tbl1', '100', 'recovery from corruption', 'admin')"
        )
        # Audit row criada
        cur.execute(
            "SELECT mode FROM etl_run_log WHERE error_message LIKE %s",
            ("%test_reset_ok%",),
        )
        rows = cur.fetchall()
        assert len(rows) >= 1
        assert rows[0][0] == "manual_reset"
        # Cleanup das audit rows
        cur.execute(
            "DELETE FROM etl_run_log WHERE error_message LIKE %s",
            ("%test_reset_ok%",),
        )


# ─── etl_watermark immutability ────────────────────────────────────────────────

def test_etl_watermark_bootstrap_fields_immutable(
    govbr_autocommit_conn, cleanup_test_source
):
    cleanup_test_source("test_imm", "tbl1")
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            """INSERT INTO etl_watermark
               (source, table_name, bootstrap_target_max, bootstrap_target_count, bootstrapped_at)
               VALUES ('test_imm', 'tbl1', '999', 1000, '2026-01-01 00:00:00+00')"""
        )
        # Tentar atualizar bootstrap_target_max
        with expect_pg_error(sqlstate=RAISE_EXCEPTION):
            cur.execute(
                "UPDATE etl_watermark SET bootstrap_target_max='888' WHERE source='test_imm'"
            )


def test_etl_watermark_bootstrap_count_immutable(
    govbr_autocommit_conn, cleanup_test_source
):
    cleanup_test_source("test_imm2", "tbl1")
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            """INSERT INTO etl_watermark
               (source, table_name, bootstrap_target_max, bootstrap_target_count, bootstrapped_at)
               VALUES ('test_imm2', 'tbl1', '999', 1000, '2026-01-01 00:00:00+00')"""
        )
        with expect_pg_error(sqlstate=RAISE_EXCEPTION):
            cur.execute(
                "UPDATE etl_watermark SET bootstrap_target_count=2000 WHERE source='test_imm2'"
            )


# ─── DLQ partition setup ──────────────────────────────────────────────────────

def test_dlq_partition_default_exists(govbr_conn):
    with govbr_conn.cursor() as cur:
        cur.execute(
            """SELECT EXISTS (SELECT 1 FROM pg_class
                            WHERE relname = 'etl_rejected_rows_default')"""
        )
        assert cur.fetchone()[0] is True


def test_dlq_has_tce_pb_and_dados_pb_partitions(govbr_conn):
    with govbr_conn.cursor() as cur:
        cur.execute(
            """SELECT c.relname FROM pg_inherits i
               JOIN pg_class c ON c.oid = i.inhrelid
               WHERE i.inhparent = 'etl_rejected_rows'::regclass
               ORDER BY c.relname"""
        )
        partitions = [r[0] for r in cur.fetchall()]
    assert "etl_rejected_rows_tce_pb" in partitions
    assert "etl_rejected_rows_dados_pb" in partitions
    assert "etl_rejected_rows_default" in partitions


def test_dlq_dedupe_via_unique_idempotent(govbr_autocommit_conn):
    """ON CONFLICT DO NOTHING dedupe funciona em retries."""
    with govbr_autocommit_conn.cursor() as cur:
        rid = "00000000-0000-0000-0000-000000000077"
        cur.execute(
            """INSERT INTO etl_rejected_rows
               (run_id, source, table_name, file_path, line_number, raw_line_hash, reason)
               VALUES (%s, 'tce_pb', 'tce_pb_despesa', 'dedup.csv', 10, 'h_dedup', 'col_count_mismatch')""",
            (rid,),
        )
        # Retry idempotente
        cur.execute(
            """INSERT INTO etl_rejected_rows
               (run_id, source, table_name, file_path, line_number, raw_line_hash, reason)
               VALUES (%s, 'tce_pb', 'tce_pb_despesa', 'dedup.csv', 10, 'h_dedup', 'col_count_mismatch')
               ON CONFLICT (source, table_name, file_path, line_number, raw_line_hash) DO NOTHING""",
            (rid,),
        )
        cur.execute(
            "SELECT count(*) FROM etl_rejected_rows WHERE raw_line_hash='h_dedup'"
        )
        assert cur.fetchone()[0] == 1
        # Cleanup
        cur.execute("DELETE FROM etl_rejected_rows_tce_pb WHERE raw_line_hash='h_dedup'")
