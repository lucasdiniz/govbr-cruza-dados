# TODO - govbr-cruza-dados

## Pendente

### Bugs de download/ETL (sessao 33 — diagnosticados na VM)

Cada fonte abaixo tem um problema específico que impede a carga correta no banco.
O deploy run 23994305748 rodou com esses bugs — precisa re-deploy após corrigir.

25. [x] **PGFN: nomes de arquivos mudaram** — Fix: glob adaptado para `pgfn/arquivo_lai_*.csv` com fallback `pgfn_*.csv` (sessão 34)
26. [x] **Sancoes: download bloqueado (IP Azure)** — Aceito dados de cache 2026-03 (22K CEIS + 1.5K CNEP + 4K CEAF). Suficiente para cruzamentos.
27. [x] **SIAPE: download parcial bloqueado** — Aceito 2 meses (jan-fev 2026): 617K cadastro + 508K remuneração. Suficiente para cruzamentos.
28. [x] **TSE: download automatizado** — `download_tse()` implementado em `etl/00_download.py`. Baixa ZIPs oficiais do CDN do TSE para 2020, 2022 e 2024 (`consulta_cand`, `bem_candidato` e `prestacao_de_contas_eleitorais_candidatos` para 2022/2024), salvando com os nomes que `etl/16_tse.py` e `etl/18_tse_prestacao.py` esperam.
29. [x] **Bolsa Família: download automatizado** — `download_bolsa_familia()` implementado em `etl/00_download.py`. Baixa `/download-de-dados/novo-bolsa-familia/YYYYMM`, extrai o ZIP e deixa `*_NovoBolsaFamilia.csv` prontos para `etl/17_bolsa_familia.py`. Observação: o mesmo bloqueio 403 da Azure ainda pode afetar meses novos.
30. [x] **Renúncias: ETL não encontra CSVs (acento)** — Fix: `_glob_renuncias()` busca com/sem acento em `renuncias/` e DATA_DIR raiz (sessão 34)

### Corrigidos nesta sessão
24. [x] **RFB: nomes de arquivos mudaram** — Fix: renomeação automática em `download_rfb()` (commit 64c497c)
31. [x] **PNCP: numeric overflow** — Fix: DECIMAL(20,2) (commit 811c1ee)
32. [x] **BNDES: formato CSV mudou** — Fix: detecção dinâmica de colunas (commit 811c1ee)
33. [x] **Indices: ordem errada** — Fix: movidos para `15_normalizar.py` (commit 811c1ee)
34. [x] **SyntaxWarning \d** — Fix: `\\d` em 7 arquivos (commit 811c1ee)
35. [x] **Validação pós-download** — `validate_downloads()` alinhada ao formato real dos loaders: PGFN (`arquivo_lai_*.csv`), Sanções (`*_CEIS.csv`, `*_CNEP.csv`, `*_Expulsoes.csv`, `*_Acordos.csv`), dados.pb com underscore, TSE (ZIP ou extraído) e Bolsa Família (`*_NovoBolsaFamilia.csv`)
36. [x] **Workflow deploy: smoke test e Tor** — `deploy.yml` agora reinicia `tor` antes do ETL e testa também TSE CDN e Novo Bolsa Família no smoke test
37. [x] **Emendas: loader aceita layout novo/antigo** — `etl/05_emendas.py` agora busca tanto em `DATA_DIR/emendas/` quanto na raiz (`etl: fix emendas paths and optional indices`, commit `b81bf92`)
38. [x] **Índices: tolerar tabelas ausentes** — `etl/10_indices.py` agora pula índices cujas tabelas ainda não existem, em vez de abortar a fase inteira (commit `b81bf92`)
39. [x] **PNCP: identificadores e processo maiores** — `sql/03_schema_pncp.sql` ampliado para evitar `value too long for type character varying(50)` em `pncp_contrato` (commit `ced083b`)
40. [x] **BNDES: parser tolerante para CSV malformado** — `etl/09_complementar.py` trocado de `COPY` bruto para parser CSV em Python + staging TSV, pulando linhas quebradas (commit `ced083b`)
41. [x] **PGFN: loader por header real** — `etl/07_pgfn.py` agora detecta layout pelo header e mapeia colunas dinamicamente, evitando `extra data after last expected column` (commit `ced083b`)
42. [x] **dados.pb: não exigir mês corrente** — `download_dados_pb()` agora para no último mês completo, reduzindo falsos `[erro]` de publicação parcial (commit `ced083b`)

