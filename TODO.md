# TODO - govbr-cruza-dados

## Pendente
- [EM BACKGROUND] Fix pgfn_divida.cpf_cnpj_norm — UPDATE 39.9M rows, ~5h rodando (PID 16664)
- [x] Fix emenda_favorecido: cnpj_basico_favorecido limpo — PJ 576k OK, PF/outros NULL. Script usa regex ^[0-9]+$
- [x] Fix ceis_sancao/cnep_sancao: cpf_digitos_6 criado (9.032 + 32 rows) + indices criados
- [ ] Atualizar Q06, Q24, Q37 para usar colunas normalizadas
- [ ] Re-executar TODAS as queries (`python -m etl.run_queries`) — apos todos os fixes
- [ ] Recriar views materializadas (`sql/12_views.sql`)
- [ ] Limpar tmp_run_q39.py, tmp_run_partial.py e tmp_analysis.sql

## Estado do banco (~285M registros)
- empresa: 66.6M, estabelecimento: 69.8M, simples: 47M, socio: 27M
- pgfn_divida: 39.9M, bolsa_familia: 20.9M, viagem: 3.9M, pncp_contrato: 3.7M
- tse_candidato: 2.1M, tse_bem_candidato: 4M, tse_receita: 2.3M, tse_despesa: 6M
- cpgf_transacao: 645k, emenda_favorecido: 1.2M, bndes_contrato: ~100k
- PostgreSQL: localhost, user=govbr, db=govbr
- Dados brutos: G:\govbr-dados-brutos (DATA_DIR no .env), disco C: 75GB livres
- GitHub: https://github.com/lucasdiniz/govbr-cruza-dados (public)

## Normalizacao (etl.15_normalizar)
Colunas desnormalizadas + ~25 indices criados. Status:
- [x] socio.cpf_cnpj_norm (6 digitos) — 27M rows OK
- [x] bolsa_familia.cpf_digitos (6 digitos) — 21M rows OK
- [x] siape_cadastro.cpf_digitos (6 digitos) — OK
- [x] cpgf_transacao.cpf_portador_digitos (6 digitos) — OK
- [x] ceaf_expulsao.cpf_cnpj_norm (6 digitos, CPF mascarado) — OK
- [x] viagem.cpf_viajante_digitos (6 digitos) — OK
- [x] pncp_contrato.cnpj_basico_fornecedor (8 digitos) — OK
- [x] emenda_favorecido.cnpj_basico_favorecido (8 digitos, MAS quebrado para PF)
- [x] ceis_sancao.cpf_cnpj_norm (CPF completo 11 dig / CNPJ 14 dig — preservar!)
- [x] cnep_sancao.cpf_cnpj_norm (idem)
- [x] acordo_leniencia.cnpj_norm — OK
- [EM BACKGROUND] pgfn_divida.cpf_cnpj_norm — 39.9M rows, rodando agora
- [x] Todos os indices das fases 2-4 criados

## Queries otimizadas (sessao 4)
14 queries migradas de REGEXP_REPLACE/SUBSTRING/LIKE para colunas normalizadas indexadas:
Q02, Q10, Q16, Q18, Q21, Q22, Q25, Q26, Q27, Q28, Q29, Q32, Q33, Q39
15 queries com UF/municipio adicionado:
Q03, Q04, Q07, Q10, Q11, Q15, Q18, Q21, Q22, Q25, Q26, Q27, Q28, Q33, Q36, Q37
Pendente otimizacao: Q06, Q24, Q37 (dependem de fix emenda/ceis/cnep)

## Log

