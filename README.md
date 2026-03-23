# govbr-cruza-dados

Pipeline ETL para cruzamento de dados abertos do governo federal brasileiro, voltado para detecao de fraudes em licitacoes, emendas parlamentares, cartao corporativo, eleicoes e programas sociais.

> **Vibe coded** com [Claude Code](https://claude.ai/claude-code) (Opus 4.6) - da modelagem do schema ate o ultimo `INSERT INTO`.

## O que faz

Carrega ~40GB de dados de **18+ fontes publicas** num banco PostgreSQL (~330M registros) e cruza tudo pelo CNPJ/CPF para encontrar padroes suspeitos:

- **Receita Federal** (66M empresas, 69.8M estabelecimentos, 27M socios, 47M simples)
- **TCE-PB** - despesas, servidores, licitacoes e receitas municipais da Paraiba (39M registros, 237 municipios)
- **dados.pb.gov.br** - pagamentos, empenhos, contratos, saude e convenios estaduais PB (~7.8M registros)
- **PNCP** - licitacoes e contratos publicos (3M contratacoes, 3.7M contratos)
- **Emendas Parlamentares** - Tesouro + TransfereGov (1.2M registros)
- **CPGF** - cartao corporativo do governo (645k transacoes)
- **PGFN** - divida ativa da Uniao (39.9M inscricoes)
- **TSE** - candidatos + bens + prestacao de contas (2.1M candidatos, 4M bens, 8.3M receitas/despesas)
- **Bolsa Familia** - beneficiarios e pagamentos (20.9M registros)
- **SIAPE** - servidores federais (cadastro + remuneracao)
- **BNDES** - emprestimos do banco de desenvolvimento
- **Holdings** - estrutura de controle societario entre empresas
- **ComprasNet** - contratos historicos (pre-PNCP)
- **Renuncias Fiscais** - beneficios e isencoes tributarias
- **Viagens a Servico** - passagens e diarias (3.9M registros)
- **Sancoes** - CEIS/CEPIM/CNEP (empresas e pessoas sancionadas)

## Queries de investigacao

42+ queries prontas organizadas em 10 categorias:

| Categoria | Queries | Exemplos |
|---|---|---|
| **Fraude em licitacao** | Q01-Q08 | Empresas do mesmo grupo disputando mesma licitacao (bid rigging), empresa-fachada recem-criada ganhando contrato grande |
| **Cartao corporativo** | Q09-Q14 | Portador com gastos concentrados em unico fornecedor, fracionamento de despesa, portador socio de empresa favorecida |
| **Emendas parlamentares** | Q15-Q20 | Parlamentar que beneficia repetidamente o mesmo favorecido, emenda para empresa com divida ativa |
| **Redes societarias** | Q21-Q26 | Pessoa socia de muitas empresas fornecedoras, socios laranjas (faixa etaria extrema), cadeia de holdings |
| **Cruzamento multi-fonte** | Q27-Q32 | Empresa que recebe BNDES + contratos + emendas, empresa inativa recebendo pagamentos |
| **Fraude eleitoral (TSE)** | Q33-Q37 | Doacao de empresa com divida ativa, candidato que recebe e gasta com mesma empresa, patrimonio incompativel |
| **Bolsa Familia** | Q38-Q42 | Servidor federal recebendo BF, socio de empresa ativa recebendo BF, candidato com patrimonio recebendo BF |
| **Superfaturamento** | Q43-Q58 | Preco unitario muito acima da mediana, fornecedor unico repetido |
| **TCE-PB / dados.pb** | Q59-Q77 | Servidor socio de fornecedor, empresa inativa recebendo pagamento estadual, fracionamento de despesa municipal |
| **Padroes temporais** | transversal | Picos de emendas em anos eleitorais, fornecedor dominante num orgao |

## Stack

- **Python 3.10+** - ETL com streaming (sem pandas, cabe em 16GB RAM)
- **PostgreSQL 16** - com pg_trgm para fuzzy match de nomes
- **psycopg2** - COPY FROM STDIN para carga rapida
- **ijson** - parsing incremental de JSONs do PNCP

## Uso rapido

```bash
# 1. Configurar
cp .env.example .env
# Editar .env com credenciais do PostgreSQL e DATA_DIR

# 2. Instalar
pip install -e .

# 3. Subir PostgreSQL (ou usar um existente)
docker compose up -d

# 4. Rodar ETL completo (19 fases, ~4-6h dependendo do disco)
python -m etl.run_all

# 5. Rodar fase especifica (ex: so fase 4 = PNCP)
python -m etl.run_all 4

# 6. Exportar resultados das queries de fraude
python -m etl.run_queries              # todas as 42 queries
python -m etl.run_queries --query Q03  # query especifica
```

## Estrutura

```
sql/           Schema do banco (extensoes, tabelas, indices, views materializadas)
etl/           Scripts de carga por fonte de dados (20 fases, 18+ fontes)
queries/       42+ queries SQL prontas para investigacao de fraudes
resultados/    CSVs com resultados das queries (gitignored)
relatorios/    Investigacoes baseadas nos resultados (Markdown)
```

## Fontes de dados

Os dados brutos devem ser baixados separadamente dos portais oficiais:

- [Receita Federal - CNPJ](https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj)
- [PNCP](https://pncp.gov.br/api/consulta/swagger-ui/index.html)
- [Portal da Transparencia](https://portaldatransparencia.gov.br/download-de-dados)
- [PGFN](https://www.gov.br/pgfn/pt-br/assuntos/divida-ativa-da-uniao/transparencia-fiscal-1)
- [BNDES](https://dadosabertos.bndes.gov.br/)
- [TSE - Prestacao de Contas](https://dadosabertos.tse.jus.br/)
- [Bolsa Familia / SIAPE / CPGF / Viagens / Sancoes](https://portaldatransparencia.gov.br/download-de-dados)
- [TCE-PB - Dados Consolidados](https://dados-abertos.tce.pb.gov.br/dados-consolidados) (despesas, servidores, licitacoes, receitas municipais PB)
- [dados.pb.gov.br](https://dados.pb.gov.br/app/) (pagamentos, empenhos, contratos estaduais PB)

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

O pipeline normaliza automaticamente (fase 14) criando colunas indexadas com apenas os digitos (`cpf_digitos`, `cpf_cnpj_norm`), permitindo JOINs por igualdade direta entre fontes. Match por **nome + 6 digitos CPF** virtualmente elimina falsos positivos.

Complementarmente:
- Tabela `pessoa` com entity resolution probabilistica
- Fuzzy matching via `pg_trgm` para nomes similares

## Licenca

MIT
