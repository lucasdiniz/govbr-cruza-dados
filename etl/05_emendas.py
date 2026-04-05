"""Fase 4.3-4.5: Carrega emendas parlamentares.

Fontes:
  - emendas_tesouro.csv (delimitador ;, com header)
  - transferegov_convenios.csv (delimitador ;, com header, quoted)
  - transferegov_favorecidos.csv (delimitador ;, com header, quoted)
"""

from pathlib import Path

from etl.config import DATA_DIR, RFB_ENCODING
from etl.db import get_conn, table_count


EMENDAS_DIR = DATA_DIR / "emendas"


def _resolve_input(*names: str) -> Path | None:
    for name in names:
        for candidate in (EMENDAS_DIR / name, DATA_DIR / name):
            if candidate.exists():
                return candidate
    return None


def _resolve_input_glob(*patterns: str) -> Path | None:
    search_dirs = [EMENDAS_DIR, DATA_DIR]
    for pattern in patterns:
        for base in search_dirs:
            matches = sorted(base.glob(pattern))
            if matches:
                return matches[0]
    return None


def _copy_csv_with_header(conn, filepath, table, encoding="utf-8"):
    """COPY FROM de CSV com header, delimitador ;, campos quoted."""
    copy_sql = f"""COPY {table} FROM STDIN
        WITH (FORMAT csv, DELIMITER ';', HEADER true, NULL '', ENCODING '{encoding}')"""

    with open(filepath, "rb") as f:
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, f)
    conn.commit()


def load_emendas_tesouro(conn):
    """Carrega emendas_tesouro.csv → emenda_tesouro."""
    filepath = _resolve_input("emendas_tesouro.csv")
    if filepath is None:
        filepath = _resolve_input_glob("*emendas*tesouro*.csv", "*tesouro*.csv")
    if filepath is None:
        print("    AVISO: emendas_tesouro.csv não encontrado.")
        return

    # Precisa staging porque decimais usam vírgula
    staging = "_stg_emenda_tes"
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"""CREATE UNLOGGED TABLE {staging} (
            c0 TEXT, c1 TEXT, c2 TEXT, c3 TEXT, c4 TEXT, c5 TEXT, c6 TEXT,
            c7 TEXT, c8 TEXT, c9 TEXT, c10 TEXT, c11 TEXT, c12 TEXT, c13 TEXT, c14 TEXT
        )""")
    conn.commit()

    copy_sql = f"""COPY {staging} FROM STDIN
        WITH (FORMAT csv, DELIMITER ';', HEADER true, NULL '', ENCODING 'LATIN1')"""
    with open(filepath, "rb") as f:
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, f)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO emenda_tesouro (
                nome_ente, uf, codigo_siafi, codigo_ibge, dt_transacao,
                ano, mes, tipo_ente, ob, cnpj_favorecido,
                nome_favorecido, nome_emenda, transferencia_especial,
                categoria_economica, valor
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3),
                CASE WHEN TRIM(c4) ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
                     THEN safe_to_date(TRIM(c4), 'DD/MM/YYYY') ELSE NULL END,
                CASE WHEN TRIM(c5) ~ '^\\d+$' THEN CAST(TRIM(c5) AS SMALLINT) ELSE NULL END,
                CASE WHEN TRIM(c6) ~ '^\\d+$' THEN CAST(TRIM(c6) AS SMALLINT) ELSE NULL END,
                TRIM(c7), TRIM(c8), TRIM(c9), TRIM(c10), TRIM(c11), TRIM(c12),
                TRIM(c13),
                CASE WHEN TRIM(c14) ~ '^[\d.,-]+$' AND TRIM(c14) != ''
                     THEN CAST(REPLACE(REPLACE(TRIM(c14), '.', ''), ',', '.') AS NUMERIC)
                     ELSE NULL END
            FROM {staging}
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()

    print(f"    emenda_tesouro: {table_count(conn, 'emenda_tesouro')} registros")


def load_convenios(conn):
    """Carrega transferegov_convenios.csv → emenda_convenio."""
    filepath = _resolve_input("transferegov_convenios.csv")
    if filepath is None:
        filepath = _resolve_input_glob("*transferegov*convenio*.csv", "*convenio*.csv")
    if filepath is None:
        print("    AVISO: transferegov_convenios.csv não encontrado.")
        return

    staging = "_stg_emconv"
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"""CREATE UNLOGGED TABLE {staging} (
            c0 TEXT, c1 TEXT, c2 TEXT, c3 TEXT, c4 TEXT, c5 TEXT,
            c6 TEXT, c7 TEXT, c8 TEXT, c9 TEXT, c10 TEXT, c11 TEXT
        )""")
    conn.commit()

    copy_sql = f"""COPY {staging} FROM STDIN
        WITH (FORMAT csv, DELIMITER ';', HEADER true, NULL '', ENCODING 'LATIN1')"""
    with open(filepath, "rb") as f:
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, f)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO emenda_convenio (
                codigo_emenda, codigo_funcao, nome_funcao, codigo_subfuncao,
                nome_subfuncao, localidade_gasto, tipo_emenda, dt_publicacao,
                convenente, objeto, numero_convenio, valor_convenio
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5),
                TRIM(c6),
                CASE WHEN TRIM(c7) ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$' THEN safe_to_date(TRIM(c7), 'DD/MM/YYYY') ELSE NULL END,
                TRIM(c8), TRIM(c9), TRIM(c10),
                CASE WHEN TRIM(c11) = '' THEN NULL
                     ELSE CAST(REPLACE(REPLACE(TRIM(c11), '.', ''), ',', '.') AS NUMERIC)
                END
            FROM {staging}
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()

    print(f"    emenda_convenio: {table_count(conn, 'emenda_convenio')} registros")


def load_favorecidos(conn):
    """Carrega transferegov_favorecidos.csv → emenda_favorecido."""
    filepath = _resolve_input("transferegov_favorecidos.csv")
    if filepath is None:
        filepath = _resolve_input_glob("*transferegov*favorecid*.csv", "*favorecid*.csv")
    if filepath is None:
        print("    AVISO: transferegov_favorecidos.csv não encontrado.")
        return

    staging = "_stg_emfav"
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"""CREATE UNLOGGED TABLE {staging} (
            c0 TEXT, c1 TEXT, c2 TEXT, c3 TEXT, c4 TEXT, c5 TEXT,
            c6 TEXT, c7 TEXT, c8 TEXT, c9 TEXT, c10 TEXT, c11 TEXT, c12 TEXT
        )""")
    conn.commit()

    copy_sql = f"""COPY {staging} FROM STDIN
        WITH (FORMAT csv, DELIMITER ';', HEADER true, NULL '', ENCODING 'LATIN1')"""
    with open(filepath, "rb") as f:
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, f)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO emenda_favorecido (
                codigo_emenda, codigo_autor, nome_autor, numero_emenda,
                tipo_emenda, ano_mes, codigo_favorecido, nome_favorecido,
                natureza_juridica, tipo_favorecido, uf_favorecido,
                municipio_favorecido, valor_recebido
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5),
                TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9), TRIM(c10), TRIM(c11),
                CASE WHEN TRIM(c12) = '' THEN NULL
                     ELSE CAST(REPLACE(REPLACE(TRIM(c12), '.', ''), ',', '.') AS NUMERIC)
                END
            FROM {staging}
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()

    print(f"    emenda_favorecido: {table_count(conn, 'emenda_favorecido')} registros")


def run():
    conn = get_conn()
    try:
        load_emendas_tesouro(conn)
        load_convenios(conn)
        load_favorecidos(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
