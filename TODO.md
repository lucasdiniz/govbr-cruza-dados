# TODO - govbr-cruza-dados

## Pendente
- [ ] **Issue #2**: Deploy VM Azure — run 23692083768 timeout (PNCP API). Fix: abort apos 20 erros consecutivos, salvar semanas falhadas em _checkpoint.json, continue-on-error no workflow. Novo deploy pendente.
- [ ] ETL pncp_itens local: pronto para re-executar (aguardando 12_views.sql terminar)
- [x] **Encoding investigado**: Tabelas RFB limpas (UPPER() OK em 66M+27M+69M rows). Erro era do psql Windows terminal — dados UTF-8 válidos no banco. Fix: usar `2>/dev/null` ou `SET client_encoding TO 'WIN1252'`
- [x] **Bug tipo_pessoa**: Corrigido em 12_views.sql — PGFN, CEIS e CNEP agora usam `IN ('PJ', 'Pessoa jurídica', 'J')`
- [ ] Q55/Q56: empresa fenix e doador→contrato — testar
- [ ] Q72 doador→prefeito: doacoes PJ sao fundo partidario (proibidas desde 2015), query nao gera achados
- [ ] MVs: 12_views.sql re-executando (sessao 23). ~70% completo, em _tmp_conflito do mv_servidor_pb_risco

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
- pncp_item: 3.8M rows (parcial, será truncado e recarregado). Alvo ~3M items de ~2.99M JSONs
- DB size: 204 GB
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

### 2026-03-28 (sessao 22)
- **Encoding investigado**: Tabelas RFB limpas. Erro era do psql Windows (terminal nao suporta UTF-8). Fix: `2>/dev/null` ou `SET client_encoding TO 'WIN1252'`
- **ETL pncp_itens**: ~40% (1.2M/3M), ainda rodando
- **MVs recriadas**: mv_empresa_governo (690K), mv_pessoa_pb (204K), mv_municipio_pb_risco (223), mv_servidor_pb_base. Resto em andamento via 12_views.sql
- **Bug tipo_pessoa**: PGFN usa "Pessoa jurídica" (nao "PJ"), CEIS usa "J" (nao "PJ"). Flags CEIS/CNEP/PGFN zeradas nas MVs.
- **3 novos relatorios**:
  1. servidor_bolsa_familia_pb: 20.566 servidores em 223 municipios recebendo BF (79% contratos temporarios)
  2. empresas_inativas_fornecedoras_pb: Edilane Carvalho (144 mun), MJ Comercio (33 mun, R$20M)
  3. risco_municipal_pb: Score 25-52, JP com 76.7% proponente unico, Lucena score 52

### 2026-03-28 (sessao 23)
- **Diagnóstico pncp_item crash**: PG log revelou `o valor "202439" está fora do intervalo para smallint` — `ano_compra SMALLINT` overflow. Dados corrompidos da API PNCP (ano+seq concatenados).
- **Fix schema**: `ano_compra SMALLINT → INTEGER` em 03_schema_pncp.sql, 03b_schema_pncp_itens.sql e ALTER TABLE no banco live
- **Fix ETL 04b_pncp_itens.py**: try/except por batch COPY, retry linha-a-linha em falha, log persistente (pncp_itens_etl.log), TRUNCATE no inicio, `_to_int()` sanitizer para ano_compra/sequencial_compra
- **Zombie PID 12536**: processo COPY pncp_item em `idle in transaction (aborted)` por 2h+. Terminado.
- **12_views.sql re-executado**: run anterior incompleta (só 3 de 7+ MVs criadas). Desbloqueado PID 20960 (orphan superuser lock em mv_servidor_pb_base). Re-run em andamento.
- **Bug tipo_pessoa**: já estava corrigido em 12_views.sql (usa `IN ('PJ', 'Pessoa jurídica', 'J')` nos filtros)

### Handoff sessao 24
- 12_views.sql: rodando (~70%, em _tmp_conflito do mv_servidor_pb_risco). Faltam: steps 4-6, mv_empresa_pb, mv_rede_pb, views
- ETL pncp_itens: pronto para re-executar apos 12_views.sql terminar (`python -m etl.04b_pncp_itens`)
- Deploy run 23692083768 status desconhecido (nao verificado nesta sessao)
- Proximos passos:
  1. Aguardar 12_views.sql terminar e validar MVs
  2. Executar ETL pncp_itens (TRUNCATE + reload com error handling)
  3. Testar Q55 empresa fenix e Q56 doador→contrato
  4. Monitorar deploy Azure
  5. Mais relatorios: Q77 fracionamento, mv_rede_pb, mv_servidor_pb_risco
  6. Push + commit
