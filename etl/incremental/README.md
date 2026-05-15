# ETL Incremental Framework

Framework para carga incremental e idempotente de fontes de dados governamentais
brasileiras (TCE-PB, Dados-PB e futuras).

## TL;DR

```bash
# Carga incremental de todas specs registradas
python -m etl.incremental.runner

# Apenas specs específicas
python -m etl.incremental.runner --only "tce_pb.tce_pb_despesa,dados_pb.pb_pagamento"

# Bootstrap inicial (uma vez antes do primeiro run)
python -m etl.incremental.bootstrap_watermark --all

# Status atual
psql -c "SELECT * FROM v_etl_status"
psql -c "SELECT * FROM v_etl_dlq_summary"
psql -c "SELECT * FROM v_etl_run_summary LIMIT 10"
```

## Princípios não-negociáveis (P1-P6)

1. 🔴 **NÃO CORROMPER DADOS EXISTENTES** (sobrepõe tudo)
2. **NÃO-DESTRUTIVO** — sem TRUNCATE/DROP/DELETE em targets
3. **AUDITÁVEL** — rastro completo, imutável pelo ETL role
4. **ERROR RESILIENT** — recuperável de qualquer crash
5. **FAST** — download condicional + idempotency
6. **ZERO TOLERANCE** — watermark nunca avança em failure; DLQ persiste mesmo em rollback do main_conn (referenciado nos headers das migrations `sql/22_etl_watermark.sql:23` e `sql/25_etl_rejected_rows.sql:21`)

## Arquitetura

### Fluxo de cada bucket

```
1. Conditional GET (HEAD probe + If-None-Match + If-Modified-Since)
   ├─ 304 Not Modified → skip download, NÃO toca target
   └─ 200 OK → baixa streaming + computa sha256
       ├─ sha256 == anterior → registra check, mas NÃO invalida
       └─ sha256 mudou → invalidate bucket_token

2. Se bucket_token já bate em etl_watermark E nada mudou: SKIP

3. _incremental_load (16 steps):
   - Validate CSV header → csv_header_hash
   - Stream CSV via csv.reader (RFC 4180) com '' → \\N (NULL)
   - COPY temp file → staging RAW (todas TEXT cols)
   - INSERT INTO staging_typed SELECT cast (BR/ISO format)
   - DELETE rows com NK NULL → DLQ + log (soft failure)
   - INSERT INTO target ON CONFLICT DO NOTHING
     (ON CONFLICT usa COALESCE/NULLIF para tratar '' = NULL)

4. Após bucket completo:
   - set_watermark com bucket_token determinístico
   - enqueue_cache_invalidation (web cache hook)
```

### Componentes

| Módulo | Responsabilidade |
|---|---|
| `etl/incremental/spec.py` | LoaderSpec dataclass |
| `etl/incremental/conn.py` | MainTxConn / LockConn / AutocommitDlqConn wrappers |
| `etl/incremental/locks.py` | pg_advisory_lock helpers |
| `etl/incremental/heartbeat.py` | HeartbeatThread + MasterWatchdog |
| `etl/incremental/parser.py` | csv.reader pre-parser + BR/ISO format helpers |
| `etl/incremental/staging.py` | staging tables lifecycle + UPSERT SQL |
| `etl/incremental/download.py` | conditional GET + sha256 invalidation |
| `etl/incremental/loader.py` | `_incremental_load` 16-step pipeline (private) |
| `etl/incremental/orchestrator.py` | `run_incremental_for_source` (public) |
| `etl/incremental/runner.py` | `python -m etl.incremental.runner` CLI |
| `etl/incremental/bootstrap_watermark.py` | Initial state capture |
| `etl/incremental/specs/` | LoaderSpec instances |
| `etl/incremental/db.py` | SECURITY DEFINER function wrappers |

## Defesa em camadas (P1)

1. **DB role primário** `etl_incremental`:
   - SELECT/INSERT/UPDATE em targets — sem DELETE/TRUNCATE/DROP
   - SELECT only em audit tables
   - CREATE em `etl_staging` schema apenas (não em `public`)
   - search_path locked, statement_timeout=30min

2. **SECURITY DEFINER functions** (em schema `etl_admin`):
   - Mutações de audit tables apenas via funções com `SET search_path` locked
   - Validation de status transitions, monotonicity, fence checks
   - 13+ funções: start_run, heartbeat_run, set_watermark, etc

3. **Imutabilidade triggers**:
   - bootstrap_target_* fields immutable após primeiro INSERT
   - etl_phase_log append-only para etl_incremental
   - DLQ e download_log: DELETE forbidden para etl_incremental

4. **Static check (CI)**: AST scan procurando `TRUNCATE`, `DROP TABLE`, etc

5. **Runtime regex** `IncrementalConn`: defesa secundária

## Idempotency (D1, D2, D9)

### `'' vs NULL` handling

