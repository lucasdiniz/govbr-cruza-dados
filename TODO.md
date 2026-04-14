# TODO - govbr-cruza-dados

## Pendente

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
- [ ] **HTTPS** — requer dominio. Opcoes: Let's Encrypt (gratis), Cloudflare proxy, ou Azure Application Gateway

### Frontend web — Arquitetura
- [x] **Endpoint batch para cache** — `POST /api/batch/{municipio}` retorna todos os resultados do `web_cache` de uma vez (JSON com query_id -> {columns, rows, row_count}). Frontend renderiza instantaneamente do cache, endpoints individuais viram fallback
- [ ] **Landing page escura precisa ajuste** — features strip nao esta 100% integrada visualmente com o backdrop

### Deploy Azure
- [x] **Deploy workflow corrigido** — `etl.01_schema` removido da fase `sql` (causava DROP+CREATE e perda de dados). Adicionada opcao `etl_phase=web` para sync de codigo sem reprocessar ETL
- [x] **Nginx reverse proxy** — porta 80 → uvicorn 8000, gzip habilitado, config em `deploy/nginx-cruza.conf`
- [ ] **ETL E2E em andamento** — run 24383758256 (`clean=true`, `etl_phase=all`), fase de download
- [ ] **mv_fornecedor_pb_perfil ownership** — view criada por user `postgres`, app roda como `govbr`. Corrigir com `ALTER MATERIALIZED VIEW mv_fornecedor_pb_perfil OWNER TO govbr`
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
- **Standard_B4as_v2** (4 vCPU, 16GB RAM) — North Central US
- Disco: 512GB Standard SSD em /data (PostgreSQL 248GB + dados brutos ~105GB apos limpeza)
- Budget: ~US$150/mes
- SSH: `ssh -i /tmp/azure_vm_key govbr@52.162.207.186`
- Workflows: `deploy.yml` (ETL + web services), `setup-runner.yml` (runner 1x)
- Secrets: `VM_HOST`, `VM_SSH_KEY`, `DB_PASSWORD`, `ENV_FILE`, `RUNNER_ADMIN_TOKEN`

### Frontend web
- **Stack**: FastAPI + Jinja2 + vanilla JS, PostgreSQL
- **Iniciar local**: `python -m uvicorn web.main:app --port 8000`
- **Cache warmer**: `python -m web.warm_cache --daemon` (PB), `--pncp` (outros estados), `--all` (PB + PNCP), `--daemon --loop` (continuo)
- **Tabela web_cache**: armazena resultados pre-processados (query_id, municipio) -> JSON
- **Services systemd**: `deploy/cruza-web.service` e `deploy/cruza-warm-cache.service`
- **15 queries PB** em 6 categorias, 224 municipios PB + qualquer municipio via PNCP
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
