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

# Modo de skip do warm. Dados das fontes governamentais sao ESTATICOS apos o
# ETL terminar, entao por padrao NAO recomputamos cache ja gerado — apenas
# preenchemos chaves ausentes ou recem-invalidadas (via TRUNCATE web_cache
# com drop_cache=true ou DELETE cirurgico com invalidate_cache_keys=...).
#
# Valores:
#   -1 (DEFAULT): skip qualquer entrada cacheada, qualquer idade. Eh o modo
#                 normal porque os dados sao estaticos. Para forcar rebuild,
#                 use drop_cache (TRUNCATE) ou invalidate_cache_keys (DELETE).
#    0: rebuild completo (sem skip). Opt-in explicito; raramente necessario.
#    N > 0: skip se cacheado nas ultimas N horas (resume mode legacy, usado
#           quando se quer um upper-bound de idade — ex: forcar reprocessar
#           tudo cacheado ha >72h).
SKIP_RECENT_HOURS = int(os.getenv("WARM_SKIP_RECENT_HOURS", "-1"))


def _skip_mode_label() -> str:
    """Etiqueta humana do modo de skip para logs."""
    if SKIP_RECENT_HOURS < 0:
        return "skip-if-cached (any age)"
    if SKIP_RECENT_HOURS == 0:
        return "rebuild completo"
    return f"skip se cacheado nas ultimas {SKIP_RECENT_HOURS}h"


# ─────────────────────────────────────────────────────────────────────────
# SHADOW REWARM — zero-downtime cache key versioning
# ─────────────────────────────────────────────────────────────────────────
# Permite re-popular uma chave do cache SEM cache-miss enquanto o warm roda.
# Durante o warm, resultados novos sao escritos em <query_id>__pending; live
# rows continuam sendo lidos pelo cruza-web normalmente. Apos warm completar
# com sucesso (fail == 0 pra essa qid), swap atomico move shadow → live numa
# UNICA transacao cobrindo TODOS os qids elegiveis (atomicity all-or-nothing):
#
#   BEGIN;
#     -- repete por qid em shadow com fail==0:
#     INSERT INTO web_cache (qid, muni, ...) SELECT '<qid>', muni, ...
#       FROM web_cache WHERE query_id = '<qid>__pending'
#       ON CONFLICT (query_id, municipio) DO UPDATE SET ...;
#     DELETE FROM web_cache WHERE query_id = '<qid>__pending';
#   COMMIT;
#
# A unica transacao garante que readers do cruza-web nunca vejam derived
# (KPI_SUMMARY) na versao NEW enquanto source (PERFIL) ainda esta OLD, ou
# vice-versa — todos os qids do shadow swap "rolam" simultaneamente do
# ponto de vista de reads concorrentes (read committed semantics).
# UPSERT (nao DELETE+RENAME) preserva munis fora do escopo do warm
# (importante em warms parciais via --mun X).
#
# Disparado via env WARM_REWARM_KEYS (CSV de patterns exatos), populado
# pelo deploy.yml a partir do input `rewarm_cache_keys`. Diferenca pro
# `invalidate_cache_keys` (que faz hard DELETE): shadow rewarm zera o
# downtime durante o warm (que pode demorar 12-18h).
#
# ─── Adicionando shadow rewarm para uma NOVA "LEAF" query ────────────────
# Leaf = query computada direto do banco/MV, NAO le de outras keys do cache
# (ex: HEATMAP, Q01-Q310 do registry, PERFIL, EMPRESA_PERFIL).
#
#   Nao requer mudancas no codigo. Basta o user passar o pattern em
#   rewarm_cache_keys; _warm_query_across_munis e _filter_cached_munis ja
#   consultam _effective_qid internamente.
#
# ─── Adicionando shadow rewarm para uma NOVA "DERIVED" query ─────────────
# Derived = query computada lendo OUTRAS keys do web_cache (ex:
# KPI_SUMMARY le PERFIL/TOP_FORNECEDORES/TOP_SERVIDORES e agrega em Python).
#
#   1. Registre as deps em CACHE_DEPENDENCY_GRAPH abaixo. Bases sao
#      sem prefixo (PERFIL, nao ANO:PERFIL) — a expansao por prefixo
#      eh automatica via _is_shadow_for.
#   2. Na funcao que computa o derived, leia cada dep do cache via
#        cache = _read_cache(conn, _effective_qid(f"{prefix}DEP"), mun)
#      (translation shadow/live automatica).
#   3. Strict no-fallback: se _is_shadow_for(derived_qid) AND
#      _is_shadow_for(dep_qid) AND cache vazio pra essa muni → retorne
#      False (a funcao FALHA pra essa muni). Sem isso, computaria
#      misturando OLD live + NEW shadow e geraria stale apos swap.
#      Ver _compute_and_cache_kpi_summary como modelo.
#   4. Em warm_cycle_pb, garanta que as deps rodam ANTES do derived
#      (ordem das fases). Hoje: PERFIL → TOP_FORN → TOP_SERV →
#      KPI_SUMMARY.
#
# ─── Por que o derived precisa entrar em shadow quando um dep entra? ─────
# Sem auto-expansao, o cenario seria:
#   - User pede rewarm_cache_keys=PERFIL
#   - Warm escreve PERFIL__pending (shadow). Live PERFIL continua VELHO.
#   - Warm chega no KPI_SUMMARY; le PERFIL do cache → le do live →
#     PERFIL VELHO. Computa KPI_SUMMARY baseado em VELHO. Escreve em
#     live KPI_SUMMARY (porque KPI_SUMMARY nao entrou em shadow).
#   - Swap do PERFIL: live PERFIL = NOVO.
#   - Live KPI_SUMMARY = computado do VELHO PERFIL → inconsistente
#     com NOVO PERFIL no UI.
# Solucao: _is_shadow_for auto-inclui o derived quando alguma dep esta
# em shadow (mesmo prefixo). Idem strict no-fallback: garante que
# shadow KPI_SUMMARY le shadow PERFIL (sem misturar).
#
# ─── Limitacoes ──────────────────────────────────────────────────────────
#   - Swap exige fail == 0 pra essa qid. Senao swap abortado e shadow rows
#     daquele ciclo sao descartados no inicio do PROXIMO deploy (via Reset
#     shadow rows step). Nao ha "reuso de shadow parcial" entre deploys —
#     decisao tomada pra evitar shadow stale quando SQL muda entre deploys
#     (P1 Opus 4.7 review PR #105). Pra que swap aconteca, todos os munis
#     da qid precisam ter sucesso num unico ciclo do warm.
#   - Shadow rows sao DELETADOS no inicio de cada deploy ("Reset shadow
#     rows" step no deploy.yml), evitando stale entre deploys que
#     mudaram a SQL.
#   - Match eh EXATO (pattern == query_id OR pattern == base), NAO substring.
#     Pattern "PERFIL" casa "PERFIL", "ANO:PERFIL", "12M:PERFIL" mas
#     NAO casa "EMPRESA_PERFIL". Use prefixos explicitos pra escopar
#     (ANO:Q65 vs Q65 sem prefixo).
# ─────────────────────────────────────────────────────────────────────────

# Sufixo aplicado a query_id pra denotar shadow rows. Reads do cruza-web
# leem apenas live (query_id sem sufixo); only o warm le shadow via
# _effective_qid.
SHADOW_SUFFIX = "__pending"

