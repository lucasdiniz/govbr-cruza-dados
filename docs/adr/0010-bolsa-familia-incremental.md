# ADR-0010: Bolsa Família incremental + histórico cumulativo

## Status

Accepted

## Date

2026-05-17

## Context

O ETL clássico do Bolsa Família (`etl/17_bolsa_familia.py` + `sql/17_schema_bolsa_familia.sql`)
era destrutivo:

1. `DROP TABLE bolsa_familia CASCADE` a cada execução.
2. `download_bolsa_familia` em `etl/00_download.py` baixava só o snapshot
   mais recente e **deletava ativamente** snapshots anteriores do disco
   (linhas 1272-1278: `if str(ym) not in old.name: old.unlink()`).
3. Resultado: a tabela `bolsa_familia` em qualquer momento continha
   apenas o **último mês** publicado pelo Portal da Transparência.

Limitações desse modelo:

- **Sem histórico**: queries que cruzam BF × servidor (`mv_servidor_pb_risco`,
  `_tmp_bf`) só conseguem detectar recebimento no mês corrente. Beneficiário
  que recebeu BF em 2024 mas não em 2026-01 é invisível no Q42/Q80.
- **Sem auditoria temporal**: relatórios de fraude não conseguem citar
  "essa pessoa recebeu BF de 2023-05 a 2024-08" — só o snapshot atual.
- **Re-download massivo**: 600 MB / mês baixados todo deploy.

Após smoke test empírico (2026-05-17) na base local e VM (read-only),
descobrimos que **a NK natural não é única em produção**:

- 18,7M rows em 1 snapshot (202601).
- **21,3% das rows (~4M)** têm `cpf_favorecido = ''` — adultos reais cujo
  CPF não está vinculado no CADUNICO (hipótese inicial "menores de 16 anos"
  foi rejeitada: apenas 305 rows têm o nome mascarado especial).
- Portal publica **parcelas retroativas** no mesmo `mes_competencia` com
  `mes_referencia` diferentes (legítimo — recebimentos atrasados).
  Exemplo real: SUELENE recebeu 8 parcelas em janeiro/26 referentes a
  8 meses distintos (mai/25 a jan/26).
- NK trio (`mes_competencia, cpf_favorecido, nis_favorecido`): 93.569
  grupos duplicados.
- NK 5-uplo (+ `mes_referencia` + `cd_municipio_siafi`): ainda 36 duplicados.
- 9 grupos com **todas 9 cols iguais** (22 rows) — true duplicates do
  ETL clássico legacy.

## Decision

Migrar Bolsa Família para o framework ETL incremental (P1-P6, ADR-0004),
acumulando snapshots mensais cumulativamente.

### Pontos críticos

1. **NK synthetic md5** (padrão `pb_extras` em `sql/35a-d`):
   - `_nk_md5 TEXT` em `bolsa_familia`.
   - Trigger `BEFORE INSERT compute_nk_md5_bolsa_familia` calcula hash das
     9 cols via `etl_admin.row_hash_md5(...)`.
   - `UNIQUE INDEX CONCURRENTLY ix_bolsa_familia_nk_md5 ON bolsa_familia(_nk_md5)`.
   - Spec `nk_synthetic_md5=True` → `build_upsert_sql` emite
     `ON CONFLICT (_nk_md5) DO NOTHING`.
   - **Justificativa**: cobre 100% sem perda de dado. NK natural exigiria
     descartar os 21% sem CPF ou aceitar duplicação retroativa.

2. **DedupeStrategy = UPSERT_DO_NOTHING**:
   - Intenção do incremental: **acumular novos meses, não corrigir
     existentes**. Reruns nunca alteram rows commitadas.
   - `refetch_recent_buckets=1` cobre republish atrasado do mês corrente
     (DO_NOTHING garante dados commitados intactos).

3. **Esquema canônico idempotente** (`sql/17_schema_bolsa_familia.sql`):
   - `CREATE TABLE IF NOT EXISTS` em vez de `DROP CASCADE + CREATE`.
   - Adicionado ao `SQL_FILES` em `etl/01_schema.py` (antes só era aplicado
     pela fase 17 classica que virou no-op).

4. **Migration `sql/41_bolsa_familia_incremental.sql`** (defs idempotent):
   - `ADD COLUMN IF NOT EXISTS` para `cpf_digitos` + `inserted_at` + `_nk_md5`.
   - `COMMENT ON COLUMN cpf_digitos` documenta que armazena **6 dígitos
     centrais** do CPF mascarado (não 11 como em outras tabelas).
   - `CREATE OR REPLACE FUNCTION etl_admin.compute_nk_md5_bolsa_familia`.
   - `CREATE TRIGGER trg_compute_nk_md5 BEFORE INSERT`.
   - `CREATE OR REPLACE PROCEDURE etl_admin.populate_nk_md5_bolsa_familia`
     (batched + COMMIT entre batches).

