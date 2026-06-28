"""Refresh de Materialized Views + tabelas _tmp_ apos ETL incremental.

Roda como step final do `etl_phase=incremental` no deploy.yml quando uma
source que tem MVs dependentes foi processada (atualmente: bolsa_familia).

Por que existe:
- O framework incremental P1-P6 (etl/incremental/) e generico: nao sabe
  quais MVs dependem de cada source. Atualizar bolsa_familia sem refresh
  deixa mv_pessoa_pb / mv_servidor_pb_risco / mv_municipio_pb_kpi_score
  com dados velhos.
- Refresh manual via deploy.yml inputs e fragil (esquecivel + drift).
- Centralizando aqui: cada source que vira incremental registra sua
  refresh fn em SOURCE_REFRESH_FNS. Step do deploy chama com --source X.

Por que hard-fail:
- Warm cache subsequente leria dados velhos se MVs nao refrescaram.
- Site continua servindo a MV antiga (que existe) ate refresh terminar —
  preferimos falhar o deploy do que entregar warm cache stale.

Por que autocommit toggle:
- REFRESH MATERIALIZED VIEW CONCURRENTLY exige rodar FORA de transacao
  explicita (mesmo motivo de CREATE INDEX CONCURRENTLY). Padrao
  etl/10_indices.py:32-36.

CLI:
    python -m etl.refresh_post_incremental --source bolsa_familia
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Callable

import psycopg2

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────

def _run_sql(conn, label: str, sql: str, *, autocommit: bool = False) -> float:
    """Executa SQL. Se autocommit=True, toggle conn.autocommit no escopo.

    Retorna tempo gasto (segundos).
    """
    prev = conn.autocommit
    if autocommit and not prev:
        conn.commit()  # encerra qualquer txn pendente
        conn.autocommit = True
    t0 = time.time()
    try:
        with conn.cursor() as cur:
            cur.execute(sql)
        if not conn.autocommit:
            conn.commit()
        dt = time.time() - t0
        logger.info("%s OK em %.1fs", label, dt)
        return dt
    finally:
        if autocommit and not prev:
            conn.autocommit = prev


def _read_sql_file(name: str) -> str:
    path = Path(__file__).resolve().parents[1] / "sql" / name
    return path.read_text(encoding="utf-8")


def populate_nk_md5_bolsa_familia(conn, batch_size: int = 100_000) -> None:
    """Popula _nk_md5 nas rows legacy de bolsa_familia em batches.

    Workaround para PG 16: PROCEDURE com COMMIT interno falha quando chamada
    via psql -c "CALL ..." (psql wrappa em transacao implicita). psycopg2
    com autocommit=True permite COMMIT entre batches sem problema.

    Idempotente: WHERE _nk_md5 IS NULL. Pode ser interrompido e re-rodado.

    Cria partial index temporario para acelerar batches (Opus 4.7-high
    review MEDIUM-4 — sem isso, o WHERE IS NULL faz seq scan O(n) por
    batch, gerando trabalho quadratico O(n²/batch) no total).
    """
    logger.info("populate_nk_md5_bolsa_familia: BATCH_SIZE=%d", batch_size)
    prev_autocommit = conn.autocommit
    conn.autocommit = True
    t0 = time.time()
    total = 0
    try:
        with conn.cursor() as cur:
            # Criar partial index ANTES do loop (CONCURRENTLY exige autocommit).
            # Idempotente (IF NOT EXISTS). Sera dropado no final.
            logger.info("creating temporary partial index for populate speedup...")
            cur.execute("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS _tmp_idx_bf_nk_md5_null
                ON bolsa_familia (id) WHERE _nk_md5 IS NULL
            """)
            # ANALYZE para o planner usar o partial index nos batches seguintes.
            cur.execute("ANALYZE bolsa_familia")

            while True:
                cur.execute("""
                    UPDATE bolsa_familia SET _nk_md5 = etl_admin.row_hash_md5(
                        coalesce(mes_competencia, ''),
                        coalesce(mes_referencia, ''),
                        coalesce(uf, ''),
                        coalesce(cd_municipio_siafi, ''),
                        coalesce(nm_municipio, ''),
                        coalesce(cpf_favorecido, ''),
                        coalesce(nis_favorecido, ''),
                        coalesce(nm_favorecido, ''),
                        coalesce(valor_parcela::text, '')
                    )
                    WHERE id IN (
                        SELECT id FROM bolsa_familia
                        WHERE _nk_md5 IS NULL ORDER BY id LIMIT %s
                    )
                """, (batch_size,))
                n = cur.rowcount
                if n == 0:
                    break
                total += n
                logger.info(
                    "populate _nk_md5: total %s rows (%.0fs)",
                    f"{total:,}", time.time() - t0,
                )

            # Drop partial index — nao serve apos populate completo.
            logger.info("dropping temporary partial index...")
            cur.execute("DROP INDEX IF EXISTS _tmp_idx_bf_nk_md5_null")
    finally:
        conn.autocommit = prev_autocommit
    logger.info("populate_nk_md5_bolsa_familia: DONE — %d rows em %.0fs",
                total, time.time() - t0)


