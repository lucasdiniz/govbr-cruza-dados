"""LoaderSpec para pb_empenho (Dados-PB).

Filename: empenho_YYYY_MM.csv. Cursor: MONTH_WINDOW.
NK: (exercicio, codigo_unidade_gestora, numero_empenho)
"""
from __future__ import annotations
import re
from datetime import date
from ..spec import LoaderSpec, CursorStrategy, DedupeStrategy

_PB_BASE = "https://dados.pb.gov.br:443/getcsv"


def _bucket_from_filename(name: str) -> str | None:
    m = re.match(r"^empenho_(\d{4})_(\d{2})\.csv$", name, re.IGNORECASE)
    return f"{m.group(1)}-{m.group(2)}" if m else None


def _file_pattern(bucket_id: str) -> list[str]:
    year, month = bucket_id.split("-")
    return [f"empenho_{year}_{month}.csv"]


def _url_for_bucket(bucket_id: str) -> list[tuple[str, str]]:
    year, month = bucket_id.split("-")
    return [(f"{_PB_BASE}?nome=empenho_original&exercicio={year}&mes={int(month)}",
             f"empenho_{year}_{month}.csv")]


def _enumerate_buckets() -> list[str]:
    today = date.today()
    out = []
    for year in range(2018, today.year + 1):
        max_month = today.month if year == today.year else 12
        for month in range(1, max_month + 1):
            out.append(f"{year}-{month:02d}")
    return out


COLUMNS = [
    "EXERCICIO", "CODIGO_UNIDADE_GESTORA", "NUMERO_EMPENHO",
    "NUMERO_EMPENHO_ORIGEM", "DATA_EMPENHO", "HISTORICO_EMPENHO",
    "CODIGO_SITUACAO_EMPENHO", "CODIGO_TIPO_EMPENHO", "DESCRICAO_TIPO_EMPENHO",
    "NOME_SITUACAO_EMPENHO", "VALOR_EMPENHO",
    "CODIGO_MODALIDADE_LICITACAO", "CODIGO_MOTIVO_DISPENSA_LICITACAO",
    "CODIGO_TIPO_CREDITO", "NOME_TIPO_CREDITO",
    "DESTINO_DIARIAS", "DATA_SAIDA_DIARIAS", "DATA_CHEGADA_DIARIAS",
    "NOME_CREDOR", "CPFCNPJ_CREDOR", "TIPO_CREDOR",
    "CODIGO_MUNICIPIO", "NOME_MUNICIPIO",
    "NUMERO_PROCESSO_PAGAMENTO", "NUMERO_CONTRATO",
    "CODIGO_UNIDADE_ORCAMENTARIA",
    "CODIGO_FUNCAO", "CODIGO_SUBFUNCAO", "CODIGO_PROGRAMA", "CODIGO_ACAO",
    "CODIGO_FONTE_RECURSO", "CODIGO_NATUREZA_DESPESA",
    "CODIGO_CATEGORIA_ECONOMICA_DESPESA",
    "CODIGO_GRUPO_NATUREZA_DESPESA", "CODIGO_MODALIDADE_APLICACAO_DESPESA",
    "CODIGO_ELEMENTO_DESPESA", "CODIGO_ITEM_DESPESA",
    "CODIGO_FINALIDADE_FIXACAO", "NOME__FINALIDADE_FIXACAO",
    "CODIGO_LICITACAO", "ORCAMENTO_DEMOCRATICO",
]

# CSV uses double-underscore typo; target uses single
COLUMN_RENAMES = {c: c.lower() for c in COLUMNS}
COLUMN_RENAMES["NOME__FINALIDADE_FIXACAO"] = "nome_finalidade_fixacao"

COLUMN_TYPES = {c: "TEXT" for c in COLUMNS}
COLUMN_TYPES["EXERCICIO"] = "SMALLINT"
COLUMN_TYPES["VALOR_EMPENHO"] = "NUMERIC"
COLUMN_TYPES["DATA_EMPENHO"] = "DATE"
COLUMN_TYPES["DATA_SAIDA_DIARIAS"] = "DATE"
COLUMN_TYPES["DATA_CHEGADA_DIARIAS"] = "DATE"


SPEC = LoaderSpec(
    source="dados_pb",
    table="pb_empenho",
    natural_key=[
        "EXERCICIO", "CODIGO_UNIDADE_GESTORA", "NUMERO_EMPENHO",
    ],
    cursor_strategy=CursorStrategy.MONTH_WINDOW,
    dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
    columns=COLUMNS,
    column_types=COLUMN_TYPES,
    column_renames=COLUMN_RENAMES,
    nk_coalesce_cols=("codigo_unidade_gestora", "numero_empenho"),
    csv_delimiter=";",
    csv_quotechar='"',
    derived_columns={},
    watermark_col="DATA_EMPENHO",
    watermark_type="string",
    encoding="latin-1",
    encoding_fallback="utf-8-sig",
    decimal_format="point",
    date_format="iso",
    refetch_recent_buckets=2,
    file_pattern=_file_pattern,
    bucket_from_filename=_bucket_from_filename,
    url_for_bucket=_url_for_bucket,
    enumerate_buckets=_enumerate_buckets,
)
