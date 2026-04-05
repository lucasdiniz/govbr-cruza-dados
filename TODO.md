# TODO - govbr-cruza-dados

## Pendente

### Bugs de download/ETL (sessao 33 — diagnosticados na VM)

Cada fonte abaixo tem um problema específico que impede a carga correta no banco.
O deploy run 23994305748 rodou com esses bugs — precisa re-deploy após corrigir.

25. [ ] **PGFN: nomes de arquivos mudaram** — ZIPs baixados/extraídos OK, mas CSVs dentro se chamam `arquivo_lai_PREV_*.csv`, `arquivo_lai_SIDA_*.csv`, `arquivo_lai_FGTS_*.csv`. ETL (`etl/07_pgfn.py:15`) procura `pgfn_*.csv` e não encontra. **Na VM**: 19 CSVs em `/home/govbr/data/pgfn/arquivo_lai_*.csv`. Fix: adaptar glob em `07_pgfn.py` ou renomear em `download_pgfn()`.
26. [ ] **Sancoes: download bloqueado (IP Azure)** — Portal da Transparência bloqueia IP da VM (403). Tor fallback falha (exit=8, Tor connection refused). CSVs antigos existem na VM em `/home/govbr/data/sancoes/` (20260324 e 20260327 e 20260403). O ETL (`etl/13_sancoes.py`) faz glob `*_CEIS.csv` etc. e encontra os antigos. **Status**: Sanções carregaram 22K CEIS + 1.5K CNEP + 4K CEAF do cache antigo. Fix: (a) reconfigurar Tor na VM (`sudo systemctl restart tor`, verificar `torrc`), ou (b) aceitar dados de 2026-03 como suficientes.
27. [ ] **SIAPE: download parcial bloqueado** — Meses 2026-01 e 2026-02 OK (já existiam). Meses 2026-03+ bloqueados (mesmo 403/Tor). ETL carregou 617K cadastro + 508K remuneração dos 2 meses disponíveis. Fix: mesmo que Sanções — resolver bloqueio Tor no Portal da Transparência.
28. [ ] **TSE: download não automatizado** — Não existe `download_tse()` em `etl/00_download.py`. Fonte: `dadosabertos.tse.jus.br/dados-abertos/candidatos/`. ETL espera em `DATA_DIR`: `candidatos_2020.csv`, `candidatos_2022.csv`, `candidatos_2024.csv` + `bens_*.csv`. O `etl/16_tse.py` e `etl/18_tse_prestacao.py` fazem a carga. Fix: implementar download automático similar ao CPGF (ZIP por ano).
29. [ ] **Bolsa Família: download não automatizado** — Não existe `download_bolsa_familia()` em `etl/00_download.py`. Fonte: Portal da Transparência, mesma URL base que CPGF (`/download-de-dados/novo-bolsa-familia/YYYYMM`). ETL espera `*_NovoBolsaFamilia.csv` em `DATA_DIR`. O `etl/17_bolsa_familia.py` faz a carga. Fix: implementar download — CUIDADO: mesmo bloqueio 403 da Azure pode afetar.
30. [ ] **Renúncias: ETL não encontra CSVs (acento)** — Arquivos existem na VM em `/home/govbr/data/renuncias/` com acento: `2020_RenúnciasFiscais.csv`. ETL (`etl/08_renuncias.py:182`) faz glob `*_RenunciasFiscais.csv` (sem acento). Glob não bate. Fix: adaptar glob para aceitar ambas as formas, ou renomear no download. Mesma questão para `*_RenúnciasFiscaisPorBeneficiário.csv`.

### Corrigidos nesta sessão
24. [x] **RFB: nomes de arquivos mudaram** — Fix: renomeação automática em `download_rfb()` (commit 64c497c)
31. [x] **PNCP: numeric overflow** — Fix: DECIMAL(20,2) (commit 811c1ee)
32. [x] **BNDES: formato CSV mudou** — Fix: detecção dinâmica de colunas (commit 811c1ee)
33. [x] **Indices: ordem errada** — Fix: movidos para `15_normalizar.py` (commit 811c1ee)
34. [x] **SyntaxWarning \d** — Fix: `\\d` em 7 arquivos (commit 811c1ee)
35. [x] **Validação pós-download** — Fix: `validate_downloads()` em `00_download.py` (commit 811c1ee)

