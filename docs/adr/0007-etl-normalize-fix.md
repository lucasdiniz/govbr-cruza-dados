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

2. **Funções `is_valid_cpf(text)` e `is_valid_cnpj(text)`**: PL/pgSQL
   `IMMUTABLE STRICT` que validam DV matemático (módulo 11, algoritmo
   oficial RFB). Rejeitam NULL, length mismatch, chars não-numéricos e
   sequências triviais (`000000000-00`, `111...`, etc).

3. **Fase 9 nova (2 UPDATEs separados + cpf_digitos via DV)**:
   - **UPDATE 1** anula `cnpj_basico` contaminado: `WHERE cnpj_basico IS NOT NULL AND NOT EXISTS estabelecimento`. Cobre qualquer doc 14-char não-RFB (CPF padded, MEI não-sincronizado, lixo).
   - **UPDATE 2** extrai `cpf_digitos` **apenas quando** o doc NÃO é CNPJ válido E os 11 chars (posição 4-14) SÃO CPF válido:
     ```sql
     UPDATE … SET cpf_digitos = SUBSTRING(doc FROM 4 FOR 11)
     WHERE cpf_digitos IS NULL
       AND LENGTH(doc) = 14
       AND NOT EXISTS (estabelecimento)
       AND NOT is_valid_cnpj(doc)              -- doc não é CNPJ matemático
       AND is_valid_cpf(SUBSTRING(doc FROM 4 FOR 11));
     ```

   **Por que DV check em vez de prefix heurístico `LEFT '000'`**: validação empírica em 16/05/2026 mostrou que docs não-RFB com prefix ≠ `000` (ex: `65494241000180` MEI André Japiassu, `04000000062504` Min. Fazenda) têm DV CNPJ **válido** — são CNPJs reais não-sincronizados, não "lixo". Heurística por prefix rejeitaria esses corretamente mas não distingue de CPFs com primeiro dígito ≠ 0 (hipotético). DV check é o discriminator definitivo.

   Aplicado em 10 tabelas (`tce_pb_despesa` + 9 `pb_*`). Idempotente: `UPDATE 1 WHERE cnpj_basico IS NOT NULL`; `UPDATE 2 WHERE cpf_digitos IS NULL`.

4. **`ALTER TABLE ADD COLUMN cpf_digitos VARCHAR(11)` + index parcial**:
   `WHERE cpf_digitos IS NOT NULL` evita inchar índice com rows-de-CNPJ.

### Comportamento garantido para MEIs/CNPJs novos não-sincronizados

| Cenário | `cnpj_basico` | `cpf_digitos` |
|---|---|---|
| CNPJ real em RFB | populado | NULL |
| MEI/CNPJ real **não em RFB** | NULL temporariamente | NULL (DV CNPJ válido bloqueia extração) |
| CPF padded válido | NULL | populado (DV CPF passa nos chars 4-14) |
| Doc lixo (DVs inválidos) | NULL | NULL |

Quando RFB sincronizar com o MEI/CNPJ novo, próximo run de `etl.15_normalizar` é idempotente — Fase 5/7 popula `cnpj_basico` retroativamente, sem precisar de intervenção manual.

### Migration standalone

`sql/15a_fix_cnpj_basico_contamination.sql`: mesmo cleanup mas como
script SQL puro, executável via `psql -f` sem precisar rodar
`etl.15_normalizar` inteiro. Necessário pra deploy cirúrgico em prod.

### Pre-flight para `mv_q67_dated_pb`

`sql/15b_add_unique_index_mv_q67.sql`: `CREATE UNIQUE INDEX CONCURRENTLY`
em `mv_q67_dated_pb (municipio, ano, cnpj_basico) NULLS NOT DISTINCT`
(PG15+). `mv_q67_dated_pb` foi criada via hotfix (PR #54) sem UNIQUE
INDEX — sem ele, `REFRESH MATERIALIZED VIEW CONCURRENTLY` falha.
`CREATE INDEX CONCURRENTLY` não bloqueia leituras.

Por que `NULLS NOT DISTINCT` (e não expression index com `COALESCE`):
PostgreSQL exige UNIQUE INDEX com colunas plain (não expressões) para
`REFRESH MATERIALIZED VIEW CONCURRENTLY` (achado em GPT-5.5 review).
`NULLS NOT DISTINCT` força Postgres a tratar NULLs como iguais sem
recorrer a expressão.

### Rebuild atômico de `_tmp_*` para `mv_servidor_pb_risco`

`mv_servidor_pb_risco` depende de 5 backing tables (`_tmp_socio_empresas`,
`_tmp_fornecedor_gov`, `_tmp_conflito`, `_tmp_bf`, `_tmp_duplo`) populadas
durante `etl.21_views`. `REFRESH MATERIALIZED VIEW CONCURRENTLY` recomputa
a MV a partir dessas tables — mas se elas estão stale (contaminadas), o
REFRESH propaga a contaminação.

Das 5 tables, apenas 2 sofrem do bug:
- `_tmp_fornecedor_gov` — lê `tce_pb_despesa`
- `_tmp_conflito` — lê `_tmp_d_agg` (que vem de `tce_pb_despesa`)

`sql/15c_rebuild_tmp_for_servidor.sql`: rebuild atômico (transaction) via
`TRUNCATE + INSERT` (preserva dependência metadata com `mv_servidor_pb_risco`).
Tempo estimado: 5-15 min em prod.

⚠️ Drift risk: 15c duplica lógica de `sql/12_views.sql:495-561`. Se
aquela seção mudar, atualize 15c.

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

Três inputs novos em `.github/workflows/deploy.yml`:

- `run_normalize_fix` (bool): executa `sql/15a_fix_cnpj_basico_contamination.sql`
  + `sql/15b_add_unique_index_mv_q67.sql`. Roda APÓS ETL phases, ANTES
  do warm.
- `rebuild_tmp_for_servidor` (bool): executa `sql/15c_rebuild_tmp_for_servidor.sql`.
  Necessário antes de `refresh_mvs=mv_servidor_pb_risco`.
- `refresh_mvs` (CSV): executa `REFRESH MATERIALIZED VIEW CONCURRENTLY`
  em cada MV listada. Sanitizado regex `[a-zA-Z0-9_,]`.

Todos os 3 acionam VM auto-resize para B4 + Premium SSD via preflight
(achado em GPT-5.5 review — antes apenas `etl_phase != web`, `warm_cache`
e `rewarm_cache_keys` acionavam).

Sequência típica:

```bash
# 1. Aplicar cleanup ETL + UNIQUE INDEX mv_q67 + rebuild _tmp_* (zero downtime)
gh workflow run deploy.yml -f etl_phase=web \
  -f run_normalize_fix=true \
  -f rebuild_tmp_for_servidor=true

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
