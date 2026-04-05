"""Carrega dados do portal dados.pb.gov.br (pagamento, empenho, contratos, saude, convenios).

Fonte: https://dados.pb.gov.br/app/
Download: etl/00_download.py (download_dados_pb)
Formato: CSV com ; separador, valores decimais com ponto, datas ISO (YYYY-MM-DD)
CPF formatado (000.123.456-78), CNPJ formatado (12.345.678/0001-90)

Uso:
  python -m etl.20_dados_pb                           # Carrega tudo
  python -m etl.20_dados_pb --only pagamento          # So pagamento
  python -m etl.20_dados_pb --anos 2024,2025          # So esses anos
  python -m etl.20_dados_pb --no-schema               # Pula DROP/CREATE
"""

import csv
import io
import sys
from pathlib import Path

from etl.config import DATA_DIR
from etl.db import get_conn, table_count


ANOS = range(2018, 2027)
MESES = range(1, 13)

PB_DIR = DATA_DIR / "dados_pb"


def _clean_cpfcnpj(val):
    """Remove formatacao de CPF/CNPJ: 000.123.456-78 -> 00012345678."""
    if not val or not val.strip():
        return None
    val = val.strip().strip('"')
    if not val:
        return None
    # Remove pontos, tracos, barras
    cleaned = val.replace(".", "").replace("-", "").replace("/", "").replace(" ", "")
    if not cleaned:
        return None
    return cleaned


def _clean_val(val):
    """Limpa campo texto para COPY."""
    if val == "" or val is None:
        return "\\N"
    val = val.strip().strip('"').strip()
    if val == "":
        return "\\N"
    val = val.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "")
    return val


def _sql_date(col):
    """Expressao SQL para datas ISO ou timestamps ISO."""
    return (
        f"CASE WHEN LEFT(TRIM({col}), 10) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' "
        f"THEN CAST(LEFT(TRIM({col}), 10) AS DATE) ELSE NULL END"
    )


def _sql_decimal(col):
    """Expressao SQL para decimais com ponto."""
    return f"CASE WHEN TRIM({col}) ~ '^-?[\\d.]+$' THEN CAST(TRIM({col}) AS DECIMAL(15,2)) ELSE NULL END"


def _sql_smallint(col):
    """Expressao SQL para SMALLINT."""
    return f"CASE WHEN TRIM({col}) ~ '^\\d{{1,4}}$' THEN CAST(TRIM({col}) AS SMALLINT) ELSE NULL END"


def _sql_digits(col):
    """Remove formatacao de CPF/CNPJ em SQL."""
    return f"REPLACE(REPLACE(REPLACE(REPLACE(TRIM({col}), '.', ''), '-', ''), '/', ''), ' ', '')"


def _load_csv(filepath):
    """Carrega CSV de disco. Download feito por etl/00_download.py."""
    if filepath.exists() and filepath.stat().st_size > 100:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    return None


def _staging_load_from_data(conn, staging, csv_data, n_cols, delimiter=";"):
    """Carrega CSV data em tabela staging via COPY."""
    col_defs = ", ".join(f"c{i} TEXT" for i in range(n_cols))
    cols = ", ".join(f"c{i}" for i in range(n_cols))

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"CREATE UNLOGGED TABLE {staging} ({col_defs})")
    conn.commit()

    copy_sql = f"""COPY {staging} ({cols}) FROM STDIN
        WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N')"""

    buf = io.BytesIO()
    count = 0

    reader = csv.reader(io.StringIO(csv_data), delimiter=delimiter, quotechar='"')
    next(reader, None)  # skip header

    for row in reader:
        if not row or all(not c.strip() for c in row):
            continue
        if len(row) > n_cols:
            row = row[:n_cols]
        elif len(row) < n_cols:
            row = row + [""] * (n_cols - len(row))

        escaped = [_clean_val(val) for val in row]
        buf.write(("\t".join(escaped) + "\n").encode("utf-8"))
        count += 1

        if count % 100000 == 0:
            buf.seek(0)
            with conn.cursor() as cur:
                cur.copy_expert(copy_sql, buf)
            conn.commit()
            buf = io.BytesIO()

    if buf.tell() > 0:
        buf.seek(0)
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, buf)
        conn.commit()

    return count


