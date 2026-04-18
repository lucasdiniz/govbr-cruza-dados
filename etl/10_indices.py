"""Fase 6: Cria todos os indices apos a carga completa dos dados."""

import re
from pathlib import Path

from etl.db import get_conn


def _table_exists(conn, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
        return cur.fetchone()[0] is not None


def _has_executable_sql(statement: str) -> bool:
    for line in statement.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("--"):
            return True
    return False


def _execute_indices_sql(conn, filename: str):
    sql_path = Path(__file__).resolve().parents[1] / "sql" / filename
    content = sql_path.read_text(encoding="utf-8")
    statements = [s.strip() for s in content.split(";") if _has_executable_sql(s)]
    skipped = 0

    # CREATE INDEX CONCURRENTLY exige que NAO esteja em transacao.
    # Setamos autocommit=True quando o arquivo usa CONCURRENTLY (ex: 19_indices_queries.sql).
    # Fora de transacao, cada CREATE INDEX faz commit implicito.
    uses_concurrently = "CONCURRENTLY" in content.upper()
    prev_autocommit = conn.autocommit
    if uses_concurrently:
        conn.commit()  # encerra qualquer txn pendente
        conn.autocommit = True

    try:
        for stmt in statements:
            match = re.search(r"\bON\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", stmt, flags=re.IGNORECASE)
            table_name = match.group(1) if match else None
            if table_name and not _table_exists(conn, table_name):
                print(f"    AVISO: tabela {table_name} nao existe ainda, pulando indice.")
                skipped += 1
                continue
            with conn.cursor() as cur:
                cur.execute(stmt)
            if not conn.autocommit:
                conn.commit()
    finally:
        if uses_concurrently:
            conn.autocommit = prev_autocommit

    if skipped:
        print(f"  Indices: {skipped} statement(s) pulados por tabela ausente.")


def run():
    conn = get_conn()
    try:
        print("  Criando indices base (11_indices.sql, pode demorar ~30-45 min)...")
        _execute_indices_sql(conn, "11_indices.sql")
        print("  Indices base criados.")
        print("  Criando indices das queries de fraude (19_indices_queries.sql, CONCURRENTLY)...")
        _execute_indices_sql(conn, "19_indices_queries.sql")
        print("  Indices das queries criados com sucesso.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
