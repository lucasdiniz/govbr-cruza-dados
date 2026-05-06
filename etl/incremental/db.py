"""Wrappers Python para etl_admin SECURITY DEFINER functions.

Funções:
- start_run / heartbeat_run / is_run_alive / finish_run
- abort_stale_runs / cleanup_orphan_staging
- set_watermark / reset_watermark
- insert_phase_log / get_watermark
- upsert_download_log_check / upsert_download_log_done / invalidate_bucket_token

Estas funções são o ÚNICO caminho para o ETL role mutar audit tables.
Veja sql/27_etl_admin_security_definer.sql + sql/29_etl_download_log.sql.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional


def start_run(
    conn,
    *,
    mode: str,
    triggered_by: str,
    commit_sha: Optional[str] = None,
) -> uuid.UUID:
    """Inicia uma nova run. Retorna run_id UUID gerado."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.start_run(%s, %s, %s)",
            (mode, triggered_by, commit_sha),
        )
        row = cur.fetchone()
        return row[0]


def heartbeat_run(conn, run_id: uuid.UUID) -> bool:
    """Atualiza last_heartbeat. Retorna False se run foi fenced."""
    with conn.cursor() as cur:
        cur.execute("SELECT etl_admin.heartbeat_run(%s)", (str(run_id),))
        return bool(cur.fetchone()[0])


def is_run_alive(conn, run_id: uuid.UUID) -> bool:
    """Lookup STABLE: run está com status='running'?"""
    with conn.cursor() as cur:
        cur.execute("SELECT etl_admin.is_run_alive(%s)", (str(run_id),))
        return bool(cur.fetchone()[0])