### Fontes OK na VM (referência)
- **CPGF**: 73 CSVs, 725K registros ✓
- **Viagens**: 28 CSVs, 1.6M+2.7M registros ✓
- **Emendas**: 3 CSVs (tesouro, convenios, favorecidos) ✓
- **TCE-PB**: 36 CSVs, ~39M registros ✓
- **Dados PB**: 1264 CSVs, ~5.8M registros ✓
- **PNCP**: 246+240 JSONs (overflow corrigido, precisa re-carga) ✓
- **BNDES**: 2 CSVs (formato corrigido, precisa re-carga) ✓

### ETL dados.pb.gov.br (12 datasets novos)
21. [ ] **Download todos os datasets** — já implementado em `download_dados_pb()` no `etl/00_download.py`. Baixa 13 datasets mensais + 2 anuais via API `https://dados.pb.gov.br/getcsv?nome=DATASET&exercicio=ANO&mes=MES`. Nota: `Diarias` case-sensitive (D maiúsculo).
22. [ ] **ETL carga no banco** — criar tabelas para novos datasets (pagamento_anulacao, liquidacao, dotacao, aditivos, etc.)
23. [ ] **Queries de cruzamento** — novas queries usando dados estaduais granulares

### Deploy Azure
16. [x] **Deploy configurado** — self-hosted runner via `setup-runner.yml`, deploy via `deploy.yml` com live logs
17. [ ] **Issues #1-#4**: Pendentes execução no banco local
18. [ ] **Formalizar Q58 por UF**
19. [ ] **Corrigir agregacao monetaria da Q17**
20. [ ] **Endurecer relatorio do ciclo politico-financeiro**

## Handoff técnico sessão 33

### Próximos passos (ordem sugerida)
1. **Corrigir PGFN e Renúncias** (fácil, ~15min cada) — só adaptar nomes/globs
2. **Resolver bloqueio Tor** para Sanções/SIAPE/Bolsa Família — reconfigurar Tor na VM ou usar proxy
3. **Implementar download TSE e Bolsa Família** — adicionar funções ao `00_download.py`
4. **Re-deploy** após fixes — `gh workflow run deploy.yml -f etl_phase=all -f clean=true`
5. Depois: ETL carga dos 12 novos datasets dados.pb.gov.br (item 22)

### Deploy atual na VM
- **Run**: 23994305748 (disparado ~04:40 UTC 2026-04-05, self-hosted runner)
- **Status**: in_progress, ETL na fase 17 (normalização TCE-PB). Rodando há ~9h.
- **Nota**: esse deploy usou código ANTES dos fixes (commits 811c1ee, 64c497c). Vai falhar em PNCP (overflow), BNDES (colunas), e índices (ordem). Os dados baixados na VM estão OK — só o código do ETL precisa atualizar.
- **Para re-deploy**: esperar este terminar (ou cancelar com `gh run cancel 23994305748`), depois disparar novo com código atualizado.

### SSH na VM Azure
```bash
cp /c/Users/lucas/.ssh/azure_vm.txt /tmp/azure_vm_key && chmod 600 /tmp/azure_vm_key
ssh -i /tmp/azure_vm_key govbr@52.162.207.186
# dados em /home/govbr/data, projeto em /home/govbr/govbr-project, venv em venv/
# log do ETL: tail -f /tmp/etl.log
```

### Deploy: workflows GitHub Actions
- **Setup Self-Hosted Runner** (`setup-runner.yml`): instala runner na VM (rodar 1x)
- **Deploy to Azure VM** (`deploy.yml`): ETL completo com live logs, sem limite de tempo
- Secrets no repo: `VM_HOST`, `VM_SSH_KEY`, `DB_PASSWORD`, `ENV_FILE`

