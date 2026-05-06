"""run_incremental_for_source — orchestrator público.

Owns:
- 3 conns (main TX, lock session, dlq autocommit)
- Run lifecycle (start_run, finish_run)
- Lock acquire/release (after main_conn commits)
- Heartbeat thread + master watchdog
- Pre-flight (abort_stale_runs, cleanup_orphan_staging)
- DOWNLOAD phase: conditional GET → invalidate bucket_token if changed (D15/D16)
- File iteration por bucket
- set_watermark APENAS após bucket completo (D1)
- Drop staging em conn isolada APÓS main_conn fecha (R6 fix)

Fluxo por bucket:
1. Download via conditional GET (HEAD probe)
2. Se sha256 mudou → invalidate bucket_token (próximo set_watermark vai re-apply)
3. Se bucket_token != watermark atual → roda _incremental_load
4. Se TODOS os arquivos do bucket succederam → set_watermark
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import psycopg2

from . import db as etl_db
from .conn import (
    AutocommitDlqConn, IncrementalLoadContext, LockConn, MainTxConn,
)
from .download import download_and_log
from .heartbeat import HeartbeatThread, MasterWatchdog
from .loader import LoadResult, RunFencedError, _incremental_load
from .locks import acquire_etl_table_locks, release_etl_table_locks
from .spec import LoaderSpec, CursorStrategy
from .staging import drop_staging

logger = logging.getLogger(__name__)


@dataclass
class BucketRun:
    """Resultado consolidado de um bucket completo (múltiplos arquivos)."""
    bucket_id: str
    files: list[tuple[Path, LoadResult]] = field(default_factory=list)
    all_success: bool = False
    total_streamed: int = 0
    total_inserted: int = 0
    total_updated: int = 0
    total_failed: int = 0


def _bucket_token(source: str, table: str, bucket_id: str) -> uuid.UUID:
    """Determinístico via uuid5 — mesmo bucket sempre gera mesmo token."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"{source}/{table}/{bucket_id}")


