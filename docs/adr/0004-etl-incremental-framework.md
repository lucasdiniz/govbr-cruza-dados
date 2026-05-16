# ADR-0004: Framework ETL incremental dedicado

## Status

Accepted

## Date

2025-03-05

## Context

Duas fontes — **TCE-PB** e **dados.pb.gov.br** — publicam dados em **janelas
mês/ano** e fazem **correções retroativas** (publicam um ajuste de 2023 em
2025, por exemplo). O ETL clássico do projeto (`TRUNCATE + rebuild` por fase)
tem dois problemas estruturais para estas fontes:

1. **Re-download massivo**: TCE-PB completo são ~20 GB. Baixar tudo todo mês,
   só para descobrir que 95% não mudou, é caro (banda, tempo, fair-use do
   portal-fonte).
2. **Histórico não preservado**: correção retroativa sobrescreve a versão
   anterior sem rastro. Auditoria forense fica impossível ("o que essa fonte
   reportava em janeiro?").

Tentativa anterior (PR #87, descartado) foi **adaptar o ETL clássico para
incremental no mesmo módulo**. Resultado:

- PRs gigantescos misturando lógica de full-load e incremental.
- Regressões em cargas full quando se mexia em incremental, e vice-versa.
- Auditoria parcial — alguns sinks tinham log, outros não.
- Sem garantia de não-corromper-dados (sem testes, sem role-segregation).

## Decision

**Subsistema dedicado em [`etl/incremental/`](../../etl/incremental/)** com
contrato bem definido e **6 princípios não-negociáveis** (P1–P6), documentados
em [`etl/incremental/README.md`](../../etl/incremental/README.md):

### Princípios (precedência em caso de conflito: P1 > P2 > … > P6)

1. **P1 — NÃO CORROMPER DADOS EXISTENTES.** Sobrepõe todos os outros. Se uma
   operação tem qualquer risco de corromper o que já está lá, ela não roda.
2. **P2 — NÃO-DESTRUTIVO.** Zero `TRUNCATE`/`DROP`/`DELETE` em tabelas
   target. Inserts e updates idempotentes apenas.
3. **P3 — AUDITÁVEL.** Rastro completo em `etl_run_log`, `etl_phase_log`,
   `etl_download_log`, `etl_rejected_rows` (DLQ).
4. **P4 — ERROR RESILIENT.** Recuperável de qualquer crash. Watermark
   persistido + `bucket_token` UUIDv5 determinístico (mesma janela → mesmo
   token → idempotência).
5. **P5 — FAST.** Download condicional: `HEAD` probe + `If-None-Match` +
   `If-Modified-Since`. Se o servidor diz 304, pula tudo.
6. **P6 — ZERO TOLERANCE.** Watermark **nunca** avança em failure. DLQ
   persiste mesmo em `ROLLBACK` da `main_conn` (escreve com conexão separada
   e commit independente).

### Role-segregation (defense-in-depth)

- **`etl_incremental`** — LOGIN NOINHERIT, GRANT SELECT/INSERT/UPDATE apenas.
  **Sem DELETE/TRUNCATE/DROP** no nível do banco. O loader corre como esse
  role.
- **`etl_admin`** — operações privilegiadas via `SECURITY DEFINER`
  functions, com `search_path` lockado e fence de identidade
  (`current_user`).
- Triggers de proteção em tabelas críticas (impedem update destrutivo de
  watermark).
- **AST scan** em CI verifica que código de loader não usa `TRUNCATE`/`DROP`
  literal.

### Cobertura atual

- **4 specs TCE-PB** + **16 specs dados-PB** = 20 specs em produção.
- ~3.3 kLOC, 23 arquivos Python, 9 SQL migrations
  (`sql/22_*.sql` a `sql/29_*.sql` + `32`, `34`, `35`).
- Único subsistema do repositório com suite de testes
  (`tests/incremental/`, 5 arquivos cobrindo invariants P1–P6 +
  defesas SECDEF + role).

## Consequences

### Positive

- **Dados históricos preservados** — toda versão de uma correção retroativa
  fica registrada via `bucket_token` + timestamp.
- **Recuperação automática** de crash: rerun pega de onde parou (watermark).
- **Auditoria forense completa** — `etl_run_log`/`etl_phase_log`/
  `etl_download_log`/`etl_rejected_rows` respondem "o que aconteceu, quando,
  com qual resultado".
- **Segurança em 4 camadas**: DB role + SECDEF function + triggers + AST
  scan. Mesmo um bug no loader não consegue destruir target.
- **Download eficiente** — em ciclos sem mudança, fonte é "pingada" e
  pipeline volta em segundos.
- **Único subsistema testado** — base para expandir testes ao resto do
  projeto.

### Negative / Trade-offs

- **Complexidade alta** — ~3.3 kLOC, 9 migrations, 23 arquivos Python.
  Curva de aprendizado real para contributors.
- **Gerador DDL não-automatizado** — adicionar spec exige sincronizar 3
  artefatos paralelos manualmente:
  - `LoaderSpec` Python (colunas tipadas)
  - DDL SQL da tabela target
  - `UNIQUE INDEX` para idempotência
  Drift entre eles é detectado apenas em runtime.
- **Auto-discovery manual** — `runner.py:_load_all_specs()` exige
  registro explícito (lista hardcoded). Esquecer = spec não roda.
- Custos operacionais (Postgres roles, GRANTs) precisam ser replicados em
  qualquer ambiente novo.
- Dois sistemas paralelos (ETL clássico + incremental) — contributor precisa
  saber em qual escrever.

### Mitigations

- [`etl/incremental/README.md`](../../etl/incremental/README.md) (8.3 KB)
  documenta P1–P6, fluxo end-to-end, comandos operacionais.
- `docs/etl-incremental-guide.md` (a ser criado) destrincha os 8 passos para
  adicionar uma nova spec, com checklist.
- Tests em `tests/incremental/` verificam invariants — quebrar um princípio
  falha CI.
- Roadmap inclui gerador DDL automático a partir de `LoaderSpec` (issue em
  aberto).

## Related

- Code:
  - [`etl/incremental/`](../../etl/incremental/) (loader, runner, specs)
  - [`etl/incremental/README.md`](../../etl/incremental/README.md) (P1–P6)
  - SQL: `sql/22_etl_watermark.sql` … `sql/29_etl_download_log.sql`,
    `sql/27_etl_admin_security_definer.sql`
  - [`tests/incremental/`](../../tests/incremental/)
- Other ADRs: [ADR-0001](0001-no-pandas.md) (mesma filosofia streaming + COPY).
- Docs: `docs/etl-incremental-guide.md` (a ser criado).
- External:
  - [PostgreSQL `SECURITY DEFINER` best practices](https://www.postgresql.org/docs/16/sql-createfunction.html#SQL-CREATEFUNCTION-SECURITY)
  - RFC 4122 UUIDv5 (namespace-based determinism)
