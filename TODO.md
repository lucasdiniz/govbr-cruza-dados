# TODO - govbr-cruza-dados

## Pendente (por prioridade)

### Enriquecimento de relatórios com cruzamentos
1. [x] **Fênix PB × mv_empresa_governo**: 43/390 contrataram governo, R$119.1M total. CONSORCIO SFT R$95.9M.
2. [ ] **Fênix PB × PGFN** (refazer com CNPJ completo 14 digitos ou CPF socio)
3. [ ] **Fênix PB × CEIS/CNEP** (refazer com CNPJ completo 14 digitos)
4. [ ] **Sobrepreço × fornecedores**: Q92 outliers → pncp_contrato → identificar CNPJs que recebem preços inflados
5. [ ] **Sobrepreço × CEIS/CNEP**: Fornecedores de Q97 (jogo planilha) têm histórico de sanções?
6. [ ] **Fracassados SES-PB × contratos diretos**: "planilha sem itens" fracassa → verificar dispensa/inexigibilidade no mesmo período
7. [ ] **Cartel (Q98) × fornecedores**: Preços idênticos → pncp_contrato → mapear rede via mv_rede_pb
8. [ ] **Rede societária × mv_empresa_governo**: Hub-sócios rankeados por volume de contratos governo
9. [ ] **Q99 Fênix nacional**: Query criada, rodando (temp tables + hash). Atualizar relatório com dados nacionais.

### Deep dives
10. [ ] **Deep dive Sec. Educação MS**: 974 licitações fracassadas arroz 19 meses. Preço teto? Fornecedores? Direcionamento?
11. [ ] **Deep dive SES-PB "planilha sem itens"**: 114 submissões R$4.9M médio, R$563M total. Contratos diretos?

### Melhorias queries
12. [ ] **Q94 mediana**: Trocar AVG por PERCENTILE_CONT (usuario exigiu metrica correta)
13. [ ] **Investigar itens > R$1B**: Q92 filtra como "sanidade" mas pode excluir superfaturamento real
14. [ ] **Série temporal de preços**: Q92/Q94 sem segmentação por período, inflação distorce

