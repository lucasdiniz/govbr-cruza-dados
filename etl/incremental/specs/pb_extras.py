"""Specs para Dados-PB tabelas secundárias (13 tabelas).

- saude (mensal)
- pagamento_anulacao (mensal)
- liquidacaodespesa (mensal — schema NU_/CD_)
- liquidacaodespesadescontos (mensal — schema mixed case)
- empenho_anulacao (mensal — empenho-like 37 cols)
- empenho_suplementacao (mensal — empenho-like 37 cols)
- diarias (mensal — empenho-like 37 cols)
- dotacao (mensal — lowercase cols)
- liquidacao_cge (mensal)
- aditivos_contrato (mensal)
- aditivos_convenio (mensal)
- convenios (anual)
- unidade_gestora (anual)
"""
from __future__ import annotations

from ._pb_helpers import make_month_window_spec, make_year_window_spec


# ─── pb_saude ───────────────────────────────────────────────────────
SAUDE = make_month_window_spec(
    table="pb_saude",
    api_name="pagamentos_gestao_pactuada_saude",
    file_prefix="saude",
    columns=[
        "CODIGO_ENVIO", "COMPETENCIA",
        "CODIGO_ORGANIZACAO_SOCIAL", "NOME_ORGANIZACAO_SOCIAL",
        "CODIGO_LANCAMENTO", "DATA_LANCAMENTO",
        "NUMERO_DOCUMENTO", "TIPO_DOCUMENTO", "NUMERO_PROCESSO",
        "CODIGO_CATEGORIA_DESPESA", "NOME_CATEGORIA_DESPESA",
        "CPFCNPJ_CREDOR", "NOME_CREDOR",
        "VALOR_LANCAMENTO", "OBSERVACAO_LANCAMENTO",
    ],
    natural_key=["CODIGO_ENVIO", "CODIGO_LANCAMENTO"],
    nk_coalesce_cols=("codigo_envio", "codigo_lancamento"),
    column_types_override={"VALOR_LANCAMENTO": "NUMERIC", "DATA_LANCAMENTO": "DATE"},
    watermark_col_csv="DATA_LANCAMENTO",
)


# ─── pb_pagamento_anulacao ──────────────────────────────────────────
PAGAMENTO_ANULACAO = make_month_window_spec(
    table="pb_pagamento_anulacao",
    api_name="pagamento_anulacao",
    file_prefix="pagamento_anulacao",
    columns=[
        "EXERCICIO", "CODIGO_UNIDADE_GESTORA",
        "NUMERO_EMPENHO", "NUMERO_GUIA_DEVOLUCAO",
        "NUMERO_AUTORIZACAO_PAGAMENTO",
        "DATA_DOCUMENTO", "VALOR_DOCUMENTO",
        "CODIGO_TIPO_DOCUMENTO", "DESCRICAO_TIPO_DOCUMENTO",
    ],
    natural_key=[
        "EXERCICIO", "CODIGO_UNIDADE_GESTORA",
        "NUMERO_EMPENHO", "NUMERO_GUIA_DEVOLUCAO",
        "NUMERO_AUTORIZACAO_PAGAMENTO",
    ],
    nk_coalesce_cols=("codigo_unidade_gestora", "numero_empenho", "numero_guia_devolucao", "numero_autorizacao_pagamento"),
    column_types_override={
        "EXERCICIO": "SMALLINT", "VALOR_DOCUMENTO": "NUMERIC",
        "DATA_DOCUMENTO": "DATE",
    },
    watermark_col_csv="DATA_DOCUMENTO",
)


