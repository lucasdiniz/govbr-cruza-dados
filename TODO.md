# TODO - govbr-cruza-dados

## Pendente

### Score unificado de risco (PR #31 — fixes do review gpt-5.4)
- [x] **BUG: CEAF JOIN quebrado** (`sql/12_views.sql`) — corrigido: agora `ce.cpf_digitos_6 = srv.cpf_digitos_6 AND nome_upper`
- [x] **BUG: KPIs sancao sem janela temporal + esfera MUNICIPAL ausente** (`sql/12_views.sql`) — corrigido: `desp_eventos` com filtro `data_empenho` na vigencia + clausula `esfera_orgao_sancionador='MUNICIPAL'` com match de nome
- [x] **BUG: pct_pago_socios conta pagamento N vezes** (`sql/12_views.sql`) — corrigido: `(SELECT DISTINCT municipio, cnpj_basico FROM socio_cnpj_mun)` antes do `SUM`
- [x] **BUG: Drift Python ↔ SQL no componente pct_pago_socios** (`web/kpis/municipio_pb.py` vs `sql/12_views.sql`) — corrigido: SQL agora usa `ROUND(..., 2)` identico a coluna `pct_pago_socios`
- [x] **Comentarios "fallback" enganosos** (`web/queries/cidade.py`, `web/routes/cidade.py`, `web/routes/og_image.py`, `sql/12_views.sql`) — corrigido: comentarios explicitam que `COALESCE` so cobre linhas faltantes na MV e que phase 18 deve rodar antes do deploy
- [ ] **Atualizar labels/legendas do mapa** (`web/static/mapa.js:6-13`) — label "Risco composto (0-100)" → "Nota de atencao (0-100)" alinhando com `/search/cidade`. Recalibrar breaks (62/65/69/73/77 calibrados ao TCE legado) apos deploy. Atualizar descricao do filtro no popover `?` mencionando os 8 KPIs componentes
- [ ] **PERF: socio_por_municipio reagrega tce_pb_despesa desnecessariamente** (`sql/12_views.sql`) — apesar de `_tmp_conflito` materializar relacao similar. Refresh fica mais caro. Opcional
- [ ] **MAINT: MV duplica formula de sql_score_expression()** — a expressao inline em `sql/12_views.sql` deveria vir de `web/kpis/municipio_pb.py:sql_score_expression()` via placeholder no `etl/21_views.py` para garantir single source of truth. Hoje sao identicas, mas drift silencioso eh possivel
- [x] **`sancoes_base` filtra 3 anos vs `desp_eventos` 2022+** (`sql/12_views.sql`) — corrigido: alinhado para `>= '2022-01-01'`. Antes excluia ~60 sancoes CEIS terminadas em 2022 cujos empenhos correspondentes estavam em desp_eventos
- [x] **Deploy MV unificada em prod (PR #31)** — concluido: deploy.yml `etl_phase=18`/`etl_phase=sql` recria todas MVs incluindo `mv_municipio_pb_kpi_score` e `mv_municipio_pb_mapa`

### Pivot PB-first — novas visualizacoes e cruzamentos
- [x] **Mapa coropletico PB** — 223 municipios pintados por metrica, 5 camadas (risco, % irregulares, % sem licitacao, top-5, per capita). Toggle, legenda, click navega para detalhe. Breaks calibrados aos percentis reais. Aliases TCE→IBGE para municipios renomeados
- [ ] **Rotatividade de credores pos-eleicao** — top 20 fornecedores antes vs depois de cada eleicao municipal. Substituicoes abruptas sinalizam troca de grupo contratado. Visual: tabela com `delta_pago`, icone de "novo" para quem nao existia no mandato anterior
- [ ] **Aditivos como % do contrato original** — `pb_aditivo_contrato` / `pb_contrato.valor_original`. Alertas >25% (limite Lei 14.133) e >100% (presuncao grave). Relatorio ja existe (`relatorio_aditivos_abusivos_estado_pb.md`), falta UI no detalhe do municipio
- [ ] **Grafo fornecedor x municipio** — rede visual mostrando CNPJs que dominam cluster de prefeituras vizinhas. Nos = municipios + CNPJs, arestas = pagamentos. Filtros por valor minimo e por N municipios. Base: `tce_pb_despesa`. Util para detectar carteis regionais
- [ ] **Timeline empenho -> liquidacao -> pagamento -> anulacao** — por `numero_contrato` ou `numero_empenho`. Expoe ciclo anulacao/reempenho, atrasos suspeitos e pagamentos sem liquidacao. Base: `pb_empenho`, `pb_liquidacao_despesa`, `pb_pagamento`, `pb_empenho_anulacao`, `pb_pagamento_anulacao`
- [x] **Heatmap mensal de empenhos** — 12 meses x N anos por municipio. Mata a Q66 (queima de orcamento em dezembro) visualmente e expoe picos pre-eleitorais. Destacar celulas com desvio >2 sigmas da media do municipio
- [ ] **Emendas federais -> municipios PB** — cruzar base de emendas parlamentares com `tce_pb_despesa` do municipio destinatario. Visual: mapa + tabela por parlamentar, cruzado com partido/aliado do prefeito. Estende o trabalho Hugo Motta para todos os parlamentares PB
- [ ] **Mesma nota fiscal em multiplos empenhos** — `pb_liquidacao_despesa.numero_nota_fiscal` repetido em UGs/municipios diferentes com `cpf_cnpj` do fornecedor. Smoking gun de duplo pagamento. Alerta direto, baixa taxa de falso positivo se validado corretamente
- [ ] **Diaria estadual x viagem federal mesmo CPF/data** — `pb_diaria` x tabelas de viagens federais. Servidor estadual recebendo diaria em D e aparecendo como passageiro/diarista federal no mesmo dia

### Frontend web — Bugs criticos
- [x] **Fornecedores nunca carrega** — era problema de performance pre-otimizacao. Funciona com cache e sem cache apos otimizacao de queries
- [x] **Servidores limitado a 10** — LIMIT aumentado para 200, paginacao client-side 10 por pagina
- [x] **Fornecedores limitado a 10** — LIMIT aumentado para 200, paginacao client-side 10 por pagina
- [x] **Botao ocultar medicos removido** — checkbox removido, mantido apenas disclaimer sobre acumulacao constitucional para profissionais de saude
- [x] **Compras sem licitacao sempre 0%** — MV `mv_municipio_pb_risco` nao detectava `numero_licitacao = '000000000'` nem `modalidade_licitacao ILIKE '%sem licit%'`. Corrigido no SQL e MV recriada
- [x] **Badges sem contexto** — badges de servidores agora mostram detalhes: "Socio de X empresas que fornece ao municipio", "Recebe Bolsa Familia", "Salario alto + vinculo societario", etc.
- [x] **Q67 e Q89 timeout** — Q67 reescrita com CTE pre-agrupado + pgfn_agg (120s→56s). Q89 adicionado filtro por nome_municipio no pb_convenio (3742→~10 iteracoes LATERAL)
- [x] **Q59 e Q63 removidas** — redundantes com tabela TOP_SERVIDORES + dialog de detalhes por servidor
- [x] **Q74 removida** — redundante com dialog (Bolsa Família aparece no detalhe do servidor)
- [x] **Alertas sem contexto nos fornecedores** — dialog mostra sancoes CEIS com datas, divida PGFN, situacao cadastral e empenhos recentes
- [x] **Colisoes CPF/CNPJ no cnpj_basico (completo)** — CPFs armazenados como 14 digitos compartilham cnpj_basico com CNPJs reais. Todas as correcoes aplicadas:
  - [x] Removido TOP_FORNECEDORES_BASIC e _BASIC_DATED (queries degradadas que retornam dados incompletos)
  - [x] Q70: substituido LENGTH guard quebrado por EXISTS(estabelecimento)
  - [x] Q71, Q77: adicionado EXISTS(estabelecimento) nos JOINs
  - [x] TOP_FORNECEDORES CTEs (base, fallback, dated, fallback_dated, PNCP): adicionado EXISTS(estabelecimento) no WHERE
  - [x] Adicionado LENGTH(cpf_cnpj_sancionado)=14 em todos os lookups CEIS/CNEP (cidade.py flags, servidores CTE, routes fornecedor/servidor detail)
  - [x] Frontend: emitir data-fornecedor-cpf-cnpj no buildResultTable, guard length>=14 nos links de licitacao (empenho, proponentes, despesas)

### Frontend web — UX e performance
- [x] **Carregamento sequencial** — implementado `POST /api/batch/{municipio}` que serve todos os dados do cache em uma unica requisicao. Frontend renderiza cards do cache instantaneamente, fallback individual para cache miss com concorrencia 4
- [x] **Ordenacao de colunas** — click-to-sort implementado em todas as tabelas (numerico e alfabetico, ASC/DESC com indicador visual)
- [x] **Suporte a municipios de qualquer estado** — autocomplete busca em PB (MV) + todos os estados (PNCP). Municipios fora da PB mostram perfil e fornecedores baseados em dados PNCP, cruzados com CEIS/PGFN/RFB
- [x] **Acentuacao quebrada** — CSVs Latin-1 de dados.pb.gov.br eram lidos como UTF-8 com `errors="replace"`, gerando U+FFFD. Corrigido com fallback UTF-8 → Latin-1 no `_load_csv()` e `set_client_encoding('UTF8')` na conexao ETL
- [x] **Dialogs fullscreen** — width/height 100vw/100vh, scroll isolado (body.dialog-open bloqueia scroll do fundo)
- [x] **Formatacao numerica em todas as tabelas** — `_shortBrl` e `_shortNum` aplicados tanto no client-side (app.js) quanto server-side (result_table.html) para colunas valor/total/pct/qtd
- [x] **Graficos de fornecedor** — mini bar chart (pagamentos mensais) e progress bars (elementos de despesa) com max-width, titulos e proporções corrigidas
- [x] **Q87 duplicatas** — tce_pb_servidor gerava N rows por mes por servidor no JOIN. Corrigido com subquery GROUP BY com MAX(valor_vantagem)
- [x] **Qualificacao societaria no dialog de servidor** — empresas vinculadas agora mostram qualificacao (ex: Socio-Administrador) e data de entrada na sociedade
- [x] **Cache invalidation endpoint** — `POST /api/cache/invalidate` permite limpar queries especificas do web_cache
- [ ] **Descricoes vagas nas secoes** — textos como "Situacoes em que servidores podem estar relacionados de forma inadequada" nao explicam nada. Reescrever com: o que estamos mostrando, por que e relevante, qual lei/norma se aplica. Menos tecnico, mais explicativo
- [ ] **Integrar mv_fornecedor_pb_perfil** — view com score de risco (0-5) por fornecedor. Pode alimentar badges de risco no dialog e ordenar Top Fornecedores por risco
- [ ] **Remover coluna CEAF cpf_digitos_6 obsoleta do normalizador** (`etl/15_normalizar.py`) — o frontend/SQL agora usa `SUBSTRING(cpf_cnpj_norm, 4, 6)` + nome normalizado. Planejar cleanup seguro sem criar dependencia nova nem mexer em producao manualmente
- [ ] **HTTPS** — requer dominio. Opcoes: Let's Encrypt (gratis), Cloudflare proxy, ou Azure Application Gateway

### Frontend web — Arquitetura
- [x] **Endpoint batch para cache** — `POST /api/batch/{municipio}` retorna todos os resultados do `web_cache` de uma vez (JSON com query_id -> {columns, rows, row_count}). Frontend renderiza instantaneamente do cache, endpoints individuais viram fallback
- [ ] **Landing page escura precisa ajuste** — features strip nao esta 100% integrada visualmente com o backdrop

### Deploy Azure
- [x] **Deploy workflow corrigido** — `etl.01_schema` removido da fase `sql` (causava DROP+CREATE e perda de dados). Adicionada opcao `etl_phase=web` para sync de codigo sem reprocessar ETL
- [x] **Nginx reverse proxy** — porta 80 → uvicorn 8000, gzip habilitado, config em `deploy/nginx-cruza.conf`
- [ ] **ETL E2E em andamento** — run 24383758256 (`clean=true`, `etl_phase=all`), fase de download
- [x] **mv_fornecedor_pb_perfil ownership** — verificado em 2026-05-03: MV nao existe mais (renomeada/removida). TODO obsoleta
- [x] **Auto-limpeza de CSVs implementada** — `run_all.py` agora remove CSVs brutos apos cada fase ETL bem-sucedida. Diretorios compartilhados (rfb, tse) so sao removidos quando todas as fases dependentes completam.
- [x] **deploy.yml atualizado** — instala `.[web]`, copia systemd services, reinicia cruza-web e cruza-warm-cache apos deploy
- [x] **Services systemd corrigidos** — paths atualizados para `/home/govbr/govbr-project` e `venv/` (matching deploy.yml)
- [ ] **Issues #1-#4**: Pendentes execucao no banco local
- [ ] **Formalizar Q58 por UF**
- [ ] **Corrigir agregacao monetaria da Q17**
- [ ] **Endurecer relatorio do ciclo politico-financeiro**
- [ ] **Revisar/arquivar relatorios invalidos** conforme classificacao abaixo
- [ ] **Padronizar citacao `razao social + CNPJ` nos relatorios ativos**
- [ ] **Corrigir relatorios com CNPJ nao encontrado na base RFB local**

### Warm cache - performance (deferred big PRs)
Os items abaixo ficaram fora do PR de speedup inicial (loop invertido + Q67 MV +
PARALLEL_WORKERS=4 + ANALYZE + work_mem + disable timers) por serem refactors
maiores. Considerar quando o ciclo atual de warm (~12-18h esperados) ainda for
bottleneck.

- [ ] **#9 Single GROUP BY query (warm 1 query agrupada para todos os munis)**
  - Hoje cada query roda 224 vezes (uma por muni). Com `WITH .. GROUP BY municipio`
    + `ROW_NUMBER() OVER (PARTITION BY municipio ORDER BY ... LIMIT 500)`, vira
    1 query unica → ~10-20x speedup esperado.
  - Risco alto: cada query em `web/queries/registry.py` tem `WHERE municipio = X`
    em local diferente (CTEs profundas, subqueries). Precisa rewrite manual de
    cada query + helper Python pra splitar resultados grouped → `web_cache`.
- [ ] **#10 Pre-aggregate todas as queries lentas em MVs unificadas**
  - Uma MV por familia de query (ex: `mv_top_fornecedores_pb`, `mv_q70_pb`,
    `mv_q89_pb`...) materializando o resultado agrupado por (muni, ano).
  - Warm passa a ser `SELECT * FROM mv_X WHERE muni=X` × N queries → ~30min total.
  - Ja temos #8 (mv_q67_dated_pb) como blueprint.
  - Custo: profile pra identificar queries com >5s/muni; design das MVs;
    espaco em disco; tempo de criacao inicial; refresh strategy.
  - Esforco: vario dias.
- [ ] **#11 Partition `tce_pb_despesa` por ano**
  - Tabela atual = 44GB. Particionando por ano (2018, 2019, ..., 2026), queries
    com filtro `WHERE ano = 2026` (ou `data_empenho >= 'YYYY-...'`) leem apenas
    o slice de ~4GB do ano corrente. Speedup: ~4-6x em queries com filtro de ano.
  - Migration: criar tabela particionada, COPY data por ano (~1-2h em B4), swap.
  - Risco medio: PG suporta nativamente, mas migration eh all-or-nothing.
    Atualizar `etl/03_rfb` ou loaders TCE-PB para escrever na tabela particionada.

### Catalogo de relatorios - revisao de validade

#### Relatorios validos
- `relatorio_falsos_positivos_pb.md`
- `relatorio_pejotizacao_campina_grande.md`
- `relatorio_contratos_fim_de_semana_pb.md`
- `relatorio_capital_minimo_contratos_pb.md`
- `relatorio_fracionamento_despesa_pb.md`
- `relatorio_empresa_fenix_pb.md`
- `relatorio_sobrepreco_pncp_item.md`
- `relatorio_sancionados_recebendo_pb.md`
- `relatorio_tratoraco_codevasf_pb.md`
- `relatorio_pejotizacao_saude_municipal_pb.md`
- `relatorio_conflito_cartao_corporativo.md`
- `relatorio_empresas_inativas_fornecedoras_pb.md`
- `relatorio_empresas_relacionadas_concorrencia_pb.md`
- `relatorio_empresas_relacionadas_concorrencia_nacional.md`
- `relatorio_aditivos_abusivos_estado_pb.md`
- `relatorio_fornecedores_irregulares_estado_pb.md`
- `relatorio_duplo_pagamento_nf_pb.md`
- `relatorio_ciclo_anulacao_reempenho_pb.md`
- `relatorio_diarias_sobrepostas_pb.md`
- `relatorio_convenios_devedores_pgfn_pb.md`
- `relatorio_suplementacoes_concentradas_pb.md`
- `relatorio_rede_empresarial_familia_hugo_motta.md`
- `relatorio_duplo_vinculo_publico_pb.md`
- `relatorio_porta_giratoria_pb.md`
- `relatorio_fornecedor_saude_dominante_pb.md`
- `relatorio_bndes_doador_tse.md`

#### Relatorios invalidos ou nao publicaveis
- `relatorio_servidor_bolsa_familia_pb.md` - depende de Q74 (CPF parcial + nome), risco alto de falso positivo
- `relatorio_laranjas_bolsa_familia_pb.md` - mesma fragilidade de Q39/Q74, CNPJs nao encontrados
- `relatorio_risco_municipal_pb.md` - score usa indicador quebrado (sem licitacao zerado) — CORRIGIDO, re-avaliar
- `relatorio_servidor_risco_pb.md` - herda ruido de Q74 e score composto
- `relatorio_risk_score_pb.md` - herda problemas de score
- `relatorio_servidor_socio_fornecedor_pb.md` - superado pela versao corrigida de Q59
- `relatorio_servidor_estadual_socio_fornecedor_pb.md` - depende de match nominal fraco (Q109)
- `relatorio_ciclo_politico_financeiro_exploratorio.md` - exploratorio, nao publicavel
- `relatorio_rede_societaria_pb.md` - bom como mapa analitico, fraco como relatorio conclusivo
- `relatorio_itens_fracassados_pncp.md` - texto forte demais para a prova atual

### Auditoria de identificadores em relatorios
- Script: `scripts/audit_report_identifiers.py`
- Problema mais comum: CNPJ citado sem nome oficial ao lado
- CNPJs nao encontrados na RFB: ver `relatorio_laranjas_bolsa_familia_pb.md`

## Referencia tecnica

### Banco de dados
- **~350M registros** em 18+ fontes, ~210GB
- PostgreSQL local: `PGPASSWORD=kong1029 "/c/Program Files/PostgreSQL/16/bin/psql.exe" -U postgres -d govbr`
- Dados brutos locais: G:\govbr-dados-brutos (HDD)
- 115+ queries em queries/*.sql, 26 relatorios validos em relatorios/

### VM Azure
- **B2as_v2** (2 vCPU, 8GB, ~$55/mes) + Standard SSD E20 ($38/mes) — uso normal (servir web)
- **B4as_v2** (4 vCPU, 16GB, ~$108/mes) + Premium SSD P20 ($73/mes, ReadOnly host caching) — durante ETL/warm
- VM e disco mudam de SKU juntos via deploy.yml (preflight upsize, postflight downsize)
- Disco Premium so cobra durante operacoes pesadas (~$3/mes vs $35/mes always-on)
- Limite Azure: 2 mudancas de SKU de disco por 24h — workflow detecta e prossegue se atingir
- IP estatico: 52.162.207.186 (~$4/mes)
- Budget: ~US$150/mes (creditos Visual Studio Enterprise)
- **Custo tipico:** ~$104/mes (web + 1 ETL + 1 warm)
- Resource group: `RG-GOVBR-NCUS`. VM: `vm-govbr`. Data disk: `disk-govbr-data`. Subscription: `90676d79-a73b-462d-bdd6-2b4c738237f5`
- SSH: `ssh -i C:\Users\lucas\.ssh\azure_vm.txt govbr@52.162.207.186` (read-only debug)
- Workflows: `deploy.yml` (preflight resize + disk SKU → ETL → postflight resize back), `setup-runner.yml` (runner 1x)
- Secrets: `VM_HOST`, `VM_SSH_KEY`, `DB_PASSWORD`, `ENV_FILE`, `RUNNER_ADMIN_TOKEN`, `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID`

### Frontend web
- **Stack**: FastAPI + Jinja2 + vanilla JS, PostgreSQL
- **Iniciar local**: `python -m uvicorn web.main:app --port 8000`
- **Cache warmer**: `python -m web.warm_cache --pb` (apenas PB), `--pncp` (outros estados), `--all` (PB + PNCP), `--daemon --loop` (continuo)
- **Tabela web_cache**: armazena resultados pre-processados (query_id, municipio) -> JSON
- **Services systemd**: `deploy/cruza-web.service` e `deploy/cruza-warm-cache.service`
- **15 queries PB** em 6 categorias priorizadas (Fornecedores Irregulares > Conflito de Interesses > Politico-Eleitoral > Licitacao > Estado x Municipio > Orcamento), 224 municipios PB + qualquer municipio via PNCP
- **Autocomplete**: busca PB (MV risco_score DESC) + outros estados (PNCP, formato "Nome - UF")

### Notas tecnicas importantes
- **pb_pagamento** tem quase 100% PF (1 CNPJ PJ). Usar **pb_empenho** para cruzamentos PJ (18K CNPJs distintos)
- **PGFN cpf_cnpj** e formatado com pontos/traco — usar `REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g')` para extrair digitos
- **CEIS/CNEP cpf_cnpj_norm** e CNPJ completo 14 digitos — match via `LEFT(cpf_cnpj_norm, 8)`
- CNPJ matching entre tabelas sempre via `cnpj_basico` (primeiros 8 digitos)
- **Performance queries**: usar match direto `d.municipio = %(municipio)s` em vez de `UPPER(unaccent())` — diferenca de 45s vs 1-4s
- **sem licitacao**: TCE PB usa `numero_licitacao = '000000000'` e `modalidade_licitacao = 'Sem Licitação'`, nao NULL/vazio

## Concluido (resumo)
- Issues #1-#5 resolvidas (codigo, nao executadas no banco)
- ETL completo local: 16+ fontes, normalizacao, indices
- 7/7 MVs + 2 views criadas. 22 relatorios validos. 14/14 enriquecimentos.
- Q101-Q111 implementadas e validadas (dados.pb)
- Q201-Q209 implementadas (rede empresarial familia Hugo Motta)
- Q301-Q310 implementadas (cruzamentos avancados: duplo vinculo, porta giratoria, BNDES x TSE, saude dominante)
- Auto-limpeza de CSVs apos ETL implementada em run_all.py
- Frontend web: landing page escura com animacao de particulas, pagina de detalhes com tabelas padronizadas
- Cache pre-processado: tabela `web_cache` + `warm_cache.py --daemon` para manter dados prontos
- Performance: queries de 45s para 1-4s removendo UPPER(unaccent()) e usando indexes existentes
- deploy.yml atualizado com install `.[web]` e deploy de systemd services
- Suporte a municipios de qualquer estado via PNCP (autocomplete + perfil + fornecedores)
- Corrigido pct_sem_licitacao (era sempre 0%, agora detecta corretamente)
- Badges de servidores com contexto detalhado
- Paginacao 10/pagina em fornecedores e servidores
- Sort click-to-sort em todas as tabelas
- Tabela pncp_municipio para autocomplete rapido (4497 rows, indice trigram)
- Cache warmer suporta PB + PNCP (--all) com 2 queries por municipio nao-PB
- Servidores com row expandivel mostrando CNPJs das empresas associadas
- Dialog de servidor com 3 secoes: Vinculos (admissao, ultimo registro, salario), Bolsa Familia (ultimo recebimento, valor), Empresas vinculadas (razao social, CNPJ, situacao, CNAE)
- Dialog de servidor enriquecido: stats grid no topo (salario, empresas, pagamentos, sancoes, PGFN, BF), badges nas empresas (CEIS/CNEP, PGFN, empenhos recebidos), secoes reordenadas (vinculos, empresas, bolsa familia)
- Indice idx_pgfn_cnpj_basico_norm para consulta rapida de dividas PGFN por cnpj_basico (40M rows, 114s → 0.14ms)
- Lazy fetch on click (1 request por servidor ao clicar, sem prefetch em massa)
- Tabela de servidores full-width com colunas: Servidor, Cargo, Municipio(s), Maior Salario, Empresas, Sinais de Atencao
- Q59, Q63, Q74 removidas (redundantes com tabela + dialog)
- Q60 filtrada por natureza_juridica (exclui entidades publicas)
- Datas formatadas em formato brasileiro (DD/MM/YYYY, MM/YYYY)
- Bolsa Familia atualizado: download busca snapshot mais recente (de tras pra frente), nao todos os meses
- Toggle ocultar medicos removido, mantido disclaimer sobre acumulacao constitucional
- Q67 e Q89 otimizadas (pre-agrupamento CTE, filtro municipio no LATERAL)
- Dialog de fornecedor: dados cadastrais, sancoes CEIS (datas inicio/fim, vigencia), divida PGFN, empenhos recentes com modalidade de licitacao
- Graficos no dialog de fornecedor: mini bar chart (pagamentos mensais) e progress bars (elementos de despesa)
- Dialogs fullscreen com scroll isolado e navegacao em pilha
- Formatacao numerica (R$ X bi/mi/mil, X.X%, X mil) em client-side e server-side
- Encoding Latin-1 corrigido nos CSVs de dados.pb.gov.br (fallback UTF-8 → Latin-1)
- Q87 corrigida (subquery GROUP BY para eliminar duplicatas de tce_pb_servidor)
- Qualificacao societaria e data de entrada no dialog de servidor
- Cache invalidation endpoint (POST /api/cache/invalidate)
- Nginx reverse proxy para producao (porta 80)
- etl.01_schema removido da fase sql do deploy (previne data loss)
- Tabela de fornecedores full-width com colunas: Fornecedor, CNPJ, Total Pago, Empenhos, Situacao, Sinais de Atencao
- pct_sem_licitacao na MV corrigido para filtrar entidades publicas (natureza_juridica NOT LIKE '1%')
- Lazy fetch on click para fornecedores (mesmo padrao de servidores)
- Integracao CNEP: sancoes CNEP unificadas com CEIS em badges, dialog, Q65 e row highlighting
- Badges de sancao: "Impedimento de contratar - CEIS/CNEP" com cores distintas (CEIS vermelho, CNEP laranja)
- Destaque vermelho (row-sancao): fornecedores que receberam durante sancao e servidores socios de empresa sancionada
- Ordenacao por risco: top fornecedores e servidores ordenados com rows vermelhos primeiro
- Legendas condicionais no topo das tabelas explicando o destaque vermelho
- Disclaimer no dialog de fornecedor explicando CEIS/CNEP para leigos
- Empenhos durante sancao em outros municipios: secao no dialog mostrando pagamentos cross-municipio
- Seletor de municipio no dialog: dropdown para alternar entre municipios onde o fornecedor recebeu
- flag_socio_sancionado: EXISTS otimizado com CTE (7.6s → 487ms) cruzando cnpjs_socio com sancoes vigentes
- docker-compose.yml removido (nao utilizado, PostgreSQL roda local)
- Secoes de investigacao reordenadas por potencial investigativo: Fornecedores Irregulares primeiro (evidencia direta de ilegalidade), Orcamento e Financeiro por ultimo (mais contextual)
- Filtro temporal global na pagina de municipio PB: barra de datas (De/Ate) com default ano atual, cache duplo (all-time + ANO), queries live para ranges custom. Hero stats, insight cards, fornecedores e 16 finding cards respondem ao filtro. Servidores (MV) mostram badge "todos os periodos"
- Abrangencia de sancao em todas as superficies: `flag_recebeu_durante_sancao` (boolean) substituido por `abrangencia_sancao_info` (texto com prefixo `!` para sancoes que se aplicam legalmente). Vermelho para inidoneidade, abrangencia nacional e orgao municipal do mesmo municipio. Amarelo para sancoes de outros entes (informativo). Nova coluna "Abrangencia" nas tabelas de fornecedores. Badges enriquecidos com orgao sancionador entre parenteses. Empenhos e graficos de barras diferenciam vermelho (grave) vs amarelo (informativo). Q65 atualizada com abrangencia detalhada. Dialog de fornecedor e servidor mostram escopo completo da sancao. Export CSV inclui parametros de data
- Colisao CPF/CNPJ no cnpj_basico: CPFs armazenados como 14 digitos (com zeros a esquerda) compartilhavam cnpj_basico com CNPJs reais (ex: CPF `00004564640429` e CNPJ `00004564000100`). Causava falsos positivos em TOP_FORNECEDORES, Q65 sancionados recebendo, doadores eleitorais e empenhos durante sancao em outros municipios. Corrigido com `EXISTS (SELECT 1 FROM estabelecimento WHERE cnpj_completo = d.cpf_cnpj)` nos JOINs afetados + identificacao por `cpf_cnpj` completo no frontend e backend
