# ADR-0007: ETL-level fix para contaminação de `cnpj_basico` + REFRESH CONCURRENTLY como propagador

## Status

Accepted

## Date

2026-05-16

## Context

Tabelas `tce_pb_despesa` e `pb_*` (`pb_empenho`, `pb_pagamento`, `pb_contrato`,
`pb_saude`, `pb_convenio`, etc) têm uma coluna `cnpj_basico VARCHAR(8)`
derivada via `etl/15_normalizar.py` como `LEFT(doc, 8)` (sem validação).
Quando `doc` é um CPF de 11 dígitos armazenado com padding de zeros à
esquerda (ex: CPF `140.207.524-35` → `00014020752435`), o "cnpj_basico"
resultante (`00014020`) colide com `cnpj_basico` de PJ real (AVICOLA
CHESTER MONGAGUA, CNPJ `00014020000111`).

Volume medido (DB local):

| Tabela | Rows contaminadas |
|---|---|
| `tce_pb_despesa` | **5.8M** (36.7% de 16M) |
| `pb_empenho` | ~1k (5.2%) |
| `pb_saude` | 34 (1.4%) |
| `pb_contrato`, `pb_liquidacao_despesa`, etc | minimal mas existe |

[PR #151](https://github.com/lucasdiniz/govbr-cruza-dados/pull/151) corrigiu
o sintoma em **queries do web** adicionando `EXISTS (SELECT 1 FROM
estabelecimento WHERE cnpj_completo = doc)`. [PR #153](https://github.com/lucasdiniz/govbr-cruza-dados/pull/153)
estendeu o fix pra `mv_empresa_pb` via [ADR-0006](0006-mv-atomic-swap.md)
(framework de atomic swap). Mas **6 outras MVs** seguem contaminadas:
`mv_empresa_governo`, `mv_q67_dated_pb`, `mv_municipio_pb_kpi_score`,
`mv_municipio_pb_mapa`, `mv_municipio_pb_risco`, `mv_pessoa_pb`.

Aplicar o fix MV-por-MV (6 PRs com 6 `deploy/mv_updates/<mv>.sql`) é
viável mas:

- Reproduz o mesmo guard em 6 lugares — drift técnico futuro.
- Não previne MVs novas de cair no mesmo bug.
- Não corrige queries one-off em `queries/*.sql` que filtram por
  `cnpj_basico` (~30+ ocorrências).

Caminhos considerados:

1. **Manter padrão MV-por-MV (ADR-0006)** — 6 PRs adicionais. Repete
   código em MVs e queries. Drift garantido.

2. **Fix de raiz no ETL** — anular `cnpj_basico` quando o doc completo
   não existe em `estabelecimento`. Todas as MVs e queries que filtram
   `WHERE cnpj_basico IS NOT NULL` automaticamente excluem CPFs padded
   sem precisar de guard explícito.

3. **Mudar schema de `cnpj_basico` para FK** — `cnpj_basico` vira chave
   estrangeira de uma tabela "empresa_basico" derivada de `estabelecimento`.
   Garantia estrutural mas refactor pesado (afeta carga incremental,
   queries, MVs).

## Decision

Adotamos **caminho 2** (fix de raiz no ETL) com **REFRESH MATERIALIZED
VIEW CONCURRENTLY** como mecanismo de propagação:

### Mudanças no ETL

`etl/15_normalizar.py`:

1. **Guard preventivo** nos `UPDATE cnpj_basico = LEFT(doc, 8)` existentes:
   adicionado `AND EXISTS (SELECT 1 FROM estabelecimento WHERE cnpj_completo = doc)`.
   Garante que cargas futuras não populam mais `cnpj_basico` contaminado.

2. **Cleanup retroativo (Fase 9 nova)**: `UPDATE ... SET cnpj_basico = NULL
   WHERE cnpj_basico IS NOT NULL AND NOT EXISTS (...)`. Aplicado em 10
   tabelas (`tce_pb_despesa` + 9 `pb_*`). Idempotente.

### Migration standalone

`sql/15a_fix_cnpj_basico_contamination.sql`: mesmo cleanup mas como
script SQL puro, executável via `psql -f` sem precisar rodar
`etl.15_normalizar` inteiro. Necessário pra deploy cirúrgico em prod.

### Pre-flight para `mv_q67_dated_pb`

`sql/15b_add_unique_index_mv_q67.sql`: `CREATE UNIQUE INDEX CONCURRENTLY`
em `mv_q67_dated_pb (municipio, ano, COALESCE(cnpj_basico, ''))`.
`mv_q67_dated_pb` foi criada via hotfix (PR #54) sem UNIQUE INDEX —
sem ele, `REFRESH MATERIALIZED VIEW CONCURRENTLY` falha. `CREATE INDEX
CONCURRENTLY` não bloqueia leituras.

### Propagação via REFRESH CONCURRENTLY

Em vez de `etl_phase=sql` (que faz `DROP CASCADE` de todas as MVs com
1-2h de downtime) ou mv_swap atômico (que exige criar
`deploy/mv_updates/<mv>.sql` por MV), usamos `REFRESH MATERIALIZED VIEW
CONCURRENTLY` em cada MV afetada:

- Requer UNIQUE INDEX (todas as MVs PB têm, ou ganham via `15b`).
- Usa `SHARE UPDATE EXCLUSIVE` em vez de `ACCESS EXCLUSIVE` — leituras
  concorrentes continuam funcionando.
- Tempo equivalente ao build (estimativa: 1-5min por MV em prod B4).
- Custo de disco: ~2x o tamanho da MV durante o refresh (snapshot +
  cópia + comparação).

Como a definição da MV não muda — só os dados subjacentes — `REFRESH`
basta. **Não precisamos de mv_swap atômico para este fix.**

### Deploy workflow

Dois inputs novos em `.github/workflows/deploy.yml`:

- `run_normalize_fix` (bool): executa `sql/15a_fix_cnpj_basico_contamination.sql`
  + `sql/15b_add_unique_index_mv_q67.sql`. Roda APÓS ETL phases, ANTES
  do warm.
- `refresh_mvs` (CSV): executa `REFRESH MATERIALIZED VIEW CONCURRENTLY`
  em cada MV listada. Sanitizado regex `[a-zA-Z0-9_,]`.

Sequência típica:

```bash
# 1. Aplicar cleanup ETL (zero downtime)
gh workflow run deploy.yml -f etl_phase=web -f run_normalize_fix=true

# 2. Propagar nas MVs L1 (zero downtime)
gh workflow run deploy.yml -f etl_phase=web \
  -f refresh_mvs=mv_pessoa_pb,mv_empresa_governo,mv_empresa_pb,mv_municipio_pb_risco

# 3. Propagar nas MVs L2 (depois das L1)
gh workflow run deploy.yml -f etl_phase=web \
  -f refresh_mvs=mv_servidor_pb_risco,mv_municipio_pb_kpi_score,mv_municipio_pb_mapa,mv_q67_dated_pb

# 4. Rewarm das cache keys afetadas (zero downtime via shadow)
gh workflow run deploy.yml -f etl_phase=web \
  -f rewarm_cache_keys=EMPRESA_PERFIL,EMPRESA_PERFIL_MUN,KPI_SUMMARY,MAPA,Q67,PERFIL,TOP_FORNECEDORES,TOP_SERVIDORES
```

## Consequences

### Positive

- **Zero downtime total**: cada etapa (UPDATE, REFRESH CONCURRENTLY,
  rewarm shadow) não bloqueia tráfego live.
- **Fix de raiz**: futuras MVs e queries herdam o filtro automaticamente
  via `WHERE cnpj_basico IS NOT NULL`.
- **Idempotente**: pode rodar 1x ou 10x — mesmo estado final.
- **Sem refactor de MVs**: definição preservada, só `REFRESH`.
- **Aplicável retroativamente** sem `etl_phase=sql` (que dropa todas as
  MVs com downtime).
- **mv_swap continua útil** pra mudanças de SCHEMA (coluna nova, tipo
  alterado) que `REFRESH` não cobre.

### Negative / Trade-offs

- **`REFRESH CONCURRENTLY` precisa de disk ~2x** o tamanho da MV
  durante o refresh. Em prod B4 com Premium SSD: ~500MB-1GB extra
  temporário cumulativo se rodar várias MVs em paralelo.
- **Janela transitória**: entre o `UPDATE` (passo 1) e o último
  `REFRESH` (passo 3), MVs servem dados velhos com contaminação.
  Usuário acessando `/empresa/<cnpj>` no meio vê dados velhos até o
  rewarm completar.
- **`mv_q67_dated_pb` precisa de UNIQUE INDEX novo** — adicionado em
  `sql/15b`, mas é uma mudança de schema permanente.
- **Não corrige `mv_rede_pb`** (sem UNIQUE INDEX, não usa `cnpj_basico`
  de tabelas contaminadas — leitura de `socio` do RFB que é 100% PJ).
- **Cleanup retroativo é destrutivo**: depois do `UPDATE NULL`, perdemos
  a informação "este empenho tinha cpf_cnpj X mesmo que não-RFB" para
  análise de fraude. Mitigação: `cpf_cnpj` original permanece intacto,
  apenas a coluna derivada `cnpj_basico` é anulada.

### Mitigations

- **Idempotência** permite re-run sem corromper.
- **`run_normalize_fix=true` em horário de baixo tráfego** mitiga a
  janela transitória — embora não seja zero, é minutos não horas.
- **Recovery**: se `UPDATE` quebra algo inesperado, basta re-rodar
  `etl.15_normalizar` que repopula `cnpj_basico` com o EXISTS guard
  novo (porém só para rows com `cnpj_basico IS NULL` — restauração
  total exige rerun completo).

## Related

- Code:
  - [`etl/15_normalizar.py`](../../etl/15_normalizar.py) (Fase 5/7 + Fase 9 nova).
  - [`sql/15a_fix_cnpj_basico_contamination.sql`](../../sql/15a_fix_cnpj_basico_contamination.sql).
  - [`sql/15b_add_unique_index_mv_q67.sql`](../../sql/15b_add_unique_index_mv_q67.sql).
- Workflow:
  - [`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml)
    (inputs `run_normalize_fix` + `refresh_mvs`).
- Other ADRs:
  - [ADR-0002](0002-mv-layered.md) — MV layers L1 → L2 → views planas.
  - [ADR-0006](0006-mv-atomic-swap.md) — Atomic swap framework
    (complementar; continua útil pra mudanças de schema).
- PRs:
  - [#151](https://github.com/lucasdiniz/govbr-cruza-dados/pull/151) —
    fix do mesmo bug em queries do web.
  - [#153](https://github.com/lucasdiniz/govbr-cruza-dados/pull/153) —
    fix de `mv_empresa_pb` via atomic swap.
- External:
  - [PostgreSQL — REFRESH MATERIALIZED VIEW](https://www.postgresql.org/docs/16/sql-refreshmaterializedview.html)
    ("The CONCURRENTLY option ... allows the materialized view to continue
    to be selected against while it is being refreshed").
