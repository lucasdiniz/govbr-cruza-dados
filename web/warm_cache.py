"""Pre-processa todas as queries para todos os municipios e salva em web_cache.

Uso:
    python -m web.warm_cache                      # processa PB uma vez
    python -m web.warm_cache --daemon --loop      # loop continuo PB
    python -m web.warm_cache --mun "João Pessoa"  # processa 1 municipio PB
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

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
from web.kpis.cidade import compute_cidade_kpis
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
# propria. Em B4as_v2 (4 vCPU) usamos 4 para saturar o CPU.
# Em VMs menores, override via env var WARM_CACHE_WORKERS.
PARALLEL_WORKERS = int(os.getenv("WARM_CACHE_WORKERS", "4"))

# work_mem por sessao do warm. Evita disk-based sorts em queries com Sort/Hash
# pesados. Padrao do PG (em B4 16GB) eh ~124MB; 256MB cobre Sort spillover
# em queries do registry sem comprometer o uso geral do banco.
WARM_WORK_MEM = "256MB"

# Timeouts (segundos) usados pelo warmer. Sao MAIORES que os do frontend
# porque rodamos em background e queremos popular o cache mesmo para queries
# pesadas. Falhar aqui significa cache miss eterno no usuario final.
TIMEOUT_PERFIL_LIVE = 600     # PERFIL_MUNICIPIO_LIVE escaneia tce_pb_despesa
TIMEOUT_TOP_FORN = 900        # TOP_FORNECEDORES com sancoes/CEIS/CNEP
TIMEOUT_TOP_SERV = 600
TIMEOUT_HEATMAP = 300
TIMEOUT_REGISTRY_DEFAULT = 600  # piso para CIDADE_QUERIES no warmer

_thread_local = threading.local()
GMT_MINUS_3 = timezone(timedelta(hours=-3))


def _today_gmt3() -> date:
    return datetime.now(GMT_MINUS_3).date()


def _thread_conn():
    """Conexao psycopg2 por thread (lazy)."""
    conn = getattr(_thread_local, "conn", None)
    if conn is None or conn.closed:
        conn = psycopg2.connect(DSN)
        conn.autocommit = False
        # Aumenta work_mem nessa sessao especifica para evitar disk-based sorts.
        # Aplica em todas as queries do warm (PERFIL, TOP_*, registry, etc).
        with conn.cursor() as cur:
            cur.execute(f"SET work_mem = '{WARM_WORK_MEM}'")
        conn.commit()
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
            # ORDER BY tamanho/risco desc primeiro: municipios maiores levam
            # mais tempo, entao processa-los cedo da feedback de progresso
            # mais real (workers terminam rapido com os pequenos depois).
            # Tambem ajuda usuarios: as cidades mais consultadas (geralmente
            # as maiores) ficam quentes no cache antes.
            cur.execute(
                """
                SELECT r.municipio
                FROM mv_municipio_pb_risco r
                LEFT JOIN mv_municipio_pb_mapa m ON m.municipio = r.municipio
                ORDER BY COALESCE(m.total_pago_pj, 0) DESC, r.municipio
                """
            )
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


def _row_to_dict(cols, row):
    """Converte row do DB para dict, normalizando Decimal/date para JSON."""
    d = {}
    for c, v in zip(cols, row):
        if hasattr(v, "as_tuple"):  # Decimal
            d[c] = float(v)
        elif hasattr(v, "isoformat"):  # date/datetime
            d[c] = v.isoformat()
        else:
            d[c] = v
    return d


def _read_cache(conn, query_id: str, mun: str):
    """Le do web_cache. Retorna (cols, rows) ou None."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT columns, rows FROM {CACHE_TABLE} WHERE query_id=%s AND municipio=%s",
            (query_id, mun),
        )
        row = cur.fetchone()
    if not row:
        return None
    cols, rows = row
    if isinstance(cols, str):
        cols = json.loads(cols)
    if isinstance(rows, str):
        rows = json.loads(rows)
    return cols, rows


