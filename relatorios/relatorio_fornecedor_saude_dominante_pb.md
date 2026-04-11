# Relatorio de Investigacao: Fornecedores Dominantes de Saude na Paraiba

**Data de Geracao:** 11 de abril de 2026
**Base de Dados:** Query Q310 -- `tce_pb_despesa` (funcao saude) x `empresa` (RFB)
**Metodologia:** agregacao de despesas municipais da funcao saude (codigo_funcao = '10') por CNPJ basico, identificando empresas presentes em 5+ municipios e ranqueadas por capilaridade e volume.

> **Disclaimer:** Este relatorio apresenta cruzamentos automatizados de dados publicos. A presenca como fornecedor dominante nao implica irregularidade automatica -- a concentracao pode refletir escassez de fornecedores, especializacao legitima ou economias de escala. Porem, dominancia extrema em muitos municipios pode indicar cartelizacao, direcionamento de licitacoes ou dependencia critica de fornecedor unico.

---

## 1. Resumo Executivo

O setor saude nos municipios da Paraiba movimenta bilhoes em despesas publicas. A analise identificou um alto grau de concentracao: poucas empresas atendem dezenas ou centenas de municipios simultaneamente.

| Metrica | Valor |
|---|---|
| Empresas fornecedoras de saude (total) | **74.149** |
| Com presenca em 5+ municipios | **14.603** (20%) |
| Com presenca em 20+ municipios | **1.363** (2%) |
| Com presenca em 50+ municipios | **342** |
| Com presenca em 100+ municipios | **90** |

Dos 223 municipios da Paraiba, uma unica distribuidora de energia atende 214 (96%) na funcao saude (contas de luz de unidades de saude), e o principal fornecedor de servicos medicos (Instituto Walfredo Guedes Pereira) atende 166 municipios (74%).

---

## 2. Top 30 Fornecedores de Saude por Capilaridade

| # | Empresa | CNPJ basico | Municipios | Total saude (R$) | Empenhos |
|---|---|---|---|---|---|
| 1 | Energisa Paraiba | 09095183 | **214** | 69.858.414 | 25.697 |
| 2 | Instituto Walfredo Guedes Pereira | 09124165 | **166** | 346.575.260 | 1.941 |
| 3 | Clinica Dom Rodrigo Ltda | 00853492 | **141** | 72.275.436 | 3.293 |
| 4 | Cirurgica Montebello Ltda | 08674752 | **139** | 17.511.200 | 6.215 |
| 5 | Banco do Brasil S/A | 00000000 | **133** | 5.689.017 | 52.314 |
| 6 | Pharmaplus Ltda | 03817043 | **120** | 13.232.855 | 4.392 |
| 7 | Drogafonte Ltda | 08778201 | **115** | 24.452.047 | 6.000 |
| 8 | Paulo Jose Maia Esmeraldo Sobreira | 09210219 | **109** | 1.445.864 | 1.074 |
| 9 | Allfamed Comercio Atacadista de Medicamentos | 31187918 | **107** | 129.054.821 | 9.163 |
| 10 | Caixa Economica Federal | 00360305 | **106** | 6.794.430 | 16.388 |
| 11 | Fiori Veiculo Ltda | 35715234 | **104** | 30.003.499 | 585 |
| 12 | Dantas Eletromoveis e Equipamentos | 49140067 | **104** | 2.505.200 | 261 |
| 13 | Clinica Radiologica Azuir Lessa Ltda | 09136540 | **104** | 1.042.184 | 1.325 |
| 14 | Telemar Norte Leste S/A | 33000118 | **103** | 5.608.771 | 4.716 |
| 15 | Edilane da Costa Carvalho | 12710916 | **102** | 6.052.320 | 289 |
| 16 | Nova Diagnostico por Imagem Ltda | 04489715 | **101** | 1.022.386 | 791 |
| 17 | CAGEPA | 09123654 | **98** | 9.106.704 | 16.616 |
| 18 | Dentalmed Produtos para Saude Ltda | 34698454 | **91** | 6.478.635 | 803 |
| 19 | **Clinica Radiologica Dr. Wanderley Ltda** | **08716557** | **90** | **15.916.517** | 4.209 |
| 20 | Hospital de Oftalmologia de Campina Grande | 13857429 | **90** | 929.275 | 808 |
| 21 | Endovideo Sociedade Simples Ltda | 41139239 | **89** | 394.616 | 330 |
| 22 | Odontomed Comercio Prod. Medico Hospitalares | 09478023 | **88** | 3.954.720 | 1.398 |
| 23 | Drogaria Drogavista Ltda | 00958548 | **84** | 26.232.714 | 16.647 |
| 24 | Dentemed Equipamentos Odontologicos | 07897039 | **84** | 2.173.027 | 211 |
| 25 | Porto Seguro Cia de Seguros Gerais | 61198164 | **82** | 3.644.431 | 1.699 |
| 26 | INSS | 29979036 | **81** | 268.727.731 | 37.228 |
| 27 | Celia Francisco de Carvalho | 15659814 | **81** | 4.674.987 | 192 |
| 28 | CRM Comercial Ltda | 04679119 | **81** | 1.778.257 | 484 |
| 29 | Hospital Antonio Targino Ltda | 08834137 | **80** | 50.720.747 | 1.184 |
| 30 | Mais Truck Comercio de Caminhoes Ltda | 17792470 | **80** | 35.207.203 | 1.622 |

---

## 3. Analise por Segmento

### 3.1. Servicos medicos especializados -- maior risco de monopolio

