"""LoaderSpec para Bolsa Familia (Portal da Transparencia).

Source: portaldatransparencia.gov.br/download-de-dados/novo-bolsa-familia/{YYYYMM}
Formato: ZIP contendo CSV {YYYYMM}_NovoBolsaFamilia.csv
         (delimiter ';', quotechar '"', encoding latin-1, decimal BR virgula).

Filename ZIP: novo_bf_{YYYYMM}.zip (consistente com etl/00_download.py).
Filename CSV (apos extracao automatica pelo framework): {YYYYMM}_NovoBolsaFamilia.csv.

Cursor: MONTH_WINDOW (bucket_id = "YYYY-MM").
Watermark: MES_COMPETENCIA (string YYYYMM).
Dedupe: UPSERT_DO_NOTHING. Intencao do incremental e ACUMULAR snapshots
        mensais novos, NAO corrigir dados existentes — escolhi DO_NOTHING
        em vez de DO_UPDATE para que reruns nunca alterem rows existentes
        (mais conservador). refetch_recent_buckets=1 cobre republish do
        mes corrente.

NK: synthetic md5 (nk_synthetic_md5=True), pattern dos 7 pb_extras tables.
   Por que nao NK natural: empirical analysis (2026-05) na base local + VM:
   * 21% rows tem cpf_favorecido='' (CADUNICO com CPF nao-vinculado).
   * Portal publica parcelas RETROATIVAS no mesmo mes_competencia com
     mes_referencia diferentes (legitimo — recebimentos atrasados).
   * Nenhuma combinacao razoavel de cols cobre 100% sem perda de dado.
   * 22 rows EXATAMENTE iguais (todas 9 cols) sao true legacy duplicates.
   Synthetic md5 das 9 cols cobre 100% via trigger BEFORE INSERT
   (ver sql/41_bolsa_familia_incremental.sql).
   natural_key abaixo e DECLARATIVO (semantico) — quando nk_synthetic_md5
   esta True, build_upsert_sql usa ON CONFLICT (_nk_md5).

Header rewrite: o CSV do Portal Transparencia publica headers com acentos e
espacos (e.g. "MES COMPETENCIA"). spec.csv_header_rewrites mapeia esses
nomes raw para os SQL-safe que aparecem em spec.columns (e.g.
"MES_COMPETENCIA"). Encoding latin-1 garante leitura correta dos acentos
antes do rewrite.

Ver ADR-0010 e docs/etl-incremental-guide.md.
"""
from __future__ import annotations

import re
from datetime import date

from ..spec import CursorStrategy, DedupeStrategy, LoaderSpec

_PORTAL_BASE = "https://portaldatransparencia.gov.br/download-de-dados/novo-bolsa-familia"


def _bucket_from_filename(name: str) -> str | None:
    """Aceita tanto o ZIP baixado (novo_bf_YYYYMM.zip) quanto o CSV interno
    (YYYYMM_NovoBolsaFamilia.csv). framework chama com o CSV apos extracao."""
    m = re.match(r"^(\d{6})_NovoBolsaFamilia\.csv$", name, re.IGNORECASE)
    if m:
        ym = m.group(1)
        return f"{ym[:4]}-{ym[4:]}"
    m = re.match(r"^novo_bf_(\d{6})\.zip$", name, re.IGNORECASE)
    if m:
        ym = m.group(1)
        return f"{ym[:4]}-{ym[4:]}"
    return None


def _file_pattern(bucket_id: str) -> list[str]:
    """CSV interno do ZIP extraido. framework usa esse nome para localizar
    o arquivo apos extracao automatica (ver etl/incremental/download.py:207+)."""
    year, month = bucket_id.split("-")
    return [f"{year}{month}_NovoBolsaFamilia.csv"]


def _url_for_bucket(bucket_id: str) -> list[tuple[str, str]]:
    """Portal Transparencia: 1 ZIP por (year, month). Nome do destino segue
    o padrao usado em etl/00_download.py:1265 (novo_bf_{YYYYMM}.zip)."""
    year, month = bucket_id.split("-")
    ym = f"{year}{month}"
    return [(f"{_PORTAL_BASE}/{ym}", f"novo_bf_{ym}.zip")]


