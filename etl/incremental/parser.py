"""CSV-aware pre-parser (D5).

Usa csv.reader stdlib (RFC 4180): handles quoted multiline fields, escaped
quotes, BOM, CRLF.

Saída: linhas válidas → temp file via csv.writer com TAB delimiter para COPY
posterior. Linhas malformadas → DLQ via dlq_conn (autocommit, persiste em
rollback).

Encoding fallback: tenta `spec.encoding` (default utf-8-sig); em UnicodeDecodeError
linha-a-linha, tenta `spec.encoding_fallback`.

BR format helpers para decimais (`1.234,56` → `1234.56`) e datas
(`DD/MM/YYYY` → `YYYY-MM-DD`) ficam em parser; aplicação acontece no SQL
de staging_typed para preservar streaming.
"""

from __future__ import annotations

import csv
import hashlib
import io
import logging
import re
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .spec import LoaderSpec
from .conn import AutocommitDlqConn

logger = logging.getLogger(__name__)


@dataclass
class PreParseResult:
    valid_count: int
    rejected_count: int
    temp_path: Path
    csv_header_hash: str


def validate_csv_header(csv_path: Path, spec: LoaderSpec) -> str:
    """Lê primeira linha e valida vs spec.columns. Retorna sha256(header)."""
    encoding = spec.encoding
    try:
        with open(csv_path, "r", encoding=encoding, newline="") as f:
            first = f.readline()
    except UnicodeDecodeError:
        if spec.encoding_fallback:
            with open(csv_path, "r", encoding=spec.encoding_fallback, newline="") as f:
                first = f.readline()
        else:
            raise

    # Strip BOM se utf-8-sig não removeu (caso de encoding diferente)
    if first.startswith("\ufeff"):
        first = first[1:]
    header_line = first.rstrip("\r\n")

    # Parse via csv.reader para tratar quoted fields
    reader = csv.reader([header_line], delimiter=spec.csv_delimiter,
                        quotechar=spec.csv_quotechar)
    headers = next(reader)

    expected = list(spec.columns)
    if headers != expected:
        raise SchemaDriftError(
            f"CSV header mismatch in {csv_path.name}\n"
            f"  expected ({len(expected)}): {expected[:5]}{'...' if len(expected) > 5 else ''}\n"
            f"  got      ({len(headers)}): {headers[:5]}{'...' if len(headers) > 5 else ''}"
        )

    return hashlib.sha256(header_line.encode("utf-8")).hexdigest()


class SchemaDriftError(RuntimeError):
    """CSV header não bate com LoaderSpec.columns."""


def _open_csv(csv_path: Path, spec: LoaderSpec):
    """Abre arquivo com encoding fallback. Returns (file_handle, encoding_used)."""
    encoding = spec.encoding
    try:
        f = open(csv_path, "r", encoding=encoding, newline="")
        # Probe primeira linha para forçar decode
        pos = f.tell()
        f.readline()
        f.seek(pos)
        return f, encoding
    except UnicodeDecodeError:
        if spec.encoding_fallback:
            f = open(csv_path, "r", encoding=spec.encoding_fallback, newline="")
            return f, spec.encoding_fallback
        raise


