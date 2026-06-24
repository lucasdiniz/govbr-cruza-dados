"""LoaderSpec para tce_pb_despesa.

Schema versioning (cutoff em 2020):
- 2018-2019: COLUMNS_OLD com 'descricao_funcao', 'codigo_natureza_despesa', etc
- 2020+:     COLUMNS_NEW com 'funcao', 'codigo_natureza', etc
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from ..spec import LoaderSpec, CursorStrategy, DedupeStrategy


_TCE_BASE = "https://download.tce.pb.gov.br/dados-abertos/dados-consolidados"


def _bucket_from_filename(name: str) -> str | None:
    m = re.match(r"^despesas-(\d{4})\.csv$", name, re.IGNORECASE)
    return m.group(1) if m else None


def _file_pattern(bucket_id: str) -> list[str]:
    return [f"despesas-{bucket_id}.csv"]


def _url_for_bucket(bucket_id: str) -> list[tuple[str, str]]:
    return [(f"{_TCE_BASE}/despesas/despesas-{bucket_id}.zip",
             f"despesas-{bucket_id}.zip")]


def _enumerate_buckets() -> list[str]:
    return [str(y) for y in range(2018, date.today().year + 1)]


COLUMNS_NEW = [
    "municipio", "codigo_unidade_gestora", "descricao_unidade_gestora",
    "numero_empenho", "data_empenho", "mes", "cpf_cnpj", "nome_credor",
    "valor_empenhado", "valor_liquidado", "valor_pago",
    "codigo_unidade_orcamentaria", "descricao_unidade_orcamentaria",
    "codigo_funcao", "funcao", "codigo_subfuncao", "subfuncao",
    "codigo_programa", "programa", "codigo_acao", "acao",
    "codigo_categoria_economica", "categoria_economica",
    "codigo_natureza", "grupo_natureza_despesa",
    "codigo_modalidade_aplicacao", "modalidade_aplicacao",
    "codigo_elemento_despesa", "elemento_despesa",
    "codigo_subelemento", "codigo_subelemento_exibicao",
    "numero_licitacao", "modalidade_licitacao",
    "numero_obra", "historico",
    "codigo_fonte_recurso", "descricao_fonte_recurso",
    "ano_fonte", "co", "descricao_co",
]

COLUMN_RENAMES_NEW = {
    "codigo_unidade_gestora": "codigo_ug",
    "descricao_unidade_gestora": "descricao_ug",
}

COLUMNS_OLD = [
    "municipio", "codigo_unidade_gestora", "descricao_unidade_gestora",
    "numero_empenho", "data_empenho", "mes", "cpf_cnpj", "nome_credor",
    "valor_empenhado", "valor_liquidado", "valor_pago",
    "codigo_unidade_orcamentaria", "descricao_unidade_orcamentaria",
    "codigo_funcao", "descricao_funcao",
    "codigo_subfuncao", "descricao_subfuncao",
    "codigo_programa", "descricao_programa",
    "codigo_acao", "descricao_acao",
    "codigo_categoria_economica", "descricao_categoria_economica",
    "codigo_natureza_despesa", "descricao_natureza_despesa",
    "codigo_modalidade", "descricao_modalidade",
    "codigo_elemento_despesa", "descricao_elemento_despesa",
    "codigo_subelemento", "descricao_subelemento",
    "numero_licitacao", "modalidade_licitacao",
    "numero_obra", "historico",
    "codigo_fonte_recurso", "descricao_fonte_recurso",
    "ano_fonte", "co", "descricao_co",
]

COLUMN_RENAMES_OLD = {
    "codigo_unidade_gestora": "codigo_ug",
    "descricao_unidade_gestora": "descricao_ug",
    "descricao_funcao": "funcao",
    "descricao_subfuncao": "subfuncao",
    "descricao_programa": "programa",
    "descricao_acao": "acao",
    "descricao_categoria_economica": "categoria_economica",
    "codigo_natureza_despesa": "codigo_natureza",
    "descricao_natureza_despesa": "grupo_natureza_despesa",
    "codigo_modalidade": "codigo_modalidade_aplicacao",
    "descricao_modalidade": "modalidade_aplicacao",
    "descricao_elemento_despesa": "elemento_despesa",
    "descricao_subelemento": "codigo_subelemento_exibicao",
}


def _columns_per_bucket(bucket_id: str) -> Optional[tuple[list[str], dict[str, str]]]:
    """TCE-PB schema cutoff: 2018-2019 -> schema antigo, 2020+ -> novo."""
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
COLUMN_TYPES.update({
    "valor_empenhado": "NUMERIC",
    "valor_liquidado": "NUMERIC",
    "valor_pago": "NUMERIC",
    "data_empenho": "DATE",
})
for c in COLUMNS_OLD:
    if c not in COLUMN_TYPES:
        COLUMN_TYPES[c] = "TEXT"


SPEC = LoaderSpec(
    source="tce_pb",
    table="tce_pb_despesa",
    # natural_key abaixo e DECLARATIVO (semantico). Quando nk_synthetic_md5=True
    # (abaixo), build_upsert_sql usa ON CONFLICT (_nk_md5) — NAO estas colunas.
    #
    # Por que synthetic md5 e nao NK natural (ADR-0014):
    #   Analise empirica em prod (2026-06) revelou que esta combinacao de
    #   colunas NAO e unica: 1037 grupos (2530 rows, 2019-2026) compartilham
    #   a NK mas tem valor_empenhado/valor_liquidado/valor_pago/cpf_cnpj/
    #   nome_credor/historico DISTINTOS — sao empenhos/parcelas legitimamente
    #   diferentes, nao duplicatas. Adicionar `mes` NAO resolve (0 grupos
    #   colapsam). Um UNIQUE INDEX nesta NK seria semanticamente errado e
    #   UPSERT_DO_NOTHING PULARIA silenciosamente novos registros distintos
    #   que colidem na NK -> perda continua de dados a cada incremental.
    #
    #   Synthetic md5 (hash de TODAS as 41 cols de negocio) so colapsa rows
    #   byte-a-byte identicas (true duplicates do ETL classico legacy). Cobre
    #   100% sem perda. Padrao das 7 tabelas pb_extras (sql/35a-d) e de
    #   bolsa_familia (sql/41). Requer:
    #     * coluna _nk_md5 (sql/42 step 1)
    #     * trigger BEFORE INSERT compute_nk_md5_tce_pb_despesa (sql/42 step 2)
    #     * UNIQUE INDEX ix_tce_pb_despesa_nk_md5 (sql/42z)
    natural_key=[
        "municipio", "codigo_unidade_gestora", "numero_empenho", "data_empenho",
        "codigo_subelemento", "codigo_fonte_recurso",
        "numero_obra", "numero_licitacao", "codigo_natureza",
        "ano_arquivo",
    ],
    cursor_strategy=CursorStrategy.YEAR_WINDOW,
    dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
    nk_synthetic_md5=True,
    columns=COLUMNS,
    column_types=COLUMN_TYPES,
    column_renames=COLUMN_RENAMES,
    nk_coalesce_cols=(
        "codigo_subelemento", "codigo_fonte_recurso",
        "numero_obra", "numero_licitacao", "codigo_natureza",
    ),
    csv_delimiter=";",
    csv_quotechar='"',
    derived_columns={"ano_arquivo": "{bucket_id}"},
    watermark_col="ano_arquivo",
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
    columns_per_bucket=_columns_per_bucket,
)
