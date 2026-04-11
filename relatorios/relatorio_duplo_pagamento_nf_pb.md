# Relatório de Investigação: Notas Fiscais Liquidadas Mais de Uma Vez no Estado da Paraíba

**Data de Geração:** 11 de abril de 2026  
**Base de Dados:** Query Q104 — `pb_liquidacao_despesa`  
**Metodologia:** identificação de notas fiscais (mesmo número, data, credor e órgão/exercício) liquidadas mais de uma vez. Excluídos NFs zeradas (`000...0`).

> **Disclaimer:** Este relatório apresenta cruzamentos automatizados de dados públicos. Os achados representam anomalias que merecem apuração. Liquidações múltiplas da mesma NF podem decorrer de parcelas contratuais, medições parciais, ou erros de lançamento. A irregularidade não é presumida pelo cruzamento.

---

## 1. Resumo Executivo

A Query Q104 identificou **20.453 notas fiscais** liquidadas mais de uma vez no sistema estadual, totalizando **R$ 3,99 bilhões** em liquidações potencialmente duplicadas. Mesmo que parte expressiva corresponda a parcelas legítimas (medições de obra, entregas parceladas), o volume exige atenção dos órgãos de controle.

Os maiores valores concentram-se em:
- órgãos de grande porte (Secretaria de Educação, Saúde, Tribunal de Justiça);
- credores com CPF mascarado (pessoa física);
- NFs genéricas (números curtos como "1", "2", "6", "7") que sugerem fragilidade no controle documental.

---

## 2. Casos Prioritários

### 2.1. NF 111111111 — R$ 67,5 milhões (18 liquidações)
- **Exercício:** 2018
- **Órgão:** 90101 (PBPREV)
- **Credor:** CPF mascarado (***670\*\*\*\*\*)
- **Empenhos envolvidos:** 18 empenhos distintos (62, 65, 66, 127-139, 1146, 1147)
- **Datas de liquidação:** 26/jan e 28/mai/2018

**Leitura investigativa:** NF com número evidentemente fictício (111111111), 18 empenhos diferentes liquidados com a mesma NF e mesma data. O número da NF e a quantidade de empenhos associados indicam falha grave no controle de documentos fiscais ou uso de NF genérica para agrupar pagamentos.

### 2.2. NF 000003815 — R$ 59,2 milhões (13 liquidações)
- **Exercício:** 2018
- **Órgão:** 220001 (Secretaria de Educação)
- **Credor:** CPF mascarado (***160\*\*\*\*\*)
- **Empenho:** 3815 (mesmo empenho liquidado 13 vezes)
- **Datas de liquidação:** mai a out/2018 (8 datas distintas)

**Leitura investigativa:** um único empenho liquidado 13 vezes contra a mesma NF ao longo de 5 meses. Pode indicar pagamentos parcelados de contrato continuado, mas a ausência de numeração distinta de NFs para cada parcela compromete a rastreabilidade.

### 2.3. NFs 2439 e 5810 — R$ 33 milhões cada (2 liquidações)
- **Exercício:** 2025
- **Órgão:** 310101 (Secretaria de Infraestrutura)
- **Credor:** CPF mascarado (***450\*\*\*\*\*)
- **Empenhos:** 3015 e 4925
- **Datas de liquidação:** jul e nov/2025

**Leitura investigativa:** mesmo credor aparece repetidamente nos maiores valores de NF duplicada (posições 4-13 do ranking). São duas NFs diferentes, ambas de mesma data (21/jul/2025), ambas liquidadas nos mesmos dois empenhos, com valor idêntico. Esse credor concentra pelo menos 10 das 50 maiores ocorrências, sugerindo padrão sistêmico de reliquidação.

### 2.4. NF 214748364 — R$ 30,7 milhões (5 liquidações)
- **Exercício:** 2018
- **Órgão:** 310001
- **Credor:** CPF mascarado (***280\*\*\*\*\*)
- **Empenhos:** 3160 a 3164 (5 empenhos consecutivos)
- **Data de liquidação:** 20/dez/2018

**Leitura investigativa:** o número da NF (214748364) é suspeito — coincide com `2^31 / 10`, um valor típico de overflow em sistemas de 32 bits. Pode indicar geração automática de NF com erro de sistema. Os 5 empenhos consecutivos liquidados no mesmo dia reforçam a anomalia.

### 2.5. NF "7" — R$ 11,1 milhões (42 liquidações)
- **Exercício:** 2026
- **Órgão:** 220001 (Secretaria de Educação)
- **Credor:** CPF mascarado (***410\*\*\*\*\*)
- **Empenho:** 7 (único)
- **Datas de liquidação:** jan/2026 (5 datas em uma semana)

**Leitura investigativa:** 42 liquidações de um único empenho usando NF "7" — um número evidentemente não fiscal. Sugere uso de código interno no campo de NF, comprometendo a auditabilidade.

---

## 3. Padrões Transversais

### 3.1. NFs com numeração genérica ou fictícia
Números como "1", "2", "6", "7", "111111111" e "214748364" aparecem recorrentemente nos maiores valores. Isso indica fragilidade sistêmica no preenchimento do campo de nota fiscal, permitindo liquidações sem lastro documental verificável.

### 3.2. Concentração em poucos credores PF
O credor com CPF ***450\*\*\*\*\* (órgão 310101) aparece pelo menos 10 vezes entre os 50 maiores casos, sempre com padrão de duas liquidações em empenhos distintos para a mesma NF. Esse padrão pode indicar medições parceladas ou pagamentos duplicados sistêmicos.

### 3.3. Concentração temporal em dezembro
Vários casos de alto valor concentram-se em dezembro (exercícios 2018, 2024), coincidindo com o período de encerramento orçamentário — padrão já documentado em outras análises como indicador de "queima de orçamento".

---

## 4. Fundamentação Jurídica

- **Art. 63, § 2º, III da Lei 4.320/64:** a liquidação da despesa exige comprovação da entrega do material ou prestação do serviço, sendo vedada a liquidação sem lastro documental.
- **Art. 93 do Decreto-Lei 200/67:** quem empenhar, liquidar ou pagar sem observar as normas está sujeito a responsabilização.
- **Art. 10, IX da Lei 8.429/92 (LIA):** constitui ato de improbidade causar lesão ao erário por ação ou omissão dolosa.

---

## 5. Recomendações

1. **Auditoria documental** nos 50 maiores casos para verificar existência das NFs e entregas correspondentes.
2. **Correção sistêmica** do campo de nota fiscal: impedir NFs genéricas (1, 2, 7) e números evidentemente fictícios.
3. **Investigação do credor ***450\*\*\*\*\*** (órgão 310101): 10+ NFs duplicadas com valores de R$ 11-33 milhões cada.
4. **Revisão do empenho 7/2026** da Secretaria de Educação: 42 liquidações é incompatível com controle mínimo.
