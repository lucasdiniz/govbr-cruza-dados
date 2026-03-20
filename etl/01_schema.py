"""Fase 1: Cria extensões e todas as tabelas do schema."""

from etl.db import get_conn, execute_sql_file

SQL_FILES = [
    "00_extensions.sql",
    "01_schema_dominio.sql",
    "02_schema_rfb.sql",
    "03_schema_pncp.sql",
    "04_schema_emendas.sql",
    "05_schema_cpgf.sql",
    "07_schema_pgfn.sql",
    "08_schema_renuncias.sql",
    "09_schema_complementar.sql",
    "10_schema_pessoa.sql",
]


def run():
    conn = get_conn()
    try:
        for sql_file in SQL_FILES:
            print(f"  Executando {sql_file}...")
            execute_sql_file(conn, sql_file)
        print("  Schema criado com sucesso.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