# Patterns de query_id em modo shadow (match EXATO de qid ou base). Vazio = sem shadow.
REWARM_KEYS = {
    k.strip() for k in os.getenv("WARM_REWARM_KEYS", "").split(",") if k.strip()
}

# Mapa derived → [source bases]. Adicione aqui novas derived queries pra
# que a auto-expansao funcione: shadow de uma source dispara shadow do
# derived (mesmo prefixo). Bases SEM prefixo.
CACHE_DEPENDENCY_GRAPH: dict[str, list[str]] = {
    "KPI_SUMMARY": ["PERFIL", "TOP_FORNECEDORES", "TOP_SERVIDORES"],
}

# Tracking dos resultados de queries que estavam em shadow durante esta
# execucao do warm. qid (logical, sem __pending) → (ok, fail). Usado no
# final do ciclo pra decidir quais qids podem ter swap (so se fail == 0).
_shadow_results: dict[str, tuple[int, int]] = {}


def _qid_base(qid: str) -> str:
    """Retorna o segmento 'base' do query_id, removendo prefixos ANO:/12M:."""
    return qid.split(":", 1)[-1] if ":" in qid else qid


def _qid_prefix(qid: str) -> str:
    """Retorna o prefixo incluindo ':', ou string vazia."""
    return qid.split(":", 1)[0] + ":" if ":" in qid else ""


def _is_shadow_for(query_id: str) -> bool:
    """True se este query_id deve usar shadow rows ao inves de live.

    Match semantics (exact base/qid, NAO substring):
      - Pattern == query_id literal (ex: "ANO:Q65" casa exato).
      - Pattern == base (qid sem prefixo): ex: "Q65" casa "Q65",
        "ANO:Q65", "12M:Q65". MAS "PERFIL" NAO casa "EMPRESA_PERFIL"
        (base de EMPRESA_PERFIL eh "EMPRESA_PERFIL" inteiro).
      - Auto-expansao: se query_id eh derived (base em
        CACHE_DEPENDENCY_GRAPH) E alguma source dep (mesmo prefixo) casa
        REWARM_KEYS → derived entra em shadow tb.

    Por que match exato e nao substring: evita "PERFIL" disparar warm
    de ~143K empresas via EMPRESA_PERFIL (P1 GPT 5.5 review PR #105).
    """
    if not REWARM_KEYS:
        return False
    base = _qid_base(query_id)
    if any(p == query_id or p == base for p in REWARM_KEYS):
        return True
    deps = CACHE_DEPENDENCY_GRAPH.get(base)
    if deps:
        prefix = _qid_prefix(query_id)
        for dep_base in deps:
            dep_qid = f"{prefix}{dep_base}"
            if any(p == dep_qid or p == dep_base for p in REWARM_KEYS):
                return True
    return False


def _effective_qid(query_id: str) -> str:
    """Retorna o query_id efetivo pra leitura/escrita do cache durante warm.

    Em modo shadow: anexa SHADOW_SUFFIX. Live rows (sem sufixo) continuam
    sendo servidos pelo cruza-web ate o swap final.
    """
    return f"{query_id}{SHADOW_SUFFIX}" if _is_shadow_for(query_id) else query_id


def _record_shadow_result(query_id: str, ok: int, fail: int) -> None:
    """Acumula resultado de um shadow warm (chamado por warm_query/warm_kpi).

    Mantido como agregado: chamadas multiplas pra mesma qid somam ok/fail.
    """
    if not _is_shadow_for(query_id):
        return
    prev_ok, prev_fail = _shadow_results.get(query_id, (0, 0))
    _shadow_results[query_id] = (prev_ok + ok, prev_fail + fail)


def _swap_all_pending_shadows(verbose: bool = True) -> tuple[int, int]:
    """Apos warm cycle, swap atomico de cada qid que estava em shadow E
    completou sem falhas (fail == 0).

    Importante (alinhado com Reset shadow step no deploy.yml):
      - Qids com fail > 0: shadow NAO promovido nesse ciclo. As rows shadow
        ficam no banco mas serao APAGADAS no inicio do proximo deploy
        (Reset). Sem reuso entre deploys — evita shadow stale quando SQL
        muda entre deploys.
      - Swap ATOMICO entre todas as qids: uma unica transacao cobre
        UPSERT+DELETE pra todos os qids elegíveis. Elimina janela onde
        derived (KPI) e source (PERFIL) ficam temporariamente em versoes
        diferentes em live. (P2 Opus 4.7 + GPT 5.5 review PR #105.)

    Returns (swapped_count, kept_count).
    """
    if not _shadow_results:
        return 0, 0

    swappable: list[str] = []
    skipped_zero: list[str] = []
    aborted: list[tuple[str, int, int]] = []
    for qid, (ok, fail) in sorted(_shadow_results.items()):
        if fail > 0:
            aborted.append((qid, ok, fail))
            continue
        if ok == 0:
            skipped_zero.append(qid)
            continue
        swappable.append(qid)

    if verbose:
        print(
            f"\n--- Shadow swap: {len(swappable)} swap, "
            f"{len(aborted)} abort (fail>0), {len(skipped_zero)} skip (0 rows) ---",
            flush=True,
        )
        for qid, ok, fail in aborted:
            print(
                f"  ABORT {qid}: {ok} ok, {fail} fail — shadow descartado "
                f"no proximo deploy (rerun com mesmo rewarm_cache_keys)",
                flush=True,
            )
        for qid in skipped_zero:
            print(
                f"  SKIP {qid}: 0 rows escritas (warm filtrou tudo — "
                f"verifique se Reset shadow rows step rodou)",
                flush=True,
            )

    if not swappable:
        if verbose:
            print("--- Shadow swap done: 0 swapped ---", flush=True)
        return 0, len(aborted) + len(skipped_zero)

    # SWAP ATOMICO entre todos os qids: uma unica transacao. Garante que
    # readers do cruza-web nunca vejam KPI v=NEW + PERFIL v=OLD durante
    # a transicao. Read-committed do PG ainda permite que uma request
    # individual veja snapshot consistente pos-COMMIT. (P2 review.)
    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    swapped = 0
    failed_qids: list[tuple[str, str]] = []
    try:
        with conn.cursor() as cur:
            for qid in swappable:
                shadow_qid = f"{qid}{SHADOW_SUFFIX}"
                try:
                    cur.execute(
                        f"""
                        INSERT INTO {CACHE_TABLE}
                            (query_id, municipio, columns, rows, row_count, updated_at)
                        SELECT %s, municipio, columns, rows, row_count, now()
                        FROM {CACHE_TABLE}
                        WHERE query_id = %s
                        ON CONFLICT (query_id, municipio) DO UPDATE SET
                            columns = EXCLUDED.columns,
                            rows = EXCLUDED.rows,
                            row_count = EXCLUDED.row_count,
                            updated_at = EXCLUDED.updated_at
                        """,
                        (qid, shadow_qid),
                    )
                    promoted = cur.rowcount
                    cur.execute(
                        f"DELETE FROM {CACHE_TABLE} WHERE query_id = %s",
                        (shadow_qid,),
                    )
                    cleaned = cur.rowcount
                    if verbose:
                        print(
                            f"  SWAP {qid}: promoted {promoted}, cleaned {cleaned}",
                            flush=True,
                        )
                    swapped += 1
                except Exception as e:
                    msg = str(e).splitlines()[0]
                    failed_qids.append((qid, msg))
                    if verbose:
                        print(f"  FAIL {qid}: {msg}", flush=True)
                    # Re-raise pra rollback de TODA a transacao —
                    # consistencia all-or-nothing entre as qids.
                    raise
        conn.commit()
    except Exception as e:
        conn.rollback()
        if verbose:
            print(
                f"--- Shadow swap ROLLBACK (atomico): {len(swappable)} qids "
                f"NAO promovidos. Re-run com mesmo rewarm_cache_keys. ---",
                flush=True,
            )
        return 0, len(swappable) + len(aborted) + len(skipped_zero)
    finally:
        conn.close()

    if verbose:
        print(
            f"--- Shadow swap done: {swapped} swapped, "
            f"{len(aborted) + len(skipped_zero)} kept/skipped ---",
            flush=True,
        )
    return swapped, len(aborted) + len(skipped_zero)