### Fontes OK na VM (referência)
- **CPGF**: 73 CSVs, 725K registros ✓
- **Viagens**: 28 CSVs, 1.6M+2.7M registros ✓
- **Emendas**: 3 CSVs (tesouro, convenios, favorecidos) ✓
- **TCE-PB**: 36 CSVs, ~39M registros ✓
- **Dados PB**: 1264 CSVs, ~5.8M registros ✓
- **PNCP**: 246+240 JSONs (overflow corrigido, precisa re-carga) ✓
- **BNDES**: 2 CSVs (formato corrigido, precisa re-carga) ✓

### ETL dados.pb.gov.br (12 datasets novos)
21. [x] **Download todos os datasets** — Implementado em `download_dados_pb()`. Deploy atual rodando na VM.
22. [x] **ETL carga no banco** — 16 tabelas pb_* carregadas localmente (~14.4M registros). Fix: linhas curtas (quebra de linha em campos texto) agora ignoradas em `_staging_load_from_data`.
23. [x] **Queries de cruzamento (Q101-Q111)** — novos cruzamentos com datasets pb_* ampliados:
    - Q101: Aditivos abusivos — contratos cujo total aditivo supera % do valor original
    - Q102: Fornecedor sancionado recebendo do estado — pb_empenho × ceis/cnep
    - Q103: Fornecedor com dívida ativa PGFN recebendo do estado
    - Q104: Duplo pagamento — mesma NF em duas liquidações diferentes
    - Q105: Ciclo empenho→anulação→re-empenho no mesmo credor
    - Q106: Diárias estaduais × viagens federais — mesmo período/destino
    - Q107: Fornecedor PB que doa para campanha TSE (ciclo empenho→doação)
    - Q108: Conveniada com dívida ativa federal
    - Q109: Servidor estadual sócio de fornecedor do estado
    - Q110: Dotação vs execução — empenho/pagamento acima da dotação
    - Q111: View mv_fornecedor_pb_perfil — visão 360° do fornecedor

### Deploy Azure
16. [x] **Deploy configurado** — self-hosted runner via `setup-runner.yml`, deploy via `deploy.yml` com live logs
17. [ ] **Issues #1-#4**: Pendentes execução no banco local
18. [ ] **Formalizar Q58 por UF**
19. [ ] **Corrigir agregacao monetaria da Q17**
20. [ ] **Endurecer relatorio do ciclo politico-financeiro**
21. [ ] **Revisar/arquivar relatorios invalidos** conforme classificacao abaixo
22. [ ] **Padronizar citacao `razao social + CNPJ` nos relatorios ativos**
23. [ ] **Corrigir relatorios com CNPJ nao encontrado na base RFB local**

### Catalogo de relatorios - revisao de validade (sessao 36)

#### Relatorios validos no estado atual
- `relatorio_falsos_positivos_pb.md`
- `relatorio_pejotizacao_campina_grande.md`
- `relatorio_contratos_fim_de_semana_pb.md`
- `relatorio_capital_minimo_contratos_pb.md`
- `relatorio_fracionamento_despesa_pb.md`
- `relatorio_empresa_fenix_pb.md`
- `relatorio_sobrepreco_pncp_item.md`
- `relatorio_sancionados_recebendo_pb.md`
- `relatorio_tratoraco_codevasf_pb.md`
- `relatorio_pejotizacao_saude_municipal_pb.md`
- `relatorio_conflito_cartao_corporativo.md`
- `relatorio_empresas_inativas_fornecedoras_pb.md`
- `relatorio_empresas_relacionadas_concorrencia_pb.md`
- `relatorio_empresas_relacionadas_concorrencia_nacional.md`
- `relatorio_aditivos_abusivos_estado_pb.md`
- `relatorio_fornecedores_irregulares_estado_pb.md`