def finish_run(
    conn,
    run_id: uuid.UUID,
    *,
    status: str,
    error: Optional[str] = None,
) -> None:
    """Termina run com transição válida ('success'|'failed'|'partial'|'aborted')."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.finish_run(%s, %s, %s)",
            (str(run_id), status, error),
        )


def abort_stale_runs(conn, *, max_age_minutes: int = 5) -> int:
    """Preflight: marca runs com heartbeat antigo como aborted. Retorna count."""
    with conn.cursor() as cur:
        cur.execute("SELECT etl_admin.abort_stale_runs(%s)", (max_age_minutes,))
        return int(cur.fetchone()[0])


def cleanup_orphan_staging(conn) -> int:
    """Janitor: drop staging tables cuja run não está running. Retorna count."""
    with conn.cursor() as cur:
        cur.execute("SELECT etl_admin.cleanup_orphan_staging()")
        return int(cur.fetchone()[0])


def set_watermark(
    conn,
    *,
    run_id: uuid.UUID,
    source: str,
    table: str,
    bucket_token: uuid.UUID,
    new_value: str,
    watermark_type: str,
    actual_max: Optional[str],
    actual_count: Optional[int],
) -> bool:
    """Avança watermark. Retorna True se avançou; False se NO-OP."""
    if watermark_type not in ("timestamp", "integer", "string"):
        raise ValueError(f"invalid watermark_type: {watermark_type}")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.set_watermark(%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                str(run_id), source, table, str(bucket_token),
                new_value, watermark_type, actual_max, actual_count,
            ),
        )
        return bool(cur.fetchone()[0])


def reset_watermark(
    conn,
    *,
    source: str,
    table: str,
    new_value: str,
    reason: str,
    approver: str,
) -> None:
    """Manual override. Reason >= 10 chars + approver obrigatório."""
    if reason is None or len(reason.strip()) < 10:
        raise ValueError("reason must be at least 10 chars")
    if approver is None or not approver.strip():
        raise ValueError("approver required")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.reset_watermark(%s, %s, %s, %s, %s)",
            (source, table, new_value, reason, approver),
        )


def insert_phase_log(
    conn,
    *,
    run_id: uuid.UUID,
    attempt: int,
    source: str,
    table: str,
    file_path: Optional[str],
    file_sequence: Optional[int],
    status: str,
    started_at: datetime,
    finished_at: Optional[datetime],
    rows_streamed: int = 0,
    rows_inserted: int = 0,
    rows_updated: int = 0,
    rows_skipped_dup: int = 0,
    rows_skipped_stale: int = 0,
    rows_failed: int = 0,
    rows_rejected_null_key: int = 0,
    rows_coerced_null: int = 0,
    rows_conflict_diff_payload: int = 0,
    watermark_before: Optional[str] = None,
    watermark_after: Optional[str] = None,
    spec_hash: Optional[str] = None,
    csv_header_hash: Optional[str] = None,
    error_message: Optional[str] = None,
) -> int:
    """Append-only insert em etl_phase_log. Único path para ETL role."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT etl_admin.insert_phase_log(
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s
            )""",
            (
                str(run_id), attempt, source, table,
                file_path, file_sequence, status,
                started_at, finished_at,
                rows_streamed, rows_inserted, rows_updated,
                rows_skipped_dup, rows_skipped_stale,
                rows_failed, rows_rejected_null_key,
                rows_coerced_null, rows_conflict_diff_payload,
                watermark_before, watermark_after,
                spec_hash, csv_header_hash, error_message,
            ),
        )
        return int(cur.fetchone()[0])


def get_watermark(conn, *, source: str, table: str) -> Optional[dict]:
    """Lê estado do watermark. Retorna None se não existe."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT
                last_value, watermark_type, last_run_at, bucket_token,
                error_count, last_error,
                bootstrap_target_max, bootstrap_target_count, bootstrapped_at,
                expected_target_max, expected_target_count,
                target_schema_hash
            FROM etl_watermark WHERE source = %s AND table_name = %s""",
            (source, table),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return {
            "last_value": row[0], "watermark_type": row[1], "last_run_at": row[2],
            "bucket_token": row[3], "error_count": row[4], "last_error": row[5],
            "bootstrap_target_max": row[6], "bootstrap_target_count": row[7],
            "bootstrapped_at": row[8], "expected_target_max": row[9],
            "expected_target_count": row[10], "target_schema_hash": row[11],
        }


# ─── Download log wrappers ────────────────────────────────────────────────────

def upsert_download_log_check(
    conn,
    *,
    run_id: uuid.UUID,
    source: str,
    table: Optional[str],
    bucket_id: str,
    url: str,
    dest_path: str,
    etag: Optional[str],
    last_modified: Optional[str],
    content_length: Optional[int],
    status: str,
) -> None:
    """HEAD probe / conditional GET 304/failed/partial. Não muda last_downloaded_at."""
    if status not in ("not_modified", "failed", "partial"):
        raise ValueError(f"invalid status for check: {status}")
    with conn.cursor() as cur:
        cur.execute(
            """SELECT etl_admin.upsert_download_log_check(
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )""",
            (
                str(run_id), source, table, bucket_id, url, dest_path,
                etag, last_modified, content_length, status,
            ),
        )


def upsert_download_log_done(
    conn,
    *,
    run_id: uuid.UUID,
    source: str,
    table: Optional[str],
    bucket_id: str,
    url: str,
    dest_path: str,
    etag: Optional[str],
    last_modified: Optional[str],
    content_length: Optional[int],
    content_sha256: str,
) -> bool:
    """Download bem-sucedido. Retorna True se content_sha256 mudou."""
    with conn.cursor() as cur:
        cur.execute(
            """SELECT etl_admin.upsert_download_log_done(
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )""",
            (
                str(run_id), source, table, bucket_id, url, dest_path,
                etag, last_modified, content_length, content_sha256,
            ),
        )
        return bool(cur.fetchone()[0])


def invalidate_bucket_token(
    conn,
    *,
    run_id: uuid.UUID,
    source: str,
    table: str,
    reason: str,
) -> bool:
    """NULLa bucket_token em etl_watermark. Reason >= 5 chars."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT etl_admin.invalidate_bucket_token(%s, %s, %s, %s)",
            (str(run_id), source, table, reason),
        )
        return bool(cur.fetchone()[0])