# ─── pb_liquidacao_despesa (schema NU_EXERCICIO/CD_ORGAO) ───────────
LIQUIDACAODESPESA = make_month_window_spec(
    table="pb_liquidacao_despesa",
    api_name="liquidacaodespesa",
    file_prefix="liquidacaodespesa",
    columns=[
        "NU_EXERCICIO", "DATA_MOV", "CD_ORGAO", "NU_EMPENHO",
        "DOCUMENTO", "DOCUMENTO_ORIGEM", "ANO_DOC_ORIGEM_LD",
        "TIPO_LIQUIDACAO", "CD_CREDOR", "CPF_CNPJ",
        "TIPO_DOC_FISCAL", "NUM_NOTAFISCAL", "DATA_NF",
        "CD_INSC_RP", "ANO_INSC_RP", "CD_ORGAO_EXTINTO", "VALOR",
    ],
    natural_key=["NU_EXERCICIO", "CD_ORGAO", "NU_EMPENHO", "DOCUMENTO", "DATA_MOV"],
    nk_coalesce_cols=("codigo_orgao", "numero_empenho", "documento"),
    column_renames_override={
        "NU_EXERCICIO": "exercicio",
        "DATA_MOV": "data_movimentacao",
        "CD_ORGAO": "codigo_orgao",
        "NU_EMPENHO": "numero_empenho",
        "DOCUMENTO": "documento",
        "DOCUMENTO_ORIGEM": "documento_origem",
        "ANO_DOC_ORIGEM_LD": "ano_documento_origem",
        "TIPO_LIQUIDACAO": "tipo_liquidacao",
        "CD_CREDOR": "codigo_credor",
        "CPF_CNPJ": "cpfcnpj_credor",
        "TIPO_DOC_FISCAL": "tipo_documento_fiscal",
        "NUM_NOTAFISCAL": "numero_nota_fiscal",
        "DATA_NF": "data_nota_fiscal",
        "CD_INSC_RP": "codigo_inscricao_rp",
        "ANO_INSC_RP": "ano_inscricao_rp",
        "CD_ORGAO_EXTINTO": "codigo_orgao_extinto",
        "VALOR": "valor_liquidacao",
    },
    column_types_override={
        "NU_EXERCICIO": "SMALLINT",
        "DATA_MOV": "DATE", "DATA_NF": "DATE",
        "VALOR": "NUMERIC",
        "ANO_DOC_ORIGEM_LD": "SMALLINT",
        "ANO_INSC_RP": "SMALLINT",
    },
    watermark_col_csv="DATA_MOV",
)


# ─── pb_liquidacao_desconto (schema mixed case) ─────────────────────
# USES SYNTHETIC NK (md5) - has 2.1M legacy duplicates after dedupe
LIQUIDACAODESPESADESCONTOS = make_month_window_spec(
    table="pb_liquidacao_desconto",
    api_name="liquidacaodespesadescontos",
    file_prefix="liquidacaodespesadescontos",
    columns=[
        "Exercicio", "CD_Orgao", "Num_Empenho", "Num_Doc",
        "DAT_PAGAMENTO", "TP_PG", "Cod_Desconto", "Desconto",
        "COD_ORGAO_PGT", "VL_Desconto",
    ],
    natural_key=["Exercicio", "CD_Orgao", "Num_Empenho", "Num_Doc", "Cod_Desconto"],
    column_renames_override={
        "Exercicio": "exercicio",
        "CD_Orgao": "codigo_orgao",
        "Num_Empenho": "numero_empenho",
        "Num_Doc": "numero_documento",
        "DAT_PAGAMENTO": "data_pagamento",
        "TP_PG": "tipo_pagamento",
        "Cod_Desconto": "codigo_desconto",
        "Desconto": "descricao_desconto",
        "COD_ORGAO_PGT": "codigo_orgao_pagamento",
        "VL_Desconto": "valor_desconto",
    },
    column_types_override={
        "Exercicio": "SMALLINT",
        "DAT_PAGAMENTO": "DATE", "VL_Desconto": "NUMERIC",
    },
    watermark_col_csv="DAT_PAGAMENTO",
)
# Force synthetic NK
import dataclasses as _dc
LIQUIDACAODESPESADESCONTOS = _dc.replace(LIQUIDACAODESPESADESCONTOS, nk_synthetic_md5=True)


# ─── pb_empenho_anulacao / suplementacao / diarias (37 cols, mesmo schema empenho) ──
_EMPENHO_VAR_COLS = [
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
]
# diarias tem 37 cols, mas empenho_anulacao/suplementacao têm 37 também.
# Rename lowercase
_EMPENHO_VAR_RENAMES = {c: c.lower() for c in _EMPENHO_VAR_COLS}
_EMPENHO_VAR_TYPES = {
    "EXERCICIO": "SMALLINT",
    "VALOR_EMPENHO": "NUMERIC",
    "DATA_EMPENHO": "DATE",
    "DATA_SAIDA_DIARIAS": "DATE",
    "DATA_CHEGADA_DIARIAS": "DATE",
}

EMPENHO_ANULACAO = make_month_window_spec(
    table="pb_empenho_anulacao",
    api_name="empenho_anulacao",
    file_prefix="empenho_anulacao",
    columns=_EMPENHO_VAR_COLS,
    natural_key=["EXERCICIO", "CODIGO_UNIDADE_GESTORA", "NUMERO_EMPENHO"],
    column_renames_override=_EMPENHO_VAR_RENAMES,
    column_types_override=_EMPENHO_VAR_TYPES,
    watermark_col_csv="DATA_EMPENHO",
)
EMPENHO_ANULACAO = _dc.replace(EMPENHO_ANULACAO, nk_synthetic_md5=True)

