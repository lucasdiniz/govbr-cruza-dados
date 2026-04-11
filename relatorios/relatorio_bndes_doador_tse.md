# Relatorio de Investigacao: Socios de Tomadores BNDES que Doam para Campanhas Eleitorais

**Data de Geracao:** 11 de abril de 2026
**Base de Dados:** Query Q306 -- `bndes_contrato` x `socio` (RFB) x `tse_receita_candidato`
**Metodologia:** cruzamento de socios de empresas com emprestimos BNDES (> R$ 500K) com doadores de campanhas eleitorais (TSE) por 6 digitos centrais do CPF + nome normalizado. Apenas doacoes PF > R$ 10.000.

> **Disclaimer:** Este relatorio apresenta cruzamentos automatizados de dados publicos. Doacoes eleitorais sao atividade legal e regulamentada. O padrao identificado -- socio de empresa beneficiada por credito publico subsidiado (BNDES) que doa para campanhas -- nao implica irregularidade per se. Porem, doacoes de grande porte por beneficiarios diretos de credito publico podem indicar retribuicao politica indevida, especialmente quando o volume de doacoes e desproporcional ou direcionado a parlamentares com influencia sobre o BNDES.

---

## 1. Resumo Executivo

A Query Q306 identificou **327 socios-doadores** vinculados a **289 empresas** tomadoras de credito BNDES que simultaneamente fizeram doacoes eleitorais acima de R$ 10.000.

| Metrica | Valor |
|---|---|
| Total de registros (socio × empresa × doacao) | **558** |
| Empresas tomadoras BNDES distintas | **289** |
| Socios-doadores distintos | **327** |
| Total doado para campanhas | **R$ 77.187.164** |
| Candidatos apoiados | **2.502** |

---

## 2. Maiores Tomadores BNDES com Socios Doadores

| Empresa | UF | Emprestimo BNDES (R$) | Socios doadores | Total doado (R$) | Candidatos |
|---|---|---|---|---|---|
| Klabin S.A. | PR | 8.085.137.083 | 6 | 754.262 | 28 |
| Banco do Brasil S.A. | IE/RJ/DF | 6.150.296.580 | 1 | 29.100 | 5 |
| CCEE (Camara Comercializacao Energia) | SP | 6.032.600.080 | 1 | 13.200 | 1 |
| Telefonica Brasil S.A. | IE/SP/PR | 5.865.463.000 | 1 | 65.840 | 1 |
| Concessionaria Rota do Oeste S.A. | MT | 5.812.000.000 | 1 | 306.400 | 5 |
| Sao Martinho S/A | GO/SP | 2.339.221.382 | 3 | 475.000 | 8 |
| Dexco S.A. | SP/IE/MG/RS | 1.431.782.618 | 1 | 1.428.198 | 25 |
| Cocal Com. Ind. Canaa Acucar e Alcool | SP | 1.263.018.000 | 4 | 2.469.074 | 49 |
| Copersucar S.A. | SP | 1.140.000.000 | 4 | 822.400 | 24 |
| BE8 Exportacao e Importacao Ltda | RS | 1.020.000.000 | 1 | 1.029.000 | 44 |

---

## 3. Maiores Doadores Individuais

| Socio-Doador | Empresa | Emprestimo BNDES (R$) | Total doado (R$) | Candidatos | Observacao |
|---|---|---|---|---|---|
| Alexandre Grendene Bartelle | Sitrel Siderurgica Tres Lagoas | 104.795.000 | **4.040.000** | 6 | Fundador da Grendene |
| Robert Carlos Lyra | Delta Sucroenergia S.A. | 623.216.680 | **1.666.667** | 9 | Setor sucroalcooleiro |
| Helio Seibel | Dexco S.A. | 1.431.782.618 | **1.428.198** | 25 | Conselheiro Duratex/Dexco |
| Ricardo Annes Guimaraes | Banco BMG S.A. | 2.000.000 | **1.283.000** | 13 | Setor bancario |
| Erasmo Carlos Battistella | BE8 Exportacao e Importacao | 1.020.000.000 | **1.029.000** | 44 | Setor energetico/biocombustiveis |
| Ricardo Santos Pacheco | Cristalia Prod. Quimicos Farmaceuticos | 90.290.676 | **1.000.000** | 1 | Industria farmaceutica |
| Roberto Argenta | Calcados Beira Rio S/A | 18.000.000 | **925.122** | 2 | Autofinanciamento eleitoral |
| Jose Francisco de F. Santos | JF Citrus Agropecuaria | 25.000.000 | **925.000** | 9 | Agronegocio |
| William Ling | Fitesa Naotecidos S/A | 245.999.999 | **848.000** | 50 | Maior numero de candidatos |

---

## 4. Padroes Identificados

### 4.1. Setor sucroalcooleiro/etanol -- maior concentracao

O setor de acucar, alcool e biocombustiveis domina tanto em volume de emprestimos BNDES quanto em doacoes eleitorais:

