# TODO - govbr-cruza-dados

## Pendente
- [ ] **Issue #2**: Deploy VM Azure — run 23692083768 em andamento (re-trigado sessao 21)
- [ ] ETL pncp_itens: re-rodando (~100 it/s, 3M arquivos, ~8h estimado no HDD)
- [ ] Q72 doador→prefeito: doacoes PJ sao fundo partidario (proibidas desde 2015), query nao gera achados
- [ ] Q55/Q56: empresa fenix e doador→contrato — nao testados ainda (cancelados para liberar recursos)

## Concluido
- [x] **Issue #1**: tce_pb_despesa dates — 3 formatos + ano_arquivo. Validado: 15.8M rows, 2018-2026
- [x] **Issue #3**: Q59/Q63 filtros temporais. Validado na query run de 28/03
- [x] **Issue #4**: CPF+nome matching em Q10/Q21/Q22/Q29. Q10: 979 (de ~16K). Validado
- [x] **Issue #5**: Q59 CTE fix validado (sessao 21). Q70 PF filter validado (redundante, resultados identicos)
- [x] Q45-Q58 implementados (fraude_superfaturamento.sql)
- [x] Views materializadas: 7 MVs + 2 views risco (12_views.sql)
- [x] 86+ queries implementadas
- [x] Downloads automatizados: RFB, PGFN, emendas, renuncias, BNDES, PNCP, TCE-PB, dados.pb
- [x] Normalizacao fases 1-8 completas (~43 indices)
- [x] VM Azure: data disk 512GB montado, PG16 instalado, deploy.yml reescrito
- [x] PNCP API fix: timeout 60→120s, retries 3→5, backoff ate 30s, sleep 0.05→0.5s
- [x] Relatorios revisados (sessao 20): 7 deletados, 4 reescritos, 11 revisados
- [x] 3 novos relatorios (sessao 21): servidor-socio, contratos fim de semana, capital minimo

## Estado do banco (~336M registros)
- empresa: 66.6M, estabelecimento: 69.8M, simples: 47M, socio: 27M
- tce_pb_servidor: 21.7M, pgfn_divida: 39.9M, bolsa_familia: 20.9M, tce_pb_despesa: 15.8M
- tse_despesa: 6M, tse_bem_candidato: 4M, pb_pagamento: 3.87M, viagem: 3.9M, pncp_contrato: 3.7M
- tse_candidato: 2.1M, tse_receita_candidato: 2.3M, pb_empenho: 1.67M, tce_pb_receita: 1.2M, emenda_favorecido: 1.2M
- cpgf_transacao: 645k, tce_pb_licitacao: 310k, pb_saude: 215k, bndes_contrato: ~100k
- pncp_item: re-carregando (era 1.6M, truncado, alvo 3M)
- PostgreSQL local: user=postgres, db=govbr, password=kong1029, work_mem=512MB
- Dados brutos: G:\govbr-dados-brutos (DATA_DIR no .env, HDD)

## Log

### 2026-03-21 — 2026-03-24 (sessoes 2-12, resumo)
- ETL completo: 15+ fontes, ~336M registros, 75 queries, 7 MVs, deploy.yml skeleton

### 2026-03-27 (sessoes 13-14)
- Issues #1/#3/#4 fixes, deploy.yml reescrito, 6 fontes download automatizadas

### 2026-03-28 (sessoes 15-20)
- ETL tce_pb completo, VM Azure disk 512GB, 77 CSVs validados
- Relatorios: 7 deletados, 4 reescritos, 11 revisados, todos verificados contra DB
- Q59 CTE fix, Q70 PF filter fix, PNCP API fix

### 2026-03-28 (sessao 21)
- **Deploy**: run 23687002733 cancelado. Re-trigado: run 23692083768
- **Q59 validado**: CTE fix funciona. Top: I2 Saude R$65.7M em 16 municipios (198 socios-medicos)
- **Q70 validado**: PF filter redundante (cnpj_basico so existe para PJ)
- **Q45-Q58 implementados**: fracionamento, queima orcamento, fim de semana, pre-eleicao, outro estado, mesmo endereco, CNAE incompativel, empresa fenix, doador→contrato, ciclo emenda→TSE, bid rigging
- **Q47 testado**: 426 contratos PB em fim de semana, R$247.9M. Top: R$96.8M fotovoltaico JP (sabado)
- **Q53 testado**: Doutor Work capital R$10K com contrato R$42M (ratio 4245x)
- **Q74 testado**: servidores PB recebendo Bolsa Familia (Queimadas concentra maioria)
- **ETL pncp_itens**: truncado e re-iniciado (3M arquivos, ~100 it/s no HDD)
- **3 novos relatorios**:
  1. servidor_socio_fornecedor_pb: I2 Saude (198 socios, R$65.7M), MaisMed (R$8.1M), MAG (R$3.7M), HSM2 (R$2.2M)
  2. contratos_fim_de_semana_pb: 426 contratos, R$247.9M
  3. capital_minimo_contratos_pb: Doutor Work R$42M, Silas Fernandes R$2.2M

### Handoff sessao 22
- Git: commit ed4c481, main
- Deploy run 23692083768 em andamento
- ETL pncp_itens rodando em background (~8h estimado)
- Issues: #2 (deploy) aberta, #5 (query quality) pode fechar
- Proximos passos:
  1. Monitorar deploy run 23692083768
  2. Monitorar ETL pncp_itens (completar 3M arquivos)
  3. Testar Q55 empresa fenix e Q56 doador→contrato PNCP
  4. Escrever mais relatorios (Q60 fornecedor sem licitacao, Q74 servidor+BF)
  5. Push final
