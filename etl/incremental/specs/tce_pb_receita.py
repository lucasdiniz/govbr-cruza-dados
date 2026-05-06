"""LoaderSpec para tce_pb_receita.

CSV: 13 cols, ; separator, encoding utf-8 BOM (latin-1 fallback).
Renames:
  codigo_unidade_gestora -> codigo_ug
  descricao_unidade_gestora -> descricao_ug
(municipio já tem nome certo)

Cursor: YEAR_WINDOW (filename is receitas-YYYY.csv).
NK candidata: (municipio, codigo_ug, mes_ano, codigo_receita, codigo_fonte_recurso)
"""
from __future__ import annotations
import re
from datetime import date
from ..spec import LoaderSpec, CursorStrategy, DedupeStrategy

_TCE_BASE = "https://download.tce.pb.gov.br/dados-abertos/dados-consolidados"


def _bucket_from_filename(name: str) -> str | None:
    m = re.match(r"^receitas-(\d{4})\.csv$", name, re.IGNORECASE)
    return m.group(1) if m else None


def _file_pattern(bucket_id: str) -> list[str]:
    return [f"receitas-{bucket_id}.csv"]


def _url_for_bucket(bucket_id: str) -> list[tuple[str, str]]:
    return [(f"{_TCE_BASE}/receitas/receitas-{bucket_id}.zip",
             f"receitas-{bucket_id}.zip")]


def _enumerate_buckets() -> list[str]:
    return [str(y) for y in range(2018, date.today().year + 1)]


COLUMNS = [
    "municipio", "codigo_unidade_gestora", "descricao_unidade_gestora",
    "mes_ano", "ano",
    "codigo_receita", "descricao_receita", "tipo_atualizacao_receita",
    "valor", "codigo_fonte_recurso", "descricao_fonte_recurso",
    "co", "descricao_co",
]

COLUMN_RENAMES = {
    "codigo_unidade_gestora": "codigo_ug",
    "descricao_unidade_gestora": "descricao_ug",
    "valor": "valor",  # explicit (no rename)
}

COLUMN_TYPES = {c: "TEXT" for c in COLUMNS}
COLUMN_TYPES.update({
    "valor": "NUMERIC",
    "ano": "SMALLINT",
})

SPEC = LoaderSpec(
    source="tce_pb",
    table="tce_pb_receita",
    natural_key=[
        "municipio", "codigo_unidade_gestora",
        "mes_ano", "codigo_receita", "codigo_fonte_recurso",
    ],
    cursor_strategy=CursorStrategy.YEAR_WINDOW,
    dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
    columns=COLUMNS,
    column_types=COLUMN_TYPES,
    column_renames=COLUMN_RENAMES,
    nk_coalesce_cols=("codigo_fonte_recurso",),
    csv_delimiter=";",
    csv_quotechar='"',
    derived_columns={},
    watermark_col="ano",
    watermark_type="integer",
    encoding="utf-8-sig",
    encoding_fallback="latin-1",
    decimal_format="br",
    date_format="br",
    refetch_recent_buckets=1,
    file_pattern=_file_pattern,
    bucket_from_filename=_bucket_from_filename,
    url_for_bucket=_url_for_bucket,
    enumerate_buckets=_enumerate_buckets,
)