def load_pagamento(conn, anos):
    """Carrega pagamento (autorizacoes de pagamento estaduais) -> pb_pagamento."""
    total = 0
    for ano in anos:
        for mes in MESES:
            cache = PB_DIR / f"pagamento_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                continue

            staging = "_stg_pb_pagamento"
            n = _staging_load_from_data(conn, staging, data, 12)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            sql = """
                INSERT INTO pb_pagamento (
                    exercicio, codigo_unidade_gestora, numero_empenho,
                    numero_autorizacao_pagamento, tipo_despesa, data_pagamento,
                    valor_pagamento, codigo_tipo_documento, descricao_tipo_documento,
                    nome_credor, cpfcnpj_credor, tipo_credor
                )
                SELECT
                    CASE WHEN TRIM(c0) ~ '^\\d{{4}}$' THEN CAST(TRIM(c0) AS SMALLINT) ELSE NULL END,
                    TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4),
                    CASE WHEN TRIM(c5) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c5) AS DATE) ELSE NULL END,
                    CASE WHEN TRIM(c6) ~ '^-?[\\d.]+$' THEN CAST(TRIM(c6) AS DECIMAL(15,2)) ELSE NULL END,
                    TRIM(c7), TRIM(c8), TRIM(c9),
                    REPLACE(REPLACE(REPLACE(REPLACE(TRIM(c10), '.', ''), '-', ''), '/', ''), ' ', ''),
                    TRIM(c11)
                FROM {staging}
            """.format(staging=staging)
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            total += n

        print(f"    pagamento-{ano}: {total:,} linhas acumuladas", flush=True)
    return total


def load_empenho(conn, anos):
    """Carrega empenho_original -> pb_empenho."""
    total = 0
    for ano in anos:
        ano_count = 0
        for mes in MESES:
            cache = PB_DIR / f"empenho_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                continue

            staging = "_stg_pb_empenho"
            n = _staging_load_from_data(conn, staging, data, 41)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            # CPF/CNPJ cleanup inline — remove formatacao na coluna c19
            # Dates: c4 (empenho), c16 (saida diarias), c17 (chegada diarias)
            sql = """
                INSERT INTO pb_empenho (
                    exercicio, codigo_unidade_gestora, numero_empenho,
                    numero_empenho_origem, data_empenho, historico_empenho,
                    codigo_situacao_empenho, codigo_tipo_empenho, descricao_tipo_empenho,
                    nome_situacao_empenho, valor_empenho, codigo_modalidade_licitacao,
                    codigo_motivo_dispensa_licitacao, codigo_tipo_credito, nome_tipo_credito,
                    destino_diarias, data_saida_diarias, data_chegada_diarias,
                    nome_credor, cpfcnpj_credor, tipo_credor,
                    codigo_municipio, nome_municipio, numero_processo_pagamento,
                    numero_contrato, codigo_unidade_orcamentaria, codigo_funcao,
                    codigo_subfuncao, codigo_programa, codigo_acao,
                    codigo_fonte_recurso, codigo_natureza_despesa,
                    codigo_categoria_economica_despesa, codigo_grupo_natureza_despesa,
                    codigo_modalidade_aplicacao_despesa, codigo_elemento_despesa,
                    codigo_item_despesa, codigo_finalidade_fixacao, nome_finalidade_fixacao,
                    codigo_licitacao, orcamento_democratico
                )
                SELECT
                    CASE WHEN TRIM(c0) ~ '^\\d{{4}}$' THEN CAST(TRIM(c0) AS SMALLINT) ELSE NULL END,
                    TRIM(c1), TRIM(c2), TRIM(c3),
                    CASE WHEN TRIM(c4) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c4) AS DATE) ELSE NULL END,
                    TRIM(c5), TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9),
                    CASE WHEN TRIM(c10) ~ '^-?[\\d.]+$' THEN CAST(TRIM(c10) AS DECIMAL(15,2)) ELSE NULL END,
                    TRIM(c11), TRIM(c12), TRIM(c13), TRIM(c14),
                    TRIM(c15),
                    CASE WHEN TRIM(c16) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c16) AS DATE) ELSE NULL END,
                    CASE WHEN TRIM(c17) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c17) AS DATE) ELSE NULL END,
                    TRIM(c18),
                    REPLACE(REPLACE(REPLACE(REPLACE(TRIM(c19), '.', ''), '-', ''), '/', ''), ' ', ''),
                    TRIM(c20),
                    TRIM(c21), TRIM(c22), TRIM(c23),
                    TRIM(c24), TRIM(c25), TRIM(c26),
                    TRIM(c27), TRIM(c28), TRIM(c29),
                    TRIM(c30), TRIM(c31),
                    TRIM(c32), TRIM(c33),
                    TRIM(c34), TRIM(c35),
                    TRIM(c36), TRIM(c37), TRIM(c38),
                    TRIM(c39), TRIM(c40)
                FROM {staging}
            """.format(staging=staging)
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            ano_count += n

        total += ano_count
        print(f"    empenho-{ano}: {ano_count:,} linhas", flush=True)
    return total