def _compute_and_cache_kpi_summary(conn, mun: str, periodo: str, verbose: bool):
    """Computa o KPI_SUMMARY a partir das listas ja cacheadas (PERFIL/TOP_FORN/TOP_SERV)
    e salva como JSON em uma unica linha {payload: {...}}.

    periodo='' -> all-time (chaves PERFIL, TOP_FORNECEDORES, TOP_SERVIDORES);
    periodo='ANO'/'12M' -> chaves prefixadas equivalentes.
    """
    prefix = f"{periodo}:" if periodo else ""
    qid = f"{prefix}KPI_SUMMARY"
    try:
        perfil_cache = _read_cache(conn, f"{prefix}PERFIL", mun)
        forn_cache = _read_cache(conn, f"{prefix}TOP_FORNECEDORES", mun)
        serv_cache = _read_cache(conn, f"{prefix}TOP_SERVIDORES", mun)
        perfil = {}
        if perfil_cache and perfil_cache[1]:
            perfil = _row_to_dict(perfil_cache[0], perfil_cache[1][0])
        fornecedores = []
        if forn_cache:
            fcols, frows = forn_cache
            fornecedores = [_row_to_dict(fcols, r) for r in frows]
        servidores = []
        if serv_cache:
            scols, srows = serv_cache
            servidores = [_row_to_dict(scols, r) for r in srows]
        summary = compute_cidade_kpis(perfil, fornecedores, servidores)
        with conn.cursor() as cur:
            _upsert(cur, qid, mun, ["payload"], [[json.dumps(summary, default=str)]])
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        if verbose:
            print(f"  [ERR] {qid} mun={mun}: {str(e).split(chr(10))[0]}", flush=True)
        return False


def _ensure_cache_table(conn):
    with conn.cursor() as cur:
        cur.execute(SCHEMA_DDL)
    conn.commit()


def _run_query_for_muni(query_id: str, sql: str, mun: str, extra_params: dict | None, timeout_sec: int):
    """Executa uma query para 1 muni e cacheia. Retorna (ok, msg|None).

    Usado pelo loop invertido (1 query × N munis em paralelo). Por design,
    nao printa nada — o caller agrega resultados e decide o que logar.
    """
    conn = _thread_conn()
    if extra_params:
        params = {**extra_params, "municipio": mun}
    else:
        params = {"municipio": mun}
    try:
        cols, rows = _execute(conn, sql, params, timeout_sec)
        conn.commit()
        with conn.cursor() as cur:
            _upsert(cur, query_id, mun, cols, rows)
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        msg = str(e).split("\n")[0]
        return False, msg


def _warm_query_across_munis(query_id: str, sql: str, municipios: list[str],
                              extra_params: dict | None, timeout: int, verbose: bool):
    """Executa uma unica query para TODOS os municipios em paralelo.

    Inversao do loop original (que era muni->query). Aqui rodamos query->muni:
    apos a primeira muni, os indexes/tables relevantes ficam quentes no
    shared_buffers/host cache, beneficiando as munis seguintes.
    """
    total = len(municipios)
    ok = fail = 0
    timeouts = 0
    t0 = time.time()

    def task(mun):
        return _run_query_for_muni(query_id, sql, mun, extra_params, timeout)

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
        for success, msg in ex.map(task, municipios):
            if success:
                ok += 1
            else:
                fail += 1
                if msg and "statement_timeout" in msg:
                    timeouts += 1

    elapsed = time.time() - t0
    if verbose:
        rate = total / elapsed if elapsed > 0 else 0
        suffix = f" ({timeouts} timeouts)" if timeouts else ""
        print(
            f"  {query_id}: {ok}/{total} ok, {fail} fail{suffix} "
            f"({elapsed:.0f}s, {rate:.1f}/s)",
            flush=True,
        )
    return ok, fail