def run_incremental_for_source(
    spec: LoaderSpec,
    *,
    data_dir: Path,
    dsn: str,                       # DSN principal (etl_incremental role typically)
    govbr_dsn: Optional[str] = None,  # DSN superuser para etl_db queries que precisam SELECT em audit
    triggered_by: str = "cli:unknown",
    commit_sha: Optional[str] = None,
    only_buckets: Optional[list[str]] = None,
    refetch_recent: Optional[int] = None,
    max_runtime_s: int = 6 * 3600,
    heartbeat_interval_s: float = 30.0,
) -> dict:
    """Roda incremental load para uma LoaderSpec, processando todos os
    arquivos esperados no data_dir.

    Pre-conditions:
    - Migrations 22-29 aplicadas
    - Roles etl_admin + etl_incremental criados
    - DSN tem permissões corretas

    Returns:
        dict com summary: {
            'run_id': UUID,
            'status': 'success' | 'partial' | 'failed',
            'buckets': [BucketRun, ...],
            'total_inserted': int, ...
        }
    """
    govbr_dsn = govbr_dsn or dsn

    # 1. Conexões
    main_raw = psycopg2.connect(dsn)
    main_raw.autocommit = False
    main = MainTxConn(main_raw)

    lock_raw = psycopg2.connect(dsn)
    lock_raw.autocommit = True
    lock = LockConn(lock_raw)

    dlq_raw = psycopg2.connect(dsn)
    dlq_raw.autocommit = True
    dlq = AutocommitDlqConn(dlq_raw)

    # govbr conn para queries de download_log (SELECT)
    govbr_raw = psycopg2.connect(govbr_dsn)
    govbr_raw.autocommit = True

    # Drop conn (isolated autocommit) para drop staging fora do main TX
    drop_raw = psycopg2.connect(govbr_dsn)
    drop_raw.autocommit = True

    # 2. Pre-flight + start_run
    with lock_raw.cursor() as cur:
        cur.execute("SELECT etl_admin.abort_stale_runs(5)")
        cur.execute("SELECT etl_admin.cleanup_orphan_staging()")

    run_id = etl_db.start_run(
        lock_raw, mode="incremental", triggered_by=triggered_by, commit_sha=commit_sha,
    )

    # 3. Heartbeat thread + master watchdog
    fence_event = threading.Event()
    hb = HeartbeatThread(run_id, dsn, fence_event, interval_s=heartbeat_interval_s)
    hb.start()

    summary = {
        "run_id": run_id,
        "status": "running",
        "spec": f"{spec.source}.{spec.table}",
        "buckets": [],
        "total_inserted": 0,
        "total_updated": 0,
        "total_failed": 0,
        "started_at": datetime.now().isoformat(),
    }
    final_status = "failed"
    error_msg = None
    all_staging_to_drop = []

    try:
        with MasterWatchdog(max_runtime_s=max_runtime_s):
            # 4. Acquire lock
            acquire_etl_table_locks(lock, spec.source, spec.table)

            # 5. Build list of buckets to process (download phase + disk enum)
            refetch_n = (
                refetch_recent if refetch_recent is not None
                else spec.refetch_recent_buckets
            )
            buckets = _build_buckets(
                spec, data_dir,
                only_buckets=only_buckets,
                refetch_recent=refetch_n,
                run_id=run_id,
                etl_conn=lock_raw,
                govbr_conn=govbr_raw,
                summary=summary,
            )
            if not buckets:
                logger.warning(
                    "no buckets found for %s.%s in %s",
                    spec.source, spec.table, data_dir,
                )
                final_status = "success"
                return summary

            # 6. Process each bucket
            for bucket_info in buckets:
                bucket_id = bucket_info["bucket_id"]
                files = bucket_info["files"]
                bucket_skip_reason = bucket_info.get("skip_reason")
                if fence_event.is_set():
                    raise RunFencedError(f"run {run_id} fenced mid-bucket")

                bucket_run = BucketRun(bucket_id=bucket_id)
                bucket_token = _bucket_token(spec.source, spec.table, bucket_id)

                # SKIP bucket if download said no change AND token already matches
                if bucket_skip_reason:
                    logger.info(
                        "bucket %s/%s skipped: %s",
                        spec.source, bucket_id, bucket_skip_reason,
                    )
                    bucket_run.all_success = True
                    summary["buckets"].append(bucket_run)
                    continue

                for seq, csv_path in enumerate(files, start=1):
                    if fence_event.is_set():
                        raise RunFencedError(f"run {run_id} fenced mid-file")

                    # Phase log: insert before processing
                    started = datetime.now()
                    file_result = LoadResult(status="failed", error="not started")
                    try:
                        # Build context (per-file, mas bucket_token shared)
                        ctx = IncrementalLoadContext(
                            main=main, lock=lock, dlq=dlq,
                            run_id=run_id, bucket_token=bucket_token,
                        )
                        try:
                            file_result = _incremental_load(
                                spec, ctx, csv_path, file_sequence=seq,
                                bucket_id=bucket_id,
                            )
                            if file_result.status == "success":
                                main_raw.commit()
                            else:
                                main_raw.rollback()
                        except Exception:
                            main_raw.rollback()
                            raise
                    except RunFencedError:
                        raise
                    except Exception as e:
                        logger.exception("error loading %s", csv_path)
                        file_result = LoadResult(status="failed", error=str(e))
                    finally:
                        all_staging_to_drop.extend(file_result.staging_tables)
                        # Phase log row
                        try:
                            etl_db.insert_phase_log(
                                lock_raw,
                                run_id=run_id, attempt=1,
                                source=spec.source, table=spec.table,
                                file_path=str(csv_path), file_sequence=seq,
                                status=file_result.status,
                                started_at=started, finished_at=datetime.now(),
                                rows_streamed=file_result.rows_streamed,
                                rows_inserted=file_result.rows_inserted,
                                rows_updated=file_result.rows_updated,
                                rows_failed=file_result.rows_failed,
                                rows_rejected_null_key=file_result.rows_rejected_null_key,
                                rows_coerced_null=file_result.rows_coerced_null,
                                spec_hash=spec.spec_hash,
                                csv_header_hash=file_result.csv_header_hash,
                                error_message=file_result.error,
                            )
                        except Exception as e:
                            logger.warning("insert_phase_log failed: %s", e)

                    bucket_run.files.append((csv_path, file_result))
                    bucket_run.total_streamed += file_result.rows_streamed
                    bucket_run.total_inserted += file_result.rows_inserted
                    bucket_run.total_updated += file_result.rows_updated
                    bucket_run.total_failed += file_result.rows_failed

                bucket_run.all_success = all(
                    r.status == "success" for _, r in bucket_run.files
                )
                summary["buckets"].append(bucket_run)
                summary["total_inserted"] += bucket_run.total_inserted
                summary["total_updated"] += bucket_run.total_updated
                summary["total_failed"] += bucket_run.total_failed

                # 7. Set watermark APENAS se bucket completo
                if bucket_run.all_success and spec.watermark_col:
                    new_wm = _max_watermark_in_bucket(bucket_run, spec.watermark_type)
                    if new_wm is not None:
                        try:
                            etl_db.set_watermark(
                                lock_raw,
                                run_id=run_id,
                                source=spec.source,
                                table=spec.table,
                                bucket_token=bucket_token,
                                new_value=new_wm,
                                watermark_type=spec.watermark_type,
                                actual_max=new_wm,
                                actual_count=None,
                            )
                        except psycopg2.Error as e:
                            logger.warning("set_watermark failed: %s", e)

            # All buckets processed
            partial_buckets = [b for b in summary["buckets"] if not b.all_success]
            if not partial_buckets:
                final_status = "success"
            elif partial_buckets and len(partial_buckets) < len(summary["buckets"]):
                final_status = "partial"
            else:
                final_status = "failed"
                error_msg = f"{len(partial_buckets)} of {len(summary['buckets'])} buckets failed"

    except RunFencedError as e:
        final_status = "aborted"
        error_msg = str(e)
        logger.error(error_msg)
    except Exception as e:
        final_status = "failed"
        error_msg = str(e)
        logger.exception("orchestrator error")
    finally:
        # Stop heartbeat first
        hb.stop()

        # Drop staging tables APÓS main_conn fechar (R6 fix)
        try:
            main_raw.close()
        except Exception:
            pass
        if all_staging_to_drop:
            # Dedupe (alias case)
            unique_stg = list(dict.fromkeys(all_staging_to_drop))
            drop_staging(drop_raw, *unique_stg)

        # Release lock
        try:
            release_etl_table_locks(lock, spec.source, spec.table)
        except Exception as e:
            logger.warning("release lock failed: %s", e)

        # Finish run
        try:
            etl_db.finish_run(lock_raw, run_id, status=final_status, error=error_msg)
        except Exception as e:
            logger.warning("finish_run failed: %s", e)

        # Cleanup conns
        for c in (lock_raw, dlq_raw, govbr_raw, drop_raw):
            try:
                c.close()
            except Exception:
                pass

        summary["status"] = final_status
        summary["error_message"] = error_msg
        summary["finished_at"] = datetime.now().isoformat()

    return summary