#### Relatorios invalidos ou nao publicaveis no estado atual
- `relatorio_servidor_bolsa_familia_pb.md` - depende fortemente de `Q74` (CPF parcial + nome), risco alto de falso positivo
- `relatorio_laranjas_bolsa_familia_pb.md` - mesma fragilidade de `Q39/Q74`, alem de CNPJs nao encontrados
- `relatorio_risco_municipal_pb.md` - score usa indicador quebrado (`sem licitacao` zerado para todos)
- `relatorio_servidor_risco_pb.md` - herda ruido forte de `Q74` e score composto
- `relatorio_risk_score_pb.md` - herda problemas de score e mistura sinais ainda nao endurecidos
- `relatorio_servidor_socio_fornecedor_pb.md` - superado pela versao corrigida de `Q59` em `relatorio_pejotizacao_saude_municipal_pb.md`
- `relatorio_servidor_estadual_socio_fornecedor_pb.md` - depende de match nominal fraco (`Q109`)
- `relatorio_ciclo_politico_financeiro_exploratorio.md` - exploratorio, nao publicavel como peca final
- `relatorio_rede_societaria_pb.md` - bom como mapa analitico, fraco como relatorio investigativo conclusivo
- `relatorio_itens_fracassados_pncp.md` - texto ainda forte demais para a prova atual e com mistura de hipoteses nao estabilizadas

### Auditoria de identificadores em relatorios (sessao 36)

Script criado:
- `scripts/audit_report_identifiers.py`

Objetivo:
- extrair `CNPJ` e `CPF` citados em `relatorios/*.md`
- validar `CNPJ -> razao social` contra a base local da RFB (`empresa` + `estabelecimento`)
- classificar como `match`, `suspeito`, `sem_nome_no_relatorio` ou `nao_encontrado_rfb`

Achados principais:
- a maioria dos CNPJs citados nominalmente bate com a razao social na base local
- o problema mais comum nao e CNPJ trocado, e sim **CNPJ citado sem nome oficial ao lado**
- relatorios devem preferir sempre `razao social oficial + CNPJ`

Casos que exigem correcao manual imediata:
- `relatorio_laranjas_bolsa_familia_pb.md`
  - `00.803.795/0001-00` (`ETHIC REPRESENTACOES COMERCIAIS LTDA`) -> `nao_encontrado_rfb`
  - `15.739.000/0001-76` (`SUCATAS HOSPITALARES COMERCIO E RECICLAGEM LTDA`) -> `nao_encontrado_rfb`
  - `50.839.309/0001-08` (`OLHO DAGUA DO CAPIM SPE LTDA`) -> `nao_encontrado_rfb`
  - `45.474.398/0001-83` -> `nao_encontrado_rfb`
- `relatorio_falsos_positivos_pb.md`
  - `09.261.843/0001-16` aparece como `suspeito` por uso de sigla (`PaqTcPB`) em vez da razao social completa `FUNDACAO PARQUE TECNOLOGICO DA PARAIBA`

Observacoes:
- `CPF` completo raramente aparece nos relatorios; validacao automatica de CPF ainda e limitada
- varios relatorios saem como `sem_nome_no_relatorio` porque so citam o numero do CNPJ; isso reduz auditabilidade, mas nao significa mismatch

## Handoff técnico sessão 34

### O que foi feito
1. **ETL dados.pb completo localmente** — 16 tabelas pb_* com ~14.4M registros carregadas. Fix: linhas curtas em `_staging_load_from_data` (commit 48d0984).
2. **Q101-Q111 escritas** em `queries/fraude_dados_pb_novos.sql` (commit 510c2cb).
3. **Normalização rodando** — `python -m etl.15_normalizar` em execução no banco local. Estava bloqueada por query antiga de 14h no `socio`, cancelada manualmente. Agora está no UPDATE do pb_pagamento.

