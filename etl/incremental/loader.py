"""_incremental_load — pipeline de 16 passos para carregar 1 arquivo CSV.

Module-private (D13). Acesso via orchestrator.py.

Pipeline (resumido — ver plan v7):
1. Validate header (csv_header_hash)
2. Fence check
3. CREATE staging RAW
4. Pre-parser CSV → temp file + DLQ malformed
5. COPY temp → staging RAW
6. Build typed INSERT INTO staging_typed (BR/ISO format conversion)
7. NK NULL move → DLQ + DELETE staging_typed
8. INSERT INTO staging_final SELECT (com derived_columns) — ou alias
9. ANALYZE staging_final
10. Count failures via DLQ counters
11. Se total_failed > 0: return 'partial' (target NOT modified)
12. Fence check 2
13. UPSERT com RETURNING xmax → stats
14. Compute new_watermark do staging
15. Return LoadResult com staging_tables list (orchestrator dropa)
"""

from __future__ import annotations

import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import psycopg2

from . import db as etl_db
from .conn import IncrementalLoadContext
from .parser import (
    SchemaDriftError, stream_csv_to_staging, validate_csv_header,
)
from .spec import DedupeStrategy, LoaderSpec
from .staging import (
    build_typed_select, build_upsert_sql, copy_temp_to_staging,
    create_staging_raw, staging_name,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class RunFencedError(RuntimeError):
    """Run foi marcada como aborted; main thread deve abortar."""


@dataclass
class LoadResult:
    """Resultado de um _incremental_load (1 arquivo)."""
    status: str  # 'success' | 'partial' | 'failed'
    rows_streamed: int = 0
    rows_inserted: int = 0
    rows_updated: int = 0
    rows_failed: int = 0
    rows_rejected_null_key: int = 0
    rows_coerced_null: int = 0
    new_watermark: Optional[str] = None
    csv_header_hash: Optional[str] = None
    staging_tables: list[str] = field(default_factory=list)
    error: Optional[str] = None


def _check_fence(ctx: IncrementalLoadContext) -> None:
    """Raise RunFencedError se run foi fenced."""
    # is_run_alive em conn dedicada (etl_conn typically) — usar lock_conn
    # como conn de leitura rápida (autocommit-friendly)
    alive = etl_db.is_run_alive(ctx.lock, ctx.run_id)
    if not alive:
        raise RunFencedError(f"run {ctx.run_id} was fenced")


def _resolve_spec_for_bucket(spec: "LoaderSpec", bucket_id: str) -> "LoaderSpec":
    """Returns spec ajustada para bucket_id (columns/renames/NK podem variar
    por bucket conforme spec.columns_per_bucket).

    Auto-translates spec.natural_key:
    1. Se nk col já está nas new_columns, mantém (CSV name match).
    2. Se nk col é target name, busca em new_renames inverse para CSV name.
    3. Se nk col é CSV name do schema antigo, mantém também.
    4. Procura em renames original spec → traduz target name → new CSV name.
    """
    if spec.columns_per_bucket is None:
        return spec
    override = spec.columns_per_bucket(bucket_id)
    if override is None:
        return spec
    new_columns, new_renames = override
    new_types = {c: spec.column_types.get(c, "TEXT") for c in new_columns}
    # Build mapping: target_col -> new_csv_col (inverse of new_renames)
    target_to_new_csv = {target: csv for csv, target in new_renames.items()}
    # Build mapping: original_csv_col -> target_col (using original spec.column_renames)
    original_csv_to_target = dict(spec.column_renames)

    new_nk = []
    for nk in spec.natural_key:
        if nk in new_columns or nk in spec.derived_columns:
            new_nk.append(nk)
        elif nk in original_csv_to_target:
            # nk era CSV name do spec original; converte para target name, depois
            # busca CSV name no schema novo via target_to_new_csv
            target_name = original_csv_to_target[nk]
            new_csv = target_to_new_csv.get(target_name, target_name)
            if new_csv in new_columns:
                new_nk.append(new_csv)
            else:
                # Fallback: nk col target == CSV col em schema novo
                new_nk.append(target_name if target_name in new_columns else nk)
        elif nk in target_to_new_csv:
            # nk é target name; converte direto para CSV name
            new_nk.append(target_to_new_csv[nk])
        else:
            # Fallback: mantém — vai falhar validation explicitamente
            new_nk.append(nk)
    import dataclasses
    return dataclasses.replace(
        spec,
        columns=new_columns,
        column_renames=new_renames,
        column_types=new_types,
        natural_key=new_nk,
    )


def _incremental_load(
    spec: LoaderSpec,
    ctx: IncrementalLoadContext,
    csv_path: Path,
    *,
    file_sequence: int,
    bucket_id: str,
) -> LoadResult:
    """Pipeline de carga de 1 arquivo CSV. Module-private."""
    if not csv_path.exists():
        return LoadResult(status="failed", error=f"file not found: {csv_path}")

    # Resolve spec para bucket (suporta schema drift histórico)
    spec = _resolve_spec_for_bucket(spec, bucket_id)

    # Step 1+2: validate header + fence
    try:
        csv_hash = validate_csv_header(csv_path, spec)
    except SchemaDriftError as e:
        return LoadResult(status="failed", error=str(e))
    _check_fence(ctx)

    # Step 3: CREATE staging RAW
    stg_raw = staging_name(spec.source, spec.table, ctx.run_id, file_sequence, "raw", bucket_id=bucket_id)
    stg_typed = staging_name(spec.source, spec.table, ctx.run_id, file_sequence, "typed", bucket_id=bucket_id)
    stg_final = staging_name(spec.source, spec.table, ctx.run_id, file_sequence, "final", bucket_id=bucket_id)
    staging_tables = [stg_raw, stg_typed, stg_final]

    create_staging_raw(ctx.main, spec, stg_raw)

    # Step 4: pre-parser CSV → temp file + DLQ
    pp = stream_csv_to_staging(
        csv_path, spec, ctx.dlq,
        run_id=ctx.run_id, source=spec.source, table=spec.table,
        bucket_id=str(file_sequence),
    )
    rows_streamed = pp.valid_count
    rows_failed_streaming = pp.rejected_count

    if rows_streamed == 0 and rows_failed_streaming == 0:
        # Empty file
        return LoadResult(
            status="success",
            rows_streamed=0,
            csv_header_hash=csv_hash,
            staging_tables=staging_tables,
        )

    # Step 5: COPY temp → staging RAW
    try:
        copy_temp_to_staging(ctx.main, stg_raw, pp.temp_path, spec.columns)
    finally:
        try:
            pp.temp_path.unlink()
        except OSError:
            pass

    # Step 6+7+8: build typed → CREATE TABLE staging_typed AS SELECT ...
    typed_sql = build_typed_select(spec, stg_raw)
    with ctx.main.cursor() as cur:
        cur.execute(f"CREATE TABLE {stg_typed} AS {typed_sql}")

    # NK NULL move via single SQL (D6 dual-write trade-off: docked em main TX)
    rows_rejected_null_key = _move_nk_null_to_dlq(spec, ctx, stg_typed)

    # Step 8: build staging_final (POC: alias for now if no derived_columns)
    # Derived columns na FORMA literal/SQL acontece no INSERT INTO target via
    # build_upsert_sql, não como CREATE TABLE separada. Para POC com
    # column_renames, stg_final = stg_typed.
    stg_final = stg_typed
    staging_tables = [stg_raw, stg_typed]

    # Step 9: ANALYZE
    with ctx.main.cursor() as cur:
        cur.execute(f"ANALYZE {stg_final}")

    # Step 10+11: count failures
    # Hard failures (streaming): col_count_mismatch, encoding_error, csv_parse_error.
    #   Estes indicam dados corrompidos, abort run.
    # Soft failures (NK NULL): row tem NK insuficiente para target uniquidade.
    #   Estes são esperados em prod (legacy data quality issues); enviam pra DLQ
    #   mas NÃO abortam load — UPSERT continua com rows válidos.
    if rows_failed_streaming > 0:
        return LoadResult(
            status="partial",
            rows_streamed=rows_streamed,
            rows_failed=rows_failed_streaming,
            rows_rejected_null_key=rows_rejected_null_key,
            csv_header_hash=csv_hash,
            staging_tables=staging_tables,
            error=f"streaming failures={rows_failed_streaming} > 0; target not modified",
        )

    # NK NULL rejections: log mas continue UPSERT
    total_failed = rows_rejected_null_key

    # Step 12: fence check 2
    _check_fence(ctx)

    # Step 13: UPSERT
    upsert_sql = build_upsert_sql(spec, stg_final, bucket_id=bucket_id)
    rows_inserted = 0
    rows_updated = 0
    with ctx.main.cursor() as cur:
        cur.execute(upsert_sql)
        if spec.dedupe_strategy in (DedupeStrategy.UPSERT_DO_NOTHING, DedupeStrategy.APPEND):
            rows_inserted = int(cur.fetchone()[0])
        else:
            row = cur.fetchone()
            rows_inserted = int(row[0]) if row[0] is not None else 0
            rows_updated = int(row[1]) if row[1] is not None else 0

    # Step 14: compute new_watermark (only if watermark_col defined)
    new_watermark = None
    if spec.watermark_col:
        # Se watermark_col é derived, usa bucket_id diretamente
        if spec.watermark_col in spec.derived_columns:
            new_watermark = bucket_id
        else:
            new_watermark = _compute_new_watermark(spec, ctx, stg_final)

    return LoadResult(
        status="success",
        rows_streamed=rows_streamed,
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        rows_failed=0,
        new_watermark=new_watermark,
        csv_header_hash=csv_hash,
        staging_tables=staging_tables,
    )


def _move_nk_null_to_dlq(
    spec: LoaderSpec,
    ctx: IncrementalLoadContext,
    stg_typed: str,
) -> int:
    """Single-SQL DELETE WHERE NK NULL em staging.

    NOTA: NK em staging usa nomes do CSV (não target). Colunas derivadas
    (ano_arquivo) NÃO existem em staging — são adicionadas no INSERT INTO target.
    Skipamos derived cols no NULL check.
    """
    # Filter NK cols to only those that exist in staging (i.e., not derived).
    # Reverse of column_renames pra mapear target → CSV name se necessário.
    target_to_csv = {v: k for k, v in spec.column_renames.items()}
    staging_nk_cols = []
    for nk in spec.natural_key:
        if nk in spec.derived_columns:
            continue  # derived — não está em staging
        # Mapear target name → CSV name se há rename
        csv_name = target_to_csv.get(nk, nk)
        staging_nk_cols.append(csv_name)

    if not staging_nk_cols:
        return 0  # All NK cols are derived (rare)

    nk_null_pred = " OR ".join(f"{c} IS NULL" for c in staging_nk_cols)

    with ctx.main.cursor() as cur:
        cur.execute(
            f"""WITH d AS (
                DELETE FROM {stg_typed}
                WHERE {nk_null_pred}
                RETURNING *
            )
            SELECT count(*) FROM d"""
        )
        deleted = int(cur.fetchone()[0])

    if deleted > 0:
        logger.info(
            "moved %d NK-NULL rows from %s to limbo (DLQ TODO)",
            deleted, stg_typed,
        )
    return deleted


def _compute_new_watermark(
    spec: LoaderSpec,
    ctx: IncrementalLoadContext,
    stg_final: str,
) -> Optional[str]:
    """SELECT MAX(watermark_col)::text FROM staging_final."""
    wm = spec.watermark_col
    with ctx.main.cursor() as cur:
        # Type-aware text conversion
        if spec.watermark_type == "timestamp":
            cur.execute(
                f"SELECT to_char(MAX({wm}), 'YYYY-MM-DD\"T\"HH24:MI:SS.US') FROM {stg_final}"
            )
        else:
            cur.execute(f"SELECT MAX({wm})::text FROM {stg_final}")
        row = cur.fetchone()
        return row[0] if row and row[0] is not None else None
