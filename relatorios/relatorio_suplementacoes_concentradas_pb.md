# Relatório de Investigação: Suplementações Orçamentárias Concentradas em Fornecedores do Estado da Paraíba

**Data de Geração:** 11 de abril de 2026  
**Base de Dados:** Query Q110 — `pb_empenho_suplementacao` × `pb_empenho`  
**Metodologia:** identificação de credores cujas suplementações representam percentual elevado do empenho original (5+ suplementações, R$ 100 mil+ suplementado), filtrado para empresas privadas. Excluídos órgãos públicos.

> **Disclaimer:** Este relatório apresenta cruzamentos automatizados de dados públicos. Suplementações podem decorrer de ampliação de demanda, reajuste contratual ou planejamento subdimensionado. Percentuais extremos podem indicar empenho-semente (valor simbólico) com suplementações posteriores, o que compromete a transparência orçamentária, mas não é automaticamente ilegal.

---

## 1. Resumo Executivo

A Query Q110 identificou fornecedores privados cujas suplementações multiplicam dramaticamente o empenho original. Os padrões mais recorrentes são:

- **Empenho-semente:** empenhos de R$ 1.000 que recebem suplementações de centenas de milhares, gerando percentuais acima de 10.000%.
- **Suplementações massivas em saúde:** empresas médicas cujos contratos crescem 800-1500% via suplementação.
- **Concentração de suplementações em segurança privada e terceirização.**

---

## 2. Casos Prioritários

### 2.1. Itaú Unibanco S/A — R$ 500 mil suplementados sobre R$ 1 mil (50.008%)
- **CNPJ:** 60.701.190/0001-04
- **UG:** 300002 (Encargos Gerais do Estado - SEFAZ)
- **Exercício:** 2023
- **Empenho original:** R$ 1.000
- **Suplementações:** 13, totalizando R$ 500 mil

**Leitura investigativa:** padrão clássico de empenho-semente para pagamento de encargos bancários. O empenho é criado com valor simbólico (R$ 1 mil) e suplementado conforme os juros e encargos da dívida vencem. Esse padrão se repete para Caixa Econômica Federal (R$ 387 mil, 27.545%) e Banco Santander (R$ 127 mil, 12.704%). Embora a prática tenha explicação operacional, ela compromete a transparência orçamentária — o empenho original não reflete o gasto real planejado.

### 2.2. Construtora Soberana Ltda — R$ 1,74 milhão suplementado sobre R$ 20 mil (8.690%)
- **CNPJ:** 33.075.863/0001-87
- **UG:** 350401 (UEPB)
- **Exercício:** 2025
- **Empenho original:** R$ 20 mil
- **Suplementações:** 7, totalizando R$ 1,74 milhão

**Leitura investigativa:** empenho de R$ 20 mil para obra que acaba custando R$ 1,76 milhão é red flag forte. Ou o planejamento foi grosseiramente subdimensionado, ou o empenho-semente foi intencional para evitar controles de valor na fase inicial. Uma construtora com contrato real de obra não deveria começar com empenho de R$ 20 mil.

### 2.3. AV Med Ltda Consultório Médico — R$ 4,5 milhões suplementados sobre R$ 300 mil (1.500%)
- **CNPJ:** 37.224.146/0001-20
- **UG:** 250001 (Secretaria de Saúde)
- **Exercício:** 2025
- **Empenho original:** R$ 300 mil
- **Suplementações:** 8, totalizando R$ 4,5 milhões

**Leitura investigativa:** empresa médica que começa com contrato de R$ 300 mil e recebe 15x o valor via suplementações. O padrão sugere contrato de serviço médico subdimensionado ou expansão contratual sem nova licitação.

### 2.4. JSL Locações e Montagens Eireli — R$ 2,75 milhões sobre R$ 200 mil (1.375%)
- **CNPJ:** 04.203.988/0001-47
- **UG:** 290001 (Secretaria de Comunicação Institucional)
- **Exercício:** 2024
- **Empenho original:** R$ 200 mil
- **Suplementações:** 9, totalizando R$ 2,75 milhões

