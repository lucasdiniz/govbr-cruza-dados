# TODO - govbr-cruza-dados

## Pendente
- [ ] **Issue #2**: Deploy VM Azure — run 23687002733 em andamento (codigo antigo). Re-triggar quando terminar.
- [ ] **Issue #5**: Q59 fix commitado (CTE pre-agrega), Q70 fix commitado (PF filter). Falta re-rodar e validar.
- [ ] ETL pncp_itens: re-rodar (crashou em 550k/3M, fix VARCHAR(500) aplicado)
- [ ] Queries superfaturamento Q45-Q58 pendentes (Q43/Q44/Q51/Q53 ja implementadas)

## Concluido
- [x] **Issue #1**: tce_pb_despesa dates — 3 formatos + ano_arquivo. Validado: 15.8M rows, 2018-2026
- [x] **Issue #3**: Q59/Q63 filtros temporais. Validado na query run de 28/03
- [x] **Issue #4**: CPF+nome matching em Q10/Q21/Q22/Q29. Q10: 979 (de ~16K). Validado
- [x] Views materializadas: 7 MVs + 2 views risco (12_views.sql)
- [x] 75 queries implementadas, 77 CSVs gerados (28/03/2026)
- [x] Downloads automatizados: RFB, PGFN, emendas, renuncias, BNDES, PNCP, TCE-PB, dados.pb
- [x] Normalizacao fases 1-8 completas (~43 indices)
- [x] VM Azure: data disk 512GB montado, PG16 instalado, deploy.yml reescrito
- [x] PNCP API fix: timeout 60→120s, retries 3→5, backoff ate 30s, sleep 0.05→0.5s
- [x] Relatorios revisados (sessao 20):
  - 7 deletados (acusatorios: cartel_combustiveis, risk_score_elite_politica/medica, smart_smurfing, fazenda_laranjas, laranjas_politicos, megafraudes)
  - 4 reescritos com linguagem neutra (laranjas_bolsa_familia, laranjas_teixeira, monopolios_terceiro_setor, tratoraco_codevasf)
  - 11 revisados: disclaimer adicionado, encoding corrigido, linguagem neutralizada
  - Todos achados verificados contra banco PostgreSQL local

## Estado do banco (~336M registros)
- empresa: 66.6M, estabelecimento: 69.8M, simples: 47M, socio: 27M
- tce_pb_servidor: 21.7M, pgfn_divida: 39.9M, bolsa_familia: 20.9M, tce_pb_despesa: 15.8M
- tse_despesa: 6M, tse_bem_candidato: 4M, pb_pagamento: 3.87M, viagem: 3.9M, pncp_contrato: 3.7M
- tse_candidato: 2.1M, tse_receita_candidato: 2.3M, pb_empenho: 1.67M, tce_pb_receita: 1.2M, emenda_favorecido: 1.2M
- cpgf_transacao: 645k, tce_pb_licitacao: 310k, pb_saude: 215k, bndes_contrato: ~100k
- pb_contrato: 15.6k, pb_convenio: 7.8k
- PostgreSQL local: user=postgres, db=govbr, password=kong1029, work_mem=512MB
- Dados brutos: G:\govbr-dados-brutos (DATA_DIR no .env, HDD)
- GitHub: https://github.com/lucasdiniz/govbr-cruza-dados (public)

## Queries pendentes (Q45-Q58)
- [x] Q43: Sobrepreco (7.496), Q44: Aditivos suspeitos (7.766), Q51: Proporcao dispensas (2.171), Q53: Capital minimo (17.234)
- [ ] Q45: Fracionamento licitacao
- [ ] Q46: Queima orcamento nov-dez, Q47: Contratos fim de semana, Q48: Pico pre-eleicao
- [ ] Q49: Fornecedor outro estado, Q50: Mesmo endereco mesmo orgao
- [ ] Q54: CNAE incompativel, Q55: Empresa fenix, Q56: Doador→contrato, Q57: Ciclo emenda→TSE, Q58: Mesmo endereco

## Log

### 2026-03-21 — 2026-03-24 (sessoes 2-12, resumo)
- ETL completo: 15+ fontes, ~336M registros, 75 queries, 7 MVs, deploy.yml skeleton

### 2026-03-27 (sessoes 13-14)
- Issues #1/#3/#4 fixes, deploy.yml reescrito, 6 fontes download automatizadas

### 2026-03-28 (sessoes 15-19)
- ETL tce_pb completo, VM Azure disk 512GB, 77 CSVs validados
- 3 novos relatorios, PNCP bulk download, Issue #5 criada
- PNCP API fix (timeout/retries/backoff/sleep)

### 2026-03-28 (sessao 20)
- **Relatorios**: 7 deletados, 4 reescritos, 11 revisados. Todos achados verificados contra DB.
- **Queries**: Q59 JOIN explosion fix (CTE pre-aggregate), Q70 PF filter fix. Commitados.
- **Deploy**: run 23687002733 ainda em andamento (step 7 Full ETL, codigo antigo)
- **cnpj_basico em tce_pb_despesa**: so populado para PJ (14 dig), nao PF. Q70 PF collision nao existe nesta tabela.

### Handoff sessao 21
- Git: commit 372aec2, pushed to main
- DB local OK, psql: `/c/Program Files/PostgreSQL/16/bin/psql.exe`, PGPASSWORD=kong1029
- Deploy run 23687002733 em andamento (step 7, codigo ANTIGO sem fix PNCP). Re-triggar quando terminar.
- Q59 CTE fix commitado mas nao testado (query pesada, timeout local). Testar na proxima sessao.
- Issues: #1/#3/#4 fechadas, #2 (deploy) aberta, #5 (query quality) aberta
- Proximos passos:
  1. Monitorar deploy, re-triggar com fix PNCP quando terminar
  2. Re-rodar Q59/Q70 e validar resultados
  3. Implementar Q45-Q58 (superfaturamento)
  4. Re-rodar pncp_itens ETL
