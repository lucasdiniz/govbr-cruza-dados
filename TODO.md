# TODO - govbr-cruza-dados

## Pendente
- [x] Views materializadas completas (`sql/12_views.sql`)
  - [x] mv_empresa_governo: 690k rows, 239MB — 360° empresa × 9 fontes + flags
  - [x] mv_municipio_pb_risco: 223 rows, 104KB — score risco por municipio PB
  - [x] mv_pessoa_pb: 204k rows, 46MB — PFs PB com cross-refs socio/servidor/TSE/BF/CEIS
  - [x] mv_servidor_pb_base: 353k rows, 85MB — servidores municipais dedup (>= 2022)
  - [x] mv_servidor_pb_risco: 353k rows, 102MB — cross-refs (socio/BF/conflito) + risk score
  - [x] mv_empresa_pb: 157k rows, 71MB — empresas ativas em PB (TCE+dados.pb)
  - [x] mv_rede_pb: 1.67M rows, 259MB — grafo conexoes PB (5 tipos aresta)
  - [x] v_risk_score_empresa + v_risk_score_pb: views de risco (instantaneas)
- [x] **Issue #1**: tce_pb_despesa.data_empenho NULL em 97.3% — fix `_DATE_SQL` 3 formatos + `ano_arquivo`
- [x] **Issue #3**: Q59 filtro temporal `d.ano >= LEFT(sv.ano_mes,4)::INT` + Q63 threshold 2022-01
- [x] **Issue #4**: Q10/Q21/Q22/Q29 nome no JOIN CPF + 3 indices compostos (Q32 CPF completo, sem nome)
- [x] **Issue #2**: deploy.yml reescrito (PG16 install, clean step, disk check, CI/CD logic)
  - Deploy automático DESATIVADO até VM pronta (disco 256GB + downloads automatizados)
