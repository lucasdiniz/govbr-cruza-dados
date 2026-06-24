# ADR-0014: NK sintética md5 para tabelas TCE-PB no ETL incremental

## Status

Accepted

## Date

2026-06-23

## Context

As quatro tabelas TCE-PB (`tce_pb_despesa`, `tce_pb_servidor`,
`tce_pb_licitacao`, `tce_pb_receita`) são carregadas pelo ETL clássico
(`etl/19_tce_pb.py`), que faz `INSERT INTO ... SELECT` **plano**: sem dedup,
sem `DELETE` prévio, sem `ON CONFLICT`. Re-rodar uma fase apenas **acumula
duplicatas**. Não existe caminho de atualização incremental seguro no ETL
clássico.

Os specs do framework incremental (`etl/incremental/specs/tce_pb_*.py`,
ADR-0004) já existiam, mas **nunca foram validados em produção**:

- O `deploy.yml` nunca aplicou `sql/30` (despesa) nem `sql/31` (servidor).
- `sql/30` criava um `UNIQUE INDEX` na NK natural **sem dedup** → falharia.
- `sql/31` tinha o `DELETE` de dedup mas estava **truncado, sem o
  `CREATE UNIQUE INDEX`**.
- As tabelas em prod só têm `PRIMARY KEY (id)` — **nenhum índice na NK** →
  o `ON CONFLICT (NK)` do framework falha com
  `there is no unique or exclusion constraint matching the ON CONFLICT
  specification`.

Ao tentar rodar o incremental em prod (2026-06-23), os 9 buckets de despesa
falharam com 0 rows inseridas (rollback limpo, sem corrupção). A investigação
read-only em prod revelou dois problemas distintos que **inviabilizam a NK
natural**:

### 1. `tce_pb_despesa` — NK natural não é única (colisões reais)

A NK candidata do spec (`municipio, codigo_ug, numero_empenho, data_empenho,
codigo_subelemento, codigo_fonte_recurso, numero_obra, numero_licitacao,
codigo_natureza, ano_arquivo`) tem **1037 grupos (2530 rows, 2019-2026)** com
mais de uma ocorrência. Análise full-payload:

- **0 dos 1037 grupos** são duplicatas reais.
- **Todos os 1037** têm `valor_empenhado`/`valor_liquidado`/`valor_pago`/
  `cpf_cnpj`/`nome_credor`/`historico` **distintos** — são empenhos/parcelas
  legitimamente diferentes que a NK não distingue.
- Adicionar `mes` à NK **não resolve** (0 grupos colapsam).

Consequência: um `UNIQUE INDEX` na NK natural seria semanticamente errado, e
`UPSERT_DO_NOTHING` **pularia silenciosamente** novos registros distintos que
colidem na NK → perda contínua de dados a cada incremental.

### 2. `tce_pb_servidor` — NULLs nas colunas da NK (double-load)

A NK natural inclui colunas **NULLABLE não-coalescidas** (`nk_coalesce_cols`
cobre só `cpf_cnpj, matricula, ano_mes, descricao_cargo`). Em prod:

- `municipio`: **90.047 rows NULL**.
- `nome_servidor`: **201 rows NULL**.

Em PostgreSQL, `UNIQUE INDEX` trata `NULL` como **distinto**. Logo essas
90k+ rows não seriam deduplicadas e o `ON CONFLICT` **não dispararia** → cada
re-run do bucket (o framework re-baixa o bucket corrente,
`refetch_recent_buckets=1`) **duplicaria** essas rows.

### 3. `tce_pb_licitacao` / `tce_pb_receita`

NK natural seria segura **hoje** (0 NULL nas cols não-coalescidas; dups são
todas full-row idênticas: licitação 79 grupos / 93 rows, receita 0). Mas
depender de auditoria de NULL a cada mudança de dados upstream é frágil.

## Decision

Migrar **as quatro tabelas TCE-PB para NK sintética md5**, exatamente como
`bolsa_familia` (ADR-0010) e as 7 tabelas `pb_extras` (`sql/35a-d`).

### Pontos críticos

1. **`_nk_md5 TEXT`** em cada tabela (`sql/42_tce_pb_synthetic_nk.sql`),
   populado por `trigger BEFORE INSERT` via
   `etl_admin.row_hash_md5(...)` (hash injetivo `array_to_json`, `sql/35a`).
   `nk_synthetic_md5=True` nos 4 specs → `build_upsert_sql` emite
   `ON CONFLICT (_nk_md5)`.

2. **Single source of truth do hash**: cada tabela tem
   `etl_admin.nk_md5_<tabela>_row(<tabela>)` (LANGUAGE sql STABLE) que é
   chamada **tanto pelo trigger** (rows novas) **quanto pelo populate** (rows
   legacy). Evita o drift de manter o hash duplicado (a despesa tem 41 cols).