5. **Populate `_nk_md5` via psycopg2 autocommit**:
   - PG 16 wrappa `CALL` em transação implícita quando invocada via
     `psql -c` ou `psql -f` (testado), causando `ERRO: encerramento de
     transação inválido` no `COMMIT` interno da PROCEDURE.
   - Workaround: `python -m etl.refresh_post_incremental --source
     bolsa_familia --populate-only` usa `conn.autocommit = True` explícito.
   - Logica equivalente à PROCEDURE mas client-side.

6. **`sql/41z_bolsa_familia_finalize.sql`** (dedupe + UNIQUE INDEX):
   - Pré-flight valida `_nk_md5` 100% populada.
   - DELETE de duplicates (ROW_NUMBER PARTITION BY `_nk_md5`, mantém
     menor `id` = mais antiga). Empirical 22 rows em 9 grupos.
   - `CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_bolsa_familia_nk_md5`.
   - Validação `pg_index.indisvalid` no fim (hard-fail se INVALID).

7. **Refresh post-incremental** (`etl/refresh_post_incremental.py`):
   - `SOURCE_REFRESH_FNS` dict — extensível para futuras sources.
   - `refresh_for_bolsa_familia`:
     1. ANALYZE bolsa_familia.
     2. REFRESH mv_pessoa_pb CONCURRENTLY (L1).
     3. `_tmp_bf` TRUNCATE+INSERT atomic consumindo `sql/41c_tmp_bf_body.sql`
        (DROP `_tmp_bf` falha — `mv_servidor_pb_risco` depende por OID).
     4. REFRESH mv_servidor_pb_risco CONCURRENTLY.
     5. Detecta via `pg_depend` se `mv_municipio_pb_kpi_score` depende
        de `mv_pessoa_pb`; se sim, REFRESH CONCURRENTLY.
   - Hard-fail: qualquer step lança → deploy aborta (warm cache subsequente
     não roda com dados velhos).

8. **Spec `etl/incremental/specs/bolsa_familia.py`**:
   - `cursor_strategy=MONTH_WINDOW`, `watermark_col=MES_COMPETENCIA`.
   - `is_zip_source=True` (framework extrai ZIP automaticamente).
   - `encoding="latin-1"` (Portal usa Latin-1 com acentos preservados).
   - `decimal_format="br"` (valor com vírgula: `1886,00`).
   - `derived_columns={"cpf_digitos": "REGEXP_REPLACE(CPF_FAVORECIDO, '[^0-9]', '', 'g')"}`
     — **UPPERCASE** (raw staging col name, não rename target).
   - `enumerate_buckets`: 2023-03 (Novo BF) até mês atual.

9. **Feature nova no framework: `csv_header_rewrites`**:
   - Campo em `LoaderSpec` (default `{}`).
   - Aplicado em `parser.validate_csv_header` ANTES do match com `spec.columns`.
   - Necessário porque o Portal publica headers raw com acentos e espaços
     (`"MÊS COMPETÊNCIA"`) — PostgreSQL CREATE TABLE staging com esses
     identifiers falha por syntax.
   - Spec BF mapeia 9 headers raw para SQL-safe (`MES_COMPETENCIA`, etc).

10. **Download dual** (compromisso com transição):
    - `download_bolsa_familia` em `etl/00_download.py` mantido em
      `all_downloaders` — clássico ETL continua tendo cache hot do último
      mês para inspeção manual.
    - Mudança mínima: linhas 1272-1278 removidas (unlink destrutivo).
    - `etl/17_bolsa_familia.py:run()` virou no-op (preserva índice de fase).
    - `_CSV_DIRS["etl.17_bolsa_familia"]` removido em `etl/run_all.py`
      (evita limpeza prematura entre fase clássica e framework).

11. **Frontend `/api/servidor/detalhes`**:
    - Removido `LIMIT 5`. Retorna histórico completo: agregados + lista
      cronológica `LIMIT 240` (20 anos × 12 meses defensivo).
    - Response shape: `{parcelas: [...], stats: {qtd_parcelas, qtd_meses,
      total_recebido, valor_medio, primeiro_mes, ultimo_mes,
      qtd_durante_vinculo, total_durante_vinculo}}`.
    - Cache in-memory via `web.db.cached_query` por
      `servidor:<cpf6>:<NOME>:bolsa_familia` (TTL padrão).
    - `servidor-dialog.js`: nova seção dedicada com stat cells + `<details>`
      nativo + dual labels (cidadão/auditor). Linhas dentro do período do
      vínculo TCE-PB recebem highlight visual.

### Deploy

Step `ETL: Incremental` em `.github/workflows/deploy.yml`:

```
if BF in scope (incremental_only vazio OU contém bolsa_familia.bolsa_familia):
    psql -f sql/41_bolsa_familia_incremental.sql    # defs idempotent
    python -m etl.refresh_post_incremental --source bolsa_familia --populate-only
    psql -f sql/41z_bolsa_familia_finalize.sql       # dedupe + UNIQUE INDEX

python -m etl.incremental.runner --only <inputs.incremental_only>

if BF in scope:
    python -m etl.refresh_post_incremental --source bolsa_familia  # MVs

python -m etl.22_mv_sitemap  # mv_empresa_municipio_pagantes (sitemap)
```

