# TODO - govbr-cruza-dados

## Pendente

### Deploy Azure
16. [ ] **Verificar benchmark PNCP e disparar deploy**: Benchmark PNCP 2024 rodando na VM (PID 189716, iniciou 19:13 UTC). Checar: `ssh -i /tmp/azure_vm_key govbr@52.162.207.186 "ls /home/govbr/data/pncp/contratacoes_2024*.json | wc -l"`. Se 2024 completou (~52 JSONs contratacoes + ~52 contratos), disparar deploy: `gh workflow run deploy.yml -f etl_phase=all` (sem clean — dados já existem na VM).
17. [ ] **Issues #1-#4**: Pendentes execução no banco local. Plano detalhado em `.claude/plans/twinkling-puzzling-giraffe.md`.

## Handoff técnico sessão 30

### SSH na VM Azure
```bash
# Preparar key (fazer 1x por sessão)
cp /c/Users/lucas/.ssh/azure_vm.txt /tmp/azure_vm_key && chmod 600 /tmp/azure_vm_key
# Conectar
ssh -i /tmp/azure_vm_key govbr@52.162.207.186
# Na VM: projeto em /home/govbr/govbr-project, venv em venv/, dados em /home/govbr/data
```

### O que foi corrigido no download PNCP (etl/00_download.py)
1. **Bug 204**: `_api_get()` tratava HTTP 204 como erro (5 retries × 60s = 28h desperdiçadas). Fix: retorna `{"data":[], ...}` para 204.
2. **urlopen→requests.Session**: Python urlopen travava 30s+ em SSL. requests.Session com pool (10 conn, 20 max) responde em 1-2s consistente.
3. **Paralelismo 2 níveis**: 3 semanas simultâneas (`PARALLEL_WEEKS=3`) × 4 modalidades/semana (`ThreadPoolExecutor(max_workers=4)` em `_fetch_week_contratacoes`).
4. **Checkpoint por batch**: `_download_one_week_contratacoes` e `_download_one_week_contratos` são thread-safe, salvam JSON individualmente. Checkpoint avança por batch.
5. **Timeout/retries**: API timeout 20s, 3 retries, backoff max 10s.

### Benchmark na VM (resultados parciais)
- **Antes (urlopen + bug 204)**: 1 semana em 9 min → impossível completar
- **Depois (requests + paralelo)**: 3 semanas em 7 min (~2.3 min/semana)
- **Estimativa 2021-2026 (275 semanas)**: ~10h contratações + contratos. Cabe no timeout de 12h.
- **Semanas grandes** (14MB+) são o bottleneck — muitas páginas, paginação sequencial dentro de cada semana

### Workflow deploy (.github/workflows/deploy.yml)
- Job timeout: 720min (12h). ETL step: 660min (11h).
- **Sem continue-on-error** — pipeline falha se download falhar (requisito do usuário)
- `skip_download` input disponível mas NÃO usar — PNCP precisa baixar

### Feedback do usuário (sessão 30)
- **Não é aceitável falhar em baixar parte dos dados** — pipeline deve completar tudo ou falhar
- **Não usar timeout/max_runtime no download** — aumentar timeout do workflow se necessário
- **Não fazer upload manual** — tudo automatizado

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
- PG16 instalado (data dir /data/postgresql/16/main). DB vazio (0 tabelas).
- Tor + torsocks instalados. requests instalado no venv.
- Dados parciais baixados: RFB completo (Empresas0-9, Estabelecimentos0-9, Socios0-9, Simples, etc.), CPGF 2020-2024, sanções (CEIS/CNEP/CEAF), viagens, TCE-PB, dados PB, PGFN, emendas
- PNCP parcial: contratacoes 2021-ago a 2024-jan (~3 semanas), contratos ainda não baixados

## Concluido (resumo)
- Issues #1-#5 resolvidas e validadas (código, não executadas no banco)
- ETL completo local: 15+ fontes, normalizacao, indices
- 7/7 MVs + 2 views criadas. 28 relatorios. 14/14 enriquecimentos.

## Log recente

### 2026-04-04 (sessao 30)
- Bug PNCP 204 + urlopen SSL corrigidos. requests.Session + paralelismo.
- Workflow timeout 12h. Removido continue-on-error.
- Benchmark PNCP na VM: ~2.3 min/semana (7.5x speedup)
- Commits: 451cae2, fed2301, 2697273, 09081dc, 83ab86c, 45a89f1, ccefdb9

### 2026-04-04 (sessao 29)
- Q100 série temporal, cartel BA, JUSTIZ network, sobrepreço fornecedores
- Deploy workflow reescrito. 14/14 TODO completo. Tor fallback.

### 2026-04-04 (sessao 28)
- 3 relatorios, Q99 fenix nacional, deep dives Sec.Educacao MS e SES-PB

### 2026-04-03 (sessao 27)
- 7 queries pncp_item (Q92-Q98), Q55 fix, achados fracassados

### 2026-04-03 (sessao 26)
- mv_empresa_governo, Q56, 4 relatorios novos
