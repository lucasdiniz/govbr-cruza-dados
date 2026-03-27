# govbr-cruza-dados

Pipeline ETL para cruzamento de dados abertos do governo federal brasileiro, voltado para detecao de fraudes em licitacoes, emendas parlamentares, cartao corporativo, eleicoes e programas sociais.

> **Vibe coded** com [Claude Code](https://claude.ai/claude-code) (Opus 4.6) - da modelagem do schema ate o ultimo `INSERT INTO`.

## O que faz

Carrega ~100GB de dados de **18+ fontes publicas** num banco PostgreSQL (~336M registros, 186GB) e cruza tudo pelo CNPJ/CPF para encontrar padroes suspeitos:

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
- **ComprasNet** - contratos federais historicos (pre-PNCP, 104k contratos incluidos no repo)
- **Renuncias Fiscais** - beneficios e isencoes tributarias
- **Viagens a Servico** - passagens e diarias (3.9M registros)
- **Sancoes** - CEIS/CEPIM/CNEP (empresas e pessoas sancionadas)

## Queries de investigacao

75 queries prontas organizadas em 11 categorias (764k resultados):

| Categoria | Queries | Exemplos |
|---|---|---|
| **Fraude em licitacao** | Q01-Q08 | Empresas do mesmo grupo disputando mesma licitacao (bid rigging), empresa-fachada recem-criada ganhando contrato grande |
| **Cartao corporativo** | Q09-Q14 | Portador com gastos concentrados em unico fornecedor, fracionamento de despesa, portador socio de empresa favorecida |
| **Emendas parlamentares** | Q15-Q20 | Parlamentar que beneficia repetidamente o mesmo favorecido, emenda para empresa com divida ativa |
| **Redes societarias** | Q21-Q26 | Pessoa socia de muitas empresas fornecedoras, socios laranjas (faixa etaria extrema), cadeia de holdings |
| **Cruzamento multi-fonte** | Q27-Q32 | Empresa que recebe BNDES + contratos + emendas, empresa inativa recebendo pagamentos |
| **Fraude eleitoral (TSE)** | Q33-Q37 | Doacao de empresa com divida ativa, candidato que recebe e gasta com mesma empresa, patrimonio incompativel |
| **Bolsa Familia** | Q38-Q42 | Servidor federal recebendo BF, socio de empresa ativa recebendo BF, candidato com patrimonio recebendo BF |
| **Superfaturamento** | Q43-Q53 | Sobrepreco valor homologado vs estimado, aditivos suspeitos, dispensas anormais, capital social minimo |
| **TCE-PB municipal** | Q59-Q77 | Servidor socio de fornecedor (32k), cartel estadual, empresa inativa, sancionado CEIS, fracionamento |
| **dados.pb estadual** | Q78-Q91 | Auto-contratacao PF/PJ, credor=candidato TSE, empresa dominante estado+municipio, saude sancionado |
| **Padroes temporais** | transversal | Picos de emendas em anos eleitorais, queima de orcamento dezembro |

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
python -m etl.run_queries              # todas as 75 queries
python -m etl.run_queries --query Q03  # query especifica
```

## Estrutura

```
sql/           Schema do banco (extensoes, tabelas, indices, views materializadas)
etl/           Scripts de carga por fonte de dados (22 fases, 18+ fontes)
queries/       75 queries SQL prontas para investigacao de fraudes
resultados/    CSVs com resultados das queries (gitignored)
relatorios/    Investigacoes baseadas nos resultados (Markdown)
data/static/   Dados estaticos incluidos no repo (comprasnet.csv.gz)
```

## Fontes de dados

A maioria dos dados e baixada automaticamente via `python -m etl.00_download`:

| Fonte | URL | Download |
|-------|-----|----------|
| Receita Federal (CNPJ) | [dadosabertos.rfb.gov.br](https://dadosabertos.rfb.gov.br/CNPJ/) | Automatico (~30GB) |
| PGFN (divida ativa) | [dadosabertos.pgfn.gov.br](https://dadosabertos.pgfn.gov.br/) | Automatico (trimestral) |
| PNCP (licitacoes) | [pncp.gov.br](https://pncp.gov.br/) | Via API (`etl.download_pncp`) |
| Portal da Transparencia | [portaldatransparencia.gov.br](https://portaldatransparencia.gov.br/download-de-dados) | Automatico (CPGF, viagens, siape, sancoes, emendas, renuncias) |
| BNDES | [dadosabertos.bndes.gov.br](https://dadosabertos.bndes.gov.br/) | Automatico |
| TSE | [dadosabertos.tse.jus.br](https://dadosabertos.tse.jus.br/) | Manual |
| Bolsa Familia | [portaldatransparencia.gov.br](https://portaldatransparencia.gov.br/download-de-dados) | Manual (20.9M rows) |
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

O pipeline normaliza automaticamente (fase 14) criando colunas indexadas com apenas os digitos (`cpf_digitos`, `cpf_cnpj_norm`), permitindo JOINs por igualdade direta entre fontes. Match por **nome + 6 digitos CPF** virtualmente elimina falsos positivos.

Match por **nome + 6 digitos CPF** entre fontes distintas (ex: socio × servidor × bolsa familia) virtualmente elimina falsos positivos mesmo com CPFs mascarados. Quando disponivel (CEIS, dados.pb pagamento), match exato por CPF 11 digitos.

## Licenca

MIT