def load_contratos(conn, anos):
    """Carrega contratos estaduais -> pb_contrato."""
    total = 0
    for ano in anos:
        cache = PB_DIR / f"contratos_{ano}.csv"
        data = _load_csv(cache)
        if data is None:
            print(f"    contratos-{ano}: sem dados (rodar 00_download primeiro)")
            continue

        staging = "_stg_pb_contrato"
        n = _staging_load_from_data(conn, staging, data, 20)
        if n == 0:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            continue

        sql = """
            INSERT INTO pb_contrato (
                codigo_contrato, numero_registro_cge, numero_contrato,
                nome_contratante, numero_processo_licitatorio,
                objeto_contrato, complemento_objeto_contrato,
                nome_contratado, cpfcnpj_contratado,
                data_celebracao_contrato, data_publicacao,
                data_inicio_vigencia, data_termino_vigencia,
                valor_original, nome_municipio, outros_municipios,
                nome_gestor_contrato, numero_portaria,
                data_publicacao_portaria, url_contrato
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4),
                TRIM(c5), TRIM(c6), TRIM(c7),
                REPLACE(REPLACE(REPLACE(REPLACE(TRIM(c8), '.', ''), '-', ''), '/', ''), ' ', ''),
                CASE WHEN TRIM(c9) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c9) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c10) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c10) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c11) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c11) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c12) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c12) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c13) ~ '^-?[\\d.]+$' THEN CAST(TRIM(c13) AS DECIMAL(15,2)) ELSE NULL END,
                TRIM(c14), TRIM(c15), TRIM(c16), TRIM(c17),
                CASE WHEN TRIM(c18) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c18) AS DATE) ELSE NULL END,
                TRIM(c19)
            FROM {staging}
        """.format(staging=staging)
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()
        total += n
        print(f"    contratos-{ano}: {n:,} linhas")
    return total


def load_saude(conn, anos):
    """Carrega pagamentos gestao pactuada saude -> pb_saude."""
    total = 0
    for ano in anos:
        for mes in MESES:
            cache = PB_DIR / f"saude_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                continue

            staging = "_stg_pb_saude"
            n = _staging_load_from_data(conn, staging, data, 15)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            sql = """
                INSERT INTO pb_saude (
                    codigo_envio, competencia, codigo_organizacao_social,
                    nome_organizacao_social, codigo_lancamento, data_lancamento,
                    numero_documento, tipo_documento, numero_processo,
                    codigo_categoria_despesa, nome_categoria_despesa,
                    cpfcnpj_credor, nome_credor, valor_lancamento,
                    observacao_lancamento
                )
                SELECT
                    TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4),
                    CASE WHEN TRIM(c5) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c5) AS DATE) ELSE NULL END,
                    TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9), TRIM(c10),
                    REPLACE(REPLACE(REPLACE(REPLACE(TRIM(c11), '.', ''), '-', ''), '/', ''), ' ', ''),
                    TRIM(c12),
                    CASE WHEN TRIM(c13) ~ '^-?[\\d.]+$' THEN CAST(TRIM(c13) AS DECIMAL(15,2)) ELSE NULL END,
                    TRIM(c14)
                FROM {staging}
            """.format(staging=staging)
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            total += n

        print(f"    saude-{ano}: {total:,} acumuladas", flush=True)
    return total


def load_convenios(conn, anos):
    """Carrega convenios estado-municipios -> pb_convenio."""
    total = 0
    for ano in anos:
        cache = PB_DIR / f"convenios_{ano}.csv"
        data = _load_csv(cache)
        if data is None:
            print(f"    convenios-{ano}: sem dados (rodar 00_download primeiro)")
            continue

        staging = "_stg_pb_convenio"
        n = _staging_load_from_data(conn, staging, data, 16)
        if n == 0:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            continue

        sql = """
            INSERT INTO pb_convenio (
                codigo_convenio, numero_registro_cge, numero_convenio,
                nome_concedente, nome_convenente, cnpj_convenente,
                nome_municipio, objetivo_convenio, complemento_objeto_convenio,
                data_celebracao_convenio, data_publicacao,
                valor_concedente, valor_contrapartida,
                data_inicio_vigencia, data_termino_vigencia, url_convenio
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4),
                REPLACE(REPLACE(REPLACE(REPLACE(TRIM(c5), '.', ''), '-', ''), '/', ''), ' ', ''),
                TRIM(c6), TRIM(c7), TRIM(c8),
                CASE WHEN TRIM(c9) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c9) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c10) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c10) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c11) ~ '^-?[\\d.]+$' THEN CAST(TRIM(c11) AS DECIMAL(15,2)) ELSE NULL END,
                CASE WHEN TRIM(c12) ~ '^-?[\\d.]+$' THEN CAST(TRIM(c12) AS DECIMAL(15,2)) ELSE NULL END,
                CASE WHEN TRIM(c13) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c13) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c14) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c14) AS DATE) ELSE NULL END,
                TRIM(c15)
            FROM {staging}
        """.format(staging=staging)
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()
        total += n
        print(f"    convenios-{ano}: {n:,} linhas")
    return total


