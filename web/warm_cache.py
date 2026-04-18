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
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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

# Numero de municipios processados em paralelo. Cada worker abre 1 conexao PG
# propria. Mantemos baixo (2) para nao competir com os 3 workers do uvicorn
# nem saturar I/O de tabelas grandes (tce_pb_despesa, etc).
PARALLEL_WORKERS = 2

# Timeouts (segundos) usados pelo warmer. Sao MAIORES que os do frontend
# porque rodamos em background e queremos popular o cache mesmo para queries
# pesadas. Falhar aqui significa cache miss eterno no usuario final.
TIMEOUT_PERFIL_LIVE = 600     # PERFIL_MUNICIPIO_LIVE escaneia tce_pb_despesa
TIMEOUT_TOP_FORN = 900        # TOP_FORNECEDORES com sancoes/CEIS/CNEP
TIMEOUT_TOP_SERV = 600
TIMEOUT_HEATMAP = 300
TIMEOUT_REGISTRY_DEFAULT = 600  # piso para CIDADE_QUERIES no warmer

_thread_local = threading.local()


def _thread_conn():
    """Conexao psycopg2 por thread (lazy)."""
    conn = getattr(_thread_local, "conn", None)
    if conn is None or conn.closed:
        conn = psycopg2.connect(DSN)
        conn.autocommit = False
        _thread_local.conn = conn
    return conn


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
        # Sempre loga (timeout incluso) para podermos identificar queries que
        # nunca completam dentro do tempo configurado.
        if verbose:
            tag = "TIMEOUT" if "statement_timeout" in msg else "ERR"
            print(f"  [{tag}] {query_id} mun={mun}: {msg}", flush=True)
        return False


def _run_and_cache_dated(conn, query_id: str, sql: str, params: dict, timeout_sec: int, verbose: bool):
    """Executa query com params de data e salva no cache. Retorna True se ok."""
    mun = params["municipio"]
    try:
        cols, rows = _execute(conn, sql, params, timeout_sec)
        conn.commit()
        with conn.cursor() as cur:
            _upsert(cur, query_id, mun, cols, rows)
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        msg = str(e).split("\n")[0]
        if verbose:
            tag = "TIMEOUT" if "statement_timeout" in msg else "ERR"
            print(f"  [{tag}] {query_id} mun={mun}: {msg}", flush=True)
        return False


def _ensure_cache_table(conn):
    with conn.cursor() as cur:
        cur.execute(SCHEMA_DDL)
    conn.commit()


def _warm_municipio_ano(mun: str, idx: int, total: int, ano_params_base: dict, all_queries: list, verbose: bool):
    """Processa todas as variantes ANO para um municipio. Usa conn por thread."""
    conn = _thread_conn()
    t0 = time.time()
    ok, fail = 0, 0
    params = {"municipio": mun, **ano_params_base}

    if _run_and_cache_dated(conn, "ANO:PERFIL", PERFIL_MUNICIPIO_LIVE, params, TIMEOUT_PERFIL_LIVE, verbose):
        ok += 1
    else:
        fail += 1

    if _run_and_cache_dated(conn, "ANO:TOP_FORNECEDORES", TOP_FORNECEDORES_DATED, params, TIMEOUT_TOP_FORN, verbose):
        ok += 1
    else:
        fail += 1

    if _run_and_cache_dated(conn, "ANO:TOP_SERVIDORES", TOP_SERVIDORES_RISCO_DATED, params, TIMEOUT_TOP_SERV, verbose):
        ok += 1
    else:
        fail += 1

    for qdef in all_queries:
        if qdef.sql_full_dated:
            cache_timeout = max(qdef.timeout_sec, TIMEOUT_REGISTRY_DEFAULT)
            if _run_and_cache_dated(conn, f"ANO:{qdef.id}", qdef.sql_full_dated, params, cache_timeout, verbose):
                ok += 1
            else:
                fail += 1

    elapsed = time.time() - t0
    if verbose:
        print(f"[{idx}/{total}] ANO:{mun}: {ok} ok, {fail} fail ({elapsed:.1f}s)", flush=True)
    return ok, fail


def _warm_municipio_alltime(mun: str, idx: int, total: int, all_queries: list, verbose: bool):
    """Processa todas as variantes all-time para um municipio. Usa conn por thread."""
    conn = _thread_conn()
    t0 = time.time()
    ok, fail = 0, 0

    if _run_and_cache(conn, "PERFIL", PERFIL_MUNICIPIO, mun, TIMEOUT_PERFIL_LIVE, verbose):
        ok += 1
    else:
        fail += 1

    if _run_and_cache(conn, "TOP_FORNECEDORES", TOP_FORNECEDORES, mun, TIMEOUT_TOP_FORN, verbose):
        ok += 1
    else:
        fail += 1

    if _run_and_cache(conn, "TOP_SERVIDORES", TOP_SERVIDORES_RISCO, mun, TIMEOUT_TOP_SERV, verbose):
        ok += 1
    else:
        fail += 1

    if _run_and_cache(conn, "HEATMAP", HEATMAP_MENSAL, mun, TIMEOUT_HEATMAP, verbose):
        ok += 1
    else:
        fail += 1

    for qdef in all_queries:
        cache_timeout = max(qdef.timeout_sec, TIMEOUT_REGISTRY_DEFAULT)
        if _run_and_cache(conn, qdef.id, qdef.sql_full, mun, cache_timeout, verbose):
            ok += 1
        else:
            fail += 1

    elapsed = time.time() - t0
    if verbose:
        print(f"[{idx}/{total}] {mun}: {ok} ok, {fail} fail ({elapsed:.1f}s)", flush=True)
    return ok, fail


def _run_parallel(label: str, municipios: list[str], task_fn, verbose: bool, **kwargs):
    """Executa task_fn(mun, idx, total, ...) em paralelo entre municipios."""
    total = len(municipios)
    if verbose:
        print(f"--- {label}: {total} municipios (workers={PARALLEL_WORKERS}) ---", flush=True)
    cycle_ok, cycle_fail = 0, 0
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
        futs = [
            ex.submit(task_fn, mun, i, total, verbose=verbose, **kwargs)
            for i, mun in enumerate(municipios, 1)
        ]
        for f in as_completed(futs):
            try:
                ok, fail = f.result()
                cycle_ok += ok
                cycle_fail += fail
            except Exception as e:
                cycle_fail += 1
                if verbose:
                    print(f"  [WORKER ERR] {e}", flush=True)
    return cycle_ok, cycle_fail


def warm_cycle_pb(municipios: list[str], verbose: bool = True):
    """Processa um ciclo completo de todos os municipios PB (ANO primeiro, all-time depois)."""
    # Garante schema da tabela de cache em conexao dedicada (curta).
    bootstrap = psycopg2.connect(DSN)
    bootstrap.autocommit = False
    _ensure_cache_table(bootstrap)
    bootstrap.close()

    all_queries = list(CIDADE_QUERIES.values())

    # 1o loop: variantes ANO (ano atual) — prioritario porque o frontend
    # usa "ano atual" como filtro padrao, gerando mais cache hits.
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

    ano_ok, ano_fail = _run_parallel(
        f"ANO {today.year}", municipios, _warm_municipio_ano, verbose,
        ano_params_base=ano_params_base, all_queries=all_queries,
    )

    # 2o loop: variantes all-time (sem prefixo)
    all_ok, all_fail = _run_parallel(
        "ALL-TIME", municipios, _warm_municipio_alltime, verbose,
        all_queries=all_queries,
    )

    return ano_ok + all_ok, ano_fail + all_fail





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
