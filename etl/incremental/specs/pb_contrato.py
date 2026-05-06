"""LoaderSpec para pb_contrato (Dados-PB).

Filename: contratos_YYYY.csv. Cursor: YEAR_WINDOW.
NK: (codigo_contrato, numero_registro_cge)
"""
from __future__ import annotations
import re
from datetime import date
from ..spec import LoaderSpec, CursorStrategy, DedupeStrategy

_PB_BASE = "https://dados.pb.gov.br:443/getcsv"


def _bucket_from_filename(name: str) -> str | None:
    m = re.match(r"^contratos_(\d{4})\.csv$", name, re.IGNORECASE)
    return m.group(1) if m else None


def _file_pattern(bucket_id: str) -> list[str]:
    return [f"contratos_{bucket_id}.csv"]


def _url_for_bucket(bucket_id: str) -> list[tuple[str, str]]:
    return [(f"{_PB_BASE}?nome=contratos&exercicio={bucket_id}",
             f"contratos_{bucket_id}.csv")]


def _enumerate_buckets() -> list[str]:
    return [str(y) for y in range(2018, date.today().year + 1)]


COLUMNS = [
    "CODIGO_CONTRATO", "NUMERO_REGISTRO_CGE", "NUMERO_CONTRATO",
    "NOME_CONTRATANTE", "NUMERO_PROCESSO_LICITATORIO",
    "OBJETO_CONTRATO", "COMPLEMENTO_OBJETO_CONTRATO",
    "NOME_CONTRATADO", "CPFCNPJ_CONTRATADO",
    "DATA_CELEBRACAO_CONTRATO", "DATA_PUBLICACAO",
    "DATA_INICIO_VIGENCIA", "DATA_TERMINO_VIGENCIA",
    "VALOR_ORIGINAL", "NOME_MUNICIPIO", "OUTROS_MUNICIPIOS",
    "NOME_GESTOR_CONTRATO", "NUMERO_PORTARIA",
    "DATA_PUBLICACAO_PORTARIA", "URL_CONTRATO",
]

COLUMN_RENAMES = {c: c.lower() for c in COLUMNS}

COLUMN_TYPES = {c: "TEXT" for c in COLUMNS}
COLUMN_TYPES["VALOR_ORIGINAL"] = "NUMERIC"
COLUMN_TYPES["DATA_CELEBRACAO_CONTRATO"] = "DATE"
COLUMN_TYPES["DATA_PUBLICACAO"] = "DATE"
COLUMN_TYPES["DATA_INICIO_VIGENCIA"] = "DATE"
COLUMN_TYPES["DATA_TERMINO_VIGENCIA"] = "DATE"
COLUMN_TYPES["DATA_PUBLICACAO_PORTARIA"] = "DATE"


SPEC = LoaderSpec(
    source="dados_pb",
    table="pb_contrato",
    natural_key=["CODIGO_CONTRATO", "NUMERO_REGISTRO_CGE"],
    cursor_strategy=CursorStrategy.YEAR_WINDOW,
    dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
    columns=COLUMNS,
    column_types=COLUMN_TYPES,
    column_renames=COLUMN_RENAMES,
    nk_coalesce_cols=("numero_registro_cge",),
    csv_delimiter=";",
    csv_quotechar='"',
    derived_columns={},
    watermark_col="DATA_CELEBRACAO_CONTRATO",
    watermark_type="string",
    encoding="latin-1",
    encoding_fallback="utf-8-sig",
    decimal_format="point",
    date_format="iso",
    refetch_recent_buckets=1,
    file_pattern=_file_pattern,
    bucket_from_filename=_bucket_from_filename,
    url_for_bucket=_url_for_bucket,
    enumerate_buckets=_enumerate_buckets,
)
