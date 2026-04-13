# govbr-cruza-dados

Pipeline ETL para cruzamento de dados abertos do governo federal brasileiro, voltado para deteccao de fraudes em licitacoes, emendas parlamentares, cartao corporativo, eleicoes e programas sociais.

> **Vibe coded** com [Claude Code](https://claude.ai/claude-code) (Opus 4.6) e Codex (GPT-5.4) - da modelagem do schema ate o ultimo `INSERT INTO`.

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
- **26 relatorios de investigacao** derivados dos resultados
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

## Frontend web

Painel interativo para consulta por municipio com cruzamentos automaticos.

- **Stack**: FastAPI + Jinja2 + vanilla JS, PostgreSQL
- **Cobertura**: 224 municipios da PB com perfil completo (TCE + dados.pb) + qualquer municipio do Brasil via PNCP
- **15 queries de investigacao** organizadas em 6 categorias (conflito de interesse, licitacao, fornecedores, etc.)
- **Dialog de servidor**: ao clicar um servidor, mostra vinculos (admissao, salario), Bolsa Familia e empresas vinculadas
- **Dialog de fornecedor**: ao clicar um fornecedor, mostra dados cadastrais, sancoes CEIS (com datas), divida PGFN e empenhos recentes
- **Cache pre-processado**: tabela `web_cache` + daemon `warm_cache.py` para manter dados prontos
- **Autocomplete**: busca PB (score de risco) + outros estados (PNCP)

```bash
# Iniciar local
python -m uvicorn web.main:app --port 8000

# Cache warmer — PB (1 ciclo)
python -m web.warm_cache --daemon

# Cache warmer — todos os estados (PB + PNCP)
python -m web.warm_cache --all --daemon

# Cache warmer — continuo
python -m web.warm_cache --all --daemon --loop
```

Municipios PB recebem perfil completo com insight cards, servidores de risco, e secoes de investigacao. Municipios de outros estados recebem perfil baseado em contratos PNCP com cruzamento de fornecedores contra CEIS, PGFN e RFB.

## Stack

- **Python 3.10+** - ETL com streaming (sem pandas, cabe em 16GB RAM)
- **PostgreSQL 16** - com `pg_trgm` para fuzzy match de nomes
- **psycopg2** - `COPY FROM STDIN` para carga rapida
- **ijson** - parsing incremental de JSONs do PNCP
- **FastAPI + Jinja2** - frontend web com cache pre-processado

## Infraestrutura

### VM Azure (producao)

| Componente | Especificacao | Custo |
|---|---|---|
| VM | Standard_B4as_v2 (4 vCPU, 16GB RAM) | ~US$110/mes |
| Disco | 512GB Standard SSD (`/data`) | ~US$38/mes |
| Regiao | North Central US | |
| **Total** | | **~US$148/mes** |

O disco de 512GB armazena tanto o PostgreSQL (~248GB) quanto os dados brutos de download (~230GB no pico). Para caber no disco, o ETL **limpa automaticamente os CSVs brutos** apos cada fase completar com sucesso (`run_all.py`). Diretorios compartilhados entre fases (ex: `rfb/`, `tse/`) so sao removidos quando todas as fases dependentes completam.

## Deploy (1 click)

O deploy roda via **GitHub Actions self-hosted runner** instalado na VM.

### Pre-requisitos

1. **VM Ubuntu** com SSH e disco de dados montado em `/data`
2. **Fork** deste repositorio
3. **Secrets obrigatorios** (Settings > Secrets > Actions):
   - `VM_HOST` — IP ou hostname da VM
   - `VM_SSH_KEY` — chave SSH privada do usuario `govbr`
   - `DB_PASSWORD` — senha do PostgreSQL
   - `ENV_FILE` — conteudo do `.env` (ver `.env.example`)
4. **Secret opcional**:
   - `RUNNER_ADMIN_TOKEN` — PAT para instalar/reparar o self-hosted runner

### Execucao

```bash
# Passo 1: Instalar o runner na VM (1x)
# Actions > "Setup Self-Hosted Runner" > Run workflow

# Passo 2: Rodar o ETL completo
# Actions > "Deploy to Azure VM" > Run workflow (etl_phase=all)
```

O workflow instala PostgreSQL 16, Python, Tor (fallback para downloads bloqueados), clona o repo, baixa os dados e popula o banco. Live logs disponiveis durante toda a execucao. Timeout maximo: 5 dias (limite do GitHub self-hosted runner). Duracao tipica: 10-20h dependendo da rede.

### Opcoes do deploy

| Parametro | Descricao |
|---|---|
| `etl_phase=all` | ETL completo (download + carga + indices + views) |
| `etl_phase=sql` | Apenas schema, indices e views (rapido) |
| `etl_phase=N` | Retomar a partir da fase N (ex: `19` para TCE-PB) |
| `skip_download=true` | Pular downloads, usar dados ja existentes na VM |
| `clean=true` | Limpar estado anterior (apaga tabelas, re-ETL do zero) |

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
relatorios/    26 investigacoes baseadas nos resultados (Markdown)
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
