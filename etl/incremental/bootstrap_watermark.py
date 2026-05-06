"""bootstrap_watermark — registra estado inicial do watermark para uma spec.

Roda uma vez antes do primeiro incremental run em produção. Captura:
- bootstrap_target_max: MAX(watermark_col) do target atual
- bootstrap_target_count: COUNT(*) do target atual
- target_schema_hash: sha256 do DDL do target

Idempotent: se watermark já existe, refuse to overwrite (precisa --force).

Uso:
    python -m etl.incremental.bootstrap_watermark --source tce_pb --table tce_pb_despesa
    python -m etl.incremental.bootstrap_watermark --source dados_pb --table pb_pagamento
    python -m etl.incremental.bootstrap_watermark --all  # bootstrap todas as specs registradas
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from typing import Optional

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _compute_target_schema_hash(conn, schema: str, table: str) -> str:
    """sha256 do schema definition (cols, types, nullable, NK index)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        cols = cur.fetchall()
    canonical = ";".join(f"{c[0]}|{c[1]}|{c[2]}" for c in cols)
    return hashlib.sha256(canonical.encode()).hexdigest()


def _bootstrap_one(govbr_conn, spec, *, force: bool = False) -> bool:
    """Bootstrap a single spec. Returns True if applied, False if skipped."""
    target = f"{spec.target_schema}.{spec.table}"
    wm_col = spec.watermark_col

    # Check existing
    with govbr_conn.cursor() as cur:
        cur.execute(
            """SELECT bootstrap_target_max, bootstrap_target_count, bootstrapped_at
               FROM etl_watermark WHERE source=%s AND table_name=%s""",
            (spec.source, spec.table),
        )
        existing = cur.fetchone()

    # `bootstrapped_at IS NOT NULL` is the canonical completion marker, since
    # `bootstrap_target_max` can legitimately be NULL (empty target/all-NULL
    # watermark column). Don't re-bootstrap if completion marker is set unless
    # operator explicitly forces.
    if existing and existing[2] is not None and not force:
        logger.warning(
            "  [skip] %s.%s already bootstrapped (max=%s, count=%s, at=%s). Use --force to overwrite.",
            spec.source, spec.table, existing[0], existing[1], existing[2],
        )
        return False

    # Compute schema hash
    schema_hash = _compute_target_schema_hash(govbr_conn, spec.target_schema, spec.table)

    # Compute MAX(watermark_col)
    target_max = None
    if wm_col:
        # Translate wm_col CSV name → target name if necessary
        target_wm = spec.column_renames.get(wm_col, wm_col)
        # Skip if derived (e.g., ano_arquivo from bucket_id)
        if wm_col not in spec.derived_columns:
            with govbr_conn.cursor() as cur:
                if spec.watermark_type == "timestamp":
                    cur.execute(
                        f"SELECT to_char(MAX({target_wm}), 'YYYY-MM-DD\"T\"HH24:MI:SS.US') FROM {target}"
                    )
                else:
                    cur.execute(f"SELECT MAX({target_wm})::text FROM {target}")
                row = cur.fetchone()
                target_max = row[0] if row else None
        else:
            # Derived watermark — capture max already in target
            target_wm_in_target = spec.column_renames.get(wm_col, wm_col)
            with govbr_conn.cursor() as cur:
                cur.execute(f"SELECT MAX({target_wm_in_target})::text FROM {target}")
                row = cur.fetchone()
                target_max = row[0] if row else None

    # Compute COUNT(*)
    with govbr_conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {target}")
        target_count = cur.fetchone()[0]

    # Insert/Update watermark — but bootstrap_* fields are immutable via trigger.
    # We bypass via direct INSERT (initial) ou via reset_watermark.
    with govbr_conn.cursor() as cur:
        if existing:
            # Use bootstrapped_at as completion marker: if NULL, this row is in
            # incomplete state (partial bootstrap from a previous failure) and
            # we can UPDATE freely. If NOT NULL, completion is recorded and the
            # immutability trigger blocks UPDATE → must use DELETE+INSERT.
            if existing[2] is None:
                cur.execute(
                    """UPDATE etl_watermark
                       SET bootstrap_target_max = %s,
                           bootstrap_target_count = %s,
                           bootstrapped_at = now(),
                           bootstrapped_by = current_user,
                           target_schema_hash = %s
                       WHERE source = %s AND table_name = %s""",
                    (target_max, target_count, schema_hash, spec.source, spec.table),
                )
            else:
                # Force overwrite (--force): trigger blocks UPDATE of bootstrapped_at,
                # so we DELETE the row and re-INSERT with fresh values. Reset of
                # last_value to NULL means subsequent runs treat as new spec
                # (no upper-bound watermark check). Operator should be aware.
                cur.execute(
                    "DELETE FROM etl_watermark WHERE source=%s AND table_name=%s",
                    (spec.source, spec.table),
                )
                cur.execute(
                    """INSERT INTO etl_watermark
                       (source, table_name, last_value, watermark_type,
                        bootstrap_target_max, bootstrap_target_count,
                        bootstrapped_at, bootstrapped_by, target_schema_hash)
                       VALUES (%s, %s, NULL, %s, %s, %s, now(), current_user, %s)""",
                    (spec.source, spec.table, spec.watermark_type or "string",
                     target_max, target_count, schema_hash),
                )
        else:
            cur.execute(
                """INSERT INTO etl_watermark
                   (source, table_name, last_value, watermark_type,
                    bootstrap_target_max, bootstrap_target_count,
                    bootstrapped_at, bootstrapped_by, target_schema_hash)
                   VALUES (%s, %s, NULL, %s, %s, %s, now(), current_user, %s)""",
                (spec.source, spec.table, spec.watermark_type or "string",
                 target_max, target_count, schema_hash),
            )
    govbr_conn.commit()
    logger.info(
        "  [ok] %s.%s bootstrapped: max=%s count=%s schema_hash=%s...",
        spec.source, spec.table, target_max, target_count, schema_hash[:16],
    )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="source (e.g., tce_pb)")
    parser.add_argument("--table", help="table (e.g., tce_pb_despesa)")
    parser.add_argument("--all", action="store_true", help="bootstrap all registered specs")
    parser.add_argument("--force", action="store_true", help="overwrite existing bootstrap")
    parser.add_argument("--govbr-dsn", default=None, help="superuser DSN")
    args = parser.parse_args()

    if not args.govbr_dsn:
        from etl.config import DSN
        args.govbr_dsn = DSN

    from etl.incremental.runner import _load_all_specs
    all_specs = _load_all_specs()

    if args.all:
        specs_to_run = all_specs
    elif args.source and args.table:
        key = f"{args.source}.{args.table}"
        if key not in all_specs:
            logger.error("Unknown spec: %s", key)
            return 2
        specs_to_run = {key: all_specs[key]}
    else:
        parser.error("--source+--table or --all required")

    govbr_conn = psycopg2.connect(args.govbr_dsn)
    try:
        for key, spec in specs_to_run.items():
            try:
                _bootstrap_one(govbr_conn, spec, force=args.force)
            except Exception as e:
                logger.exception("bootstrap %s failed: %s", key, e)
                govbr_conn.rollback()
    finally:
        govbr_conn.close()


if __name__ == "__main__":
    sys.exit(main())