def _warm_kpi_summary_across_munis(municipios: list[str], periodo: str, verbose: bool):
    """Computa KPI_SUMMARY para todos os munis em paralelo. Depende de
    PERFIL/TOP_FORN/TOP_SERV ja cacheados para o periodo."""
    total = len(municipios)
    ok = fail = 0
    t0 = time.time()
    qid = f"{periodo}:KPI_SUMMARY" if periodo else "KPI_SUMMARY"

    def task(mun):
        conn = _thread_conn()
        return _compute_and_cache_kpi_summary(conn, mun, periodo, verbose=False)

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
        for result in ex.map(task, municipios):
            if result:
                ok += 1
            else:
                fail += 1

    elapsed = time.time() - t0
    if verbose:
        print(f"  {qid}: {ok}/{total} ok, {fail} fail ({elapsed:.0f}s)", flush=True)
    return ok, fail


def _warm_phase(phase_name: str, municipios: list[str], all_queries: list,
                extra_params: dict | None, verbose: bool):
    """Roda um ciclo completo para uma fase (ANO/12M/ALL-TIME) com loop
    invertido: cada query roda contra todos os munis em paralelo, em ordem
    de dependencia (PERFIL/TOP_* primeiro, depois KPI_SUMMARY, depois
    HEATMAP, depois queries do registry).

    Beneficios vs loop original (muni->query):
    - Cache locality: indexes/tables consultadas pela query ficam quentes
      no shared_buffers/host cache apos a primeira muni; demais munis se
      beneficiam.
    - Plan caching: postgres pode reusar o plano executado para uma muni
      ao executar a mesma query (com municipio diferente) na proxima.
    - Progresso visivel: cada query tem seu proprio summary timing.
    """
    is_dated = bool(extra_params)
    prefix = f"{phase_name}:" if phase_name else ""
    label = phase_name or "ALL-TIME"
    if verbose:
        print(f"\n--- {label}: {len(municipios)} munis, "
              f"workers={PARALLEL_WORKERS} (loop invertido) ---", flush=True)

    cycle_ok = cycle_fail = 0

    # 1. PERFIL — alimenta KPI_SUMMARY (dependencia)
    perfil_sql = PERFIL_MUNICIPIO_LIVE if is_dated else PERFIL_MUNICIPIO
    ok, fail = _warm_query_across_munis(
        f"{prefix}PERFIL", perfil_sql, municipios, extra_params, TIMEOUT_PERFIL_LIVE, verbose,
    )
    cycle_ok += ok
    cycle_fail += fail

    # 2. TOP_FORNECEDORES — alimenta KPI_SUMMARY
    forn_sql = TOP_FORNECEDORES_DATED if is_dated else TOP_FORNECEDORES
    ok, fail = _warm_query_across_munis(
        f"{prefix}TOP_FORNECEDORES", forn_sql, municipios, extra_params, TIMEOUT_TOP_FORN, verbose,
    )
    cycle_ok += ok
    cycle_fail += fail

    # 3. TOP_SERVIDORES — alimenta KPI_SUMMARY
    serv_sql = TOP_SERVIDORES_RISCO_DATED if is_dated else TOP_SERVIDORES_RISCO
    ok, fail = _warm_query_across_munis(
        f"{prefix}TOP_SERVIDORES", serv_sql, municipios, extra_params, TIMEOUT_TOP_SERV, verbose,
    )
    cycle_ok += ok
    cycle_fail += fail

    # 4. KPI_SUMMARY — depende dos 3 acima
    ok, fail = _warm_kpi_summary_across_munis(municipios, phase_name, verbose)
    cycle_ok += ok
    cycle_fail += fail

    # 5. HEATMAP — apenas all-time
    if not is_dated:
        ok, fail = _warm_query_across_munis(
            "HEATMAP", HEATMAP_MENSAL, municipios, None, TIMEOUT_HEATMAP, verbose,
        )
        cycle_ok += ok
        cycle_fail += fail

    # 6. Queries do registry (Q01-Q310). Cada uma roda contra todos os munis.
    for qdef in all_queries:
        if is_dated:
            sql = qdef.sql_full_dated
            if not sql:
                continue  # registry permite query sem variante dated
        else:
            sql = qdef.sql_full
        cache_timeout = max(qdef.timeout_sec, TIMEOUT_REGISTRY_DEFAULT)
        ok, fail = _warm_query_across_munis(
            f"{prefix}{qdef.id}", sql, municipios, extra_params, cache_timeout, verbose,
        )
        cycle_ok += ok
        cycle_fail += fail

    return cycle_ok, cycle_fail


