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
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import psycopg2

from . import db as etl_db
from .conn import IncrementalLoadContext
from .parser import SchemaDriftError, _dlq_insert, stream_csv_to_staging, validate_csv_header
from .replace import GUARD_PREFIX, ReplaceGuardError, apply_bucket_replace
from .spec import DedupeStrategy, LoaderSpec
from .staging import (
    build_target_projection, build_typed_select, build_upsert_sql, copy_temp_to_staging,
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
    rows_skipped_dup: int = 0
    rows_skipped_stale: int = 0
    rows_conflict_diff_payload: int = 0
    rows_failed: int = 0
    rows_rejected_null_key: int = 0
    rows_coerced_null: int = 0
    rows_deleted: int = 0          # replace por bucket (ADR-0015)
    replace_stats: Optional[dict] = None
    new_watermark: Optional[str] = None
    csv_header_hash: Optional[str] = None
    arquivo_sha256: Optional[str] = None
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
    progresso: Optional[LoadResult] = None,
) -> LoadResult:
    """Pipeline de carga de 1 arquivo CSV. Module-private."""
    if not csv_path.exists():
        return LoadResult(status="failed", error=f"file not found: {csv_path}")

    # Resolve spec para bucket (suporta schema drift histórico)
    spec = _resolve_spec_for_bucket(spec, bucket_id)

    def _vazio(reason: str, csv_header_hash: str = "", staging=None) -> LoadResult:
        prefixo = f"{GUARD_PREFIX} G4: " if spec.bucket_replace is not None else ""
        return LoadResult(
            status="failed",
            error=f"{prefixo}{spec.table} bucket {bucket_id}: {reason}",
            csv_header_hash=csv_header_hash,
            staging_tables=staging or [],
        )

    # Step 0: skip empty files (source publica 0-byte placeholders em alguns meses)
    if csv_path.stat().st_size == 0:
        return _vazio("arquivo de 0 bytes")

    # Step 0b: skip HTML placeholder pages ("Arquivo Sendo Processado")
    try:
        with open(csv_path, "rb") as _fchk:
            _head = _fchk.read(64)
        if _head.lstrip().startswith(b"<!DOCTYPE") or _head.lstrip().startswith(b"<html"):
            return _vazio("arquivo e pagina HTML (placeholder)")
    except Exception:
        pass

    # Step 1+2: validate header + fence
    try:
        csv_hash = validate_csv_header(csv_path, spec)
    except SchemaDriftError as e:
        # Se arquivo só tem header com whitespace/garbage e zero rows,
        # ainda contam como "soft skip" — vamos checar se ele tem só header line
        try:
            with open(csv_path, "rb") as f:
                content = f.read(2048)
            if not content.strip() or content.count(b"\n") <= 1:
                # File tem só header (ou nada) — não é dados reais
                return _vazio("arquivo so com cabecalho")
        except Exception:
            pass
        return LoadResult(status="failed", error=str(e))
    _check_fence(ctx)

    # Step 3: CREATE staging RAW
    stg_raw = staging_name(spec.source, spec.table, ctx.run_id, file_sequence, "raw", bucket_id=bucket_id)
    stg_typed = staging_name(spec.source, spec.table, ctx.run_id, file_sequence, "typed", bucket_id=bucket_id)
    stg_final = staging_name(spec.source, spec.table, ctx.run_id, file_sequence, "final", bucket_id=bucket_id)
    staging_tables = [stg_raw, stg_typed, stg_final]

    create_staging_raw(ctx.main, spec, stg_raw)

    # A identidade da versão usada na DLQ deve existir antes da primeira rejeição.
    antes = csv_path.stat()
    digest = hashlib.sha256()
    with csv_path.open("rb") as fonte:
        for bloco in iter(lambda: fonte.read(1024 * 1024), b""):
            digest.update(bloco)
    arquivo_sha256 = digest.hexdigest()
    if progresso is not None:
        progresso.arquivo_sha256 = arquivo_sha256
        progresso.csv_header_hash = csv_hash
        progresso.error = "pré-parser"
    pp = stream_csv_to_staging(
        csv_path, spec, ctx.dlq,
        run_id=ctx.run_id, source=spec.source, table=spec.table,
        bucket_id=bucket_id, arquivo_sha256=arquivo_sha256,
    )
    rows_streamed = pp.valid_count + pp.rejected_count
    rows_failed_streaming = pp.rejected_count
    if progresso is not None:
        progresso.rows_streamed = rows_streamed
        progresso.rows_failed = rows_failed_streaming
        progresso.error = "COPY"

    # Step 5: COPY temp → staging RAW
    try:
        depois = csv_path.stat()
        if (antes.st_ino, antes.st_dev, antes.st_ctime_ns, antes.st_size) != (
            depois.st_ino, depois.st_dev, depois.st_ctime_ns, depois.st_size
        ):
            raise RuntimeError("Arquivo mudou durante a leitura; versão não confirmada")
        if not rows_streamed:
            return _vazio("arquivo sem linhas", csv_hash, staging_tables)
        copiadas = copy_temp_to_staging(ctx.main, stg_raw, pp.temp_path, [*spec.columns, "_registro_origem"])
        if copiadas != pp.valid_count:
            raise RuntimeError(f"Balanço do COPY divergente: válidas={pp.valid_count}, copiadas={copiadas}")
    finally:
        try:
            pp.temp_path.unlink()
        except OSError:
            pass

    # Step 6+7+8: build typed → CREATE TABLE staging_typed AS SELECT ...
    typed_sql = build_typed_select(spec, stg_raw)
    if progresso is not None:
        progresso.error = "tipagem e validação"
    with ctx.main.cursor() as cur:
        cur.execute(f"CREATE TABLE {stg_typed} AS {typed_sql}")

    # NK NULL move via single SQL (D6 dual-write trade-off: docked em main TX)
    # Replace por bucket (ADR-0015): o arquivo inteiro e a verdade do bucket e
    # o ON CONFLICT usa so o _nk_md5 (que tolera NULL). Desviar linhas com NK
    # declarativa NULL (ex.: municipio vazio em despesas-2023, valor '0' em
    # receitas) faria o replace apagar as copias delas que ja estao no banco.
    if spec.bucket_replace is not None:
        rows_rejected_null_key = 0
    else:
        rows_rejected_null_key = _registrar_nk_nula(spec, ctx, stg_typed, f"{csv_path}#sha256={arquivo_sha256}")

    # Step 8: build staging_final (POC: alias for now if no derived_columns)
    # Derived columns na FORMA literal/SQL acontece no INSERT INTO target via
    # build_upsert_sql, não como CREATE TABLE separada. Para POC com
    # column_renames, stg_final = stg_typed.
    stg_final = stg_typed
    staging_tables = [stg_raw, stg_typed]

    # Step 9: ANALYZE
    with ctx.main.cursor() as cur:
        cur.execute(f"ANALYZE {stg_final}")

    # Durante a contenção não mudar a identidade histórica. Rejeição não
    # autoriza upsert parcial nem avanço da marca; a DLQ sobrevive ao rollback.
    if rows_failed_streaming or rows_rejected_null_key:
        return LoadResult(
            status="partial",
            rows_streamed=rows_streamed,
            rows_failed=rows_failed_streaming + rows_rejected_null_key,
            rows_rejected_null_key=rows_rejected_null_key,
            csv_header_hash=csv_hash,
            arquivo_sha256=arquivo_sha256,
            staging_tables=staging_tables,
            error=f"Arquivo não aplicado: rejeições de leitura={rows_failed_streaming}, NK={rows_rejected_null_key}",
        )

    # Step 12: fence check 2
    _check_fence(ctx)

    # Step 13: UPSERT
    if progresso is not None:
        progresso.error = "upsert e paridade"
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

    restantes = copiadas - rows_inserted - rows_updated
    if restantes < 0 or (spec.dedupe_strategy == DedupeStrategy.APPEND and restantes):
        raise RuntimeError("Balanço do upsert divergente")
    if restantes and not spec.nk_synthetic_md5 and spec.dedupe_strategy == DedupeStrategy.UPSERT_DO_NOTHING:
        # A chave natural pode conflitar com outro pagamento. Após o INSERT,
        # cada ocorrência precisa de um espelho completo na live nesta TX.
        exprs, colunas = build_target_projection(spec, bucket_id=bucket_id)
        proj = ", ".join(f"{e} AS {c}" for e, c in zip(exprs, colunas))
        nk = [spec.column_renames.get(c, c) for c in spec.natural_key]
        chaves = " AND ".join(f"t.{c}=s.{c}" for c in nk)
        iguais = " AND ".join(f"t.{c} IS NOT DISTINCT FROM s.{c}" for c in colunas)
        with ctx.main.cursor() as cur:
            cur.execute(f"""SELECT count(*) FROM (SELECT {proj} FROM {stg_final}) s
                WHERE NOT EXISTS (SELECT FROM {spec.target_schema}.{spec.table} t WHERE {chaves} AND {iguais})""")
            divergentes = cur.fetchone()[0]
        if divergentes:
            return LoadResult(status="partial", rows_streamed=rows_streamed, rows_failed=divergentes,
                              rows_conflict_diff_payload=divergentes, arquivo_sha256=arquivo_sha256,
                              csv_header_hash=csv_hash, staging_tables=staging_tables,
                              error="Conflito de chave natural sem payload equivalente; arquivo não aplicado")

    # Step 13b: replace por bucket (ADR-0015) — mesma transação do upsert.
    rows_deleted = 0
    replace_stats = None
    if spec.bucket_replace is not None:
        if file_sequence != 1:
            raise ReplaceGuardError(
                f"{GUARD_PREFIX}: {spec.table} bucket {bucket_id} tem mais de 1 "
                f"arquivo (seq={file_sequence}); replace exige 1 arquivo = bucket inteiro"
            )
        # G5: linhas do arquivo desviadas para a DLQ (NK NULL) nao entram no
        # conjunto de hashes — as copias delas no banco seriam tratadas como
        # "fora do arquivo" e removidas. Replace exige o arquivo completo.
        if rows_rejected_null_key > 0:
            raise ReplaceGuardError(
                f"{GUARD_PREFIX} G5: {spec.table} bucket {bucket_id} — "
                f"{rows_rejected_null_key} linha(s) do arquivo foram para a DLQ "
                f"(NK NULL); replace exige o arquivo completo"
            )
        _check_fence(ctx)
        replace_stats = apply_bucket_replace(
            ctx.main, spec, stg_final, bucket_id=bucket_id, run_id=ctx.run_id,
        )
        rows_deleted = int(replace_stats.get("removidas") or 0)

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
        rows_skipped_dup=restantes if spec.dedupe_strategy == DedupeStrategy.UPSERT_DO_NOTHING else 0,
        rows_skipped_stale=restantes if spec.dedupe_strategy == DedupeStrategy.UPSERT_DO_UPDATE else 0,
        rows_failed=0,
        rows_deleted=rows_deleted,
        replace_stats=replace_stats,
        new_watermark=new_watermark,
        csv_header_hash=csv_hash,
        arquivo_sha256=arquivo_sha256,
        staging_tables=staging_tables,
    )


def _registrar_nk_nula(
    spec: LoaderSpec,
    ctx: IncrementalLoadContext,
    stg_typed: str,
    csv_path: str,
) -> int:
    """Conta ocorrências (não chaves distintas). A staging inteira reverte se houver rejeições."""
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

    import json

    qtd = 0
    with ctx.main.cursor(name="rejeicoes_nk") as cur:
        cur.execute(f"SELECT _registro_origem, {', '.join(spec.columns)} FROM {stg_typed} WHERE {nk_null_pred}")
        for posicao, *campos in cur:
            registro = {k.lower(): str(v) if v is not None else None for k, v in zip(spec.columns, campos)}
            _dlq_insert(ctx.dlq, ctx.run_id, spec.source, spec.table, csv_path, posicao,
                        json.dumps(registro, ensure_ascii=False), "NK_NULL")
            qtd += 1
    return qtd


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