### Validação das queries (banco local)
| Query | Status | Observação |
|-------|--------|------------|
| Q101 aditivos | OK | Resultados fortes: UNIPLACAS R$10 → R$1.5B aditivos |
| Q102 sancionado CEIS | OK | Reescrita para `pb_empenho`; 52 grupos encontrados |
| Q103 PGFN | OK | Reescrita para `pb_empenho`; 2757 grupos encontrados |
| Q104 NF dupla | OK | Encontra NFs duplicadas. Filtro `!~ '^0+$'` adicionado para remover NF zerada |
| Q105 ciclo anulação | OK | Funciona, PBPREV domina (esperado) |
| Q106 diárias × viagens | OK | Detecta sobreposição por nome. Funciona! |
| Q107 doador TSE | OK | Reescrita para `pb_empenho`; 1 caso encontrado |
| Q108 convênio PGFN | OK | Bayeux, Campina Grande com dívidas bilionárias |
| Q109 servidor sócio | OK | Query reescrita sem `LATERAL`; 577 grupos encontrados |
| Q110 suplementações | OK | Reformulada: concentração de suplementações por credor |
| Q111 view perfil | OK | Alias `tem_cnep` corrigido; MV criada e `REFRESH` executado (18.306 linhas) |

### Descoberta crítica: pb_pagamento tem apenas 1 CNPJ PJ
- `pb_pagamento` tem 3.9M registros mas **apenas 1 CNPJ de PJ** (02221962 = secretarias do governo). Todo o resto são PF (CPF).
- **pb_empenho tem 18K CNPJs PJ distintos** — é a tabela correta para cruzamentos PJ.
- **Q102, Q103, Q107 foram reescritas** para usar `pb_empenho` em vez de `pb_pagamento` no match por CNPJ.
- pb_pagamento ainda é útil para matches PF (CPF completo, 11 dígitos).

### Correções de schema descobertas
- **PGFN `cpf_cnpj`** é formatado com pontos/traço (ex: `08.064.568/0001-88`). `cpf_cnpj_norm` é 6 dígitos (CPF parcial), NÃO cnpj_basico. Precisa `REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g')` para extrair dígitos. CTE `pgfn_pj` já implementada em Q103/Q108.
- **CEIS/CNEP `cpf_cnpj_norm`** é CNPJ completo 14 dígitos. Match via `LEFT(cpf_cnpj_norm, 8)`. `tipo_pessoa='J'` para filtrar PJ.