# ─────────────────────────────────────────────────────────────────────────
# CLEANUP ORPHAN EMPRESA CACHE — DELETE entries stale pos-MV refresh
# ─────────────────────────────────────────────────────────────────────────
# Stale entries surgem quando o ETL normalize remove CPFs padded contaminados
# de tabelas-fonte (ADR-0007). Empresas "fantasma" (ex: AVICOLA CHESTER
# MONGAGUA LTDA com cnpj_basico 00014020 colidindo com prefixo de CPFs
# mascarados 000.014.020-XX) saem de mv_empresa_pb apos REFRESH CONCURRENTLY,
# mas suas entries em web_cache (EMPRESA_PERFIL, EMPRESA_PERFIL_MUN)
# permanecem stale: o warm cycle sobrescreve apenas empresas qualificadas
# atuais, nunca toca as orfas.
#
# Sintoma: paginas /empresa/<cnpj>/<slug> orfas servem KPIs falsos do cache
# (R$ X mil, N empenhos) com tabela live retornando 0 — inconsistencia
# visivel ao usuario (descoberta apos PR #156 / ADR-0007).
#
# Decisao de DELETE (vs zerar agregados ou tabela durable de URLs): ver
# ADR-0009. Resumo: simplicidade arquitetural, sitemap regenera natural
# (so qualifying da MV), Google de-indexa URLs orfas via 503 transient
# (cache miss). Dados "vazios" (cadastrais OK + agregados zero) sao tao
# uteis ao usuario quanto a ausencia da pagina.
#
# Esta funcao roda STANDALONE — nao depende nem dispara warm cycle. Pode
# ser invocada via:
#   python -m web.warm_cache --cleanup-orphan-empresa
#   python -m web.warm_cache --cleanup-orphan-empresa --dry-run
# Ou via deploy.yml input `cleanup_orphan_empresa_cache=true`.
# ─────────────────────────────────────────────────────────────────────────

def cleanup_orphan_empresa_cache(
    dry_run: bool = False, batch_size: int = 5000, verbose: bool = True
) -> tuple[int, int]:
    """DELETE entries em web_cache (EMPRESA_PERFIL, EMPRESA_PERFIL_MUN)
    apontando para CNPJs nao mais qualificados em mv_empresa_pb.

    Identifica stale via NOT EXISTS (SELECT 1 FROM mv_empresa_pb WHERE
    cnpj_basico = substring(municipio, 1, 8)):
      - EMPRESA_PERFIL: municipio = cnpj_completo (14 digitos)
      - EMPRESA_PERFIL_MUN: municipio = '<cnpj14>:<slug>' (composite)

    Em ambos os casos substring(municipio, 1, 8) extrai o cnpj_basico.
    Filtros casam.

    DELETEs sao em batches via WITH ... USING ctid pra:
      - Nao segurar lock longo em web_cache (que e read-heavy pelo cruza-web).
      - Permitir progress log e interrupcao limpa.

    Args:
        dry_run: se True, so loga contagem (sem DELETE).
        batch_size: rows por iteracao. Default 5k = ~100 iteracoes pra
            511k rows tipicas pos-fix.
        verbose: log progresso a cada batch.

    Returns: (deleted_perfil, deleted_perfil_mun).
    """
    print(
        f"=== Cleanup orphan empresa cache ({'DRY-RUN' if dry_run else 'LIVE'}) ===",
        flush=True,
    )
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            # Pre-flight: web_cache existe? mv_empresa_pb existe?
            cur.execute("SELECT to_regclass('public.web_cache')")
            wc_ok = cur.fetchone()[0]
            cur.execute("SELECT to_regclass('public.mv_empresa_pb')")
            mv_ok = cur.fetchone()[0]
            if not wc_ok or not mv_ok:
                print(
                    f"  web_cache={wc_ok}, mv_empresa_pb={mv_ok} — abortando "
                    f"(uma das relacoes nao existe).",
                    flush=True,
                )
                return 0, 0

            # Conta total estimado antes de comecar (info pro user).
            for qid in ("EMPRESA_PERFIL", "EMPRESA_PERFIL_MUN"):
                cur.execute(
                    """
                    SELECT count(*) FROM web_cache wc
                    WHERE wc.query_id = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM mv_empresa_pb m
                          WHERE m.cnpj_basico = substring(wc.municipio, 1, 8)
                      )
                    """,
                    (qid,),
                )
                est = cur.fetchone()[0]
                print(f"  {qid}: {est} entries orfas identificadas", flush=True)

            if dry_run:
                print("  DRY-RUN — nenhuma row deletada.", flush=True)
                return 0, 0

            # DELETE em batches por qid. Usa WITH ... USING ctid pra
            # contornar a limitacao do PG (LIMIT direto em DELETE nao
            # suportado) E permitir progress log entre batches.
            deleted_total: dict[str, int] = {
                "EMPRESA_PERFIL": 0,
                "EMPRESA_PERFIL_MUN": 0,
            }
            for qid in ("EMPRESA_PERFIL", "EMPRESA_PERFIL_MUN"):
                batch = 0
                t0 = time.time()
                while True:
                    cur.execute(
                        """
                        WITH stale AS (
                            SELECT wc.ctid
                            FROM web_cache wc
                            WHERE wc.query_id = %s
                              AND NOT EXISTS (
                                  SELECT 1 FROM mv_empresa_pb m
                                  WHERE m.cnpj_basico = substring(wc.municipio, 1, 8)
                              )
                            LIMIT %s
                        )
                        DELETE FROM web_cache wc
                        USING stale s
                        WHERE wc.ctid = s.ctid
                        """,
                        (qid, batch_size),
                    )
                    n = cur.rowcount
                    deleted_total[qid] += n
                    batch += 1
                    if verbose and (batch % 10 == 0 or n < batch_size):
                        elapsed = time.time() - t0
                        rate = deleted_total[qid] / elapsed if elapsed > 0 else 0
                        print(
                            f"  {qid}: batch {batch} ({n} deleted) — "
                            f"total {deleted_total[qid]} ({rate:.0f}/s, "
                            f"{elapsed:.1f}s)",
                            flush=True,
                        )
                    if n == 0:
                        break
                print(
                    f"  {qid}: DONE — {deleted_total[qid]} deleted em {batch} batches",
                    flush=True,
                )
    finally:
        conn.close()

    print(
        f"=== Cleanup complete: "
        f"{deleted_total['EMPRESA_PERFIL']} EMPRESA_PERFIL + "
        f"{deleted_total['EMPRESA_PERFIL_MUN']} EMPRESA_PERFIL_MUN ===",
        flush=True,
    )
    return deleted_total["EMPRESA_PERFIL"], deleted_total["EMPRESA_PERFIL_MUN"]


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

    Shadow rewarm: KPI_SUMMARY eh "derived" (le PERFIL/TOP_FORN/TOP_SERV
    do cache pra computar). Se qualquer dep esta em shadow neste deploy
    (REWARM_KEYS casa), KPI_SUMMARY entra em shadow auto (via
    _is_shadow_for + CACHE_DEPENDENCY_GRAPH).

    Strict no-fallback: se KPI_SUMMARY esta em shadow E uma dep tb esta
    em shadow E o shadow da dep ESTA VAZIO pra essa muni → retorna False.
    Sem isso, computariamos misturando NEW shadow + OLD live e ficaria
    stale apos o swap dos deps. Munis que falham aqui sao reprocessadas
    no proximo deploy (junto com a dep que falhou).
    """
    prefix = f"{periodo}:" if periodo else ""
    qid = f"{prefix}KPI_SUMMARY"
    try:
        # Leitura via _effective_qid: em shadow mode (REWARM casa PERFIL),
        # le PERFIL__pending; senao le live PERFIL. Mesmo pra TOP_*.
        perfil_qid = f"{prefix}PERFIL"
        forn_qid = f"{prefix}TOP_FORNECEDORES"
        serv_qid = f"{prefix}TOP_SERVIDORES"
        perfil_cache = _read_cache(conn, _effective_qid(perfil_qid), mun)
        forn_cache = _read_cache(conn, _effective_qid(forn_qid), mun)
        serv_cache = _read_cache(conn, _effective_qid(serv_qid), mun)

        # Strict no-fallback: se SOMOS shadow E alguma dep tb eh shadow E
        # o shadow da dep esta vazio pra essa muni, abortamos. Caso
        # contrario contaminariamos o shadow KPI_SUMMARY com OLD data.
        if _is_shadow_for(qid):
            missing: list[str] = []
            if _is_shadow_for(perfil_qid) and not (perfil_cache and perfil_cache[1]):
                missing.append("PERFIL")
            if _is_shadow_for(forn_qid) and not forn_cache:
                missing.append("TOP_FORNECEDORES")
            if _is_shadow_for(serv_qid) and not serv_cache:
                missing.append("TOP_SERVIDORES")
            if missing:
                if verbose:
                    print(
                        f"  [SKIP] {qid} mun={mun}: shadow deps vazios "
                        f"({','.join(missing)}) — strict no-fallback",
                        flush=True,
                    )
                return False

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
        # Tambem via _effective_qid pra honrar shadow do PERFIL all-time
        # quando REWARM casa.
        score_canonical = perfil.get("risco_score") if not prefix else None
        if score_canonical is None and prefix:
            alltime_perfil_cache = _read_cache(conn, _effective_qid("PERFIL"), mun)
            if alltime_perfil_cache and alltime_perfil_cache[1]:
                alltime_perfil = _row_to_dict(alltime_perfil_cache[0], alltime_perfil_cache[1][0])
                score_canonical = alltime_perfil.get("risco_score")
        summary["score_canonical"] = score_canonical
        with conn.cursor() as cur:
            _upsert(cur, _effective_qid(qid), mun, ["payload"], [[json.dumps(summary, default=str)]])
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

    Em modo shadow (REWARM_KEYS casa query_id), escreve em
    <query_id>__pending em vez de live. Caller usa _effective_qid pra
    decidir; aqui aplicamos _effective_qid antes do upsert pra centralizar
    a logica.
    """
    conn = _thread_conn()
    if extra_params:
        params = {**extra_params, "municipio": mun}
    else:
        params = {"municipio": mun}
    write_qid = _effective_qid(query_id)
    try:
        cols, rows = _execute(conn, sql, params, timeout_sec)
        conn.commit()
        with conn.cursor() as cur:
            _upsert(cur, write_qid, mun, cols, rows)
        conn.commit()
        return True, None
    except Exception as e:
        conn.rollback()
        msg = str(e).split("\n")[0]
        return False, msg