### Infra
15. [ ] **Deploy Azure (Issue #2)**: DB vazio. Downloads 403. Investigar bloqueio IP Azure.

## Estado do banco local
- **~336M registros** em 15+ fontes. DB size: 205 GB. C: 91GB livres.
- Tabelas principais: empresa 66.6M, estabelecimento 69.8M, simples 47M, socio 27M, pgfn_divida 39.9M, tce_pb_servidor 21.7M, bolsa_familia 20.9M, tce_pb_despesa 15.8M, pncp_item 4.71M, pncp_contrato 3.76M
- **MVs OK**: mv_rede_pb 1.68M, mv_servidor_pb_base 353K, mv_servidor_pb_risco 353K, mv_pessoa_pb 205K, mv_empresa_pb 157K, v_risk_score_pb 135K, mv_municipio_pb_risco 224
- mv_empresa_governo 690K rows (criada sessao 26)
- PostgreSQL: `PGPASSWORD=kong1029 "/c/Program Files/PostgreSQL/16/bin/psql.exe" -U postgres -d govbr`
- Dados brutos: G:\govbr-dados-brutos (HDD)
- 93+ queries em queries/*.sql, 28 relatorios em relatorios/

## Concluido (resumo)
- Issues #1-#5 resolvidas e validadas
- ETL completo: 15+ fontes, normalizacao, indices
- Bug tipo_pessoa corrigido em 12_views.sql (PGFN="Pessoa jurídica", CEIS="J", filtros usam IN)
- Encoding: dados UTF-8 válidos, erro era psql Windows (fix: `2>/dev/null` ou `SET client_encoding TO 'WIN1252'`)
- pncp_itens ETL completo (4.71M rows)
- **7/7 MVs + 2 views criadas** (todas completas)
- 25 relatorios escritos e revisados
- VM Azure configurada (disk 512GB, PG16), deploy.yml com continue-on-error

## Log recente

### 2026-03-29 (sessao 24)
- Deploy timeout 5h PNCP API. Fix: abort 20 erros, checkpoint, continue-on-error
- IDE crash matou processos locais. Fix: run_remaining.ps1 detached

### 2026-04-03 (sessao 25)
- Diagnostico pos-intervalo: 6/7 MVs OK, mv_empresa_governo falhou (disk space)
- pncp_item completo: 4.71M rows
- Deploy 23718465381 "success" mas DB Azure vazio (downloads bloqueados)
- tipo_pessoa fix linhas 661/668 aplicado (ja commitado)

### 2026-04-04 (sessao 28)
- 3 relatorios escritos: sobrepreco_pncp_item, itens_fracassados_pncp, empresa_fenix_pb
- Q99 criada: fenix nacional com temp tables (18.7M closed × 16.3M active, 2020+)
- Cruzamento fenix PB: 43/390 empresas novas contrataram governo (R$119.1M). Top: CONSORCIO SFT R$95.9M
- PGFN/CEIS cruzamento por cnpj_basico retornou 0 (precisa CNPJ completo ou CPF socio)
- Deep dive Sec.Educacao MS: preco NÃO é o problema (R$25.28 vs R$26.01 nacional). 96% fracassos via Dispensa individual por escola (4781 processos), apenas 3 via Pregao Eletronico. Hipotese: modelo operacional ineficiente, nao fraude de preco.
- Deep dive SES-PB: "planilha sem itens" é workaround PNCP para credenciamento, NAO fraude. Mas R$1.17B via inexigibilidade/dispensa sem detalhamento de itens. PB SAUDE R$355M, JUSTIZ R$40M. Risco de controle.
- Relatorios fenix e fracassados enriquecidos com dados reais dos cruzamentos e deep dives

### 2026-04-03 (sessao 27)
- 7 queries pncp_item criadas (Q92-Q98): sobrepreco, fracassados repetidos, variacao UF, concentracao fornecedor, sigiloso, jogo de planilha, precos identicos
- Q55 fix: filtro UF='PB' reduz cost de 21M para 2.9M. 483 empresas fenix na PB (390 novas, 397 socios, 36 municipios, 174 em <30 dias)
- Q92 performance: window functions timeout, temp table com MD5 hash funciona (~2min)
- Dados: 46% dos itens homologados compartilham descricao exata com 10+ outros
- NCM esparso (1.4%), catalogo quase inexistente (0.1%) — queries usam descricao normalizada
- Achados: Sec. Educacao MS 974 licitacoes fracassadas arroz; flanela R$22K (388x media); SES-PB planilha vazia R$563M
- Agentes Sonnet para relatorios falharam (limite de uso Anthropic) — dados coletados, relatorios pendentes
- Feedback usuario: nao usar metrica errada (AVG vs mediana) por economia; investigar itens >R$1B; adicionar serie temporal

### 2026-04-03 (sessao 26)
- mv_empresa_governo criada: 690K rows, 5 indices. (1a tentativa falhou maintenance_work_mem 1kB acima max)
- Q56 (doador->contrato) testada OK: 3 doadores distintos, 322 matches. FM PRODUCOES (PL-SE) mais relevante.
- Q55 (empresa fenix) adiada: self-join muito pesado, competiria com MV por temp space.
- Index criado: idx_tse_rec_cnpj_basico_doador (funcional, para Q56)
- 4 relatorios novos escritos:
  - relatorio_fracionamento_despesa_pb.md (26K grupos, R$3.6B, ALLFAMED padrao sistematico)
  - relatorio_risk_score_pb.md (135K entidades, 81 alto risco, medicos dominam)
  - relatorio_servidor_risco_pb.md (353K servidores, 73 score>=70, todos medicos)
  - relatorio_rede_societaria_pb.md (1.68M arestas, Cavalcanti hub 28 empresas)