def _enumerate_buckets(
    spec: LoaderSpec,
    data_dir: Path,
    *,
    only_buckets: Optional[list[str]] = None,
) -> list[tuple[str, list[Path]]]:
    """Lista buckets disponíveis no data_dir, filtrando por only_buckets."""
    if spec.cursor_strategy == CursorStrategy.SNAPSHOT:
        # Snapshot: 1 bucket synthetic 'snapshot'
        if spec.file_pattern is None:
            return []
        files = []
        for fname in spec.file_pattern("snapshot"):
            p = data_dir / fname
            if p.exists():
                files.append(p)
        return [("snapshot", files)] if files else []

    # YEAR_WINDOW / MONTH_WINDOW: enumerate disk + group by bucket_from_filename
    by_bucket: dict[str, list[Path]] = {}
    for child in sorted(data_dir.iterdir()):
        if not child.is_file() or not child.name.lower().endswith(".csv"):
            continue
        try:
            bid = spec.bucket_from_filename(child.name)
        except (ValueError, AttributeError):
            continue
        if bid is None:
            continue
        if only_buckets and bid not in only_buckets:
            continue
        by_bucket.setdefault(bid, []).append(child)

    # Return sorted by bucket_id
    return [(bid, sorted(by_bucket[bid])) for bid in sorted(by_bucket.keys())]


