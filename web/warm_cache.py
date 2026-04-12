"""Pre-processa todas as queries para todos os municipios e salva em web_cache.

Uso:
    python -m web.warm_cache                      # processa todos uma vez
    python -m web.warm_cache --daemon              # loop infinito (recomeça ao terminar)
    python -m web.warm_cache --mun "João Pessoa"   # processa 1 municipio
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime

import psycopg2

from etl.config import DSN
from web.queries.cidade import (
    PERFIL_MUNICIPIO,
    TOP_FORNECEDORES,
    TOP_FORNECEDORES_BASIC,
    TOP_FORNECEDORES_FALLBACK,
    TOP_SERVIDORES_RISCO,
)
from web.queries.registry import CIDADE_QUERIES

CACHE_TABLE = "web_cache"

SCHEMA_DDL = f"""
CREATE TABLE IF NOT EXISTS {CACHE_TABLE} (
    query_id   TEXT NOT NULL,
    municipio  TEXT NOT NULL,
    columns    JSONB NOT NULL DEFAULT '[]',
    rows       JSONB NOT NULL DEFAULT '[]',
    row_count  INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (query_id, municipio)
);
"""

PAUSE_BETWEEN_CYCLES = 60  # seconds between full cycles in daemon mode


def _get_municipios(conn, only: str | None = None) -> list[str]:
    with conn.cursor() as cur:
        if only:
            cur.execute(
                "SELECT municipio FROM mv_municipio_pb_risco "
                "WHERE unaccent(municipio) ILIKE unaccent(%s) LIMIT 1",
                (only,),
            )
        else:
            cur.execute("SELECT municipio FROM mv_municipio_pb_risco ORDER BY municipio")
        return [r[0] for r in cur.fetchall()]


def _execute(conn, sql: str, params: dict, timeout_sec: int):
    with conn.cursor() as cur:
        cur.execute(f"SET statement_timeout = '{timeout_sec * 1000}'")
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall() if cur.description else []
        cur.execute("RESET statement_timeout")
        return cols, rows


def _upsert(cur, query_id: str, municipio: str, cols: list, rows: list):
    serializable_rows = []
    for row in rows:
        serializable_row = []
        for val in row:
            if isinstance(val, (datetime,)):
                serializable_row.append(val.isoformat())
            elif isinstance(val, list):
                serializable_row.append(val)
            else:
                serializable_row.append(val)
        serializable_rows.append(serializable_row)

    cur.execute(
        f"""
        INSERT INTO {CACHE_TABLE} (query_id, municipio, columns, rows, row_count, updated_at)
        VALUES (%s, %s, %s, %s, %s, now())
        ON CONFLICT (query_id, municipio)
        DO UPDATE SET columns = EXCLUDED.columns,
                      rows = EXCLUDED.rows,
                      row_count = EXCLUDED.row_count,
                      updated_at = now()
        """,
        (query_id, municipio, json.dumps(cols), json.dumps(serializable_rows, default=str), len(rows)),
    )


def _run_and_cache(conn, query_id: str, sql: str, mun: str, timeout_sec: int, verbose: bool):
    """Executa uma query e salva no cache. Retorna True se ok."""
    try:
        cols, rows = _execute(conn, sql, {"municipio": mun}, timeout_sec)
        conn.commit()
        with conn.cursor() as cur:
            _upsert(cur, query_id, mun, cols, rows)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        msg = str(e).split("\n")[0]
        if verbose and "statement_timeout" not in msg:
            print(f"  {query_id}: {msg}")
        return False


def warm_cycle(municipios: list[str], verbose: bool = True):
    """Processa um ciclo completo de todos os municipios."""
    conn = psycopg2.connect(DSN)
    conn.autocommit = False

    with conn.cursor() as cur:
        cur.execute(SCHEMA_DDL)
    conn.commit()

    total = len(municipios)
    all_queries = list(CIDADE_QUERIES.values())
    cycle_ok, cycle_fail = 0, 0

    for i, mun in enumerate(municipios, 1):
        t0 = time.time()
        ok, fail = 0, 0

        # Profile
        if _run_and_cache(conn, "PERFIL", PERFIL_MUNICIPIO, mun, 10, verbose):
            ok += 1
        else:
            fail += 1

        # Top fornecedores (fallback chain)
        forn_ok = False
        for sql in [TOP_FORNECEDORES, TOP_FORNECEDORES_FALLBACK, TOP_FORNECEDORES_BASIC]:
            if _run_and_cache(conn, "TOP_FORNECEDORES", sql, mun, 30, False):
                forn_ok = True
                break
        ok += 1 if forn_ok else 0
        fail += 0 if forn_ok else 1

        # Top servidores
        if _run_and_cache(conn, "TOP_SERVIDORES", TOP_SERVIDORES_RISCO, mun, 15, verbose):
            ok += 1
        else:
            fail += 1

        # Registry queries
        for qdef in all_queries:
            if _run_and_cache(conn, qdef.id, qdef.sql_full, mun, qdef.timeout_sec, verbose):
                ok += 1
            else:
                fail += 1

        cycle_ok += ok
        cycle_fail += fail
        elapsed = time.time() - t0
        if verbose:
            print(f"[{i}/{total}] {mun}: {ok} ok, {fail} fail ({elapsed:.1f}s)")

    conn.close()
    return cycle_ok, cycle_fail


def main():
    parser = argparse.ArgumentParser(description="Pre-processa queries para cache do frontend")
    parser.add_argument("--mun", type=str, default=None, help="Processar apenas um municipio")
    parser.add_argument("--daemon", action="store_true", help="Processa todos os municipios (use com --loop para repetir)")
    parser.add_argument("--loop", action="store_true", help="Recomeça automaticamente ao terminar a lista")
    args = parser.parse_args()

    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    municipios = _get_municipios(conn, args.mun)
    conn.close()

    if not municipios:
        print("Nenhum municipio encontrado.")
        sys.exit(1)

    if args.daemon:
        print(f"Daemon mode: {len(municipios)} municipios em loop continuo.")
        cycle = 0
        while True:
            cycle += 1
            print(f"\n=== Ciclo {cycle} iniciado em {datetime.now().strftime('%H:%M:%S')} ===")
            t0 = time.time()
            ok, fail = warm_cycle(municipios)
            elapsed = time.time() - t0
            print(f"=== Ciclo {cycle} completo: {ok} ok, {fail} fail ({elapsed/60:.1f}min) ===")
            if not args.loop:
                print("Ciclo unico finalizado (use --loop para repetir).")
                break
            print(f"Proximo ciclo em {PAUSE_BETWEEN_CYCLES}s...")
            time.sleep(PAUSE_BETWEEN_CYCLES)
    else:
        print(f"Processando {len(municipios)} municipios...")
        ok, fail = warm_cycle(municipios)
        print(f"Completo: {ok} ok, {fail} fail")


if __name__ == "__main__":
    main()
