# Copilot instructions — govbr-cruza-dados

ETL pipeline (Python 3.10+ / PostgreSQL 16) that loads ~350M records from ~18 Brazilian open-data sources and cross-references them by CNPJ/CPF to detect fraud. Includes a FastAPI frontend for municipality profiles.

## Setup & commands

Config is loaded from `.env` by `etl/config.py` (see `.env.example`). `DATA_DIR` points at raw CSV/JSON downloads; `DSN` is built from `POSTGRES_*` vars.

```bash
pip install -e .                  # core deps
pip install -e .[web]             # + FastAPI/uvicorn/jinja2

python -m etl.run_all             # full ETL (23 phases)
python -m etl.run_all 4           # resume from phase N (1-based)
python -m etl.00_download         # downloads only
python -m etl.probe_sources       # test source availability (runs in deploy)

python -m etl.run_queries                 # run all Q## fraud queries → resultados/
python -m etl.run_queries --query Q03     # single query

python -m uvicorn web.main:app --port 8000
python -m web.warm_cache --pb             # warm web_cache table
```

No automated test suite exists. Basic validation: `python -m compileall etl -q`.

## Architecture

**Phase-based ETL (`etl/run_all.py`).** 23 phases in a fixed list; each phase is a module with a `run()` function. Order matters — later phases depend on tables/columns created earlier. To resume mid-pipeline, pass the 1-based phase index. Phase 0 is download, phase 17 (`15_normalizar.py`) creates normalized CPF/CNPJ digit columns that every cross-source join relies on, phase 18 (`21_views.py`) builds MVs.

**Automatic disk cleanup.** After each phase's `run()` succeeds, `_cleanup_csvs` deletes the raw CSV dirs listed in `_CSV_DIRS` (e.g. `etl.03_rfb` → `rfb/`). Shared dirs in `_SHARED_DIRS` (`rfb/`, `tse/`) are only removed once **all** dependent phases have succeeded. When adding a new phase that consumes existing raw files, register it in `_SHARED_DIRS` or the directory will be wiped before your phase runs.

**Schema in `sql/`.** Numbered `.sql` files executed by `etl.db.execute_sql_file`. `sql/11_indices.sql` and `sql/19_indices_queries.sql` hold the indices the fraud queries depend on — changing column names there usually breaks queries in `queries/` and `web/queries/registry.py`.

**Entity resolution.** CPFs come masked in different formats per source (see README “Entity Resolution”). Phase 17 writes `cpf_digitos` / `cpf_cnpj_norm` columns so cross-source joins are equality joins, not LIKE/regex. Prefer joining on these normalized columns. For supplier identity, use full `cpf_cnpj` (14 digits) not `cnpj_basico` (8 digits) to avoid CPF/CNPJ prefix collisions — filter with `EXISTS (SELECT 1 FROM estabelecimento …)` to exclude CPFs when a query should only hit real CNPJs.

**Fraud queries (`queries/*.sql`).** Each file groups queries by theme; individual queries are labeled `Q01`…`Q310` in SQL comments. `etl/run_queries.py` parses them with a custom splitter (`split_sql_statements`) that tracks quotes and dollar-quoting — query bodies are free to contain `;`. Results land in `resultados/Q##_*.csv`.

**Materialized views (`sql/12_views.sql`).** Built by phase 18 (`etl.21_views`). Layered: L1 independent MVs (`mv_empresa_governo`, `mv_pessoa_pb`, `mv_municipio_pb_risco`, `mv_servidor_pb_base`) → L2 MVs that depend on them (`mv_servidor_pb_risco`, `mv_empresa_pb`, `mv_rede_pb`) → plain views (`v_risk_score_empresa`, `v_risk_score_pb`). The file drops everything in reverse-dependency order at the top; when adding an MV keep that pattern and add a `REFRESH MATERIALIZED VIEW CONCURRENTLY` line in the footer comment. The web UI reads heavily from `mv_municipio_pb_risco`, `mv_servidor_pb_risco`, and `mv_empresa_pb` — breaking a column there cascades into `web/queries/registry.py`.

**Reports (`relatorios/`).** Markdown investigations (40+) written against query outputs in `resultados/`. Each report cites CNPJs/CPFs from real data; before merging new reports or editing identifiers, run `python scripts/audit_report_identifiers.py [--report relatorios/foo.md]` — it validates CNPJs against the local `empresa`/`estabelecimento` tables. CPF validation is best-effort (most CPFs are masked).

**Web app (`web/`).** FastAPI + Jinja2, no ORM — raw SQL via `web/db.py` pool. Two query flavours per cidade query are registered in `web/queries/registry.py`: `sql_full` (all time) and optional `sql_full_dated` that accepts `%(data_inicio)s`, `%(data_fim)s`, `%(ano_inicio)s`, `%(ano_fim)s`, `%(ano_mes_inicio)s`, `%(ano_mes_fim)s`. Results are cached in a `web_cache` PostgreSQL table; `web/warm_cache.py` pre-computes both all-time and current-year variants. PB municipalities use TCE/dados.pb tables; other states fall back to PNCP.

## Conventions

- **No pandas.** ETL streams line-by-line and loads via `COPY FROM STDIN` (see `etl/db.py`: `copy_from_stream`, `copy_csv_streaming`, `batch_insert`). Target box is 16GB RAM — don't introduce DataFrame-based loads.
- **BR data parsing** lives in `etl/utils.py` (`parse_date_br`, `parse_decimal_br`, `clean_cpf`, `clean_cnpj`, `extract_cpf_masked`, `normalize_name`). Reuse these rather than reimplementing; date/decimal inputs come in multiple formats per source.
- **RFB encoding is latin-1** (`RFB_ENCODING` in `etl/config.py`); use `latin1_lines` when reading RFB CSVs.
- **Portuguese is the working language** for identifiers, comments, SQL, query titles, and commit messages; match that style.
- **Queries are numbered globally** (Q01-Q310). When adding one, keep the `-- Q##:` comment header so `run_queries.py` and the registry can find it, and add the matching index in `sql/19_indices_queries.sql` if the query is expected to run in the web UI (queries time out at `QueryDef.timeout_sec`, default 30s).
- **Deploy is GitHub-Actions-driven** against a self-hosted runner (`.github/workflows/deploy.yml`). The `etl_phase` input is the 1-based position in the `run_all` phases list (phase 0 = Download counts as item 1). `etl_phase=sql` runs indices/normalization/views only; `etl_phase=web` just syncs code and restarts systemd units from `deploy/`.
- **Do not commit** files in the repo root like `db_*.txt`, `pg_*.txt`, `mv_status.txt`, `*_debug*.txt`, `*.log`, `q##_result.csv` — they're scratch outputs from local DB inspection.

## Git

Commit trailer required by tooling:

```
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```