EMPENHO_SUPLEMENTACAO = make_month_window_spec(
    table="pb_empenho_suplementacao",
    api_name="empenho_suplementacao",
    file_prefix="empenho_suplementacao",
    columns=_EMPENHO_VAR_COLS,
    natural_key=["EXERCICIO", "CODIGO_UNIDADE_GESTORA", "NUMERO_EMPENHO"],
    column_renames_override=_EMPENHO_VAR_RENAMES,
    column_types_override=_EMPENHO_VAR_TYPES,
    watermark_col_csv="DATA_EMPENHO",
)
EMPENHO_SUPLEMENTACAO = _dc.replace(EMPENHO_SUPLEMENTACAO, nk_synthetic_md5=True)

DIARIAS = make_month_window_spec(
    table="pb_diaria",
    api_name="Diarias",  # case-sensitive: D maiúsculo per legacy
    file_prefix="diarias",
    columns=_EMPENHO_VAR_COLS,
    natural_key=["EXERCICIO", "CODIGO_UNIDADE_GESTORA", "NUMERO_EMPENHO"],
    column_renames_override=_EMPENHO_VAR_RENAMES,
    column_types_override=_EMPENHO_VAR_TYPES,
    watermark_col_csv="DATA_EMPENHO",
)
DIARIAS = _dc.replace(DIARIAS, nk_synthetic_md5=True)


# ─── pb_dotacao (lowercase cols) ────────────────────────────────────
# USES SYNTHETIC NK (md5)
DOTACAO = make_month_window_spec(
    table="pb_dotacao",
    api_name="dotacao",
    file_prefix="dotacao",
    columns=[
        "unidade_gestora", "exercicio", "unidade_orcamentaria", "funcao",
        "subfuncao", "programa", "acao", "meta", "localidade",
        "categoria", "grupo_despesa", "modalidade",
        "elemento_despesa", "fonte_recurso", "valor_orcado",
    ],
    natural_key=[
        "unidade_gestora", "exercicio", "unidade_orcamentaria", "funcao",
        "subfuncao", "programa", "acao", "elemento_despesa", "fonte_recurso",
    ],
    column_renames_override={
        "unidade_gestora": "codigo_unidade_gestora",
        "exercicio": "exercicio",
        "unidade_orcamentaria": "codigo_unidade_orcamentaria",
        "funcao": "codigo_funcao",
        "subfuncao": "codigo_subfuncao",
        "programa": "codigo_programa",
        "acao": "codigo_acao",
        "meta": "meta",
        "localidade": "localidade",
        "categoria": "categoria",
        "grupo_despesa": "grupo_despesa",
        "modalidade": "modalidade",
        "elemento_despesa": "elemento_despesa",
        "fonte_recurso": "fonte_recurso",
        "valor_orcado": "valor_orcado",
    },
    column_types_override={
        "exercicio": "SMALLINT", "valor_orcado": "NUMERIC",
    },
    watermark_col_csv="exercicio",
    watermark_type="integer",
)
DOTACAO = _dc.replace(DOTACAO, nk_synthetic_md5=True)