def _build_buckets(
    spec: LoaderSpec,
    data_dir: Path,
    *,
    only_buckets: Optional[list[str]],
    refetch_recent: int,
    run_id,
    etl_conn,
    govbr_conn,
    summary: dict,
) -> list[dict]:
    """Constrói lista de buckets a processar.

    Pra cada bucket:
    1. Se url_for_bucket está definido: tenta conditional GET de cada arquivo
       - 304 not_modified → flag bucket_skip se token já bate
       - 200 changed → invalida bucket_token (já fez via download_and_log)
       - failed → mantém bucket pra retry
    2. Sempre re-baixa últimos `refetch_recent` buckets (D15 refetch window)
    3. Verifica se bucket_token atual em etl_watermark == bucket_token
       determinístico do bucket. Se sim AND nada baixou → skip.

    Returns:
        list of dict {bucket_id, files, skip_reason}
    """
    # Enumerate disk-based buckets first
    disk_buckets = _enumerate_buckets(spec, data_dir, only_buckets=only_buckets)
    bucket_ids_disk = [bid for bid, _ in disk_buckets]

    # Also enumerate via spec.enumerate_buckets if defined (for buckets not on disk yet)
    if spec.enumerate_buckets is not None:
        try:
            extra = spec.enumerate_buckets()
            for bid in extra:
                if only_buckets and bid not in only_buckets:
                    continue
                if bid not in bucket_ids_disk:
                    disk_buckets.append((bid, []))
                    bucket_ids_disk.append(bid)
        except Exception as e:
            logger.warning("spec.enumerate_buckets() failed: %s", e)

    # Sort buckets ascending; refetch_recent applies to TAIL N
    disk_buckets.sort(key=lambda t: t[0])
    if refetch_recent > 0:
        tail_set = set(bid for bid, _ in disk_buckets[-refetch_recent:])
    else:
        tail_set = set()  # NÃO usar [-0:] (= lista inteira em Python)

    download_summary = []
    result = []

    for bid, files_on_disk in disk_buckets:
        # Build expected file list
        if spec.file_pattern is not None:
            expected_files = spec.file_pattern(bid)
        else:
            expected_files = [p.name for p in files_on_disk]

        # 1. Download phase per file (if url_for_bucket defined)
        bucket_changed = False
        all_not_modified = True
        download_skipped_count = 0
        download_failed_count = 0

        if spec.url_for_bucket is not None:
            try:
                url_pairs = spec.url_for_bucket(bid)
            except Exception as e:
                logger.warning("url_for_bucket(%s) failed: %s", bid, e)
                url_pairs = []

            for url, fname in url_pairs:
                dest = data_dir / fname
                force = bid in tail_set
                try:
                    dr = download_and_log(
                        etl_conn=etl_conn,
                        govbr_conn=govbr_conn,
                        run_id=run_id,
                        source=spec.source,
                        table=spec.table,
                        bucket_id=bid,
                        url=url,
                        dest_path=dest,
                        force_refetch=force,
                    )
                    download_summary.append({
                        "bucket": bid, "url": url,
                        "status": dr.status, "changed": dr.content_changed,
                        "bytes": dr.bytes_downloaded,
                    })
                    if dr.status == "downloaded":
                        all_not_modified = False
                        if dr.content_changed:
                            bucket_changed = True
                    elif dr.status == "not_modified":
                        download_skipped_count += 1
                    elif dr.status == "failed":
                        all_not_modified = False
                        download_failed_count += 1
                except Exception as e:
                    logger.warning("download error for %s: %s", url, e)
                    download_failed_count += 1

        # 2. Re-enumerate files on disk after potential downloads
        files_on_disk_now = []
        for ef in expected_files:
            p = data_dir / ef
            if p.exists():
                files_on_disk_now.append(p)
        if not files_on_disk_now:
            files_on_disk_now = files_on_disk

        # 3. Determine skip
        # Skip if: NO download was performed (no url_for_bucket OR all 304 OR no urls)
        # AND bucket_token in etl_watermark already matches deterministic token
        # AND not in refetch tail
        skip_reason = None
        if (not bucket_changed
                and bid not in tail_set
                and (spec.url_for_bucket is None or all_not_modified)):
            try:
                wm = etl_db.get_watermark(govbr_conn, source=spec.source, table=spec.table)
                if wm is not None and wm["bucket_token"] is not None:
                    expected_token = _bucket_token(spec.source, spec.table, bid)
                    if str(wm["bucket_token"]) == str(expected_token):
                        skip_reason = (
                            f"bucket_token matches and no download change "
                            f"({download_skipped_count} not_modified)"
                        )
            except Exception as e:
                logger.warning("get_watermark failed: %s", e)

        result.append({
            "bucket_id": bid,
            "files": files_on_disk_now,
            "skip_reason": skip_reason,
        })

    summary["downloads"] = download_summary
    return result


def _max_watermark_in_bucket(bucket: BucketRun, watermark_type: str) -> Optional[str]:
    """Retorna MAX watermark do bucket (type-aware via Python convert)."""
    candidates = [r.new_watermark for _, r in bucket.files
                  if r.new_watermark is not None]
    if not candidates:
        return None
    if watermark_type == "integer":
        return str(max(int(c) for c in candidates))
    elif watermark_type == "timestamp":
        # ISO-comparable lex
        return max(candidates)
    else:
        return max(candidates)
