# Relatório de Auditoria: Servidores Municipais Recebendo Bolsa Família na Paraíba

**Data de Geração:** 28 de Março de 2026
**Base de Dados:** Query Q74 — cruzamento tce_pb_servidor × bolsa_familia
**Metodologia:** Identificação de servidores municipais da Paraíba (SAGRES/TCE-PB, 2024-2026) cujo CPF (6 dígitos centrais) e nome completo coincidem com beneficiários do Novo Bolsa Família, com remuneração municipal superior a R$1.500/mês.

> **Disclaimer:** Este relatório apresenta cruzamentos automatizados de dados públicos. Os achados representam **anomalias estatísticas** que merecem apuração. A coincidência de CPF parcial + nome completo é uma heurística forte, mas não equivale a CPF completo (11 dígitos). Possíveis explicações legítimas incluem: homônimos (mesmo nome e CPF parcial em pessoas diferentes), benefício em nome do titular para dependentes, temporalidade (benefício concedido antes da nomeação), e renda per capita familiar abaixo do limiar apesar do salário. A apuração compete ao MDS, CGU e órgãos de controle.

---

## 1. Resumo Executivo

Foram identificados **20.566 servidores municipais únicos** em **223 municípios** da Paraíba que simultaneamente:
1. Constam na folha de pagamento municipal (SAGRES/TCE-PB, ano_mes >= 2024-01)
2. Recebem remuneração superior a R$1.500/mês
3. Aparecem como beneficiários do Novo Bolsa Família com o mesmo CPF parcial e nome completo

O valor médio de Bolsa Família é R$600/mês, enquanto a remuneração média dos servidores identificados é R$2.200/mês — acima do limiar de elegibilidade do programa (renda per capita familiar de R$218/mês em 2024).

---

## 2. Distribuição por Tipo de Vínculo

| Tipo de Cargo | Servidores | Remuneração Média |
|---------------|-----------|-------------------|
| Contrato temporário (excepcional interesse público) | 16.275 | R$ 2.235 |
| Cargo Comissionado | 3.906 | R$ 2.218 |
| Efetivos | 1.077 | R$ 2.599 |
| Eletivos | 282 | R$ 2.539 |
| Inativos/Pensionistas | 150 | R$ 2.163 |
| Benefício previdenciário temporário | 120 | R$ 2.208 |
| Função de confiança | 50 | R$ 2.208 |
| **Total** | **20.566** | **R$ 2.235** |

**79% são contratos temporários** — profissionais contratados por "excepcional interesse público" (professores, técnicos de enfermagem, auxiliares), típicos de municípios pequenos que dependem de contratos temporários para manter serviços básicos.

---

## 3. Distribuição por Município (Top 25)

| Município | Servidores | Remuneração Média | BF Médio | Total BF Mensal |
|-----------|-----------|-------------------|----------|-----------------|
| João Pessoa | 882 | R$ 2.538 | R$ 645 | R$ 6.679.600 |
| Bayeux | 841 | R$ 2.005 | R$ 624 | R$ 3.655.024 |
| Campina Grande | 838 | R$ 2.471 | R$ 626 | R$ 6.576.260 |
| Santa Rita | 603 | R$ 2.250 | R$ 599 | R$ 3.252.847 |
| Sapé | 544 | R$ 2.041 | R$ 639 | R$ 4.088.503 |
| Patos | 492 | R$ 1.851 | R$ 579 | R$ 3.128.220 |
| Ingá | 463 | R$ 1.864 | R$ 580 | R$ 2.636.622 |
| Pitimbu | 374 | R$ 2.073 | R$ 578 | R$ 2.278.494 |
| Caaporã | 368 | R$ 2.007 | R$ 630 | R$ 2.430.706 |
| Mari | 317 | R$ 2.252 | R$ 632 | R$ 2.172.242 |
| São João do Rio do Peixe | 309 | R$ 2.033 | R$ 618 | R$ 2.448.990 |
| Teixeira | 258 | R$ 2.212 | R$ 540 | R$ 1.604.944 |
| Sousa | 256 | R$ 1.961 | R$ 585 | R$ 2.017.259 |
| Mamanguape | 254 | R$ 2.040 | R$ 621 | R$ 1.673.736 |
| Alhandra | 254 | R$ 2.133 | R$ 471 | R$ 1.637.030 |
| Umbuzeiro | 252 | R$ 2.229 | R$ 634 | R$ 1.916.783 |
| Cajazeiras | 231 | R$ 2.332 | R$ 580 | R$ 1.596.456 |
| Esperança | 228 | R$ 2.031 | R$ 526 | R$ 1.159.342 |
| Pedras de Fogo | 219 | R$ 2.282 | R$ 489 | R$ 743.029 |
| Jacaraú | 217 | R$ 2.253 | R$ 602 | R$ 1.226.817 |
| Baía da Traição | 216 | R$ 2.423 | R$ 584 | R$ 1.729.737 |
| Cruz do Espírito Santo | 210 | R$ 1.924 | R$ 472 | R$ 1.331.728 |
| Alagoa Grande | 196 | R$ 2.786 | R$ 622 | R$ 1.005.439 |
| Mogeiro | 192 | R$ 2.400 | R$ 519 | R$ 1.315.193 |
| Conde | 185 | R$ 2.200 | R$ 580 | R$ 1.250.000 |

