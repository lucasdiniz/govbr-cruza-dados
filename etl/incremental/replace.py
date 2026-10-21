"""Replace por bucket (ADR-0015) — o target do bucket passa a ser IGUAL ao arquivo.

Chamado pelo loader logo após o upsert, na MESMA transação do arquivo:

1. Recalcula o ``_nk_md5`` de cada linha do arquivo com a MESMA projeção do
   upsert (``build_target_projection``) e a MESMA função do trigger
   (``etl_admin.nk_md5_<tabela>_row``), montando ``ROW(...)::<tabela>`` com
   cada coluna convertida para o tipo+typmod do target (ex.: DECIMAL(15,2))
   — o mesmo arredondamento do INSERT. (~10x mais rápido que
   ``jsonb_populate_record``: ~2 min vs ~30 min para 2M linhas.)
2. Passa os hashes como ``TEXT[]`` (dado, não relação) para
   ``etl_admin.tce_pb_replace_bucket`` (SECURITY DEFINER, sql/46), que
   valida as guardas G1-G4 (G5 fica no loader), faz backup e remove as linhas do bucket que não
   estão no arquivo.

Qualquer guarda violada levanta ``ReplaceGuardError``: o orchestrator faz
rollback do arquivo inteiro (upsert incluso) e o runner sai com erro.
"""

from __future__ import annotations

import json
import logging
import os

import psycopg2

from .staging import build_target_projection

logger = logging.getLogger(__name__)

GUARD_PREFIX = "GUARDA_REPLACE"
DRY_RUN_ENV = "ETL_REPLACE_DRY_RUN"


class ReplaceGuardError(RuntimeError):
    """Guarda do replace violada — nada do arquivo é gravado."""


class ReplaceDryRun(RuntimeError):
    """Dry-run do replace: estatísticas calculadas, transação deve voltar."""


def _dry_run_enabled() -> bool:
    return os.environ.get(DRY_RUN_ENV, "").strip().lower() in ("1", "true", "yes")


def apply_bucket_replace(main, spec, stg_final: str, *, bucket_id: str, run_id) -> dict:
    """Executa o replace do bucket. Retorna as estatísticas (jsonb da função).

    ``main`` é a conexão transacional do arquivo (sem commit aqui).
    """
    cfg = spec.bucket_replace
    if cfg is None:
        raise ValueError(f"{spec.table}: bucket_replace não configurado")
    try:
        bucket = int(bucket_id)
    except (TypeError, ValueError) as e:
        raise ReplaceGuardError(
            f"{GUARD_PREFIX}: bucket {bucket_id!r} não é um ano"
        ) from e

    target = f"{spec.target_schema}.{spec.table}"
    hash_fn = f"etl_admin.nk_md5_{spec.table}_row"
    select_parts, target_cols = build_target_projection(spec, bucket_id=bucket_id)
    by_col = dict(zip(target_cols, select_parts))
    dry_run = _dry_run_enabled()

    with main.cursor() as cur:
        cur.execute("SELECT to_regprocedure(%s)", (f"{hash_fn}({target})",))
        if cur.fetchone()[0] is None:
            raise ReplaceGuardError(
                f"{GUARD_PREFIX}: {hash_fn}({target}) ausente — rode sql/42"
            )
        # Colunas do target na ordem física, com tipo+typmod: o ROW(...) tem
        # que bater 1:1 com o tipo composto da tabela.
        cur.execute(
            """SELECT a.attname, format_type(a.atttypid, a.atttypmod)
                 FROM pg_attribute a
                WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
                ORDER BY a.attnum""",
            (target,),
        )
        target_attrs = cur.fetchall()
        missing = set(target_cols) - {name for name, _ in target_attrs}
        if missing:
            raise ReplaceGuardError(
                f"{GUARD_PREFIX}: colunas da projeção ausentes em {target}: {sorted(missing)}"
            )
        row_expr = "ROW(" + ", ".join(
            f"({by_col[name]})::{typ}" if name in by_col else f"NULL::{typ}"
            for name, typ in target_attrs
        ) + f")::{target}"
        cur.execute("DROP TABLE IF EXISTS pg_temp._replace_file_hashes")
        cur.execute(
            f"""CREATE TEMP TABLE _replace_file_hashes ON COMMIT DROP AS
                SELECT {hash_fn}({row_expr}) AS h FROM {stg_final}"""
        )
        try:
            cur.execute(
                # ARRAY(...) e avaliado AQUI (contexto do chamador), antes de
                # entrar na funcao SECURITY DEFINER — ver sql/46.
                """SELECT etl_admin.tce_pb_replace_bucket(
                       %s, %s, ARRAY(SELECT h FROM pg_temp._replace_file_hashes), %s,
                       %s, %s, %s)""",
                (
                    spec.table, bucket, str(run_id),
                    cfg.max_orphan_pct, cfg.min_orphan_abs, dry_run,
                ),
            )
        except psycopg2.Error as e:
            msg = (e.diag.message_primary or str(e)) if e.diag else str(e)
            if GUARD_PREFIX in msg:
                raise ReplaceGuardError(msg) from e
            raise
        stats = cur.fetchone()[0]

    if isinstance(stats, str):
        stats = json.loads(stats)
    logger.info(
        "replace %s bucket %s: antes=%s arquivo=%s mantidas=%s "
        "removidas(versao_substituida=%s, ausente_no_arquivo=%s) depois=%s%s",
        spec.table, bucket_id,
        stats.get("linhas_bucket_antes"), stats.get("hashes_arquivo"),
        stats.get("mantidas"), stats.get("remover_versao_substituida"),
        stats.get("remover_ausente_no_arquivo"), stats.get("linhas_bucket_depois"),
        " [DRY-RUN]" if dry_run else "",
    )
    if dry_run:
        raise ReplaceDryRun(f"dry-run {spec.table} bucket {bucket_id}: {json.dumps(stats)}")
    return stats
