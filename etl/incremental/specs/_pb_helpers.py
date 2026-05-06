"""Helper para gerar LoaderSpec Dados-PB MONTH_WINDOW typical pattern.

Pattern: filename {prefix}_{ano}_{mes}.csv, latin-1, ; quote ", iso date, point decimal.
"""
from __future__ import annotations
import re
from datetime import date
from typing import Optional, Callable
from ..spec import LoaderSpec, CursorStrategy, DedupeStrategy

_PB_BASE = "https://dados.pb.gov.br:443/getcsv"


def make_month_window_spec(
    *,
    table: str,
    api_name: str,
    file_prefix: str,
    columns: list[str],
    natural_key: list[str],
    nk_coalesce_cols: tuple[str, ...] = (),
    column_types_override: Optional[dict[str, str]] = None,
    column_renames_override: Optional[dict[str, str]] = None,
    watermark_col_csv: Optional[str] = None,
    watermark_type: str = "string",
    refetch_recent_buckets: int = 2,
) -> LoaderSpec:
    """Cria LoaderSpec para Dados-PB com cursor mensal.

    `columns`: nomes UPPERCASE (ou exatos) do CSV.
    `natural_key`: subset de columns (CSV names).
    `nk_coalesce_cols`: TARGET names (lowercase após rename).
    `column_renames_override`: se None, default = lowercase de columns.
    """

    def _bucket_from_filename(name: str) -> str | None:
        m = re.match(rf"^{re.escape(file_prefix)}_(\d{{4}})_(\d{{2}})\.csv$", name, re.IGNORECASE)
        return f"{m.group(1)}-{m.group(2)}" if m else None

    def _file_pattern(bucket_id: str) -> list[str]:
        year, month = bucket_id.split("-")
        return [f"{file_prefix}_{year}_{month}.csv"]

    def _url_for_bucket(bucket_id: str) -> list[tuple[str, str]]:
        year, month = bucket_id.split("-")
        return [(f"{_PB_BASE}?nome={api_name}&exercicio={year}&mes={int(month)}",
                 f"{file_prefix}_{year}_{month}.csv")]

    def _enumerate_buckets() -> list[str]:
        today = date.today()
        out = []
        for year in range(2018, today.year + 1):
            max_month = today.month if year == today.year else 12
            for month in range(1, max_month + 1):
                out.append(f"{year}-{month:02d}")
        return out

    column_renames = column_renames_override or {c: c.lower() for c in columns}
    column_types = {c: "TEXT" for c in columns}
    if column_types_override:
        column_types.update(column_types_override)

    return LoaderSpec(
        source="dados_pb",
        table=table,
        natural_key=natural_key,
        cursor_strategy=CursorStrategy.MONTH_WINDOW,
        dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
        columns=columns,
        column_types=column_types,
        column_renames=column_renames,
        nk_coalesce_cols=nk_coalesce_cols,
        csv_delimiter=";",
        csv_quotechar='"',
        derived_columns={},
        watermark_col=watermark_col_csv,
        watermark_type=watermark_type,
        encoding="latin-1",
        encoding_fallback="utf-8-sig",
        decimal_format="point",
        date_format="iso",
        refetch_recent_buckets=refetch_recent_buckets,
        file_pattern=_file_pattern,
        bucket_from_filename=_bucket_from_filename,
        url_for_bucket=_url_for_bucket,
        enumerate_buckets=_enumerate_buckets,
    )


def make_year_window_spec(
    *,
    table: str,
    api_name: str,
    file_prefix: str,
    columns: list[str],
    natural_key: list[str],
    nk_coalesce_cols: tuple[str, ...] = (),
    column_types_override: Optional[dict[str, str]] = None,
    column_renames_override: Optional[dict[str, str]] = None,
    watermark_col_csv: Optional[str] = None,
    watermark_type: str = "string",
    refetch_recent_buckets: int = 1,
) -> LoaderSpec:
    """Cria LoaderSpec para Dados-PB com cursor anual."""

    def _bucket_from_filename(name: str) -> str | None:
        m = re.match(rf"^{re.escape(file_prefix)}_(\d{{4}})\.csv$", name, re.IGNORECASE)
        return m.group(1) if m else None

    def _file_pattern(bucket_id: str) -> list[str]:
        return [f"{file_prefix}_{bucket_id}.csv"]

    def _url_for_bucket(bucket_id: str) -> list[tuple[str, str]]:
        return [(f"{_PB_BASE}?nome={api_name}&exercicio={bucket_id}",
                 f"{file_prefix}_{bucket_id}.csv")]

    def _enumerate_buckets() -> list[str]:
        return [str(y) for y in range(2018, date.today().year + 1)]

    column_renames = column_renames_override or {c: c.lower() for c in columns}
    column_types = {c: "TEXT" for c in columns}
    if column_types_override:
        column_types.update(column_types_override)

    return LoaderSpec(
        source="dados_pb",
        table=table,
        natural_key=natural_key,
        cursor_strategy=CursorStrategy.YEAR_WINDOW,
        dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
        columns=columns,
        column_types=column_types,
        column_renames=column_renames,
        nk_coalesce_cols=nk_coalesce_cols,
        csv_delimiter=";",
        csv_quotechar='"',
        derived_columns={},
        watermark_col=watermark_col_csv,
        watermark_type=watermark_type,
        encoding="latin-1",
        encoding_fallback="utf-8-sig",
        decimal_format="point",
        date_format="iso",
        refetch_recent_buckets=refetch_recent_buckets,
        file_pattern=_file_pattern,
        bucket_from_filename=_bucket_from_filename,
        url_for_bucket=_url_for_bucket,
        enumerate_buckets=_enumerate_buckets,
    )
