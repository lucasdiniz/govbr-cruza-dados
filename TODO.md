# TODO - govbr-cruza-dados

## Pendente
- [ ] Rodar `python -m etl.15_normalizar` (normalizar CPF/CNPJ para JOINs)
- [ ] Rodar `python -m etl.16_tse` (candidatos + bens 2020/2022/2024)
- [ ] Recriar views materializadas (`sql/12_views.sql`) apos normalizacao
- [ ] Rodar as 42 queries de fraude e verificar resultados
- [ ] Push para GitHub (repo: github.com/lucasdiniz/govbr-cruza-dados)

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