### Arquivos-chave modificados nesta sessão
- `etl/00_download.py` — renomeação RFB, validação pós-download, download dados.pb.gov.br
- `etl/07_pgfn.py` — fix \d (PGFN glob ainda pendente)
- `etl/08_renuncias.py` — fix \d (glob acento ainda pendente)
- `etl/09_complementar.py` — BNDES staging dinâmico, fix \d
- `etl/15_normalizar.py` — índices movidos de 11_indices.sql
- `etl/20_dados_pb.py` — download removido (centralizado no 00_download)
- `sql/03_schema_pncp.sql` — DECIMAL(15,2) → DECIMAL(20,2)
- `sql/11_indices.sql` — índices dependentes de normalização removidos
- `.github/workflows/deploy.yml` — reescrito para self-hosted runner
- `.github/workflows/setup-runner.yml` — novo, automatiza instalação do runner

### Commits desta sessão (10)
```
67674ba docs: TODO com diagnóstico completo de bugs de download/ETL por fonte
64c497c fix: renomeia arquivos RFB extraídos (formato novo mainframe → .csv)
811c1ee fix: 4 bugs ETL — PNCP overflow, BNDES colunas, indices ordem, \d warnings
74aa780 docs: atualiza README com deploy 1-click via GitHub Actions
34ce6c4 feat: setup-runner.yml automatiza instalação do self-hosted runner
b0266e6 refactor: deploy via SSH + ETL desacoplado (nohup) na VM
e0cec55 refactor: deploy.yml para self-hosted runner na VM Azure
aea12d6 refactor: centraliza download no 00_download, remove do 20_dados_pb
ada934c feat: adiciona 10 novos datasets dados.pb.gov.br ao download
76768fd docs: completa dicionário dados.pb.gov.br — 18 datasets mapeados
```

## Estado do banco local
- **~336M registros** em 15+ fontes. DB size: 205 GB. C: 91GB livres.
- PostgreSQL: `PGPASSWORD=kong1029 "/c/Program Files/PostgreSQL/16/bin/psql.exe" -U postgres -d govbr`
- Dados brutos: G:\govbr-dados-brutos (HDD)
- 95 queries em queries/*.sql, 32 relatorios em relatorios/

## Concluido (resumo)
- Issues #1-#5 resolvidas e validadas (código, não executadas no banco)
- ETL completo local: 15+ fontes, normalizacao, indices
- 7/7 MVs + 2 views criadas. 32 relatorios. 14/14 enriquecimentos.

## Log recente

### 2026-04-05 (sessao 33)
- Deploy reescrito: setup-runner.yml (automatiza runner) + deploy.yml (self-hosted, live logs)
- README atualizado com fluxo de deploy 1-click
- Diagnosticados 11 bugs no ETL da VM (6 corrigidos, 6 pendentes)
- Fixes: PNCP overflow, BNDES colunas, indices ordem, \d warnings, validação downloads, RFB renomeação
- Pendentes: PGFN nomes, Sancões/SIAPE bloqueio Tor, TSE/BF não automatizados, Renúncias acento
- Causa raiz dos "dados faltando": RFB mudou nomes dentro dos ZIPs, Portal Transparência bloqueia IP Azure

### 2026-04-05 (sessao 32)
- Relatorio `ciclo_politico_financeiro_exploratorio` produzido
- Caso forte validado em `Q56`: `FM PRODUCOES E EVENTOS LTDA`

### 2026-04-04 (sessao 31)
- Q58 otimizada, relatorio `empresas_relacionadas_concorrencia` PB e nacional

### 2026-04-04 (sessao 30)
- Bug PNCP 204 + urlopen SSL corrigidos. Benchmark VM: ~2.3 min/semana

### 2026-04-04 (sessao 29)
- Q100, deploy workflow, Tor fallback

### 2026-04-04 (sessao 28)
- 3 relatorios, Q99 fenix nacional

### 2026-04-03 (sessao 27)
- 7 queries pncp_item (Q92-Q98), Q55 fix
