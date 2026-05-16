"""Atomic MV swap framework — zero-downtime MV updates.

## Por que existe

`sql/12_views.sql` faz `DROP MATERIALIZED VIEW ... CASCADE` de TODAS as MVs
no inicio, depois recria tudo. Pra mudar UMA MV (ex: corrigir `mv_empresa_pb`
sem rebuildar `mv_municipio_pb_kpi_score`, `mv_servidor_pb_risco`, etc), o
DROP CASCADE atual:
- Derruba MVs nao-afetadas (downtime de 1-2h ate todas reconstruirem)
- For ca rodar `etl_phase=sql` no deploy (resize de VM, etc)
- Bloqueia trafego live durante o rebuild

Este modulo permite atualizar UMA MV (e suas views/MVs dependentes) com
**downtime de ~1s** (so a transacao de RENAME).

## Estrategia

1. **Build paralelo** (autocommit): cria `<mv>_swap` com a nova definicao
   em background. Trafego live continua na MV original.
2. **Snapshot de dependentes**: captura `pg_get_viewdef()` de todas as
   views (e MVs) que referenciam a MV original.
3. **Indexes**: o caller passa SQL com `CREATE INDEX ... ON <mv>_swap`.
4. **ANALYZE** na MV nova (stats frescas no momento do swap).
5. **Swap atomico em 1 transacao** (ACCESS EXCLUSIVE, dura <1s):
     - `DROP MATERIALIZED VIEW <mv> CASCADE` — drop velho + dependentes
     - `ALTER MV <mv>_swap RENAME TO <mv>` — promove novo
     - Renomeia indexes (sufixo _swap removido)
     - Recria cada view dependente com SQL capturado
     - Pra MVs dependentes: recria como MV vazia + agenda REFRESH
       (REFRESH dentro de transacao bloqueia uso concorrente)
6. **Fora da transacao**: roda `REFRESH MATERIALIZED VIEW` em cada MV
   dependente sequencialmente.

## Limitacoes

- **MVs dependentes**: durante o REFRESH pos-swap, MVs dependentes ficam
  vazias (rows=0). Site renderizado a partir delas serve dados degradados
  temporariamente. Pra MVs que alimentam fluxo critico, prefira atualizar
  ambas em um unico run com 2 invocations.
- **Indexes em deps**: indexes em MVs/views dependentes sao perdidos
  quando recriamos a definicao via `pg_get_viewdef`. Capturamos e
  recriamos via `pg_indexes`.
- **Permissoes**: requer privilegios pra DROP/CREATE/RENAME MVs +
  read em pg_depend/pg_rewrite/pg_class.

## Uso

CLI:

    python -m etl.mv_swap mv_empresa_pb deploy/mv_updates/mv_empresa_pb.sql

API:

    from etl.mv_swap import swap_materialized_view
    swap_materialized_view(
        "mv_empresa_pb",
        Path("deploy/mv_updates/mv_empresa_pb.sql").read_text(),
    )

## Formato do SQL de definicao

Arquivo deve conter:

    CREATE MATERIALIZED VIEW mv_empresa_pb_swap AS
    WITH ... SELECT ...;

    CREATE UNIQUE INDEX idx_mv_epb_cnpj_swap ON mv_empresa_pb_swap(cnpj_basico);
    CREATE INDEX idx_mv_epb_inativa_swap ON mv_empresa_pb_swap(...);
    ...

Convencao: todos os identifiers que sobreviverao ao swap usam sufixo
`_swap`; serao renomeados pelo framework removendo o sufixo.
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
import time
from pathlib import Path

from etl.db import get_conn

log = logging.getLogger("mv_swap")


def _capture_dependents(cur, mv_name: str) -> list[dict]:
    """Captura snapshot de views/MVs que referenciam `mv_name`.

    Retorna lista em ordem topologica (dependentes diretos primeiro),
    cada item:
      {
        "name": "v_risk_score_pb",
        "kind": "v" | "m",  # view ou matview
        "definition": "SELECT ... FROM mv_name ...",
        "indexes": [(index_name, index_def), ...],
      }
    """
    cur.execute(
        """
        WITH RECURSIVE deps AS (
            SELECT DISTINCT
                dependent.oid,
                dependent.relname,
                dependent.relkind,
                1 AS depth
            FROM pg_depend d
            JOIN pg_rewrite r ON d.objid = r.oid
            JOIN pg_class dependent ON r.ev_class = dependent.oid
            JOIN pg_class source ON d.refobjid = source.oid
            WHERE source.relname = %s
              AND dependent.relname <> %s
              AND dependent.relkind IN ('v', 'm')
            UNION ALL
            SELECT DISTINCT
                dependent.oid,
                dependent.relname,
                dependent.relkind,
                deps.depth + 1
            FROM deps
            JOIN pg_depend d ON d.refobjid = deps.oid
            JOIN pg_rewrite r ON d.objid = r.oid
            JOIN pg_class dependent ON r.ev_class = dependent.oid
            WHERE dependent.oid <> deps.oid
              AND dependent.relkind IN ('v', 'm')
        )
        SELECT relname, relkind, MAX(depth) AS depth
        FROM deps
        GROUP BY relname, relkind
        -- Order by MAX(depth) ASC: pra um dependente com multiplos paths
        -- (ex: B depende da MV diretamente E de A que tambem depende),
        -- precisamos recriar A antes de B. Usar MAX garante que B (depth 2
        -- via A) venha depois de A (depth 1). MIN(depth) ordenaria B como
        -- 1 e quebraria o recreate. Achado em GPT-5.5 review da PR #153.
        ORDER BY MAX(depth) ASC, relname
        """,
        (mv_name, mv_name),
    )
    rows = cur.fetchall()

    deps: list[dict] = []
    for name, kind, depth in rows:
        cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", (name,))
        viewdef = cur.fetchone()[0].rstrip().rstrip(";")
        cur.execute(
            """
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = %s
            """,
            (name,),
        )
        indexes = list(cur.fetchall())
        deps.append({
            "name": name,
            "kind": kind,
            "depth": depth,
            "definition": viewdef,
            "indexes": indexes,
        })
        log.info(
            f"  dependent: {name} ({'matview' if kind == 'm' else 'view'}, "
            f"depth={depth}, {len(indexes)} indexes)"
        )
    return deps


def _exists_mv(cur, name: str) -> bool:
    cur.execute(
        """
        SELECT 1 FROM pg_class
        WHERE relname = %s AND relkind = 'm' AND relnamespace = 'public'::regnamespace
        """,
        (name,),
    )
    return cur.fetchone() is not None


def _get_mv_indexes(cur, mv_name: str) -> list[tuple[str, str]]:
    cur.execute(
        """
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public' AND tablename = %s
        ORDER BY indexname
        """,
        (mv_name,),
    )
    return list(cur.fetchall())


def _rebuild_dependent(cur, dep: dict, mv_name: str) -> None:
    """Recria view/matview dependente apos swap.

    Importante: como capturamos a definicao via `pg_get_viewdef` ANTES do
    swap, ela ja referencia `mv_name` pelo nome correto (que apos swap
    aponta pro novo objeto, ja que renomeamos os 2 objetos).
    """
    name = dep["name"]
    if dep["kind"] == "v":
        cur.execute(f"CREATE OR REPLACE VIEW {name} AS {dep['definition']}")
    else:  # matview
        # Pra MV: precisa DROP+CREATE (CREATE OR REPLACE nao existe pra MV).
        # Ja foi dropada via DROP CASCADE; criar vazia, REFRESH depois.
        cur.execute(f"CREATE MATERIALIZED VIEW {name} AS {dep['definition']} WITH NO DATA")
    # Recriar indexes
    for idx_name, idx_def in dep["indexes"]:
        # idx_def ja inclui "ON public.<name>" — basta executar
        cur.execute(idx_def)


def swap_materialized_view(mv_name: str, new_definition_sql: str) -> None:
    """Substitui MV `mv_name` pela nova definicao com swap atomico.

    Args:
        mv_name: nome da MV existente (ex: 'mv_empresa_pb').
        new_definition_sql: SQL contendo `CREATE MATERIALIZED VIEW <mv>_swap`
          + `CREATE INDEX ... ON <mv>_swap`. Tudo com sufixo `_swap`.

    Raises:
        RuntimeError: validacoes pre-flight falham.
    """
    swap_name = f"{mv_name}_swap"

    if swap_name not in new_definition_sql:
        raise RuntimeError(
            f"SQL deve referenciar '{swap_name}' (CREATE MATERIALIZED VIEW + INDEX). "
            f"Garante que todos os identifiers usem o sufixo _swap."
        )

    conn = get_conn()
    try:
        # === Fase 1: validacoes + build paralelo (autocommit) ===
        conn.autocommit = True
        with conn.cursor() as cur:
            if not _exists_mv(cur, mv_name):
                raise RuntimeError(f"MV '{mv_name}' nao existe; abortado.")
            if _exists_mv(cur, swap_name):
                log.warning(f"MV '{swap_name}' stale; dropando antes do build")
                cur.execute(f"DROP MATERIALIZED VIEW {swap_name} CASCADE")

            log.info(f"=== Build paralelo de {swap_name} ===")
            t0 = time.time()
            cur.execute(new_definition_sql)
            log.info(f"=== Build concluido em {time.time()-t0:.1f}s ===")

            if not _exists_mv(cur, swap_name):
                raise RuntimeError(
                    f"SQL executou mas '{swap_name}' nao foi criada. "
                    f"Verifique que CREATE MATERIALIZED VIEW usa esse nome."
                )

            # Captura: indexes do swap + indexes do original + dependentes
            log.info(f"=== Capturando metadados ===")
            swap_indexes = _get_mv_indexes(cur, swap_name)
            log.info(f"  {len(swap_indexes)} indexes na MV nova")
            dependents = _capture_dependents(cur, mv_name)
            log.info(f"  {len(dependents)} dependentes a recriar")

            cur.execute(f"ANALYZE {swap_name}")

        # === Fase 2: swap atomico (transacao) ===
        log.info(f"=== Swap atomico ===")
        conn.autocommit = False
        try:
            with conn.cursor() as cur:
                # Bound lock + statement time. ACCESS EXCLUSIVE do DROP
                # MATERIALIZED VIEW espera readers terminarem; se houver
                # SELECT lento (warm worker, request agressivo), o swap fica
                # bloqueado e enfileira novos readers atras dele.
                # lock_timeout: aborta se nao consegue o lock em 30s.
                # statement_timeout: cap total da transacao em 120s.
                # Ambos LOCAL: nao vazam pra outras conexoes.
                cur.execute("SET LOCAL lock_timeout = '30s'")
                cur.execute("SET LOCAL statement_timeout = '120s'")

                # 1. Drop velho (CASCADE drops dependentes automaticamente).
                # DROP MATERIALIZED VIEW ja adquire ACCESS EXCLUSIVE lock na MV
                # e propaga pra dependentes; LOCK TABLE explicito nao funciona
                # pra MVs (Postgres restringe LOCK ao relkind 'r').
                t0 = time.time()
                cur.execute(f"DROP MATERIALIZED VIEW {mv_name} CASCADE")
                log.info(f"  drop velho + dependentes ({time.time()-t0:.2f}s)")

                # 2. Rename swap -> nome final
                cur.execute(
                    f"ALTER MATERIALIZED VIEW {swap_name} RENAME TO {mv_name}"
                )
                log.info(f"  {swap_name} -> {mv_name}")

                # 3. Rename indexes do swap (sufixo _swap removido).
                # Guard: skip se nome final ja existe (footgun defensivo se
                # algum dep usa nome colidente; raro mas barato proteger).
                for idx_name, _idx_def in swap_indexes:
                    if not idx_name.endswith("_swap"):
                        continue
                    final = idx_name[: -len("_swap")]
                    cur.execute(
                        """
                        SELECT 1 FROM pg_class
                        WHERE relname = %s AND relkind = 'i'
                          AND relnamespace = 'public'::regnamespace
                        """,
                        (final,),
                    )
                    if cur.fetchone():
                        log.warning(
                            f"  skip rename de '{idx_name}': '{final}' ja existe "
                            f"(provavelmente collision com index de dependente)"
                        )
                        continue
                    cur.execute(f"ALTER INDEX {idx_name} RENAME TO {final}")

                # 4. Recriar dependentes (views: imediato; matviews: vazias)
                for dep in dependents:
                    log.info(f"  recriando {dep['kind']}: {dep['name']}")
                    _rebuild_dependent(cur, dep, mv_name)

                conn.commit()
                log.info(f"=== Swap commit OK ===")
        except Exception:
            conn.rollback()
            log.exception("Swap falhou; transacao revertida")
            raise

        # === Fase 3: REFRESH MVs dependentes (fora de tx, sem bloqueio longo) ===
        matview_deps = [d for d in dependents if d["kind"] == "m"]
        if matview_deps:
            log.info(f"=== REFRESH de {len(matview_deps)} MVs dependentes ===")
            conn.autocommit = True
            with conn.cursor() as cur:
                for dep in matview_deps:
                    t0 = time.time()
                    cur.execute(f"REFRESH MATERIALIZED VIEW {dep['name']}")
                    log.info(f"  {dep['name']} refreshed ({time.time()-t0:.1f}s)")
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("mv_name", help="Nome da MV (ex: mv_empresa_pb)")
    parser.add_argument(
        "definition_file",
        help="Path do arquivo SQL com CREATE MATERIALIZED VIEW <mv>_swap + INDEX",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

    sql = Path(args.definition_file).read_text(encoding="utf-8")
    swap_materialized_view(args.mv_name, sql)
    log.info("=== DONE ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