Legacy ETL gravou `''` em algumas cols opcionais; nosso pre-parser converte `''` → NULL. Para ON CONFLICT funcionar:

```sql
CREATE UNIQUE INDEX ix_<table>_nk
ON <table> (
    nk_col_1, nk_col_2,                                  -- never-NULL
    COALESCE(NULLIF(nk_col_3, ''), '__NULL__'),          -- pode ser '' ou NULL
    COALESCE(NULLIF(nk_col_4, ''), '__NULL__'),
    ...
);
```

Configurado via `LoaderSpec.nk_coalesce_cols` (target names lowercase).

### bucket_token

UUID5 determinístico de `(source, table, bucket_id)`:
- Mesmo bucket = mesmo token
- `set_watermark` é NO-OP se token bate em etl_watermark
- `download_and_log` invalida bucket_token se sha256 mudou

### Schema versioning

Spec pode declarar `columns_per_bucket(bucket_id)` callable que retorna
`(cols, renames)` overrides. Útil para schema drift (e.g., TCE-PB mudou nomes em 2020).

## Como adicionar nova spec

1. Profilar NK candidata em prod read-only:
```sql
SELECT count(*) FROM (
  SELECT col1, col2, col3 FROM target
  GROUP BY 1,2,3 HAVING count(*) > 1
) d;
```

2. Criar UNIQUE INDEX expression-based:
```sql
CREATE UNIQUE INDEX CONCURRENTLY ix_<table>_nk
ON <target> (
    nk_col_1, nk_col_2,
    COALESCE(NULLIF(nk_col_3, ''), '__NULL__')
);
```

3. Criar spec em `etl/incremental/specs/<source>_<table>.py`:
```python
SPEC = LoaderSpec(
    source="my_source",
    table="my_target",
    natural_key=["NK_COL_1", "NK_COL_2", "NK_COL_3"],  # CSV names
    nk_coalesce_cols=("nk_col_3",),                     # target names lowercase
    cursor_strategy=CursorStrategy.MONTH_WINDOW,
    dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
    columns=[...],                  # CSV column order
    column_types={...},             # PG types
    column_renames={"CSV_NAME": "target_name"},
    csv_delimiter=";",
    encoding="latin-1",
    encoding_fallback="utf-8-sig",
    decimal_format="point",
    date_format="iso",
    watermark_col="DATA_X",         # CSV name
    watermark_type="string",
    file_pattern=lambda b: [...],
    bucket_from_filename=lambda n: ...,
    url_for_bucket=lambda b: [(url, fname)],
    enumerate_buckets=lambda: [...],
)
```

4. Registrar em `etl/incremental/runner.py::_load_all_specs()`.

5. Bootstrap em prod:
```bash
python -m etl.incremental.bootstrap_watermark --source my_source --table my_target
```

6. Primeiro run:
```bash
python -m etl.incremental.runner --only "my_source.my_target"
```

## Recovery

| Cenário | Procedimento |
|---|---|
| Run zumbi (status='running' há > 5min sem heartbeat) | `SELECT etl_admin.abort_stale_runs(5)` (orchestrator chama no preflight) |
| Watermark stale + data committed | Re-run incremental — idempotent via bucket_token + ON CONFLICT |
| Schema drift detectado | Verificar `csv_header_hash` em etl_phase_log; ajustar columns_per_bucket |
| DLQ inflando | Query `v_etl_dlq_summary`; investigate raw_line; fix source ou ajustar coerce |
| Manual rollback do watermark | `SELECT etl_admin.reset_watermark(source, table, new_value, reason, approver)` |
| Corruption suspeita | Audit via `etl_run_log` + `etl_phase_log` — append-only |

## Status atual (POC PB)

| Source | Tabela | Rows | Status |
|---|---|---|---|
| tce_pb | tce_pb_despesa | 15.83M | ✅ E2E validado |
| tce_pb | tce_pb_servidor | 21.78M | ✅ E2E validado |
| tce_pb | tce_pb_licitacao | 310k | ✅ E2E validado |
| tce_pb | tce_pb_receita | 1.19M | ✅ E2E validado |
| dados_pb | pb_pagamento | 4.8M+ | ⏳ Loading |
| dados_pb | pb_empenho | 1.7M | ⏳ Pending load |
| dados_pb | pb_contrato | 11k | ⚠️ 2022/2023 partial (CSV errors) |
| dados_pb | (13 tabelas extras) | - | ⏳ Specs criadas, load pendente |

## Próximas iterações

- Cache invalidation consumer em `web/warm_cache.py` (queue → re-warm específico)
- Profiling NK em prod para 13 Dados-PB specs novas
- Index creation para 13 Dados-PB specs novas
- E2E validation para todas 16 Dados-PB specs
- Dashboard observability (FastAPI route + template)
- Janitor cron (drop staging órfã, retention DLQ)
