# TODO - govbr-cruza-dados

## Pendente

### Bugs de download/ETL (sessao 33 — diagnosticados na VM)

Cada fonte abaixo tem um problema específico que impede a carga correta no banco.

24. [x] **RFB: nomes de arquivos mudaram** — ZIPs baixados OK, mas arquivos dentro mudaram de `Empresas0.csv` para `K3241.K03200Y0.D60314.EMPRECSV`. ETL procura `*.csv` e não encontra. **Fix:** renomeação automática em `download_rfb()` (commit 64c497c).
25. [ ] **PGFN: nomes de arquivos mudaram** — ZIPs baixados/extraídos OK, mas CSVs dentro se chamam `arquivo_lai_PREV_*.csv`, `arquivo_lai_SIDA_*.csv`, `arquivo_lai_FGTS_*.csv`. ETL procura `pgfn_*.csv`. Fix: renomear ou adaptar glob no ETL (`07_pgfn.py` linha 15).
26. [ ] **Sancoes: download bloqueado (IP Azure)** — Portal da Transparência bloqueia IP da VM (403). Tor fallback também falha (exit=8). CSVs antigos existem (20260324) mas novos não baixam. Fix: (a) reconfigurar Tor na VM, ou (b) usar proxy alternativo, ou (c) aceitar dados de 2026-03 como recentes o suficiente.
27. [ ] **SIAPE: download parcial bloqueado** — Meses 2026-01 e 2026-02 OK (já existiam). Meses 2026-03+ bloqueados (mesmo problema Tor/403). ETL carrega os 2 meses disponíveis (617K cadastro, 508K remuneração). Fix: mesmo que Sanções — resolver bloqueio Tor.
28. [ ] **TSE: download não automatizado** — Não existe `download_tse()` em `00_download.py`. Dados precisam ser baixados manualmente de dadosabertos.tse.jus.br. Fix: implementar download automático ou documentar processo manual.
29. [ ] **Bolsa Família: download não automatizado** — Não existe `download_bolsa_familia()` em `00_download.py`. Dados precisam ser baixados manualmente do Portal da Transparência. Fix: implementar download automático.
30. [ ] **Renúncias: ETL não encontra CSVs** — Arquivos existem na VM (`2020_RenúnciasFiscais.csv` com acento) mas ETL procura `*_RenunciasFiscais.csv` (sem acento). Glob não bate por causa do acento no nome. Fix: adaptar glob ou renomear.
31. [x] **PNCP: numeric overflow** — DECIMAL(15,2) no schema era pequeno demais. Fix: DECIMAL(20,2) (commit 811c1ee).
32. [x] **BNDES: formato CSV mudou** — Staging com 34 colunas fixas, CSV novo tem menos. Fix: detecção dinâmica de colunas (commit 811c1ee).
33. [x] **Indices: ordem errada** — Fase 6 criava índices em colunas que só existem na fase 17. Fix: movidos para `15_normalizar.py` (commit 811c1ee).
34. [x] **SyntaxWarning \d** — Python 3.12+ rejeita `\d` em strings normais. Fix: `\\d` em 7 arquivos (commit 811c1ee).
35. [x] **Validação pós-download** — Pipeline não falhava quando dados faltavam. Fix: `validate_downloads()` em `00_download.py` (commit 811c1ee).

### Fontes OK na VM (referência)
- **CPGF**: 73 CSVs, 725K registros carregados ✓
- **Viagens**: 28 CSVs, 1.6M registros carregados ✓
- **Emendas**: 3 CSVs extraídos, carregado OK ✓
- **TCE-PB**: 36 CSVs, ~39M registros carregados ✓
- **Dados PB**: 1264 CSVs, ~5.8M registros carregados ✓
- **PNCP**: 246 contratações + 240 contratos JSONs, carregado (overflow corrigido) ✓
- **BNDES**: 2 CSVs, formato corrigido ✓