- [ ] Re-rodar todas queries após ETL tce_pb_despesa terminar (validar fixes Issues #1/#3/#4)
- [x] Automatizar downloads: RFB (auto-detect mês), PGFN (trimestral), emendas, renúncias, BNDES (2 CSVs)
  - PNCP: bulk download via API Consulta (contratacoes dia×modalidade + contratos dia) + itens via download_pncp.py
  - ComprasNet: incluído no repo como data/static/comprasnet.csv.gz (13MB)
  - Holdings: removido do pipeline (redundante com socio WHERE tipo_socio=1)
- [x] Preparar VM Azure: data disk 512GB montado em /data, PG16 instalado, deploy rodando
- [ ] Reativar deploy automático no push (após Full ETL completar na VM)
- [ ] Analisar resultados das 75 queries (764k resultados totais — ver resumo sessao 10)
- [ ] Continuar relatorios de investigacao (foco Paraiba)
- [ ] ETL pncp_itens: rodando em background (3M arquivos, fix catalogo dict→string)
- [ ] Queries superfaturamento Q45-Q58 (Q43/Q44/Q51/Q53 ja implementadas)

## Estado do banco (~336M registros)
- empresa: 66.6M, estabelecimento: 69.8M, simples: 47M, socio: 27M
- tce_pb_servidor: 21.7M, pgfn_divida: 39.9M, bolsa_familia: 20.9M, tce_pb_despesa: 15.8M
- tse_despesa: 6M, tse_bem_candidato: 4M, pb_pagamento: 3.87M, viagem: 3.9M, pncp_contrato: 3.7M
- tse_candidato: 2.1M, tse_receita_candidato: 2.3M, pb_empenho: 1.67M, tce_pb_receita: 1.2M, emenda_favorecido: 1.2M
- cpgf_transacao: 645k, tce_pb_licitacao: 310k, pb_saude: 215k, bndes_contrato: ~100k
- pb_contrato: 15.6k, pb_convenio: 7.8k
- PostgreSQL: localhost, user=govbr, db=govbr
- Dados brutos: G:\govbr-dados-brutos (DATA_DIR no .env, HDD)
- PostgreSQL data: disco C: (SSD), ~45GB livres
- GitHub: https://github.com/lucasdiniz/govbr-cruza-dados (public)
- MVs criadas: mv_empresa_governo (239MB), mv_municipio_pb_risco (104KB), mv_pessoa_pb (46MB), mv_servidor_pb_base (85MB), mv_servidor_pb_risco (102MB), mv_empresa_pb (71MB), mv_rede_pb (259MB)
- Views risco: v_risk_score_empresa, v_risk_score_pb
- Indices compostos: idx_socio_norm_nome (1040MB), idx_bf_cpf_nome (910MB)

## Normalizacao (etl.15_normalizar) — Fases 1-8 COMPLETAS
Fases 1-8: todas colunas desnormalizadas + ~43 indices.
- [x] pgfn_divida.cpf_cnpj_norm — 39.9M rows (CPF 6dig + CNPJ 14dig misturados)
- [x] socio.cpf_cnpj_norm (6 digitos) — 27M rows
- [x] bolsa_familia.cpf_digitos (6 digitos) — 21M rows
- [x] siape_cadastro.cpf_digitos, cpgf_transacao.cpf_portador_digitos, ceaf_expulsao.cpf_cnpj_norm, viagem.cpf_viajante_digitos — OK
- [x] pncp_contrato.cnpj_basico_fornecedor (8 digitos) — OK
- [x] emenda_favorecido.cnpj_basico_favorecido — somente CNPJ puro (regex ^[0-9]+$), PF/outros = NULL
- [x] ceis_sancao.cpf_cnpj_norm (CPF completo 11 dig / CNPJ 14 dig) + cpf_digitos_6 (6 centrais) — 9.032 CPFs
- [x] cnep_sancao.cpf_cnpj_norm (idem) + cpf_digitos_6 — 32 CPFs
- [x] acordo_leniencia.cnpj_norm — OK
- [x] Todos os indices das fases 2-4 criados + idx_ceis/cnep_cpf_digitos_6
- [x] Fases 5-6: TCE-PB cnpj_basico, cpf_digitos_6, nome_upper, ano + 9 indices CONCURRENTLY (completa)
- [x] Fases 7-8: dados.pb.gov.br cnpj_basico (5 tabelas), cpf_digitos_6, nome_upper (pb_pagamento) + 7 indices CONCURRENTLY

## Queries — 75 implementadas (764k resultados)
Queries Q01-Q91 migradas para colunas normalizadas indexadas. Status:
- 17 queries otimizadas: Q02,Q06,Q10,Q16,Q18,Q21,Q22,Q24,Q25,Q26,Q27,Q28,Q29,Q32,Q33,Q37,Q39
- 15+ queries com UF/municipio: Q03,Q04,Q06,Q07,Q10,Q11,Q15,Q18,Q21,Q22,Q24,Q25,Q26,Q27,Q28,Q33,Q36,Q37
- Q19 reescrita com limites legais dinamicos por decreto (2018-2026), faixa 60-100% + R$700-999 fixo, granularidade dia+mes
- Q02 otimizada com CTE (evita self-join 27M x 27M), Q06 otimizada sem JOIN intermediario
- Queries pesadas precisam SET work_mem = '512MB' (Q02, Q06, Q10, Q15)
- run_queries.py: `python -m etl.run_queries` (todas) ou `--query Q19` (especifica)
- NOVAS queries/fraude_tce_pb.sql: Q59-Q68, Q70-Q72, Q74, Q77 (14 queries TCE-PB municipais)
- NOVAS queries/fraude_dados_pb.sql: Q78-Q91 (14 queries dados.pb estaduais)
- Total: 75 queries implementadas, 764k resultados. Destaques PB: Q59 32k servidores-socios, Q60 9.3k sem licitacao, Q83 500 empresas dominantes

## Log

### 2026-03-22 (sessao 6)
- Limpeza: removidos tmp_run_q39.py, tmp_run_partial.py, tmp_analysis.sql
- work_mem configurado permanente: 512MB no postgresql.conf + pg_reload_conf(). Queries pesadas nao precisam mais de SET manual
- Planejamento superfaturamento: 16 novas queries propostas (Q43-Q58), melhorias Q02 (filtro CNAE/NJ falsos positivos)
- Mapeamento API PNCP: endpoints descobertos e testados:
  - Itens: GET /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens
  - Resultados: GET /api/pncp/v1/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{num}/resultados
  - API publica nao expoe propostas/concorrentes perdedores, apenas vencedores
- Criado etl/download_pncp.py: download paralelo de itens PNCP via API REST (checkpoint, retomavel, --workers)
- Atualizado etl/00_download.py com referencia ao novo script
- Download itens PNCP iniciado: ~3M contratacoes, 30 workers, ~18h estimado, destino G:\govbr-dados-brutos\pncp_itens
- Criado sql/03b_schema_pncp_itens.sql: tabela pncp_item (8 indices incluindo trigram para busca textual)
- Criado etl/04b_pncp_itens.py: ETL itens JSON → PostgreSQL
- Pendente: normalizar pncp_item.unidade_medida (mapear variacoes tipo "UNIDADE (UN)"/"UND"/"UN" → padrao unico) e descricao (remover HTML tags, UPPER). Precisa amostrar unidades primeiro
- Implementadas 4 novas queries de superfaturamento: Q43 (7.080), Q44 (6.211), Q51 (2.171), Q53 (rodando)
- Q02 melhorada: filtro CNAE utilidades publicas (35xx-37xx) removeu ~3k falsos positivos (230k → de 233k)
- Decidido NAO excluir fundacoes de apoio (NJ 3034/3069) da Q02 — podem ser usadas em esquemas reais
- Download PNCP itens em andamento: ~106k de 3M contratacoes processadas (~3.5%)

### 2026-03-22 (sessao 7)
- Nova fonte: TCE-PB dados consolidados (despesas, servidores, licitacoes, receitas) 2018-2026
- URL pattern: https://download.tce.pb.gov.br/dados-abertos/dados-consolidados/{cat}/{cat}-{ano}.zip
- Download completo: 36 arquivos, ~2GB, adicionado download_tce_pb() ao 00_download.py
- Schema criado: sql/19_schema_tce_pb.sql (4 tabelas, campos TEXT para descritivos longos)
- ETL criado: etl/19_tce_pb.py (--only, --anos, --no-schema) — parsing CSV br (;, UTF-8 BOM, virgula decimal)
- Dados carregados: despesa 15.8M, servidor 21.7M, licitacao 310k, receita 1.2M = 39M registros
- Normalizacao adicionada ao 15_normalizar.py (Fases 5-6): cnpj_basico, cpf_digitos_6, nome_upper, ano + 9 indices
- Normalizacao TCE-PB rodando em background (UPDATE 15.8M cnpj_basico + 21.7M cpf/nome + indices)
- Q53 concluida: 14.020 resultados (capital social minimo ganhando contratos alto valor)
- Propostas 16 queries TCE-PB: Q59-Q68 + Q70-Q77 (priorizadas: Q70 empresa inativa, Q71 mesmo endereco, Q72 doador-prefeito, Q74 servidor+BF, Q77 fracionamento, Q59 servidor-socio)
- Investigado dados.pb.gov.br: encontrados datasets pagamento (estadual, CPF/CNPJ), liquidacao, convenios. App JSF dificulta discovery
- Investigado SAGRES API: requer token do TCE (email suportesagres@tce.pb.gov.br), valor marginal vs CSVs ja baixados
- Commit ae07d0a: pipeline TCE-PB completa

### 2026-03-22 (sessao 8)
- Investigacao aprofundada dados.pb.gov.br: discovery completo via JSF AJAX (40+ datasets mapeados)
- Tecnica: POST com datasetZip_input={ID} + CSRF token para extrair nomes API reais
- Pipeline completo criado: sql/20_schema_dados_pb.sql + etl/20_dados_pb.py + download em 00_download.py + normalizacao Fases 7-8
- Download completo: 262 arquivos, 1.6GB em G:\govbr-dados-brutos\dados_pb\
- Carga completa: pb_pagamento 3.87M, pb_empenho 1.67M, pb_contrato 15.6k, pb_saude 215k, pb_convenio 7.8k = 5.78M registros
- Fix encoding (errors='replace'), fix VARCHAR truncation (saude numero_documento, empenho schema inteiro)
- Normalizacao TCE-PB (Fases 5-6) completou: cnpj_basico 33min, cpf_digitos_6 23min, nome_upper 30min + 9 indices 16min
- 14 novas queries propostas (Q78-Q91) cruzando dados.pb × TCE-PB × fontes federais
- Diferencial chave: pb_pagamento tem CPF COMPLETO (match exato com socio, TSE, CEIS, PGFN)
- Commit dd88b45: pipeline dados.pb.gov.br completo

### 2026-03-22 (sessao 9)
- Normalizacao Fases 7-8 (dados.pb.gov.br) executada e concluida: cnpj_basico 5 tabelas, cpf_digitos_6 + nome_upper pb_pagamento + 7 indices CONCURRENTLY
- Implementadas 14 queries TCE-PB municipais (queries/fraude_tce_pb.sql): Q59-Q68, Q70-Q72, Q74, Q77
  - Destaques: Q59 servidor-socio-fornecedor, Q70 empresa inativa, Q71 mesmo endereco, Q72 doador-prefeito, Q74 servidor+BF
- Implementadas 14 queries dados.pb estaduais (queries/fraude_dados_pb.sql): Q78-Q91
  - CPF completo: Q78 auto-contratacao, Q79 candidato TSE, Q80 BF, Q81 sancionado, Q82 servidor SIAPE
  - CNPJ cross: Q83 empresa dominante estado+municipio, Q84 inativa, Q85 PGFN, Q86 saude, Q87 socio=servidor
  - Cross fontes: Q88 duplo vinculo, Q89 convenio, Q90 fracionamento, Q91 splitting
- Download PNCP itens: ~1.1M/3M (~37%)
- Total queries implementadas: 42 + 28 novas = 70
- Planejamento views materializadas: 6 MVs + 2 views de risco (plano completo em .claude/plans/)
  - mv_empresa_governo (360° empresa × 10 fontes), mv_pessoa_pb (CPF completo × 6 fontes), mv_municipio_pb_risco (score município), mv_servidor_pb_risco (servidor+flags), mv_empresa_pb (foco PB), mv_rede_pb (grafo conexões)
  - v_risk_score_empresa + v_risk_score_pb (ranking unificado)
- 70 queries rodando em background (run_queries.py)
- Commit 61b194f: 28 novas queries

### 2026-03-23 (sessao 10)
- Corrigido dt_situacao_cadastral → dt_situacao em Q70 e Q84 (coluna nao existia no estabelecimento)
- Corrigido Q64: ORDER BY ABS(diferenca) → ORDER BY ABS(SUM(...)) (alias nao valido em ORDER com GROUP BY)
- Corrigido Q72: tse_receita → tse_receita_candidato, colunas nr_cpf_cnpj_doador → cpf_cnpj_doador, sg_ue → nm_ue
- Corrigido Q78: JOIN socio por cpf_cnpj_norm (11dig) impossivel (socio tem 6dig mascarado) → cpf_digitos_6 + nome_upper
- Corrigido Q79: tc.nr_cpf_candidato → tc.cpf (coluna real em tse_candidato)
- Corrigido Q83: LATERAL JOINs sobre 66M empresas → CTEs pre-agregadas; pb_pagamento (99% PF) → pb_empenho (666k CNPJs)
- Descoberta: pb_pagamento tem 3.67M CPFs numericos 11dig + 188k mascarados + 276 CNPJs. Quase todo PF!
- Cancelada query orphaned (PID 6796, 7h rodando) da sessao anterior
- Todas 75 queries executadas com sucesso. 764k resultados totais
- Destaques novas queries PB:
  - Q59: 32.094 servidores municipais socios de fornecedoras (MAIOR achado!)
  - Q60: 9.322 fornecedores sem licitacao em 5+ municipios
  - Q62: 1.670 cartel estadual (mesmo fornecedor 10+ municipios)
  - Q70: 1.328 empresas inativas recebendo pagamento municipal
  - Q84: 760 contratadas estaduais inativas
  - Q65: 514 sancionados CEIS recebendo de municipios
  - Q83: 500 empresas dominantes estado+municipio
  - Q87: 500 socios de contratada estadual = servidor municipal
  - Q86: 108 fornecedores saude sancionados
- Queries com 0 resultados: Q64, Q66, Q72, Q78, Q80-82, Q85 — threshold alto ou dados nao cruzam
- Limpeza TODO/README: removidos itens stale, marcados Q43/Q44/Q51/Q53 como feitos, corrigido tse_receita→tse_receita_candidato, ~40GB→~100GB dados (186GB DB)
- Download PNCP itens retomado (~91%, 2.71M/2.99M contratacoes)

### 2026-03-23 (sessao 11)
- sql/12_views.sql reescrito: 7 MVs + 2 views de risco (split servidor em base+risco para evitar re-scan 21M rows)
- Nomes corretos de tabelas: ceis_sancao (nao sancao_ceis), cnep_sancao (nao sancao_cnep), pncp_contratacao (nao pncp_licitacao), holding nao existe
- tce_pb_despesa.mes formato "12-Dezembro" (nao integer) — usar LIKE '12%'
- Fixes durante criacao: COUNT(DISTINCT) OVER → subquery, LATERAL JOIN tse_candidato → CTE DISTINCT ON (OOM), EXISTS full scan 27M → JOIN from small side
- MVs criadas com sucesso:
  - mv_empresa_governo: 690,734 rows (209MB) — 9 fontes governo + flags inativa/CEIS/CNEP/PGFN
  - mv_municipio_pb_risco: 223 rows (64KB) — score 0-100 por municipio PB
  - mv_pessoa_pb: 204,828 rows (36MB) — PFs PB cross-ref socio/servidor/SIAPE/TSE/BF/CEIS
  - mv_servidor_pb_base: 353,177 rows (66MB) — servidores dedup (cpf_digitos_6+nome_upper)
- mv_servidor_pb_risco NAO concluida: JOINs com socio(27M) e bolsa_familia(21M) lentos sem indice composto em (cpf_digitos_6, nome_upper)
- Diagnostico: indices existentes sao single-column (idx_socio_norm, idx_bf_cpf_digitos). PostgreSQL faz index lookup no primeiro campo mas precisa ler cada row da tabela para filtrar nome. Indice composto eliminaria o table fetch
- Download PNCP itens: 99.98% (2,987,291/2,987,788) — praticamente completo
- Disco C: (SSD, PostgreSQL): 47GB livres. Indices compostos estimados em ~2-3.5GB

### 2026-03-24 (sessao 12)
- Indices compostos criados: idx_socio_norm_nome (1040MB, socio 27M rows), idx_bf_cpf_nome (910MB, bolsa_familia 21M rows) — adicionados a sql/11_indices.sql
- mv_servidor_pb_risco: CTE-unica timeout (BOOL_OR(EXISTS) correlated subquery: 26s→10min+). Fix: abordagem stepwise com tabelas regulares (_tmp_socio_empresas, _tmp_fornecedor_gov, _tmp_conflito, _tmp_bf, _tmp_duplo) — resultado: 353k rows, 102MB, 2809 conflitos, 25883 BF, 32545 com risco
- mv_empresa_pb: 157k rows, 71MB — criada com sucesso (Layer 2)
- mv_rede_pb: UNION ALL de 5 subqueries pesadas causa timeout 30min. Fix: stepwise com tabelas por tipo de aresta (_tmp_rede_*) — resultado: 1.67M rows, 259MB
- v_risk_score_empresa + v_risk_score_pb criadas (Layer 3, instantaneas)
- sql/12_views.sql reescrito com abordagem stepwise para mv_servidor_pb_risco e mv_rede_pb
- etl/04b_pncp_itens.py reescrito: thread pool (8 workers) + COPY + os.scandir (100 it/s vs 20 it/s)
- sql/03b_schema_pncp_itens.sql: numero_item SMALLINT→INTEGER (overflow fix)
- etl/run_all.py: adicionadas fases 14-18 (TCE-PB, dados.pb, PNCP itens, normalizacao, views)
- etl/21_views.py: novo executor de views por statement com progress
- etl/config.py: DATA_DIR fallback alterado para /data/raw-data (Linux/Azure friendly)
- .github/workflows/deploy.yml: CI/CD skeleton (precisa secrets VM_HOST, VM_SSH_KEY)
- Deploy Azure pausado: B4ms SkuNotAvailable em eastus e brazilsouth
- Diagnostico zombie processes: ls/du em diretorio 3M arquivos pncp_itens (HDD) causava 300-600 IOPS

### 2026-03-27 (sessao 13)
- sql/12_views.sql reescrito com abordagem stepwise confirmada (commit 99c2d75)
- TODO.md atualizado com changelog sessao 12 completo
- etl/04b_pncp_itens.py fix: catalogo era dict JSON, agora extrai campo nome (commit 288fcc5)
- PNCP items ETL rodando em background (~3M arquivos, HDD)
- Investigacao 4 issues GitHub:
  - Issue #1: ROOT CAUSE ENCONTRADO — `_DATE_SQL` regex espera DD/MM/YYYY mas CSVs 2018-2025 usam ISO YYYY-MM-DD. Resultado: 97.3% (15.4M/15.8M) data_empenho NULL. So 2026 (434k) tem data.
  - Issue #2: VM 52.162.207.186 disco 100% cheio (30GB), PostgreSQL nao instalado. Deploy falhou na Fase 1 (Connection refused)
  - Issue #3: Q59 falso positivo (prefeita Baraunas) — depende Issue #1 para filtro temporal
  - Issue #4: 5 queries (Q10,Q21,Q22,Q29,Q32) sem nome no JOIN CPF
- Plano aprovado: Issues #1→#4→#3→#2. Disco VM→256GB. Automatizar 8 fontes download.
- deploy.yml atualizado pelo user (commit c417ce4): etl_phase input, PostgreSQL setup placeholder

### 2026-03-27 (sessao 14)
- Issue #1 FIX: `_DATE_SQL` reescrito para 3 formatos (ISO+timestamp, ISO date, DD/MM/YYYY)
  - etl/19_tce_pb.py: regex `^\d{4}-\d{2}-\d{2}` → LEFT(10) + TO_DATE, fallback DD/MM/YYYY
  - sql/19_schema_tce_pb.sql: adicionado `ano_arquivo SMALLINT` (ano do filename como fallback)
  - etl/15_normalizar.py: `ano = COALESCE(EXTRACT(YEAR FROM data_empenho), ano_arquivo)`
  - ETL tce_pb_despesa re-rodando (TRUNCATE + reload 9 anos)
- Issue #4 FIX: nome adicionado a 4 queries (Q10, Q21, Q22, Q29). Q32 mantido sem nome (CEAF CPF completo)
  - sql/11_indices.sql + etl/15_normalizar.py: 3 indices compostos (cpgf, siape, viagem) cpf+UPPER(nome)
- Issue #3 FIX: Q59 `AND d.ano >= LEFT(sv.ano_mes, 4)::INT`, Q63 threshold relaxado 2024→2022
- Issue #2: deploy.yml reescrito completo
  - PostgreSQL 16 install step (user, db, pg_trgm, tuning 16GB RAM)
  - Clean step (workflow_dispatch com `clean: true`)
  - Disk check + warning
  - CI/CD: push→SQL only, manual dispatch→ETL phase, first run→full ETL
  - Deploy automático DESATIVADO até VM pronta
- etl/00_download.py: hardcoded `range(2020, 2027)` → dynamic `CURRENT_YEAR`
- etl/19_tce_pb.py: `ANOS = range(2018, 2027)` → dynamic
- etl/00_download.py: 6 fontes automatizadas (RFB auto-detect mês, PGFN trimestral, emendas, renúncias, BNDES 2 CSVs)
  - URLs testadas: PGFN OK, Emendas OK, BNDES OK (1.1GB), Renúncias OK (`/renuncias/` não `/renuncias-fiscais/`)
  - RFB: servidor timeout (normal, precisa retry longo). PNCP: sem bulk, API only
  - Holdings/ComprasNet: sem fonte pública — arquivos estáticos
- deploy.yml: adicionado step "Run queries" (`python -m etl.run_queries`)
- ETL tce_pb_despesa re-rodando (schema recreou todas 4 tabelas — servidores/licitacoes/receitas precisam reload)

### 2026-03-28 (sessao 15)
- ETL local tce_pb: despesas 15.8M OK + servidores 21.7M + licitacoes 310k + receitas 1.2M recarregados
- Issue #1 VALIDADO: data_empenho 100% populado em todos os anos 2018-2026 (antes 2.7%)
- Normalizacao 15_normalizar rodando (Fases 1-8)
- VM Azure: data disk 512GB descoberto e montado em /data (era desmontado)
  - OS disk liberado de 99%→8% (dados movidos para /data/govbr)
  - Symlink /home/govbr/data → /data/govbr
  - PG data dir configurado para /data/postgresql (deploy.yml)
- Deploy fixes:
  - safe_to_date() nao existia no repo (so no banco local) → adicionada a sql/00_extensions.sql
  - YAML nested heredoc CONF → echo -e
  - python -c indentacao → extraido para etl/verify.py
  - Views step sem || true → adicionado
  - CPGF baixava meses futuros (403) → para no mes atual
  - SIAPE mes unico → tenta 3 meses (atraso publicacao)
  - Sancoes data exata → tenta 7 dias retroativos
  - BNDES URL 404 (dataset antigo removido) → 2 novos CSVs (nao-automaticas 19MB + indiretas-automaticas 1.1GB)
  - DB_PASSWORD secret adicionado no GitHub
- Deploy rodando: run 23674360290 (clean=true, etl_phase=all) — First run Full ETL em progresso
- Commits: 379da10, e6dc07f, fc23d5e, 15ca486, 7998b0e

#### Avaliacao relatorios (gerados pelo Gemini)
20 relatorios em relatorios/ avaliados. Problemas globais:
- **Linguagem acusatoria**: quase todos usam "fraude comprovada", "mafia", "peculato" — excede o que dados permitem
- **Encoding UTF-8 quebrado**: secoes "Fontes e Referencias" duplicadas com caracteres garbled
- **"Deteccao precoce" infalsificavel**: ausencia de investigacao ≠ prova de que sistema detectou antes

Relatorios mais problematicos:
1. **conflito_cartao_corporativo** — CRITICO. Baseado em Q10 PRE-FIX (CPF 6dig sem nome). Resultados provavelmente falsos positivos. DEVE ser regenerado.
2. **cartel_combustiveis_pb** — ALTO RISCO. Pessoa nomeada como "Paciente Zero de mafia" baseado so em estrutura societaria. Redes de postos usam 1 CNPJ/ponto (normal). Zero evidencia de co-participacao em licitacao.
3. **smart_smurfing_cpgf** (secao ABIN) — ALTO RISCO. Acusa agencias de inteligencia sem considerar gastos sub-limite legitimos por razoes operacionais.
4. **risk_score_elite_politica_pb** (Barauna) — Report identifica como falso positivo mas mantem em contexto difamatorio.
5. **fazenda_laranjas_mato_grosso_pb** — Declara "roubo de identidade"/"quadrilha" sem evidencia alem do padrao de dados.

Relatorios solidos: falsos_positivos_pb (modelo auto-critico), megafraudes_sertao_pb (corroborado TCU/MPPB), cartel_equipamentos_medicos_jp (precedentes TCE-BA/RN), empresas_inativas_pb (check binario CNPJ), smart_smurfing_cpgf (exceto ABIN)

Recomendacoes:
- [ ] Regenerar relatorios baseados em Q10/Q21/Q22/Q29 apos re-rodar queries com fix nome
- [ ] Adicionar disclaimer padrao: "Analise identifica anomalias estatisticas. Nenhuma conclusao sobre responsabilidade criminal."
- [ ] Corrigir encoding UTF-8 nas secoes duplicadas
- [ ] Reclassificar cartel_combustiveis de "fraude" para "padrao requer analise licitacoes especificas"
- [ ] Remover/caveatar secao ABIN/GSI do relatorio CPGF smurfing

### 2026-03-28 (sessao 16)
- Diagnosticado deploy run 23674360290: RFB timeout, ComprasNet VARCHAR crash, run_all raise parava todo ETL
- **ComprasNet VARCHAR fix**: sql/09_schema_complementar.sql cnpj/fornecedor_cnpj_cpf VARCHAR(14)→VARCHAR(20) (CSVs tem formato 12.345.678/0001-90)
- **run_all.py error handling**: removido `raise` que parava todas fases — agora coleta erros e continua, sys.exit(1) no final com resumo
- **deploy.yml double-execution fix**: `etl_phase=all` triggava "First run" E "Run ETL from phase" — adicionado `inputs.etl_phase != 'all'` na condicao
- **deploy.yml first-run**: adicionado `|| true` para `.initialized` ser criado mesmo com erros parciais
- **RFB download reescrito**: dadosabertos.rfb.gov.br morto → Nextcloud WebDAV em arquivos.receitafederal.gov.br
  - Novo `_download_rfb_webdav()` com Basic Auth (token YggdBLfdninEJX9), forçando IPv4 (IPv6 timeout)
  - Auto-detect mes: tenta mes atual ate 3 anteriores via Cnaes.zip (menor arquivo)
- **CPGF/dados_pb future month fix**: skip meses futuros (`current_ym` check)
- **SIAPE**: tenta mes atual + 2 anteriores (atraso publicacao)
- **Sancoes**: tenta hoje + 7 dias retroativos (atraso publicacao)
- **User-Agent** adicionado a todos urlopen (algumas APIs bloqueiam Python default)

### 2026-03-28 (sessao 17+18)
- **PNCP bulk download**: via API Consulta (`/api/consulta/v1/`)
  - BUGFIX: `tamanhoPagina=500` causava 400 na API contratacoes (max=50). Contratos aceita 500.
  - Otimizado: intervalos semanais em vez de diarios (7x menos chamadas de date range)
  - Contratacoes: semana × 13 modalidades, 50/pagina, salva em DATA_DIR/pncp/contratacoes_YYYYMMDD_YYYYMMDD.json
  - Contratos: semana, 500/pagina, salva em DATA_DIR/pncp_contratos/contratos_YYYYMMDD_YYYYMMDD.json
  - Checkpoint em _checkpoint.json (retomavel), skip existing files
  - Range: 2021→ano atual (PNCP existe desde 2021)
  - 04_pncp.py: exclui _checkpoint.json do glob loader
- **_unzip fix**: deleta zips corrompidos para permitir re-download (RFB tinha HTMLs salvos como .zip)
- **pncp_item.unidade_medida**: VARCHAR(100)→VARCHAR(500) (campo contem descricoes longas)
- **Diagnostico deploy run 23675652803**:
  - PNCP 400s: page size 500→50 (fixed)
  - RFB "invalid zip": corrupt files from previous run (fixed by _unzip delete)
  - CPGF 202511/202603: 403 normal (meses nao publicados)
  - SIAPE 202603: 403 (tenta 202602 que funciona)
  - Sancoes 20260328: 403 (fallback para 20260327 funciona)
  - PGFN Q1/2026: 404 (nao publicado, fallback para Q4/2025)
  - ETL nunca passou de Fase 0 (downloads): PNCP travou 5h em 400s
- **PostgreSQL local**: crashou durante ALTER, recuperado via pg_ctl restart + kill psql zombies
- **TCE-PB verificado**: ano 2018-2026 totalmente preenchido (15.8M rows)
- **Normalizacao**: completou com sucesso (fases 1-8 + TCE-PB + dados.pb)

### Handoff proxima sessao (sessao 19)
- Git: commits ate e4cc52f, pushed to main
- DB local: OK, PostgreSQL rodando, 61 tabelas, pncp_item.unidade_medida alargado
  - Pendente: rodar `python -m etl.run_queries` para validar fixes Issues #1/#3/#4
  - Pendente: re-rodar `python -m etl.04b_pncp_itens` (crashou em 550k/3M por unidade_medida, agora VARCHAR(500))
- VM Azure: re-triggar deploy com `gh workflow run deploy.yml -f etl_phase=all -f clean=true`
  - PNCP download inicial sera lento (5 anos × 52 semanas × 13 mod), mas checkpoint salva progresso entre deploys
- Relatorios: 5 problematicos identificados, recomendacoes de fix na secao "Avaliacao relatorios"
- Pendente: regenerar relatorios afetados por fix Q10/Q21/Q22/Q29

### 2026-03-22 (sessao 5)
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
- PGFN normalizacao concluida: 39.9M rows em ~6h06min (22012s). 100% com cpf_cnpj_norm
- Queries Q06/Q24/Q37 atualizadas para usar colunas normalizadas + UF/municipio
- Commit + push: 658cc8a
- 42 queries executadas: 36 OK, 6 falharam (Q02/Q06 disco cheio, Q13/Q17 alias, Q36 coluna, Q38 coluna)
- Fix Q38: remuneracao_basica → remuneracao_basica_bruta
- Fix Q13/Q17: alias no ORDER BY → expressao completa
- Fix Q36: tipo_sancao/dt_fim_sancao → categoria_sancao/dt_final_sancao
- Fix Q02: otimizada com CTE socios_fornecedores (filtra antes do self-join). 233k resultados em 204s
- Fix Q06: eliminado JOIN via socio (causava 236B rows estimados). Agrega por cnpj_basico separado. 31k resultados em 10s
- work_mem = 512MB necessario para Q02/Q06 (default 4MB causa temp files >24GB)
- Q19 reescrita com limites legais dinamicos por decreto:
  - Pequeno vulto: R$800 (2018) → R$880 (Decreto 9.412/18) → R$10k (Lei 14.133/21) → R$13.098 (Decreto 12.807/25)
  - Dispensa: R$17.6k → R$50k → R$65.492
  - Faixa 60-100% do limite vigente na data da transacao + faixa fixa R$700-999
  - Granularidade dia (>=3 transacoes) e mes (>=2 transacoes) por portador+favorecido
  - 12.478 resultados: 11.183 abaixo_1k, 1.285 pronto_pgto, 10 dispensa
- Re-executadas 6 queries corrigidas: 42/42 OK
- Commit + push: 777e2b8
- Licao: psql no bash do Windows tem problemas com encoding UTF-8 (acentos). Usar SET client_encoding TO 'WIN1252' ou evitar strings com acento em queries via bash

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

## Superfaturamento em licitacoes (foco municipal/estadual)
- [~] Download itens PNCP via API (~91% completo, 2.71M/2.99M contratacoes) — G:\govbr-dados-brutos\pncp_itens
- [ ] ETL itens PNCP: schema pncp_item (sql/03b_schema_pncp_itens.sql) + etl/04b_pncp_itens.py (ja criados, aguardando download)
- [ ] Download propostas/resultados PNCP via API — API nao expoe propostas/perdedores, apenas vencedores
- [ ] Queries item-nivel (apos ETL itens): comparacao preco unitario entre municipios, desvio da mediana por item
- [ ] Queries propostas (dados limitados pela API): licitacao dirigida, cover bidding, cartel rotativo

## Queries pendentes (Q45-Q58)
### Superfaturamento / Sobrepreco
- [x] Q43: Sobrepreco direto — valor_homologado >> valor_estimado (7.496 resultados)
- [x] Q44: Aditivos suspeitos — valor_global >> valor_inicial (7.766 resultados)
- [ ] Q45: Fracionamento de licitacao — mesmo orgao+objeto fragmentado em multiplos contratos abaixo do teto de dispensa
### Padroes temporais
- [ ] Q46: Queima de orcamento — contratos concentrados em nov-dez (final do exercicio fiscal)
- [ ] Q47: Contratos assinados em finais de semana/feriados (urgencia fabricada)
- [ ] Q48: Pico de contratos pre-eleicao no municipio do candidato
### Padroes geograficos
- [ ] Q49: Fornecedor de outro estado ganhando contrato municipal
- [ ] Q50: Multiplos fornecedores do mesmo endereco ganhando contratos no mesmo orgao
### Manipulacao de modalidade
- [x] Q51: Orgao com proporcao anormal de dispensas vs licitacoes competitivas (2.171 resultados)
- [ ] Q52: Mesmo orgao+objeto fragmentado em contratos abaixo do teto (consolidar com Q45)
### Perfil do fornecedor
- [x] Q53: Capital social minimo ganhando contratos de alto valor (17.234 resultados)
- [ ] Q54: CNAE incompativel com objeto do contrato
- [ ] Q55: Empresa fenix — criada recentemente + socio de empresa sancionada CEIS/CNEP
### Conexoes politicas (aprofundamento)
- [ ] Q56: Doador de campanha ganha contrato no municipio do candidato eleito
- [ ] Q57: Ciclo emenda → empresa → doacao TSE de volta ao parlamentar
### Rede societaria
- [ ] Q58: Multiplos fornecedores com mesmo endereco comercial

## TCE-PB — Dados Consolidados (nova fonte)
Fonte: https://dados-abertos.tce.pb.gov.br/dados-consolidados
URL: https://download.tce.pb.gov.br/dados-abertos/dados-consolidados/{cat}/{cat}-{ano}.zip
Categorias: despesas, servidores, licitacoes, receitas (2018-2026)
Total: ~2GB comprimido, 237 municipios PB

### Download
- [x] Download TCE-PB: `python -m etl.00_download --only tce_pb` (36 arquivos, ~2GB, 4 categorias × 9 anos)
- [x] Verificar integridade: dados carregados e queries executadas com sucesso

### Schema + ETL
- [x] Schema tce_pb_despesa, tce_pb_servidor, tce_pb_licitacao, tce_pb_receita (sql/19_schema_tce_pb.sql)
- [x] ETL despesas: 15.8M registros (2018-2026)
- [x] ETL servidores: 21.7M registros (2018-2026)
- [x] ETL licitacoes: 310k registros (2018-2026)
- [x] ETL receitas: 1.2M registros (2018-2026)
- [x] Formato: CSV ; separador, UTF-8 BOM, virgula decimal. ETL: etl/19_tce_pb.py

### Normalizacao — COMPLETA (Fases 5-6, ~1.5h)
- [x] tce_pb_despesa.cnpj_basico (15.8M, 33min) + ano (1.7min)
- [x] tce_pb_servidor.cpf_digitos_6 (21.7M, 23min) + nome_upper (30min)
- [x] tce_pb_licitacao.cnpj_basico_proponente + cpf_digitos_proponente (310k, <1min)
- [x] 9 indices CONCURRENTLY criados (~16min total)

### Queries possiveis (Q59-Q68) — IMPLEMENTADAS (queries/fraude_tce_pb.sql)
- [x] Q59: Servidor municipal que eh socio de empresa fornecedora do mesmo municipio
- [x] Q60: Fornecedor recebendo pagamentos "Sem Licitacao" em multiplos municipios PB
- [x] Q61: Divergencia empenhado vs pago — empenhos com valor_pago muito menor que empenhado
- [x] Q62: Mesmo fornecedor ganhando licitacao em muitos municipios (cartel estadual)
- [x] Q63: Servidor municipal com salario alto + socio de empresa (conflito de interesses)
- [x] Q64: Cruzamento tce_pb_despesa × pncp_contrato — verificar se valores batem
- [x] Q65: Fornecedor sancionado (CEIS/CNEP) recebendo pagamento municipal
- [x] Q66: Empenhos concentrados em dez (queima de orcamento municipal)
- [x] Q67: Fornecedor com PGFN divida ativa recebendo pagamento municipal
- [x] Q68: Licitacao TCE-PB com proponente unico (competicao ficticia)

### Queries alto valor (Q70-Q77) — IMPLEMENTADAS (queries/fraude_tce_pb.sql)
- [x] Q70: Empresa inativa/baixada recebendo pagamento municipal. Irregularidade objetiva
- [x] Q71: Fornecedores com mesmo endereco comercial recebendo no mesmo municipio. Empresas fachada
- [x] Q72: Doador de campanha → prefeito eleito → pagamento municipal. Quid pro quo direto
- [x] Q74: Servidor municipal recebendo Bolsa Familia. Fraude BF ou servidor fantasma
- [x] Q77: Fracionamento de despesa — multiplos empenhos pequenos somando acima do limite dispensa

## Portal dados.pb.gov.br — Dados estaduais PB
API: https://dados.pb.gov.br:443/getcsv?nome={dataset}&exercicio={ano}&mes={mes}
Dados do GOVERNO DO ESTADO (complementa TCE-PB que cobre 237 municipios).
Exercicios disponiveis: 2000-2026 (varia por dataset). Formato: CSV com ; separador, valores decimais com ponto.

### Mapeamento completo dos datasets (ID JSF → nome API)
Discovery via JSF AJAX (POST com datasetZip_input={ID}):

**SIAF (alto valor):**
- **pagamento** (ID=4): Autorizacoes de pagamento estaduais. 13 cols. CPF COMPLETO + CNPJ credor, nome, valor, data. ~50k/mes. Param: mes=
  - Volume: ~5M registros (2018-2026, ~550k/ano). Dados 2026 disponiveis (jan=15.5k)
  - Cruzamentos: CPF completo → socio, PGFN, TSE, CEIS/CNEP, BF. CNPJ → empresa RFB inativa/inapta
- **empenho_original** (ID=1): Notas de empenho. 41 cols. CNPJ completo (PJ), CPF mascarado (PF), modalidade licitacao, motivo dispensa, numero contrato, historico, dados diarias (destino, datas). Param: mes=
  - Volume: ~2.3M registros (2018-2026, ~250k/ano). Alguns meses sem dados (gaps). Dados 2026 disponiveis (jan=7.2k)
  - Cruzamentos: cnpj_basico → empresa + socio. Modalidade × valor → fracionamento
- **Diarias** (ID=5): Empenhos de diarias. Mesma estrutura do empenho_original. CPF mascarado. Param: mes=
  - Volume: ~2k/mes. Dados 2026 disponiveis (jan=2.2k)
- empenho_suplementacao (ID=8), empenho_anulacao (ID=9), pagamento_anulacao (ID=40): Valor medio (padroes empenha-anula-reempenha)
- liquidacaodespesa (ID=107), liquidacaodespesadescontos (ID=108): Sem CPF/CNPJ direto
- receitas_execucao (ID=3), receitas_previsao (ID=2): Sem CPF/CNPJ

**SIGA (alto valor):**
- **contratos** (ID=35): Contratos estaduais. 20 cols. CNPJ/CPF contratado, nome, objeto, valor, processo licitatorio, gestor, municipio. Param: exercicio= (sem mes)
  - Volume: ~11k registros (2020-2023 disponiveis; 2024-2026 sem dados ainda)
  - Cruzamentos: CNPJ contratado → empresa RFB (ativa?), socio (servidor socio?), PGFN, CEIS
- **convenios** (ID=37): Convenios estado-municipios. 16 cols. CNPJ convenente, objetivo, valores concedente/contrapartida, vigencia, URL documento. Param: mes_inicio= mes_fim=
  - Volume: ~9k registros (2018-2026, ~1k/ano). Dados 2026 disponiveis (187)
- aditivos_contrato (ID=38): Aditivos de contrato. 12 cols. Sem CPF/CNPJ direto (JOIN via CODIGO_CONTRATO). Param: mes_inicio= mes_fim=
- aditivos_convenio (ID=39): Aditivos de convenio. 13 cols. Sem CPF/CNPJ direto. Param: mes_inicio= mes_fim=

**Saude/Educacao:**
- **pagamentos_gestao_pactuada_saude** (ID=104): Pagamentos organizacoes sociais saude. 15 cols. CNPJ credor, nome, valor, nota fiscal, categoria despesa. Param: mes=
  - Volume: ~50k registros. Setor saude propenso a fraude
- pagamentos_gestao_pactuada_educacao (ID=105): Idem educacao. Vazio em 2025, dados 2026 disponiveis (jan=461)

**CGE:**
- dotacao (ID=46): Dotacao orcamentaria. 15 cols. Sem CPF/CNPJ. Param: mes=
- liquidacao (ID=48): Liquidacoes CGE. 27 cols. Sem CPF/CNPJ. Param: mes=
- tipo_modalidade_pagamento (ID=45): Tabela referencia

**FOPAG:**
- resumo_folha (ID=42): Resumo folha pagamento. Vazio/sem dados

**DADOS-PB (tabelas referencia):**
- acao (ID=22), categoria_economica_despesa (ID=23), dispensa_licitacao (ID=24), elemento_despesa (ID=25)
- funcao (ID=26), grupo_natureza_despesa (ID=27), item_despesa (ID=28), modalidade_aplicacao_despesa (ID=29)
- modalidade_licitacao (ID=30), programa_dadospb (ID=31), subfuncao_dadospb (ID=32)
- unidade_gestora_dadospb (ID=33), unidade_orcamentaria_dadospb (ID=34), tipos_de_orcamento (ID=65)

**Referencia SIAF:**
- grupo_financeiro (ID=44), situacao_empenho (ID=51), tipos_documento (ID=52), tipo_credito (ID=54), tipo_movimentacao_orcamentaria (ID=49)

### Pipeline dados.pb.gov.br — estimativa total ~7.8M registros, ~1.8GB
Arquivos criados:
- sql/20_schema_dados_pb.sql — 5 tabelas: pb_pagamento, pb_empenho, pb_contrato, pb_saude, pb_convenio
- etl/20_dados_pb.py — ETL completo (--only, --anos, --no-schema), download+cache em G:\govbr-dados-brutos\dados_pb\
- etl/00_download.py — download_dados_pb() adicionado ao orquestrador
- etl/15_normalizar.py — Fases 7-8 (cnpj_basico, cpf_digitos_6, nome_upper + 7 indices CONCURRENTLY)

Status:
- [x] Schema SQL (sql/20_schema_dados_pb.sql)
- [x] ETL criado (etl/20_dados_pb.py) — staging COPY + limpeza CPF/CNPJ inline
- [x] Download completo: 262 arquivos, 1.6GB em G:\govbr-dados-brutos\dados_pb\
- [x] Carga completa: pb_pagamento 3.87M, pb_empenho 1.67M, pb_contrato 15.6k, pb_saude 215k, pb_convenio 7.8k = 5.78M registros
- [x] Indices basicos criados (17 indices)
- [x] Normalizacao Fases 7-8 concluida: cnpj_basico (5 tabelas), cpf_digitos_6 + nome_upper (pb_pagamento) + 7 indices
- [x] Queries cruzadas (Q78-Q91) — implementadas e executadas (sessao 9-10)

### Queries dados.pb × TCE-PB × fontes federais (Q78-Q91) — IMPLEMENTADAS (queries/fraude_dados_pb.sql)
Diferencial: pb_pagamento tem CPF COMPLETO (3.67M de 11 dig numericos). Socio tem CPF mascarado → match via cpf_digitos_6 + nome_upper.

**CPF completo (pb_pagamento) — cruzamentos ineditos:**
- [x] Q78: Auto-contratacao — credor PF do estado eh socio de empresa que tambem recebe do estado. LATERAL JOIN
- [x] Q79: Credor PF do estado eh candidato TSE — match exato CPF 11 dig
- [x] Q80: Credor PF do estado recebe Bolsa Familia — cpf_digitos_6 + nome_upper
- [x] Q81: Credor PF sancionado (CEIS/CNEP) recebendo pagamento estadual — CPF 11 dig exato
- [x] Q82: Credor PF do estado eh servidor federal SIAPE — cpf_digitos_6 + nome_upper

**CNPJ — cruzamento estado × municipio × federal:**
- [x] Q83: Empresa dominante — recebe do estado (pb_empenho) E municipios (tce_pb_despesa) via cnpj_basico. CTEs pre-agregadas
- [x] Q84: Contratada estadual inativa/inapta — pb_contrato × estabelecimento
- [x] Q85: Fornecedor estadual com divida ativa PGFN — cnpj_basico
- [x] Q86: Fornecedor saude sancionado — pb_saude × ceis_sancao
- [x] Q87: Socio de contratada estadual eh servidor municipal — pb_contrato × socio × tce_pb_servidor

**Cross TCE-PB × dados.pb:**
- [x] Q88: Servidor municipal recebe pagamento estadual como PF — cpf_digitos_6 + nome_upper
- [x] Q89: Convenio estado→municipio com despesas suspeitas — LATERAL JOIN periodo

**Fracionamento / padroes:**
- [x] Q90: Empenhos estaduais abaixo do limite de dispensa — fracionamento
- [x] Q91: Mesmo credor, multiplos pagamentos no mesmo dia — splitting

Normalizacao Fases 7-8 COMPLETA. Todas queries executadas sessao 10.

## Proxima iteracao: novas fontes
- [ ] Pessoas Expostas Politicamente (PEP) — deu 403, tentar novamente
- [ ] Favorecidos PJ - Portal da Transparencia (dados.gov.br)
- [ ] Notas Fiscais Eletronicas (portaldatransparencia.gov.br) — benchmark de preco federal, nao cobre municipal
- [ ] Explorar catalogo completo do dados.gov.br via API (chave no .env)
- [ ] Solicitar token SAGRES (sagrescaptura.tce.pb.gov.br): email suportesagres@tce.pb.gov.br

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
