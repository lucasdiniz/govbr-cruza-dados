# TODO - govbr-cruza-dados

## Pendente

### Infra / DX
- [ ] **Docker Compose completo** — adicionar service `etl` (Dockerfile com Python + deps) para deploy local de 1 comando. Hoje o compose só sobe o Postgres.

### Deploy Azure
- [ ] **Deploy em andamento** — retomado a partir da fase 19 (run 24286000479). CSVs de rfb (58GB) e bolsa_familia (85GB) removidos manualmente para liberar disco. 143GB livres.
- [ ] **Auto-limpeza de CSVs implementada** — `run_all.py` agora remove CSVs brutos após cada fase ETL bem-sucedida. Diretórios compartilhados (rfb, tse) só são removidos quando todas as fases dependentes completam.
- [ ] **Issues #1-#4**: Pendentes execução no banco local
- [ ] **Formalizar Q58 por UF**
- [ ] **Corrigir agregacao monetaria da Q17**
- [ ] **Endurecer relatorio do ciclo politico-financeiro**
- [ ] **Revisar/arquivar relatorios invalidos** conforme classificacao abaixo
- [ ] **Padronizar citacao `razao social + CNPJ` nos relatorios ativos**
- [ ] **Corrigir relatorios com CNPJ nao encontrado na base RFB local**

### Catalogo de relatorios - revisao de validade

#### Relatorios validos
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
- `relatorio_duplo_pagamento_nf_pb.md`
- `relatorio_ciclo_anulacao_reempenho_pb.md`
- `relatorio_diarias_sobrepostas_pb.md`
- `relatorio_convenios_devedores_pgfn_pb.md`
- `relatorio_suplementacoes_concentradas_pb.md`
- `relatorio_rede_empresarial_familia_hugo_motta.md`
- `relatorio_duplo_vinculo_publico_pb.md`
- `relatorio_porta_giratoria_pb.md`
- `relatorio_fornecedor_saude_dominante_pb.md`
- `relatorio_bndes_doador_tse.md`

#### Relatorios invalidos ou nao publicaveis
- `relatorio_servidor_bolsa_familia_pb.md` - depende de Q74 (CPF parcial + nome), risco alto de falso positivo
- `relatorio_laranjas_bolsa_familia_pb.md` - mesma fragilidade de Q39/Q74, CNPJs nao encontrados
- `relatorio_risco_municipal_pb.md` - score usa indicador quebrado (sem licitacao zerado)
- `relatorio_servidor_risco_pb.md` - herda ruido de Q74 e score composto
- `relatorio_risk_score_pb.md` - herda problemas de score
- `relatorio_servidor_socio_fornecedor_pb.md` - superado pela versao corrigida de Q59
- `relatorio_servidor_estadual_socio_fornecedor_pb.md` - depende de match nominal fraco (Q109)
- `relatorio_ciclo_politico_financeiro_exploratorio.md` - exploratorio, nao publicavel
- `relatorio_rede_societaria_pb.md` - bom como mapa analitico, fraco como relatorio conclusivo
- `relatorio_itens_fracassados_pncp.md` - texto forte demais para a prova atual

### Auditoria de identificadores em relatorios
- Script: `scripts/audit_report_identifiers.py`
- Problema mais comum: CNPJ citado sem nome oficial ao lado
- CNPJs nao encontrados na RFB: ver `relatorio_laranjas_bolsa_familia_pb.md`

## Referencia tecnica

### Banco de dados
- **~350M registros** em 18+ fontes, ~210GB
- PostgreSQL local: `PGPASSWORD=kong1029 "/c/Program Files/PostgreSQL/16/bin/psql.exe" -U postgres -d govbr`
- Dados brutos locais: G:\govbr-dados-brutos (HDD)
- 115+ queries em queries/*.sql, 26 relatorios validos em relatorios/

### VM Azure
- **Standard_B4as_v2** (4 vCPU, 16GB RAM) — North Central US
- Disco: 512GB Standard SSD em /data (PostgreSQL 248GB + dados brutos ~105GB após limpeza)
- Budget: ~US$150/mês
- SSH: `ssh -i /tmp/azure_vm_key govbr@52.162.207.186`
- Workflows: `deploy.yml` (ETL), `setup-runner.yml` (runner 1x)
- Secrets: `VM_HOST`, `VM_SSH_KEY`, `DB_PASSWORD`, `ENV_FILE`, `RUNNER_ADMIN_TOKEN`

### Notas tecnicas importantes
- **pb_pagamento** tem quase 100% PF (1 CNPJ PJ). Usar **pb_empenho** para cruzamentos PJ (18K CNPJs distintos)
- **PGFN cpf_cnpj** é formatado com pontos/traço — usar `REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g')` para extrair dígitos
- **CEIS/CNEP cpf_cnpj_norm** é CNPJ completo 14 dígitos — match via `LEFT(cpf_cnpj_norm, 8)`
- CNPJ matching entre tabelas sempre via `cnpj_basico` (primeiros 8 dígitos)

## Concluido (resumo)
- Issues #1-#5 resolvidas (código, não executadas no banco)
- ETL completo local: 16+ fontes, normalizacao, indices
- 7/7 MVs + 2 views criadas. 22 relatorios validos. 14/14 enriquecimentos.
- Q101-Q111 implementadas e validadas (dados.pb)
- Q201-Q209 implementadas (rede empresarial família Hugo Motta)
- Q301-Q310 implementadas (cruzamentos avançados: duplo vínculo, porta giratória, BNDES×TSE, saúde dominante)
- Auto-limpeza de CSVs após ETL implementada em run_all.py
