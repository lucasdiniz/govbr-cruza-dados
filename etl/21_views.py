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


def _strip_line_comments(sql: str) -> str:
    """Remove '--' line comments, preservando literais entre aspas.

    Necessário porque sql/12_views.sql tem comentários com ';' dentro
    (ex.: ``-- DROP TABLE foo;  -- nota``). Sem essa limpeza, um
    ``split(';')`` ingênuo quebra no meio dos comentários e cola chunks
    reais de CREATE a blocos de comentário, fazendo com que statements
    sejam silenciosamente descartados pelo filtro ``startswith('--')``.
    """
    out: list[str] = []
    in_single = False
    in_double = False
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'" and not in_double:
            # Aspas duplicadas ('') = apóstrofo literal dentro de string
            if in_single and i + 1 < n and sql[i + 1] == "'":
                out.append("''")
                i += 2
                continue
            in_single = not in_single
            out.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
            i += 1
            continue
        if ch == "-" and i + 1 < n and sql[i + 1] == "-" and not in_single and not in_double:
            # Pula até o fim da linha (preserva o \n para manter numeração)
            while i < n and sql[i] != "\n":
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _split_statements(sql: str) -> list[str]:
    """Divide SQL em statements por ';', respeitando literais."""
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'" and not in_double:
            if in_single and i + 1 < n and sql[i + 1] == "'":
                current.append(ch)
                current.append(sql[i + 1])
                i += 2
                continue
            in_single = not in_single
            current.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            current.append(ch)
            i += 1
            continue
        if ch == ";" and not in_single and not in_double:
            stmt = "".join(current).strip()
            if stmt:
                statements.append(stmt)
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _label(stmt: str) -> str:
    """Gera um rótulo curto para log de progresso."""
    m = re.search(
        r"(CREATE|DROP|REFRESH)\s+(?:UNIQUE\s+)?(?:MATERIALIZED\s+)?"
        r"(VIEW|INDEX|TABLE)\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?"
        r"(?:CONCURRENTLY\s+)?(\w+)",
        stmt,
        re.IGNORECASE,
    )
    if m:
        return f"{m.group(1).upper()} {m.group(2).upper()} {m.group(3)}"
    first_line = next((ln for ln in stmt.splitlines() if ln.strip()), "")
    return first_line[:100]


def run():
    path = SQL_DIR / "12_views.sql"
    raw = path.read_text(encoding="utf-8")
    cleaned = _strip_line_comments(raw)
    statements = _split_statements(cleaned)

    print(f"  Total: {len(statements)} statements a executar", flush=True)

    conn = get_conn()
    conn.autocommit = True
    try:
        for i, stmt in enumerate(statements, 1):
            label = _label(stmt)
            print(f"  [{i}/{len(statements)}] {label}...", flush=True)
            t0 = time.time()
            with conn.cursor() as cur:
                cur.execute(stmt)
            elapsed = time.time() - t0
            if elapsed > 5:
                print(f"    Concluído em {elapsed:.0f}s", flush=True)
    finally:
        conn.close()

    print("  Views materializadas criadas com sucesso.", flush=True)


if __name__ == "__main__":
    run()
