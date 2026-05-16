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
  - [x] **(PR #151)** Pagina `/empresa/<cnpj>`: 12 queries em `web/queries/empresa.py` (EMPRESA_MUNICIPIOS_PAGANTES, EMPRESA_TOP_ELEMENTOS_*, EMPRESA_EMPENHOS_*, EMPRESA_STATS_BY_MUN, EMPRESA_PAGAMENTOS_*, EMPRESA_PAGAMENTOS_SANCAO_OUTROS) + 3 queries de servidor em `web/routes/cidade.py` (empresa_empenhos, empenhos_durante_vinculo) e `web/queries/cidade.py` (TOP_SERVIDORES_RISCO.total_pago_durante_vinculo) + `empresa_pagamentos` CTE e ambas EXISTS de `_FLAGS_SANCAO_DURANTE_PB` em `cidade.py` (achado em review GPT-5.5) tinham padrao `cnpj_basico = LEFT(d.cpf_cnpj, 8)` sem EXISTS guard, contaminando `/empresa`, perfil de servidor e flags de sancao em TOP_FORNECEDORES com empenhos de CPFs padded (`000XXXXXXXXXXX`). Caso reproduzido: AVICOLA CHESTER MONGAGUA (CNPJ basico 00014020) listava 112 empenhos de PFs cujos CPFs comecavam com prefixo coincidente. Volume global: 36.7% empenhos eram CPFs padded mal-atribuidos (5.8M de 16M)
  - [x] **(PR feat/mv-atomic-swap)** `mv_empresa_pb` (tce_agg + pb_cnpj): mesma classe de bug nos KPIs do header de `/empresa`. Framework `etl/mv_swap.py` cria a MV nova em paralelo e troca via RENAME atomico (~1s downtime, vs 1-2h de DROP CASCADE em `sql/12_views.sql`). Suporta MVs com dependentes (views + matviews) via snapshot + recreate em transacao.

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

### ETL Incremental — atualizar dados sem full reload (~2-4 dias)

**Motivacao**: Full ETL leva 2-4 dias e custa ~$15 USD em VM B4. Mas as fontes
publicam updates frequentes (CPGF/PNCP/sancoes/dados.pb diarias; SIAPE/Bolsa
mensais; RFB mensal). Fazer "delta ETL" mensal/semanal evita drift de dados.

**Status atual**: dos 18 phases de ETL com I/O, apenas 4 sao incrementais
hoje (PNCP contratacoes, SIAPE cadastro, mv_pessoa, mv_views). O resto faz
TRUNCATE+reload OU append-only sem dedupe (re-rodar sem reset duplica linhas).

**Estrategia geral por phase**:
1. Adicionar tabela de controle `etl_watermark(source TEXT, table_name TEXT,
   last_value TEXT, last_run_at TIMESTAMPTZ)` para rastrear o que ja foi carregado.
2. Refatorar cada loader pra usar staging table + `INSERT ... ON CONFLICT` com
   chave natural definida por phase (vide tabela abaixo).
3. Download incremental apenas dos arquivos novos/modificados (HEAD + Last-Modified
   ou checkpoint de mes/ano).
4. Apos load, `15_normalizar` roda apenas em rows com `cpf_cnpj_norm IS NULL`
   (ja eh esse padrao). MVs em `21_views` recriadas inteiras (DROP+CREATE)
   porque dependem de toda a tabela; refresh seletivo eh viavel mas mais complexo.

#### Framework reutilizavel — `etl/incremental.py`

Pra evitar reimplementar a mesma logica em cada loader (e pra que **fontes
NOVAS** ja nasçam incrementais), criar um modulo `etl/incremental.py` com
abstracoes declarativas. Loaders declaram metadata; o framework cuida do
boilerplate (watermark, staging, UPSERT, skip-if-loaded).

**Componentes**:

1. **`LoaderSpec`** (dataclass declarativo) — descreve UM loader incremental:
   ```python
   @dataclass
   class LoaderSpec:
       source: str                    # "cpgf", "siape_remuneracao", ...
       table: str                     # "cpgf_transacao"
       natural_key: list[str]         # ["codigo_orgao_superior", "cpf_portador", "dt_transacao", "valor"]
       watermark_col: str | None      # "ano_extrato_mes_extrato" (NULL = use last_run_at)
       cursor_strategy: CursorStrategy  # MONTH_WINDOW | YEAR_WINDOW | DAILY_SNAPSHOT | API_SINCE | UNIQUE_ID
       dedupe_strategy: DedupeStrategy  # UPSERT | REPLACE_SNAPSHOT | APPEND_UNIQUE
       on_conflict_action: str        # "DO NOTHING" | "DO UPDATE SET col1=EXCLUDED.col1, ..."
       columns: list[str]             # nome explicito das colunas do COPY
       transform: callable | None     # opcional: row -> row antes do COPY
   ```

2. **`incremental_load(spec, file_iter, conn)`** — orquestra:
   - Le `etl_watermark` pra saber `last_value` (ex: ultimo ano_mes processado).
   - Chama `file_iter` apenas para arquivos novos (>= last_value).
   - Cria staging table com schema espelhando target.
   - Streama CSV → staging via `copy_from_stream` (preserva contrato sem-pandas).
   - `INSERT ... ON CONFLICT` com `natural_key` no target.
   - `DROP TABLE staging`.
   - Atualiza `etl_watermark` com novo `last_value` + `last_run_at`.
   - Retorna `LoadResult(rows_inserted, rows_updated, rows_skipped, errors)`.

3. **Cursor strategies** (helpers comuns):
   - `MONTH_WINDOW`: itera `YYYYMM` desde watermark+1 ate hoje. Usado por
     CPGF, SIAPE, Bolsa Familia.
   - `YEAR_WINDOW`: itera `YYYY` desde watermark ate hoje. Usado por Viagens,
     Renuncias, dados.pb por ano.
   - `DAILY_SNAPSHOT`: baixa apenas snapshot de hoje (skip se LastMod nao
     mudou). Usado por Sancoes (CEIS/CNEP/CEAF/Acordos).
   - `API_SINCE`: faz request a API com `?since=watermark`. Usado por PNCP
     (`/contratacoes/atualizacao?dataInicial=...`).
   - `UNIQUE_ID`: nao tem watermark temporal, usa apenas natural_key + UPSERT.
     Usado por dom_*, Q-derived tables.

4. **Dedupe strategies**:
   - `UPSERT`: padrao. Insert + ON CONFLICT.
   - `REPLACE_SNAPSHOT`: TRUNCATE target antes do load (Sancoes — fonte ja
     vem como "estado atual").
   - `APPEND_UNIQUE`: insert + DELETE pre-existing rows com mesma chave
     (raramente necessario).

5. **`etl_watermark` schema** (em `sql/01_schema.sql` ou novo `sql/22_watermark.sql`):
   ```sql
   CREATE TABLE IF NOT EXISTS etl_watermark (
       source       TEXT NOT NULL,
       table_name   TEXT NOT NULL,
       last_value   TEXT,                  -- '202604' / '2026' / '2026-04-30T18:00:00Z'
       last_run_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
       rows_loaded  BIGINT DEFAULT 0,
       error_count  INT DEFAULT 0,
       last_error   TEXT,
       PRIMARY KEY (source, table_name)
   );
   ```

6. **`run_all.py` --incremental flag**:
   - Por default segue comportamento atual (full reload).
   - Com `--incremental`: cada phase consulta sua `LoaderSpec`. Se tiver uma
     definida, usa o framework. Se nao tiver, **pula a phase** (e loga aviso).
   - Phases sem spec (RFB, TSE) so rodam em full reload.

**Como adicionar uma nova fonte ao ETL**:

Cada novo loader (existente ou futuro) que queira incremental segue:

1. Definir o schema em `sql/NN_schema_{source}.sql` com PRIMARY KEY ou UNIQUE
   index na chave natural.
2. Criar `etl/NN_{source}.py` com:
   ```python
   from etl.incremental import LoaderSpec, CursorStrategy, DedupeStrategy, incremental_load

   SPEC = LoaderSpec(
       source="cpgf",
       table="cpgf_transacao",
       natural_key=["codigo_orgao_superior", "cpf_portador", "dt_transacao", "valor"],
       watermark_col="ano_extrato_mes_extrato",
       cursor_strategy=CursorStrategy.MONTH_WINDOW,
       dedupe_strategy=DedupeStrategy.UPSERT,
       columns=[...],  # mesma ordem do CSV
   )

   def run(conn, mode="full"):
       if mode == "incremental":
           return incremental_load(SPEC, conn, file_iter=iter_cpgf_files)
       else:
           return _full_reload(conn)  # comportamento legado preservado
   ```
3. Adicionar a phase em `etl/run_all.py:_PHASES` com `mode` propagado.
4. Documentar a chave natural em `etl/README.md` (seção "Incremental ETL —
   chaves naturais por fonte").

**Beneficios do framework**:
- Fontes novas ja nascem incrementais com ~5 linhas de declaracao.
- Watermark, retry, dedupe ficam em um lugar so (DRY).
- Refactors futuros (ex: trocar UPSERT por MERGE quando PG17) afetam um arquivo so.
- Test harness compartilhado: cada loader testa via mock do `file_iter`.

#### Infraestrutura compartilhada (uma vez antes da Onda 1)
- [ ] **#i0a Tabela `etl_watermark` + helpers minimos** (~baixo esforco)
  - Schema em `sql/22_watermark.sql`.
  - Helpers em `etl/db.py`: `get_watermark(conn, source, table) -> str | None`,
    `set_watermark(conn, source, table, last_value, rows_loaded)`.
- [ ] **#i0b Modulo `etl/incremental.py` (framework declarativo)** (~medio esforco)
  - `LoaderSpec` dataclass + enums `CursorStrategy` / `DedupeStrategy`.
  - `incremental_load(spec, conn, file_iter)` orchestrator.
  - 4 cursor helpers (MONTH/YEAR/DAILY/API_SINCE).
  - Suite de testes em `tests/etl/test_incremental.py` com mock de file_iter.
- [ ] **#i0c Migration de UM loader como prova de conceito** (~baixo esforco)
  - Escolher PNCP itens (ja tem PK + 9M rows = bom stress test).
  - Refatorar pra usar `LoaderSpec`.
  - Validar: drop+full reload da mesmos rows que incremental + UPSERT.
- [ ] **#i0d Documentar pattern em `etl/README.md`** (~baixo esforco)
  - Seção "How to make a loader incremental" com checklist.
  - Tabela "natural key por fonte" (ground truth pra evitar drift).

**Ondas de implementacao**:

#### Onda 1 — quick wins (alta frequencia + baixa complexidade)
- [ ] **#i1 04b PNCP itens incremental** (~baixo esforco)
  - Hoje: `TRUNCATE pncp_item` + reload total (~9.3M rows).
  - Schema ja tem composite PK `(numero_controle_pncp, numero_item)`.
  - Fix: trocar TRUNCATE por staging + UPSERT. Watermark = max(dt_atualizacao).
  - Speedup esperado: 2-4h → ~10min/run.

- [ ] **#i2 12 SIAPE incremental completo** (~baixo esforco)
  - Hoje: `cadastro` ja usa `ON CONFLICT (id_servidor_portal) DO NOTHING`,
    mas pega "ultimo arquivo" sem rastrear watermark.
  - Fix: usar `etl_watermark` pra saber qual ano_mes ja foi processado.
    `siape_remuneracao` precisa chave natural (id_servidor_portal, ano, mes)
    + UPSERT.
  - Speedup: incremental real, 1 mes em ~5min vs reload total ~30min.

- [ ] **#i3 13 Sancoes (CEIS/CNEP/CEAF/Acordos) incremental** (~baixo esforco)
  - Fonte: snapshot diario (substitui o anterior).
  - Estrategia: TRUNCATE+reload do snapshot mais recente — fonte ja eh
    "estado atual" das sancoes vigentes. Manter logica atual mas adicionar
    watermark de "ultimo snapshot baixado" pra nao re-baixar mesmo dia.
  - Speedup: skip se ja baixou hoje. Util pra runs frequentes.

- [ ] **#i4 06 CPGF incremental** (~medio esforco)
  - Hoje: append por arquivo `{ym}_CPGF.zip`. Sem chave natural, re-rodar
    duplica.
  - Fix: definir chave (orgao + unidade_gestora + cpf_portador + dt_transacao
    + valor + favorecido) → UPSERT. Watermark = (ano_extrato, mes_extrato).
  - Bonus: arquivo do mes corrente cresce diariamente (Banco do Brasil envia
    diariamente). Re-rodar mes corrente da pra fazer diff via UPSERT.

- [ ] **#i5 17 Bolsa Familia incremental** (~medio esforco)
  - Hoje: append por arquivo mensal sem dedupe.
  - Fix: chave (cpf_favorecido, mes_competencia) + UPSERT. Watermark = mes_competencia.

#### Onda 2 — fontes com keys naturais claras
- [ ] **#i6 14 Viagens incremental** (~medio esforco)
  - Hoje: append por ano sem dedupe (VM atrasada 16+ meses).
  - Fix: chave (codigo_viagem, cpf_viajante) + UPSERT. Watermark = ano.

- [ ] **#i7 04 PNCP contratos/contratacoes UPSERT formal** (~medio esforco)
  - Hoje: append-only mas tabelas tem PKs.
  - Fix: trocar `INSERT` por `ON CONFLICT (numero_controle_pncp) DO UPDATE
    SET dt_atualizacao = EXCLUDED.dt_atualizacao` (PNCP rows sao mutaveis —
    aditivos, retificacoes, etc).
  - Usar API `/contratacoes/atualizacao?dataInicial=watermark` pra pegar so
    o que mudou desde a ultima run.

- [ ] **#i8 19 TCE-PB incremental** (~medio/alto esforco)
  - Hoje: full reload.
  - Despesa: chave (exercicio, codigo_ug, numero_empenho) + UPSERT. Watermark = ano.
  - Receita: chave (ano, codigo_ug, numero_lancamento) + UPSERT.
  - Servidor: chave (cpf, ano_mes, codigo_ug) + UPSERT.
  - Licitacao: chave (ano_licitacao, codigo_ug, numero_licitacao) + UPSERT.

- [ ] **#i9 20 dados.pb.gov.br incremental** (~medio/alto esforco)
  - Multiplos datasets (empenho, contrato, pagamento, servidor, etc) — cada
    um precisa chave propria.
  - Fonte eh "diaria" (FAQ oficial), entao incremental tem alto valor.
  - Estrategia: 1 PR por dataset, comecando pelos mais usados no frontend
    (pb_empenho, pb_pagamento, pb_contrato, pb_servidor).

#### Onda 3 — fontes com keys complicadas
- [ ] **#i10 05 Emendas incremental** (~alto esforco)
  - Multiplas sub-tabelas (emenda_pagamento, emenda_favorecido, etc).
  - Definir chaves por sub-tabela; algumas fontes sao snapshots consolidados.

- [ ] **#i11 07 PGFN incremental** (~alto esforco)
  - Chave natural: `numero_inscricao` (mesma divida tem 1 numero unico).
  - Watermark = max(dt_inscricao).

- [ ] **#i12 08 Renuncias incremental** (~alto esforco)
  - 4 sub-tabelas; algumas anuais, outras snapshots.

- [ ] **#i13 09 Complementar (BNDES/Holdings/ComprasNet) incremental** (~alto esforco)
  - Fonte mista; cada dataset precisa estrategia propria.

#### Phases que NAO viram incrementais (full reload mantido)
- **03 RFB CNPJ**: Receita publica dump full mensal (7GB/mes). Sem delta
  publico. Strategy: reload mensal completo, ~30min em B4.
- **16/18 TSE**: snapshots por ciclo eleitoral; reload anual em ano de eleicao.
- **02 Dominio, 01 Schema, 10 Indices**: estaticos.

#### Infraestrutura compartilhada (uma vez antes da Onda 1)
Items #i0a-#i0d listados acima na seção "Framework reutilizavel".

#### Workflow novo no deploy.yml
- [ ] **#i14 etl_phase=incremental no deploy.yml**
  - Roda apenas phases incrementais + 15_normalizar (filtra por novas rows) +
    21_views (refresh).
  - Dispatch mensal manual ou agendado via cron (`schedule: cron: '0 6 1 * *'`).
  - ETA esperado pos-Ondas 1+2: ~30min-2h vs 2-4 dias do full ETL.

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

### Observabilidade — analytics pipeline
- [ ] **Ingestao access.log -> PostgreSQL** — Vector/Filebeat ou daemon Python que tail+parse+COPY do nginx access.log
  pra uma tabela `access_log_raw(ts, ip, ua, path, status, referer, bytes, ua_category, geo_city)`. Habilita SQL ad-hoc
  sobre todo o trafego com retencao configuravel — resolve o que `/_traffic/raw` (so ultimas 1000 linhas) e a skill
  `analyze-prod-traffic` (on-demand, sem persistencia) nao cobrem. JOINs com tabela `cidades` permitem perguntar
  "quantos hits em /cidade/X agrupados por dia/mes". Complementa o digest diario (cruza-traffic-digest) que da resumo
  mas nao permite drill-down. Esforco: 1-2 dias (parser + schema + retencao + dashboard SQL).

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
- IP estatico dedicado (~$4/mes)
- Budget: ~US$150/mes (creditos Visual Studio Enterprise)
- **Custo tipico:** ~$104/mes (web + 1 ETL + 1 warm)
- Resource group, VM name, data disk e subscription ficam em GitHub Secrets (`AZURE_RESOURCE_GROUP`, `AZURE_VM_NAME`, `AZURE_DATA_DISK_NAME`, `AZURE_SUBSCRIPTION_ID`) e nao sao expostos no repo.
- SSH read-only de debug: `ssh -i <chave-privada> govbr@<VM_HOST>` (host e chave ficam locais ao mantenedor)
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
