# ADR-0002: Materialized Views em camadas L1 → L2 → views planas

## Status

Accepted

## Date

2024-09-10

## Context

O cálculo de **score de risco** (municipal, empresa, servidor) cruza de 5 a 10
tabelas grandes: `tce_pb_*`, `empresa`, `estabelecimento`, `socio`, `ceis_sancao`,
`cnep`, `bolsa_familia`, `servidor_pb`, entre outras. Algumas delas têm dezenas de
milhões de linhas.

Caminhos considerados:

1. **Query live em request time** — joins em todas as tabelas a cada request.
   Mesmo com índices, alguns scores levavam minutos; em produção dariam timeout.
2. **Cache em `web_cache` (Postgres table)** — já existe (ver
   [ADR-0003](0003-shadow-rewarm.md)). Funciona para o output final, mas precisa
   de um **input estável e re-runnable** — a query bruta ainda é cara.
3. **Materialized Views** — Postgres armazena o resultado fisicamente,
   `REFRESH MATERIALIZED VIEW CONCURRENTLY` permite atualização sem bloquear
   leitores. Drawback: refresh demora, e MVs com dependências entre si exigem
   ordem.

A primeira versão tinha um arquivo `sql/12_views.sql` com 30 MVs sem ordem
explícita. Mudar a definição de uma quebrava cascata e ninguém entendia mais a
ordem correta de `REFRESH`.

## Decision

MVs organizadas em **3 camadas** em [`sql/12_views.sql`](../../sql/12_views.sql),
com regras estritas:

### Camada L1 — independentes

Agregam apenas **tabelas físicas**. Sem depender de outras MVs.

- `mv_empresa_governo` — empresas com contrato governo (qualquer ente)
- `mv_pessoa_pb` — universo de pessoas PB (CPF + nome)
- `mv_municipio_pb_risco` — agregações por município PB
- `mv_servidor_pb_base` — servidores PB consolidados
- `mv_empresa_municipio_pagantes` — pares (empresa, município) com pagamento

### Camada L2 — derivadas

Dependem de **uma ou mais L1** (e possivelmente de tabelas físicas).

- `mv_servidor_pb_risco` (← `mv_servidor_pb_base`)
- `mv_empresa_pb` (← `mv_empresa_governo`, `mv_empresa_municipio_pagantes`)
- `mv_rede_pb` (← múltiplas L1)
- `mv_municipio_pb_kpi_score`, `mv_municipio_pb_mapa` (← `mv_municipio_pb_risco`)
- `mv_q67_dated_pb`

### Camada L3 — views planas (não materializadas)

Views normais (sem armazenamento próprio) que apenas **renomeiam ou compõem L2**
para consumo do web.

- `v_risk_score_pb` (← `mv_municipio_pb_kpi_score`)
- `v_risk_score_empresa` (← `mv_empresa_pb`)

### Convenções obrigatórias em `sql/12_views.sql`

1. **DROP em ordem reversa no topo do arquivo** (L3 → L2 → L1). Isso evita
   `cannot drop because other objects depend on it`.
2. **CREATE em ordem direta** (L1 → L2 → L3), seções comentadas separando
   camadas.
3. **`REFRESH CONCURRENTLY` exige `UNIQUE INDEX`** — toda MV criada precisa de
   pelo menos um índice único declarado logo após o `CREATE MATERIALIZED VIEW`.
4. **Rodapé do arquivo** lista os comandos `REFRESH MATERIALIZED VIEW
   CONCURRENTLY` em ordem topológica, para uso operacional.
5. **Cada MV tem comentário inline** com propósito + dependências explícitas
   (`-- depends on: mv_xxx, tabela_yyy`).

A fase 18 do ETL ([`etl/21_views.py`](../../etl/21_views.py)) reexecuta o arquivo
inteiro após mudanças de dados.

## Consequences

### Positive

- Queries da UI leem MV → **microssegundos vs minutos**.
- Contributor adicionando query nova **reusa MV existente** em vez de duplicar
  joins.
- Refresh roda **offline** (cron noturno + `warm_cache` em sequência) sem
  impacto em produção.
- A camada explícita força o autor a decidir *onde* uma agregação pertence —
  reduz duplicação acidental.

### Negative / Trade-offs

- **Refresh demora horas** para MVs grandes (5M+ rows com `CONCURRENTLY`).
- **MV stale** se uma tabela física é atualizada sem refresh subsequente — não
  há invalidação automática. O ETL principal sempre refaz, mas alterações
  manuais não.
- Mudança em **coluna de L1 quebra L2 em cascata**. Renomear `mv_pessoa_pb.cpf`
  para `cpf_digitos` exige varrer todas as L2 e atualizar.
- `web/queries/registry.py` referencia colunas de MVs por nome — drift entre
  SQL e Python só aparece em runtime.

### Mitigations

- Cada MV é documentada inline com dependências; navegar `sql/12_views.sql`
  topo-pra-baixo é suficiente para entender a árvore.
- A fase 18 do ETL reexecuta todo o arquivo — refresh diário evita stale em
  produção.
- [`docs/mv-guide.md`](../mv-guide.md) detalha o passo-a-passo para adicionar uma
  MV nova respeitando as 5 convenções.
- CI futuro (issue [#135]) pode detectar drift entre MVs e referências em
  `web/queries/registry.py`.

## Related

- Code: [`sql/12_views.sql`](../../sql/12_views.sql),
  [`etl/21_views.py`](../../etl/21_views.py),
  [`web/queries/registry.py`](../../web/queries/registry.py).
- Other ADRs: [ADR-0001](0001-no-pandas.md) (JOINs em SQL, não em Python),
  [ADR-0003](0003-shadow-rewarm.md) (cache de output usa MVs como input).
- Docs: [`docs/architecture.md`](../architecture.md) seção "Materialized Views
  em camadas".
- External: [PostgreSQL `REFRESH MATERIALIZED VIEW
  CONCURRENTLY`](https://www.postgresql.org/docs/16/sql-refreshmaterializedview.html).