def load_pagamento_anulacao(conn, anos):
    """Carrega pagamento_anulacao -> pb_pagamento_anulacao."""
    total = 0
    for ano in anos:
        ano_count = 0
        for mes in MESES:
            cache = PB_DIR / f"pagamento_anulacao_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                continue

            staging = "_stg_pb_pagamento_anulacao"
            n = _staging_load_from_data(conn, staging, data, 9)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            sql = f"""
                INSERT INTO pb_pagamento_anulacao (
                    exercicio, codigo_unidade_gestora, numero_empenho,
                    numero_guia_devolucao, numero_autorizacao_pagamento,
                    data_documento, valor_documento,
                    codigo_tipo_documento, descricao_tipo_documento
                )
                SELECT
                    {_sql_smallint('c0')},
                    TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4),
                    {_sql_date('c5')},
                    {_sql_decimal('c6')},
                    TRIM(c7), TRIM(c8)
                FROM {staging}
            """
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            ano_count += n

        total += ano_count
        print(f"    pagamento_anulacao-{ano}: {ano_count:,} linhas", flush=True)
    return total


def load_liquidacaodespesa(conn, anos):
    """Carrega liquidacaodespesa -> pb_liquidacao_despesa."""
    total = 0
    for ano in anos:
        ano_count = 0
        for mes in MESES:
            cache = PB_DIR / f"liquidacaodespesa_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                continue

            staging = "_stg_pb_liquidacao_despesa"
            n = _staging_load_from_data(conn, staging, data, 17)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            sql = f"""
                INSERT INTO pb_liquidacao_despesa (
                    exercicio, data_movimentacao, codigo_orgao,
                    numero_empenho, documento, documento_origem,
                    ano_documento_origem, tipo_liquidacao, codigo_credor,
                    cpfcnpj_credor, tipo_documento_fiscal, numero_nota_fiscal,
                    data_nota_fiscal, codigo_inscricao_rp, ano_inscricao_rp,
                    codigo_orgao_extinto, valor_liquidacao
                )
                SELECT
                    {_sql_smallint('c0')},
                    {_sql_date('c1')},
                    TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5),
                    {_sql_smallint('c6')},
                    TRIM(c7), TRIM(c8),
                    {_sql_digits('c9')},
                    TRIM(c10), TRIM(c11),
                    {_sql_date('c12')},
                    TRIM(c13), {_sql_smallint('c14')},
                    TRIM(c15), {_sql_decimal('c16')}
                FROM {staging}
            """
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            ano_count += n

        total += ano_count
        print(f"    liquidacaodespesa-{ano}: {ano_count:,} linhas", flush=True)
    return total


def load_liquidacaodespesadescontos(conn, anos):
    """Carrega liquidacaodespesadescontos -> pb_liquidacao_desconto."""
    total = 0
    for ano in anos:
        ano_count = 0
        for mes in MESES:
            cache = PB_DIR / f"liquidacaodespesadescontos_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                continue

            staging = "_stg_pb_liquidacao_desconto"
            n = _staging_load_from_data(conn, staging, data, 10)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            sql = f"""
                INSERT INTO pb_liquidacao_desconto (
                    exercicio, codigo_orgao, numero_empenho,
                    numero_documento, data_pagamento, tipo_pagamento,
                    codigo_desconto, descricao_desconto,
                    codigo_orgao_pagamento, valor_desconto
                )
                SELECT
                    {_sql_smallint('c0')},
                    TRIM(c1), TRIM(c2), TRIM(c3),
                    {_sql_date('c4')},
                    TRIM(c5), TRIM(c6), TRIM(c7),
                    TRIM(c8), {_sql_decimal('c9')}
                FROM {staging}
            """
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            ano_count += n

        total += ano_count
        print(f"    liquidacaodespesadescontos-{ano}: {ano_count:,} linhas", flush=True)
    return total


