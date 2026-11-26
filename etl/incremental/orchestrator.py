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
    total_deleted: int = 0


def _bucket_token(source: str, table: str, bucket_id: str) -> uuid.UUID:
    """Determinístico via uuid5 — mesmo bucket sempre gera mesmo token."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"{source}/{table}/{bucket_id}")


def _registrar_fase(conn, run_id, spec, caminho, seq, inicio, resultado):
    referencia = str(caminho)
    if resultado.arquivo_sha256:
        referencia += f"#sha256={resultado.arquivo_sha256}"
    return etl_db.insert_phase_log(
        conn, run_id=run_id, attempt=1, source=spec.source, table=spec.table,
        file_path=referencia, file_sequence=seq, status=resultado.status,
        started_at=inicio, finished_at=datetime.now(),
        rows_streamed=resultado.rows_streamed, rows_inserted=resultado.rows_inserted,
        rows_updated=resultado.rows_updated, rows_failed=resultado.rows_failed,
        rows_skipped_dup=resultado.rows_skipped_dup, rows_skipped_stale=resultado.rows_skipped_stale,
        rows_rejected_null_key=resultado.rows_rejected_null_key,
        rows_coerced_null=resultado.rows_coerced_null, spec_hash=spec.spec_hash,
        csv_header_hash=resultado.csv_header_hash, error_message=resultado.error,
    )


class SchemaDriftError(RuntimeError):
    """Target schema mudou desde o bootstrap; abort para inspecao manual."""


def _check_target_schema_drift(govbr_conn, spec) -> None:
    """Recompute target schema_hash and compare with bootstrap baseline.

    If different, raise SchemaDriftError to abort the run before any mutation.
    Operator should inspect the target (column added/dropped, type changed, etc.)
    and run `bootstrap_watermark.py --force` to re-baseline if drift is intentional.

    No-op if spec was never bootstrapped (auto-bootstrap will populate baseline).
    """
    from etl.incremental.bootstrap_watermark import _compute_target_schema_hash

    with govbr_conn.cursor() as cur:
        cur.execute(
            "SELECT target_schema_hash FROM etl_watermark WHERE source=%s AND table_name=%s",
            (spec.source, spec.table),
        )
        row = cur.fetchone()
    if not row or row[0] is None:
        # Pre-bootstrap state; auto-bootstrap will set baseline. No drift to check.
        return

    bootstrap_hash = row[0]
    current_hash = _compute_target_schema_hash(govbr_conn, spec.target_schema, spec.table)
    if current_hash != bootstrap_hash:
        raise SchemaDriftError(
            f"Target schema drift detected for {spec.source}.{spec.table}: "
            f"bootstrap_hash={bootstrap_hash[:16]}... current_hash={current_hash[:16]}... "
            f"Inspect target and re-bootstrap with --force if drift is intentional."
        )


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

    # 2b. Schema drift check: compare current target schema fingerprint against
    # bootstrapped baseline. Run BEFORE any mutation (abort_stale_runs/cleanup)
    # so that drift detection doesn't happen with audit-tables already touched.
    _check_target_schema_drift(govbr_raw, spec)

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
        "total_deleted": 0,
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
            faltantes = set(only_buckets or []) - {b["bucket_id"] for b in buckets}
            if not buckets or faltantes:
                raise ValueError(f"Nenhum bucket ou escopo incompleto; faltantes={sorted(faltantes)}")

            # 6. Process each bucket
            for bucket_info in buckets:
                bucket_id = bucket_info["bucket_id"]
                files = bucket_info["files"]
                bucket_skip_reason = bucket_info.get("skip_reason")
                bucket_download_failed = bucket_info.get("download_failed", False)
                if fence_event.is_set():
                    raise RunFencedError(f"run {run_id} fenced mid-bucket")

                bucket_run = BucketRun(bucket_id=bucket_id)
                bucket_token = _bucket_token(spec.source, spec.table, bucket_id)

                if bucket_download_failed:
                    logger.error(
                        "bucket %s/%s: download incompleto; cache local não será aplicado",
                        spec.source, bucket_id,
                    )
                    bucket_run.total_failed = 1
                    summary["buckets"].append(bucket_run)
                    summary["total_failed"] += 1
                    break

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
                        file_result = _incremental_load(
                            spec, ctx, csv_path, file_sequence=seq, bucket_id=bucket_id,
                        )
                        if only_buckets and file_result.status == "success" and not file_result.rows_streamed:
                            file_result.status = "failed"
                            file_result.error = "Arquivo solicitado vazio ou placeholder"
                        if file_result.status == "success":
                            # Fase e pendência de publicação têm o mesmo COMMIT
                            # que o arquivo. Nunca perder a pendência num retry sem delta.
                            _registrar_fase(main_raw, run_id, spec, csv_path, seq, started, file_result)
                            if file_result.rows_inserted or file_result.rows_updated or file_result.rows_deleted:
                                with main_raw.cursor() as cur:
                                    cur.execute(
                                        "SELECT etl_admin.enqueue_cache_invalidation(%s,%s,%s,%s,%s,%s,%s)",
                                        (str(run_id), spec.source, spec.table, bucket_id, file_result.rows_inserted,
                                         file_result.rows_updated + file_result.rows_deleted, None),
                                    )
                            if seq == len(files) and spec.watermark_col:
                                valores = [r.new_watermark for _, r in bucket_run.files] + [file_result.new_watermark]
                                marca = _maior_marca(valores, spec.watermark_type)
                                if marca is None and (only_buckets or file_result.rows_streamed):
                                    raise ValueError("Arquivo sem watermark verificável")
                                if marca is not None:
                                    etl_db.set_watermark(
                                        main_raw, run_id=run_id, source=spec.source, table=spec.table,
                                        bucket_token=bucket_token, new_value=marca, watermark_type=spec.watermark_type,
                                        actual_max=marca, actual_count=None,
                                    )
                            main_raw.commit()
                        else:
                            main_raw.rollback()
                    except RunFencedError:
                        main_raw.rollback()
                        raise
                    except (psycopg2.InterfaceError, psycopg2.OperationalError):
                        # COMMIT pode ter sido confirmado pelo servidor. A fase
                        # transacional é a evidência; não gravar "falhou" às cegas.
                        raise RuntimeError("Conexão interrompida; conferir fase antes de retomar") from None
                    except Exception as e:
                        main_raw.rollback()
                        logger.error("Arquivo %s não aplicado (%s)", csv_path.name, type(e).__name__)
                        file_result = LoadResult(status="failed", error=type(e).__name__,
                                                 arquivo_sha256=file_result.arquivo_sha256)
                    if file_result.status != "success":
                        _registrar_fase(lock_raw, run_id, spec, csv_path, seq, started, file_result)
                    all_staging_to_drop.extend(drop_staging(drop_raw, *dict.fromkeys(file_result.staging_tables)))

                    bucket_run.files.append((csv_path, file_result))
                    bucket_run.total_streamed += file_result.rows_streamed
                    bucket_run.total_inserted += file_result.rows_inserted
                    bucket_run.total_updated += file_result.rows_updated
                    bucket_run.total_failed += file_result.rows_failed
                    bucket_run.total_deleted += file_result.rows_deleted
                    if file_result.status != "success":
                        break

                bucket_run.all_success = (
                    bool(bucket_run.files)
                    and not bucket_download_failed
                    and all(r.status == "success" for _, r in bucket_run.files)
                )
                # If download failed and no cache, record an explicit failed
                # phase entry so the run summary reflects the failure (instead
                # of silently advancing past a missing source file).
                if bucket_download_failed and not bucket_run.files:
                    bucket_run.total_failed = max(bucket_run.total_failed, 1)
                summary["buckets"].append(bucket_run)
                summary["total_inserted"] += bucket_run.total_inserted
                summary["total_updated"] += bucket_run.total_updated
                summary["total_failed"] += bucket_run.total_failed
                summary["total_deleted"] += bucket_run.total_deleted

                if not bucket_run.all_success:
                    break  # mês seguinte não pode encobrir lacuna na marca

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

        # Retry de drops que falharam durante o processamento.
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
            final_status = "failed"
            error_msg = f"Não foi possível confirmar o encerramento ({type(e).__name__})"
            logger.error(error_msg)

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
    if not data_dir.exists():
        # Fresh deploy: data_dir nao foi criado ainda. Framework cria via
        # download.py:_download_one quando url_for_bucket gera URLs. Retorna
        # vazio aqui para que _build_buckets caia no caminho de enumerate
        # via spec.enumerate_buckets() + url_for_bucket.
        return []
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
            raise RuntimeError("Falha ao enumerar competências") from e

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
                raise RuntimeError(f"Falha ao identificar fonte do bucket {bid}") from e

            if not url_pairs:
                download_failed_count += 1

            for url, fname in url_pairs:
                dest = data_dir / fname
                # Replace (ADR-0015) sempre re-baixa: o arquivo vira a verdade
                # do bucket, entao nao pode ser um cache antigo (304).
                force = bid in tail_set or spec.bucket_replace is not None
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
                        membros_esperados=tuple(expected_files) if len(url_pairs) == 1 else (),
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
        membros_ausentes = len(files_on_disk_now) != len(expected_files)

        # 3. Determine skip
        # Skip só com confirmação da fonte (304) e marca correspondente.
        skip_reason = None
        if (not bucket_changed and not download_failed_count and spec.bucket_replace is None
                and bid not in tail_set
                and download_skipped_count and all_not_modified):
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
            "download_failed": download_failed_count > 0 or (membros_ausentes and not skip_reason),
        })

    summary["downloads"] = download_summary
    return result


def _maior_marca(valores: list[Optional[str]], watermark_type: str) -> Optional[str]:
    candidates = [v for v in valores if v is not None]
    if not candidates:
        return None
    if watermark_type == "integer":
        return str(max(int(c) for c in candidates))
    elif watermark_type == "timestamp":
        # ISO-comparable lex
        return max(candidates)
    else:
        return max(candidates)