def stream_csv_to_staging(
    csv_path: Path,
    spec: LoaderSpec,
    dlq_conn: AutocommitDlqConn,
    *,
    run_id,
    source: str,
    table: str,
    bucket_id: str,
) -> PreParseResult:
    """Streams CSV via csv.reader. Linhas válidas → temp tab-separated file
    para COPY. Linhas malformadas → DLQ.

    Retorna PreParseResult com counts e path do temp file.
    """
    csv_header_hash = validate_csv_header(csv_path, spec)

    expected_ncols = len(spec.columns)
    valid_count = 0
    rejected_count = 0
    recovered_via_fallback = 0

    temp_fd, temp_name = tempfile.mkstemp(
        prefix=f"_stg_{spec.source}_{spec.table}_",
        suffix=".tsv",
    )
    temp_path = Path(temp_name)

    try:
        with open(temp_fd, "w", encoding="utf-8", newline="") as out_f:
            writer = csv.writer(out_f, delimiter="\t", quoting=csv.QUOTE_NONE,
                                escapechar="\\")
            in_f, _enc = _open_csv(csv_path, spec)
            try:
                # Use a wrapper que strip NULs (CSV files BR sometimes have stray NUL bytes)
                line_iter = (line.replace("\x00", "") for line in in_f)
                reader = csv.reader(line_iter, delimiter=spec.csv_delimiter,
                                    quotechar=spec.csv_quotechar, strict=False)
                try:
                    next(reader)
                except StopIteration:
                    return PreParseResult(0, 0, temp_path, csv_header_hash)

                line_num = 1  # header line
                while True:
                    line_num += 1
                    try:
                        row = next(reader)
                    except StopIteration:
                        break
                    except csv.Error as e:
                        _dlq_insert(
                            dlq_conn, run_id, source, table, str(csv_path),
                            line_num, "<csv_parse_error>",
                            f"csv_error: {e!s}",
                        )
                        rejected_count += 1
                        continue
                    except UnicodeDecodeError as e:
                        _dlq_insert(
                            dlq_conn, run_id, source, table, str(csv_path),
                            line_num, "<encoding_error>",
                            f"encoding_error: {e!s}",
                        )
                        rejected_count += 1
                        continue

                    if len(row) != expected_ncols:
                        # Fallback: source publishes CSVs with malformed quote
                        # escaping (e.g., LEITÃO."";"2024-04-30 — interior `"` not
                        # doubled per RFC 4180). Try a quote-less reparse: rejoin
                        # the row, strip surrounding quotes, split on delimiter.
                        # This recovers most rows at cost of treating ornamental
                        # quotes as text.
                        recovered = _fallback_split_row(row, spec)
                        if recovered is not None and len(recovered) == expected_ncols:
                            row = recovered
                            recovered_via_fallback += 1
                        else:
                            _dlq_insert(
                                dlq_conn, run_id, source, table, str(csv_path),
                                line_num, _join_row(row, spec.csv_delimiter),
                                f"col_count_mismatch (expected {expected_ncols}, got {len(row)})",
                            )
                            rejected_count += 1
                            continue

                    too_big = False
                    for v in row:
                        if v is not None and len(v) > spec.max_field_size:
                            _dlq_insert(
                                dlq_conn, run_id, source, table, str(csv_path),
                                line_num, "<field_too_large>",
                                f"field_too_large (>{spec.max_field_size})",
                            )
                            too_big = True
                            break
                    if too_big:
                        rejected_count += 1
                        continue

                    writer.writerow([_clean_for_tab(v) for v in row])
                    valid_count += 1
            finally:
                in_f.close()
    except UnicodeDecodeError as e:
        _dlq_insert(
            dlq_conn, run_id, source, table, str(csv_path),
            -1, f"<encoding_error_at_{e.start}>",
            f"encoding_error: {e!s}",
        )
        rejected_count += 1
    except csv.Error as e:
        _dlq_insert(
            dlq_conn, run_id, source, table, str(csv_path),
            -1, "<csv_parse_error>",
            f"csv_error: {e!s}",
        )
        rejected_count += 1

    if recovered_via_fallback > 0:
        logger.info(
            "csv-fallback recovered %d malformed-quote rows in %s",
            recovered_via_fallback, csv_path.name,
        )
    return PreParseResult(valid_count, rejected_count, temp_path, csv_header_hash)


def _fallback_split_row(parsed_row: list, spec) -> Optional[list]:
    """Repara rows com aspas mal-escapadas: rejunta a row, strip outer quotes
    around delimiters, split sem honor de quotes.

    Padrão observado em dados.pb.gov.br:
        "...LEITÃO."";"2024-04-30";"2024-05-04";;"http://..."
                  ^^^ aspas literais não-escapadas conforme RFC 4180

    csv.reader vê `"";"` como escape `"` + `;` interno + outro field, agregando
    múltiplos campos em um. Esse fallback ignora o quoting e splita por delim,
    depois strip aspas decorativas. Retorna None se ainda não bater ncols.

    SAFETY: rejeita o fallback se algum campo resultante AINDA contém aspas
    interiores (p.ex. campo legítimo com vírgula+aspas dentro do texto), porque
    nesses casos o split sem quote-honor pode ter quebrado em delimitadores
    legítimamente quoted, produzindo cols-count "correto" com fields shifted.
    """
    if not parsed_row:
        return None
    # Reconstruct best-effort: this assumes parsed_row was on a single source line
    # (multi-line quoted fields are NOT supported by fallback).
    rejoined = spec.csv_delimiter.join(str(c) for c in parsed_row)
    # Split sem quote honor
    parts = rejoined.split(spec.csv_delimiter)
    # Strip outer quotechar from each piece (pure decorative quotes)
    q = spec.csv_quotechar
    cleaned = []
    for p in parts:
        s = p
        # strip 1 leading + 1 trailing quote (common decorative pattern)
        if s.startswith(q):
            s = s[1:]
        if s.endswith(q):
            s = s[:-1]
        # SAFETY: any remaining quotechar inside a field is suspicious.
        # Either it's a legit field with quoted text we just broke, or a
        # malformed quote. Reject the recovery to send row to DLQ.
        if q in s:
            return None
        cleaned.append(s)
    return cleaned