# ──────────────────────────────────────────────────────────────────────────
# TCE-PB: synthetic md5 NK (ADR-0014)
# ──────────────────────────────────────────────────────────────────────────
# Tabelas TCE-PB que usam _nk_md5 (sql/42 + sql/42z). A funcao de hash
# etl_admin.nk_md5_<tabela>_row e single source of truth (trigger E populate
# chamam a mesma), evitando drift.
TCE_PB_MD5_TABLES: tuple[str, ...] = (
    "tce_pb_despesa",
    "tce_pb_servidor",
    "tce_pb_licitacao",
    "tce_pb_receita",
)


def _populate_nk_md5_table(conn, table: str, batch_size: int = 200_000) -> None:
    """Popula _nk_md5 em batches numa tabela TCE-PB via row-function SQL.

    Reusa etl_admin.nk_md5_<table>_row (mesma funcao do trigger) — zero drift
    entre rows novas (trigger) e legacy (populate).

    Batching por FAIXA DE id (PK) — cada batch faz UPDATE de um range
    [lo, lo+batch) filtrando _nk_md5 IS NULL. Cada faixa e escaneada UMA vez via
    o indice da PK, sem depender de um indice parcial que encolhe.

    Por que NAO usar `WHERE _nk_md5 IS NULL ORDER BY id LIMIT N` (padrao BF):
    em tabelas grandes (despesa 16M) cada UPDATE deixa dead tuples no indice
    parcial `WHERE _nk_md5 IS NULL`; como autovacuum nao acompanha o ritmo, o
    Index-Only-Scan passa a pular milhoes de entradas mortas -> tempo por batch
    cresce (degradacao quase-quadratica observada: 44s -> 109s/batch). A faixa
    de id evita isso (escaneia cada range uma vez).

    psycopg2 autocommit=True: COMMIT entre batches (psql -c/-f wrappa em
    transacao implicita e o COMMIT-em-PROCEDURE falharia no PG 16).
    Idempotente/resumivel: o filtro _nk_md5 IS NULL pula faixas ja populadas.
    """
    if table not in TCE_PB_MD5_TABLES:
        raise ValueError(f"tabela TCE-PB desconhecida: {table!r}")
    hash_fn = f"etl_admin.nk_md5_{table}_row"
    logger.info("populate _nk_md5 %s: BATCH_SIZE=%d (id-range)", table, batch_size)
    prev_autocommit = conn.autocommit
    conn.autocommit = True
    t0 = time.time()
    total = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT min(id), max(id) FROM {table} WHERE _nk_md5 IS NULL"
            )
            lo, hi = cur.fetchone()
            if lo is None:
                logger.info("populate _nk_md5 %s: nada a fazer (ja populado)", table)
                return

            cur_id = lo
            while cur_id <= hi:
                cur.execute(
                    f"UPDATE {table} t SET _nk_md5 = {hash_fn}(t) "
                    f"WHERE t.id >= %s AND t.id < %s AND t._nk_md5 IS NULL",
                    (cur_id, cur_id + batch_size),
                )
                n = cur.rowcount
                total += n
                cur_id += batch_size
                if n:
                    logger.info(
                        "populate _nk_md5 %s: ~%s/%s ids, %s rows (%.0fs)",
                        table, f"{min(cur_id, hi + 1):,}", f"{hi:,}",
                        f"{total:,}", time.time() - t0,
                    )
    finally:
        conn.autocommit = prev_autocommit
    logger.info(
        "populate _nk_md5 %s: DONE — %d rows em %.0fs",
        table, total, time.time() - t0,
    )


def populate_nk_md5_tce_pb(conn, batch_size: int = 100_000) -> None:
    """Popula _nk_md5 em todas as 4 tabelas TCE-PB (despesa/servidor/licitacao/
    receita). Chamado pelo deploy entre sql/42 e sql/42z."""
    for table in TCE_PB_MD5_TABLES:
        _populate_nk_md5_table(conn, table, batch_size=batch_size)


# ──────────────────────────────────────────────────────────────────────────
# Refresh por source
# ──────────────────────────────────────────────────────────────────────────

