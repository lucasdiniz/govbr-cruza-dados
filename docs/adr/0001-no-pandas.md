# ADR-0001: No pandas — streaming + COPY FROM STDIN

## Status

Accepted

## Date

2024-06-15

## Context

O ETL precisa carregar aproximadamente **350 milhões de linhas** vindas de ~18
fontes (RFB, TCE-PB, dados.pb, TSE, Bolsa Família, CEIS, CNEP, etc.) em uma VM
Azure B4as_v2 com **16 GB de RAM**. Apenas a RFB sozinha são ~58 GB de CSV cru
(latin-1).

Caminhos considerados:

1. **pandas DataFrame + `to_sql`** — abordagem padrão da comunidade Python. Carrega
   o CSV inteiro em memória antes de qualquer escrita. Para a RFB ou TCE-PB,
   estoura RAM antes mesmo do primeiro `INSERT`. `chunksize` ameniza mas continua
   alocando objetos Python para cada célula.
2. **`psycopg2.executemany`** com listas Python — cabe em RAM se a leitura for
   streaming, mas o protocolo extended-query do Postgres envia cada `INSERT`
   individualmente. Para 350M rows isso é ordens de magnitude mais lento que
   `COPY` (testes locais: ~50x).
3. **`COPY FROM STDIN`** com geradores Python — Postgres consome um fluxo de
   bytes diretamente do socket. Memória usada = buffer do `COPY` (alguns MB) +
   uma linha em flight no Python.

## Decision

**O projeto não usa pandas em código ETL.** Toda carga de dados segue o padrão:

1. **Streaming line-by-line** com generators Python (`open(...)`, `csv.reader`,
   ou helpers como `latin1_lines` em `etl/utils.py`).
2. **`COPY FROM STDIN`** via helpers em `etl/db.py`:
   - `copy_from_stream(conn, table, columns, iterator)` — recebe um generator
     de tuples, escreve no `COPY`.
   - `copy_csv_streaming(conn, table, csv_path, ...)` — caso comum CSV→tabela.
   - `batch_insert(conn, table, rows, batch_size=...)` — fallback para casos
     que precisam de `INSERT ... ON CONFLICT`.
3. **Parsing BR-específico** centralizado em `etl/utils.py`:
   `parse_date_br`, `parse_decimal_br`, `clean_cpf`, `clean_cnpj`,
   `extract_cpf_masked`, `normalize_name`. Reuso obrigatório — os formatos de
   data e decimal variam por fonte (e às vezes dentro da mesma fonte).

JOINs e agregações ficam **em SQL**, não em Python. Materialized Views (ver
[ADR-0002](0002-mv-layered.md)) materializam o resultado.

## Consequences

### Positive

- **Cabe em <8 GB de RAM** mesmo para a RFB de 58 GB. O resto da RAM fica
  disponível para o Postgres (`work_mem`, `shared_buffers`).
- **ETL completo em ~10-20 h** na VM-alvo (B4as_v2, 4 vCPU). Estimativa com
  pandas/executemany era de **dias**. A RFB (a maior fonte) carrega em ~30 min.
- JOINs em SQL forçam o trabalho a acontecer onde o índice e o planner ajudam.
- Sem dependência de NumPy/pandas (centenas de MB de wheels) na imagem do
  runner.

### Negative / Trade-offs

- **Learning curve** para contributors vindos de Django/Flask + pandas. Não há
  `df.merge`, `df.groupby`, `df.pivot_table` — tudo isso vira SQL.
- Métricas, profiling e validação de qualidade exigem código manual (não dá
  para `df.describe()` no meio do pipeline). Em geral fica como query
  ad-hoc.
- Sem o ecossistema de I/O do pandas (Parquet, Excel, Feather). O projeto lida
  só com CSV/JSON, então isso não doeu, mas é uma porta fechada.
- `COPY FROM STDIN` é menos amigável a erros: uma linha malformada aborta o
  batch. Validação tem que acontecer antes de entrar no generator.

### Mitigations

- Helpers em `etl/db.py` reduzem boilerplate ao mínimo. O contributor escreve
  apenas o generator de linhas; o `COPY` é uma chamada de função.
- `CONTRIBUTING.md` documenta a convenção na seção "Convenções Python".
- [`docs/etl-guide.md`](../etl-guide.md) traz exemplos completos do padrão
  generator → `copy_from_stream`.
- Para análise exploratória, contributors podem usar pandas em
  Jupyter/notebooks **fora do código de produção** — basta não importar pandas
  em `etl/**`.

## Related

- Code: [`etl/db.py`](../../etl/db.py) (`copy_from_stream`, `copy_csv_streaming`,
  `batch_insert`), [`etl/utils.py`](../../etl/utils.py) (parsers BR).
- Other ADRs: [ADR-0002](0002-mv-layered.md) (JOINs em SQL → MVs em camadas),
  [ADR-0005](0005-no-orm-web.md) (mesma filosofia raw-SQL no web).
- External:
  - [PostgreSQL `COPY` docs](https://www.postgresql.org/docs/16/sql-copy.html)
  - [psycopg2 `copy_expert`](https://www.psycopg.org/docs/cursor.html#cursor.copy_expert)
