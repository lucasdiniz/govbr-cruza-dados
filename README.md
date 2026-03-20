# govbr-cruza-dados

Pipeline ETL para cruzamento de dados abertos do governo federal brasileiro, voltado para detecao de fraudes em licitacoes, emendas parlamentares e cartao corporativo.

> **Vibe coded** com [Claude Code](https://claude.ai/claude-code) (Opus 4.6) - da modelagem do schema ate o ultimo `INSERT INTO`.

## O que faz

Carrega ~28GB de dados de **10+ fontes publicas** num banco PostgreSQL e cruza tudo pelo CNPJ/CPF para encontrar padroes suspeitos:

- **Receita Federal** (66M empresas, 60M+ estabelecimentos, 27M socios)
- **PNCP** - licitacoes e contratos publicos (3M contratacoes, 3.7M contratos)
- **Emendas Parlamentares** - Tesouro + TransfereGov (1.2M registros)
- **CPGF** - cartao corporativo do governo (645k transacoes)
- **PGFN** - divida ativa da Uniao (40M inscricoes)
- **BNDES** - emprestimos do banco de desenvolvimento
- **Holdings** - estrutura de controle societario entre empresas
- **ComprasNet** - contratos historicos (pre-PNCP)
- **Renuncias Fiscais** - beneficios e isencoes tributarias

## Queries de investigacao

20 queries prontas organizadas em 6 categorias:

| Categoria | Exemplos |
|---|---|
| **Fraude em licitacao** | Empresas do mesmo grupo disputando mesma licitacao (bid rigging), empresa-fachada recem-criada ganhando contrato grande |
| **Emendas parlamentares** | Parlamentar que beneficia repetidamente o mesmo favorecido, emenda para empresa com divida ativa |
| **Cartao corporativo** | Portador com gastos concentrados em unico fornecedor, fracionamento de despesa (valores logo abaixo de limites) |
| **Redes societarias** | Pessoa socia de muitas empresas fornecedoras, socios laranjas (faixa etaria extrema), cadeia de holdings |
| **Cruzamento multi-fonte** | Empresa que recebe BNDES + contratos + emendas, empresa inativa recebendo pagamentos |
| **Padroes temporais** | Picos de emendas em anos eleitorais, fornecedor dominante num orgao |

## Stack

- **Python 3.10+** - ETL com streaming (sem pandas, cabe em 16GB RAM)
- **PostgreSQL 16** - com pg_trgm para fuzzy match de nomes
- **psycopg2** - COPY FROM STDIN para carga rapida
- **ijson** - parsing incremental de JSONs do PNCP

## Uso rapido

```bash
# 1. Configurar
cp .env.example .env
# Editar .env com credenciais do PostgreSQL

# 2. Instalar
pip install -e .

# 3. Subir PostgreSQL (ou usar um existente)
docker compose up -d

# 4. Rodar ETL completo (~2-3h)
python -m etl.run_all

# 5. Rodar fase especifica (ex: so fase 4 = PNCP)
python -m etl.run_all 4
```

## Estrutura

```
sql/           Schema do banco (extensoes, tabelas, indices, views materializadas)
etl/           Scripts de carga por fonte de dados
queries/       20 queries SQL prontas para investigacao de fraudes
```

## Fontes de dados

Os dados brutos devem ser baixados separadamente dos portais oficiais:

- [Receita Federal - CNPJ](https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj)
- [PNCP](https://pncp.gov.br/api/consulta/swagger-ui/index.html)
- [Portal da Transparencia](https://portaldatransparencia.gov.br/download-de-dados)
- [PGFN](https://www.gov.br/pgfn/pt-br/assuntos/divida-ativa-da-uniao/transparencia-fiscal-1)
- [BNDES](https://dadosabertos.bndes.gov.br/)

## Entity Resolution

CPFs aparecem mascarados na maioria das bases (`***.456.789-**`). O sistema usa uma abordagem probabilistica para resolver identidades:

- Tabela `pessoa` sem constraint UNIQUE (aceita possiveis duplicatas)
- Tabela `pessoa_merge` com scores de confianca por metodo de match
- Fuzzy matching via `pg_trgm` para nomes similares

## Licenca

MIT