def _load_empenho_variacao(conn, anos, prefix, table_name):
    """Carrega datasets com layout de 37 colunas tipo empenho."""
    total = 0
    for ano in anos:
        ano_count = 0
        for mes in MESES:
            cache = PB_DIR / f"{prefix}_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                continue

            staging = f"_stg_{table_name}"
            n = _staging_load_from_data(conn, staging, data, 37)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            sql = f"""
                INSERT INTO {table_name} (
                    exercicio, codigo_unidade_gestora, numero_empenho,
                    numero_empenho_origem, data_empenho, historico_empenho,
                    codigo_situacao_empenho, codigo_tipo_empenho, descricao_tipo_empenho,
                    nome_situacao_empenho, valor_empenho, codigo_modalidade_licitacao,
                    codigo_motivo_dispensa_licitacao, codigo_tipo_credito, nome_tipo_credito,
                    destino_diarias, data_saida_diarias, data_chegada_diarias,
                    nome_credor, cpfcnpj_credor, tipo_credor,
                    codigo_municipio, nome_municipio, numero_processo_pagamento,
                    numero_contrato, codigo_unidade_orcamentaria, codigo_funcao,
                    codigo_subfuncao, codigo_programa, codigo_acao,
                    codigo_fonte_recurso, codigo_natureza_despesa,
                    codigo_categoria_economica_despesa, codigo_grupo_natureza_despesa,
                    codigo_modalidade_aplicacao_despesa, codigo_elemento_despesa,
                    codigo_item_despesa
                )
                SELECT
                    {_sql_smallint('c0')},
                    TRIM(c1), TRIM(c2), TRIM(c3),
                    {_sql_date('c4')},
                    TRIM(c5), TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9),
                    {_sql_decimal('c10')},
                    TRIM(c11), TRIM(c12), TRIM(c13), TRIM(c14),
                    TRIM(c15),
                    {_sql_date('c16')},
                    {_sql_date('c17')},
                    TRIM(c18), {_sql_digits('c19')}, TRIM(c20),
                    TRIM(c21), TRIM(c22), TRIM(c23), TRIM(c24),
                    TRIM(c25), TRIM(c26), TRIM(c27), TRIM(c28), TRIM(c29),
                    TRIM(c30), TRIM(c31), TRIM(c32), TRIM(c33), TRIM(c34),
                    TRIM(c35), TRIM(c36)
                FROM {staging}
            """
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            ano_count += n

        total += ano_count
        print(f"    {prefix}-{ano}: {ano_count:,} linhas", flush=True)
    return total


def load_dotacao(conn, anos):
    """Carrega dotacao -> pb_dotacao."""
    total = 0
    for ano in anos:
        ano_count = 0
        for mes in MESES:
            cache = PB_DIR / f"dotacao_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                continue

            staging = "_stg_pb_dotacao"
            n = _staging_load_from_data(conn, staging, data, 15)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            sql = f"""
                INSERT INTO pb_dotacao (
                    codigo_unidade_gestora, exercicio, codigo_unidade_orcamentaria,
                    codigo_funcao, codigo_subfuncao, codigo_programa,
                    codigo_acao, meta, localidade, categoria,
                    grupo_despesa, modalidade, elemento_despesa,
                    fonte_recurso, valor_orcado
                )
                SELECT
                    TRIM(c0), {_sql_smallint('c1')}, TRIM(c2),
                    TRIM(c3), TRIM(c4), TRIM(c5),
                    TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9),
                    TRIM(c10), TRIM(c11), TRIM(c12),
                    TRIM(c13), {_sql_decimal('c14')}
                FROM {staging}
            """
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            ano_count += n

        total += ano_count
        print(f"    dotacao-{ano}: {ano_count:,} linhas", flush=True)
    return total


