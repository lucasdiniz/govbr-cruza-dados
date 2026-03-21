"""Normaliza identificadores (CPF/CNPJ) para facilitar JOINs entre tabelas.

Cria colunas _norm com apenas digitos e indices parciais.
EXECUTAR APOS a carga completa (sem INSERTs ativos).
"""

from etl.db import get_conn, execute_sql_file


def run():
    conn = get_conn()
    try:
        print("  Normalizando identificadores...")
        print("  (pode demorar ~10-20min para tabelas grandes como PGFN e socio)")
        execute_sql_file(conn, "15_normalizar_ids.sql")
        print("  Normalizacao concluida.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
