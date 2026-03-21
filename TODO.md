# TODO - govbr-cruza-dados

## Pendente
- [EM BACKGROUND] `python -m etl.15_normalizar` — PID 9244, no UPDATE pgfn 40M. Inclui indices. Idempotente (pode retomar)
- [EM BACKGROUND] tmp_run_partial.py (Q01-Q37 + Q41) — PID 12632, salvando CSVs em resultados/. Pulou Q38/Q39/Q40/Q42
- [EM BACKGROUND] tmp_run_q39.py — PID 20960, versão antiga da Q39 (pode matar: taskkill /PID 20960 /F)
- [x] Rodar `python -m etl.16_tse` — tse_candidato: 2.1M, tse_bem_candidato: 4M (2020/2022/2024)
- [ ] Rodar Q38/Q39/Q40/Q42 (dependem de 15_normalizar terminar)
- [ ] Recriar views materializadas (`sql/12_views.sql`) apos normalizacao
- [ ] Push para GitHub (repo: github.com/lucasdiniz/govbr-cruza-dados) — user logou no github
- [ ] Limpar tmp_run_q39.py e tmp_run_partial.py apos uso

## Log

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
