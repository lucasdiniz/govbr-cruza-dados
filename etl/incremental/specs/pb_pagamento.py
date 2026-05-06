"""LoaderSpec para pb_pagamento (Dados-PB Estaduais).

Source: https://dados.pb.gov.br:443/getcsv?nome=pagamento&exercicio=YYYY&mes=MM
Formato: CSV com ; quote ", encoding latin-1, decimal ponto, datas ISO.

Filename: pagamento_YYYY_MM.csv. Cursor: MONTH_WINDOW.
NK: (exercicio, codigo_unidade_gestora, numero_empenho, numero_autorizacao_pagamento, data_pagamento)
"""
from __future__ import annotations
import re
from datetime import date
from ..spec import LoaderSpec, CursorStrategy, DedupeStrategy

_PB_BASE = "https://dados.pb.gov.br:443/getcsv"


def _bucket_from_filename(name: str) -> str | None:
    m = re.match(r"^pagamento_(\d{4})_(\d{2})\.csv$", name, re.IGNORECASE)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _file_pattern(bucket_id: str) -> list[str]:
    year, month = bucket_id.split("-")
    return [f"pagamento_{year}_{month}.csv"]


def _url_for_bucket(bucket_id: str) -> list[tuple[str, str]]:
    year, month = bucket_id.split("-")
    return [(f"{_PB_BASE}?nome=pagamento&exercicio={year}&mes={int(month)}",
             f"pagamento_{year}_{month}.csv")]


def _enumerate_buckets() -> list[str]:
    today = date.today()
    out = []
    for year in range(2018, today.year + 1):
        max_month = today.month if year == today.year else 12
        for month in range(1, max_month + 1):
            out.append(f"{year}-{month:02d}")
    return out


# CSV cols UPPERCASE → target cols lowercase
COLUMNS = [
    "EXERCICIO", "CODIGO_UNIDADE_GESTORA", "NUMERO_EMPENHO",
    "NUMERO_AUTORIZACAO_PAGAMENTO", "TIPO_DESPESA", "DATA_PAGAMENTO",
    "VALOR_PAGAMENTO",
    "CODIGO_TIPO_DOCUMENTO", "DESCRICAO_TIPO_DOCUMENTO",
    "NOME_CREDOR", "CPFCNPJ_CREDOR", "TIPO_CREDOR",
]

COLUMN_RENAMES = {c: c.lower() for c in COLUMNS}

COLUMN_TYPES = {c: "TEXT" for c in COLUMNS}
COLUMN_TYPES["EXERCICIO"] = "SMALLINT"
COLUMN_TYPES["VALOR_PAGAMENTO"] = "NUMERIC"
COLUMN_TYPES["DATA_PAGAMENTO"] = "DATE"


SPEC = LoaderSpec(
    source="dados_pb",
    table="pb_pagamento",
    natural_key=[
        "EXERCICIO", "CODIGO_UNIDADE_GESTORA", "NUMERO_EMPENHO",
        "NUMERO_AUTORIZACAO_PAGAMENTO", "DATA_PAGAMENTO",
    ],
    cursor_strategy=CursorStrategy.MONTH_WINDOW,
    dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
    columns=COLUMNS,
    column_types=COLUMN_TYPES,
    column_renames=COLUMN_RENAMES,
    nk_coalesce_cols=("numero_autorizacao_pagamento",),
    csv_delimiter=";",
    csv_quotechar='"',
    derived_columns={},
    watermark_col="DATA_PAGAMENTO",
    watermark_type="string",
    encoding="latin-1",
    encoding_fallback="utf-8-sig",
    decimal_format="point",
    date_format="iso",
    refetch_recent_buckets=2,  # ultimo + penultimo mes (dados publicados retroativamente)
    file_pattern=_file_pattern,
    bucket_from_filename=_bucket_from_filename,
    url_for_bucket=_url_for_bucket,
    enumerate_buckets=_enumerate_buckets,
)
