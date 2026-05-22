# govbr-cruza-dados

Pipeline ETL para cruzamento de dados abertos do governo brasileiro, voltado para detecção de fraudes em licitações, emendas parlamentares, cartão corporativo, eleições, programas sociais e contratos públicos.

Alimenta o portal público **[transparenciapb.org](https://transparenciapb.org)** com perfis investigativos de todos os 223 municípios da Paraíba.

> **Vibe coded** com GitHub Copilot, [Claude Code](https://claude.ai/claude-code) e Codex (Opus 4.5/4.6/4.7, GPT-5.2/5.4/5.5) — da modelagem do schema até o último `INSERT INTO`. Veja [CONTRIBUTING.md](CONTRIBUTING.md) para participar.

## O que é

Carrega ~350M registros (~210GB raw) de 18+ fontes públicas brasileiras em um PostgreSQL 16 e cruza pessoas/empresas por CPF/CNPJ para revelar padrões suspeitos, conflitos de interesse e anomalias de contratação.

- **24 fases de ETL** orquestradas por `python -m etl.run_all` (modelo full-reload)
- **Framework ETL incremental** ([`etl/incremental/`](etl/incremental/README.md)) para fontes append-only com watermark, conditional GET e DLQ — hoje cobre 21 specs do TCE-PB, dados.pb.gov.br e Bolsa Família (~60M rows)
- **125+ queries SQL** em 17 arquivos temáticos (Q01-Q310)
- **40+ relatórios** investigativos derivados dos resultados
- **Materialized views em camadas** (L1 → L2 → views planas) para score de risco por município, empresa, pessoa e rede societária
- **Frontend FastAPI** servindo transparenciapb.org com cache pré-computado e *shadow rewarm* zero-downtime
- **Observabilidade self-hosted** — Umami + GoAccess + traffic-digest
- **Auto-resize VM Azure** (B2 → B4 + Standard SSD → Premium SSD) por etl_phase, custos prorrateados por hora

Fontes integradas: Receita Federal, PNCP, TCE-PB (despesas + DOE/acórdãos), dados.pb.gov.br, TSE, PGFN, SIAPE, Bolsa Família, CPGF, BNDES, ComprasNet, emendas parlamentares, sanções (CEIS/CNEP/CEAF), renúncias fiscais, viagens a serviço e acordos de leniência.

## Quickstart

```bash
# Instalar (Python 3.10+, Node 20+, PostgreSQL 16)
pip install -e .[web,dev]
npm ci
cp .env.example .env                      # editar com creds locais

# Postgres 16 — instale local (apt / Homebrew / instalador Windows). Depois crie o banco:
sudo -u postgres psql -c "CREATE USER govbr WITH PASSWORD 'govbr_dev';"
sudo -u postgres psql -c "CREATE DATABASE govbr OWNER govbr;"
sudo -u postgres psql -d govbr -c "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;"
# (Alternativa via Docker, se preferir: ver CONTRIBUTING.md)

# Smoke
python -m compileall etl web scripts -q
pytest tests/incremental/test_framework_smoke.py

# ETL completo (~10-20h em B4as_v2)
python -m etl.run_all

# Frontend (precisa de schema + cache populado)
npm run build
python -m web.warm_cache --pb                 # ~5-7h em B4 — popula web_cache antes de servir
python -m uvicorn web.main:app --port 8000
```

Para contribuição parcial (só `web/`, só `queries/`, só relatórios), veja [CONTRIBUTING.md](CONTRIBUTING.md).

## Comandos principais

```bash
python -m etl.run_all                        # 24 fases (download + carga + indices + views)
python -m etl.run_all 4                      # retomar a partir da fase N (1-based)
python -m etl.00_download                    # apenas downloads
python -m etl.incremental.runner             # framework incremental — todas specs registradas
python -m etl.incremental.runner --only "tce_pb.tce_pb_despesa,dados_pb.pb_pagamento"
python -m etl.incremental.bootstrap_watermark --all   # 1x antes do primeiro incremental
python -m etl.run_queries                    # 125+ queries Q## → resultados/
python -m etl.run_queries --query Q03
python -m etl.probe_sources                  # disponibilidade das fontes remotas

python -m uvicorn web.main:app --port 8000   # frontend local
python -m web.warm_cache --pb                # warm cache (1 ciclo, PB)
python -m web.warm_cache --daemon --loop     # warm cache contínuo
python -m web.indexnow_submit                # notifica Bing/Yandex de mudanças

npm run build                                # esbuild concat + minify + content-hash
npm run build:check                          # smoke do build (CI)
python scripts/audit_report_identifiers.py --strict   # checa CPFs não-mascarados (offline)
```

## Variáveis de ambiente

Toda configuração via `.env` (ver [`.env.example`](.env.example)).

| Variável | Obrigatória? | Default | Propósito |
|---|---|---|---|
| `POSTGRES_HOST` / `_PORT` / `_DB` / `_USER` / `_PASSWORD` | sim | `localhost:5432/govbr/govbr/govbr_dev` | Conexão Postgres |
| `DATA_DIR` | sim para ETL | `/data/raw-data` | Diretório dos CSVs/JSONs raw |
| `RESEND_API_KEY` | opcional | — | Página `/contato` envia email via [Resend](https://resend.com); sem a chave, salva no DB mas não envia |
| `RESEND_FROM`, `CONTATO_DEST` | opcional | `noreply@…` / `contato@…` | Endereços usados pelo formulário |
| `GOOGLE_SITE_VERIFICATION` | opcional | — | Meta tag de verificação do Google Search Console |
| `BING_SITE_VERIFICATION` | opcional | — | Meta tag Bing Webmaster Tools (alimenta também DuckDuckGo/ChatGPT search) |
| `INDEXNOW_KEY` | opcional | — | Token IndexNow para Bing/Yandex/Seznam (32+ chars) |
| `SITE_URL` | opcional | `https://transparenciapb.org` | Origem completa do site |
| `UMAMI_SCRIPT_URL`, `UMAMI_WEBSITE_ID` | opcional | `/_traffic/analytics/script.js` / — | Snippet Umami injetado quando ambas estiverem preenchidas |
| `CACHE_INVALIDATE_TOKEN` | opcional | — | Token admin para `POST /api/cache/invalidate`. Sem ele, endpoint responde 503 (fail-closed); a invalidação operacional vai pelo workflow do deploy |

## Tests

```bash
pip install -e .[dev]                                # adiciona pytest + pytest-mock
pytest tests/incremental/test_framework_smoke.py     # subset offline
pytest tests/incremental                              # suite completa (precisa Postgres + migrations 22-29+32+34+35 + roles)
python -m compileall etl web scripts -q              # smoke de sintaxe
```

A maior parte dos testes hoje cobre o framework ETL incremental. Migração para suite mais ampla + CI rodando em PRs está em andamento — veja issues abertos com label `tests` / `ci`.

## ETL Incremental Framework

Framework dedicado em [`etl/incremental/`](etl/incremental/README.md) para fontes que publicam dados em janelas mês/ano e exigem preservação histórica (TCE-PB, dados.pb.gov.br hoje). Diferenças vs ETL clássico:

|  | Clássico (`etl/00-22`) | Incremental (`etl/incremental/`) |
|---|---|---|
| Carga | TRUNCATE + reload | Append-only + `ON CONFLICT DO NOTHING` |
| Role DB | superuser | `etl_incremental` (sem DROP/DELETE/TRUNCATE) |
| Audit | logs efêmeros | `etl_run_log` + `etl_phase_log` + `etl_download_log` + `etl_rejected_rows` (DLQ) |
| Idempotência | manual | watermark + uuid5 bucket_token |
| Schema drift | quebra silenciosa | `SchemaDriftError` antes de qualquer mutação |
| Download | full re-fetch | Conditional GET (HEAD probe + If-None-Match + If-Modified-Since) |

### Princípios não-negociáveis (P1-P6)

1. 🔴 **NÃO CORROMPER DADOS EXISTENTES** (sobrepõe tudo)
2. **NÃO-DESTRUTIVO** — sem TRUNCATE/DROP/DELETE em targets
3. **AUDITÁVEL** — rastro completo, imutável pelo role ETL
4. **ERROR RESILIENT** — recuperável de qualquer crash
5. **FAST** — download condicional + idempotency
6. **ZERO TOLERANCE** — watermark nunca avança em failure; DLQ persiste mesmo em rollback do main_conn

Detalhes do fluxo end-to-end, specs registradas, observabilidade (`v_etl_status`, `v_etl_dlq_summary`, `v_etl_run_summary`) e como adicionar fonte nova: [`etl/incremental/README.md`](etl/incremental/README.md).

## Arquitetura

### MVs em camadas

```
L1 (independentes)                  L2 (derivadas)              L3 (views planas)
mv_empresa_governo  ─────┐
mv_pessoa_pb        ─────┼─► mv_servidor_pb_risco ─► v_risk_score_pb
mv_municipio_pb_risco ───┤    mv_empresa_pb       ─► v_risk_score_empresa
mv_servidor_pb_base ─────┘    mv_rede_pb
                              mv_municipio_pb_kpi_score
                              mv_municipio_pb_mapa
                              mv_q67_dated_pb
```

`sql/12_views.sql` segue convenções estritas: DROP no topo em ordem reversa, criação por camadas, refresh order documentado no rodapé.

### Entity resolution CPF/CNPJ

CPFs aparecem mascarados em formatos diferentes por fonte:

| Fonte | Formato | Notas |
|---|---|---|
| Bolsa Família / SIAPE / CPGF | `***.456.789-**` | 6 dígitos centrais visíveis |
| Sócio (RFB) | `***456789**` | sem pontuação |
| PGFN | `XXX456.789XX` | formato próprio |
| CEIS / CNEP | `12345678901` | completo (raro) |
| TCE-PB servidores | `***.456.789-**` | 6 dígitos centrais |
| dados.pb pagamento | `00045678901` | **completo** (11 dígitos) |
| dados.pb empenho PF | `***456***` | só 3 dígitos centrais |

A fase 17 (`etl/15_normalizar.py`) cria colunas indexadas `cpf_digitos` e `cpf_cnpj_norm` com apenas os dígitos. JOINs cross-source usam igualdade direta nessas colunas (não LIKE/regex), o que torna viável cruzamento em 350M linhas.

Match por **nome normalizado + 6 dígitos centrais** entre fontes distintas (sócio × servidor × Bolsa Família) reduz falsos positivos mesmo com CPFs mascarados. Quando uma fonte tem CPF completo (CEIS, dados.pb pagamento), o cruzamento usa os 11 dígitos diretamente.

O frontend também sinaliza vínculos **municipal + federal** na lista de servidores ao cruzar `tce_pb_servidor` com SIAPE (`siape_cadastro`) por nome normalizado + 6 dígitos centrais do CPF. Esse badge é triagem: acumulação pode ser legal em hipóteses como saúde e magistério.

### Identificação de fornecedores

Use `cpf_cnpj` completo (14 dígitos) — não `cnpj_basico` (8 dígitos), que sofre colisão com CPFs que coincidem no prefixo. Filtre com `EXISTS (SELECT 1 FROM estabelecimento WHERE cpf_cnpj = ...)` para excluir falsos positivos. Desde PR feat/etl-cnpj-basico-fix, o ETL aplica esse guard preventivamente em `tce_pb_despesa` + 9 tabelas `pb_*`, e a coluna nova `cpf_digitos` (11 dígitos extraídos via DV check matemático módulo 11) viabiliza queries de pessoa física (ex: `/empenho-pf/<cpf>`). Ver [ADR-0007](docs/adr/0007-etl-normalize-fix.md).

### Web cache e shadow rewarm

A tabela `web_cache` armazena resultados pré-computados (FastAPI lê direto dela, sem rodar SQL pesado em request time). Quatro modos de manutenção:

- **drop_cache** — `TRUNCATE web_cache` (12-18h de cache miss; use só em mudança de schema).
- **invalidate_cache_keys** — `DELETE` cirúrgico HARD por **substring** de qid (causa cache miss até warm). Cuidado: `PERFIL` casa também `EMPRESA_PERFIL`, `PERFIL_DATED`, etc.
- **rewarm_cache_keys** — shadow rewarm **zero-downtime**: warm escreve em `<qid>__pending`, swap atômico promove `__pending` → live só se todas as queries da chave passaram (fail==0); caso contrário, aborta e mantém live antigo. **Default recomendado** para mudanças em `web/queries/registry.py`.
- **cleanup_orphan_empresa_cache** — `DELETE` standalone de entries `EMPRESA_PERFIL` + `EMPRESA_PERFIL_MUN` cujo `cnpj_basico` não existe mais em `mv_empresa_pb` (típico após `run_normalize_fix` + `refresh_mvs=mv_empresa_pb` que removeu empresas contaminadas por CPF padded). Não dispara warm. Ver [ADR-0009](docs/adr/0009-orphan-empresa-cache-cleanup.md).

Auto-expansão: shadow de `PERFIL`/`TOP_FORN`/`TOP_SERV` propaga para `KPI_SUMMARY` (mesmo prefixo).

### MV atomic swap (zero-downtime)

`etl/mv_swap.py` permite atualizar UMA `MATERIALIZED VIEW` (incluindo schema/colunas novas) com downtime de ~1s, sem dropar as outras. **É o caminho default para qualquer mudança de definição de UMA MV.** Comparado a `etl_phase=sql` que faz `DROP CASCADE` de todas as MVs em `sql/12_views.sql` (1-2h + VM resize, e não-cancelável mid-flight), o swap usa a VM atual e mantém o tráfego servindo a MV antiga durante o build.

Mecânica:

1. Build paralelo: `CREATE MATERIALIZED VIEW <mv>_swap AS …` em autocommit (sem bloqueio).
2. Captura recursiva de dependentes via `pg_depend`/`pg_rewrite` + `pg_get_viewdef`.
3. Transação atômica (~1s): `DROP MV <mv> CASCADE` + `ALTER MV <mv>_swap RENAME TO <mv>` + recria views/MVs dependentes.
4. `REFRESH MATERIALIZED VIEW` em MVs dependentes (fora de tx).

Uso via deploy:

```bash
gh workflow run deploy.yml --ref main \
  -f etl_phase=web \
  -f mv_swap=mv_empresa_pb \
  -f rewarm_cache_keys=EMPRESA_PERFIL,EMPRESA_PERFIL_MUN
```

Pra cada MV, crie `deploy/mv_updates/<mv_name>.sql` com a nova definição usando sufixo `_swap` em todos os identifiers (será removido pelo framework). Veja `deploy/mv_updates/mv_empresa_pb.sql` como exemplo.

Uso direto:

```bash
python -m etl.mv_swap mv_empresa_pb deploy/mv_updates/mv_empresa_pb.sql
```

### 24 fases ETL e auto-cleanup

`etl/run_all.py` mantém uma lista hardcoded de 24 módulos (`etl.00_download`, `etl.01_schema`, …, `etl.22_mv_sitemap`). Após cada fase concluir, `_cleanup_csvs` remove os CSVs raw daquela fase (espaço em disco é restrito). Diretórios compartilhados (`rfb/`, `tse/`) só são removidos quando todas as fases dependentes terminaram (`_SHARED_DIRS`).

**Ao adicionar fase nova consumindo CSVs já baixados:** registre o módulo em `_SHARED_DIRS` ou os arquivos são apagados antes da fase rodar.

## Features de produção (transparenciapb.org)

A stack roda numa VM Ubuntu Azure com systemd services e Nginx reverse proxy. Componentes:

| Componente | Systemd unit | Função |
|---|---|---|
| Frontend FastAPI | `cruza-web.service` | Uvicorn :8000, restart=always |
| Warm cache | `cruza-warm-cache.service` | Type=oneshot, dispara via workflow |
| **Umami analytics** | `cruza-umami.service` | Self-hosted em `/_traffic/analytics/`, basic-auth + login |
| **GoAccess** | `cruza-goaccess.service` | Dashboard tempo real `/_traffic/goaccess/` |
| Traffic tail | `cruza-traffic-tail.service` | Expõe últimas N linhas do access.log raw |
| Traffic digest | `cruza-traffic-digest.{service,timer}` | Cron diário 10:00 UTC com sumário do dia |
| PG auto-tune | `pg-autotune.service` | Recalcula `shared_buffers`/`effective_cache_size`/`work_mem`/`maintenance_work_mem` por RAM atual da VM |

Outras camadas:

- **Nginx** — gzip, rate-limit zones (`api_heavy` 2 r/s), CSP Report-Only, HSTS, GeoIP anonymize.
- **fail2ban** — jails customizadas para 429 (rate-limit abuse), exploit-paths (`/wp-admin`, `/.env`, `/.git`, etc.) e recidive.
- **Let's Encrypt** via certbot (`deploy/setup-letsencrypt.sh`), renovação automática.
- **Service Worker** — `web/static/sw.js` com stale-while-revalidate para `/static/dist/` (cache 1 ano via manifest content-hash).

## SEO

A descobribilidade do transparenciapb.org foi tratada como camada de produto: o objetivo é que jornalistas, pesquisadores e cidadãos encontrem perfis específicos de municípios, empresas e licitações via Google/Bing, não só pela home.

### Sitemap-index com sub-sitemaps shardeados

`web/routes/seo.py` (~38KB, 8 rotas) implementa o pattern recomendado pelo [sitemaps.org](https://www.sitemaps.org/protocol.html#index) para escalar acima do limite de 50.000 URLs por arquivo. Cada sub-sitemap tem cap em **49.000 URLs** (folga vs limite) e é shardeado por inteiro 1-indexed:

```
/sitemap.xml                                       ← sitemapindex (lista os abaixo)
  ├─ /sitemap-cidades.xml                          ← páginas estáticas + 223 /cidade/<slug>
  ├─ /sitemap-empresas-1.xml                       ← empresas 1-49.000          (toggle: enable)
  ├─ /sitemap-empresas-2.xml                       ← empresas 49.001-98.000
  ├─ /sitemap-empresas-{n}.xml                     ← …até cobrir o universo
  ├─ /sitemap-empresas-municipios-{n}.xml          ← /empresa/<cnpj>/<slug>     (toggle: enable)
  ├─ /sitemap-licitacoes-{n}.xml                   ← /licitacao/<mun>/<ano>/<ug>/<modnum>  (toggle: enable)
  └─ /sitemap-cidade-resumo.xml                    ← ~14k /cidade/<slug>/<yyyy>-<mm>  (toggle: enable)
```

URLs cobertas hoje (com todos os toggles ativos): home, sobre, glossário, contato, mapa, 223 cidades PB, ~245k empresas, ~245k pares empresa-município, ~50k licitações cacheadas, ~14k cidade-mês — **~550k URLs no total**.

### Toggles de exposição no `deploy.yml`

Três inputs de `workflow_dispatch` controlam quais sub-sitemaps aparecem no `/sitemap.xml` (default: todos `keep` = preserva estado atual):

| Input | Função | Pré-requisito |
|---|---|---|
| `expose_empresa_sitemap` | `keep` / `enable` / `disable` URLs `/empresa/<cnpj>` e `/empresa/<cnpj>/<slug>` | Cobertura ≥ 80% **dos caches `EMPRESA_PERFIL` e `EMPRESA_PERFIL_MUN`** antes de `enable` |
| `expose_licitacoes_sitemap` | idem para `/licitacao/<mun>/<ano>/<ug>/<modnum>` | Cobertura ≥ 80% do cache `LICITACAO_PERFIL` |
| `expose_cidade_resumo_sitemap` | idem para `/cidade/<slug>/<yyyy>-<mm>` | Cobertura ≥ 80% do cache `CIDADE_RESUMO_MENSAL` |

O workflow falha o deploy com `::error::` se `enable` for usado sem cobertura mínima — evita expor sitemap com 503 nas URLs.

### Caching de sitemap (24h TTL em memória)

`_SITEMAP_CACHE` em `web/routes/seo.py:53` cacheia cada urlset/index 24h. TTL longo é defesa contra "Couldn't fetch" do Google Search Console quando o primeiro hit pós-restart bate em GROUP BY pesado. O COUNT/PAGINATED dos shards usa a MV `mv_empresa_municipio_pagantes` (instantânea via phase 22 `etl.22_mv_sitemap`) em vez de GROUP BY live em ~16M rows.

### Meta tags por página

`web/templates/base.html` injeta em todas as páginas:

- **Canonical** — `canonical_url(request)` strip query params `d_*` (de dialogs JS) para evitar duplicate content.
- **Open Graph** — `og:site_name`, `og:type`, `og:title`, `og:description`, `og:locale=pt_BR`, `og:url`, `og:image`.
- **Twitter Card** — `summary_large_image` com mesmo `og:image`.
- **Verification** — `<meta name="google-site-verification">` e `msvalidate.01` (Bing) injetadas quando `GOOGLE_SITE_VERIFICATION` / `BING_SITE_VERIFICATION` estão setadas no `.env`. Bing também alimenta DuckDuckGo, ChatGPT search e Yahoo.

### OG image dinâmica

`web/routes/og_image.py` gera previews via Pillow para a home e perfis de cidade:

- **`/og/home.png`** — preview da home (regenerado on-demand).
- **`/og/cidade/<slug>.png`** — preview por município PB, com nome + KPIs principais renderizados.
- Cache em disco em `data/og_cache/` (não versionado).
- Demais páginas (`/empresa/...`, `/licitacao/...`, `/sobre`, `/glossario`) herdam o `og:image` default da home; `/caso/<slug>` usa imagem estática custom servida via `meta.og_image`.

Plano: estender Pillow rendering para `/empresa/<cnpj>` e `/licitacao/...` quando o volume de share-clicks justificar — por hora, herdar a OG da home já evita o Twitter/WhatsApp default sem preview.

### IndexNow

Protocolo aberto suportado por Bing, Yandex, Yahoo, Seznam e Naver. Submete mudanças de URL sem depender de crawl periódico (acelera indexação de novas páginas de dias para horas).

```bash
# Gerar a key (32+ chars URL-safe)
python -c "import secrets; print(secrets.token_urlsafe(32))"
# Setar INDEXNOW_KEY no .env, redeploy do web

# Submeter URLs novas
python -m web.indexnow_submit
```

A rota `/<key>.txt` serve o conteúdo da key como verificação (exigência do protocolo). Tem regex guard `^[A-Za-z0-9_\-]{8,128}$` + `secrets.compare_digest` timing-safe para reduzir superfície de probing.

### FAQ schema.org structured data

Páginas relevantes incluem JSON-LD com `FAQPage` (`web/templates/partials/seo/_faq.html`) — eleva o resultado no Google Search com FAQ rich snippet e alimenta o ChatGPT search com perguntas estruturadas.

### Configuração

Variáveis no `.env` (todas opcionais; meta tags só aparecem se preenchidas):

| Variável | Origem |
|---|---|
| `GOOGLE_SITE_VERIFICATION` | [Search Console](https://search.google.com/search-console) → adicionar propriedade → "Tag HTML" |
| `BING_SITE_VERIFICATION` | [Bing Webmaster Tools](https://www.bing.com/webmasters) → Add site → "Meta tag" |
| `INDEXNOW_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `SITE_URL` | Origem do site (`https://transparenciapb.org`) |

## Deploy

O deploy roda via **GitHub Actions self-hosted runner** instalado na VM Azure, em 3 jobs:

```
preflight (github-hosted, OIDC) → deploy (self-hosted na VM) → postflight (github-hosted, OIDC)
```

O `preflight` faz resize VM/disco para cima quando o `etl_phase` exige; o `postflight` desce para B2 + Standard SSD quando o trabalho pesado acaba.

**Inputs do `workflow_dispatch`** (resumo):

| Input | Tipo | Função |
|---|---|---|
| `etl_phase` | `web` / `all` / `sql` / `incremental` / `N` | seleciona qual trabalho rodar |
| `clean` | bool | reset destrutivo (apaga tabelas) |
| `skip_download` | bool | usa raw já presente no `DATA_DIR` |
| `warm_cache` | bool | força warm em `etl_phase=web` |
| `run_queries` | bool | roda `etl.run_queries` após ETL |
| `incremental_only` | csv | limita incremental a specs específicas |
| `drop_cache` | bool | TRUNCATE web_cache antes do warm |
| `invalidate_cache_keys` | csv | DELETE cirúrgico HARD por **substring** (`LIKE '%termo%'`); `PERFIL` casa também `EMPRESA_PERFIL` |
| `rewarm_cache_keys` | csv | shadow rewarm zero-downtime (preferido) |
| `cleanup_orphan_empresa_cache` | bool | DELETE entries de `EMPRESA_PERFIL`/`EMPRESA_PERFIL_MUN` para CNPJs fora de `mv_empresa_pb` (após `refresh_mvs=mv_empresa_pb`) |
| `warm_skip_hours` | int | controle de skip/rebuild do warm |
| `expose_empresa_sitemap` / `_licitacoes_` / `_cidade_resumo_` | keep/enable/disable | toggle de URLs no sitemap |
| `download_sources` | csv | re-baixa fontes específicas antes da fase |

### VM Azure (custos)

VM e disco mudam de SKU juntos por hora, então Premium SSD só cobra durante operações pesadas:

| Componente | Leve (web) | Pesado (ETL/warm) | Δ/hora |
|---|---|---|---|
| VM | B2as_v2 (2 vCPU, 8GB) | B4as_v2 (4 vCPU, 16GB) | +$0.07 |
| Disco | Standard SSD E20 | Premium SSD P20 + ReadOnly host caching | +$0.05 |

**Custo típico ~$104/mês** (web base + 1 ETL + 1 warm). Cabe nos $150/mês de crédito Visual Studio Enterprise. Nomes de RG/VM/disco ficam em GitHub Secrets (`AZURE_RESOURCE_GROUP`, `AZURE_VM_NAME`, `AZURE_DATA_DISK_NAME`).

> **Limite Azure:** 2 mudanças de SKU de disco por 24h. Workflow detecta e segue se o limite for atingido.

### Cleanup de disco

O disco de 512GB armazena Postgres (~248GB) + raw downloads (~230GB no pico). O ETL **limpa automaticamente os CSVs brutos** após cada fase com sucesso (`run_all.py:_cleanup_csvs`). Diretórios compartilhados são removidos só quando todas as fases dependentes terminaram.

## Estrutura do repositório

```
sql/              Schema (extensões, tabelas, índices, MVs). 22-29+32+34+35 são do framework incremental.
etl/              Carga e orquestração — 24 fases executadas por run_all
etl/incremental/  Framework incremental (TCE-PB + dados.pb.gov.br)
queries/          125+ queries SQL em 17 arquivos temáticos
resultados/       CSVs gerados pelas queries (versionados)
relatorios/       40 investigações Markdown derivadas dos resultados
web/              Frontend FastAPI + Jinja2 + JS + Material Design 3
web/queries/      QueryDef registry (sql_full + sql_full_dated)
web/static/       Assets — esbuild gera dist/ com content-hash
deploy/           Systemd services, Nginx, fail2ban, setup scripts
scripts/          Build de assets (esbuild), audit de identificadores
docs/             Dicionário de dados, planos, guias (em desenvolvimento)
data/static/      Snapshots binários versionados (comprasnet.csv.gz)
tests/incremental/ Suite atual — cobre o framework incremental
```

## Documentação adicional

Comece pela [arquitetura](docs/architecture.md), depois siga pro guia específico da sua área de contribuição.

### Para todos os contributors

- [`docs/architecture.md`](docs/architecture.md) — **landing page arquitetural** com 7 diagramas Mermaid (data flow ETL, entity resolution, ERD, MV layers, shadow rewarm sequence, deploy pipeline)
- [`docs/glossario.md`](docs/glossario.md) — 60+ termos do domínio público brasileiro (empenho, UG, CEIS, LGPD, etc.)
- [`docs/onboarding.md`](docs/onboarding.md) — walk-through clone → `uvicorn` em 3 caminhos
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — convenções de código, commits, PRs
- [`AGENTS.md`](AGENTS.md) — instruções canônicas para agentes de IA (Copilot CLI, Claude Code, Cursor, Aider, Codex). Inclui mapa de docs, comandos, convenções, quirks descobertos e checklist obrigatório de PR. Veja [ADR-0008](docs/adr/0008-agents-md-canonical.md)

### Guias por área

- [`docs/etl-guide.md`](docs/etl-guide.md) — como adicionar fase ETL clássica
- [`docs/etl-incremental-guide.md`](docs/etl-incremental-guide.md) — como adicionar spec ao framework incremental (princípios P1-P6)
- [`docs/web-guide.md`](docs/web-guide.md) — como adicionar query/rota/template/componente MD3
- [`docs/queries-guide.md`](docs/queries-guide.md) — como adicionar Q## (header, EXPLAIN, índices)
- [`docs/mv-guide.md`](docs/mv-guide.md) — como adicionar MV (camadas L1/L2/L3)
- [`docs/cache.md`](docs/cache.md) — `web_cache` + shadow rewarm zero-downtime

### Operações

- [`docs/deploy.md`](docs/deploy.md) — 14 inputs do `deploy.yml` + cenários + OIDC setup
- [`docs/ops.md`](docs/ops.md) — runbooks (rollback, restore, backup, runner repair, troubleshoot warm)

### Privacidade e licenciamento

- [`docs/privacidade.md`](docs/privacidade.md) — política LGPD pública
- [`DATA-LICENSE.md`](DATA-LICENSE.md) — licenciamento de dados + disclaimer LGPD

### Decisões arquiteturais (ADRs)

- [`docs/adr/`](docs/adr/) — 11 ADRs: no-pandas, MV layered, shadow rewarm, framework incremental, no-ORM web, MV atomic swap, ETL normalize fix, AGENTS.md canonical, orphan empresa cache cleanup, Bolsa Família incremental (ADR-0010), remover LIMIT top tabelas (ADR-0011 Proposed)

### Referência

- [`etl/incremental/README.md`](etl/incremental/README.md) — framework incremental detalhado (P1-P6, observabilidade, comandos)
- [`docs/dicionario_dados_pb.md`](docs/dicionario_dados_pb.md) — catálogo de colunas TCE-PB e dados.pb.gov.br
- [`docs/plano_novas_fontes.md`](docs/plano_novas_fontes.md) — roadmap histórico de fontes (legado)
- [`relatorios/`](relatorios/) — 40+ investigações sobre casos reais (mascaradas conforme LGPD)

## Licença

Código sob [MIT](LICENSE). Os dados públicos têm cada um sua própria licença (Lei 12.527/2011 + LGPD + termos da fonte). Veja `LICENSE` para detalhes.

Para reportar problemas de segurança ou exposição de PII, use [GitHub Security Advisories](https://github.com/lucasdiniz/govbr-cruza-dados/security/advisories) ou [contato@transparenciapb.org](mailto:contato@transparenciapb.org).
