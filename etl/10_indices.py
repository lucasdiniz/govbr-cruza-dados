"""Fase 6: Cria todos os índices após a carga completa dos dados."""

from etl.db import get_conn, execute_sql_file


def run():
    conn = get_conn()
    try:
        print("  Criando índices (pode demorar ~30-45 min)...")
        execute_sql_file(conn, "11_indices.sql")
        print("  Índices criados com sucesso.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
