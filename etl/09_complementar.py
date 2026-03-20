"""Fase 4.7-4.8 + 5.2: Carrega BNDES, Holdings e ComprasNet.

Fontes:
  - bndes.csv (delimitador ;, quoted, com header)
  - holding.csv (delimitador ,, com header)
  - comprasnet.csv (delimitador ,, com header)
"""

from etl.config import DATA_DIR
from etl.db import get_conn, table_count


def load_bndes(conn):
    """Carrega bndes.csv → bndes_contrato."""
    filepath = DATA_DIR / "bndes.csv"
    if not filepath.exists():
        print("    AVISO: bndes.csv não encontrado.")
        return

    staging = "_stg_bndes"
    cols = ", ".join(f"c{i} TEXT" for i in range(34))
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"CREATE UNLOGGED TABLE {staging} ({cols})")
    conn.commit()

    copy_sql = f"""COPY {staging} FROM STDIN
        WITH (FORMAT csv, DELIMITER ';', HEADER true, NULL '', ENCODING 'LATIN1')"""
    with open(filepath, "rb") as f:
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, f)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO bndes_contrato (
                cliente, cnpj, descricao_projeto, uf, municipio, municipio_codigo,
                numero_contrato, dt_contratacao, valor_contratado, valor_desembolsado,
                fonte_recurso, custo_financeiro, juros, prazo_carencia_meses,
                prazo_amortizacao_meses, modalidade_apoio, forma_apoio, produto,
                instrumento_financeiro, inovacao, area_operacional,
                setor_cnae, subsetor_cnae, subsetor_cnae_codigo,
                setor_bndes, subsetor_bndes, porte_cliente, natureza_cliente,
                instituicao_credenciada, cnpj_instituicao,
                tipo_garantia, tipo_excepcionalidade, situacao_contrato
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5),
                TRIM(c6),
                CASE WHEN TRIM(c7) ~ '^\d{2}/\d{2}/\d{4}$' THEN safe_to_date(TRIM(c7), 'DD/MM/YYYY') ELSE NULL END,
                CASE WHEN TRIM(c8) = '' THEN NULL
                     ELSE CAST(REPLACE(REPLACE(TRIM(c8), '.', ''), ',', '.') AS NUMERIC) END,
                CASE WHEN TRIM(c9) = '' THEN NULL
                     ELSE CAST(REPLACE(REPLACE(TRIM(c9), '.', ''), ',', '.') AS NUMERIC) END,
                TRIM(c10), TRIM(c11), TRIM(c12),
                CASE WHEN TRIM(c13) ~ '^\d+$' THEN CAST(TRIM(c13) AS INT) ELSE NULL END,
                CASE WHEN TRIM(c14) ~ '^\d+$' THEN CAST(TRIM(c14) AS INT) ELSE NULL END,
                TRIM(c15), TRIM(c16), TRIM(c17), TRIM(c18), TRIM(c19), TRIM(c20),
                TRIM(c21), TRIM(c22), TRIM(c23), TRIM(c24), TRIM(c25),
                TRIM(c26), TRIM(c27), TRIM(c28), TRIM(c29),
                TRIM(c30), TRIM(c31), TRIM(c32)
            FROM {staging}
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()

    print(f"    bndes_contrato: {table_count(conn, 'bndes_contrato')} registros")


def load_holdings(conn):
    """Carrega holding.csv → holding_vinculo."""
    filepath = DATA_DIR / "holding.csv"
    if not filepath.exists():
        print("    AVISO: holding.csv não encontrado.")
        return

    staging = "_stg_holding"
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"""CREATE UNLOGGED TABLE {staging} (
            c0 TEXT, c1 TEXT, c2 TEXT, c3 TEXT, c4 TEXT, c5 TEXT
        )""")
    conn.commit()

    # holding.csv usa VÍRGULA como delimitador
    copy_sql = f"""COPY {staging} FROM STDIN
        WITH (FORMAT csv, DELIMITER ',', HEADER true, NULL '', ENCODING 'UTF8')"""
    with open(filepath, "rb") as f:
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, f)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO holding_vinculo (
                holding_cnpj, holding_razao_social,
                cnpj_subsidiaria, razao_social_subsidiaria,
                codigo_qualificacao, qualificacao
            )
            SELECT TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5)
            FROM {staging}
            WHERE TRIM(c0) != '' AND TRIM(c2) != ''
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()

    print(f"    holding_vinculo: {table_count(conn, 'holding_vinculo')} registros")


