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
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from web.queries.empresa import (
    EMPRESAS_MUNICIPIOS_QUALIFICADAS_TODOS,
    EMPRESAS_QUALIFICADAS_PARA_SITEMAP,
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
# pesados. Padrao do PG (em B4 16GB) eh ~124MB.
# 192MB = compromisso entre acelerar Sort e nao saturar memoria com 4 workers
# rodando simultaneamente (4 workers * 3 sort ops * 192MB = ~2.3GB peak).
# Nota: psycopg2 nao suporta SET LOCAL fora de transacao explicita; SET
# session-level afeta apenas as conexoes abertas pelo warm (nao o postgres
# como um todo). cruza-web abre suas proprias conexoes e nao eh afetado.
WARM_WORK_MEM = "192MB"

# Resume mode: pula queries cacheadas ha menos de N horas.
# Usado quando os DADOS nao mudaram (ex: etl_phase=web warm_cache=true).
# 0 = sem skip (rebuild completo), tipico apos ETL/SQL que recriou MVs.
# 24 = pula tudo cacheado nas ultimas 24h (resume de warm interrompido).
# Configurado via env var pelo deploy.yml conforme etl_phase.
SKIP_RECENT_HOURS = int(os.getenv("WARM_SKIP_RECENT_HOURS", "0"))

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
                "WHERE municipio IS NOT NULL "
                "  AND unaccent(municipio) ILIKE unaccent(%s) LIMIT 1",
                (only,),
            )
        else:
            # ORDER BY tamanho/risco desc primeiro: municipios maiores levam
            # mais tempo, entao processa-los cedo da feedback de progresso
            # mais real (workers terminam rapido com os pequenos depois).
            # Tambem ajuda usuarios: as cidades mais consultadas (geralmente
            # as maiores) ficam quentes no cache antes.
            # WHERE municipio IS NOT NULL exclui 1 row "fantasma" presente
            # nas MVs por dados ruins na origem (tce_pb_despesa). Sem isso,
            # o warm tenta inserir muni=None no web_cache e leva NOT NULL
            # constraint violation. Causa raiz das MVs deve ser tratada em
            # outro PR (TODO #12).
            cur.execute(
                """
                SELECT r.municipio
                FROM mv_municipio_pb_risco r
                LEFT JOIN mv_municipio_pb_mapa m ON m.municipio = r.municipio
                WHERE r.municipio IS NOT NULL
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
        # score_canonical = mv_municipio_pb_kpi_score.risco_score_unificado, mesmo
        # valor exibido no mapa coropletico. Eh uma metrica all-time da reputacao
        # do municipio, period-independent. Para periodos ANO/12M, o PERFIL local
        # tem risco_score=NULL (PERFIL_MUNICIPIO_LIVE forca NULL), entao buscamos
        # do PERFIL all-time (cache sem prefix). Garante que a "Nota de atencao"
        # bate 1:1 com o mapa em todos os filtros temporais.
        score_canonical = perfil.get("risco_score") if not prefix else None
        if score_canonical is None and prefix:
            alltime_perfil_cache = _read_cache(conn, "PERFIL", mun)
            if alltime_perfil_cache and alltime_perfil_cache[1]:
                alltime_perfil = _row_to_dict(alltime_perfil_cache[0], alltime_perfil_cache[1][0])
                score_canonical = alltime_perfil.get("risco_score")
        summary["score_canonical"] = score_canonical
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


def _filter_cached_munis(query_id: str, municipios: list[str]) -> tuple[list[str], int]:
    """Em resume mode (SKIP_RECENT_HOURS > 0), remove munis cujo cache para
    `query_id` foi atualizado nas ultimas SKIP_RECENT_HOURS horas.

    Returns (munis_to_process, num_skipped).
    """
    if SKIP_RECENT_HOURS <= 0:
        return municipios, 0

    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT municipio FROM {CACHE_TABLE} "
                f"WHERE query_id = %s AND updated_at > now() - interval %s",
                (query_id, f"{SKIP_RECENT_HOURS} hours"),
            )
            cached = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()

    if not cached:
        return municipios, 0
    remaining = [m for m in municipios if m not in cached]
    return remaining, len(municipios) - len(remaining)


def _warm_query_across_munis(query_id: str, sql: str, municipios: list[str],
                              extra_params: dict | None, timeout: int, verbose: bool):
    """Executa uma unica query para TODOS os municipios em paralelo.

    Inversao do loop original (que era muni->query). Aqui rodamos query->muni:
    apos a primeira muni, os indexes/tables relevantes ficam quentes no
    shared_buffers/host cache, beneficiando as munis seguintes.

    Em resume mode (SKIP_RECENT_HOURS > 0), pula munis ja cacheados
    recentemente para essa query.
    """
    original_total = len(municipios)
    municipios, skipped = _filter_cached_munis(query_id, municipios)
    if not municipios:
        if verbose:
            print(f"  {query_id}: skipped {skipped}/{original_total} (resume mode)", flush=True)
        return skipped, 0  # contam como ok porque ja estao cacheados

    total = len(municipios)
    ok = fail = 0
    timeouts = 0
    failed_munis: list[tuple[str, str]] = []
    t0 = time.time()

    # Reportar progresso a cada ~10% completado (minimo a cada 1 muni). Da
    # heartbeat + ETA durante queries longas (PERFIL ~47min, TOP_FORN ~13min)
    # ao inves de silencio total ate o sumario final.
    progress_step = max(1, total // 10)
    next_progress = progress_step
    completed = 0

    def task(mun):
        return mun, _run_query_for_muni(query_id, sql, mun, extra_params, timeout)

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
        futures = [ex.submit(task, mun) for mun in municipios]
        # as_completed iterada apenas pela thread principal -> sem lock
        # necessario nos contadores (ok/fail/completed sao mutados aqui).
        for fut in as_completed(futures):
            mun, (success, msg) = fut.result()
            completed += 1
            if success:
                ok += 1
            else:
                fail += 1
                if msg and "statement_timeout" in msg:
                    timeouts += 1
                failed_munis.append((mun, msg or ""))

            if verbose and completed >= next_progress and completed < total:
                elapsed = time.time() - t0
                rate = completed / elapsed if elapsed > 0 else 0
                pct = 100.0 * completed / total
                eta_sec = (total - completed) / rate if rate > 0 else 0
                print(
                    f"  {query_id}: {completed}/{total} ({pct:.0f}%) "
                    f"[{rate:.1f}/s, ETA {eta_sec:.0f}s, {fail} fail]",
                    flush=True,
                )
                next_progress += progress_step

    elapsed = time.time() - t0
    if verbose:
        rate = total / elapsed if elapsed > 0 else 0
        suffix = f" ({timeouts} timeouts)" if timeouts else ""
        skip_msg = f", {skipped} skipped" if skipped else ""
        print(
            f"  {query_id}: {ok}/{total} ok, {fail} fail{suffix}{skip_msg} "
            f"({elapsed:.0f}s, {rate:.1f}/s)",
            flush=True,
        )
        # Lista munis que falharam (ate 10) com mensagem truncada — facilita
        # diagnostico sem ter que ir ao journalctl filtrar por "ERROR".
        if failed_munis:
            shown = failed_munis[:10]
            for mun_failed, msg in shown:
                short_msg = (msg[:100] or "<no message>").replace("\n", " ")
                print(f"    FAIL {query_id} {mun_failed}: {short_msg}", flush=True)
            if len(failed_munis) > 10:
                print(f"    ... +{len(failed_munis) - 10} outras falhas (ver journal)", flush=True)
    # Skipped contam como ok no agregado: ja estao cacheados.
    return ok + skipped, fail


def _warm_kpi_summary_across_munis(municipios: list[str], periodo: str, verbose: bool):
    """Computa KPI_SUMMARY para todos os munis em paralelo. Depende de
    PERFIL/TOP_FORN/TOP_SERV ja cacheados para o periodo."""
    qid = f"{periodo}:KPI_SUMMARY" if periodo else "KPI_SUMMARY"
    original_total = len(municipios)
    municipios, skipped = _filter_cached_munis(qid, municipios)
    if not municipios:
        if verbose:
            print(f"  {qid}: skipped {skipped}/{original_total} (resume mode)", flush=True)
        return skipped, 0

    total = len(municipios)
    ok = fail = 0
    failed_munis: list[str] = []
    t0 = time.time()

    progress_step = max(1, total // 10)
    next_progress = progress_step
    completed = 0

    def task(mun):
        conn = _thread_conn()
        return mun, _compute_and_cache_kpi_summary(conn, mun, periodo, verbose=False)

    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
        futures = [ex.submit(task, mun) for mun in municipios]
        for fut in as_completed(futures):
            mun, result = fut.result()
            completed += 1
            if result:
                ok += 1
            else:
                fail += 1
                failed_munis.append(mun)

            if verbose and completed >= next_progress and completed < total:
                elapsed = time.time() - t0
                rate = completed / elapsed if elapsed > 0 else 0
                pct = 100.0 * completed / total
                eta_sec = (total - completed) / rate if rate > 0 else 0
                print(
                    f"  {qid}: {completed}/{total} ({pct:.0f}%) "
                    f"[{rate:.1f}/s, ETA {eta_sec:.0f}s, {fail} fail]",
                    flush=True,
                )
                next_progress += progress_step

    elapsed = time.time() - t0
    if verbose:
        skip_msg = f", {skipped} skipped" if skipped else ""
        print(f"  {qid}: {ok}/{total} ok, {fail} fail{skip_msg} ({elapsed:.0f}s)", flush=True)
        if failed_munis:
            shown = failed_munis[:10]
            for mun_failed in shown:
                print(f"    FAIL {qid} {mun_failed}", flush=True)
            if len(failed_munis) > 10:
                print(f"    ... +{len(failed_munis) - 10} outras falhas", flush=True)
    return ok + skipped, fail


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
        # Em ANO/12M, mostrar o range efetivo nos logs ja que o prefix
        # nao carrega mais o ano (precisa bater com ANO: lido pelo frontend).
        range_info = ""
        if extra_params:
            range_info = f" (ano_inicio={extra_params.get('ano_inicio')}, ano_fim={extra_params.get('ano_fim')})"
        print(f"\n--- {label}{range_info}: {len(municipios)} munis, "
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
    # IMPORTANTE: usar prefix "ANO" (sem ano), porque eh o que o frontend espera
    # ler em web/db.py e web/routes/cidade.py. O ano em si vai nos params.
    ano_ok, ano_fail = _warm_phase(
        "ANO", municipios, all_queries, ano_params_base, verbose,
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


# ─────────────────────────────────────────────────────────────────────────
# Empresa warmer — pre-computa o dict completo de cada /empresa/<cnpj>.
# Necessario porque a rota e CACHE-ONLY (cache miss = 503) pra evitar
# thundering herd quando crawlers acessam 45K URLs.
#
# Storage no web_cache:
#   query_id = "EMPRESA_PERFIL"
#   municipio = cnpj_completo (14 digitos numericos)
#   columns = ["payload"]
#   rows = [[<dict_serializado_como_json>]]
#
# Read pela rota:
#   read_web_cache("EMPRESA_PERFIL", cnpj) -> rows[0][0] = dict
# ─────────────────────────────────────────────────────────────────────────


def _get_qualifying_empresas(conn) -> list[str]:
    """Lista cnpj_completo (14 digits) das empresas qualificadas.

    Usa EMPRESAS_QUALIFICADAS_PARA_SITEMAP de web.queries.empresa que retorna
    TODAS as empresas em mv_empresa_pb com matriz cadastrada em
    estabelecimento (cnpj_ordem='0001'). Sem LIMIT — warmer cacheia tudo
    pra cobertura total do sitemap-index.
    """
    with conn.cursor() as cur:
        cur.execute(EMPRESAS_QUALIFICADAS_PARA_SITEMAP)
        rows = cur.fetchall()
    out = []
    seen = set()
    for _razao, cnpj_completo in rows:
        if not cnpj_completo:
            continue
        cnpj_str = str(cnpj_completo).strip()
        if len(cnpj_str) != 14 or not cnpj_str.isdigit():
            continue
        if cnpj_str in seen:
            continue
        seen.add(cnpj_str)
        out.append(cnpj_str)
    return out


def _warm_one_empresa(cnpj_completo: str) -> tuple[bool, str | None]:
    """Computa o perfil de uma empresa e armazena em web_cache.

    Retorna (ok, mensagem_de_erro_ou_None). Cada chamada abre conexao
    propria (thread-safe via _thread_conn).
    """
    # Import diferido pra evitar ciclo na inicializacao do modulo
    # (web.routes.empresa importa web.db que importa etl.config).
    from web.config import TIMEOUT_PROFILE_WARM
    from web.routes.empresa import (
        CACHE_QUERY_ID as EMPRESA_CACHE_QID,
        EmpresaNotFoundError,
        compute_empresa_perfil_dict,
    )

    try:
        # timeout_sec=120 cobre mega-empresas governamentais (BB,
        # Caixa, INSS) com milhoes de empenhos. TIMEOUT_PROFILE=3s do
        # frontend nao se aplica aqui (warmer roda offline).
        data = compute_empresa_perfil_dict(
            cnpj_completo, timeout_sec=TIMEOUT_PROFILE_WARM
        )
    except EmpresaNotFoundError as e:
        # Empresa sem dados PB — nao deve estar no sitemap qualificado,
        # mas pode acontecer se mv_empresa_pb e estabelecimento divergem.
        # Skip silencioso (nao caching, nao erro fatal).
        return False, f"not_found:{e}"
    except Exception as e:
        return False, f"compute_failed:{str(e).splitlines()[0]}"

    # Passamos o dict CRU pra _upsert. Ele faz UM `json.dumps(rows, default=str)`
    # que serializa os valores aninhados (dict, list, datetime) em JSONB
    # corretamente. Ao ler com read_web_cache, psycopg2 desserializa o JSONB
    # de volta pra Python — `rows[0][0]` retorna o dict.
    #
    # NAO fazer json.dumps aqui antes de _upsert: dupla-serializacao gera
    # string JSON aninhada (o que JSONB armazena seria '[["{...}"]]', com
    # o objeto como string, nao dict). Resultado: toda leitura volta str em
    # vez de dict, isinstance(data, dict) falha, rota cai pra 503 mesmo com
    # cache "popular". Bug pego pelo Opus 4.7 review do PR #58 (P0).
    try:
        conn = _thread_conn()
        with conn.cursor() as cur:
            _upsert(
                cur,
                EMPRESA_CACHE_QID,
                cnpj_completo,
                ["payload"],
                [[data]],
            )
        conn.commit()
    except Exception as e:
        try:
            _thread_conn().rollback()
        except Exception:
            pass
        return False, f"cache_write_failed:{str(e).splitlines()[0]}"
    return True, None


def warm_cycle_empresas(cnpjs: list[str], verbose: bool = True) -> tuple[int, int, int]:
    """Processa empresas em paralelo. Cada falha eh logada mas nao aborta.

    Args:
        cnpjs: lista de 14-digit CNPJ completo. Resume mode (via env
            WARM_SKIP_RECENT_HOURS) ja foi aplicado pelo caller via
            _filter_cached_munis(query_id="EMPRESA_PERFIL", ...).
        verbose: log progresso a cada 200 processadas.

    Returns: (ok, fail, skipped_not_found)
        - ok: dict computado e cacheado com sucesso.
        - fail: erro real (compute exception, cache write fail).
        - skipped_not_found: empresa qualificada no sitemap mas sem
          cadastro RFB (mv_empresa_pb e estabelecimento divergem).
          Conta separado pra nao inflar threshold de falha.
    """
    bootstrap = psycopg2.connect(DSN)
    bootstrap.autocommit = False
    _ensure_cache_table(bootstrap)
    bootstrap.close()

    total = len(cnpjs)
    if total == 0:
        return 0, 0, 0
    print(
        f"[empresas] Warming {total} empresas em {PARALLEL_WORKERS} workers...",
        flush=True,
    )

    ok = 0
    fail = 0
    skipped = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
        futures = {ex.submit(_warm_one_empresa, c): c for c in cnpjs}
        done = 0
        for fut in as_completed(futures):
            done += 1
            cnpj = futures[fut]
            try:
                success, msg = fut.result()
            except Exception as e:
                success = False
                msg = f"future_exception:{e}"
            if success:
                ok += 1
            elif msg and msg.startswith("not_found:"):
                # Empresa no sitemap mas sem cadastro RFB. Esperado em
                # ETL stale; nao conta como fail no threshold.
                skipped += 1
            else:
                fail += 1
                if verbose and msg:
                    print(f"  [ERR] {cnpj}: {msg}", flush=True)
            if verbose and done % 200 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                print(
                    f"[empresas] {done}/{total} "
                    f"({ok} ok, {fail} fail, {skipped} skipped) — "
                    f"{rate:.1f}/s, eta {eta/60:.1f}min",
                    flush=True,
                )
    elapsed = time.time() - t0
    print(
        f"[empresas] Completo: {ok} ok, {fail} fail, {skipped} skipped "
        f"({elapsed/60:.1f}min)",
        flush=True,
    )
    return ok, fail, skipped





def main():
    parser = argparse.ArgumentParser(description="Pre-processa queries para cache do frontend (PB) — cidades + empresas")
    parser.add_argument("--mun", type=str, default=None, help="Processar apenas um municipio (skip empresas)")
    parser.add_argument("--daemon", action="store_true", help="Processa todos os municipios (use com --loop para repetir)")
    parser.add_argument("--loop", action="store_true", help="Recomeça automaticamente ao terminar a lista (skip empresas)")
    parser.add_argument("--pb", action="store_true", help="(compat) Processar PB - default")
    parser.add_argument(
        "--skip-empresas",
        action="store_true",
        help=(
            "Pula warming de empresas. Default: processa cidades + empresas em sequencia. "
            "Use com --mun ou --loop (que ja sao escopados a cidades)."
        ),
    )
    args = parser.parse_args()

    conn = psycopg2.connect(DSN)
    conn.autocommit = True

    municipios_pb = _get_municipios_pb(conn, args.mun)
    conn.close()

    if not municipios_pb:
        print("Nenhum municipio encontrado.")
        sys.exit(1)

    # Empresas seguem o mesmo fluxo de warm: resume mode (skip cacheados
    # nas ultimas WARM_SKIP_RECENT_HOURS), threshold combinado com cidades,
    # invalidate_cache_keys via deploy.yml usando 'EMPRESA_PERFIL'.
    # Skip se: (a) --mun (foco numa cidade especifica), (b) --loop (daemon
    # contnuo, empresas ja warmadas no primeiro ciclo), (c) --skip-empresas.
    skip_empresas_flag = bool(args.mun) or args.loop or args.skip_empresas

    def run_one_cycle(cycle_num: int | None = None):
        if cycle_num:
            print(f"\n=== Ciclo {cycle_num} iniciado em {datetime.now().strftime('%H:%M:%S')} ===")
        print(f"--- PB: {len(municipios_pb)} municipios ---")
        ok_p, fail_p = warm_cycle_pb(municipios_pb)
        ok_e = fail_e = skip_e = 0
        ok_em = fail_em = skip_em = 0
        if not skip_empresas_flag:
            ok_e, fail_e, skip_e = _warm_empresas_phase()
            ok_em, fail_em, skip_em = _warm_empresas_municipios_phase()
        return ok_p + ok_e + ok_em, fail_p + fail_e + fail_em, skip_e + skip_em

    if args.daemon:
        print(f"Daemon mode: {len(municipios_pb)} PB municipios.")
        cycle = 0
        last_fail_pct = 0.0
        while True:
            cycle += 1
            t0 = time.time()
            ok, fail, skipped = run_one_cycle(cycle)
            elapsed = time.time() - t0
            total = ok + fail
            last_fail_pct = (fail / total * 100) if total > 0 else 0.0
            print(
                f"=== Ciclo {cycle} completo: {ok} ok, {fail} fail, {skipped} skipped "
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
        ok, fail, skipped = run_one_cycle()
        total = ok + fail
        fail_pct = (fail / total * 100) if total > 0 else 0.0
        print(f"Completo: {ok} ok, {fail} fail, {skipped} skipped ({fail_pct:.1f}%)")
        if fail_pct > 5.0:
            print(f"ERRO: taxa de falha {fail_pct:.1f}% > 5% — exit 1", file=sys.stderr)
            sys.exit(1)


def _warm_empresas_phase() -> tuple[int, int, int]:
    """Fase de warming de empresas, integrada com cidades.

    Aplica resume mode (WARM_SKIP_RECENT_HOURS) via _filter_cached_munis
    com query_id='EMPRESA_PERFIL'. Inicializa pool DB explicitamente porque
    compute_empresa_perfil_dict() usa execute_query/get_conn que dependem
    de _pool inicializado (em runtime via FastAPI lifespan).

    Returns: (ok, fail, skipped) — somam aos contadores de cidades pra
    threshold global de 5% no main().
    """
    print("--- Empresas: enumerando qualificadas ---")
    boot = psycopg2.connect(DSN)
    boot.autocommit = True
    try:
        all_cnpjs = _get_qualifying_empresas(boot)
    finally:
        boot.close()

    if not all_cnpjs:
        print(
            "[empresas] Nenhuma empresa qualificada (mv_empresa_pb vazia ou "
            "filtro >=10k/CEIS/PGFN nao matchou). Skipping."
        )
        return 0, 0, 0

    # Resume mode: skip CNPJs cacheados nas ultimas WARM_SKIP_RECENT_HOURS.
    # Mesma logica de cidades — reusa _filter_cached_munis (generico em
    # query_id e lista de keys).
    cnpjs, skipped_resume = _filter_cached_munis(
        "EMPRESA_PERFIL", all_cnpjs
    )
    if skipped_resume > 0:
        print(
            f"[empresas] Resume mode: {skipped_resume} ja cacheadas nas "
            f"ultimas {SKIP_RECENT_HOURS}h, processando {len(cnpjs)} restantes."
        )

    if not cnpjs:
        return 0, 0, skipped_resume

    # web.routes.empresa.compute_empresa_perfil_dict usa execute_query/
    # get_conn de web/db.py. Pool precisa ser inicializado explicitamente
    # — em runtime web/main.py:lifespan inicializa, mas no warmer (CLI
    # standalone) nao tem lifespan.
    from web import db as web_db

    web_db.init_pool()
    try:
        ok, fail, skip_nf = warm_cycle_empresas(cnpjs)
    finally:
        try:
            web_db.close_pool()
        except Exception:
            pass

    # skip_resume eh tambem skipped (nao foi processado nesse ciclo).
    # Soma com skip_nf pra reportagem completa.
    return ok, fail, skipped_resume + skip_nf


# ─────────────────────────────────────────────────────────────────────────
# Empresa x Municipio warmer — pre-computa /empresa/<cnpj>/<slug>.
# Mesma estrategia de cache-only do /empresa/<cnpj>: cache miss = 503.
#
# Storage no web_cache:
#   query_id = "EMPRESA_PERFIL_MUN"
#   municipio = f"{cnpj_completo}:{slug}" (key composta)
#   columns = ["payload"]
#   rows = [[<dict_serializado_como_json>]]
# ─────────────────────────────────────────────────────────────────────────


def _get_qualifying_empresas_municipios(conn) -> list[tuple[str, str]]:
    """Lista pares (cnpj_completo, municipio_nome) das empresas qualificadas
    em cada municipio onde tem pagamentos. Usa a mesma query do sitemap."""
    with conn.cursor() as cur:
        cur.execute(EMPRESAS_MUNICIPIOS_QUALIFICADAS_TODOS)
        rows = cur.fetchall()
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for cnpj_completo, municipio in rows:
        if not cnpj_completo or not municipio:
            continue
        cnpj_str = str(cnpj_completo).strip()
        if len(cnpj_str) != 14 or not cnpj_str.isdigit():
            continue
        mun = str(municipio).strip()
        if not mun:
            continue
        key = (cnpj_str, mun)
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _warm_one_empresa_municipio(par: tuple[str, str]) -> tuple[bool, str | None]:
    """Computa o perfil de uma empresa em um municipio especifico e armazena
    em web_cache. par = (cnpj_completo, municipio_nome).

    OTIMIZACAO: reusa cache global EMPRESA_PERFIL:<cnpj> pra cadastrais
    (estabelecimento, matriz, socios, sancoes, pgfn, leniencia) e
    agregados (mv_empresa_pb). Evita 5-7 queries redundantes por par.
    BB com 200 munis fazia 1400 queries cadastrais — agora faz 7 (uma
    leitura do cache global) + 200x5 queries scoped = 1007 vs 2400+.

    Se o cache global nao existe (warmer ainda nao processou esse cnpj
    ou cache foi dropado), fallback pro compute completo.
    """
    from web.config import TIMEOUT_PROFILE_WARM
    from web.db import read_web_cache
    from web.routes.empresa import (
        CACHE_QUERY_ID as EMPRESA_CACHE_QID,
        CACHE_QUERY_ID_MUN as EMPRESA_MUN_CACHE_QID,
        EmpresaNotFoundError,
        compute_empresa_municipio_perfil_dict,
    )
    from web.utils.slug import municipio_slug as _slug_of

    cnpj_completo, municipio_nome = par
    slug = _slug_of(municipio_nome)
    if not slug:
        return False, "no_slug"

    # Tenta reusar cadastrais do cache global (preenchido pelo phase
    # anterior _warm_empresas_phase). Read sub-ms.
    cadastral_cache = None
    agregados_cache = None
    try:
        cached = read_web_cache(EMPRESA_CACHE_QID, cnpj_completo)
        if cached is not None:
            cols, rows = cached
            if rows and rows[0]:
                global_data = rows[0][0]
                if isinstance(global_data, dict):
                    cadastral_cache = {
                        "estabelecimento": global_data.get("estabelecimento") or {},
                        "matriz": global_data.get("matriz"),
                        "socios": global_data.get("socios") or [],
                        "sancoes": global_data.get("sancoes") or [],
                        "pgfn": global_data.get("pgfn") or [],
                        "acordos_leniencia": global_data.get("acordos_leniencia") or [],
                        "municipios_pagantes": global_data.get("municipios_pagantes") or [],
                        "top_elementos": global_data.get("top_elementos") or [],
                        "monthly_global": global_data.get("monthly_global") or [],
                    }
                    agregados_cache = global_data.get("agregados") or {}
    except Exception:
        # Falha de leitura nao eh fatal — fallback pro compute completo.
        cadastral_cache = None
        agregados_cache = None

    try:
        data = compute_empresa_municipio_perfil_dict(
            cnpj_completo, municipio_nome,
            timeout_sec=TIMEOUT_PROFILE_WARM,
            cadastral_cache=cadastral_cache,
            agregados_cache=agregados_cache,
        )
    except EmpresaNotFoundError as e:
        return False, f"not_found:{e}"
    except Exception as e:
        return False, f"compute_failed:{str(e).splitlines()[0]}"

    key = f"{cnpj_completo}:{slug}"
    try:
        conn = _thread_conn()
        with conn.cursor() as cur:
            _upsert(
                cur,
                EMPRESA_MUN_CACHE_QID,
                key,
                ["payload"],
                [[data]],
            )
        conn.commit()
    except Exception as e:
        try:
            _thread_conn().rollback()
        except Exception:
            pass
        return False, f"cache_write_failed:{str(e).splitlines()[0]}"
    return True, None


def warm_cycle_empresas_municipios(
    pares: list[tuple[str, str]], verbose: bool = True
) -> tuple[int, int, int]:
    """Processa pares (empresa, municipio) em paralelo. Mesma semantica de
    warm_cycle_empresas. Returns: (ok, fail, skipped_not_found)."""
    bootstrap = psycopg2.connect(DSN)
    bootstrap.autocommit = False
    _ensure_cache_table(bootstrap)
    bootstrap.close()

    total = len(pares)
    if total == 0:
        return 0, 0, 0
    print(
        f"[empresas-mun] Warming {total} pares em {PARALLEL_WORKERS} workers...",
        flush=True,
    )

    ok = 0
    fail = 0
    skipped = 0
    t0 = time.time()
    # Workers maior aqui: empresa-municipio eh I/O bound (5 queries por
    # par, todas com index hits sub-ms na maioria dos casos). 4 workers
    # subutilizam o DB; bump pra 8 (B4 tem 4 vCPU mas postgres async I/O
    # se beneficia de mais conexoes paralelas). Override via env
    # WARM_CACHE_WORKERS_MUN.
    workers_mun = int(os.getenv("WARM_CACHE_WORKERS_MUN", str(PARALLEL_WORKERS * 2)))
    with ThreadPoolExecutor(max_workers=workers_mun) as ex:
        futures = {ex.submit(_warm_one_empresa_municipio, p): p for p in pares}
        done = 0
        for fut in as_completed(futures):
            done += 1
            par = futures[fut]
            try:
                success, msg = fut.result()
            except Exception as e:
                success = False
                msg = f"future_exception:{e}"
            if success:
                ok += 1
            elif msg and msg.startswith("not_found:"):
                skipped += 1
            else:
                fail += 1
                if verbose and msg:
                    print(f"  [ERR] {par[0]}@{par[1]}: {msg}", flush=True)
            if verbose and done % 500 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                print(
                    f"[empresas-mun] {done}/{total} "
                    f"({ok} ok, {fail} fail, {skipped} skipped) — "
                    f"{rate:.1f}/s, eta {eta/60:.1f}min",
                    flush=True,
                )
    elapsed = time.time() - t0
    print(
        f"[empresas-mun] Completo: {ok} ok, {fail} fail, {skipped} skipped "
        f"({elapsed/60:.1f}min)",
        flush=True,
    )
    return ok, fail, skipped


def _warm_empresas_municipios_phase() -> tuple[int, int, int]:
    """Fase de warming de pares (empresa, municipio). Mesma logica do
    _warm_empresas_phase mas sobre EMPRESA_PERFIL_MUN. Resume mode aplicado
    via _filter_cached_munis com keys f'{cnpj}:{slug}'.
    """
    from web.utils.slug import municipio_slug as _slug_of

    print("--- Empresas-Municipios: enumerando qualificadas ---")
    boot = psycopg2.connect(DSN)
    boot.autocommit = True
    try:
        all_pares = _get_qualifying_empresas_municipios(boot)
    finally:
        boot.close()

    if not all_pares:
        print(
            "[empresas-mun] Nenhum par (empresa, municipio) qualificado. "
            "Skipping."
        )
        return 0, 0, 0

    # Construir keys e mapping pra filtrar resume mode.
    par_by_key: dict[str, tuple[str, str]] = {}
    keys: list[str] = []
    for cnpj_completo, municipio_nome in all_pares:
        slug = _slug_of(municipio_nome)
        if not slug:
            continue
        key = f"{cnpj_completo}:{slug}"
        par_by_key[key] = (cnpj_completo, municipio_nome)
        keys.append(key)

    if not keys:
        return 0, 0, 0

    remaining_keys, skipped_resume = _filter_cached_munis(
        "EMPRESA_PERFIL_MUN", keys
    )
    if skipped_resume > 0:
        print(
            f"[empresas-mun] Resume mode: {skipped_resume} ja cacheados nas "
            f"ultimas {SKIP_RECENT_HOURS}h, processando {len(remaining_keys)} "
            f"restantes."
        )

    if not remaining_keys:
        return 0, 0, skipped_resume

    pares_proc = [par_by_key[k] for k in remaining_keys if k in par_by_key]

    from web import db as web_db

    web_db.init_pool()
    try:
        ok, fail, skip_nf = warm_cycle_empresas_municipios(pares_proc)
    finally:
        try:
            web_db.close_pool()
        except Exception:
            pass

    return ok, fail, skipped_resume + skip_nf


if __name__ == "__main__":
    main()
