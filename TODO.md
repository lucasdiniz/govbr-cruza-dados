# TODO - govbr-cruza-dados

## Pendente
- [EM BACKGROUND] Fix pgfn_divida.cpf_cnpj_norm — UPDATE 39.9M rows rodando agora
- [ ] Re-executar TODAS as queries (`python -m etl.run_queries`) — queries agora usam colunas normalizadas + UF/municipio
- [ ] Fix: emenda_favorecido.cnpj_basico_favorecido quebrado para PF (LEFT de CPF mascarado → '***.433.'). Filtrar por LENGTH >= 14 ou tipo_favorecido
- [ ] Fix: ceis_sancao/cnep_sancao tem CPF completo (11 digitos) — preservar cpf_cnpj_norm atual + criar cpf_digitos_6 com 6 centrais para match com socio
- [ ] Apos fixes acima: atualizar Q06, Q24, Q37 para usar colunas normalizadas
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

### 2026-03-21 (sessao 4)
- Normalizacao concluida: colunas + 25 indices (exceto pgfn que foi cancelado, re-executando)
- Fix Q15: filtro temporal em CPGF/emenda + formato ano_mes corrigido (YYYYMM). 1.470 resultados
- 4 relatorios de investigacao PB: Campina Grande (pejotizacao), Conceicao, Imaculada, Sao Bento
- UF/municipio adicionado em 15 queries (fonte caso a caso: orgao contratante vs sede empresa)
- 14 queries otimizadas: REGEXP_REPLACE/SUBSTRING/LIKE → colunas normalizadas indexadas
- Verificacao normalizacao: pgfn nulls, emenda PF quebrado, ceis/cnep CPF completo (preservar)
- run_all.py atualizado com 4 fases faltantes (TSE, BF, prestacao contas, normalizar)
- README atualizado: entity resolution, run_queries, relatorios/
- Push para GitHub: https://github.com/lucasdiniz/govbr-cruza-dados

### 2026-03-21 (sessao 3)
- PGFN verificado: 39.9M, 0 datas NULL, duplicatas sao PRINCIPAL+CORRESPONSAVEL (normal)
- Limpeza disco: 45GB liberados no C: (dados duplicados movidos para G:)
- Q39: 59k socios de empresas recebendo BF (nome + 6 digitos CPF, empresas ativas, exclui associacoes)
- etl/15_normalizar.py reescrito: por statement (idempotente), colunas + indices
- etl/run_queries.py criado: exporta 42 queries para CSV em resultados/
- TSE candidatos + bens: 2.1M + 4M (2020/2022/2024)

### 2026-03-21 (sessao 2)
- Dados orphaned recuperados: _stg_estab +4.7M, _stg_pgfn +12.1M
- Fix regex f-string: \d{2} → \d{{2}} em 07_pgfn, 06_cpgf, 05_emendas
- Recarga PGFN (39.9M) e emenda_convenio (80k) com datas corrigidas
- ETL Bolsa Familia (20.9M), TSE Prestacao de Contas (receitas 2.3M + despesas 6M)
- Estabelecimentos: 69.8M (inclui staging recuperada)
- Queries de fraude TSE (Q33-Q37) e Bolsa Familia (Q38-Q42)

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