| Empresa | Municipios | Total (R$) | Segmento |
|---|---|---|---|
| Instituto Walfredo Guedes Pereira | 166 | 346,6M | Diagnostico/tratamento |
| Clinica Dom Rodrigo | 141 | 72,3M | Clinica medica |
| Clinica Radiologica Azuir Lessa | 104 | 1,0M | Radiologia |
| Nova Diagnostico por Imagem | 101 | 1,0M | Imagem/diagnostico |
| **Clinica Radiologica Dr. Wanderley** | **90** | **15,9M** | **Radiologia** |
| Hospital Oftalmologia CG | 90 | 929K | Oftalmologia |
| Endovideo | 89 | 395K | Endoscopia/video |
| Hospital Antonio Targino | 80 | 50,7M | Hospital geral |

O **Instituto Walfredo Guedes Pereira** se destaca com R$ 346,6M em 166 municipios -- o maior fornecedor de saude do estado em volume financeiro e capilaridade combinados.

A **Clinica Radiologica Dr. Wanderley** (90 municipios, R$ 15,9M) ja foi identificada em relatorios anteriores deste projeto como fornecedor com padrao atipico de dominancia.

### 3.2. Distribuicao farmaceutica -- cadeia concentrada

| Empresa | Municipios | Total (R$) |
|---|---|---|
| Allfamed Com. Atacadista Medicamentos | 107 | 129,1M |
| Pharmaplus | 120 | 13,2M |
| Drogafonte | 115 | 24,5M |
| Drogaria Drogavista | 84 | 26,2M |
| Dentalmed Prod. Saude | 91 | 6,5M |
| Cirurgica Montebello | 139 | 17,5M |
| Odontomed | 88 | 4,0M |

As **7 maiores distribuidoras farmaceuticas** juntas atendem quase todos os municipios do estado, com volume combinado superior a **R$ 220 milhoes**. A Allfamed lidera em valor (R$ 129M) enquanto a Cirurgica Montebello lidera em capilaridade (139 municipios).

### 3.3. Veiculos e equipamentos

| Empresa | Municipios | Total (R$) |
|---|---|---|
| Fiori Veiculo | 104 | 30,0M |
| Mais Truck Comercio Caminhoes | 80 | 35,2M |
| Dantas Eletromoveis | 104 | 2,5M |

Compra de veiculos (ambulancias) e equipamentos para unidades de saude tambem apresenta alta concentracao. A Fiori Veiculo (104 municipios, R$ 30M) e a Mais Truck (80 municipios, R$ 35,2M) dominam o segmento.

### 3.4. Pessoa fisica fornecedora em 100+ municipios

| Nome | Municipios | Total (R$) |
|---|---|---|
| Paulo Jose Maia Esmeraldo Sobreira | 109 | 1,4M |
| Edilane da Costa Carvalho | 102 | 6,1M |
| Celia Francisco de Carvalho | 81 | 4,7M |

Pessoas fisicas fornecendo para 80-109 municipios e um padrao atipico que merece investigacao. Pode indicar intermediarios, representantes comerciais ou prestadores de servico com rede incomum de contratos.

---

## 4. Indicadores de Risco

### 4.1. Valor medio por empenho muito alto

| Empresa | Total (R$) | Empenhos | Valor medio/empenho |
|---|---|---|---|
| Instituto Walfredo Guedes Pereira | 346,6M | 1.941 | **R$ 178.555** |
| Fiori Veiculo | 30,0M | 585 | **R$ 51.289** |
| Mais Truck | 35,2M | 1.622 | **R$ 21.708** |
| Hospital Antonio Targino | 50,7M | 1.184 | **R$ 42.838** |

Valores medios acima de R$ 50.000 por empenho, combinados com presenca em dezenas de municipios, sugerem contratos de alto valor repetidos em escala.

### 4.2. Concentracao de valor em poucos fornecedores

Os **5 maiores fornecedores por valor** (excluindo concessionarias e bancos) concentram:

| Empresa | Total saude (R$) |
|---|---|
| Instituto Walfredo Guedes Pereira | 346,6M |
| INSS (contribuicoes patronais) | 268,7M |
| Allfamed | 129,1M |
| Clinica Dom Rodrigo | 72,3M |
| Hospital Antonio Targino | 50,7M |
| **Subtotal top 5** | **~R$ 867M** |

---

## 5. Fundamentacao Juridica

- **Art. 3 da Lei 14.133/21**: licitacao destina-se a garantir a selecao da proposta mais vantajosa, observados os principios da competitividade e da economicidade.
- **Art. 75, II da Lei 14.133/21**: dispensa de licitacao por valor (ate R$ 50.000 para bens/servicos) nao deve ser fracionada para evitar limites.
- **Art. 37, XXI da CF/88**: obras, servicos, compras e alienacoes serao contratados mediante licitacao publica que assegure igualdade de condicoes.
- **Resolucao TCE-PB 01/2019**: normas de fiscalizacao de contratos municipais.
- **Lei 12.529/2011** (CADE): infracos a ordem economica por dominancia de mercado e cartel.

---

## 6. Recomendacoes

1. **Auditar o Instituto Walfredo Guedes Pereira** -- R$ 346,6M em 166 municipios e dominancia extrema. Verificar se ha licitacao ou contrato padronizado e se houve competicao real.
2. **Investigar cadeia farmaceutica concentrada** -- 7 distribuidoras dominam o fornecimento de medicamentos para quase todos os 223 municipios. Verificar se ha rodizio ou conluio entre elas.
3. **Cruzar fornecedores dominantes com licitacoes** -- verificar se empresas presentes em 100+ municipios participam de licitacoes competitivas ou sao contratadas por dispensa/inexigibilidade.
4. **Verificar pessoas fisicas fornecedoras em 80+ municipios** -- padroes atipicos que podem indicar intermediacao ou fachada.
5. **Comparar precos praticados** -- fornecedores dominantes tem poder de mercado que pode resultar em precos acima do referencial. Cruzar com PNCP para comparar valores unitarios.
