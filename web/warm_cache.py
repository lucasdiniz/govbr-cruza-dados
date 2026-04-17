"""Pre-processa todas as queries para todos os municipios e salva em web_cache.

Uso:
    python -m web.warm_cache                      # processa PB uma vez
    python -m web.warm_cache --daemon --loop      # loop continuo PB
    python -m web.warm_cache --mun "João Pessoa"  # processa 1 municipio PB
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
    HEATMAP_MENSAL,
    PERFIL_MUNICIPIO,
    PERFIL_MUNICIPIO_LIVE,
    TOP_FORNECEDORES,
    TOP_FORNECEDORES_DATED,
    TOP_SERVIDORES_RISCO,
    TOP_SERVIDORES_RISCO_DATED,
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


def _get_municipios_pb(conn, only: str | None = None) -> list[str]:
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


def _run_and_cache_dated(conn, query_id: str, sql: str, params: dict, timeout_sec: int, verbose: bool):
    """Executa query com params de data e salva no cache. Retorna True se ok."""
    try:
        cols, rows = _execute(conn, sql, params, timeout_sec)
        conn.commit()
        mun = params["municipio"]
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


def _ensure_cache_table(conn):
    with conn.cursor() as cur:
        cur.execute(SCHEMA_DDL)
    conn.commit()


def warm_cycle_pb(municipios: list[str], verbose: bool = True):
    """Processa um ciclo completo de todos os municipios PB."""
    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    _ensure_cache_table(conn)

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

        # Top fornecedores
        if _run_and_cache(conn, "TOP_FORNECEDORES", TOP_FORNECEDORES, mun, 90, verbose):
            ok += 1
        else:
            fail += 1

        # Top servidores
        if _run_and_cache(conn, "TOP_SERVIDORES", TOP_SERVIDORES_RISCO, mun, 30, verbose):
            ok += 1
        else:
            fail += 1

        # Heatmap mensal (empenhos por ano/mes)
        if _run_and_cache(conn, "HEATMAP", HEATMAP_MENSAL, mun, 30, verbose):
            ok += 1
        else:
            fail += 1

        # Registry queries (use higher timeout for cache warming)
        for qdef in all_queries:
            cache_timeout = max(qdef.timeout_sec, 60)
            if _run_and_cache(conn, qdef.id, qdef.sql_full, mun, cache_timeout, verbose):
                ok += 1
            else:
                fail += 1

        cycle_ok += ok
        cycle_fail += fail
        elapsed = time.time() - t0
        if verbose:
            print(f"[{i}/{total}] {mun}: {ok} ok, {fail} fail ({elapsed:.1f}s)")

    # 2o loop: variantes ANO (ano atual)
    from datetime import date as _date
    today = _date.today()
    ano_params_base = {
        "data_inicio": f"{today.year}-01-01",
        "data_fim": f"{today.year}-12-31",
        "ano_inicio": today.year,
        "ano_fim": today.year,
        "ano_mes_inicio": f"{today.year}-01",
        "ano_mes_fim": f"{today.year}-12",
    }
    if verbose:
        print(f"\n--- ANO {today.year}: {total} municipios ---")

    for i, mun in enumerate(municipios, 1):
        t0 = time.time()
        ok, fail = 0, 0
        params = {"municipio": mun, **ano_params_base}

        # PERFIL ANO
        if _run_and_cache_dated(conn, "ANO:PERFIL", PERFIL_MUNICIPIO_LIVE, params, 15, verbose):
            ok += 1
        else:
            fail += 1

        # TOP_FORNECEDORES ANO
        if _run_and_cache_dated(conn, "ANO:TOP_FORNECEDORES", TOP_FORNECEDORES_DATED, params, 90, verbose):
            ok += 1
        else:
            fail += 1

        # TOP_SERVIDORES ANO
        if _run_and_cache_dated(conn, "ANO:TOP_SERVIDORES", TOP_SERVIDORES_RISCO_DATED, params, 90, verbose):
            ok += 1
        else:
            fail += 1

        # Registry queries ANO
        for qdef in all_queries:
            if qdef.sql_full_dated:
                cache_timeout = max(qdef.timeout_sec, 60)
                if _run_and_cache_dated(conn, f"ANO:{qdef.id}", qdef.sql_full_dated, params, cache_timeout, verbose):
                    ok += 1
                else:
                    fail += 1

        cycle_ok += ok
        cycle_fail += fail
        elapsed = time.time() - t0
        if verbose:
            print(f"[{i}/{total}] ANO:{mun}: {ok} ok, {fail} fail ({elapsed:.1f}s)")

    conn.close()
    return cycle_ok, cycle_fail





def main():
    parser = argparse.ArgumentParser(description="Pre-processa queries para cache do frontend (PB)")
    parser.add_argument("--mun", type=str, default=None, help="Processar apenas um municipio")
    parser.add_argument("--daemon", action="store_true", help="Processa todos os municipios (use com --loop para repetir)")
    parser.add_argument("--loop", action="store_true", help="Recomeça automaticamente ao terminar a lista")
    parser.add_argument("--pb", action="store_true", help="(compat) Processar PB - default")
    args = parser.parse_args()

    conn = psycopg2.connect(DSN)
    conn.autocommit = True

    municipios_pb = _get_municipios_pb(conn, args.mun)
    conn.close()

    if not municipios_pb:
        print("Nenhum municipio encontrado.")
        sys.exit(1)

    def run_one_cycle(cycle_num: int | None = None):
        if cycle_num:
            print(f"\n=== Ciclo {cycle_num} iniciado em {datetime.now().strftime('%H:%M:%S')} ===")
        print(f"--- PB: {len(municipios_pb)} municipios ---")
        return warm_cycle_pb(municipios_pb)

    if args.daemon:
        print(f"Daemon mode: {len(municipios_pb)} PB municipios.")
        cycle = 0
        while True:
            cycle += 1
            t0 = time.time()
            ok, fail = run_one_cycle(cycle)
            elapsed = time.time() - t0
            print(f"=== Ciclo {cycle} completo: {ok} ok, {fail} fail ({elapsed/60:.1f}min) ===")
            if not args.loop:
                print("Ciclo unico finalizado (use --loop para repetir).")
                break
            print(f"Proximo ciclo em {PAUSE_BETWEEN_CYCLES}s...")
            time.sleep(PAUSE_BETWEEN_CYCLES)
    else:
        print(f"Processando {len(municipios_pb)} PB municipios...")
        ok, fail = run_one_cycle()
        print(f"Completo: {ok} ok, {fail} fail")


if __name__ == "__main__":
    main()