def load_comprasnet(conn):
    """Carrega comprasnet.csv → comprasnet_contrato."""
    filepath = DATA_DIR / "comprasnet.csv"
    if not filepath.exists():
        print("    AVISO: comprasnet.csv não encontrado.")
        return

    staging = "_stg_comprasnet"
    cols = ", ".join(f"c{i} TEXT" for i in range(38))
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"CREATE UNLOGGED TABLE {staging} ({cols})")
    conn.commit()

    # comprasnet.csv usa VÍRGULA como delimitador
    copy_sql = f"""COPY {staging} FROM STDIN
        WITH (FORMAT csv, DELIMITER ',', HEADER true, NULL '', ENCODING 'UTF8')"""
    with open(filepath, "rb") as f:
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, f)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO comprasnet_contrato (
                id_comprasnet, receita_despesa, numero, orgao_codigo, orgao_nome,
                unidade_codigo, esfera, poder, sisg, gestao,
                unidade_nome_resumido, unidade_nome, unidade_origem_codigo, unidade_origem_nome,
                fornecedor_tipo, fornecedor_cnpj_cpf, fornecedor_nome,
                codigo_tipo, tipo, categoria, processo, objeto,
                fundamento_legal, informacao_complementar,
                codigo_modalidade, modalidade, unidade_compra, licitacao_numero,
                dt_assinatura, dt_publicacao, vigencia_inicio, vigencia_fim,
                valor_inicial, valor_global, num_parcelas, valor_parcela,
                valor_acumulado, situacao
            )
            SELECT
                CASE WHEN TRIM(c0) ~ '^\d+$' THEN CAST(TRIM(c0) AS INT) ELSE NULL END,
                TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5),
                TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9),
                TRIM(c10), TRIM(c11), TRIM(c12), TRIM(c13),
                TRIM(c14), TRIM(c15), TRIM(c16), TRIM(c17), TRIM(c18),
                TRIM(c19), TRIM(c20), TRIM(c21), TRIM(c22), TRIM(c23),
                TRIM(c24), TRIM(c25), TRIM(c26), TRIM(c27),
                CASE WHEN TRIM(c28) ~ '^\d{4}-\d{2}-\d{2}$' THEN safe_to_date(TRIM(c28), 'YYYY-MM-DD') ELSE NULL END,
                CASE WHEN TRIM(c29) ~ '^\d{4}-\d{2}-\d{2}$' THEN safe_to_date(TRIM(c29), 'YYYY-MM-DD') ELSE NULL END,
                CASE WHEN TRIM(c30) ~ '^\d{4}-\d{2}-\d{2}$' THEN safe_to_date(TRIM(c30), 'YYYY-MM-DD') ELSE NULL END,
                CASE WHEN TRIM(c31) ~ '^\d{4}-\d{2}-\d{2}$' THEN safe_to_date(TRIM(c31), 'YYYY-MM-DD') ELSE NULL END,
                CASE WHEN TRIM(c32) = '' THEN NULL ELSE CAST(TRIM(c32) AS NUMERIC) END,
                CASE WHEN TRIM(c33) = '' THEN NULL ELSE CAST(TRIM(c33) AS NUMERIC) END,
                CASE WHEN TRIM(c34) ~ '^\d+$' THEN CAST(TRIM(c34) AS INT) ELSE NULL END,
                CASE WHEN TRIM(c35) = '' THEN NULL ELSE CAST(TRIM(c35) AS NUMERIC) END,
                CASE WHEN TRIM(c36) = '' THEN NULL ELSE CAST(TRIM(c36) AS NUMERIC) END,
                TRIM(c37)
            FROM {staging}
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()

    print(f"    comprasnet_contrato: {table_count(conn, 'comprasnet_contrato')} registros")


def run():
    conn = get_conn()
    try:
        load_bndes(conn)
        load_holdings(conn)
        load_comprasnet(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
