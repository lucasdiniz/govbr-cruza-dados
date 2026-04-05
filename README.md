# govbr-cruza-dados

Pipeline ETL para cruzamento de dados abertos do governo federal brasileiro, voltado para deteccao de fraudes em licitacoes, emendas parlamentares, cartao corporativo, eleicoes e programas sociais.

> **Vibe coded** com [Claude Code](https://claude.ai/claude-code) (Opus 4.6) - da modelagem do schema ate o ultimo `INSERT INTO`.

## O que faz

Carrega ~100GB de dados de **18+ fontes publicas** em um banco PostgreSQL local e cruza tudo por CNPJ/CPF para encontrar padroes suspeitos, conflitos de interesse e anomalias de contratacao:

- **Receita Federal** (66M empresas, 69.8M estabelecimentos, 27M socios, 47M simples)
- **TCE-PB** - despesas, servidores, licitacoes e receitas municipais da Paraiba (39M registros, 237 municipios)
- **dados.pb.gov.br** - pagamentos, empenhos, contratos, saude e convenios estaduais PB (~7.8M registros)
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
- **95 queries SQL** em 14 arquivos tematicos (`Q01-Q100`, com lacunas em `Q52`, `Q69`, `Q73`, `Q75` e `Q76`)
- **32 relatorios Markdown** derivados dos resultados
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
| `fraude_pncp_item.sql` | Q92-Q100 | Itens do PNCP: sobrepreco por item, fracasso repetido e serie temporal |

Relatorios ja produzidos cobrem temas como:

- pejotizacao medica e conflito entre servidor e fornecedor
- empresas inativas, sancionadas ou com divida ativa recebendo recursos publicos
- sobrepreco por item no PNCP
- fracionamento de despesa municipal e estadual
- empresas relacionadas competindo entre si ou recebendo juntas, em recorte PB e nacional
- ciclo politico-financeiro em versao exploratoria, com casos fortes e limites atuais das queries
- risco municipal e score composto na Paraiba

## Stack

- **Python 3.10+** - ETL com streaming (sem pandas, cabe em 16GB RAM)
- **PostgreSQL 16** - com `pg_trgm` para fuzzy match de nomes
- **psycopg2** - `COPY FROM STDIN` para carga rapida
- **ijson** - parsing incremental de JSONs do PNCP

## Deploy (1 click)

O jeito mais facil de rodar o projeto e via GitHub Actions em uma VM Ubuntu:

### Pre-requisitos

1. **VM Ubuntu** com SSH (testado em Azure Standard_D4s_v3, 16GB RAM, disco de dados 400GB+ montado em `/data`)
2. **Fork** deste repositorio
3. **Configurar 4 secrets** no repositorio (Settings > Secrets > Actions):
   - `VM_HOST` — IP ou hostname da VM
   - `VM_SSH_KEY` — chave SSH privada do usuario `govbr` na VM
   - `DB_PASSWORD` — senha do PostgreSQL
   - `ENV_FILE` — conteudo do `.env` (ver `.env.example`)

### Execucao

```bash
# Passo 1: Instalar o runner na VM (1x)
# Actions > "Setup Self-Hosted Runner" > Run workflow

# Passo 2: Rodar o ETL completo
# Actions > "Deploy to Azure VM" > Run workflow (etl_phase=all)
```

O workflow instala PostgreSQL 16, Python, Tor (fallback para downloads bloqueados), clona o repo, baixa ~100GB de dados de 18+ fontes e popula o banco. Live logs disponiveis no GitHub Actions durante toda a execucao. Duracao tipica: 10-20h dependendo da rede.

Opcoes do deploy:
- `etl_phase=all` — ETL completo (download + carga + queries)
- `etl_phase=sql` — apenas schema, indices e views (rapido)
- `etl_phase=N` — iniciar na fase N (ex: `4` para PNCP)
- `skip_download=true` — pular downloads (usar dados ja existentes na VM)
- `clean=true` — limpar estado anterior (apaga tabelas, permite re-ETL do zero)

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

# 5. Rodar fase especifica (ex: iniciar na fase 4 = PNCP)
python -m etl.run_all 4

# 6. Exportar resultados das queries de fraude
python -m etl.run_queries              # todas as 95 queries
python -m etl.run_queries --query Q03  # query especifica
```

## Estrutura

```
sql/           Schema do banco (extensoes, tabelas, indices, views materializadas)
etl/           Modulos de carga e orquestracao (23 fases executadas por run_all)
queries/       95 queries SQL em 14 arquivos tematicos
resultados/    CSVs gerados pelas queries; o repo ja inclui resultados de referencia
relatorios/    32 investigacoes baseadas nos resultados (Markdown)
data/static/   Dados estaticos incluidos no repo (comprasnet.csv.gz)
```

## Fontes de dados

A maioria dos dados e baixada automaticamente via `python -m etl.00_download`:

| Fonte | URL | Download |
|-------|-----|----------|
| Receita Federal (CNPJ) | [dadosabertos.rfb.gov.br](https://dadosabertos.rfb.gov.br/CNPJ/) | Automatico (~30GB) |
| PGFN (divida ativa) | [dadosabertos.pgfn.gov.br](https://dadosabertos.pgfn.gov.br/) | Automatico (trimestral) |
| PNCP (licitacoes/contratos/itens) | [pncp.gov.br](https://pncp.gov.br/) | Via API (`etl.download_pncp`) |
| Portal da Transparencia | [portaldatransparencia.gov.br](https://portaldatransparencia.gov.br/download-de-dados) | Automatico (CPGF, viagens, siape, sancoes, emendas, renuncias, Novo Bolsa Familia) |
| BNDES | [dadosabertos.bndes.gov.br](https://dadosabertos.bndes.gov.br/) | Automatico |
| TSE | [dadosabertos.tse.jus.br](https://dadosabertos.tse.jus.br/) | Automatico (ZIPs por ano para candidatos, bens e prestacao) |
| Bolsa Familia | [portaldatransparencia.gov.br](https://portaldatransparencia.gov.br/download-de-dados) | Automatico (mensal, com extracao do ZIP) |
| TCE-PB | [dados-abertos.tce.pb.gov.br](https://dados-abertos.tce.pb.gov.br/dados-consolidados) | Automatico |
| dados.pb.gov.br | [dados.pb.gov.br](https://dados.pb.gov.br/app/) | Automatico |
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