# ─── pb_liquidacao_cge (schema NU_/CD_) ─────────────────────────────
LIQUIDACAO_CGE = make_month_window_spec(
    table="pb_liquidacao_cge",
    api_name="liquidacao",
    file_prefix="liquidacao_cge",
    columns=[
        "NU_EXERCICIO", "CD_ORGAO", "NU_CLASSIFICACAO", "CD_UNIDADE",
        "CD_FUNCAO", "CD_SUBFUNCAO", "CD_PROGRAMA", "CD_PROJETO_ATIV",
        "META", "LOCALIDADE", "CD_NATUREZA", "CD_FONTE", "VALOR",
        "NU_EMPENHO", "DOCUMENTO", "TIPO_LIQUIDACAO",
        "TIPO_DOC_FISCAL", "NUM_NOTAFISCAL", "DATA_NF",
        "DATA_MOV", "DATA_PROC", "DATA_ATUALIZACAO", "USUARIO",
        "DOCUMENTO_ORIGEM", "CD_INSC_RP", "ANO_INSC_RP", "ANO_DOC_ORIGEM_LD",
    ],
    natural_key=["NU_EXERCICIO", "CD_ORGAO", "NU_EMPENHO", "DOCUMENTO", "DATA_MOV"],
    nk_coalesce_cols=("codigo_orgao", "numero_empenho", "documento"),
    column_renames_override={
        "NU_EXERCICIO": "exercicio",
        "CD_ORGAO": "codigo_orgao",
        "NU_CLASSIFICACAO": "numero_classificacao",
        "CD_UNIDADE": "codigo_unidade",
        "CD_FUNCAO": "codigo_funcao",
        "CD_SUBFUNCAO": "codigo_subfuncao",
        "CD_PROGRAMA": "codigo_programa",
        "CD_PROJETO_ATIV": "codigo_projeto_atividade",
        "META": "meta",
        "LOCALIDADE": "localidade",
        "CD_NATUREZA": "codigo_natureza",
        "CD_FONTE": "codigo_fonte",
        "VALOR": "valor",
        "NU_EMPENHO": "numero_empenho",
        "DOCUMENTO": "documento",
        "TIPO_LIQUIDACAO": "tipo_liquidacao",
        "TIPO_DOC_FISCAL": "tipo_documento_fiscal",
        "NUM_NOTAFISCAL": "numero_nota_fiscal",
        "DATA_NF": "data_nota_fiscal",
        "DATA_MOV": "data_movimentacao",
        "DATA_PROC": "data_processo",
        "DATA_ATUALIZACAO": "data_atualizacao",
        "USUARIO": "usuario_atualizacao",
        "DOCUMENTO_ORIGEM": "documento_origem",
        "CD_INSC_RP": "codigo_inscricao_rp",
        "ANO_INSC_RP": "ano_inscricao_rp",
        "ANO_DOC_ORIGEM_LD": "ano_documento_origem",
    },
    column_types_override={
        "NU_EXERCICIO": "SMALLINT",
        "VALOR": "NUMERIC",
        "DATA_MOV": "DATE", "DATA_NF": "DATE",
        "DATA_PROC": "DATE", "DATA_ATUALIZACAO": "DATE",
        "ANO_INSC_RP": "SMALLINT", "ANO_DOC_ORIGEM_LD": "SMALLINT",
    },
    watermark_col_csv="DATA_MOV",
)


# ─── pb_aditivo_contrato (mensal) ───────────────────────────────────
ADITIVO_CONTRATO = make_month_window_spec(
    table="pb_aditivo_contrato",
    api_name="aditivos_contrato",
    file_prefix="aditivos_contrato",
    columns=[
        "CODIGO_ADITIVO_CONTRATO", "CODIGO_CONTRATO",
        "MOTIVO_ADITIVACAO", "NUMERO_ADITIVO_CONTRATO",
        "DATA_INICIO_VIGENCIA", "DATA_TERMINO_VIGENCIA",
        "VALOR_ADITIVO", "OBJETO_ADITIVO",
        "DATA_CELEBRACAO_ADITIVO", "DATA_PUBLICACAO",
        "DATA_REPUBLICACAO", "URL_ADITIVO_CONTRATO",
    ],
    natural_key=["CODIGO_ADITIVO_CONTRATO"],
    column_types_override={
        "VALOR_ADITIVO": "NUMERIC",
        "DATA_INICIO_VIGENCIA": "DATE", "DATA_TERMINO_VIGENCIA": "DATE",
        "DATA_CELEBRACAO_ADITIVO": "DATE", "DATA_PUBLICACAO": "DATE",
        "DATA_REPUBLICACAO": "DATE",
    },
    watermark_col_csv="DATA_CELEBRACAO_ADITIVO",
)
ADITIVO_CONTRATO = _dc.replace(ADITIVO_CONTRATO, nk_synthetic_md5=True)


# ─── pb_aditivo_convenio (mensal) ───────────────────────────────────
ADITIVO_CONVENIO = make_month_window_spec(
    table="pb_aditivo_convenio",
    api_name="aditivos_convenio",
    file_prefix="aditivos_convenio",
    columns=[
        "CODIGO_ADITIVO_CONVENIO", "CODIGO_CONVENIO",
        "MOTIVO_ADITIVACAO", "NUMERO_ADITIVO_CONVENIO",
        "DATA_INICIO_VIGENCIA", "DATA_TERMINO_VIGENCIA",
        "VALOR_CONCEDENTE", "VALOR_CONVENENTE",
        "OBJETO_ADITIVO", "DATA_CELEBRACAO_ADITIVO",
        "DATA_PUBLICACAO", "DATA_REPUBLICACAO", "URL_ADITIVO_CONVENIO",
    ],
    natural_key=["CODIGO_ADITIVO_CONVENIO"],
    column_types_override={
        "VALOR_CONCEDENTE": "NUMERIC", "VALOR_CONVENENTE": "NUMERIC",
        "DATA_INICIO_VIGENCIA": "DATE", "DATA_TERMINO_VIGENCIA": "DATE",
        "DATA_CELEBRACAO_ADITIVO": "DATE", "DATA_PUBLICACAO": "DATE",
        "DATA_REPUBLICACAO": "DATE",
    },
    watermark_col_csv="DATA_CELEBRACAO_ADITIVO",
)
ADITIVO_CONVENIO = _dc.replace(ADITIVO_CONVENIO, nk_synthetic_md5=True)


