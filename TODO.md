# TODO - govbr-cruza-dados

## Pendente

### Frontend web — Bugs criticos
- [x] **Fornecedores nunca carrega** — era problema de performance pre-otimizacao. Funciona com cache e sem cache apos otimizacao de queries
- [x] **Servidores limitado a 10** — LIMIT aumentado para 200, paginacao client-side 10 por pagina
- [x] **Fornecedores limitado a 10** — LIMIT aumentado para 200, paginacao client-side 10 por pagina
- [x] **Botao ocultar medicos quebrado** — `initInteractiveToggles` procurava `.disclaimer-box` mas checkbox esta em `.result-block`. Corrigido
- [x] **Compras sem licitacao sempre 0%** — MV `mv_municipio_pb_risco` nao detectava `numero_licitacao = '000000000'` nem `modalidade_licitacao ILIKE '%sem licit%'`. Corrigido no SQL e MV recriada
- [x] **Badges sem contexto** — badges de servidores agora mostram detalhes: "Socio de X empresas que fornece ao municipio", "Recebe Bolsa Familia", "Salario alto + vinculo societario", etc.
- [ ] **Q59 e Q63 timeout constante** — warm_cache agora usa timeout de 60s+. Ainda pode falhar em municipios grandes. Considerar materialized view para o join servidor-socio
- [ ] **Alertas sem contexto nos fornecedores** — badge "Sancao ativa" poderia incluir detalhes da sancao

### Frontend web — UX e performance
- [x] **Carregamento sequencial** — implementado `POST /api/batch/{municipio}` que serve todos os dados do cache em uma unica requisicao. Frontend renderiza cards do cache instantaneamente, fallback individual para cache miss com concorrencia 4
- [x] **Ordenacao de colunas** — click-to-sort implementado em todas as tabelas (numerico e alfabetico, ASC/DESC com indicador visual)
- [x] **Suporte a municipios de qualquer estado** — autocomplete busca em PB (MV) + todos os estados (PNCP). Municipios fora da PB mostram perfil e fornecedores baseados em dados PNCP, cruzados com CEIS/PGFN/RFB
- [ ] **Descricoes vagas nas secoes** — textos como "Situacoes em que servidores podem estar relacionados de forma inadequada" nao explicam nada. Reescrever com: o que estamos mostrando, por que e relevante, qual lei/norma se aplica. Menos tecnico, mais explicativo
- [ ] **Melhorar graficos/visualizacoes** na pagina de detalhes
- [ ] **Acentuacao quebrada** em algumas tabelas (dados vindos do banco com encoding errado)
- [ ] **Adicionar mais graficos** — graficos de barras/pizza nos blocos de investigacao

### Frontend web — Arquitetura
- [x] **Endpoint batch para cache** — `POST /api/batch/{municipio}` retorna todos os resultados do `web_cache` de uma vez (JSON com query_id -> {columns, rows, row_count}). Frontend renderiza instantaneamente do cache, endpoints individuais viram fallback
- [ ] **Landing page escura precisa ajuste** — features strip nao esta 100% integrada visualmente com o backdrop

### Infra / DX
- [ ] **Docker Compose completo** — adicionar service `etl` (Dockerfile com Python + deps) para deploy local de 1 comando. Hoje o compose so sobe o Postgres.

### Deploy Azure
- [ ] **Deploy em andamento** — retomado a partir da fase 19 (run 24286000479). CSVs de rfb (58GB) e bolsa_familia (85GB) removidos manualmente para liberar disco. 143GB livres.
- [ ] **Auto-limpeza de CSVs implementada** — `run_all.py` agora remove CSVs brutos apos cada fase ETL bem-sucedida. Diretorios compartilhados (rfb, tse) so sao removidos quando todas as fases dependentes completam.
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
- **Cache warmer**: `python -m web.warm_cache --daemon` (1 ciclo) ou `--daemon --loop` (continuo)
- **Tabela web_cache**: armazena resultados pre-processados (query_id, municipio) -> JSON
- **Services systemd**: `deploy/cruza-web.service` e `deploy/cruza-warm-cache.service`
- **18 queries PB** em 6 categorias, 224 municipios PB + qualquer municipio via PNCP
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