### 2026-03-21 (sessao 5)
- Retomada: PGFN UPDATE ainda rodando (~5h, PID 16664), 39.9M rows transacao unica
- Preparado fix emenda_favorecido no 15_normalizar.py: UPDATE filtra tipo_favorecido='Pessoa Juridica' + limpa 218k PF com cnpj_basico lixo
- Preparado fix ceis/cnep no 15_normalizar.py: nova coluna cpf_digitos_6 = SUBSTRING(cpf_cnpj_norm, 4, 6) para CPFs 11 digitos
- Verificado fixes: emenda PF tem lixo confirmado (***.630. etc), ceis match com socio via 6 digitos funciona (testado)
- ceis: 9.032 CPFs + 13.513 CNPJs, cnep: 32 CPFs + 1.550 CNPJs
- Fixes emenda + ceis/cnep rodando em paralelo com PGFN (tabelas diferentes, sem conflito)
- Fix emenda: primeiro UPDATE limpou demais (tipo_favorecido com acento nao matchou string literal). Corrigido com regex codigo_favorecido ~ '[^0-9]'
- Fix emenda: segundo problema — CPF mascarado ***.053.502-** tem LENGTH=14 igual CNPJ. Filtro final: codigo_favorecido ~ '^[0-9]+$'
- Fix emenda concluido: PJ 576k com cnpj_basico, PF/outros 221k limpos (NULL)
- Fix ceis/cnep concluido: cpf_digitos_6 = SUBSTRING(cpf_cnpj_norm, 4, 6) para CPFs 11 dig. ceis 9.032 + cnep 32 rows + 2 indices
- 15_normalizar.py atualizado com ambos os fixes (regex para emenda, cpf_digitos_6 para ceis/cnep)

### 2026-03-21 (sessao 4)
- Verificado processos background: normalizar (PID 9244) e partial runner (PID 12632) rodando OK
- Normalização progrediu: PGFN (40M rows) concluido, avançou para socio (27M rows)
- Matou Q39 duplicada que competia por recursos + limpou shells residuais do psql
- Atualizado README com todas as 15+ fontes e 42 queries
- Push para GitHub: https://github.com/lucasdiniz/govbr-cruza-dados
- Fix Q15: adicionado filtro temporal em CPGF (dt_transacao > dt_situacao) e emenda (TO_DATE(ano_mes) > dt_situacao)
- Fix Q15: corrigido formato ano_mes (YYYYMM, não YYYY/MM)
- Q15 re-executada: 1.470 resultados (empresas inativas recebendo pagamentos apos baixa)
- Criada pasta relatorios/ para investigacoes baseadas nos resultados das queries
- 4 relatorios de investigacao: Campina Grande (pejotizacao medicos), Conceicao, Imaculada, Sao Bento (empresas fachada)
- Detectado deadlock: query sancoes do partial runner bloqueava ALTER TABLE do normalizer por ~53min. Cancelada query para liberar
- Normalização avancou: PGFN OK, socio OK, agora em viagem/pncp_contrato (tabelas menores)
- Adicionado UF/municipio em 15 queries (Q03,Q04,Q07,Q10,Q11,Q15,Q18,Q21,Q22,Q25,Q26,Q27,Q28,Q33,Q36,Q37)
- Fonte decidida caso a caso: orgao contratante (pc.uf) para contratos PNCP, sede da empresa (est.uf) para queries societarias, ambos para Q03
- Partial runner (PID 12632) parado para re-executar queries com UF/municipio apos normalizacao
- Queries otimizadas: REGEXP_REPLACE/SUBSTRING/LIKE → colunas normalizadas (cpf_digitos, cpf_cnpj_norm, cnpj_basico_fornecedor)
- Queries modificadas: Q02,Q10,Q16,Q18,Q21,Q22,Q25,Q26,Q27,Q28,Q29,Q32,Q33,Q39
- Pendente otimizacao: Q06,Q24,Q37 (dependem de fix em emenda_favorecido/ceis/cnep)
- Verificacao normalizacao: pgfn 39.9M nulls (UPDATE cancelado em sessao anterior), emenda PF quebrado, ceis/cnep tem CPF completo (preservar)
- Normalizacao concluida: todas colunas + 25 indices criados (exceto pgfn — re-executando UPDATE agora)
- PGFN cpf_cnpj tem CPF e CNPJ misturados: 24.8M CNPJs (18 chars, ex: 57.934.457/0001-90) + 15.1M CPFs mascarados (12 chars, ex: XXX987.448XX)
- run_all.py atualizado com 4 fases faltantes (TSE candidatos, BF, TSE prestacao contas, normalizar)
- README atualizado: entity resolution com tabela de formatos CPF, run_queries usage, relatorios/
- TODO reorganizado: adicionado estado do banco, status normalizacao, queries otimizadas