### ETL dados.pb.gov.br (12 datasets novos)
21. [ ] **Download todos os datasets** — baixar CSVs de 2020-2026 para os 12 datasets atualizados:
   - SIAF: `empenho_original` (até 2025/10), `pagamento`, `pagamento_anulacao`, `liquidacaodespesa`, `liquidacaodespesadescontos`, `empenho_anulacao`, `empenho_suplementacao`
   - CGE: `dotacao`, `liquidacao`
   - SIGA: `aditivos_contrato`, `aditivos_convenio`, `convenios`
   - Dimensão: `unidade_gestora_dadospb`
   - API: `https://dados.pb.gov.br/getcsv?nome=DATASET&exercicio=ANO&mes=MES`
   - Nota: `Diarias` case-sensitive (D maiúsculo). `contratos`/`resumo_folha` descartados (dados parados 2022-2023)
22. [ ] **ETL carga no banco** — criar tabelas, importar CSVs, normalizar, índices
23. [ ] **Queries de cruzamento** — novas queries usando dados estaduais granulares

### Deploy Azure
16. [x] **Deploy disparado** — self-hosted runner configurado via `setup-runner.yml`. Deploy com live logs.
17. [ ] **Issues #1-#4**: Pendentes execução no banco local. Plano detalhado em `.claude/plans/twinkling-puzzling-giraffe.md`.
18. [ ] **Formalizar Q58 por UF**: Criar variante estavel para recortes estaduais sem depender de ajuste de planner em sessao.
19. [ ] **Corrigir agregacao monetaria da Q17**: Deduplicar por base de CNPJ antes de somar PNCP/emendas/BNDES por holding.
20. [ ] **Endurecer relatorio do ciclo politico-financeiro**: Q56, Q57 e Q79 precisam saneamento para versao final.

## Handoff técnico sessão 33

### SSH na VM Azure
```bash
cp /c/Users/lucas/.ssh/azure_vm.txt /tmp/azure_vm_key && chmod 600 /tmp/azure_vm_key
ssh -i /tmp/azure_vm_key govbr@52.162.207.186
# dados em /home/govbr/data, projeto em /home/govbr/govbr-project
```

### Deploy: 3 workflows
- **Setup Self-Hosted Runner** (`setup-runner.yml`): instala runner na VM (1x)
- **Deploy to Azure VM** (`deploy.yml`): ETL completo com live logs, sem limite de tempo
- **Secrets necessários**: `VM_HOST`, `VM_SSH_KEY`, `DB_PASSWORD`, `ENV_FILE`

### Estado da VM (2026-04-05)
- Deploy run 23994305748 rodando (~8h+), ETL na fase de normalização/índices
- Tabelas carregadas: CPGF 725K, PNCP ~3K (overflow impediu carga completa), SIAPE 617K+508K, Sanções 22K+1.5K+4K, Viagens 1.6M+2.7M, TCE-PB ~39M, Dados PB ~5.8M
- Tabelas VAZIAS por bugs de download: RFB (0), PGFN (0), TSE (0), Bolsa Família (0), Renúncias (0)

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
- Diagnosticados 11 bugs no ETL da VM (5 corrigidos, 6 pendentes)
- Fixes: PNCP overflow, BNDES colunas, indices ordem, \d warnings, validação downloads, RFB renomeação
- Pendentes: PGFN nomes, Sancões/SIAPE bloqueio Tor, TSE/BF não automatizados, Renúncias acento

### 2026-04-05 (sessao 32)
- Relatorio `ciclo_politico_financeiro_exploratorio` produzido
- Caso forte validado em `Q56`: `FM PRODUCOES E EVENTOS LTDA`

### 2026-04-04 (sessao 31)
- Q58 otimizada, relatorio `empresas_relacionadas_concorrencia` PB e nacional

### 2026-04-04 (sessao 30)
- Bug PNCP 204 + urlopen SSL corrigidos. Benchmark VM: ~2.3 min/semana
- Commits: 451cae2, fed2301, 2697273, 09081dc, 83ab86c, 45a89f1, ccefdb9

### 2026-04-04 (sessao 29)
- Q100, deploy workflow, Tor fallback

### 2026-04-04 (sessao 28)
- 3 relatorios, Q99 fenix nacional

### 2026-04-03 (sessao 27)
- 7 queries pncp_item (Q92-Q98), Q55 fix
