"""Staging tables lifecycle.

Convenção de nomes: `etl_staging._stg_{source}_{table}_{run8}_{seq}_{kind}`
onde kind ∈ {raw, typed, final}.

Helper `staging_name` valida 63-byte limit (PG identifier max) com truncate +
md5 fallback (R6 BLOCKING fix).

3 estágios:
- raw:   todas TEXT, populada por COPY do temp tab-separated
- typed: cast com BR format conversion + sentinel coerce + type validation
- final: derived_columns adicionadas

Para POC sem derived_columns nem type-strict, raw e typed podem ser aliases.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .conn import MainTxConn
    from .spec import LoaderSpec

logger = logging.getLogger(__name__)

PG_IDENT_MAX = 63
STAGING_SCHEMA = "etl_staging"


def staging_name(source: str, table: str, run_id, seq: int, kind: str, *, bucket_id: str = "0") -> str:
    """Gera nome qualificado de staging table com truncate seguro a 63 bytes.

    Formato: etl_staging._stg_{source}_{table}_{run8}_{bucket}_{seq}_{kind}
    bucket incluído para evitar collision entre buckets na mesma run.
    Se nome exceder 63 bytes (PG identifier limit), trunca via md5 fallback.
    """
    if isinstance(run_id, uuid.UUID):
        run8 = run_id.hex[:8]
    else:
        run8 = str(run_id).replace("-", "")[:8]

    # Sanitize bucket_id (e.g., '2024-03' -> '2024_03')
    bucket_clean = "".join(c if c.isalnum() else "_" for c in str(bucket_id))[:8]

    base = f"_stg_{source}_{table}_{run8}_{bucket_clean}_{seq}_{kind}"
    if len(base) <= PG_IDENT_MAX:
        return f"{STAGING_SCHEMA}.{base}"

    # Fallback: md5 hash do nome completo + truncate prefix
    h = hashlib.md5(base.encode()).hexdigest()[:8]
    truncated = f"_stg_{source[:8]}_{table[:8]}_{h}_{bucket_clean}_{seq}_{kind}"
    if len(truncated) > PG_IDENT_MAX:
        truncated = f"_stg_{h}_{run8}_{bucket_clean}_{seq}_{kind}"
    if len(truncated) > PG_IDENT_MAX:
        raise RuntimeError(f"staging_name overflow even after truncate: {truncated}")
    return f"{STAGING_SCHEMA}.{truncated}"


def create_staging_raw(main: "MainTxConn", spec: "LoaderSpec", stg_qualified: str) -> None:
    """CREATE TABLE staging RAW com todas TEXT cols + metadata cols.

    Metadata cols são adicionadas no fim:
    - _line_num BIGINT (line number original do CSV)
    - _raw_line TEXT (não armazenamos em raw, fica no DLQ se necessário)
    """
    cols_def = ", ".join(f"{c} TEXT" for c in spec.columns)
    sql = f"CREATE TABLE {stg_qualified} ({cols_def})"
    with main.cursor() as cur:
        cur.execute(sql)


def copy_temp_to_staging(
    main: "MainTxConn",
    stg_qualified: str,
    temp_path,
    columns: list[str],
) -> int:
    """COPY do temp tab-separated file para staging RAW.

    Retorna count de rows importadas.
    """
    cols = ", ".join(columns)
    copy_sql = (
        f"COPY {stg_qualified} ({cols}) FROM STDIN "
        f"WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N')"
    )
    with main.cursor() as cur:
        with open(temp_path, "r", encoding="utf-8") as f:
            cur.copy_expert(copy_sql, f)
        cur.execute(f"SELECT count(*) FROM {stg_qualified}")
        return int(cur.fetchone()[0])


def drop_staging(conn, *staging_qualified: str) -> None:
    """DROP TABLE IF EXISTS para cada staging passada. Best-effort.

    IMPORTANTE: usa conn separada autocommit (passada pelo orchestrator),
    não main_conn. Drop após main_conn fechar (evita deadlock).
    """
    for stg in staging_qualified:
        try:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {stg}")
        except Exception as e:
            logger.warning("drop_staging %s failed: %s", stg, e)


def build_typed_select(spec: "LoaderSpec", stg_raw: str) -> str:
    """SQL SELECT que converte staging RAW (TEXT cols) para typed values.

    Inclui:
    - BR decimal/date conversion (parser._sql helpers)
    - sentinel coerce → NULL para colunas nullable
    - cast para column_type final
    - rename CSV cols → target cols (column_renames)

    POC: assume cols are TEXT/VARCHAR/INTEGER/BIGINT/DATE/TIMESTAMP/NUMERIC.
    """
    from .parser import (
        br_date_to_sql_expr, br_decimal_to_sql_expr,
        iso_date_to_sql_expr, point_decimal_to_sql_expr,
    )

    parts = []
    for col in spec.columns:
        col_type = spec.column_types.get(col, "TEXT").upper()
        sentinels = spec.column_overrides.get(col, {}).get(
            "null_sentinels", spec.default_null_sentinels
        )

        # Convert TEXT col to typed
        if col_type in ("DATE",):
            if spec.date_format == "br":
                expr = br_date_to_sql_expr(col)
            else:
                expr = iso_date_to_sql_expr(col)
        elif col_type.startswith("NUMERIC") or col_type in ("REAL", "DOUBLE PRECISION"):
            if spec.decimal_format == "br":
                expr = br_decimal_to_sql_expr(col)
            else:
                expr = point_decimal_to_sql_expr(col)
        elif col_type in ("INTEGER", "BIGINT", "SMALLINT", "INT"):
            expr = (
                f"CASE WHEN trim({col}) ~ '^-?[0-9]+$' "
                f"     THEN trim({col})::{col_type} ELSE NULL END"
            )
        elif col_type.startswith("TIMESTAMP"):
            expr = (
                f"CASE WHEN substring(trim({col}), 1, 10) ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$' "
                f"     THEN trim({col})::{col_type} ELSE NULL END"
            )
        else:
            # TEXT, VARCHAR, etc — sentinel coerce + trim
            sentinel_list = ",".join(f"'{s}'" for s in sentinels)
            expr = f"CASE WHEN trim({col}) IN ({sentinel_list}) THEN NULL ELSE trim({col}) END"

        # Use CSV col name in staging (target rename happens at INSERT)
        parts.append(f"{expr} AS {col}")

    return f"SELECT\n  " + ",\n  ".join(parts) + f"\nFROM {stg_raw}"


def build_upsert_sql(spec: "LoaderSpec", stg_typed: str, *, bucket_id: str = None) -> str:
    """SQL para INSERT INTO target ... ON CONFLICT (NK) ... RETURNING xmax.

    Aplica column_renames (CSV col → target col) e derived_columns substitution
    (e.g., {bucket_id} → '2026' literal).

    nk_coalesce_cols: target cols que precisam COALESCE(NULLIF(c, ''), '__NULL__')
    no ON CONFLICT para tratar '' e NULL como equivalentes.
    """
    from .spec import DedupeStrategy

    target = f"{spec.target_schema}.{spec.table}"

    # Build SELECT clause: CSV cols (renamed where needed) + derived
    select_parts = []
    target_cols = []
    for col in spec.columns:
        target_col = spec.column_renames.get(col, col)
        select_parts.append(col)  # raw col name from staging
        target_cols.append(target_col)

    # Derived columns
    for col, expr in spec.derived_columns.items():
        if "{bucket_id}" in expr and bucket_id is not None:
            resolved = expr.replace("{bucket_id}", repr(bucket_id))
        else:
            resolved = expr
        select_parts.append(resolved)
        target_cols.append(col)

    select_clause = ", ".join(select_parts)
    target_cols_str = ", ".join(target_cols)

    # NK list (apply column_renames + nk_coalesce_cols wrapping)
    coalesce_set = set(spec.nk_coalesce_cols)
    nk_list_raw = [spec.column_renames.get(c, c) for c in spec.natural_key]
    nk_list_for_conflict = []
    for c in nk_list_raw:
        if c in coalesce_set:
            nk_list_for_conflict.append(f"COALESCE(NULLIF({c}, ''), '__NULL__')")
        else:
            nk_list_for_conflict.append(c)
    nk_str = ", ".join(nk_list_for_conflict)

    if spec.dedupe_strategy == DedupeStrategy.APPEND:
        sql = f"""WITH ins AS (
            INSERT INTO {target} ({target_cols_str})
            SELECT {select_clause} FROM {stg_typed}
            RETURNING 1
        )
        SELECT count(*) FROM ins"""
    elif spec.dedupe_strategy == DedupeStrategy.UPSERT_DO_NOTHING:
        sql = f"""WITH ins AS (
            INSERT INTO {target} ({target_cols_str})
            SELECT {select_clause} FROM {stg_typed}
            ON CONFLICT ({nk_str}) DO NOTHING
            RETURNING 1
        )
        SELECT count(*) FROM ins"""
    else:
        wm = spec.column_renames.get(spec.watermark_col, spec.watermark_col)
        update_cols = [c for c in target_cols if c not in nk_list_raw]
        update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)
        sql = f"""WITH upserted AS (
            INSERT INTO {target} ({target_cols_str})
            SELECT {select_clause} FROM {stg_typed}
            ON CONFLICT ({nk_str}) DO UPDATE
            SET {update_set}
            WHERE EXCLUDED.{wm} IS NOT NULL
              AND ({target}.{wm} IS NULL OR EXCLUDED.{wm} > {target}.{wm})
            RETURNING xmax
        )
        SELECT
            count(*) FILTER (WHERE xmax = 0) AS rows_inserted,
            count(*) FILTER (WHERE xmax <> 0) AS rows_updated
        FROM upserted"""

    return sql