---

## 4. Exemplos Individuais

### 4.1. Pensionista com R$87K em São José dos Ramos
- **Servidor:** Albertina Maria da Conceição
- **Município:** São José dos Ramos
- **Cargo:** Pensionista
- **Remuneração:** R$ 87.285 (valor acumulado no período)
- **Bolsa Família:** R$ 440/mês
- **Análise:** O valor de R$87K é acumulado (possivelmente retroativo). Pensionistas podem ter renda variável.

### 4.2. Professores em Queimadas (padrão sistêmico)
- **25+ professores** contratados por excepcional interesse público
- **Remuneração:** R$ 25.000-26.000 (valor acumulado, ~R$4.000-5.000/mês considerando 13º e férias)
- **Bolsa Família:** R$ 325-910/mês
- **Análise:** Padrão que se repete massivamente em Queimadas. A remuneração mensal individual (~R$4K) coloca estes professores acima da renda per capita de elegibilidade do BF, a menos que tenham famílias numerosas.

### 4.3. Casos em municípios diversos
- **Jaciara Furtunato da Silva** (Baía da Traição): Merendeira, R$6.919 + BF R$650
- **Maria Edilma de Sousa Araújo** (Campina Grande): Professora, R$3.483 + BF R$1.002
- **Josefa Clauciana Barbosa da Silva** (Gado Bravo): Merendeira efetiva, R$8.712 + BF R$350

---

## 5. Padrões Observados

1. **Contratos temporários dominam** (79%): A maioria dos servidores com BF são contratados temporários, sugerindo que o benefício foi concedido antes da contratação e não foi atualizado no CadÚnico
2. **Municípios pequenos concentram os casos**: Proporcionalmente, municípios como Ingá (463 casos) e Pitimbu (374 casos) têm percentuais altíssimos de servidores com BF, refletindo a precariedade do vínculo laboral
3. **Remuneração típica de R$2.000-2.500**: Faixa que pode manter elegibilidade ao BF em famílias com 4+ membros (renda per capita ~R$500-625, acima do limiar de R$218 mas dentro da faixa de cadastrados)
4. **Valores de BF baixos (média R$600)**: Consistente com famílias que estão na faixa limítrofe de renda

---

## 6. Ressalvas Importantes

1. **Renda per capita familiar**: O critério do BF é renda per capita familiar (R$218/mês em 2024), não renda individual. Um servidor com R$2.500/mês e 6 dependentes pode ser elegível
2. **Temporalidade**: O benefício pode ter sido concedido antes da contratação. Contratos temporários são frequentemente de 6-12 meses
3. **Valores acumulados**: O campo `valor_vantagem` no SAGRES pode representar acumulado anual, não mensal. Os R$25K de Queimadas são ~R$4K/mês
4. **CPF parcial**: O matching usa 6 dígitos centrais + nome completo, não CPF completo. Há risco residual de falso positivo por homônimos

---

## 7. Enquadramento Legal

- **Lei 14.601/23, art. 3º**: Renda familiar per capita de até R$218/mês para ingresso no programa
- **Lei 14.601/23, art. 19**: Atualização cadastral obrigatória a cada 24 meses
- **Decreto 11.016/22, art. 26**: Perda do benefício por omissão ou prestação de informações falsas
- **Nota:** A atualização cadastral no CadÚnico é responsabilidade do beneficiário. Municípios devem promover ações de atualização.

---

## 8. Recomendações

1. **MDS/Secretaria de Avaliação**: Cruzar a base do CadÚnico com a folha SAGRES/TCE-PB para verificar atualização de renda dos 20.566 servidores identificados
2. **CGU**: Avaliar se os municípios com maior concentração (Bayeux, Ingá, Pitimbu) realizam atualização cadastral conforme o Decreto 11.016/22
3. **Prefeituras**: Incluir procedimento de verificação BF no processo de contratação de servidores temporários
4. **TCE-PB**: Incluir o cruzamento servidor × BF no escopo de auditorias municipais

## Fontes
1. **TCE-PB SAGRES:** Folha de servidores municipais 2024-2026
2. **MDS/Caixa:** Novo Bolsa Família, parcelas mensais
3. **Query Q74:** `queries/fraude_tce_pb.sql`
