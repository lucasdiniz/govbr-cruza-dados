"""ETL Incremental runner — entry point para `python -m etl.incremental.runner`.

Itera todas LoaderSpec registradas e roda incremental for each. Suporta filtro
via --only "source.table,source.table" CSV.

Falha workflow se qualquer spec terminar com status='failed' (não 'partial' ou
'success'). 'partial' = avisa mas não falha (NK NULL rows são esperados em
produção e não são erros graves).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _load_all_specs():
    """Discover all LoaderSpec instances in etl.incremental.specs.*"""
    from etl.incremental.specs import pb_pagamento, pb_empenho, pb_contrato
    from etl.incremental.specs import tce_pb_despesa, tce_pb_servidor, tce_pb_licitacao, tce_pb_receita
    from etl.incremental.specs.pb_extras import ALL_SPECS as PB_EXTRAS

    specs = {
        f"{spec.source}.{spec.table}": spec
        for spec in [
            tce_pb_despesa.SPEC,
            tce_pb_servidor.SPEC,
            tce_pb_licitacao.SPEC,
            tce_pb_receita.SPEC,
            pb_pagamento.SPEC,
            pb_empenho.SPEC,
            pb_contrato.SPEC,
        ]
    }
    for spec in PB_EXTRAS.values():
        specs[f"{spec.source}.{spec.table}"] = spec
    return specs


def _data_dir_for_source(source: str, base: Path) -> Path:
    return base / source


def _auto_bootstrap_if_needed(specs_to_run: dict, govbr_dsn: str) -> list:
    """Bootstrap automatico de specs ainda sem etl_watermark row OU sem
    bootstrap_target_max preenchido (caso de bootstrap parcial anterior).

    Idempotent: skip apenas se bootstrap_target_max IS NOT NULL (estado completo).

    Em prod: garante que primeira run apos deploy tenha 'foto inicial' do
    target capturada antes de qualquer mutacao. Falhas de bootstrap são
    tratadas como FATAL: retorna lista de spec keys com falha pra runner
    abortar antes de mutar targets sem baseline.
    """
    import psycopg2

    try:
        from etl.incremental.bootstrap_watermark import _bootstrap_one
    except ImportError:
        logger.warning("bootstrap_watermark module not available; skipping auto-bootstrap")
        return []

    needs_bootstrap = []
    with psycopg2.connect(govbr_dsn) as conn:
        with conn.cursor() as cur:
            for key, spec in specs_to_run.items():
                cur.execute(
                    """SELECT bootstrapped_at
                       FROM etl_watermark
                       WHERE source=%s AND table_name=%s""",
                    (spec.source, spec.table),
                )
                row = cur.fetchone()
                # bootstrapped_at IS NOT NULL is the canonical completion marker.
                # bootstrap_target_max can legitimately be NULL (empty target,
                # all-NULL watermark column), so we don't gate on it. Trigger
                # in sql/22 makes bootstrapped_at immutable once set.
                if row is None or row[0] is None:
                    needs_bootstrap.append((key, spec))

    if not needs_bootstrap:
        return []

    logger.info("Auto-bootstrap: %d spec(s) needing bootstrap", len(needs_bootstrap))
    failed_keys = []
    # Per-spec connection: if one bootstrap fails, transaction abort doesn't
    # poison subsequent specs. Each spec gets its own clean connection.
    for key, spec in needs_bootstrap:
        try:
            with psycopg2.connect(govbr_dsn) as spec_conn:
                applied = _bootstrap_one(spec_conn, spec, force=False)
                if applied:
                    logger.info("Auto-bootstrap: %s applied", key)
                else:
                    logger.info("Auto-bootstrap: %s skipped (already bootstrapped)", key)
        except Exception as e:
            logger.exception("Auto-bootstrap: %s FAILED: %s", key, e)
            failed_keys.append(key)
    return failed_keys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default="", help='CSV "source.table,source.table"')
    parser.add_argument("--data-dir", default=os.environ.get("DATA_DIR"))
    parser.add_argument("--dsn", default=None, help="Override DSN")
    parser.add_argument("--govbr-dsn", default=None, help="Override govbr DSN (admin)")
    parser.add_argument("--triggered-by", default=os.environ.get("ETL_TRIGGERED_BY", "cli"))
    parser.add_argument("--commit-sha", default=os.environ.get("GITHUB_SHA"))
    parser.add_argument("--max-runtime-s", type=int, default=6 * 3600)
    args = parser.parse_args()

    # Default DSNs from etl.config
    if not args.dsn:
        from etl.config import DSN
        args.dsn = DSN
    if not args.govbr_dsn:
        args.govbr_dsn = args.dsn

    if not args.data_dir:
        from etl.config import DATA_DIR
        args.data_dir = str(DATA_DIR)
    data_dir_base = Path(args.data_dir)

    all_specs = _load_all_specs()

    if args.only:
        only_keys = set(args.only.split(","))
        unknown = only_keys - set(all_specs.keys())
        if unknown:
            logger.error("Unknown specs: %s. Known: %s",
                         unknown, list(all_specs.keys()))
            return 2
        specs_to_run = {k: v for k, v in all_specs.items() if k in only_keys}
    else:
        specs_to_run = all_specs

    logger.info("Running %d specs: %s", len(specs_to_run), list(specs_to_run.keys()))

    # Auto-bootstrap: any spec without etl_watermark row OR with NULL bootstrap
    # fields gets bootstrapped automatically. Failed bootstraps remove that
    # spec from the run to prevent mutating targets without baseline snapshot.
    bootstrap_failed = _auto_bootstrap_if_needed(specs_to_run, args.govbr_dsn)
    if bootstrap_failed:
        logger.error("Removing specs with failed bootstrap from this run: %s",
                     bootstrap_failed)
        for key in bootstrap_failed:
            specs_to_run.pop(key, None)
        if not specs_to_run:
            logger.error("All specs failed bootstrap; aborting.")
            return 3

    from etl.incremental.orchestrator import run_incremental_for_source

    summaries = []
    for key, spec in specs_to_run.items():
        logger.info("=== START %s ===", key)
        data_dir = _data_dir_for_source(spec.source, data_dir_base)
        try:
            summary = run_incremental_for_source(
                spec,
                data_dir=data_dir,
                dsn=args.dsn,
                govbr_dsn=args.govbr_dsn,
                triggered_by=args.triggered_by,
                commit_sha=args.commit_sha,
                max_runtime_s=args.max_runtime_s,
            )
        except Exception as e:
            logger.exception("=== FAIL %s: %s ===", key, e)
            summary = {"status": "failed", "error_message": str(e), "buckets": []}
        summaries.append((key, summary))

        status = summary["status"]
        n_success = sum(1 for b in summary.get("buckets", []) if getattr(b, "all_success", False))
        n_total = len(summary.get("buckets", []))
        n_inserted = sum(getattr(b, "total_inserted", 0) for b in summary.get("buckets", []))
        logger.info("=== END %s status=%s buckets=%d/%d inserted=%d ===",
                    key, status, n_success, n_total, n_inserted)

    # Final report
    print("\n" + "=" * 60)
    print("INCREMENTAL ETL SUMMARY")
    print("=" * 60)
    n_failed = 0
    for key, summary in summaries:
        status = summary["status"]
        marker = "✓" if status == "success" else ("⚠" if status == "partial" else "✗")
        n_buckets = len(summary.get("buckets", []))
        n_success = sum(1 for b in summary.get("buckets", []) if getattr(b, "all_success", False))
        n_inserted = sum(getattr(b, "total_inserted", 0) for b in summary.get("buckets", []))
        print(f"  {marker} {key}: {status} ({n_success}/{n_buckets} buckets, +{n_inserted} rows)")
        if status == "failed":
            n_failed += 1

    print(f"\nTotal: {len(summaries)} specs, {n_failed} failed")
    return 1 if n_failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