def load_liquidacao_cge(conn, anos):
    """Carrega liquidacao_cge -> pb_liquidacao_cge."""
    total = 0
    for ano in anos:
        ano_count = 0
        for mes in MESES:
            cache = PB_DIR / f"liquidacao_cge_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                continue

            staging = "_stg_pb_liquidacao_cge"
            n = _staging_load_from_data(conn, staging, data, 27)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            sql = f"""
                INSERT INTO pb_liquidacao_cge (
                    exercicio, codigo_orgao, numero_classificacao,
                    codigo_unidade, codigo_funcao, codigo_subfuncao,
                    codigo_programa, codigo_projeto_atividade, meta,
                    localidade, codigo_natureza, codigo_fonte,
                    valor, numero_empenho, documento,
                    tipo_liquidacao, tipo_documento_fiscal, numero_nota_fiscal,
                    data_nota_fiscal, data_movimentacao, data_processo,
                    data_atualizacao, usuario_atualizacao, documento_origem,
                    codigo_inscricao_rp, ano_inscricao_rp, ano_documento_origem
                )
                SELECT
                    {_sql_smallint('c0')},
                    TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5),
                    TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9), TRIM(c10), TRIM(c11),
                    {_sql_decimal('c12')},
                    TRIM(c13), TRIM(c14), TRIM(c15), TRIM(c16), TRIM(c17),
                    {_sql_date('c18')},
                    {_sql_date('c19')},
                    {_sql_date('c20')},
                    {_sql_date('c21')},
                    TRIM(c22), TRIM(c23), TRIM(c24),
                    {_sql_smallint('c25')},
                    {_sql_smallint('c26')}
                FROM {staging}
            """
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            ano_count += n

        total += ano_count
        print(f"    liquidacao_cge-{ano}: {ano_count:,} linhas", flush=True)
    return total


def load_aditivos_contrato(conn, anos):
    """Carrega aditivos_contrato -> pb_aditivo_contrato."""
    total = 0
    for ano in anos:
        ano_count = 0
        for mes in MESES:
            cache = PB_DIR / f"aditivos_contrato_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                continue

            staging = "_stg_pb_aditivo_contrato"
            n = _staging_load_from_data(conn, staging, data, 12)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            sql = f"""
                INSERT INTO pb_aditivo_contrato (
                    codigo_aditivo_contrato, codigo_contrato, motivo_aditivacao,
                    numero_aditivo_contrato, data_inicio_vigencia, data_termino_vigencia,
                    valor_aditivo, objeto_aditivo, data_celebracao_aditivo,
                    data_publicacao, data_republicacao, url_aditivo_contrato
                )
                SELECT
                    TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3),
                    {_sql_date('c4')}, {_sql_date('c5')},
                    {_sql_decimal('c6')},
                    TRIM(c7), {_sql_date('c8')}, {_sql_date('c9')},
                    {_sql_date('c10')}, TRIM(c11)
                FROM {staging}
            """
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            ano_count += n

        total += ano_count
        print(f"    aditivos_contrato-{ano}: {ano_count:,} linhas", flush=True)
    return total


def load_aditivos_convenio(conn, anos):
    """Carrega aditivos_convenio -> pb_aditivo_convenio."""
    total = 0
    for ano in anos:
        ano_count = 0
        for mes in MESES:
            cache = PB_DIR / f"aditivos_convenio_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                continue

            staging = "_stg_pb_aditivo_convenio"
            n = _staging_load_from_data(conn, staging, data, 13)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            sql = f"""
                INSERT INTO pb_aditivo_convenio (
                    codigo_aditivo_convenio, codigo_convenio, motivo_aditivacao,
                    numero_aditivo_convenio, data_inicio_vigencia, data_termino_vigencia,
                    valor_concedente, valor_convenente, objeto_aditivo,
                    data_celebracao_aditivo, data_publicacao, data_republicacao,
                    url_aditivo_convenio
                )
                SELECT
                    TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3),
                    {_sql_date('c4')}, {_sql_date('c5')},
                    {_sql_decimal('c6')}, {_sql_decimal('c7')},
                    TRIM(c8), {_sql_date('c9')}, {_sql_date('c10')},
                    {_sql_date('c11')}, TRIM(c12)
                FROM {staging}
            """
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            ano_count += n

        total += ano_count
        print(f"    aditivos_convenio-{ano}: {ano_count:,} linhas", flush=True)
    return total


def load_unidade_gestora(conn, anos):
    """Carrega unidade_gestora -> pb_unidade_gestora."""
    total = 0
    for ano in anos:
        cache = PB_DIR / f"unidade_gestora_{ano}.csv"
        data = _load_csv(cache)
        if data is None:
            continue

        staging = "_stg_pb_unidade_gestora"
        n = _staging_load_from_data(conn, staging, data, 5)
        if n == 0:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            continue

        sql = f"""
            INSERT INTO pb_unidade_gestora (
                exercicio, codigo_unidade_gestora, sigla_unidade_gestora,
                nome_unidade_gestora, tipo_administracao
            )
            SELECT
                {_sql_smallint('c0')},
                TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4)
            FROM {staging}
        """
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()
        total += n
        print(f"    unidade_gestora-{ano}: {n:,} linhas", flush=True)
    return total


