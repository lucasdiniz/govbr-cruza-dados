"""Fase 18: Cria views materializadas e views de risco.

Pré-requisito: normalizacao (fase 17) completa com todos os indices.
Pode demorar ~1-2h dependendo do hardware.

Uso:
  python -m etl.21_views
"""

import re
import time

from etl.config import SQL_DIR
from etl.db import get_conn


def run():
    path = SQL_DIR / "12_views.sql"
    sql = path.read_text(encoding="utf-8")

    # Split into individual statements (ignoring comments and empty lines)
    # Each CREATE/DROP/SET is a separate statement
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]

    conn = get_conn()
    conn.autocommit = True
    try:
        for i, stmt in enumerate(statements, 1):
            # Extract a short label for progress
            label = stmt[:80].replace("\n", " ")
            if match := re.search(r"(CREATE|DROP)\s+\w+\s+(?:VIEW|INDEX)\s+(?:IF\s+\w+\s+)?(\w+)", stmt, re.IGNORECASE):
                label = f"{match.group(1)} {match.group(2)}"

            print(f"  [{i}/{len(statements)}] {label}...")
            t0 = time.time()
            with conn.cursor() as cur:
                cur.execute(stmt)
            elapsed = time.time() - t0
            if elapsed > 5:
                print(f"    Concluído em {elapsed:.0f}s")
    finally:
        conn.close()

    print("  Views materializadas criadas com sucesso.")


if __name__ == "__main__":
    run()
