# TODO - govbr-cruza-dados

## Pendente

### Deploy Azure
16. [ ] **Deploy completo**: Benchmark PNCP com requests.Session rodando na VM. Após confirmar velocidade, re-disparar deploy com `gh workflow run deploy.yml -f etl_phase=all -f clean=true`. Workflow timeout aumentado para 12h.
17. [ ] **Issues #1-#4**: Pendentes execução no banco (Issue #1 tce_pb data_empenho, #3 filtro temporal Q59/Q63, #4 JOINs CPF sem nome). Plano completo em `.claude/plans/twinkling-puzzling-giraffe.md`.

## Estado do banco local
- **~336M registros** em 15+ fontes. DB size: 205 GB. C: 91GB livres.
- Tabelas principais: empresa 66.6M, estabelecimento 69.8M, simples 47M, socio 27M, pgfn_divida 39.9M, tce_pb_servidor 21.7M, bolsa_familia 20.9M, tce_pb_despesa 15.8M, pncp_item 4.71M, pncp_contrato 3.76M
- **MVs OK**: mv_rede_pb 1.68M, mv_servidor_pb_base 353K, mv_servidor_pb_risco 353K, mv_pessoa_pb 205K, mv_empresa_pb 157K, v_risk_score_pb 135K, mv_municipio_pb_risco 224
- mv_empresa_governo 690K rows
- PostgreSQL: `PGPASSWORD=kong1029 "/c/Program Files/PostgreSQL/16/bin/psql.exe" -U postgres -d govbr`
- Dados brutos: G:\govbr-dados-brutos (HDD)
- 93+ queries em queries/*.sql, 28 relatorios em relatorios/

## VM Azure
- IP: 52.162.207.186, user: govbr, SSH key: `C:\Users\lucas\.ssh\azure_vm.txt`
- Disco /data: 403GB disponíveis. OS disk: 30GB (9.5% usado).
- PostgreSQL 16 instalado, data dir em /data/postgresql/16/main
- Tor + torsocks instalados (fallback para 403)
- DB vazio (0 tabelas) — ETL nunca completou
- Dados parciais já baixados: RFB (Empresas0-9, Estabelecimentos0-9, etc.), CPGF 2020-2024, sanções, viagens, TCE-PB, dados PB

## Concluido (resumo)
- Issues #1-#5 resolvidas e validadas (código, não executadas no banco)
- ETL completo local: 15+ fontes, normalizacao, indices
- 7/7 MVs + 2 views criadas
- 28 relatorios escritos e revisados
- 14/14 items de enriquecimento completos (sessão 29)

## Log recente

### 2026-04-04 (sessao 30)
- **Bug PNCP 204 encontrado e corrigido**: API retorna HTTP 204 (No Content) para modalidade/semana sem dados. Código antigo tratava como erro → 5 retries × 60s backoff × ~1650 combinações = **28h desperdiçadas**. Fix: retornar resultado vazio para 204.
- **Python urlopen trava 30s+ em SSL**: curl responde em 1-2s, urlopen trava. Fix: trocado por requests.Session com connection pooling (10 conn, 20 max).
- **Paralelismo**: 3 semanas simultâneas × 4 modalidades por semana = 12 requests paralelos. Estimativa: 2024 inteiro em ~15min (vs horas antes).
- Workflow timeout aumentado: job 720min (12h), ETL step 660min (11h). Removido continue-on-error do ETL step.
- `requests>=2.31` adicionado ao pyproject.toml
- Processo antigo do deploy (PID 175533, rodando 8h) matado na VM
- Benchmark em andamento na VM com requests.Session
- Commits: 451cae2, fed2301, 2697273, 09081dc, 83ab86c, 45a89f1

### 2026-04-04 (sessao 29)
- Q100 série temporal: 22K grupos × semestre, 30 saltos >2× detectados
- SES-PB × JUSTIZ: 247 empresas, R$52M+, R$13.7M multas CLT
- Cartel BA: 3 empresas mesmo endereço, 4.551 contratos 100% BA
- Sobrepreço × fornecedores: PRIME CONSULTORIA 324× R$10.3B. 0 sanções.
- Rede societária × governo: RUDIMAR R$49.2B, LINCOLN THIAGO 3 CEIS
- Deploy Azure: workflow reescrito, Tor fallback. 14/14 TODO completo.
- Commits: 745ee96, 9193d25, cbf81a7, e6af076, 16e1134, 7033552, 5fb0302

### 2026-04-04 (sessao 28)
- 3 relatorios, Q99 fenix nacional, deep dives Sec.Educacao MS e SES-PB

### 2026-04-03 (sessao 27)
- 7 queries pncp_item (Q92-Q98), Q55 fix, achados fracassados

### 2026-04-03 (sessao 26)
- mv_empresa_governo, Q56, 4 relatorios novos
