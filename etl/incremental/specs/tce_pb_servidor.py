"""LoaderSpec para tce_pb_servidor.

CSV: 11 cols, ; separator, encoding utf-8 BOM (latin-1 fallback).
Renames:
  nome_municipio -> municipio
  codigo_unidade_gestora -> codigo_ug
  descricao_unidade_gestora -> descricao_ug

Cursor: YEAR_WINDOW. NK candidata: (municipio, codigo_ug, cpf_cnpj, matricula, ano_mes).
"""
from __future__ import annotations
import re
from datetime import date
from ..spec import LoaderSpec, CursorStrategy, DedupeStrategy

_TCE_BASE = "https://download.tce.pb.gov.br/dados-abertos/dados-consolidados"


def _bucket_from_filename(name: str) -> str | None:
    m = re.match(r"^servidores-(\d{4})\.csv$", name, re.IGNORECASE)
    return m.group(1) if m else None


def _file_pattern(bucket_id: str) -> list[str]:
    return [f"servidores-{bucket_id}.csv"]


def _url_for_bucket(bucket_id: str) -> list[tuple[str, str]]:
    return [(f"{_TCE_BASE}/servidores/servidores-{bucket_id}.zip",
             f"servidores-{bucket_id}.zip")]


def _enumerate_buckets() -> list[str]:
    return [str(y) for y in range(2018, date.today().year + 1)]


COLUMNS = [
    "nome_municipio", "codigo_unidade_gestora", "descricao_unidade_gestora",
    "cpf_cnpj", "nome_servidor", "tipo_cargo", "descricao_cargo",
    "valor_vantagem", "data_admissao", "matricula", "ano_mes",
]

COLUMN_RENAMES = {
    "nome_municipio": "municipio",
    "codigo_unidade_gestora": "codigo_ug",
    "descricao_unidade_gestora": "descricao_ug",
}

COLUMN_TYPES = {c: "TEXT" for c in COLUMNS}
COLUMN_TYPES.update({
    "valor_vantagem": "NUMERIC",
    "data_admissao": "DATE",
})

SPEC = LoaderSpec(
    source="tce_pb",
    table="tce_pb_servidor",
    natural_key=[
        "nome_municipio", "codigo_unidade_gestora", "cpf_cnpj", "matricula", "ano_mes",
    ],
    cursor_strategy=CursorStrategy.YEAR_WINDOW,
    dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
    columns=COLUMNS,
    column_types=COLUMN_TYPES,
    column_renames=COLUMN_RENAMES,
    nk_coalesce_cols=("cpf_cnpj", "matricula", "ano_mes"),
    csv_delimiter=";",
    csv_quotechar='"',
    derived_columns={},
    watermark_col="ano_mes",
    watermark_type="string",
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
