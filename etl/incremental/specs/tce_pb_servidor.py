"""LoaderSpec para tce_pb_servidor.

Schema versioning:
- 2018: usa 'municipio' (sem prefix nome_)
- 2019+: usa 'nome_municipio'

CSV: 11 cols, ; separator, encoding utf-8 BOM.
NK: (municipio, codigo_ug, cpf_cnpj, matricula, ano_mes).
"""
from __future__ import annotations
import re
from datetime import date
from typing import Optional
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


# Schema 2019+ (default)
COLUMNS_NEW = [
    "nome_municipio", "codigo_unidade_gestora", "descricao_unidade_gestora",
    "cpf_cnpj", "nome_servidor", "tipo_cargo", "descricao_cargo",
    "valor_vantagem", "data_admissao", "matricula", "ano_mes",
]
COLUMN_RENAMES_NEW = {
    "nome_municipio": "municipio",
    "codigo_unidade_gestora": "codigo_ug",
    "descricao_unidade_gestora": "descricao_ug",
}

# Schema 2018: 'municipio' direto
COLUMNS_OLD = [
    "municipio", "codigo_unidade_gestora", "descricao_unidade_gestora",
    "cpf_cnpj", "nome_servidor", "tipo_cargo", "descricao_cargo",
    "valor_vantagem", "data_admissao", "matricula", "ano_mes",
]
COLUMN_RENAMES_OLD = {
    "codigo_unidade_gestora": "codigo_ug",
    "descricao_unidade_gestora": "descricao_ug",
}


def _columns_per_bucket(bucket_id: str) -> Optional[tuple[list[str], dict[str, str]]]:
    try:
        year = int(bucket_id)
    except ValueError:
        return None
    if year <= 2019:
        return (COLUMNS_OLD, COLUMN_RENAMES_OLD)
    return None


COLUMNS = COLUMNS_NEW
COLUMN_RENAMES = COLUMN_RENAMES_NEW

COLUMN_TYPES = {c: "TEXT" for c in COLUMNS}
COLUMN_TYPES["valor_vantagem"] = "NUMERIC"
COLUMN_TYPES["data_admissao"] = "DATE"
for c in COLUMNS_OLD:
    if c not in COLUMN_TYPES:
        COLUMN_TYPES[c] = "TEXT"


SPEC = LoaderSpec(
    source="tce_pb",
    table="tce_pb_servidor",
    natural_key=[
        "nome_municipio", "codigo_unidade_gestora",
        "cpf_cnpj", "matricula", "ano_mes",
        "tipo_cargo", "valor_vantagem", "descricao_cargo",
        "nome_servidor", "data_admissao",
    ],
    cursor_strategy=CursorStrategy.YEAR_WINDOW,
    dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
    # natural_key abaixo e DECLARATIVO. nk_synthetic_md5=True -> build_upsert_sql
    # usa ON CONFLICT (_nk_md5). Por que md5 e nao NK natural (ADR-0014):
    # municipio (90.047 rows) e nome_servidor (201) tem NULL e fazem parte da
    # NK natural; UNIQUE INDEX trata NULL como distinto -> ON CONFLICT nao
    # dispara -> re-run do bucket DUPLICARIA essas rows. md5 (coalesce->'')
    # trata NULL uniformemente. Requer sql/42 (col+trigger) + sql/42z (index).
    nk_synthetic_md5=True,
    columns=COLUMNS,
    column_types=COLUMN_TYPES,
    column_renames=COLUMN_RENAMES,
    nk_coalesce_cols=("cpf_cnpj", "matricula", "ano_mes", "descricao_cargo"),
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
    columns_per_bucket=_columns_per_bucket,
)