def refresh_for_bolsa_familia(conn) -> None:
    """Refresh das MVs que dependem de bolsa_familia.

    Ordem (Layer 1 -> tmp -> Layer 2):
      1. ANALYZE bolsa_familia (planner stats — barato e necessario)
      2. REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pessoa_pb (L1)
      3. _tmp_bf via TRUNCATE+INSERT consumindo sql/41c_tmp_bf_body.sql
         (DROP _tmp_bf falha — mv_servidor_pb_risco depende por OID)
      4. mv_servidor_pb_risco: REFRESH CONCURRENTLY (usa _tmp_bf novo)
      5. mv_municipio_pb_kpi_score: REFRESH CONCURRENTLY (depende de
         mv_pessoa_pb agregado)

    Hard-fail: qualquer step lanca → script aborta com exit code 1.
    """
    logger.info("=" * 60)
    logger.info("refresh_for_bolsa_familia: iniciando")
    logger.info("=" * 60)

    total_t0 = time.time()

    # 1. ANALYZE — refresh planner stats antes de queries pesadas.
    _run_sql(conn, "ANALYZE bolsa_familia", "ANALYZE bolsa_familia")

    # 2. mv_pessoa_pb (L1): SUM/COUNT bolsa_familia por cpf_digitos_6 + nome.
    _run_sql(
        conn,
        "REFRESH mv_pessoa_pb",
        "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pessoa_pb",
        autocommit=True,
    )

    # 3. _tmp_bf rebuild via TRUNCATE+INSERT atomic.
    # Body extraido para sql/41c_tmp_bf_body.sql — drift com sql/12_views.sql
    # quebra esta logica (validado em smoke tests).
    body = _read_sql_file("41c_tmp_bf_body.sql")
    # Strip statement terminator do body antes de injetar — evita ambiguidade
    # com concatenacoes futuras (Opus 4.7-high review LOW-5).
    body_stripped = body.rstrip().rstrip(";").rstrip()
    # TRUNCATE + INSERT atomic via transacao implicita do psycopg2
    # (autocommit=False default). Os dois statements executam em UMA
    # transacao; AccessExclusiveLock do TRUNCATE eh mantido ate o
    # commit() em _run_sql. mv_servidor_pb_risco nao vai ver estado
    # intermediario.
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE _tmp_bf")
        cur.execute(f"INSERT INTO _tmp_bf {body_stripped}")
    conn.commit()
    logger.info("_tmp_bf TRUNCATE + INSERT OK")

    # 4. mv_servidor_pb_risco: depende de _tmp_bf novo.
    # IMPORTANTE: a MV nao suporta REFRESH "limpo" porque _tmp_bf nao tem
    # UNIQUE INDEX (foi criado via CREATE TABLE AS, sem PK). Mas
    # mv_servidor_pb_risco TEM idx_mv_srv_cpf_nome UNIQUE → suporta
    # REFRESH CONCURRENTLY.
    _run_sql(
        conn,
        "REFRESH mv_servidor_pb_risco",
        "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_servidor_pb_risco",
        autocommit=True,
    )

    # 5. mv_municipio_pb_kpi_score: agrega indicadores PB incluindo BF
    # (via mv_pessoa_pb). Validar dependencia em runtime via pg_depend
    # para nao quebrar silenciosamente se 12_views.sql for refatorado.
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT 1 FROM pg_depend d
                JOIN pg_class c1 ON c1.oid = d.refobjid
                JOIN pg_class c2 ON c2.oid = d.objid
                WHERE c1.relname = 'mv_pessoa_pb'
                  AND c2.relname = 'mv_municipio_pb_kpi_score'
            )
        """)
        depends = cur.fetchone()[0]
    if depends:
        _run_sql(
            conn,
            "REFRESH mv_municipio_pb_kpi_score",
            "REFRESH MATERIALIZED VIEW CONCURRENTLY mv_municipio_pb_kpi_score",
            autocommit=True,
        )
    else:
        logger.info("mv_municipio_pb_kpi_score nao depende de mv_pessoa_pb — skip.")

    total_dt = time.time() - total_t0
    logger.info("refresh_for_bolsa_familia: DONE em %.1fs (%.1f min)", total_dt, total_dt / 60)


# MVs PB que dependem DIRETAMENTE das tabelas tce_pb_*, em ordem L1 -> L2
# (sql/12_views.sql). _tmp_bf NAO e reconstruido aqui: reflete o estado atual
# de bolsa_familia, que nao muda num run TCE-PB.
#
# mv_rede_pb foi DELIBERADAMENTE excluida: e montada a partir das tabelas
# _tmp_rede_* (socio/fornecedor/servidor/credor/doador-campanha) que NAO sao
# reconstruidas aqui — um REFRESH apenas re-le _tmp_rede_* stale (no-op util) e,
# alem disso, mv_rede_pb nao tem UNIQUE INDEX (REFRESH CONCURRENTLY falharia).
_TCE_PB_MVS_L1 = (
    "mv_empresa_governo",
    "mv_servidor_pb_base",
    "mv_municipio_pb_risco",
    "mv_pessoa_pb",
)
_TCE_PB_MVS_L2 = (
    "mv_servidor_pb_risco",
    "mv_empresa_pb",
    "mv_municipio_pb_kpi_score",
    "mv_municipio_pb_mapa",
    "mv_q67_dated_pb",
)


def _refresh_mv_adaptive(conn, mv: str) -> None:
    """REFRESH de uma MV escolhendo o modo certo:
      - CONCURRENTLY se a MV tem UNIQUE INDEX (zero-downtime);
      - REFRESH simples (lock ACCESS EXCLUSIVE breve) se NAO tem (ex.:
        mv_q67_dated_pb em prod) — CONCURRENTLY exigiria UNIQUE INDEX e
        falharia;
      - skip + warning se a MV nao existe (drift entre ambientes).

    Erros reais de REFRESH propagam (hard-fail) — so o caso "sem unique index"
    e tratado, nao mascaramos falhas de dados.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM pg_class WHERE relname = %s AND relkind = 'm'", (mv,)
        )
        if cur.fetchone() is None:
            logger.warning("MV %s nao existe — skip refresh (drift?)", mv)
            return
        cur.execute(
            "SELECT bool_or(coalesce(i.indisunique, false)) "
            "FROM pg_index i JOIN pg_class c ON c.oid = i.indrelid "
            "WHERE c.relname = %s",
            (mv,),
        )
        has_unique = bool(cur.fetchone()[0])

    if has_unique:
        _run_sql(conn, f"REFRESH {mv} (CONCURRENTLY)",
                 f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv}", autocommit=True)
    else:
        logger.warning(
            "MV %s sem UNIQUE INDEX — REFRESH simples (lock breve, nao-concurrent)",
            mv,
        )
        _run_sql(conn, f"REFRESH {mv} (plain)",
                 f"REFRESH MATERIALIZED VIEW {mv}", autocommit=True)