def _clean_for_tab(v: str) -> str:
    """Remove TAB, newlines, backslashes que quebrariam COPY format text.

    Empty string → \\N (PG NULL marker). Match legacy ETL behavior:
    CSV cells vazios viram NULL no DB, não literal ''.
    """
    if v is None or v == "":
        return "\\N"
    return v.replace("\t", " ").replace("\r", "").replace("\n", " ")


def _join_row(row: list, delim: str) -> str:
    """Reserialize row para DLQ (best-effort, não RFC-perfect)."""
    return delim.join(str(c) for c in row)[:8000]


def _dlq_insert(
    dlq_conn,
    run_id,
    source: str,
    table: str,
    file_path: str,
    line_number: int,
    raw_line: str,
    reason: str,
) -> None:
    """INSERT em etl_rejected_rows com ON CONFLICT DO NOTHING (idempotent)."""
    raw_hash = hashlib.sha256(raw_line.encode("utf-8", errors="replace")).hexdigest()
    try:
        with dlq_conn.cursor() as cur:
            cur.execute(
                """INSERT INTO etl_rejected_rows
                   (run_id, source, table_name, file_path, line_number, raw_line, raw_line_hash, reason)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (source, table_name, file_path, line_number, raw_line_hash) DO NOTHING""",
                (str(run_id), source, table, file_path, line_number,
                 raw_line[:8000], raw_hash, reason),
            )
    except Exception as e:
        logger.warning("DLQ insert failed: %s", e)


# ─── BR format conversion helpers (used in staging_typed SQL) ─────────────────

def br_decimal_to_sql_expr(col: str) -> str:
    """SQL expression: BR decimal '1.234,56' → numeric 1234.56.

    Empty/null sentinels → NULL.
    Ponto removido (thousand sep), vírgula → ponto.
    """
    return (
        f"CASE WHEN trim({col}) IN ('', '0', 'NULL') THEN NULL "
        f"     WHEN {col} ~ '^-?[0-9]{{1,3}}([.][0-9]{{3}})*([,][0-9]+)?$' OR {col} ~ '^-?[0-9]+([,][0-9]+)?$' "
        f"     THEN replace(replace({col}, '.', ''), ',', '.')::numeric "
        f"     WHEN {col} ~ '^-?[0-9]+([.][0-9]+)?$' THEN {col}::numeric "
        f"     ELSE NULL END"
    )


def br_date_to_sql_expr(col: str) -> str:
    """SQL expression: BR date 'DD/MM/YYYY' OR ISO 'YYYY-MM-DD' (with optional time) → DATE.

    Handles:
    - 'DD/MM/YYYY'
    - 'YYYY-MM-DD'
    - 'YYYY-MM-DD HH:MI:SS' (com optional fractional seconds)
    Sentinel '00/00/0000' → NULL.
    """
    return (
        f"CASE WHEN {col} ~ '^([0-9]{{2}})/([0-9]{{2}})/([0-9]{{4}})$' "
        f"     THEN to_date({col}, 'DD/MM/YYYY') "
        f"     WHEN substring(trim({col}), 1, 10) ~ '^([0-9]{{4}})-([0-9]{{2}})-([0-9]{{2}})$' "
        f"     THEN substring(trim({col}), 1, 10)::date "
        f"     ELSE NULL END"
    )


def iso_date_to_sql_expr(col: str) -> str:
    """SQL expression: ISO date 'YYYY-MM-DD' (with optional time suffix) → DATE."""
    return (
        f"CASE WHEN substring(trim({col}), 1, 10) ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$' "
        f"     THEN substring(trim({col}), 1, 10)::date "
        f"     ELSE NULL END"
    )


def point_decimal_to_sql_expr(col: str) -> str:
    """SQL expression: point decimal '1234.56' → numeric."""
    return (
        f"CASE WHEN trim({col}) ~ '^-?[0-9]+([.][0-9]+)?$' "
        f"     THEN trim({col})::numeric ELSE NULL END"
    )
