"""LoaderSpec para tce_pb_licitacao.

CSV: 13 cols, ; separator, encoding utf-8 BOM (latin-1 fallback).
Renames:
  nome_municipio -> municipio
  codigo_unidade_gestora -> codigo_ug
  descricao_unidade_gestora -> descricao_ug

Cursor: YEAR_WINDOW.
NK candidata: (municipio, codigo_ug, numero_licitacao, ano_licitacao, cpf_cnpj_proponente)
"""
from __future__ import annotations
import re
from datetime import date
from ..spec import LoaderSpec, CursorStrategy, DedupeStrategy

_TCE_BASE = "https://download.tce.pb.gov.br/dados-abertos/dados-consolidados"


def _bucket_from_filename(name: str) -> str | None:
    m = re.match(r"^licitacoes-(\d{4})\.csv$", name, re.IGNORECASE)
    return m.group(1) if m else None


def _file_pattern(bucket_id: str) -> list[str]:
    return [f"licitacoes-{bucket_id}.csv"]


def _url_for_bucket(bucket_id: str) -> list[tuple[str, str]]:
    return [(f"{_TCE_BASE}/licitacoes/licitacoes-{bucket_id}.zip",
             f"licitacoes-{bucket_id}.zip")]


def _enumerate_buckets() -> list[str]:
    return [str(y) for y in range(2018, date.today().year + 1)]


COLUMNS = [
    "nome_municipio", "codigo_unidade_gestora", "descricao_unidade_gestora",
    "numero_licitacao", "numero_protocolo_tce", "ano_licitacao",
    "modalidade", "objeto_licitacao", "data_homologacao",
    "nome_proponente", "cpf_cnpj_proponente", "valor_ofertado", "situacao_proposta",
]

COLUMN_RENAMES = {
    "nome_municipio": "municipio",
    "codigo_unidade_gestora": "codigo_ug",
    "descricao_unidade_gestora": "descricao_ug",
}

COLUMN_TYPES = {c: "TEXT" for c in COLUMNS}
COLUMN_TYPES.update({
    "valor_ofertado": "NUMERIC",
    "data_homologacao": "DATE",
    "ano_licitacao": "SMALLINT",
})

SPEC = LoaderSpec(
    source="tce_pb",
    table="tce_pb_licitacao",
    natural_key=[
        "nome_municipio", "codigo_unidade_gestora",
        "numero_licitacao", "ano_licitacao", "cpf_cnpj_proponente",
        "valor_ofertado", "situacao_proposta", "modalidade",
        "numero_protocolo_tce", "nome_proponente",
    ],
    cursor_strategy=CursorStrategy.YEAR_WINDOW,
    dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
    columns=COLUMNS,
    column_types=COLUMN_TYPES,
    column_renames=COLUMN_RENAMES,
    nk_coalesce_cols=(
        "numero_licitacao", "cpf_cnpj_proponente",
        "situacao_proposta", "modalidade",
        "numero_protocolo_tce", "nome_proponente",
    ),
    csv_delimiter=";",
    csv_quotechar='"',
    derived_columns={},
    watermark_col="ano_licitacao",
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
