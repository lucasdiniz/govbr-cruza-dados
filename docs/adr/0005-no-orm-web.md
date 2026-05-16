# ADR-0005: Sem ORM no web — raw SQL via psycopg2

## Status

Accepted

## Date

2024-08-01

## Context

A camada web (FastAPI + Jinja2 em [`web/`](../../web/)) precisa servir queries
analíticas pesadas: agregações por município, rankings de fornecedores,
cruzamentos entre `mv_municipio_pb_risco` e `mv_empresa_pb`, queries Q01–Q310
parametrizadas por intervalo de data.

Caminhos considerados:

1. **SQLAlchemy ORM** — padrão da comunidade Python web. Boa ergonomia para
   CRUD. **Problemas no nosso caso**:
   - Mapear MVs (ver [ADR-0002](0002-mv-layered.md)) e views planas exige
     declarar modelos artificiais; mudanças em SQL exigem mudança em Python.
   - JOINs analíticos complexos (5–10 tabelas, window functions, CTEs)
     viram código ORM ilegível ou caem em `text()` — anulando o ORM.
   - Geração de SQL do SQLAlchemy nem sempre usa o plano que escolheríamos;
     ajustes finos exigem hints/raw fragments.
2. **SQLAlchemy Core (sem ORM)** — query builder declarativo. Melhor que ORM
   para analytics, mas ainda exige duplicar schema em metadata Python.
3. **psycopg2 raw + `web/queries/registry.py`** — queries escritas em SQL
   puro, parametrizadas com `%(named)s`, registradas em um `dict` por
   `query_id`. Web app só executa.

A filosofia de [ADR-0001](0001-no-pandas.md) (trabalho pesado em SQL, Python
apenas como driver) e de [ADR-0002](0002-mv-layered.md) (MVs como contrato)
favorecem a opção 3 fortemente.

## Decision

**Sem ORM e sem query builder.** A camada web usa **psycopg2 raw** com pool de
conexões em [`web/db.py`](../../web/db.py).

Queries vivem em **`web/queries/registry.py`** como objetos `QueryDef`:

```python
QueryDef(
    qid="Q65",
    title="Top fornecedores PB...",
    sql_full="""SELECT ... FROM mv_empresa_pb WHERE ...""",
    sql_full_dated="""SELECT ... WHERE data BETWEEN %(data_inicio)s AND %(data_fim)s""",
    params=("municipio_id",),
    timeout_sec=30,
)
```

Convenções:

- **Duas variantes** por query quando aplicável: `sql_full` (all-time) e
  `sql_full_dated` (com placeholders `data_inicio`/`data_fim`,
  `ano_inicio`/`ano_fim`, `ano_mes_inicio`/`ano_mes_fim`).
- **Parâmetros sempre nomeados** (`%(nome)s`) — psycopg2 escapa, evita SQL
  injection, ordem não importa.
- **Timeout por query** (`QueryDef.timeout_sec`, default 30 s) aplicado via
  `SET LOCAL statement_timeout`.
- **Cache em `web_cache`** ([ADR-0003](0003-shadow-rewarm.md)) intermedia
  produção — a query raw só roda em warm/miss.

## Consequences

### Positive

- **SQL é o contrato** — DBA, analista e developer leem a mesma fonte
  (`registry.py`), não precisam saber Python para entender o que sai do
  banco.
- Mudança em MV → ajuste pontual na query, sem migration de modelo Python.
- **Plano de execução previsível** — o SQL que está no arquivo é o SQL que o
  Postgres recebe (`EXPLAIN` direto, sem indireção do ORM).
- Compatível com `pgbadger`/`pg_stat_statements` para profiling — query text
  é o ID natural.
- Coerente com [ADR-0001](0001-no-pandas.md): SQL no SQL, Python como driver.

### Negative / Trade-offs

- **Sem migrações automáticas de schema** — schema vive em `sql/*.sql`,
  alterado à mão. Não há `alembic upgrade head`.
- **Sem refactoring assistido** — renomear coluna exige `grep` em
  `registry.py` + SQL files; IDE não ajuda.
- **Risco de SQL injection** se contributor concatenar strings em vez de usar
  `%(named)s`. Convenção + code review mitigam.
- Sem mapeamento automático row → objeto — `cursor.fetchall()` retorna
  tuples/dicts; conversão para template Jinja é manual.

### Mitigations

- `web/db.py` expõe helpers (`fetch_one`, `fetch_all`, `execute`) que
  encapsulam pool + cursor + timeout — contributor raramente toca psycopg2
  diretamente.
- `registry.py` é a única porta de entrada — code review foca lá.
- Schema vive versionado em `sql/*.sql` numerados; mudanças passam pelo
  mesmo PR review.
- Para o futuro: CI poderia rodar `EXPLAIN` em cada query do registry e
  alertar regressões de plano.

## Related

- Code: [`web/db.py`](../../web/db.py),
  [`web/queries/registry.py`](../../web/queries/registry.py),
  [`web/main.py`](../../web/main.py).
- Other ADRs: [ADR-0001](0001-no-pandas.md) (filosofia raw + streaming),
  [ADR-0002](0002-mv-layered.md) (MVs são o "modelo" lido pelo web),
  [ADR-0003](0003-shadow-rewarm.md) (cache em frente às queries raw).
- External:
  - [psycopg2 parameter passing](https://www.psycopg.org/docs/usage.html#passing-parameters-to-sql-queries)
  - [PostgreSQL `statement_timeout`](https://www.postgresql.org/docs/16/runtime-config-client.html#GUC-STATEMENT-TIMEOUT)