def _enumerate_buckets() -> list[str]:
    """Novo Bolsa Familia substituiu Auxilio Brasil em marco/2023.
    Listamos do primeiro mes disponivel ate o mes atual.
    """
    today = date.today()
    out = []
    start_year, start_month = 2023, 3  # Marco/2023 = primeiro mes do Novo BF
    year, month = start_year, start_month
    while (year, month) <= (today.year, today.month):
        out.append(f"{year}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    return out


# Headers SQL-safe declarados em spec.columns. O CSV raw publica nomes com
# acentos e espacos; csv_header_rewrites faz o mapeamento.
COLUMNS = [
    "MES_COMPETENCIA",
    "MES_REFERENCIA",
    "UF",
    "CODIGO_MUNICIPIO_SIAFI",
    "NOME_MUNICIPIO",
    "CPF_FAVORECIDO",
    "NIS_FAVORECIDO",
    "NOME_FAVORECIDO",
    "VALOR_PARCELA",
]

# Header raw do CSV publicado pelo Portal da Transparencia. Encoding latin-1
# preserva os acentos. Validado em 2026-05 com 202510, 202512 e 202602.
CSV_HEADER_REWRITES = {
    "MÊS COMPETÊNCIA": "MES_COMPETENCIA",
    "MÊS REFERÊNCIA": "MES_REFERENCIA",
    "UF": "UF",
    "CÓDIGO MUNICÍPIO SIAFI": "CODIGO_MUNICIPIO_SIAFI",
    "NOME MUNICÍPIO": "NOME_MUNICIPIO",
    "CPF FAVORECIDO": "CPF_FAVORECIDO",
    "NIS FAVORECIDO": "NIS_FAVORECIDO",
    "NOME FAVORECIDO": "NOME_FAVORECIDO",
    "VALOR PARCELA": "VALOR_PARCELA",
}

# Column renames: CSV col raw (UPPERCASE) -> target col (lowercase).
# CRITICO: a tabela bolsa_familia usa nomes LEGADOS estilo SIAFI antigo
# (cd_municipio_siafi, nm_municipio, nm_favorecido), NAO o padrao Portal
# (codigo_municipio_siafi, nome_municipio, nome_favorecido). Mapping
# explicito abaixo evita o bug que blanket lowercase causaria (INSERT em
# coluna inexistente). Validado contra sql/17_schema_bolsa_familia.sql
# (schema canonico) e information_schema.columns em prod 2026-05.
COLUMN_RENAMES = {
    "MES_COMPETENCIA": "mes_competencia",
    "MES_REFERENCIA": "mes_referencia",
    "UF": "uf",
    "CODIGO_MUNICIPIO_SIAFI": "cd_municipio_siafi",
    "NOME_MUNICIPIO": "nm_municipio",
    "CPF_FAVORECIDO": "cpf_favorecido",
    "NIS_FAVORECIDO": "nis_favorecido",
    "NOME_FAVORECIDO": "nm_favorecido",
    "VALOR_PARCELA": "valor_parcela",
}

COLUMN_TYPES = {c: "TEXT" for c in COLUMNS}
COLUMN_TYPES["VALOR_PARCELA"] = "NUMERIC"


SPEC = LoaderSpec(
    source="bolsa_familia",
    table="bolsa_familia",
    # natural_key abaixo e DECLARATIVO (semantico): identifica a parcela
    # individual. Quando nk_synthetic_md5=True (abaixo), o framework usa
    # ON CONFLICT (_nk_md5) em vez desses cols. Mantemos a lista coerente
    # com o significado de "uma parcela" para que reviewers entendam a
    # intencao mesmo sem ler o sql/41.
    natural_key=[
        "MES_COMPETENCIA",
        "MES_REFERENCIA",
        "CPF_FAVORECIDO",
        "NIS_FAVORECIDO",
    ],
    cursor_strategy=CursorStrategy.MONTH_WINDOW,
    dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
    # CRITICO: synthetic md5 NK. Cobre cenarios onde nem trio (cpf vazio)
    # nem 4-uplo (parcelas retroativas) sao 100%-unicos. Padrao pb_extras.
    # Requer:
    #   * coluna _nk_md5 (criada em sql/41 step 1)
    #   * trigger BEFORE INSERT compute_nk_md5_bolsa_familia (sql/41 step 2)
    #   * UNIQUE INDEX ix_bolsa_familia_nk_md5 (sql/41 step 5)
    nk_synthetic_md5=True,
    columns=COLUMNS,
    column_types=COLUMN_TYPES,
    column_renames=COLUMN_RENAMES,
    csv_delimiter=";",
    csv_quotechar='"',
    # cpf_digitos populado pelo framework via REGEXP_REPLACE. Use UPPERCASE
    # exato do nome em spec.columns (ver staging.py linhas 183-185 — derived
    # SELECT usa raw staging col names, antes do column_renames).
    derived_columns={
        "cpf_digitos": "REGEXP_REPLACE(CPF_FAVORECIDO, '[^0-9]', '', 'g')",
    },
    watermark_col="MES_COMPETENCIA",
    watermark_type="string",
    encoding="latin-1",
    decimal_format="br",   # CSV usa virgula como decimal (1886,00)
    date_format="iso",
    is_zip_source=True,
    refetch_recent_buckets=1,
    file_pattern=_file_pattern,
    bucket_from_filename=_bucket_from_filename,
    url_for_bucket=_url_for_bucket,
    enumerate_buckets=_enumerate_buckets,
    csv_header_rewrites=CSV_HEADER_REWRITES,
)
