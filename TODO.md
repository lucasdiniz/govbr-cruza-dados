# TODO - govbr-cruza-dados

## Pendente
- [ ] **Issue #2**: Deploy VM Azure — run 23687002733 em andamento (clean=true, etl_phase=all)
- [ ] **Issue #5**: Corrigir queries (Q59 JOIN explosion, Q70 CNPJ collision, Q21 valores absurdos, Q29 ruido)
- [ ] ETL pncp_itens: re-rodar (crashou em 550k/3M, fix VARCHAR(500) aplicado)
- [ ] Queries superfaturamento Q45-Q58 pendentes (Q43/Q44/Q51/Q53 ja implementadas)
- [ ] Relatorios pendentes:
  - [ ] Corrigir cartel_combustiveis_pb (linguagem acusatoria, reclassificar)
  - [ ] Corrigir smart_smurfing_cpgf (remover secao ABIN/GSI)
  - [ ] Corrigir risk_score_elite_politica_pb (falso positivo Barauna)
  - [ ] Corrigir fazenda_laranjas_mato_grosso_pb (sem evidencia de "quadrilha")
  - [ ] Adicionar disclaimer padrao a todos relatorios
  - [ ] Corrigir encoding UTF-8 nas secoes duplicadas

## Concluido
- [x] **Issue #1**: tce_pb_despesa dates — 3 formatos + ano_arquivo. Validado: 15.8M rows, 2018-2026
- [x] **Issue #3**: Q59/Q63 filtros temporais. Validado na query run de 28/03
- [x] **Issue #4**: CPF+nome matching em Q10/Q21/Q22/Q29. Q10: 979 (de ~16K). Validado
- [x] Views materializadas: 7 MVs + 2 views risco (12_views.sql)
- [x] 75 queries implementadas, 77 CSVs gerados (28/03/2026)
- [x] 22 relatorios (3 novos sessao 19: sancionados_pb, pejotizacao_saude_pb, conflito_cartao_v2)
- [x] Downloads automatizados: RFB, PGFN, emendas, renuncias, BNDES, PNCP, TCE-PB, dados.pb
- [x] Normalizacao fases 1-8 completas (~43 indices)
- [x] VM Azure: data disk 512GB montado, PG16 instalado, deploy.yml reescrito

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

## Avaliacao relatorios (sessao 15)
Problemas globais: linguagem acusatoria, encoding quebrado, "deteccao precoce" infalsificavel.
- Solidos: falsos_positivos_pb, megafraudes_sertao_pb, cartel_equipamentos_medicos_jp, empresas_inativas_pb
- Problematicos: cartel_combustiveis_pb, smart_smurfing_cpgf (ABIN), risk_score_elite_politica_pb, fazenda_laranjas

## Log

### 2026-03-21 — 2026-03-24 (sessoes 2-12, resumo)
- Sessao 2: Fix f-string regex, recarga PGFN/emendas, ETL BF 20.9M + TSE 8.3M
- Sessao 3: Limpeza disco 45GB, indices, Q39 BF 59k resultados
- Sessao 4: Normalizacao 15_normalizar (fases 1-4), 42 queries executadas, UF/municipio em 15+ queries, Q19 limites legais
- Sessao 5: Fix emenda cpf_cnpj, fix ceis/cnep cpf_digitos_6, PGFN 39.9M normalizado
- Sessao 6: API PNCP mapeada, download_pncp.py criado, Q43/Q44/Q51/Q53 superfaturamento, download itens iniciado
- Sessao 7: TCE-PB nova fonte (4 tabelas, 39M registros), normalizacao fases 5-6
- Sessao 8: dados.pb.gov.br pipeline completo (5 tabelas, 5.78M registros), normalizacao fases 7-8
- Sessao 9: 28 novas queries (Q59-Q91), download PNCP itens 91%
- Sessao 10: Todas 75 queries OK (764k resultados), destaques: Q59 32k, Q60 9.3k, Q62 1.6k
- Sessao 11: 7 MVs + 2 views risco criadas, indices compostos socio+bf (1.95GB)
- Sessao 12: mv_rede_pb (1.67M), etl/04b_pncp_itens.py reescrito, deploy.yml skeleton

### 2026-03-27 (sessao 13)
- Investigacao 4 issues GitHub, plano aprovado: #1→#4→#3→#2
- Root cause Issue #1: _DATE_SQL regex so matchava DD/MM/YYYY (2026), ISO ignorado (97.3% NULL)

### 2026-03-27 (sessao 14)
- Issues #1/#3/#4 FIXES aplicados: _DATE_SQL 3 formatos, nome no JOIN CPF, filtros temporais
- deploy.yml reescrito completo (PG16, clean step, CI/CD)
- 6 fontes download automatizadas (RFB WebDAV, PGFN, emendas, renuncias, BNDES)
- ETL tce_pb_despesa re-rodando

### 2026-03-28 (sessao 15)
- ETL tce_pb completo. Issue #1 validado: data_empenho 100% populado
- VM Azure: data disk 512GB montado, OS disk liberado 99%→8%
- Deploy fixes: safe_to_date, YAML heredoc, verify.py, future month skips
- Avaliacao 20 relatorios (5 problematicos identificados)

### 2026-03-28 (sessao 16)
- Deploy diagnosticado: RFB timeout, ComprasNet VARCHAR(14→20), run_all raise→continue
- RFB reescrito: Nextcloud WebDAV IPv4, auto-detect mes
- User-Agent em todos urlopen

### 2026-03-28 (sessao 17+18)
- PNCP bulk download: API Consulta, page size 50 (contratacoes) / 500 (contratos), intervalos semanais
- Corrupt zip fix, pncp_item.unidade_medida VARCHAR(500)
- PostgreSQL local crashou e recuperado

### 2026-03-28 (sessao 19)
- **Queries validadas**: 77 CSVs. Q10: 979 (CPF+nome OK). Q21: 95. Q22: 4. Q59: 32K. Q63: 501
- **Issues fechadas**: #1, #3, #4. **Issue #5 criada** (query quality bugs)
- **Relatorios**:
  - conflito_cartao_corporativo **REGENERADO v2** (979 matches, removidos falsos positivos CBTU/ICMBio)
  - sancionados_recebendo_pb **NOVO** — 270 empresas CEIS, R$170.6M, 199 municipios
  - pejotizacao_saude_municipal_pb **NOVO** — I2 Saude R$65.8M, 16 municipios, 29+ medicos-socios
- Deploy run 23687002733 em andamento

### Handoff sessao 20
- Git: commits ate 4479008, pushed to main
- DB local: OK, 77 query results em resultados/
- VM: deploy em andamento
- Proximos passos: monitorar deploy, corrigir relatorios problematicos, fix Issue #5 queries