**Leitura investigativa:** empresa de locação de estruturas/montagens para eventos, com 9 suplementações concentradas na Secretaria de Comunicação. Pode indicar eventos sucessivos sem planejamento prévio adequado.

### 2.5. WM&M Serviços Médicos Ltda — R$ 6,05 milhões sobre R$ 550 mil (1.100%)
- **CNPJ:** 35.342.311/0001-13
- **UG:** 250001 (Secretaria de Saúde)
- **Exercício:** 2025
- **Empenho original:** R$ 550 mil
- **Suplementações:** 8, totalizando R$ 6,05 milhões

**Leitura investigativa:** outro caso de empresa médica na Secretaria de Saúde com expansão de 11x via suplementação. O padrão se repete: empenho inicial modesto seguido de suplementações massivas.

### 2.6. Justiz Terceirização de Mão de Obra Ltda — R$ 3,37 milhões sobre R$ 261 mil (1.292%)
- **CNPJ:** 06.538.799/0001-50
- **UG:** 250001 (Secretaria de Saúde)
- **Exercício:** 2026
- **Empenho original:** R$ 261 mil
- **Suplementações:** 6, totalizando R$ 3,37 milhões

**Leitura investigativa:** empresa de terceirização com expansão de 13x. A combinação terceirização + saúde + suplementações massivas é padrão recorrente nesta análise.

### 2.7. Weider Segurança Privada Ltda — R$ 4,05 milhões sobre R$ 400 mil (1.012%)
- **CNPJ:** 08.705.015/0001-67
- **UG:** 220401 (UEPB)
- **Exercício:** 2022
- **Empenho original:** R$ 400 mil
- **Suplementações:** 13, totalizando R$ 4,05 milhões

**Leitura investigativa:** empresa de segurança privada que inicia com R$ 400 mil e recebe 13 suplementações totalizando R$ 4 milhões. A quantidade elevada de suplementações (13 em um exercício) sugere ampliação mensal sem planejamento anual adequado.

---

## 3. Padrões Transversais

### 3.1. Empenho-semente como prática sistêmica
Bancos (Itaú, CEF, Santander) e empresas de serviços começam com empenhos de R$ 1.000 a R$ 20.000, suplementados em 5.000-50.000%. Isso sugere prática orçamentária de abrir empenho simbólico para garantir dotação, suplementando depois.

### 3.2. Saúde concentra as maiores suplementações privadas
AV Med, WM&M, Justiz, Hospital Milagres, Med Patos — todas na Secretaria de Saúde (250001). O setor de saúde é o principal gerador de suplementações concentradas em fornecedores privados.

### 3.3. Segurança privada e terceirização com suplementações mensais
Kairos Segurança, Alforge Segurança, Weider Segurança, Zelo Locação — padrão de empenho inicial baixo com suplementação mensal, indicando contratos continuados mal dimensionados ou intencionalmente subdimensionados.

---

## 4. Fundamentação Jurídica

- **Art. 65, § 1º da Lei 8.666/93:** o contratado fica obrigado a aceitar acréscimos até 25% do valor original (50% para reformas). Suplementações que excedem esses limites sem nova licitação podem ser irregulares.
- **Art. 167, V da CF/88:** veda a abertura de crédito suplementar sem indicação de recursos disponíveis e sem autorização legislativa.
- **Art. 10, XI da Lei 8.429/92 (LIA):** liberar recurso público sem observância das normas orçamentárias constitui ato de improbidade.

---

## 5. Recomendações

1. **Auditar o padrão empenho-semente** na SEFAZ (UG 300002): verificar se a prática de empenhos de R$ 1.000 com suplementações milionárias tem amparo normativo.
2. **Investigar Construtora Soberana na UEPB**: empenho de R$ 20 mil para obra que custou R$ 1,76 milhão é incompatível com planejamento mínimo.
3. **Revisar contratos de saúde** (AV Med, WM&M, Justiz): verificar se as suplementações respeitam o limite de 25% da Lei de Licitações.
4. **Estabelecer alerta** para suplementações que excedam 100% do empenho original no mesmo exercício.
