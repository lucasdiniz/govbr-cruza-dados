"""Phase 1a tests — etl_download_log + invalidate_bucket_token.

Valida invariantes do tracking de download:
- upsert_download_log_done com sha256 nova → retorna TRUE (changed)
- Mesmo sha256 → retorna FALSE (idempotent)
- upsert_download_log_check (HEAD probe / 304) só atualiza last_checked_at
- invalidate_bucket_token NULLa watermark.bucket_token
- invalidate requires running run (fence)
- DLQ-style trigger: etl_incremental não pode DELETE em download_log
"""

from __future__ import annotations

import uuid

import pytest
from .conftest import expect_pg_error


RAISE_EXCEPTION = "P0001"


def test_upsert_download_log_done_first_call_returns_changed_true(
    run_id, govbr_autocommit_conn
):
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            """SELECT etl_admin.upsert_download_log_done(
                %s, 'test_dl', 'test_tbl', '2024',
                'https://test.example/foo.zip', '/tmp/foo.zip',
                'etag1', 'Wed, 01 Mar 2026 12:00:00 GMT', 1024,
                'sha_initial'
            )""",
            (str(run_id),),
        )
        assert cur.fetchone()[0] is True
        cur.execute(
            "DELETE FROM etl_download_log WHERE source='test_dl'"
        )


def test_upsert_download_log_done_same_sha_returns_changed_false(
    run_id, govbr_autocommit_conn
):
    with govbr_autocommit_conn.cursor() as cur:
        # First insert
        cur.execute(
            """SELECT etl_admin.upsert_download_log_done(
                %s, 'test_dl_same', 'test_tbl', '2024',
                'https://test.example/foo.zip', '/tmp/foo.zip',
                'etag1', NULL, 1024, 'sha_same'
            )""",
            (str(run_id),),
        )
        assert cur.fetchone()[0] is True
        # Same sha — NO-OP
        cur.execute(
            """SELECT etl_admin.upsert_download_log_done(
                %s, 'test_dl_same', 'test_tbl', '2024',
                'https://test.example/foo.zip', '/tmp/foo.zip',
                'etag1', NULL, 1024, 'sha_same'
            )""",
            (str(run_id),),
        )
        assert cur.fetchone()[0] is False
        cur.execute("DELETE FROM etl_download_log WHERE source='test_dl_same'")


def test_upsert_download_log_done_new_sha_returns_changed_true(
    run_id, govbr_autocommit_conn
):
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            """SELECT etl_admin.upsert_download_log_done(
                %s, 'test_dl_new', 'test_tbl', '2024',
                'https://test.example/foo.zip', '/tmp/foo.zip',
                'etag1', NULL, 1024, 'sha_v1'
            )""",
            (str(run_id),),
        )
        assert cur.fetchone()[0] is True
        # New sha — changed
        cur.execute(
            """SELECT etl_admin.upsert_download_log_done(
                %s, 'test_dl_new', 'test_tbl', '2024',
                'https://test.example/foo.zip', '/tmp/foo.zip',
                'etag2', NULL, 2048, 'sha_v2'
            )""",
            (str(run_id),),
        )
        assert cur.fetchone()[0] is True
        cur.execute("DELETE FROM etl_download_log WHERE source='test_dl_new'")


def test_upsert_download_log_check_updates_last_checked_at(
    run_id, govbr_autocommit_conn
):
    """HEAD probe (not_modified) só atualiza last_checked_at, não last_downloaded_at."""
    with govbr_autocommit_conn.cursor() as cur:
        # Setup: full download primeiro
        cur.execute(
            """SELECT etl_admin.upsert_download_log_done(
                %s, 'test_check', 'test_tbl', '2024',
                'https://test.example/foo.zip', '/tmp/foo.zip',
                'etag1', NULL, 1024, 'sha_initial'
            )""",
            (str(run_id),),
        )
        cur.execute(
            """SELECT last_downloaded_at, last_checked_at
               FROM etl_download_log
               WHERE source='test_check' AND bucket_id='2024'"""
        )
        dl1, ck1 = cur.fetchone()
        assert dl1 is not None
        assert ck1 is not None

        # HEAD probe: não muda last_downloaded_at
        cur.execute(
            """SELECT etl_admin.upsert_download_log_check(
                %s, 'test_check', 'test_tbl', '2024',
                'https://test.example/foo.zip', '/tmp/foo.zip',
                'etag1', NULL, 1024, 'not_modified'
            )""",
            (str(run_id),),
        )

        cur.execute(
            """SELECT last_downloaded_at, last_checked_at, last_status
               FROM etl_download_log
               WHERE source='test_check' AND bucket_id='2024'"""
        )
        dl2, ck2, status = cur.fetchone()
        assert dl2 == dl1, "last_downloaded_at NÃO deve mudar em HEAD probe"
        assert ck2 > ck1, "last_checked_at deve mudar"
        assert status == "not_modified"

        cur.execute("DELETE FROM etl_download_log WHERE source='test_check'")


def test_invalidate_bucket_token_nulls_token(
    run_id, govbr_autocommit_conn, cleanup_test_source
):
    cleanup_test_source("test_invl", "test_tbl")
    with govbr_autocommit_conn.cursor() as cur:
        # Setup: watermark com bucket_token preenchido
        cur.execute(
            """INSERT INTO etl_watermark
               (source, table_name, last_value, watermark_type, bucket_token)
               VALUES ('test_invl', 'test_tbl', '2024', 'integer',
                       '11111111-2222-3333-4444-555555555555')"""
        )
        # Invalidate
        cur.execute(
            "SELECT etl_admin.invalidate_bucket_token(%s, 'test_invl', 'test_tbl', 'sha256 changed')",
            (str(run_id),),
        )
        assert cur.fetchone()[0] is True
        cur.execute(
            "SELECT bucket_token FROM etl_watermark WHERE source='test_invl' AND table_name='test_tbl'"
        )
        assert cur.fetchone()[0] is None


def test_invalidate_bucket_token_requires_running_run(
    govbr_autocommit_conn, cleanup_test_source
):
    cleanup_test_source("test_invl_fence", "test_tbl")
    with govbr_autocommit_conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.start_run('incremental', 'pytest:invl_fence', NULL)"
        )
        rid = cur.fetchone()[0]
        cur.execute("SELECT etl_admin.finish_run(%s, 'success', NULL)", (str(rid),))
        # Run finished — invalidate deve falhar
        with expect_pg_error(sqlstate=RAISE_EXCEPTION):
            cur.execute(
                "SELECT etl_admin.invalidate_bucket_token(%s, 'test_invl_fence', 'test_tbl', 'reason here')",
                (str(rid),),
            )
        cur.execute("DELETE FROM etl_run_log WHERE run_id = %s", (str(rid),))


def test_invalidate_bucket_token_requires_reason(
    run_id, govbr_autocommit_conn
):
    with govbr_autocommit_conn.cursor() as cur:
        with expect_pg_error(sqlstate=RAISE_EXCEPTION):
            cur.execute(
                "SELECT etl_admin.invalidate_bucket_token(%s, 'a', 'b', '')",
                (str(run_id),),
            )