# ─── pb_convenio (anual) ────────────────────────────────────────────
CONVENIO = make_year_window_spec(
    table="pb_convenio",
    api_name="convenios",
    file_prefix="convenios",
    columns=[
        "CODIGO_CONVENIO", "NUMERO_REGISTRO_CGE", "NUMERO_CONVENIO",
        "NOME_CONCEDENTE", "NOME_CONVENENTE", "CNPJ_CONVENENTE",
        "NOME_MUNICIPIO", "OBJETIVO_CONVENIO", "COMPLEMENTO_OBJETO_CONVENIO",
        "DATA_CELEBRACAO_CONVENIO", "DATA_PUBLICACAO",
        "VALOR_CONCEDENTE", "VALOR_CONTRAPARTIDA",
        "DATA_INICIO_VIGENCIA", "DATA_TERMINO_VIGENCIA", "URL_CONVENIO",
    ],
    natural_key=["CODIGO_CONVENIO", "NUMERO_REGISTRO_CGE"],
    nk_coalesce_cols=("codigo_convenio", "numero_registro_cge"),
    column_types_override={
        "VALOR_CONCEDENTE": "NUMERIC", "VALOR_CONTRAPARTIDA": "NUMERIC",
        "DATA_CELEBRACAO_CONVENIO": "DATE", "DATA_PUBLICACAO": "DATE",
        "DATA_INICIO_VIGENCIA": "DATE", "DATA_TERMINO_VIGENCIA": "DATE",
    },
    watermark_col_csv="DATA_CELEBRACAO_CONVENIO",
)


# ─── pb_unidade_gestora (anual) ─────────────────────────────────────
UNIDADE_GESTORA = make_year_window_spec(
    table="pb_unidade_gestora",
    api_name="unidades_gestoras",
    file_prefix="unidade_gestora",
    columns=[
        "EXERCICIO", "CODIGO_UNIDADE_GESTORA",
        "SIGLA_UNIDADE_GESTORA", "NOME_UNIDADE_GESTORA",
        "TIPO_ADMINISTRACAO_UNIDADE_GESTORA",
    ],
    natural_key=["EXERCICIO", "CODIGO_UNIDADE_GESTORA"],
    nk_coalesce_cols=("codigo_unidade_gestora",),
    column_renames_override={
        "EXERCICIO": "exercicio",
        "CODIGO_UNIDADE_GESTORA": "codigo_unidade_gestora",
        "SIGLA_UNIDADE_GESTORA": "sigla_unidade_gestora",
        "NOME_UNIDADE_GESTORA": "nome_unidade_gestora",
        "TIPO_ADMINISTRACAO_UNIDADE_GESTORA": "tipo_administracao",
    },
    column_types_override={"EXERCICIO": "SMALLINT"},
    watermark_col_csv="EXERCICIO",
    watermark_type="integer",
)


ALL_SPECS = {
    "pb_saude": SAUDE,
    "pb_pagamento_anulacao": PAGAMENTO_ANULACAO,
    "pb_liquidacao_despesa": LIQUIDACAODESPESA,
    "pb_liquidacao_desconto": LIQUIDACAODESPESADESCONTOS,
    "pb_empenho_anulacao": EMPENHO_ANULACAO,
    "pb_empenho_suplementacao": EMPENHO_SUPLEMENTACAO,
    "pb_diaria": DIARIAS,
    "pb_dotacao": DOTACAO,
    "pb_liquidacao_cge": LIQUIDACAO_CGE,
    "pb_aditivo_contrato": ADITIVO_CONTRATO,
    "pb_aditivo_convenio": ADITIVO_CONVENIO,
    "pb_convenio": CONVENIO,
    "pb_unidade_gestora": UNIDADE_GESTORA,
}
