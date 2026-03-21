"""Executa todas as queries de fraude e salva resultados em CSV.

Uso: python -m etl.run_queries [--query Q39] [--dir resultados]
"""

import argparse
import csv
import re
import time
from pathlib import Path

from etl.db import get_conn

QUERIES_DIR = Path(__file__).resolve().parent.parent / "queries"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "resultados"


def extract_queries(sql_text):
    """Extrai queries individuais de um arquivo SQL, separadas por '-- Qxx:'."""
    pattern = r"(-- Q(\d+): ([^\n]+)\n.*?)(?=-- Q\d+:|$)"
    matches = re.findall(pattern, sql_text, re.DOTALL)
    queries = []
    for full_block, num, title in matches:
        # Remove linhas de comentário para execução
        lines = []
        for line in full_block.strip().split("\n"):
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            lines.append(line)
        sql = "\n".join(lines).strip().rstrip(";")
        if sql:
            queries.append((int(num), title.strip(), sql))
    return queries


def run_query(conn, num, title, sql, results_dir):
    """Executa uma query e salva o resultado em CSV."""
    filename = f"q{num:02d}_{re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')[:60]}.csv"
    outpath = results_dir / filename

    cur = conn.cursor()
    try:
        t0 = time.time()
        cur.execute(sql)
        rows = cur.fetchall()
        elapsed = time.time() - t0
        cols = [d[0] for d in cur.description]

        with open(outpath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(cols)
            w.writerows(rows)

        print(f"  Q{num:02d}: {len(rows):>7,} resultados ({elapsed:.1f}s) -> {filename}")
        return len(rows)
    except Exception as e:
        conn.rollback()
        print(f"  Q{num:02d}: ERRO - {e}")
        return -1


def run(query_filter=None, results_dir=None):
    results_dir = Path(results_dir) if results_dir else RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)

    conn = get_conn()
    try:
        sql_files = sorted(QUERIES_DIR.glob("fraude_*.sql"))
        total_results = 0
        total_queries = 0

        for sql_file in sql_files:
            sql_text = sql_file.read_text(encoding="utf-8")
            queries = extract_queries(sql_text)

            if not queries:
                continue

            print(f"\n{sql_file.name}:")
            for num, title, sql in queries:
                if query_filter and f"Q{num}" != query_filter.upper():
                    continue
                count = run_query(conn, num, title, sql, results_dir)
                if count >= 0:
                    total_results += count
                    total_queries += 1

        print(f"\n{'='*60}")
        print(f"Total: {total_queries} queries, {total_results:,} resultados")
        print(f"Salvos em: {results_dir}")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", help="Rodar apenas uma query (ex: Q39)")
    parser.add_argument("--dir", help="Diretório de saída", default=None)
    args = parser.parse_args()
    run(query_filter=args.query, results_dir=args.dir)