3. **Hash de TODAS as colunas de negócio**, excluindo `id` e as colunas de
   **normalização** (`cnpj_basico`, `ano`, `cpf_digitos`, `cpf_digitos_6`,
   `nome_upper`, `cnpj_basico_proponente`, `cpf_digitos_proponente`) — que
   ficam NULL em rows recém-inseridas e preenchidas em rows legacy; incluí-las
   quebraria a idempotência.

4. **Populate batched** via `python -m etl.refresh_post_incremental
   --source tce_pb --populate-only` (psycopg2 `autocommit=True` + partial
   index temporário; o quirk PG16 de COMMIT-em-PROCEDURE via `psql -c/-f`
   também se aplica aqui — ver ADR-0010).

5. **`sql/42z_tce_pb_finalize.sql`**: preflight (`_nk_md5` populado) → dedupe
   por `_nk_md5` (keep `min(id)`, statement único em DO-block, sem
   CALL/COMMIT) → `UNIQUE INDEX CONCURRENTLY ix_tce_pb_<tabela>_nk_md5` →
   validação. Dedupe esperado: despesa 0, servidor ~23, licitação ~93,
   receita 0.

6. **Refresh das MVs PB** dependentes (L1→L2) em
   `etl/refresh_post_incremental.py:refresh_for_tce_pb` — sem isso o
   shadow rewarm/warm leria MVs stale e o swap atômico promoveria cache velho.

7. **`deploy.yml`**: detecta `TCE_PB_IN_SCOPE` e aplica `sql/42` → populate →
   `sql/42z` antes do runner, e `refresh_for_tce_pb` depois (espelha o bloco
   `bolsa_familia`).

### Idempotência cross-boundary (clássico → incremental)

Para que re-inserir um bucket já carregado pelo ETL clássico **não duplique**,
o `_nk_md5` da row re-inserida (trigger) deve igualar o da row legacy
(populate). Garantido porque:

- Ambos usam a **mesma** `nk_md5_<tabela>_row`.
- TEXT: clássico (`TRIM`) e framework (`build_typed_select` → `trim`) ambos
  aparam espaços.
- `DECIMAL(15,2)`: escala fixa pela coluna → `::text` canônico (`'N.NN'`) nos
  dois caminhos (validado: `10.50` armazenado → `'10.50'`).
- `DATE`: `to_char(col,'YYYY-MM-DD')`.
- `SMALLINT`: `::text`.

Resíduo de risco: cols TEXT com sentinelas raras (`'NULL'`, `'00/00/0000'`)
que o framework converte para NULL e o clássico manteve literais. Esperado
~zero em despesa; mitigado pelo **pré-flight de produção** (abaixo).

## Consequences

### Positivas

- TCE-PB ganha atualização incremental **idempotente** real (o gap original:
  servidor abril/2026 só tinha 4.040 de ~255k rows).
- Sem perda de registros distintos (despesa) nem double-load (servidor).
- Uniforme com `bolsa_familia` + `pb_extras` → uma única forma de revisar.

### Negativas / custos

- **Populate inicial** de ~40M rows (despesa 16M + servidor 22M + licitação
  318k + receita 1,2M): ~60-75 min, uma única vez. Execuções seguintes:
  `WHERE _nk_md5 IS NULL` → 0 rows, rápido.
- `+1` coluna `_nk_md5` + `UNIQUE INDEX` por tabela (overhead de espaço/escrita
  aceitável).

### Pré-flight obrigatório de produção (antes do 1º run real)

Como a idempotência cross-boundary depende de paridade de parsing
clássico↔incremental, antes do primeiro incremental de produção: rodar o
bucket corrente e **conferir o `rows_inserted`** — deve ser ≈ (contagem
upstream − contagem já carregada), **não** ≈ bucket inteiro. Se for ≈ bucket
inteiro, há divergência de parsing (double-load) e o run deve ser abortado e
investigado. Os `UNIQUE INDEX ix_tce_pb_*_nk_md5` impedem colisões exatas mas
não rows logicamente-iguais com hash divergente.

## Alternatives considered

- **NK natural + UNIQUE INDEX** (`sql/30`/`sql/31` originais): rejeitada —
  despesa tem 1037 colisões reais (perda de dados) e servidor tem 90k NULLs
  na NK (double-load). Frágil para licitação/receita (auditoria de NULL).
- **`DedupeStrategy.APPEND`** (sem `ON CONFLICT`): rejeitada — republish do
  bucket duplicaria tudo (o spec comenta isso).
- **Recarregar via ETL clássico** (`etl/19_tce_pb.py --anos 2026`): rejeitada
  — `INSERT` plano sem dedup duplicaria 2026 inteiro; e o usuário exige evitar
  ETL completo.

## References

- ADR-0004 (framework incremental P1-P6)
- ADR-0010 (Bolsa Família incremental — mesmo padrão synthetic md5)
- `sql/35a-d` (padrão `pb_extras`)
- `sql/42_tce_pb_synthetic_nk.sql`, `sql/42z_tce_pb_finalize.sql`
- `etl/refresh_post_incremental.py` (`populate_nk_md5_tce_pb`,
  `refresh_for_tce_pb`)