### 2026-03-21 (sessao 3)
- Verificado PGFN: 39.9M registros, 0 datas NULL, sem duplicatas reais (mesmo numero_inscricao = PRINCIPAL + CORRESPONSAVEL)
- Criado indice idx_pgfn_inscricao em pgfn_divida(numero_inscricao)
- Limpeza disco: removido 45GB de dados duplicados do C: (ja estavam em G:\govbr-dados-brutos). Disco C: 75GB livres agora
- DATA_DIR ja apontava para G:\govbr-dados-brutos no .env
- PARADO etl.15_normalizar — interrompido para varredura de indices. Precisa retomar
- Q39 testada: 59.168 socios de empresas comerciais recebendo Bolsa Familia (match nome + 6 digitos CPF)
- Refinada queries BF (Q38/Q39/Q40): adicionado match por digitos centrais CPF + exclusao de associacoes/cooperativas
- Fix: removido DROP de tse_receita/despesa do schema 16 (evita perder 8.3M registros do ETL 18)
- Criado etl/run_queries.py — exporta resultados das 42 queries para CSV em resultados/
- Varredura de indices: criado sql/19_indices_queries.sql com ~20 indices (LEFT8, UPPER/TRIM, cpf_digitos, datas)
- Reescrito etl/15_normalizar.py: execucao por statement (idempotente), inclui novos indices + colunas BF/SIAPE/CPGF
- Queries BF atualizadas para usar colunas desnormalizadas (cpf_digitos) em vez de REGEXP_REPLACE inline
- Q39 agora filtra apenas empresas ativas + mostra CNPJ completo + porte/NJ por extenso
- PARADO Q39 — recriar depois de rodar 15_normalizar
- TSE candidatos + bens carregados: 2.1M candidatos + 4M bens (2020/2022/2024)

### 2026-03-21 (sessao 2)
- Recuperado dados orphaned: _stg_estab +4.7M, _stg_pgfn +12.1M
- Fix regex f-string: \d{2} → \d{{2}} em 07_pgfn, 06_cpgf, 05_emendas
- Recarga completa PGFN (39.9M, 100% datas) e emenda_convenio (80k, 100% datas)
- ETL + carga Bolsa Familia: 20.9M registros
- ETL + carga TSE Prestacao de Contas: receitas 2.3M + despesas 6M
- Fix extracao incompleta prestacao_contas_2024.zip (25 UFs faltando)
- Queries de fraude TSE (Q33-Q37) e Bolsa Familia (Q38-Q42)
- Estabelecimentos: 69.8M registros (inclui staging recuperada)

## Proxima iteracao: novas fontes
- [ ] Pessoas Expostas Politicamente (PEP) — deu 403, tentar novamente
- [ ] Favorecidos PJ - Portal da Transparencia (dados.gov.br)
- [ ] Notas Fiscais Eletronicas (portaldatransparencia.gov.br)
- [ ] Explorar catalogo completo do dados.gov.br via API (chave no .env)

## Melhorias tecnicas
- [ ] Otimizar _staging_copy do RFB (csv.reader Python lento para 13GB)
- [ ] Script de validacao (wc -l CSVs vs COUNT(*) tabelas)
- [ ] Script de atualizacao incremental
- [ ] Trocar senha do PostgreSQL (exposta em historicos de conversa)
- [ ] Configurar max_wal_size no PostgreSQL

## Qualidade dos dados
- [ ] 101 registros de empresa com natureza_juridica corrompida
- [ ] CPGF: 25% transacoes sem data (sigiloso) — normal, nao e bug
- [ ] Recarregar CPGF com regex corrigida (pode ganhar mais datas)
- [ ] Estabelecimentos: conferir se 69.8M bate com total esperado