### Próximos passos (ordem sugerida)
1. ~~**Produzir relatórios dos novos datasets PB**~~ — FEITO (sessão 37): Q101 `relatorio_aditivos_abusivos_estado_pb.md`, Q102/Q103/Q111 `relatorio_fornecedores_irregulares_estado_pb.md`, Q104 `relatorio_duplo_pagamento_nf_pb.md`, Q105 `relatorio_ciclo_anulacao_reempenho_pb.md`, Q106 `relatorio_diarias_sobrepostas_pb.md`, Q108 `relatorio_convenios_devedores_pgfn_pb.md`, Q110 `relatorio_suplementacoes_concentradas_pb.md`. Q107 tem apenas 1 resultado (fraco)
2. **Formalizar a exportação/runner** para `queries/fraude_dados_pb_novos.sql` no fluxo padrão de `etl.run_queries`
3. **Re-deploy VM com `main` atual** — validar se os fixes `b81bf92` e `ced083b` eliminam os erros de Emendas/PNCP/BNDES/PGFN/Índices
4. Bugs infra pendentes: Sanções/SIAPE bloqueio Tor (#26, #27)

### Deploy VM
- **Run problemático documentado**: 24002741785 — headSha antigo `296981b`
- **Código atualizado no `origin/main`**: `ced083b`
- **Fixes já publicados após o run antigo**:
  - `402220b` validação final das Q102-Q111
  - `b81bf92` paths de emendas + índices tolerantes
  - `ced083b` hardening de PNCP/BNDES/PGFN/validação

### SSH na VM Azure
```bash
cp /c/Users/lucas/.ssh/azure_vm.txt /tmp/azure_vm_key && chmod 600 /tmp/azure_vm_key
ssh -i /tmp/azure_vm_key govbr@52.162.207.186
```

### Deploy: workflows GitHub Actions
- **Setup Self-Hosted Runner** (`setup-runner.yml`): instala runner na VM (rodar 1x)
- **Deploy to Azure VM** (`deploy.yml`): ETL completo com live logs, sem limite de tempo
- Secrets no repo: `VM_HOST`, `VM_SSH_KEY`, `DB_PASSWORD`, `ENV_FILE`
- Secret opcional recomendado para reparo do runner: `RUNNER_ADMIN_TOKEN`

### Commits sessão 34
```
48d0984 fix: skip short rows in dados_pb ETL (multiline text fields)
510c2cb feat: Q101-Q111 queries para novos datasets dados.pb
```

## Estado do banco local
- **~350M registros** em 16+ fontes (inclui 14.4M novos dados.pb). DB size: ~210 GB.
- PostgreSQL: `PGPASSWORD=kong1029 "/c/Program Files/PostgreSQL/16/bin/psql.exe" -U postgres -d govbr`
- Dados brutos: G:\govbr-dados-brutos (HDD)
- 106 queries em queries/*.sql, 32 relatorios em relatorios/
- **Normalização concluída para o bloco pb_*** — colunas `cnpj_basico`/`nome_upper` já disponíveis nas tabelas usadas por Q102-Q111

## Concluido (resumo)
- Issues #1-#5 resolvidas e validadas (código, não executadas no banco)
- ETL completo local: 16+ fontes, normalizacao, indices
- 7/7 MVs + 2 views criadas. 32 relatorios. 14/14 enriquecimentos.

## Log recente

### 2026-04-05 (sessao 34)
- ETL dados.pb: 16 tabelas pb_* carregadas localmente (~14.4M registros)
- Fix: linhas curtas em _staging_load_from_data (quebra de linha em campos texto)
- Q101-Q111 implementadas em queries/fraude_dados_pb_novos.sql
- Validação: Q101, Q104, Q105, Q106, Q108, Q110 funcionam. Q102/Q103/Q107 precisam usar pb_empenho (pb_pagamento tem só 1 CNPJ PJ)
- Descoberta: pb_pagamento = quase 100% PF; pb_empenho = 18K CNPJs PJ
- Normalização rodando (foi desbloqueada ao cancelar query PNCP de 14h)

### 2026-04-05 (continuação sessao 34)
- Q102, Q103 e Q107 reescritas para usar `pb_empenho` em vez de `pb_pagamento`
- Índices adicionados em `sql/19_indices_queries.sql` para `pb_empenho`, CEIS/CNEP, PGFN, TSE e `socio(tipo_socio, nome_upper, cnpj_basico)`
- Validação local: Q102 = 52 grupos, Q103 = 2757 grupos, Q107 = 1 caso
- Q109 reescrita para remover `JOIN LATERAL` explosivo; agora retorna 577 grupos em ~12s
- Q111 corrigida (`tem_cnep`), MV criada com sucesso e `REFRESH MATERIALIZED VIEW` executado: 18.306 linhas

### 2026-04-05 (sessao 35)
- Loader de emendas ajustado para aceitar arquivos na raiz e em `DATA_DIR/emendas`
- Fase de índices ajustada para pular tabelas ainda ausentes em vez de abortar
- Schema PNCP ampliado para identificadores/processo longos
- Loader BNDES trocado para parser CSV tolerante com skip de linhas malformadas
- Loader PGFN reescrito para mapear colunas dinamicamente pelo header
- `download_dados_pb()` e `validate_downloads()` ajustados para não exigir o mês corrente e aceitar layouts antigo/novo de BNDES/PGFN/Emendas
- Commits publicados em `origin/main`: `b81bf92`, `ced083b`

### 2026-04-05 (sessao 33)
- Deploy reescrito: setup-runner.yml + deploy.yml (self-hosted, live logs)
- Diagnosticados 11 bugs no ETL da VM (6 corrigidos, 6 pendentes)
- Fixes: PNCP overflow, BNDES colunas, indices ordem, \d warnings, validação downloads, RFB renomeação

### 2026-04-05 (sessao 32)
- Relatorio `ciclo_politico_financeiro_exploratorio` produzido
- Caso forte validado em `Q56`: `FM PRODUCOES E EVENTOS LTDA`

### 2026-04-04 (sessao 31)
- Q58 otimizada, relatorio `empresas_relacionadas_concorrencia` PB e nacional

### 2026-04-04 (sessao 30)
- Bug PNCP 204 + urlopen SSL corrigidos. Benchmark VM: ~2.3 min/semana
