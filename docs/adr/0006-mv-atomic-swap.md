# ADR-0006: Atomic swap de Materialized Views (zero-downtime updates)

## Status

Accepted

## Date

2026-05-16

## Context

[`sql/12_views.sql`](../../sql/12_views.sql) define 10 MVs em camadas L1 → L2
→ views planas (ver [ADR-0002](0002-mv-layered.md)). O arquivo começa com
**`DROP MATERIALIZED VIEW ... CASCADE`** de todas as MVs em ordem reversa de
dependência, depois recria tudo. Esse padrão garante consistência de schema
mas tem um custo operacional pesado quando o que muda é **uma única MV**.

Cenário disparador: PR #151 corrigiu contaminação de CPF padded em queries
que filtram `tce_pb_despesa.cnpj_basico`. O mesmo bug existe em `mv_empresa_pb`
(no `tce_agg` CTE e nas demais fontes PB), afetando os KPIs do header de
`/empresa/<cnpj>`. Como aplicar essa correção?

Caminhos considerados:

1. **`etl_phase=sql`** — roda `etl.21_views` que executa `sql/12_views.sql`
   inteiro. Drop+create de TODAS as MVs (incluindo `mv_municipio_pb_kpi_score`,
   `mv_servidor_pb_risco`, etc, que não tinham bug nenhum). Downtime real:
   1–2h até todas reconstruirem. Força resize de VM para B4. Bloqueia
   tráfego live nas páginas dependentes.

2. **`REFRESH MATERIALIZED VIEW CONCURRENTLY`** — não serve. CONCURRENTLY
   só recalcula dados com a definição existente; aqui a definição
   (CTE `tce_agg`) mudou.

3. **Tabela intermediária + view union** — manter MV antiga e nova como
   tabelas, decidir qual ler via view. Requer mudar 30+ queries de
   `web/queries/*.py` para apontar pra view, refactor pesado.

4. **Build paralelo + RENAME atômico** — criar `mv_empresa_pb_swap` em
   paralelo (autocommit, sem bloqueio), capturar dependentes via
   `pg_depend`/`pg_rewrite`, fazer DROP CASCADE + RENAME + recreate
   dependentes em uma transação curta. Resto do tempo o site serve dados
   antigos.

## Decision

Framework genérico em [`etl/mv_swap.py`](../../etl/mv_swap.py) que aplica o
padrão (4): build paralelo + rename atômico com captura/recreate de
dependentes. Reutilizável pra qualquer MV.

### Mecânica

1. **Validação pre-flight**: MV existe; SQL referencia `<mv>_swap`; nenhum
   `<mv>_swap` stale (drop se houver).
2. **Build paralelo** (autocommit, sem bloqueio):
   ```sql
   CREATE MATERIALIZED VIEW <mv>_swap AS ...;
   CREATE [UNIQUE] INDEX ... ON <mv>_swap ...;
   ```
   Tráfego live continua na MV original. Tempo varia conforme MV (build de
   `mv_empresa_pb` local: 91s).
3. **Snapshot recursivo de dependentes** via:
   ```sql
   WITH RECURSIVE deps AS (
       SELECT ... FROM pg_depend JOIN pg_rewrite ... WHERE source=<mv>
       UNION ALL
       SELECT ... FROM deps JOIN pg_depend ... (next layer)
   )
   ```
   Captura `pg_get_viewdef()` + `pg_indexes.indexdef` pra cada dependente.
   Ordering: `MAX(depth) ASC` pra topological sort em grafos com múltiplos
   paths (parents antes de children).
4. **ANALYZE** no swap (planner statistics).
5. **Transação atômica** (`lock_timeout=30s`, `statement_timeout=120s`):
   ```sql
   BEGIN;
   SET LOCAL lock_timeout = '30s';
   SET LOCAL statement_timeout = '120s';

   DROP MATERIALIZED VIEW <mv> CASCADE;
   ALTER MATERIALIZED VIEW <mv>_swap RENAME TO <mv>;
   ALTER INDEX <idx>_swap RENAME TO <idx>;  -- pra cada index, com collision guard
   -- Recreate cada dependente (CREATE OR REPLACE VIEW; ou CREATE MATVIEW WITH NO DATA)
   COMMIT;
   ```
   Downtime real: ~1s (só os RENAME no catálogo).
6. **Fora da transação**: `REFRESH MATERIALIZED VIEW <dep>` pra cada MV
   dependente (não-CONCURRENT — recém criada).

### Integração com workflow

