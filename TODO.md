# TODO - govbr-cruza-dados

## Pendente
- [EM BACKGROUND] `python -m etl.15_normalizar` — PID 9244. Normalizacao avancando: PGFN (40M) concluido, agora em socio (27M). Checar: tasklist | grep 9244
- [PARADO] tmp_run_partial.py — parado para re-executar com UF/municipio nas queries
- [x] Rodar `python -m etl.16_tse` — tse_candidato: 2.1M, tse_bem_candidato: 4M (2020/2022/2024)
- [x] Push para GitHub (repo: github.com/lucasdiniz/govbr-cruza-dados)
- [ ] Quando 15_normalizar terminar: re-executar TODAS as queries (`python -m etl.run_queries`) com colunas normalizadas + UF/municipio
- [ ] Fix: pgfn_divida.cpf_cnpj_norm com 39.9M nulls — re-executar normalizacao para esta tabela
- [ ] Fix: emenda_favorecido.cnpj_basico_favorecido quebrado para PF (LEFT de CPF mascarado → '***.433.'). Filtrar por LENGTH >= 14 ou tipo_favorecido
- [ ] Fix: ceis_sancao/cnep_sancao tem CPF completo (11 digitos) — preservar cpf_cnpj_norm atual + criar cpf_digitos_6 com 6 centrais para match com socio
- [ ] Apos fixes acima: atualizar Q06, Q24, Q37 para usar colunas normalizadas
- [ ] Recriar views materializadas (`sql/12_views.sql`) apos normalizacao
- [ ] Limpar tmp_run_q39.py e tmp_run_partial.py apos uso

## Log

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
- Verificacao normalizacao: pgfn 39.9M nulls, emenda PF quebrado, ceis/cnep tem CPF completo (preservar)

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

## Concluido (2026-03-21)
- [x] Recuperar dados orphaned das staging tables (_stg_estab +4.7M, _stg_pgfn +12.1M)
- [x] Fix: regex em f-strings quebrava datas (\d{2} → \d{{2}} em 07_pgfn, 06_cpgf, 05_emendas)
- [x] Recarga completa PGFN com datas corrigidas (39.9M, 100% com data)
- [x] Recarga emenda_convenio com datas corrigidas (80k, 100% com data)
- [x] ETL + carga Bolsa Familia (20.9M registros, fev/2024)
- [x] ETL + carga TSE Prestacao de Contas 2022+2024 (receitas: 2.3M, despesas: 6M)
- [x] Fix: extração incompleta prestacao_contas_2024.zip (25 UFs faltando)
- [x] Queries de fraude para TSE (Q33-Q37) e Bolsa Familia (Q38-Q42)
- [x] Estabelecimentos: 69.8M registros (inclui staging recuperada)

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
