# govbr-cruza-dados

Pipeline ETL para cruzamento de dados abertos do governo federal brasileiro, voltado para deteccao de fraudes em licitacoes, emendas parlamentares, cartao corporativo, eleicoes e programas sociais.

> **Vibe coded** com Github Copilot, [Claude Code](https://claude.ai/claude-code), e Codex (Opus 4.6, Opus 4.7, GPT-5.4 e GPT 5.5) - da modelagem do schema ate o ultimo `INSERT INTO`.

## O que faz

Carrega **~350M registros (~210GB)** de **18+ fontes publicas** em um banco PostgreSQL e cruza tudo por CNPJ/CPF para encontrar padroes suspeitos, conflitos de interesse e anomalias de contratacao:

- **Receita Federal** (66M empresas, 69.8M estabelecimentos, 27M socios, 47M simples)
- **TCE-PB** - despesas, servidores, licitacoes e receitas municipais da Paraiba (39M registros, 237 municipios)
- **dados.pb.gov.br** - pagamentos, empenhos, contratos, saude, convenios e 11 datasets auxiliares estaduais PB (~14.4M registros)
- **PNCP** - licitacoes, contratos e itens publicos
- **Emendas Parlamentares** - Tesouro + TransfereGov
- **CPGF** - cartao corporativo do governo
- **PGFN** - divida ativa da Uniao
- **TSE** - candidatos, bens e prestacao de contas
- **Bolsa Familia** - beneficiarios e pagamentos
- **SIAPE** - servidores federais (cadastro + remuneracao)
- **BNDES** - emprestimos do banco de desenvolvimento
- **ComprasNet** - contratos federais historicos (pre-PNCP, base estatica incluida no repo)
- **Renuncias Fiscais** - beneficios e isencoes tributarias
- **Viagens a Servico** - passagens e diarias
- **Sancoes** - CEIS, CNEP, CEAF e acordos de leniencia

O repositorio hoje inclui:

- **23 fases de ETL** orquestradas por `python -m etl.run_all`
- **125+ queries SQL** em 17 arquivos tematicos (`Q01-Q310`)
- **40 relatorios de investigacao** derivados dos resultados
- **Views materializadas** para perfil de empresa, pessoa, rede societaria e score de risco

## Queries de investigacao

As queries estao organizadas por dominio de analise:

| Arquivo | Faixa | Tema |
|---|---|---|
| `fraude_licitacao.sql` | Q01-Q05 | Licitacao, bid rigging, fornecedor dominante, empresa recem-criada |
| `fraude_emendas.sql` | Q06-Q08, Q20 | Emendas parlamentares, concentracao de favorecidos, divida ativa |
| `fraude_cpgf.sql` | Q09-Q11, Q19 | Cartao corporativo, concentracao de gastos, conflito com socios, fracionamento |
| `fraude_cruzamento.sql` | Q12-Q15 | Cruzamento multi-fonte, beneficio triplo, empresa inativa recebendo pagamentos |
| `fraude_rede_societaria.sql` | Q16-Q18 | Redes societarias, holdings, socios laranjas |
| `fraude_servidores.sql` | Q21-Q24 | Servidores federais, remuneracao, emendas, conflito de interesses |
| `fraude_sancoes.sql` | Q25-Q28 | CEIS, CNEP, CEAF e acordos de leniencia |
| `fraude_viagens.sql` | Q29-Q32 | Viagens a servico, gastos fora do padrao, servidor expulso |
| `fraude_tse.sql` | Q33-Q37 | Candidatos, doadores, patrimonio, sancoes eleitorais |
| `fraude_bolsa_familia.sql` | Q38-Q42 | Bolsa Familia, socios, candidatos, concentracao municipal |
| `fraude_superfaturamento.sql` | Q43-Q58, Q99 | Sobrepreco, aditivos, fracionamento, empresa fenix, ciclo politico-eleitoral |
| `fraude_tce_pb.sql` | Q59-Q68, Q70-Q72, Q74, Q77 | TCE-PB municipal: despesas, servidores, licitacoes e Bolsa Familia |
| `fraude_dados_pb.sql` | Q78-Q91 | dados PB estadual: PF/PJ, saude, convenios, dominancia e splitting |
| `fraude_dados_pb_novos.sql` | Q101-Q111 | dados PB ampliados: NF duplicada, ciclo anulacao, diarias sobrepostas, suplementacoes |
| `fraude_pncp_item.sql` | Q92-Q100 | Itens do PNCP: sobrepreco por item, fracasso repetido e serie temporal |
| `fraude_familia_hugo_motta.sql` | Q201-Q209 | Rede empresarial da familia Hugo Motta na Paraiba |
| `fraude_cruzamentos_avancados.sql` | Q301-Q310 | Duplo vinculo, porta giratoria, BNDES×TSE, saude dominante |

Relatorios ja produzidos cobrem temas como:

- Pejotizacao medica e conflito entre servidor e fornecedor
- Empresas inativas, sancionadas ou com divida ativa recebendo recursos publicos
- Sobrepreco por item no PNCP
- Fracionamento de despesa municipal e estadual
- Empresas relacionadas competindo entre si em licitacoes (PB e nacional)
- Duplo pagamento de notas fiscais e ciclos de anulacao/re-empenho
- Suplementacoes orcamentarias concentradas (empenho-semente)
- Convenios com entidades devedoras da Uniao
- Rede empresarial familiar (caso Hugo Motta: 23 empresas, R$52.8M em contratos publicos)
- Duplo vinculo publico: servidores federais e municipais simultaneos (815 casos PB)
- Porta giratoria: servidores municipais socios de fornecedores (4.616 casos)
- Fornecedores de saude dominantes: monopolio em dezenas de municipios
- BNDES x doador eleitoral: socios de tomadores de credito publico que financiam campanhas
- Inidoneidade ilegal: 33 empresas declaradas inidoneas recebendo R$9.7M de 105 municipios PB

## Frontend web (TransparenciaPB)

Painel interativo para consulta por municipio da Paraiba com cruzamentos automaticos, branded como **TransparenciaPB**.

- **Stack**: FastAPI + Jinja2 + vanilla JS, PostgreSQL, Leaflet para o mapa coropletico
- **Cobertura**: 223 municipios da PB com perfil completo (TCE + dados.pb)
- **Home page**: mapa coropletico da Paraiba em tela cheia com 5 metricas selecionaveis (risco composto, % irregulares, sem licitacao, concentracao top-5, per capita), busca por municipio inline e tema escuro unificado
- **Modo escuro global**: todas as paginas (home + detalhes do municipio) usam a identidade visual escura com aurora + dot-field no fundo
- **Risco composto (0-100)**: score ponderado computado em `mv_municipio_pb_risco` combinando 5 sinais do TCE-PB: compras sem licitacao (30 pts), licitacoes com proponente unico (25 pts), concentracao em dezembro (20 pts), valor empenhado nao pago (15 pts) e folha/receita (10 pts)
- **15 queries de investigacao** em 6 categorias priorizadas por potencial investigativo: Fornecedores Irregulares, Conflito de Interesses, Politico-Eleitoral, Licitacao e Concorrencia, Cruzamento Estado x Municipio, Orcamento e Financeiro
- **Dialog de servidor**: ao clicar um servidor, mostra stats grid (salario, empresas, pagamentos, sancoes), vinculos (admissao, salario), empresas vinculadas com badges (CEIS/CNEP, PGFN, Acordo de Leniencia, empenhos recebidos), Bolsa Familia, expulsoes CEAF e empenhos recebidos pelas empresas durante o vinculo funcional (conflito de interesses temporal)
- **Dialog de fornecedor**: ao clicar um fornecedor, mostra dados cadastrais, sancoes CEIS/CNEP (com datas, disclaimer explicativo, origem, vigencia e abrangencia da sancao com orgao sancionador), divida PGFN, acordos de leniencia (com efeitos e status), empenhos recentes com seletor de municipio, pagamentos durante sancao em outros municipios, graficos de pagamentos mensais e elementos de despesa. Linhas e barras de empenho feitas durante periodo de sancao sao destacadas em vermelho (sancao se aplica ao municipio) ou amarelo (informativo)
- **Destaque de risco com abrangencia de sancao**: fornecedores que receberam pagamentos durante sancao sao destacados em vermelho (sancao se aplica legalmente: inidoneidade, abrangencia nacional, orgao municipal do mesmo municipio) ou amarelo (sancao de outro ente, informativo). Coluna "Abrangencia" mostra escopo da sancao com orgao sancionador. Badges incluem orgao sancionador entre parenteses. Servidores socios de empresas sancionadas (CEIS/CNEP), servidores expulsos (CEAF) e empresas que receberam empenhos sao destacados com legendas explicativas
- **Dialogs fullscreen** com navegacao em pilha (drill-down entre entidades), scroll isolado do fundo
- **Cache pre-processado**: tabela `web_cache` + daemon `warm_cache.py` + endpoint de invalidacao seletiva
- **Cache duplo (all + ano)**: `warm_cache` pre-computa variantes all-time e ano-atual por query. Filtro temporal no frontend usa cache para 01/01-31/12 do ano, queries live para ranges custom
- **Filtro temporal**: barra de datas no perfil PB filtra hero stats, insight cards, fornecedores e todos os finding cards. Servidores (MV) sempre mostram todos os periodos
- **Autocomplete**: restrito aos 223 municipios da PB (via `mv_municipio_pb_risco`)
- **Nginx reverse proxy** para producao (porta 80 → uvicorn 8000, gzip habilitado)
- **Identificacao precisa de fornecedores**: usa `cpf_cnpj` completo (14 digitos) em vez de apenas `cnpj_basico` (8 digitos) para evitar colisoes entre CPFs e CNPJs que compartilham o mesmo prefixo. Queries de sancoes (Q65), doadores eleitorais e empenhos durante sancao filtram com `EXISTS (estabelecimento)` para excluir falsos positivos de CPFs

```bash
# Iniciar local
python -m uvicorn web.main:app --port 8000

# Cache warmer — PB (1 ciclo)
python -m web.warm_cache

# Cache warmer — continuo
python -m web.warm_cache --daemon --loop
```

Todos os municipios da PB recebem perfil completo com insight cards, servidores de risco e secoes de investigacao.

## Stack

- **Python 3.10+** - ETL com streaming (sem pandas, cabe em 16GB RAM)
- **PostgreSQL 16** - com `pg_trgm` para fuzzy match de nomes
- **psycopg2** - `COPY FROM STDIN` para carga rapida
- **ijson** - parsing incremental de JSONs do PNCP
- **FastAPI + Jinja2** - frontend web com cache pre-processado

## Infraestrutura

### VM Azure (producao)

A VM **muda de tamanho automaticamente** dependendo do trabalho — `B2as_v2` (8GB) para servir web normalmente, `B4as_v2` (16GB) durante ETL/views pesados. Ver secao [Auto-resize de VM](#auto-resize-de-vm) abaixo.

| Componente | Spec | Custo/mes (USD) | Custo/mes (BRL ~5.6) |
|---|---|---|---|
| **VM web** (`B2as_v2`, 2 vCPU, 8GB) | uso 100% do mes | ~$55 | ~R$ 308 |
| **VM ETL** (`B4as_v2`, 4 vCPU, 16GB) | uso pontual (~$1.80/dia extra) | $54-108 (variavel) | R$ 300-600 |
| Disco dados (`/data`) | 512GB Standard SSD | ~$38 | ~R$ 213 |
| Disco OS | 32GB Standard SSD | ~$2.40 | ~R$ 13 |
| IP publico estatico | Standard | ~$4 | ~R$ 22 |
| Bandwidth | trafego web normal | ~$1 | ~R$ 6 |
| **Total tipico (apenas web)** | | **~$100** | **~R$ 562** |
| **Total com 1 ETL/mes** | | **~$115** | **~R$ 645** |

> Cabe nos **$150/mes de credito Azure** (Visual Studio Enterprise) com folga de ~$35-50.
> Regiao: **North Central US**. Resource group: `RG-GOVBR-NCUS`. VM: `vm-govbr`.

O disco de 512GB armazena tanto o PostgreSQL (~248GB) quanto os dados brutos de download (~230GB no pico). Para caber no disco, o ETL **limpa automaticamente os CSVs brutos** apos cada fase completar com sucesso (`run_all.py`). Diretorios compartilhados entre fases (ex: `rfb/`, `tse/`) so sao removidos quando todas as fases dependentes completam.

### Auto-resize de VM

O workflow `deploy.yml` tem 3 jobs:

```
preflight (github-hosted, OIDC) → deploy (self-hosted na VM) → postflight (github-hosted, OIDC)
```

| Cenario | Preflight | Steps no deploy | Postflight |
|---|---|---|---|
| `etl_phase=web` (default) | B2as_v2 (8GB) | sync code, restart cruza-web | (nenhum) |
| `etl_phase=web warm_cache=true` | B4as_v2 (16GB) | sync + warm_cache (~20h) | downsize → B2as_v2 |
| `etl_phase=all` | B4as_v2 (16GB) | ETL completo + warm_cache (auto) | downsize → B2as_v2 |
| `etl_phase=sql` | B4as_v2 (16GB) | indices/normalizar/views + warm_cache (auto) | downsize → B2as_v2 |
| `etl_phase=N` | B4as_v2 (16GB) | ETL phase N (warm NAO eh auto, use warm_cache=true) | downsize → B2as_v2 |
| `etl_phase=N run_queries=true warm_cache=true` | B4as_v2 (16GB) | ETL + queries + warm_cache | downsize → B2as_v2 |

**O que acontece:**
1. **Preflight** redimensiona a VM (`az vm deallocate → resize → start`). Valida disponibilidade do SKU antes e faz rollback se resize falhar.
2. **Deploy** roda no self-hosted runner DENTRO da VM. O step `Apply PostgreSQL auto-tuning` detecta a RAM atual e ajusta `shared_buffers / effective_cache / work_mem / maintenance_work_mem`. Os steps de ETL/queries/warm sao opt-in conforme inputs.
3. **Postflight** so roda quando preflight fez upsize E deploy succeeded. Faz downsize de volta para `B2as_v2`. No proximo boot da VM, `pg-autotune.service` re-tuna o postgres antes dele subir.

**Quando o deploy falha no meio**, postflight nao roda — a VM fica em B4as_v2 (16GB) para voce retomar com `etl_phase=N` sem outro resize.

**Tuning detectado automaticamente** (formulas Postgres-best-practices):
- `shared_buffers` = 25% RAM
- `effective_cache_size` = 75% RAM
- `work_mem` = RAM / 128
- `maintenance_work_mem` = 6% RAM (cap 1GB)

### Cache warming (web_cache table)

A tabela `web_cache` armazena resultados pre-computados das queries do frontend (FastAPI le diretamente dela em vez de rodar SQL pesado em request time). Os dados das tabelas mudam APENAS quando o ETL roda, entao o warm-cache foi simplificado:

- `cruza-warm-cache.service` eh `Type=oneshot` e **NAO** tem `[Install]` section (nao auto-inicia no boot).
- Roda 1 ciclo completo (`python -m web.warm_cache --daemon` sem `--loop`) e termina.
- Workflow dispara via `sudo systemctl start --wait cruza-warm-cache` — bloqueia ate completar e propaga exit code.
- Auto-disparado apos `etl_phase=all` ou `etl_phase=sql` (dados/queries mudaram).
- Para `etl_phase=N` ou `etl_phase=web`: opt-in via input `warm_cache=true`.
- Disparo manual na VM: `sudo systemctl start cruza-warm-cache`.

O processo retorna exit 1 quando >5% das queries falham, sinalizando warm parcial. O deploy job marca o step como failed mas o `continue-on-error` garante que o postflight ainda faz downsize da VM (evita deixar B4 ligada por engano). Logs ficam disponiveis via `journalctl -u cruza-warm-cache`.

Tempo esperado: **~20h em B4as_v2 (16GB)** por ciclo completo de 224 municipios PB.

## Deploy (1 click)

O deploy roda via **GitHub Actions self-hosted runner** instalado na VM.

### Pre-requisitos

1. **VM Ubuntu** com SSH e disco de dados montado em `/data`
2. **Fork** deste repositorio
3. **Secrets obrigatorios** (Settings > Secrets > Actions):
   - `VM_HOST` — IP ou hostname da VM
   - `DB_PASSWORD` — senha do PostgreSQL
   - `ENV_FILE` — conteudo do `.env` (ver `.env.example`)
   - `AZURE_CLIENT_ID` — clientId do AD app para OIDC (auto-resize)
   - `AZURE_TENANT_ID` — tenantId Azure
   - `AZURE_SUBSCRIPTION_ID` — subscription com a VM
4. **Secrets opcionais** (apenas para `setup-runner.yml`, nao usados no deploy):
   - `VM_SSH_KEY` — chave SSH privada do usuario `govbr` (instalacao/reparo do runner)
   - `RUNNER_ADMIN_TOKEN` — PAT para registrar/atualizar o self-hosted runner

**Setup do OIDC para auto-resize** (1x, ~5min):

```bash
# Cria AD app + service principal + role no resource group + federated credential
az ad app create --display-name govbr-deploy-github-oidc
APP_ID=<appId-retornado>
az ad sp create --id $APP_ID
SP_ID=$(az ad sp show --id $APP_ID --query id -o tsv)
az role assignment create \
  --assignee-object-id $SP_ID \
  --assignee-principal-type ServicePrincipal \
  --role "Virtual Machine Contributor" \
  --scope /subscriptions/<SUB_ID>/resourceGroups/<RG>

# Federated credential trustando workflow_dispatch da branch main
az ad app federated-credential create --id $APP_ID --parameters '{
  "name": "github-deploy-main",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:<OWNER>/<REPO>:ref:refs/heads/main",
  "audiences": ["api://AzureADTokenExchange"]
}'

# Adiciona secrets no GitHub
gh secret set AZURE_CLIENT_ID --body "$APP_ID"
gh secret set AZURE_TENANT_ID --body "$(az account show --query tenantId -o tsv)"
gh secret set AZURE_SUBSCRIPTION_ID --body "<SUB_ID>"
```

O service principal so tem permissao de mexer em VMs/discos do resource group especifico — nao acessa outras subscriptions, billing, etc.

### Execucao

```bash
# Passo 1: Instalar o runner na VM (1x)
# Actions > "Setup Self-Hosted Runner" > Run workflow

# Passo 2: Rodar o ETL completo
# Actions > "Deploy to Azure VM" > Run workflow (etl_phase=all)
```

O workflow instala PostgreSQL 16, Python, Tor (fallback para downloads bloqueados), clona o repo, baixa os dados e popula o banco. Live logs disponiveis durante toda a execucao. Timeout maximo: 5 dias (limite do GitHub self-hosted runner). Duracao tipica: 10-20h dependendo da rede.

### Opcoes do deploy

| Input | Descricao | Default | VM size |
|---|---|---|---|
| `etl_phase=all` | ETL completo (download + carga + indices + views) + warm_cache auto | — | B4as_v2 (16GB) |
| `etl_phase=sql` | Apenas indices, normalizacao e views + warm_cache auto | — | B4as_v2 (16GB) |
| `etl_phase=web` | Sync de codigo + restart web services | — | B2as_v2 (8GB) |
| `etl_phase=N` | Retomar a partir da fase N (ex: `19` para TCE-PB). Warm NAO auto. | — | B4as_v2 (16GB) |
| `warm_cache=true` | Forca warm_cache em qualquer etl_phase (~20h em B4) | `false` | B4as_v2 (16GB) |
| `run_queries=true` | Roda etl.run_queries (~30min) apos ETL — analises de fraude | `false` | (sem mudanca) |
| `skip_download=true` | Pular downloads, usar dados ja existentes na VM | `false` | (sem mudanca) |
| `clean=true` | Limpar estado anterior (apaga tabelas, re-ETL do zero) | `false` | (sem mudanca) |

**Cenarios tipicos:**
- `etl_phase=web` (sozinho): rapido (~5min), sem warm_cache. Use para deploy de mudancas frontend que nao afetam queries.
- `etl_phase=web warm_cache=true`: deploy + re-warming (~20h em B4). Use apos mudancas em `web/queries/registry.py`.
- `etl_phase=all`: ETL completo + warm_cache automatico. Use para reload completo dos dados.
- `etl_phase=19`: retoma fase 19 sem warm. Adicione `warm_cache=true` se a fase reabastecer dados que afetam o cache.

### Uso local

```bash
# 1. Configurar
cp .env.example .env
# Editar .env com credenciais do PostgreSQL e DATA_DIR

# 2. Instalar
pip install -e .

# 3. Subir PostgreSQL (ou usar um existente)
docker compose up -d

# 4. Rodar ETL completo
python -m etl.run_all

# 5. Retomar a partir de fase especifica (ex: fase 4 = PNCP)
python -m etl.run_all 4

# 6. Exportar resultados das queries de fraude
python -m etl.run_queries              # todas as queries
python -m etl.run_queries --query Q03  # query especifica
```

## Estrutura

```
sql/           Schema do banco (extensoes, tabelas, indices, views materializadas)
etl/           Modulos de carga e orquestracao (23 fases executadas por run_all)
queries/       125+ queries SQL em 17 arquivos tematicos
resultados/    CSVs gerados pelas queries; o repo ja inclui resultados de referencia
relatorios/    40 investigacoes baseadas nos resultados (Markdown)
web/           Frontend web (FastAPI + Jinja2 + JS) — painel por municipio
deploy/        Systemd services e configuracao de deploy
data/static/   Dados estaticos incluidos no repo (comprasnet.csv.gz)
scripts/       Scripts auxiliares (auditoria de identificadores, validacao)
```

## Fontes de dados

Todas baixadas automaticamente via `python -m etl.00_download`:

| Fonte | URL | Tamanho aprox. |
|-------|-----|----------------|
| Receita Federal (CNPJ) | [dadosabertos.rfb.gov.br](https://dadosabertos.rfb.gov.br/CNPJ/) | ~58GB |
| Bolsa Familia | [portaldatransparencia.gov.br](https://portaldatransparencia.gov.br/download-de-dados) | ~2GB (snapshot mais recente) |
| TCE-PB | [dados-abertos.tce.pb.gov.br](https://dados-abertos.tce.pb.gov.br/dados-consolidados) | ~20GB |
| PNCP (itens) | [pncp.gov.br](https://pncp.gov.br/) | ~19GB |
| TSE | [dadosabertos.tse.jus.br](https://dadosabertos.tse.jus.br/) | ~12GB |
| PGFN (divida ativa) | [dadosabertos.pgfn.gov.br](https://dadosabertos.pgfn.gov.br/) | ~11GB |
| PNCP (contratos) | [pncp.gov.br](https://pncp.gov.br/) | ~6GB |
| Viagens a Servico | [portaldatransparencia.gov.br](https://portaldatransparencia.gov.br/download-de-dados) | ~6GB |
| PNCP (contratacoes) | [pncp.gov.br](https://pncp.gov.br/) | ~5GB |
| dados.pb.gov.br | [dados.pb.gov.br](https://dados.pb.gov.br/app/) | ~4GB |
| Emendas Parlamentares | [portaldatransparencia.gov.br](https://portaldatransparencia.gov.br/download-de-dados) | ~1GB |
| SIAPE | [portaldatransparencia.gov.br](https://portaldatransparencia.gov.br/download-de-dados) | ~1.3GB |
| BNDES | [dadosabertos.bndes.gov.br](https://dadosabertos.bndes.gov.br/) | ~1.1GB |
| CPGF | [portaldatransparencia.gov.br](https://portaldatransparencia.gov.br/download-de-dados) | ~210MB |
| Renuncias Fiscais | [portaldatransparencia.gov.br](https://portaldatransparencia.gov.br/download-de-dados) | ~510MB |
| Sancoes | [portaldatransparencia.gov.br](https://portaldatransparencia.gov.br/download-de-dados) | ~240MB |
| ComprasNet | Incluido no repo (`data/static/`) | N/A |

## Entity Resolution

CPFs aparecem mascarados na maioria das bases, com formatos diferentes por fonte:

| Fonte | Formato | Exemplo |
|-------|---------|---------|
| Bolsa Familia / SIAPE / CPGF | `***.456.789-**` | 6 digitos centrais visiveis |
| Socio (RFB) | `***456789**` | 6 digitos centrais, sem pontuacao |
| PGFN | `XXX456.789XX` | 6 digitos centrais, formato proprio |
| CEIS/CNEP | `12345678901` | CPF completo (raro) |
| TCE-PB servidores | `***.456.789-**` | 6 digitos centrais |
| dados.pb.gov.br pagamento | `00045678901` | CPF **completo** (11 digitos) |
| dados.pb.gov.br empenho PF | `***456***` | CPF mascarado (3 digitos centrais) |

O pipeline normaliza automaticamente na **fase 17** criando colunas indexadas com apenas os digitos (`cpf_digitos`, `cpf_cnpj_norm`), permitindo `JOIN`s por igualdade direta entre fontes.

Match por **nome + 6 digitos CPF** entre fontes distintas (ex: socio x servidor x Bolsa Familia) reduz drasticamente falsos positivos mesmo com CPFs mascarados. Quando disponivel (CEIS, dados.pb pagamento), o cruzamento usa CPF completo de 11 digitos.

## Licenca

MIT