def refresh_for_tce_pb(conn) -> None:
    """Refresh das MVs que dependem das tabelas TCE-PB (despesa/servidor/
    licitacao/receita), em ordem L1 -> L2.

    Hard-fail: qualquer REFRESH que lance (erro real) aborta o script (exit 1) —
    preferimos falhar o deploy a deixar o warm/shadow rewarm subsequente ler MV
    stale. MVs sem UNIQUE INDEX usam REFRESH simples (ver _refresh_mv_adaptive).

    NOTA: mv_empresa_municipio_pagantes (sitemap) e refrescada a parte por
    etl.22_mv_sitemap no proprio step do deploy.
    """
    logger.info("=" * 60)
    logger.info("refresh_for_tce_pb: iniciando (L1 -> L2)")
    logger.info("=" * 60)
    total_t0 = time.time()

    # ANALYZE das tabelas base antes das queries pesadas das MVs.
    for table in TCE_PB_MD5_TABLES:
        _run_sql(conn, f"ANALYZE {table}", f"ANALYZE {table}")

    for mv in _TCE_PB_MVS_L1 + _TCE_PB_MVS_L2:
        _refresh_mv_adaptive(conn, mv)

    total_dt = time.time() - total_t0
    logger.info("refresh_for_tce_pb: DONE em %.1fs (%.1f min)", total_dt, total_dt / 60)


# ──────────────────────────────────────────────────────────────────────────
# Registry — fontes que tem refresh hooks
# ──────────────────────────────────────────────────────────────────────────

SOURCE_REFRESH_FNS: dict[str, Callable] = {
    "bolsa_familia": refresh_for_bolsa_familia,
    "tce_pb": refresh_for_tce_pb,
}


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Refresh MVs apos ETL incremental por source"
    )
    parser.add_argument(
        "--source",
        required=True,
        choices=sorted(SOURCE_REFRESH_FNS.keys()),
        help="Source registrada em SOURCE_REFRESH_FNS",
    )
    parser.add_argument(
        "--populate-only",
        action="store_true",
        help="So roda populate_nk_md5 (sem MV refresh). Usado entre sql/41 e "
             "sql/41z (bolsa_familia) ou sql/42 e sql/42z (tce_pb) no deploy.",
    )
    parser.add_argument(
        "--dsn",
        default=None,
        help="Override DSN (default: etl.config.DSN)",
    )
    args = parser.parse_args()

    if args.dsn is None:
        from etl.config import DSN
        args.dsn = DSN

    conn = psycopg2.connect(args.dsn)
    try:
        if args.populate_only:
            if args.source == "bolsa_familia":
                populate_nk_md5_bolsa_familia(conn)
            elif args.source == "tce_pb":
                populate_nk_md5_tce_pb(conn)
            else:
                logger.error(
                    "--populate-only so suporta source=bolsa_familia|tce_pb"
                )
                return 2
        else:
            fn = SOURCE_REFRESH_FNS[args.source]
            fn(conn)
    except Exception:
        logger.exception("refresh_for_%s FAILED", args.source)
        return 1
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