def create_indices(conn):
    """Cria indices para as tabelas dados.pb.gov.br."""
    print("    Criando indices...")
    indices = [
        # Pagamento
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_cpfcnpj ON pb_pagamento(cpfcnpj_credor)",
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_exercicio ON pb_pagamento(exercicio)",
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_data ON pb_pagamento(data_pagamento)",
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_ug ON pb_pagamento(codigo_unidade_gestora)",
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_valor ON pb_pagamento(valor_pagamento)",
        # Empenho
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_cpfcnpj ON pb_empenho(cpfcnpj_credor)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_exercicio ON pb_empenho(exercicio)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_data ON pb_empenho(data_empenho)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_modalidade ON pb_empenho(codigo_modalidade_licitacao)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_ug ON pb_empenho(codigo_unidade_gestora)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_valor ON pb_empenho(valor_empenho)",
        # Contrato
        "CREATE INDEX IF NOT EXISTS idx_pb_ctr_cpfcnpj ON pb_contrato(cpfcnpj_contratado)",
        "CREATE INDEX IF NOT EXISTS idx_pb_ctr_valor ON pb_contrato(valor_original)",
        # Saude
        "CREATE INDEX IF NOT EXISTS idx_pb_saude_cpfcnpj ON pb_saude(cpfcnpj_credor)",
        "CREATE INDEX IF NOT EXISTS idx_pb_saude_valor ON pb_saude(valor_lancamento)",
        # Convenio
        "CREATE INDEX IF NOT EXISTS idx_pb_conv_cnpj ON pb_convenio(cnpj_convenente)",
        "CREATE INDEX IF NOT EXISTS idx_pb_conv_valor ON pb_convenio(valor_concedente)",
        # Pagamento anulacao
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_anul_exercicio ON pb_pagamento_anulacao(exercicio)",
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_anul_data ON pb_pagamento_anulacao(data_documento)",
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_anul_ug ON pb_pagamento_anulacao(codigo_unidade_gestora)",
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_anul_empenho ON pb_pagamento_anulacao(numero_empenho)",
        # Liquidacao despesa
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_desp_exercicio ON pb_liquidacao_despesa(exercicio)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_desp_data ON pb_liquidacao_despesa(data_movimentacao)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_desp_orgao ON pb_liquidacao_despesa(codigo_orgao)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_desp_empenho ON pb_liquidacao_despesa(numero_empenho)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_desp_cpfcnpj ON pb_liquidacao_despesa(cpfcnpj_credor)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_desp_valor ON pb_liquidacao_despesa(valor_liquidacao)",
        # Liquidacao desconto
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_desc_exercicio ON pb_liquidacao_desconto(exercicio)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_desc_data ON pb_liquidacao_desconto(data_pagamento)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_desc_orgao ON pb_liquidacao_desconto(codigo_orgao)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_desc_empenho ON pb_liquidacao_desconto(numero_empenho)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_desc_codigo ON pb_liquidacao_desconto(codigo_desconto)",
        # Empenho variacoes
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_anul_cpfcnpj ON pb_empenho_anulacao(cpfcnpj_credor)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_anul_data ON pb_empenho_anulacao(data_empenho)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_anul_ug ON pb_empenho_anulacao(codigo_unidade_gestora)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_supl_cpfcnpj ON pb_empenho_suplementacao(cpfcnpj_credor)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_supl_data ON pb_empenho_suplementacao(data_empenho)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_supl_ug ON pb_empenho_suplementacao(codigo_unidade_gestora)",
        "CREATE INDEX IF NOT EXISTS idx_pb_diaria_cpfcnpj ON pb_diaria(cpfcnpj_credor)",
        "CREATE INDEX IF NOT EXISTS idx_pb_diaria_data ON pb_diaria(data_empenho)",
        "CREATE INDEX IF NOT EXISTS idx_pb_diaria_destino ON pb_diaria(destino_diarias)",
        # Dotacao
        "CREATE INDEX IF NOT EXISTS idx_pb_dot_exercicio ON pb_dotacao(exercicio)",
        "CREATE INDEX IF NOT EXISTS idx_pb_dot_ug ON pb_dotacao(codigo_unidade_gestora)",
        "CREATE INDEX IF NOT EXISTS idx_pb_dot_uo ON pb_dotacao(codigo_unidade_orcamentaria)",
        "CREATE INDEX IF NOT EXISTS idx_pb_dot_fonte ON pb_dotacao(fonte_recurso)",
        # Liquidacao CGE
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_cge_exercicio ON pb_liquidacao_cge(exercicio)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_cge_orgao ON pb_liquidacao_cge(codigo_orgao)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_cge_empenho ON pb_liquidacao_cge(numero_empenho)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_cge_data ON pb_liquidacao_cge(data_movimentacao)",
        "CREATE INDEX IF NOT EXISTS idx_pb_liq_cge_valor ON pb_liquidacao_cge(valor)",
        # Aditivos
        "CREATE INDEX IF NOT EXISTS idx_pb_ad_ct_contrato ON pb_aditivo_contrato(codigo_contrato)",
        "CREATE INDEX IF NOT EXISTS idx_pb_ad_ct_publicacao ON pb_aditivo_contrato(data_publicacao)",
        "CREATE INDEX IF NOT EXISTS idx_pb_ad_ct_valor ON pb_aditivo_contrato(valor_aditivo)",
        "CREATE INDEX IF NOT EXISTS idx_pb_ad_cv_convenio ON pb_aditivo_convenio(codigo_convenio)",
        "CREATE INDEX IF NOT EXISTS idx_pb_ad_cv_publicacao ON pb_aditivo_convenio(data_publicacao)",
        "CREATE INDEX IF NOT EXISTS idx_pb_ad_cv_valor ON pb_aditivo_convenio(valor_concedente)",
        # Unidade gestora
        "CREATE INDEX IF NOT EXISTS idx_pb_ug_exercicio ON pb_unidade_gestora(exercicio)",
        "CREATE INDEX IF NOT EXISTS idx_pb_ug_codigo ON pb_unidade_gestora(codigo_unidade_gestora)",
        "CREATE INDEX IF NOT EXISTS idx_pb_ug_sigla ON pb_unidade_gestora(sigla_unidade_gestora)",
    ]
    with conn.cursor() as cur:
        for idx_sql in indices:
            cur.execute(idx_sql)
    conn.commit()
    print("    Indices criados.")