Gates de cache (`ANALYZE`, `Reset shadow`, `Warm cache`) passaram a incluir
`inputs.etl_phase == 'incremental'` — warm automático sem precisar
`warm_cache=true` manual.

### Padrão de uso (acionamento)

```bash
# Carregar todos os meses faltantes + refresh MVs + warm cache:
gh workflow run deploy.yml -f etl_phase=incremental

# Só Bolsa Família (sem reprocessar TCE-PB/Dados-PB):
gh workflow run deploy.yml -f etl_phase=incremental \
    -f incremental_only=bolsa_familia.bolsa_familia
```

## Trade-offs aceitos

1. **Synthetic NK md5 em vez de NK natural**:
   - Contra: hash não tem significado semântico; uma row deletada e
     re-inserida com mesmo conteúdo "perde a história" do `inserted_at`.
   - Pro: cobre 100% sem perda de dado e segue padrão `pb_extras` já
     testado em prod (7 tabelas, 60M+ rows). Trigger BEFORE INSERT
     popula automaticamente, então `INSERT` do framework não precisa
     calcular o hash.

2. **UPSERT_DO_NOTHING em vez de DO_UPDATE**:
   - Contra: republish do Portal com correção de valor em mês já carregado
     não atualiza a row local.
   - Pro: previsibilidade total. Reruns sempre seguros. F1 da rodada de
     revisão (predicate `EXCLUDED.{wm} > {target}.{wm}` estrito em
     `staging.py:244`) tornaria DO_UPDATE ineficaz para correções no
     mesmo bucket anyway.

3. **Populate via psycopg2 (não PROCEDURE)**:
   - Contra: lógica duplicada (PROCEDURE em SQL + Python). Drift potencial.
   - Pro: contorna bug de PG 16 (`COMMIT em PROCEDURE` falha em
     `psql -c/-f`). PROCEDURE serve como documentação SQL e ponto de
     entrada para manutenção emergencial (`psql -f sql/41` + `psql -c
     "CALL etl_admin.populate_nk_md5_bolsa_familia();"` — funciona se
     rodado em sessão psql interativa).

4. **`/api/servidor/detalhes` cache in-memory, não server-side persistente**:
   - Contra: cache morre em restart, e cada worker tem cache próprio.
   - Pro: zero acoplamento com `LIMIT 200` dos top servidores
     (`web/queries/cidade.py:805`). ADR-0011 (proposta) discute remover
     esse LIMIT — se acontecer, cache server-side teria que migrar para
     lazy warm. In-memory escapa dessa interação.

5. **`_tmp_bf` SELECT body duplicado em `sql/12_views.sql` + `sql/41c_tmp_bf_body.sql`**:
   - Contra: drift entre os dois arquivos quebra `mv_servidor_pb_risco`.
   - Pro: `12_views.sql` é monolítico (executado por `etl/21_views.py`
     via `execute_sql_file` sem include dinâmico). Comentário cross-ref
     no `12_views.sql:563` + smoke test cobrindo isso reduzem o risco.
   - Padrão similar já documentado como tech debt em
     `sql/15c_rebuild_tmp_for_servidor.sql:30-33`.

## Consequences

### Positivas
- BF acumula meses ao longo do tempo (auditoria forense possível).
- Queries Q38/Q40/Q42/Q74/Q80 + relatórios podem citar período completo
  de recebimento BF de cada beneficiário.
- Re-download massivo do Portal cai (HEAD probe + `If-None-Match` do
  framework). 600 MB/mês → 0 quando mês não mudou.
- Frontend de servidor mostra histórico real (não apenas "Sim/Não").

### Negativas / Riscos
- Tabela `bolsa_familia` cresce **~600 MB/mês** com snapshots cumulativos.
  18,7M rows hoje → ~600M rows em 5 anos. Plano de mitigação: revisitar
  particionamento ou archive de meses > 5 anos no momento certo.
- Trigger `BEFORE INSERT` em cada INSERT adiciona overhead — medido em
  ~5% do tempo de COPY no smoke local.
- `populate_nk_md5` em 18,7M rows local levou ~90min (disco rotacional).
  Em SSD prod estimamos 15-30 min. Step rodando em deploy `incremental`
  significa primeira aplicação leva ~30min adicionais.

## References

- [ADR-0001: Sem pandas](./0001-no-pandas.md) — princípio de streaming.
- [ADR-0002: MVs layered](./0002-mv-layered.md) — `_tmp_bf` faz parte L1/L2.
- [ADR-0004: ETL incremental](./0004-etl-incremental-framework.md) —
  princípios P1-P6 que esta migração aplica.
- [ADR-0011 (Proposed): Remover LIMIT top tabelas](./0011-remover-limit-top-tabelas.md)
  — interage com cache do endpoint `/api/servidor/detalhes`.
- `sql/35a-d` — padrão synthetic NK md5 estabelecido em PR anterior.
- `sql/15c_rebuild_tmp_for_servidor.sql` — padrão TRUNCATE+INSERT atomic
  para `_tmp_*` tables.
- `etl/incremental/specs/bolsa_familia.py` — spec final.