def warm_cycle_pb(municipios: list[str], verbose: bool = True):
    """Processa um ciclo completo com loop invertido (query->muni).

    Estrategia: para cada fase (ANO, 12M, all-time), iteramos QUERIES e
    paralelizamos sobre munis. Isso melhora cache locality vs o loop
    original (muni->query) — apos a primeira muni, indexes/tables
    relevantes ja estao quentes no shared_buffers/host cache.
    """
    # Garante schema da tabela de cache em conexao dedicada (curta).
    bootstrap = psycopg2.connect(DSN)
    bootstrap.autocommit = False
    _ensure_cache_table(bootstrap)
    bootstrap.close()

    all_queries = list(CIDADE_QUERIES.values())

    today = _today_gmt3()
    ano_params_base = {
        "data_inicio": f"{today.year}-01-01",
        "data_fim": today.isoformat(),
        "ano_inicio": today.year,
        "ano_fim": today.year,
        "ano_mes_inicio": f"{today.year}-01",
        "ano_mes_fim": today.strftime("%Y-%m"),
    }
    try:
        inicio_12m = today.replace(year=today.year - 1) + timedelta(days=1)
    except ValueError:
        inicio_12m = date(today.year - 1, 3, 1)
    params_12m_base = {
        "data_inicio": inicio_12m.isoformat(),
        "data_fim": today.isoformat(),
        "ano_inicio": inicio_12m.year,
        "ano_fim": today.year,
        "ano_mes_inicio": inicio_12m.strftime("%Y-%m"),
        "ano_mes_fim": today.strftime("%Y-%m"),
    }

    # Fase 1: ANO atual — prioritario porque o frontend usa "ano atual" como
    # filtro padrao, gerando mais cache hits.
    ano_ok, ano_fail = _warm_phase(
        f"ANO {today.year}", municipios, all_queries, ano_params_base, verbose,
    )

    # Fase 2: ultimos 12 meses, usado pelo preset frequente do frontend.
    m12_ok, m12_fail = _warm_phase(
        "12M", municipios, all_queries, params_12m_base, verbose,
    )

    # Fase 3: all-time (sem prefixo, sem params de data).
    all_ok, all_fail = _warm_phase(
        "", municipios, all_queries, None, verbose,
    )

    return ano_ok + m12_ok + all_ok, ano_fail + m12_fail + all_fail





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
        last_fail_pct = 0.0
        while True:
            cycle += 1
            t0 = time.time()
            ok, fail = run_one_cycle(cycle)
            elapsed = time.time() - t0
            total = ok + fail
            last_fail_pct = (fail / total * 100) if total > 0 else 0.0
            print(
                f"=== Ciclo {cycle} completo: {ok} ok, {fail} fail "
                f"({last_fail_pct:.1f}%, {elapsed/60:.1f}min) ==="
            )
            if not args.loop:
                print("Ciclo unico finalizado (use --loop para repetir).")
                break
            print(f"Proximo ciclo em {PAUSE_BETWEEN_CYCLES}s...")
            time.sleep(PAUSE_BETWEEN_CYCLES)

        # Falha o processo se taxa de falha >5% em ciclo unico (--daemon sem --loop).
        # Isso permite ao deploy.yml detectar warm parcial e nao mascarar como sucesso.
        # Em modo --loop nao falhamos: o intuito eh continuar tentando.
        if not args.loop and last_fail_pct > 5.0:
            print(
                f"ERRO: taxa de falha {last_fail_pct:.1f}% > 5% — exit 1",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        print(f"Processando {len(municipios_pb)} PB municipios...")
        ok, fail = run_one_cycle()
        total = ok + fail
        fail_pct = (fail / total * 100) if total > 0 else 0.0
        print(f"Completo: {ok} ok, {fail} fail ({fail_pct:.1f}%)")
        if fail_pct > 5.0:
            print(f"ERRO: taxa de falha {fail_pct:.1f}% > 5% — exit 1", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