Input `mv_swap` em [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml)
aceita CSV de MVs. Step roda **APÓS** todos os ETL phases
(`etl_phase=sql/all/N/incremental`, `download_sources`, `run_queries`) e
**ANTES** do warm cache. Ordem importa: se rodasse antes, ETL mutaria as
tabelas-fonte depois do swap, deixando a MV stale.

Convenção: cada MV elegível precisa de `deploy/mv_updates/<mv_name>.sql`
contendo `CREATE MATERIALIZED VIEW <mv_name>_swap` + indexes (sufixo `_swap`
removido pelo framework).

## Consequences

### Positive

- **Downtime efetivo ~1s** vs 1–2h do `etl_phase=sql`.
- **Sem VM resize** — usa o tamanho atual da VM (B2 normalmente, vs B4
  forçado pelo `etl_phase=sql`).
- **Tráfego live preservado** durante o build paralelo (~90s+) — readers
  continuam na MV antiga até o swap.
- **Atomicity all-or-nothing** — se recreate de dependente falha,
  transação rollback restaura estado anterior.
- **Reusável** — framework é genérico; cada MV nova adiciona um
  `deploy/mv_updates/<mv>.sql`, sem código novo.

### Negative / Trade-offs

- **Storage temporário**: durante o build, `<mv>_swap` ocupa espaço
  equivalente à MV original (ex: `mv_empresa_pb` ~50 MB local).
- **MVs dependentes ficam vazias temporariamente**: o framework recria MVs
  dependentes via `CREATE ... WITH NO DATA` dentro da transação (REFRESH
  pesado dentro de tx seria contraproducente). REFRESH roda fora da tx, mas
  durante esse intervalo dependent MVs servem zero rows.
- **`ACCESS EXCLUSIVE` no DROP**: se houver query lenta concorrente lendo
  a MV (warm worker, request agressivo), o swap aguarda até o `lock_timeout`
  (30s) e aborta limpo. Tráfego enfileirado atrás dele durante esse período.
- **Não substitui `etl_phase=sql`** quando múltiplas MVs precisam mudar
  simultaneamente e referenciam umas às outras (ordem de DROP+CREATE em
  cascade é mais simples nesse caso).
- **Drift potencial entre `sql/12_views.sql` e `deploy/mv_updates/<mv>.sql`**:
  precisamos manter as duas em sincronia para que o próximo full rebuild não
  regrida o fix.

### Mitigations

- `lock_timeout=30s` + `statement_timeout=120s` abortam limpo em vez de
  stallar tráfego indefinidamente.
- Step do workflow é **APÓS** ETL phases (achado em review GPT-5.5 da
  PR #153) — garante que MV é buildada com dados consistentes pós-ETL.
- Sanitização do input `mv_swap` (regex `[a-zA-Z0-9_,]`) bloqueia injection
  e escape de path (`/` rejeitado).
- Para MVs com dependentes MV pesados, recomenda-se rodar em janela de
  baixo tráfego (o REFRESH pós-swap leva minutos durante os quais a UI
  serve dados stale).
- Convenção: ao mudar uma MV via swap, sempre atualizar **também**
  `sql/12_views.sql` no mesmo PR (próximo full rebuild reflete o fix).

## Related

- Code: [`etl/mv_swap.py`](../../etl/mv_swap.py)
  (`swap_materialized_view`, `_capture_dependents`, `_rebuild_dependent`).
- Workflow: [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml)
  (input `mv_swap` + step "MV atomic swap").
- Docs:
  - [`docs/mv-guide.md`](../mv-guide.md) — seção "Atualizando UMA MV existente".
  - [`docs/deploy.md`](../deploy.md) — input `mv_swap` na tabela + cenário.
  - [`docs/architecture.md`](../architecture.md) — referência cruzada na
    seção de MVs.
- Primeiro caso de uso:
  [`deploy/mv_updates/mv_empresa_pb.sql`](../../deploy/mv_updates/mv_empresa_pb.sql)
  (corrigir contaminação de CPF padded em `mv_empresa_pb`, follow-up da
  PR #151).
- Other ADRs:
  - [ADR-0002](0002-mv-layered.md) — define o pattern de MV em camadas
    L1 → L2 → views planas. Este ADR estende com mecanismo de update.
  - [ADR-0003](0003-shadow-rewarm.md) — mesmo princípio (shadow + swap)
    aplicado a `web_cache` em vez de MV.
- External:
  - PostgreSQL docs: [ALTER MATERIALIZED VIEW](https://www.postgresql.org/docs/16/sql-altermaterializedview.html),
    [pg_depend](https://www.postgresql.org/docs/16/catalog-pg-depend.html),
    [pg_rewrite](https://www.postgresql.org/docs/16/catalog-pg-rewrite.html).