def run():
    # Parse args
    only = None
    anos = list(ANOS)
    skip_schema = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--only" and i + 1 < len(args):
            only = args[i + 1].split(",")
            i += 2
        elif args[i] == "--anos" and i + 1 < len(args):
            anos = [int(a) for a in args[i + 1].split(",")]
            i += 2
        elif args[i] == "--no-schema":
            skip_schema = True
            i += 1
        else:
            i += 1

    conn = get_conn()
    try:
        if not skip_schema:
            from etl.config import SQL_DIR
            sql = (SQL_DIR / "20_schema_dados_pb.sql").read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            print("    Schema dados.pb.gov.br criado.")
        else:
            print("    Schema skip (--no-schema).")

        loaders = {
            "pagamento": load_pagamento,
            "empenho": load_empenho,
            "contratos": load_contratos,
            "saude": load_saude,
            "convenios": load_convenios,
            "pagamento_anulacao": load_pagamento_anulacao,
            "liquidacaodespesa": load_liquidacaodespesa,
            "liquidacaodespesadescontos": load_liquidacaodespesadescontos,
            "empenho_anulacao": lambda c, a: _load_empenho_variacao(c, a, "empenho_anulacao", "pb_empenho_anulacao"),
            "empenho_suplementacao": lambda c, a: _load_empenho_variacao(c, a, "empenho_suplementacao", "pb_empenho_suplementacao"),
            "dotacao": load_dotacao,
            "liquidacao_cge": load_liquidacao_cge,
            "aditivos_contrato": load_aditivos_contrato,
            "aditivos_convenio": load_aditivos_convenio,
            "diarias": lambda c, a: _load_empenho_variacao(c, a, "diarias", "pb_diaria"),
            "unidade_gestora": load_unidade_gestora,
        }

        targets = only if only else loaders.keys()
        for target in targets:
            if target in loaders:
                print(f"\n  [{target}]")
                loaders[target](conn, anos)

        # Contagens
        print()
        for t in [
            "pb_pagamento", "pb_empenho", "pb_contrato", "pb_saude", "pb_convenio",
            "pb_pagamento_anulacao", "pb_liquidacao_despesa", "pb_liquidacao_desconto",
            "pb_empenho_anulacao", "pb_empenho_suplementacao", "pb_dotacao",
            "pb_liquidacao_cge", "pb_aditivo_contrato", "pb_aditivo_convenio",
            "pb_diaria", "pb_unidade_gestora",
        ]:
            print(f"    {t}: {table_count(conn, t):,} registros")

        # Indices
        create_indices(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    run()