def _filter_cached_munis(query_id: str, municipios: list[str]) -> tuple[list[str], int]:
    """Filtra munis ja cacheados conforme WARM_SKIP_RECENT_HOURS:
      * -1 (default): skip QUALQUER muni cacheado, qualquer idade. Dados
        sao estaticos, reprocessar eh waste. Para forcar rebuild use
        drop_cache=true ou invalidate_cache_keys=... no deploy.yml.
      *  0: nao pula nada (rebuild completo).
      *  N > 0: skip munis com cache atualizado nas ultimas N horas.

    Em modo shadow (query_id casa REWARM_KEYS), filtramos pelo
    _effective_qid (<query_id>__pending), pra permitir RESUME de uma
    shadow warm interrompida no MESMO deploy. Entre deploys, "Reset
    shadow rows" no deploy.yml apaga os __pending antes do warm.

    Returns (munis_to_process, num_skipped).
    """
    if SKIP_RECENT_HOURS == 0:
        return municipios, 0

    effective_qid = _effective_qid(query_id)
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            if SKIP_RECENT_HOURS < 0:
                # Skip qualquer entrada existente, independente de idade.
                cur.execute(
                    f"SELECT municipio FROM {CACHE_TABLE} WHERE query_id = %s",
                    (effective_qid,),
                )
            else:
                cur.execute(
                    f"SELECT municipio FROM {CACHE_TABLE} "
                    f"WHERE query_id = %s AND updated_at > now() - interval %s",
                    (effective_qid, f"{SKIP_RECENT_HOURS} hours"),
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

    Por padrao (WARM_SKIP_RECENT_HOURS=-1), pula munis ja cacheados,
    qualquer idade — dados sao estaticos. Ver _filter_cached_munis para
    detalhes dos modos suportados.
    """
    original_total = len(municipios)
    municipios, skipped = _filter_cached_munis(query_id, municipios)
    if not municipios:
        if verbose:
            print(
                f"  {query_id}: skipped {skipped}/{original_total} "
                f"({_skip_mode_label()})",
                flush=True,
            )
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
        shadow_msg = " [SHADOW]" if _is_shadow_for(query_id) else ""
        print(
            f"  {query_id}{shadow_msg}: {ok}/{total} ok, {fail} fail{suffix}{skip_msg} "
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
    # Em shadow mode, registra resultado pra decisao de swap no fim do ciclo.
    _record_shadow_result(query_id, ok, fail)
    return ok + skipped, fail


def _warm_kpi_summary_across_munis(municipios: list[str], periodo: str, verbose: bool):
    """Computa KPI_SUMMARY para todos os munis em paralelo. Depende de
    PERFIL/TOP_FORN/TOP_SERV ja cacheados para o periodo."""
    qid = f"{periodo}:KPI_SUMMARY" if periodo else "KPI_SUMMARY"
    original_total = len(municipios)
    municipios, skipped = _filter_cached_munis(qid, municipios)
    if not municipios:
        if verbose:
            print(
                f"  {qid}: skipped {skipped}/{original_total} "
                f"({_skip_mode_label()})",
                flush=True,
            )
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
        shadow_msg = " [SHADOW]" if _is_shadow_for(qid) else ""
        print(
            f"  {qid}{shadow_msg}: {ok}/{total} ok, {fail} fail{skip_msg} "
            f"({elapsed:.0f}s)",
            flush=True,
        )
        if failed_munis:
            shown = failed_munis[:10]
            for mun_failed in shown:
                print(f"    FAIL {qid} {mun_failed}", flush=True)
            if len(failed_munis) > 10:
                print(f"    ... +{len(failed_munis) - 10} outras falhas", flush=True)
    # Registra resultado pra decisao de swap no fim do ciclo (shadow mode).
    _record_shadow_result(qid, ok, fail)
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
                _effective_qid(EMPRESA_CACHE_QID),
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
    # Registra resultado pra swap atomico no fim do ciclo (shadow mode).
    # Usa a constante canonica de web.routes.empresa em vez de literal pra
    # nao desincronizar se a constante mudar (P2 Opus 4.7 review PR #105).
    # Import diferido pra evitar cycle no topo do modulo.
    from web.routes.empresa import CACHE_QUERY_ID as _EMPRESA_QID
    _record_shadow_result(_EMPRESA_QID, ok, fail)
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
    parser.add_argument(
        "--cleanup-orphan-empresa",
        action="store_true",
        help=(
            "STANDALONE: DELETE entries em web_cache (EMPRESA_PERFIL, "
            "EMPRESA_PERFIL_MUN) apontando para CNPJs nao mais qualificados "
            "em mv_empresa_pb. NAO dispara warm cycle. Use apos ETL "
            "normalize fix (ADR-0007) ou refresh de mv_empresa_pb que "
            "removeu empresas (ex: contaminacao por CPF padded). Idempotente. "
            "Combine com --dry-run pra so contar."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Usado com --cleanup-orphan-empresa: so loga contagem sem deletar.",
    )
    args = parser.parse_args()

    # Standalone cleanup: nao dispara warm, sai apos limpar.
    if args.cleanup_orphan_empresa:
        cleanup_orphan_empresa_cache(dry_run=args.dry_run, verbose=True)
        sys.exit(0)

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
        ok_l = fail_l = skip_l = 0
        ok_r = fail_r = skip_r = 0
        ok_sm = fail_sm = skip_sm = 0
        if not skip_empresas_flag:
            ok_e, fail_e, skip_e = _warm_empresas_phase()
            ok_em, fail_em, skip_em = _warm_empresas_municipios_phase()
            ok_l, fail_l, skip_l = _warm_licitacoes_phase()
            ok_r, fail_r, skip_r = _warm_cidade_resumo_phase()
        # Shadow swap: apos TODO trabalho do ciclo terminar, fazemos os
        # swaps atomicos (UMA transacao cobrindo todos os qids elegiveis)
        # das qids que estavam em shadow E completaram sem falhas.
        # Qids com fail > 0 ficam SEM swap nesse ciclo; o "Reset shadow
        # rows" step no proximo deploy descarta o shadow stale antes de
        # reprocessar.
        # Importante: swap acontece UMA VEZ por ciclo, depois das fases
        # PB + empresas + empresas_municipios + licitacoes + cidade_resumo.
        # Garante que KPI_SUMMARY (derived) ja foi computado contra o
        # shadow de PERFIL antes do swap dos deps.
        _swap_all_pending_shadows(verbose=True)
        # Reset tracking pra eventual proximo ciclo (mode --loop).
        _shadow_results.clear()
        # Sitemaps sempre rodam por ULTIMO (rapido, ~30-60s pra ~40 entries)
        # — pre-popula web_cache pra eliminar timeout pos-restart do
        # cruza-web. Roda APOS shadow swap porque os counts() referenciam
        # MVs que ja devem estar no estado final (qids SITEMAP_XML nao
        # participam de shadow swap). PR #85 + rebase 2026-05-19.
        ok_sm, fail_sm, skip_sm = _warm_sitemaps_phase()
        return (
            ok_p + ok_e + ok_em + ok_l + ok_r + ok_sm,
            fail_p + fail_e + fail_em + fail_l + fail_r + fail_sm,
            skip_e + skip_em + skip_l + skip_r + skip_sm,
        )

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

    # Skip mode: pula CNPJs ja cacheados conforme WARM_SKIP_RECENT_HOURS.
    # Mesma logica de cidades — reusa _filter_cached_munis (generico em
    # query_id e lista de keys).
    cnpjs, skipped_resume = _filter_cached_munis(
        "EMPRESA_PERFIL", all_cnpjs
    )
    if skipped_resume > 0:
        print(
            f"[empresas] {_skip_mode_label()}: {skipped_resume} ja cacheadas, "
            f"processando {len(cnpjs)} restantes."
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
                _effective_qid(EMPRESA_MUN_CACHE_QID),
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
    # Mesma logica: usa constante canonica em vez de literal.
    from web.routes.empresa import CACHE_QUERY_ID_MUN as _EMPRESA_MUN_QID
    _record_shadow_result(_EMPRESA_MUN_QID, ok, fail)
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
            f"[empresas-mun] {_skip_mode_label()}: {skipped_resume} ja "
            f"cacheados, processando {len(remaining_keys)} restantes."
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


# ─────────────────────────────────────────────────────────────────────────
# Licitacoes — warm /licitacao/<mun>/<ano>/<ug>/<mod-num>
# ─────────────────────────────────────────────────────────────────────────


def _warm_licitacoes_phase() -> tuple[int, int, int]:
    """Fase de warming de licitacoes. Cada licitacao qualificada (>=1
    proponente PJ) vira uma pagina.

    Returns: (ok, fail, skipped). skipped = ja cacheados (resume) +
    licitacoes que nao retornaram dados (skip_nf).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from web.config import TIMEOUT_PROFILE_WARM
    from web.queries.licitacao import LICITACOES_QUALIFICADAS_PAGINATED
    from web.routes.licitacao import (
        CACHE_QUERY_ID as LIC_CACHE_QID,
        LicitacaoNotFoundError,
        _build_cache_key,
        _build_mod_num_slug,
        compute_licitacao_dict,
    )
    from web.utils.slug import municipio_slug as _mun_slug, numero_slug as _num_slug

    print("--- Licitacoes: enumerando qualificadas ---")
    _WARM_LIC_LIMIT = 1000000  # Limite defensivo de fetch in-memory.
    boot = psycopg2.connect(DSN)
    boot.autocommit = True
    all_lics: list[tuple[str, int, str, str, str, str]] = []
    try:
        with boot.cursor() as cur:
            cur.execute(
                LICITACOES_QUALIFICADAS_PAGINATED,
                {"limit": _WARM_LIC_LIMIT, "offset": 0},
            )
            for municipio, ano, codigo_ug, descricao_ug, modalidade, numero in cur.fetchall():
                if not (municipio and ano and codigo_ug and modalidade and numero):
                    continue
                all_lics.append((
                    str(municipio), int(ano), str(codigo_ug),
                    str(descricao_ug or ""), str(modalidade), str(numero),
                ))
    finally:
        boot.close()

    # Detecta truncamento silencioso (S Opus PR #108) — se a base crescer
    # alem do LIMIT, warmer perderia linhas sem aviso. Loga error e prossegue
    # com o subset (melhor warm parcial do que crash).
    if len(all_lics) >= _WARM_LIC_LIMIT:
        print(
            f"::error::[licitacoes] Fetch truncado em {_WARM_LIC_LIMIT}. "
            f"Base de licitacoes cresceu — adapte pra streaming/paginar.",
            flush=True,
        )

    if not all_lics:
        print("[licitacoes] Nenhuma qualificada. Skipping.")
        return 0, 0, 0

    # Constroi keys canonicas (com slugs) pra checar cache
    lic_by_key: dict[str, tuple] = {}
    keys: list[str] = []
    for municipio, ano, codigo_ug, descricao_ug, modalidade, numero in all_lics:
        mun_slug = _mun_slug(municipio)
        if not mun_slug:
            continue
        ug_slug = _num_slug(descricao_ug) or "prefeitura"
        mod_num_slug = _build_mod_num_slug(modalidade, numero)
        if not mod_num_slug:
            continue
        key = _build_cache_key(mun_slug, ano, ug_slug, mod_num_slug)
        lic_by_key[key] = (municipio, ano, codigo_ug, modalidade, numero)
        keys.append(key)

    if not keys:
        return 0, 0, 0

    remaining_keys, skipped_resume = _filter_cached_munis(LIC_CACHE_QID, keys)
    if skipped_resume > 0:
        print(
            f"[licitacoes] {_skip_mode_label()}: {skipped_resume} ja cacheadas, "
            f"processando {len(remaining_keys)} restantes."
        )

    if not remaining_keys:
        return 0, 0, skipped_resume

    from web import db as web_db
    web_db.init_pool()

    def _warm_one(key: str) -> tuple[bool, str | None]:
        try:
            municipio, ano, codigo_ug, modalidade, numero = lic_by_key[key]
            data = compute_licitacao_dict(
                municipio, ano, codigo_ug, modalidade, numero,
                timeout_sec=TIMEOUT_PROFILE_WARM,
            )
            conn = _thread_conn()
            with conn.cursor() as cur:
                _upsert(
                    cur,
                    _effective_qid(LIC_CACHE_QID),
                    key,
                    ["payload"],
                    [[data]],
                )
            conn.commit()
            return True, None
        except LicitacaoNotFoundError as e:
            return False, f"not_found:{e}"
        except Exception as e:
            try:
                _thread_conn().rollback()
            except Exception:
                pass
            return False, f"compute_failed:{str(e).splitlines()[0]}"

    total = len(remaining_keys)
    print(
        f"[licitacoes] Warming {total} licitacoes em {PARALLEL_WORKERS} workers...",
        flush=True,
    )
    ok = fail = skipped_nf = 0
    t0 = time.time()
    try:
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
            futures = {ex.submit(_warm_one, k): k for k in remaining_keys}
            done = 0
            for fut in as_completed(futures):
                done += 1
                try:
                    success, msg = fut.result()
                except Exception as e:
                    success, msg = False, f"future_exception:{e}"
                if success:
                    ok += 1
                elif msg and msg.startswith("not_found:"):
                    skipped_nf += 1
                else:
                    fail += 1
                if done % 200 == 0:
                    elapsed = time.time() - t0
                    rate = done / elapsed if elapsed > 0 else 0
                    eta = (total - done) / rate if rate > 0 else 0
                    print(
                        f"[licitacoes] {done}/{total} "
                        f"({ok} ok, {fail} fail, {skipped_nf} not_found) — "
                        f"{rate:.1f}/s, eta {eta/60:.1f}min",
                        flush=True,
                    )
    finally:
        try:
            web_db.close_pool()
        except Exception:
            pass

    elapsed = time.time() - t0
    print(
        f"[licitacoes] Completo: {ok} ok, {fail} fail, {skipped_nf} not_found "
        f"({elapsed/60:.1f}min)",
        flush=True,
    )
    _record_shadow_result(LIC_CACHE_QID, ok, fail)
    return ok, fail, skipped_resume + skipped_nf


# ─────────────────────────────────────────────────────────────────────────
# Cidade Resumo Mensal — warm /cidade/<slug>/<yyyy>-<mm>
# ─────────────────────────────────────────────────────────────────────────


def _warm_cidade_resumo_phase() -> tuple[int, int, int]:
    """Fase de warming de resumo mensal de cidade. ~14k paginas
    (237 munis × ~60 meses).

    Returns: (ok, fail, skipped).
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from web.config import TIMEOUT_PROFILE_WARM
    from web.queries.cidade_resumo import CIDADE_RESUMO_QUALIFICADOS_LIST
    from web.routes.cidade import CACHE_QUERY_ID_RESUMO, _build_resumo_cache_key
    from web.routes.cidade_resumo_compute import (
        CidadeResumoEmpty,
        compute_cidade_resumo_dict,
    )
    from web.utils.slug import municipio_slug as _mun_slug

    print("--- Cidade-resumo: enumerando (mun, ano, mes) qualificados ---")
    boot = psycopg2.connect(DSN)
    boot.autocommit = True
    all_triples: list[tuple[str, int, int]] = []
    try:
        with boot.cursor() as cur:
            cur.execute(CIDADE_RESUMO_QUALIFICADOS_LIST)
            for municipio, ano, mes, _qtd in cur.fetchall():
                if not municipio or not ano or not mes:
                    continue
                all_triples.append((str(municipio), int(ano), int(mes)))
    finally:
        boot.close()

    if not all_triples:
        print("[cidade-resumo] Nenhum (mun, ano, mes) qualificado. Skipping.")
        return 0, 0, 0

    triple_by_key: dict[str, tuple[str, int, int]] = {}
    keys: list[str] = []
    for municipio, ano, mes in all_triples:
        mun_slug = _mun_slug(municipio)
        if not mun_slug:
            continue
        key = _build_resumo_cache_key(mun_slug, ano, mes)
        triple_by_key[key] = (municipio, ano, mes)
        keys.append(key)

    if not keys:
        return 0, 0, 0

    remaining_keys, skipped_resume = _filter_cached_munis(CACHE_QUERY_ID_RESUMO, keys)
    if skipped_resume > 0:
        print(
            f"[cidade-resumo] {_skip_mode_label()}: {skipped_resume} ja "
            f"cacheados, processando {len(remaining_keys)} restantes."
        )

    if not remaining_keys:
        return 0, 0, skipped_resume

    from web import db as web_db
    web_db.init_pool()

    def _warm_one(key: str) -> tuple[bool, str | None]:
        try:
            municipio, ano, mes = triple_by_key[key]
            data = compute_cidade_resumo_dict(
                municipio, ano, mes,
                timeout_sec=TIMEOUT_PROFILE_WARM,
            )
            conn = _thread_conn()
            with conn.cursor() as cur:
                _upsert(
                    cur,
                    _effective_qid(CACHE_QUERY_ID_RESUMO),
                    key,
                    ["payload"],
                    [[data]],
                )
            conn.commit()
            return True, None
        except CidadeResumoEmpty as e:
            return False, f"empty:{e}"
        except Exception as e:
            try:
                _thread_conn().rollback()
            except Exception:
                pass
            return False, f"compute_failed:{str(e).splitlines()[0]}"

    total = len(remaining_keys)
    print(
        f"[cidade-resumo] Warming {total} (mun, ano, mes) em {PARALLEL_WORKERS} workers...",
        flush=True,
    )
    ok = fail = skipped_empty = 0
    t0 = time.time()
    try:
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as ex:
            futures = {ex.submit(_warm_one, k): k for k in remaining_keys}
            done = 0
            for fut in as_completed(futures):
                done += 1
                try:
                    success, msg = fut.result()
                except Exception as e:
                    success, msg = False, f"future_exception:{e}"
                if success:
                    ok += 1
                elif msg and msg.startswith("empty:"):
                    skipped_empty += 1
                else:
                    fail += 1
                if done % 200 == 0:
                    elapsed = time.time() - t0
                    rate = done / elapsed if elapsed > 0 else 0
                    eta = (total - done) / rate if rate > 0 else 0
                    print(
                        f"[cidade-resumo] {done}/{total} "
                        f"({ok} ok, {fail} fail, {skipped_empty} empty) — "
                        f"{rate:.1f}/s, eta {eta/60:.1f}min",
                        flush=True,
                    )
    finally:
        try:
            web_db.close_pool()
        except Exception:
            pass

    elapsed = time.time() - t0
    print(
        f"[cidade-resumo] Completo: {ok} ok, {fail} fail, {skipped_empty} empty "
        f"({elapsed/60:.1f}min)",
        flush=True,
    )
    _record_shadow_result(CACHE_QUERY_ID_RESUMO, ok, fail)
    return ok, fail, skipped_resume + skipped_empty


# ─────────────────────────────────────────────────────────────────────────
# _warm_sitemaps_phase — popula web_cache (query_id=SITEMAP_XML) com os
# XMLs pre-gerados. Resolve o problema do GSC reportar "Couldn't fetch"
# quando primeiro hit pos-restart do cruza-web bate em build live > 30s.
#
# Naming convention das keys (rebase 2026-05-19):
#   - '<scope>-urlset'       -> sitemap unico (sem shards)
#   - '<scope>-shard:N'      -> shard N de um sitemap shardado
#   - 'root-index'           -> sitemap-index top-level que agrega tudo
#
# Keys cacheadas:
#   - 'root-index'                       -> /sitemap.xml
#   - 'cidades-urlset'                   -> /sitemap-cidades.xml
#   - 'empresas-shard:N'                 -> /sitemap-empresas-N.xml
#   - 'empresas-municipios-shard:N'      -> /sitemap-empresas-municipios-N.xml
#   - 'licitacoes-shard:N'               -> /sitemap-licitacoes-N.xml (PR #108)
#   - 'cidade-resumo-urlset'             -> /sitemap-cidade-resumo.xml (PR #108)
# ─────────────────────────────────────────────────────────────────────────


def _warm_sitemaps_phase() -> tuple[int, int, int]:
    """Pre-gera todos os sitemaps e armazena em web_cache (query_id=SITEMAP_XML).

    Rapido (~30-60s pra ~40 entries em 145K empresas + 775K pares
    + N licitacoes + 14K cidade-mes). Sempre roda (ignora SKIP_RECENT_HOURS)
    — sitemaps sao baratos e essenciais pra primeiro hit pos-restart nao
    quebrar.

    DB pool: init_pool() + close_pool() balanceados em try/finally.
    Sem close_pool, daemon mode vazaria conexoes a cada ciclo (Opus 4.7
    P1 PR #85). As outras phases (_warm_empresas_phase,
    _warm_empresas_municipios_phase) seguem o mesmo padrao.

    Pruning: ao final, remove entries em web_cache cuja key nao foi
    escrita neste ciclo (i.e., shards past-end ou tipo removido). Usa
    expected_keys (built before write) nao written_keys, pra nao deletar
    entries por causa de falhas transientes de write. skip_prune_prefixes
    protege scopes onde a contagem falhou (nao conhecemos expected, nao
    deletamos nada do scope).
    """
    print("--- Sitemaps: pre-gerando XML pra web_cache ---", flush=True)
    t0 = time.time()

    try:
        from web import db as web_db
        web_db.init_pool()
    except Exception as exc:
        print(f"  ERRO init pool DB: {exc}", flush=True)
        return 0, 1, 0

    # Origin canonico — sem Request object, ler de env ou hardcode.
    # transparenciapb.org eh o unico host atual; futuras mudancas devem
    # vir via SITE_ORIGIN env.
    origin = os.environ.get(
        "SITE_ORIGIN", "https://transparenciapb.org"
    ).rstrip("/")

    # Forca flags ON pra incluir TODOS os shards no index (mesmo que o
    # processo cruza-web em prod tenha drop-in apenas pra empresas — aqui
    # pre-geramos tudo, route decide quais expor).
    prev_emp = os.environ.get("SITEMAP_INCLUDE_EMPRESAS")
    prev_lic = os.environ.get("SITEMAP_INCLUDE_LICITACOES")
    prev_res = os.environ.get("SITEMAP_INCLUDE_CIDADE_RESUMO")
    os.environ["SITEMAP_INCLUDE_EMPRESAS"] = "1"
    os.environ["SITEMAP_INCLUDE_LICITACOES"] = "1"
    os.environ["SITEMAP_INCLUDE_CIDADE_RESUMO"] = "1"

    ok = 0
    fail = 0
    expected_keys: set[str] = set()       # Keys que ESPERAMOS escrever (pra prune)
    skip_prune_prefixes: set[str] = set()  # Scopes onde count falhou (no prune)

    try:
        from web.routes.seo import (
            EMPRESA_SHARD_SIZE,
            LICITACAO_SHARD_SIZE,
            _build_cidade_resumo_sitemap,
            _build_cidades_sitemap,
            _build_empresas_municipios_shard_sitemap,
            _build_empresas_shard_sitemap,
            _build_licitacoes_shard_sitemap,
            _build_sitemap_index,
            _cidade_resumo_qualificados,
            _empresas_municipios_qualificadas_count,
            _empresas_qualificadas_count,
            _licitacoes_qualificadas_count,
            _sitemap_pg_write,
        )

        # 1. Index (root-index)
        expected_keys.add("root-index")
        try:
            xml = _build_sitemap_index(origin)
            if "/sitemap-empresas-" in xml:
                if _sitemap_pg_write("root-index", xml):
                    ok += 1
                    print(f"  ok  root-index ({len(xml)} bytes)", flush=True)
                else:
                    fail += 1
                    print("  fail  root-index (pg write retornou False)", flush=True)
            else:
                fail += 1
                print("  fail  root-index (sem empresas shards — DB falhou?)", flush=True)
        except Exception as exc:
            fail += 1
            print(f"  fail  root-index: {exc}", flush=True)

        # 2. Cidades (cidades-urlset)
        expected_keys.add("cidades-urlset")
        try:
            xml = _build_cidades_sitemap(origin)
            cidades_n = xml.count("/cidade/")
            if cidades_n >= 100:
                if _sitemap_pg_write("cidades-urlset", xml):
                    ok += 1
                    print(f"  ok  cidades-urlset ({cidades_n} URLs)", flush=True)
                else:
                    fail += 1
                    print("  fail  cidades-urlset (pg write retornou False)", flush=True)
            else:
                fail += 1
                print(f"  fail  cidades-urlset ({cidades_n} URLs — < 100)", flush=True)
        except Exception as exc:
            fail += 1
            print(f"  fail  cidades-urlset: {exc}", flush=True)

        # 3. Empresas shards (empresas-shard:N)
        try:
            total_emp = _empresas_qualificadas_count()
            num_shards_emp = math.ceil(total_emp / EMPRESA_SHARD_SIZE) if total_emp > 0 else 0
            print(f"  Empresas: total={total_emp:,} shards={num_shards_emp}", flush=True)
            for n in range(1, num_shards_emp + 1):
                key = f"empresas-shard:{n}"
                expected_keys.add(key)
                try:
                    xml = _build_empresas_shard_sitemap(origin, n)
                    urls_n = xml.count("/empresa/")
                    if urls_n > 0:
                        if _sitemap_pg_write(key, xml):
                            ok += 1
                            print(f"  ok  {key} ({urls_n} URLs)", flush=True)
                        else:
                            fail += 1
                            print(f"  fail  {key} (pg write retornou False)", flush=True)
                    else:
                        fail += 1
                        print(f"  fail  {key} (vazio)", flush=True)
                except Exception as exc:
                    fail += 1
                    print(f"  fail  {key}: {exc}", flush=True)
        except Exception as exc:
            fail += 1
            skip_prune_prefixes.add("empresas-shard:")
            print(f"  fail  contar empresas: {exc} (pruning de empresas-shard: pulado)", flush=True)

        # 4. Empresas × Municipios shards (empresas-municipios-shard:N)
        try:
            total_mun = _empresas_municipios_qualificadas_count()
            num_shards_mun = math.ceil(total_mun / EMPRESA_SHARD_SIZE) if total_mun > 0 else 0
            print(f"  Empresas-Mun: total={total_mun:,} shards={num_shards_mun}", flush=True)
            for n in range(1, num_shards_mun + 1):
                key = f"empresas-municipios-shard:{n}"
                expected_keys.add(key)
                try:
                    xml = _build_empresas_municipios_shard_sitemap(origin, n)
                    urls_n = xml.count("/empresa/")
                    if urls_n > 0:
                        if _sitemap_pg_write(key, xml):
                            ok += 1
                            print(f"  ok  {key} ({urls_n} URLs)", flush=True)
                        else:
                            fail += 1
                            print(f"  fail  {key} (pg write retornou False)", flush=True)
                    else:
                        fail += 1
                        print(f"  fail  {key} (vazio)", flush=True)
                except Exception as exc:
                    fail += 1
                    print(f"  fail  {key}: {exc}", flush=True)
        except Exception as exc:
            fail += 1
            skip_prune_prefixes.add("empresas-municipios-shard:")
            print(f"  fail  contar empresas-municipios: {exc} (pruning pulado)", flush=True)

        # 5. Licitacoes shards (licitacoes-shard:N) — alinhado com main PR #108
        try:
            total_lic = _licitacoes_qualificadas_count()
            num_shards_lic = math.ceil(total_lic / LICITACAO_SHARD_SIZE) if total_lic > 0 else 0
            print(f"  Licitacoes: total={total_lic:,} shards={num_shards_lic}", flush=True)
            for n in range(1, num_shards_lic + 1):
                key = f"licitacoes-shard:{n}"
                expected_keys.add(key)
                try:
                    xml = _build_licitacoes_shard_sitemap(origin, n)
                    urls_n = xml.count("/licitacao/")
                    if urls_n > 0:
                        if _sitemap_pg_write(key, xml):
                            ok += 1
                            print(f"  ok  {key} ({urls_n} URLs)", flush=True)
                        else:
                            fail += 1
                            print(f"  fail  {key} (pg write retornou False)", flush=True)
                    else:
                        fail += 1
                        print(f"  fail  {key} (vazio)", flush=True)
                except Exception as exc:
                    fail += 1
                    print(f"  fail  {key}: {exc}", flush=True)
        except Exception as exc:
            fail += 1
            skip_prune_prefixes.add("licitacoes-shard:")
            print(f"  fail  contar licitacoes: {exc} (pruning pulado)", flush=True)

        # 6. Cidade resumo urlset (cidade-resumo-urlset)
        expected_keys.add("cidade-resumo-urlset")
        try:
            qualificados = _cidade_resumo_qualificados()
            total_res = len(qualificados)
            print(f"  Cidade-resumo: total={total_res:,}", flush=True)
            if total_res > 0:
                xml = _build_cidade_resumo_sitemap(origin)
                urls_n = xml.count("/cidade/")
                if urls_n > 0:
                    if _sitemap_pg_write("cidade-resumo-urlset", xml):
                        ok += 1
                        print(f"  ok  cidade-resumo-urlset ({urls_n} URLs)", flush=True)
                    else:
                        fail += 1
                        print("  fail  cidade-resumo-urlset (pg write retornou False)", flush=True)
                else:
                    fail += 1
                    print("  fail  cidade-resumo-urlset (vazio)", flush=True)
        except Exception as exc:
            fail += 1
            print(f"  fail  cidade-resumo-urlset: {exc}", flush=True)

        # ─── Prune ─── Remove entries cujo key nao esta em expected_keys
        # (i.e., shards past-end ou tipo removido). USA expected_keys (built
        # before write), nao written_keys: falhas transientes de write nao
        # devem deletar entries previamente boas.
        # skip_prune_prefixes protege scopes onde contagem falhou — sem
        # expected_keys confiavel pra esse scope, nao deletamos nada dele.
        # `if expected_keys` guarda contra prune destrutivo se todos os
        # scopes falharem (warm catastrofico).
        if expected_keys:
            try:
                with web_db.get_conn() as conn:
                    conn.autocommit = True
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT municipio FROM web_cache WHERE query_id = %s",
                            ("SITEMAP_XML",),
                        )
                        existing = {row[0] for row in cur.fetchall()}
                        to_delete = []
                        for k in existing:
                            if k in expected_keys:
                                continue
                            # Skip se algum prefix esta protegido
                            if any(k.startswith(p) for p in skip_prune_prefixes):
                                continue
                            to_delete.append(k)
                        if to_delete:
                            cur.execute(
                                "DELETE FROM web_cache WHERE query_id = %s AND municipio = ANY(%s)",
                                ("SITEMAP_XML", to_delete),
                            )
                            print(
                                f"  prune  removidas {len(to_delete)} entries stale: "
                                f"{', '.join(sorted(to_delete)[:5])}{'...' if len(to_delete) > 5 else ''}",
                                flush=True,
                            )
            except Exception as exc:
                print(f"  warn  prune falhou: {exc}", flush=True)

    finally:
        # Restaura env vars (preserva drop-ins reais do systemd se houver).
        for var, prev in [
            ("SITEMAP_INCLUDE_EMPRESAS", prev_emp),
            ("SITEMAP_INCLUDE_LICITACOES", prev_lic),
            ("SITEMAP_INCLUDE_CIDADE_RESUMO", prev_res),
        ]:
            if prev is not None:
                os.environ[var] = prev
            else:
                os.environ.pop(var, None)
        # Fecha pool DB pra evitar leak em daemon mode (Opus 4.7 P1 PR #85).
        try:
            web_db.close_pool()
        except Exception:
            pass

    elapsed = time.time() - t0
    print(
        f"--- Sitemaps: {ok} ok, {fail} fail em {elapsed:.0f}s ---",
        flush=True,
    )
    return ok, fail, 0


if __name__ == "__main__":
    main()