| Empresa | Emprestimo BNDES | Socios doadores | Total doado |
|---|---|---|---|
| Sao Martinho | R$ 2,3B | 3 | R$ 475K |
| Cocal Canaa | R$ 1,3B | 4 | R$ 2,5M |
| Copersucar | R$ 1,1B | 4 | R$ 822K |
| BE8 | R$ 1,0B | 1 | R$ 1,0M |
| FS Industria Etanol | R$ 964M | 1 | R$ 100K |
| Delta Sucroenergia | R$ 623M | 1 | R$ 1,7M |
| Jalles Machado | R$ 844M | 4 | R$ 537K |
| Usina Batatais | R$ 770M | 3 | R$ 91K |
| **Total setor** | **~R$ 8,9B** | **21** | **~R$ 7,2M** |

O padrao JBS se repete: grandes tomadores de credito publico subsidiado cujos socios irrigam campanhas de dezenas de candidatos.

### 4.2. Doadores "pulverizados" -- muitos candidatos apoiados

| Doador | Candidatos apoiados | Total doado | Empresa |
|---|---|---|---|
| William Ling | **50** | R$ 848K | Fitesa |
| Cocal (4 socios) | **49** | R$ 2,5M | Cocal Canaa |
| Erasmo C. Battistella | **44** | R$ 1,0M | BE8 |
| Klabin (6 socios) | **28** | R$ 754K | Klabin |
| Helio Seibel | **25** | R$ 1,4M | Dexco |
| Copersucar (4 socios) | **24** | R$ 822K | Copersucar |

Doadores que apoiam 25+ candidatos simultaneamente sugerem estrategia organizada de influencia politica, nao mero apoio ideologico.

### 4.3. Autofinanciamento eleitoral

Roberto Argenta (Beira Rio) doou R$ 925K para apenas 2 candidatos, incluindo a si proprio (ROBERTO ARGENTA, 2022). Deputados-empresarios que usam receita de empresas beneficiadas por credito publico para financiar suas proprias campanhas representam conflito de interesses direto.

### 4.4. Doacao unica de alto valor

Ricardo Santos Pacheco (Cristalia Farmaceutica, R$ 90M em BNDES) doou R$ 1.000.000 para um unico candidato (Ronaldo Dimas Nogueira Pereira, 2022). Doacoes concentradas de grande porte para um unico candidato sugerem relacao pessoal ou expectativa de retorno especifico.

---

## 5. Eleicoes Cobertas

As doacoes identificadas concentram-se nas eleicoes de **2022** (eleicoes gerais -- governador, senador, deputados) e **2024** (eleicoes municipais). A legislacao eleitoral proibe doacoes de pessoa juridica desde 2015 (ADI 4.650/STF), mas permite doacoes de pessoas fisicas (inclusive socios de empresas) ate o limite de 10% dos rendimentos brutos do ano anterior.

---

## 6. Fundamentacao Juridica

- **Lei 9.504/97, art. 23**: limite de doacao por pessoa fisica (10% dos rendimentos brutos do ano anterior).
- **ADI 4.650/STF** (2015): proibiu doacoes de pessoa juridica, mas socios continuam podendo doar como PF.
- **Lei 12.846/2013** (Lei Anticorrupcao): prometer, oferecer ou dar vantagem indevida a agente publico, ou financiar pratica de atos ilicitos.
- **Art. 1, V da LC 64/90**: inelegibilidade por condenacao por abuso do poder economico.
- **Art. 30-A da Lei 9.504/97**: captacao ou gastos ilicitos de recursos para fins eleitorais.

---

## 7. Limitacoes

- **Match por 6 digitos CPF + nome**: pode gerar falsos positivos em homonimos com CPF parcialmente coincidente. Recomenda-se validacao manual dos casos prioritarios.
- **Causalidade nao comprovada**: a correlacao entre emprestimo BNDES e doacao eleitoral nao comprova retribuicao. Muitos empresarios doam por convicao ideologica independentemente de credito publico.
- **Empresas com multiplas UFs**: o mesmo emprestimo pode aparecer desdobrado por UF de filiais, inflando o total. Os valores de emprestimo foram agrupados por empresa quando possivel.
- **Periodo temporal**: os emprestimos BNDES cobrem decadas enquanto as doacoes TSE cobrem 2022-2024. A relacao temporal especifica deve ser verificada caso a caso.

---

## 8. Recomendacoes

1. **Priorizar setor sucroalcooleiro** -- 21 socios-doadores de 8+ empresas, R$ 8,9B em emprestimos BNDES e R$ 7,2M em doacoes. Concentracao setorial sugere coordenacao.
2. **Investigar doacoes de R$ 1M+** para candidato unico (caso Cristalia/Pacheco) -- valor desproporcional sugere expectativa de retorno.
3. **Verificar autofinanciamento** de deputados-empresarios que tomam BNDES -- conflito de interesses direto entre mandato legislativo e beneficio de credito publico.
4. **Cruzar com votacoes parlamentares** -- verificar se candidatos apoiados por socios de tomadores BNDES votaram a favor de projetos que beneficiam o BNDES ou os setores em questao.
5. **Validar limites legais de doacao** -- confirmar se doacoes individuais > R$ 1M respeitaram o teto de 10% dos rendimentos brutos.
