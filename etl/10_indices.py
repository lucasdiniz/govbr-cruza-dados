"""Fase 6: Cria todos os indices apos a carga completa dos dados."""

import re
from pathlib import Path

from etl.db import get_conn


def _table_exists(conn, table_name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
        return cur.fetchone()[0] is not None


def _has_executable_sql(statement: str) -> bool:
    without_block_comments = re.sub(r"/\*.*?\*/", "", statement, flags=re.DOTALL)
    without_line_comments = re.sub(r"^\s*--.*$", "", without_block_comments, flags=re.MULTILINE)
    return bool(without_line_comments.strip())


def _execute_indices_sql(conn, filename: str):
    sql_path = Path(__file__).resolve().parents[1] / "sql" / filename
    content = sql_path.read_text(encoding="utf-8")
    statements = [s.strip() for s in content.split(";") if _has_executable_sql(s)]
    skipped = 0

    for stmt in statements:
        match = re.search(r"\bON\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", stmt, flags=re.IGNORECASE)
        table_name = match.group(1) if match else None
        if table_name and not _table_exists(conn, table_name):
            print(f"    AVISO: tabela {table_name} nao existe ainda, pulando indice.")
            skipped += 1
            continue
        with conn.cursor() as cur:
            cur.execute(stmt)
        conn.commit()

    if skipped:
        print(f"  Indices: {skipped} statement(s) pulados por tabela ausente.")


def run():
    conn = get_conn()
    try:
        print("  Criando indices (pode demorar ~30-45 min)...")
        _execute_indices_sql(conn, "11_indices.sql")
        print("  Indices criados com sucesso.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
