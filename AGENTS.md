# AGENTS.md

> **Instructions for AI coding agents** working in `lucasdiniz/govbr-cruza-dados`.
> Read by GitHub Copilot CLI, Claude Code, Cursor, Aider, Codex and any tool
> that follows the [agents.md](https://agents.md) convention. `CLAUDE.md` and
> `.github/copilot-instructions.md` are short pointers to this file
> ([ADR-0008](docs/adr/0008-agents-md-canonical.md)).
>
> Human contributors: see [`README.md`](README.md) and [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Project at a glance

ETL pipeline (Python 3.10+ / PostgreSQL 16) that loads ~350M records from ~18
Brazilian open-data sources and cross-references them by CNPJ/CPF to detect
fraud. Includes a FastAPI/Jinja2 frontend at
[transparenciapb.org](https://transparenciapb.org) for municipal profiles.

**Working language is Portuguese (BR)** for identifiers, comments, SQL, query
titles, commit messages, PR descriptions, issues and user-facing strings. This
file is in English so generic AI agents can parse it; everything you produce in
the repo should be PT-BR.

## Documentation map (read in this order on a fresh task)

1. [`README.md`](README.md) — project overview, quick start, full feature list.
2. [`docs/architecture.md`](docs/architecture.md) — **landing page** with 7 Mermaid
   diagrams (data flow, entity resolution, ERD, MV layers, shadow rewarm,
   deploy pipeline).
3. [`docs/glossario.md`](docs/glossario.md) — 60+ domain terms (empenho, UG, CEIS,
   LGPD, etc.).
4. [`docs/onboarding.md`](docs/onboarding.md) — clone → `uvicorn` in 3 paths.
5. [`CONTRIBUTING.md`](CONTRIBUTING.md) — code/commit/PR conventions, what you
   can and can't touch.
6. **Area guides** (only the one(s) relevant to your task):
   - [`docs/etl-guide.md`](docs/etl-guide.md) — classic phase-based ETL
   - [`docs/etl-incremental-guide.md`](docs/etl-incremental-guide.md) — incremental framework (P1-P6)
   - [`docs/web-guide.md`](docs/web-guide.md) — query/route/template/MD3 component
   - [`docs/queries-guide.md`](docs/queries-guide.md) — adding Q##
   - [`docs/mv-guide.md`](docs/mv-guide.md) — adding Materialized Views
   - [`docs/cache.md`](docs/cache.md) — `web_cache` + shadow rewarm
   - [`docs/deploy.md`](docs/deploy.md) — `deploy.yml` inputs and scenarios
   - [`docs/ops.md`](docs/ops.md) — runbooks (rollback, restore, backup)
7. [`docs/adr/`](docs/adr/) — Architecture Decision Records (the institutional memory).

## Setup & commands

Config loaded from `.env` by `etl/config.py` (see `.env.example`). `DATA_DIR`
points at raw CSV/JSON downloads; `DSN` is built from `POSTGRES_*` vars.

```bash
pip install -e .                  # core deps
pip install -e .[web]             # + FastAPI/uvicorn/jinja2

python -m etl.run_all             # full ETL (24 phases incl. Download)
python -m etl.run_all 4           # resume from phase N (1-based index into phases list)
python -m etl.00_download         # downloads only
python -m etl.probe_sources       # test source availability

python -m etl.run_queries                 # run all Q## fraud queries → resultados/
python -m etl.run_queries --query Q03     # single query

python -m uvicorn web.main:app --port 8000
python -m web.warm_cache --pb             # warm web_cache table
```

No automated test suite outside `tests/incremental/` exists yet. Basic
validation for ETL changes: `python -m compileall etl -q`.

## Architecture (essentials)

**Phase-based ETL** (`etl/run_all.py`): 24 phases in a fixed list (`phases`);
each phase is a module with a `run()` function. Order matters — later phases
depend on tables/columns created earlier. Phase 17 (`15_normalizar.py`) creates
normalized CPF/CNPJ digit columns; phase 18 (`21_views.py`) builds MVs. Full
detail: [`docs/etl-guide.md`](docs/etl-guide.md).

**Automatic disk cleanup**: after each phase `run()` succeeds, `_cleanup_csvs`
deletes raw CSV dirs in `_CSV_DIRS`. Shared dirs in `_SHARED_DIRS` (`rfb/`,
`tse/`) only get removed once **all** dependent phases have succeeded. When
adding a phase that consumes existing raw files, register it in `_SHARED_DIRS`
or the directory will be wiped before your phase runs.

**Schema** in `sql/`: numbered `.sql` files executed by `etl.db.execute_sql_file`.
`sql/11_indices.sql` and `sql/19_indices_queries.sql` hold the indices the
fraud queries depend on — changing column names there usually breaks queries
in `queries/` and `web/queries/registry.py`.

**Entity resolution**: CPFs come masked in different formats per source. Phase
17 writes `cpf_digitos` / `cpf_cnpj_norm` columns so cross-source joins are
equality joins, not LIKE/regex. **Always join on these normalized columns.**
For supplier identity, use full `cpf_cnpj` (14 digits), **not `cnpj_basico`**
(8 digits — collides with CPFs); filter with `EXISTS (SELECT 1 FROM
estabelecimento …)` to exclude CPFs when a query should only hit real CNPJs.

**Fraud queries** (`queries/*.sql`): labeled `Q01`…`Q310` in SQL comments.
`etl/run_queries.py` parses with a custom splitter (`split_sql_statements`)
that tracks quotes and dollar-quoting — query bodies are free to contain `;`.
Results land in `resultados/Q##_*.csv`.

**Materialized views** (`sql/12_views.sql`): layered — **L1** independent MVs
(`mv_empresa_governo`, `mv_pessoa_pb`, `mv_municipio_pb_risco`,
`mv_servidor_pb_base`) → **L2** MVs that depend on them (`mv_servidor_pb_risco`,
`mv_empresa_pb`, `mv_rede_pb`, `mv_municipio_pb_kpi_score`,
`mv_municipio_pb_mapa`, `mv_q67_dated_pb`) → plain views
(`v_risk_score_empresa`, `v_risk_score_pb`). The file drops everything at
the top with `CASCADE` in intended reverse-dependency order, then recreates
L1 → L2 → views. When adding an MV, follow the pattern in both blocks **and**
add a `REFRESH MATERIALIZED VIEW CONCURRENTLY` line in the footer comment
(needs a `UNIQUE INDEX` on the MV). The L2 list above is the current set;
treat `sql/12_views.sql` as the source of truth. Detail:
[`docs/mv-guide.md`](docs/mv-guide.md) and [ADR-0002](docs/adr/0002-mv-layered.md).

**Web app** (`web/`): FastAPI + Jinja2, **no ORM** — raw SQL via `web/db.py`
pool. Two query flavours per cidade query are registered in
`web/queries/registry.py`: `sql_full` (all time) and optional `sql_full_dated`
that accepts `%(data_inicio)s`, `%(data_fim)s`, `%(ano_inicio)s`, `%(ano_fim)s`,
`%(ano_mes_inicio)s`, `%(ano_mes_fim)s`. Results cached in `web_cache`
PostgreSQL table; `web/warm_cache.py` pre-computes both all-time and
current-year variants. PB municipalities use TCE/dados.pb tables; other states
fall back to PNCP. Rationale: [ADR-0005](docs/adr/0005-no-orm-web.md).

**Reports** (`relatorios/`): markdown investigations citing CNPJs/CPFs from
real data. Before merging new reports or editing identifiers, run
`python scripts/audit_report_identifiers.py [--report relatorios/foo.md]`.

## Conventions

- **No pandas.** ETL streams line-by-line and loads via `COPY FROM STDIN` (see
  `etl/db.py`: `copy_from_stream`, `copy_csv_streaming`, `batch_insert`).
  Target box is 16GB RAM — don't introduce DataFrame-based loads.
  [ADR-0001](docs/adr/0001-no-pandas.md).
- **BR data parsing** lives in `etl/utils.py` (`parse_date_br`,
  `parse_decimal_br`, `clean_cpf`, `clean_cnpj`, `extract_cpf_masked`,
  `normalize_name`). Reuse these.
- **RFB encoding is latin-1** (`RFB_ENCODING` in `etl/config.py`); use
  `latin1_lines` when reading RFB CSVs.
- **Queries are numbered globally** (Q01–Q310). Keep the `-- Q##:` comment
  header so `run_queries.py` and the registry can find it. Add a matching index
  in `sql/19_indices_queries.sql` if the query is expected to run in the web UI
  (queries time out at `QueryDef.timeout_sec`, default 30s).
- **Reports mask CPFs** as `***.NNN.NNN-**` (keeps the 6 middle digits, mirrors
  `cpf_digitos_6` in MVs). CNPJs stay fully visible (public RFB data).
- **Deploy is GitHub Actions** against a self-hosted runner
  (`.github/workflows/deploy.yml`). The `etl_phase` input accepts:
  - `all` — full ETL from Phase 0 Download through MV refresh + warm
  - `incremental` — runs the P1-P6 framework ([ADR-0004](docs/adr/0004-etl-incremental-framework.md));
    optional `incremental_specs` input narrows which specs run
  - `sql` — indices/normalization/views only (no ETL)
  - `web` — code sync + systemd restart only (no ETL/SQL)
  - Numeric `N` — **1-based index** into the `phases` list in
    `etl/run_all.py` (Phase 0 Download counts as item 1) — **not** the
    "Fase N" label in the phase name.
- **`deploy.yml` one-off inputs are technical debt.** Inputs like
  `run_normalize_fix`, `rebuild_tmp_for_servidor`, `cleanup_orphan_empresa_cache`,
  and ad-hoc `refresh_mvs` targets were created to remediate specific bugs
  (typically a corresponding ADR). After they run **once** in production
  they become dead code. When adding a similar one-off step:
  1. Document the **trigger condition** and **expected removal criteria** in
     the related ADR (e.g. "remove after running once in prod and verifying
     X").
  2. Open a follow-up issue to remove it.
  3. Periodically (every few months) sweep `deploy.yml` and delete inputs
     whose ADRs are `Status: Superseded` / no longer applicable.
  See [`docs/deploy.md`](docs/deploy.md) section "One-off inputs hygiene" for
  the current debt list.
- **Do not commit** scratch outputs from local DB inspection: `db_*.txt`,
  `pg_*.txt`, `mv_status.txt`, `*_debug*.txt`, `*.log`, `q##_result.csv`.

## Agent-discovered quirks

These are gotchas the maintainer + previous agents have hit. Internalize
before editing the relevant area.

### Frontend / JS / MD3

- **MD3 custom-element upgrade is async.** Calling methods like `dialog.show()`
  on a `<md-dialog>` before its custom element upgraded triggers
  `dialog.show is undefined`. Gate behind
  `window.whenMD3Ready(cb)` from
  [`web/static/js/lib/md3-ready.js`](web/static/js/lib/md3-ready.js) for
  anything that depends on the upgraded API.
- **In-page anchor expansion is centralized.**
  [`web/static/js/lib/expand-context.js#expandReportContext`](web/static/js/lib/expand-context.js)
  is the single entry point for "open content via in-page anchor" (supports
  `.report-section`, `.finding-card`, `details.collapsible-details`). New
  collapsible components should register there.
- **`anchor-auto-expand` intercepts every `a[href^="#"]` click** with
  `preventDefault()` + `history.replaceState()`. Because `replaceState`
  doesn't fire a `hashchange` event, click-driven anchor navigation never
  triggers `hashchange` handlers. The component itself **does** listen on
  `hashchange` to handle browser back/forward across hash anchors. When
  adding components that should respond to anchor navigation, register them
  in `expandReportContext` rather than wiring your own `hashchange`
  listener — the central registry covers both click and browser-history
  paths.
- **`<details>` `toggle` event fires asynchronously** (queued task). To suppress
  handlers during programmatic expansion (e.g. print mode), use a flag and
  clear it with `setTimeout(0)` — never clear synchronously after setting
  `d.open = X`.
- **Collapsible sections** use the macro
  [`web/templates/partials/_collapsible.html`](web/templates/partials/_collapsible.html):
  `{% call collapsible(id, title, count=N, section_attrs={...}) %}…{% endcall %}`.
  Default is `open=True`. Reuse this — do not roll your own `<details>`.
- **Service Worker cache version** in
  [`web/static/sw.js`](web/static/sw.js):
  bump `FALLBACK_CACHE_VERSION` whenever you rename assets or change the SW
  pipeline. `ASSET_VERSION` in [`web/main.py`](web/main.py) is hash-based via
  `web/static/dist/manifest.json` — no manual bump needed in prod, but bump the
  string when you change JS/CSS so dev fallback (`?v=NNN`) invalidates browser
  caches.
- **Umami event names**: kebab-case, no page prefix. Valid: `secao-toggle`,
  `dialog-tab-change`, `modo-toggle`, `font-size-change`. Avoid `empresa-X`,
  `cidade-X`. See [`web/static/js/components/`](web/static/js/components/).
- **Dual-mode UI.** Frontend has two technicality levels. Use
  `dualLabel('cidadao', 'auditor')` in JS and `citizen-only` / `auditor-only`
  CSS classes in templates. Always provide both texts when you add a new
  label, stat or dialog content.

### Templates / Jinja

- **Cached numeric values come back as strings.** `cached_query()` returns
  dicts without type normalization; `web/warm_cache.py` serializes with
  `default=str` → numbers become strings. In templates, coerce with `|float` /
  `|int` before `round()` / `|tojson` (see
  [`web/templates/results/cidade.html`](web/templates/results/cidade.html)
  for the canonical coerce setblock pattern).
- **Jinja smoke-parse outside FastAPI.** For templates using custom filters
  (`short_brl`, `clean_text`, `municipio_slug`, `date_br`, etc.) in a test
  harness, catch `TemplateAssertionError` "No filter named X" and register
  `env.filters[name] = lambda x: x` dynamically before retrying. Custom
  filters are registered in [`web/main.py`](web/main.py) (~lines 185-188).

### SQL / Materialized Views

- **MV file structure**: `sql/12_views.sql` drops in reverse-dependency order
  at the top, recreates L1 → L2 → views. Adding a new MV requires updating
  both blocks **and** the `REFRESH MATERIALIZED VIEW CONCURRENTLY` footer.
  `REFRESH CONCURRENTLY` needs a UNIQUE INDEX on the MV.
- **Query timeouts in production.** `QueryDef.timeout_sec` is per-query in
  [`web/queries/registry.py`](web/queries/registry.py); default `30s`. Real
  values for the heavy queries:
  - **Q65** (fornecedor sancionado recebendo) — `timeout=90`; Nginx
    `proxy_read_timeout=60s` is the binding ceiling here — large cities
    (São Bento do Una, João Pessoa) hit nginx 504 before the app times out.
  - **Q77** (fracionamento de despesa) — `timeout=45`; tight per-query
    budget, can still trigger app-side timeout in big municipalities.
  - **Q61** (divergência empenhado vs pago) — `timeout=15`; rarely reaches
    nginx ceiling.
  When tuning, audit `sql/19_indices_queries.sql` indices first, then
  consider pre-computing into a MV instead of raising the timeout.

### Mermaid in `docs/`

Two parser quirks discovered in the Mermaid 10 build that GitHub uses:

1. **`;` in `sequenceDiagram` message labels** acts as a command terminator
   → `Expecting SOLID_ARROW … got NEWLINE`. Replace with " e " or another
   separator word.
2. **`&gt;` / `&lt;` HTML entities are NOT decoded** in `alt` / `else` / `opt`
   condition labels. Spell out with words: `fail diferente de zero` instead of
   `fail&gt;0`.

Also avoid `(`, `)`, `/`, `:`, `<br/>` inside `participant ID as Display Name`
aliases — they break the parser. Use plain ASCII names; put any rich text in
the message bodies instead.

**Local validation without rendering** (avoids puppeteer/Chromium):

```bash
mkdir mermaid-check && cd mermaid-check
npm init -y && npm install mermaid jsdom
# write parse.mjs that loops mermaid.parse(code) over fenced ```mermaid blocks
```

A working `parse.mjs` was used to validate
[`docs/architecture.md`](docs/architecture.md) and friends — all 16 blocks
parse clean as of PR #155. See those PRs for the exact pattern.

### ETL / Data quirks

- **`mv_empresa_pb` slug bug**: two variants of the same municipality coexist
  (correct `olho-dagua` + buggy `olho-d-agua`; same for `mae-d-agua` vs
  `mae-dagua`). Sitemap generates the buggy URLs → ~50 Googlebot 404s/day.
  Fix at source in [`etl/15_normalizar.py`](etl/15_normalizar.py).
- **`audit_report_identifiers.py`** with `--strict` runs offline (no Postgres),
  checks only CPF masking. Without `--strict` it validates CNPJs against
  local `empresa` + `estabelecimento` (requires ~58GB of RFB data loaded).

### Git / Workflow / Deploy

- **`gh` labels available**: only the 9 GitHub defaults (`bug`,
  `documentation`, `enhancement`, `good-first-issue`, `help wanted`, `invalid`,
  `question`, `duplicate`, `wontfix`). No custom labels yet — use
  `enhancement` for tech-debt / web / infra.
- **Self-hosted runner is single-slot** — deploys process one at a time.
  Long ETL deploys (8h+) block queued `web` deploys. Plan accordingly.
- **`deploy.yml` etl_phase** (see the "Conventions" section above for the
  full enumeration): `all` / `incremental` / `sql` / `web` / numeric `N`
  (1-based index into the `phases` list).
- **Multi-worktree `gh pr merge` warning.** When merging from a worktree that
  isn't `main`, `gh pr merge --squash --delete-branch` may print
  `fatal: 'main' is already used by worktree at ...`. **This is cosmetic** —
  the merge on GitHub still completes. Verify with `gh pr view <N> --json
  mergedAt`.
- **Recommended for significant PRs**: launch two parallel reviewers
  (Opus 4.7 + GPT 5.5). Convergence on a HIGH-severity finding validates it;
  divergence weakens confidence. Used routinely for PRs touching templates +
  SQL + cached data.

## PR checklist

Before opening or merging a PR, verify:

- [ ] **README** — does this change introduce a new feature, command, env var,
  or fundamental concept the README should mention?
- [ ] **`docs/`** — is the right area guide updated
  (`etl-guide` / `web-guide` / `queries-guide` / `mv-guide` / `cache` /
  `deploy` / `ops`)? Add or update Mermaid diagrams if the data flow or
  topology changed.
- [ ] **ADR** — is this a non-obvious architectural decision (affects multiple
  modules, has trade-offs, future contributors will ask "why?")? If yes, add
  `docs/adr/NNNN-titulo.md` following the template in
  [`docs/adr/README.md`](docs/adr/README.md). ADRs are **immutable** once
  `Accepted` — supersede with a new ADR rather than rewriting.
- [ ] **Glossary** — new domain term that needs an entry in
  [`docs/glossario.md`](docs/glossario.md)?
- [ ] **Tests** — `tests/incremental/` covers the framework; for one-shot
  changes, `python -m compileall etl -q` is the minimum baseline.
- [ ] **Audit scripts** — touched `relatorios/` or report identifiers? Run
  `python scripts/audit_report_identifiers.py --strict`.
- [ ] **Commit trailer** — every commit has
  `Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>`.

## Privacy & security

- This is a **private repo** at the moment (basic-auth hardening on
  `/_traffic/*` pending) — don't post repo URLs publicly. A formal
  `SECURITY.md` is pending; in the meantime report vulnerabilities via
  [GitHub Security Advisory](https://github.com/lucasdiniz/govbr-cruza-dados/security/advisories).
- Data is public BR open data. Reports may cite real CNPJs (public);
  CPFs must always be masked as `***.NNN.NNN-**`. LGPD considerations live in
  [`docs/privacidade.md`](docs/privacidade.md) and
  [`DATA-LICENSE.md`](DATA-LICENSE.md).
- Never commit secrets. `.env` is gitignored; `.env.example` is the template.
- Do not expose VM hostnames, Azure resource IDs, IPs or basic-auth credentials
  in code, commit messages, PR bodies or issues.

## Trailer (required)

Every commit message must end with:

```
Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

Tooling that produces deploy artefacts and review summaries depends on this
trailer being present.

---

When in doubt, prefer the most recent guidance you find in `docs/` and the
ADRs over older commits or this file. If an ADR contradicts this file, the
ADR wins.
