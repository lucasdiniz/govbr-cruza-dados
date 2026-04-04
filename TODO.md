# TODO - govbr-cruza-dados

## Pendente (por prioridade)
1. [x] **Relatórios pncp_item**: 3 relatórios escritos (sessao 28):
   - relatorio_sobrepreco_pncp_item.md (Q92/Q94/Q97 — 159 linhas)
   - relatorio_itens_fracassados_pncp.md (Q93/Q96/Q98 — 196 linhas)
   - relatorio_empresa_fenix_pb.md (Q55 — 166 linhas)
2. [ ] **Q94 mediana**: Trocar AVG por PERCENTILE_CONT ou abordagem mais precisa (usuario pediu metrica correta, nao economizar processamento)
3. [ ] **Investigar itens > R$1B**: Q92 filtra valor_total<=1B como "sanidade" mas pode excluir superfaturamento real. Analisar esses separadamente.
4. [ ] **Série temporal de preços**: Q92/Q94 nao segmentam por periodo. Inflacao e cambio distorcem comparacao. Adicionar filtro temporal (ex: mesmo ano).
5. [ ] **Deep dive Sec. Educação MS**: 974 licitacoes fracassadas de arroz em 19 meses. Investigar: preco teto irrealista? falta de fornecedores? direcionamento?
6. [ ] **Deep dive SES-PB "planilha sem itens"**: 114 submissoes a R$4.9M medio, R$563M total em 595 dias. Muito suspeito.
7. [ ] **Deploy Azure (Issue #2)**: DB vazio. Downloads 403 (CPGF, SIAPE, CEIS, CNEP, CEAF) + PNCP API 500/empty body da VM. Investigar bloqueio IP Azure.

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
