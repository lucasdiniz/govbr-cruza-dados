# Relatório de Auditoria: Suspeita de Fracionamento de Despesa nos Municípios da Paraíba

**Data de Geração:** 3 de Abril de 2026
**Base de Dados:** tce_pb_despesa — despesas municipais SAGRES/TCE-PB, 2018-2026
**Metodologia:** Query Q77 — agrupamento por fornecedor + elemento de despesa + município + mês/ano, com filtros de volume, quantidade de empenhos e valor total do grupo

> **Disclaimer:** Este relatório apresenta indicadores estatísticos de risco de fracionamento de despesa, não conclusões de irregularidade. O padrão detectado é um indicador que merece investigação, mas pode ter explicações legítimas — contratos de fornecimento contínuo de combustível e medicamentos naturalmente geram múltiplos empenhos mensais dentro de dispensas regulares. A apuração de eventuais irregularidades compete aos órgãos de controle (TCE-PB, CGE-PB, Ministério Público).

---

## 1. Resumo Executivo

A análise de padrões de despesa municipal identificou **26.195 grupos suspeitos** de fracionamento de despesa nos municípios da Paraíba, envolvendo **R$ 3,63 bilhões** em valores empenhados, distribuídos em **225 municípios** e **3.206 fornecedores distintos**.

O fracionamento de despesa consiste em dividir uma compra de grande valor em múltiplas aquisições menores para manter cada transação abaixo dos limites legais de dispensa de licitação, evitando assim o processo licitatório obrigatório. A prática viola o princípio da licitação competitiva previsto na Lei 8.666/1993 e na Lei 14.133/2021.

**Dimensão do problema:**
| Indicador | Valor |
|-----------|-------|
| Grupos suspeitos | 26.195 |
| Valor total envolvido | R$ 3,63 bilhões |
| Municípios afetados | 225 |
| Fornecedores envolvidos | 3.206 |
| Período coberto | 2018-2026 |

A abrangência quase universal — virtualmente todos os municípios paraibanos apresentam ao menos um grupo suspeito — indica que o padrão é **sistêmico**, não isolado a casos pontuais.

---

## 2. Metodologia

### 2.1. Critérios de Detecção (Query Q77)

Um grupo suspeito é definido pela combinação de:
- **Mesmo fornecedor** (CNPJ ou nome)
- **Mesmo elemento de despesa** (ex.: Material de Consumo, Serviços de Terceiros)
- **Mesmo município**
- **Mesmo mês e ano**

E que satisfaça simultaneamente:
1. Valor individual de cada empenho **menor que R$ 50.000** (abaixo do limite de dispensa de licitação)
2. **5 ou mais empenhos** no grupo no período
3. Valor **total do grupo maior que R$ 80.000** (soma que ultrapassaria o limite de dispensa)

### 2.2. Filtros Aplicados

Foram **incluídos** apenas elementos de despesa relativos a aquisições sujeitas a licitação:
- Material de Consumo (3390.30)
- Outros Serviços de Terceiros — Pessoa Jurídica (3390.39)
- Outros Serviços de Terceiros — Pessoa Física (3390.36)
- Equipamentos e Material Permanente (4490.52)
- Obras e Instalações (4490.51)

Foram **excluídos** elementos não sujeitos ao regime licitatório padrão:
- Pessoal e encargos (folha de pagamento)
- Sentenças judiciais e precatórios
- Transferências intergovernamentais e intragovernamentais

### 2.3. Referência Legal

Os limites de dispensa de licitação variam por ano conforme decreto presidencial. O limite geral para compras e serviços em 2024-2025 é de R$ 50.000 (Lei 14.133/2021, art. 75). Valores consolidados no mesmo mês/fornecedor/elemento acima desse patamar, compostos por múltiplos empenhos individuais menores, caracterizam o padrão de fracionamento.

---

## 3. Padrões Identificados

### 3.1. Medicamentos e Insumos Farmaceuticos — Padrão Sistêmico

O padrão mais expressivo identificado envolve o fornecedor **ALLFAMED** (ALLFAMED COMERCIO ATACADISTA DE MEDICAMENTOS / ALLFAMED COM. ATACADISTA DE MEDICAMENTOS LTDA), que aparece **6 vezes** no top 20 de casos por valor total, em **3 municípios distintos**: Piancó, Serra Branca e Coremas.

- Em Piancó, o mesmo fornecedor aparece em **4 meses diferentes** (fevereiro/2023, abril/2024, julho/2024, dezembro/2024 e março/2025), com totais que variam de R$ 662 mil a R$ 788 mil por mês.
- Os empenhos individuais ficam sistematicamente na faixa de R$ 18 mil a R$ 29 mil — abaixo do limite de dispensa — enquanto o total mensal supera R$ 600 mil a R$ 950 mil.
- A recorrência em múltiplos meses e municípios distintos, sempre com o mesmo fornecedor de medicamentos, aponta para um padrão coordenado de contratação.

Outros fornecedores farmacêuticos identificados na análise:
- **LARMED DISTR DE MEDICAMENTOS E MAT MEDICO HOSPITALAR LTDA** — São Bento, fevereiro/2018: R$ 705,8 mil em 24 empenhos
- **A. COSTA COM. ATAC. DE PROD. FARMACEUTICOS LTDA** — Ingá, dezembro/2024: R$ 649 mil em 34 empenhos

### 3.2. Combustiveis — Dispersao Geografica

Postos de combustível aparecem em múltiplos municípios no top 20, geralmente classificados como Material de Consumo:

| Município | Fornecedor | Mês/Ano | Empenhos | Total |
|-----------|-----------|---------|----------|-------|
| São João do Rio do Peixe | MUNDO NOVO COMERCIO PETROLEO LTDA-ME | Nov/2024 | 63 | R$ 750,1K |
| Rio Tinto | POSTO DE COMBUSTIVEL NOVA MAMANGUAPE LTDA | Dez/2024 | 89 | R$ 729,9K |
| Pilões | POSTO SÃO FRANCISCO | Dez/2024 | 97 | R$ 643,1K |
| Cruz do Espírito Santo | COMERCIAL DE COMBUSTÍVEIS SANTA RITA LTDA | Out/2025 | 45 | R$ 701,8K |
| Picuí | NGC COMBUSTIVEIS LTDA | Dez/2024 | 74 | R$ 617,1K |
| Teixeira | POSTO HW COMBUSTIVEIS COMERCIO LTDA-ME | Dez/2024 | 47 | R$ 612,9K |

Neste segmento, o número de empenhos mensais é elevado (45 a 97 por mês), com valores médios baixos (R$ 6,6 mil a R$ 15,5 mil), o que pode refletir abastecimento diário da frota municipal. Ainda assim, o volume total mensal por fornecedor supera consideravelmente os limites de dispensa, justificando verificação se há contrato ou ata de registro de preços que ampare os pagamentos.

### 3.3. Concentracao em Dezembro — Corrida Orcamentaria de Fim de Ano

**8 dos 20 maiores casos** ocorreram em dezembro, sugerindo uma corrida para utilizar o saldo orçamentário antes do encerramento do exercício:

| Mês | Casos no Top 20 |
|-----|----------------|
| Dezembro | 8 |
| Novembro | 3 |
| Julho | 1 |
| Outros | 8 |

A concentração em dezembro é compatível com o fenômeno de "queima de orçamento", em que gestores empreendem múltiplas aquisições apressadas para não devolver recursos ao final do exercício — frequentemente com menor rigor nos processos de contratação.

### 3.4. Outros Servicos de Terceiros

O fornecedor **O & L LOCACAO EIRELI**, em Pitimbu, aparece com R$ 638,5 mil em 45 empenhos de Outros Serviços de Terceiros — Pessoa Jurídica em novembro/2025 (média R$ 14,1 mil por empenho). Serviços de locação em volume alto e segmentados em empenhos repetitivos merecem atenção especial, pois a natureza do serviço (locação) não justifica, por si só, a ausência de contrato único.

---

## 4. Casos de Maior Risco

### 4.1. Top 20 — Grupos com Maior Valor Total

| # | Município | Fornecedor | Elemento | Ano | Mês | Empenhos | Total | Media/empenho |
|---|-----------|-----------|----------|-----|-----|----------|-------|--------------|
| 1 | Serra Branca | ALLFAMED COMERCIO ATACADISTA DE MEDICAMENTOS | Material de Consumo | 2025 | Agosto | 41 | R$ 956,7K | R$ 23,3K |
| 2 | Piancó | ALLFAMED COM. ATACADISTA DE MEDICAMENTOS LTDA | Material de Consumo | 2024 | Julho | 31 | R$ 788,6K | R$ 25,4K |
| 3 | Areia | 49.990.588 ALUSKA MARIA TAVARES | Material de Consumo | 2025 | Setembro | 34 | R$ 752,3K | R$ 22,1K |
| 4 | Coremas | ALLFAMED COM. ATACADISTA DE MEDICAMENTOS LTDA | Material de Consumo | 2025 | Novembro | 31 | R$ 751,1K | R$ 24,2K |
| 5 | São João do Rio do Peixe | MUNDO NOVO COMERCIO PETROLEO LTDA-ME | Material de Consumo | 2024 | Novembro | 63 | R$ 750,1K | R$ 11,9K |
| 6 | Rio Tinto | POSTO DE COMBUSTIVEL NOVA MAMANGUAPE LTDA | Material de Consumo | 2024 | Dezembro | 89 | R$ 729,9K | R$ 8,2K |
| 7 | São Bento | LARMED DISTR DE MEDICAMENTOS E MAT MEDICO HOSPITALAR LTDA | Material de Consumo | 2018 | Fevereiro | 24 | R$ 705,8K | R$ 29,4K |
| 8 | Cruz do Espírito Santo | COMERCIAL DE COMBUSTÍVEIS SANTA RITA LTDA | Material de Consumo | 2025 | Outubro | 45 | R$ 701,8K | R$ 15,5K |
| 9 | Piancó | ALLFAMED COM. ATACADISTA DE MEDICAMENTOS LTDA | Material de Consumo | 2025 | Março | 26 | R$ 698,3K | R$ 26,8K |
| 10 | Piancó | ALLFAMED COM. ATACADISTA DE MEDICAMENTOS LTDA | Material de Consumo | 2023 | Fevereiro | 27 | R$ 696,5K | R$ 25,7K |
| 11 | Piancó | ALLFAMED COM. ATACADISTA DE MEDICAMENTOS LTDA | Material de Consumo | 2024 | Abril | 37 | R$ 669,6K | R$ 18,0K |
| 12 | Piancó | ALLFAMED COM. ATACADISTA DE MEDICAMENTOS LTDA | Material de Consumo | 2024 | Dezembro | 23 | R$ 662,0K | R$ 28,7K |
| 13 | Juazeirinho | POSTO DIESEL SAO JOSE LTDA | Material de Consumo | 2024 | Dezembro | 49 | R$ 649,1K | R$ 13,2K |
| 14 | Ingá | A. COSTA COM. ATAC. DE PROD. FARMACEUTICOS LTDA | Material de Consumo | 2024 | Dezembro | 34 | R$ 649,0K | R$ 19,0K |
| 15 | Pilões | POSTO SÃO FRANCISCO | Material de Consumo | 2024 | Dezembro | 97 | R$ 643,1K | R$ 6,6K |
| 16 | Pitimbu | O & L LOCACAO EIRELI | Outros Serv. Terceiros - PJ | 2025 | Novembro | 45 | R$ 638,5K | R$ 14,1K |
| 17 | Cabedelo | LINK CARD ADM DE BENEFICIOS EIRELI | Material de Consumo | 2021 | Maio | 68 | R$ 623,3K | R$ 9,1K |
| 18 | Picuí | NGC COMBUSTIVEIS LTDA | Material de Consumo | 2024 | Dezembro | 74 | R$ 617,1K | R$ 8,3K |
| 19 | Teixeira | POSTO HW COMBUSTIVEIS COMERCIO LTDA-ME | Material de Consumo | 2024 | Dezembro | 47 | R$ 612,9K | R$ 13,0K |
| 20 | Juazeirinho | POSTO DIESEL SAO JOSE LTDA | Material de Consumo | 2024 | Novembro | 51 | R$ 611,6K | R$ 12,0K |

### 4.2. Analise por Caso

**Serra Branca / ALLFAMED (agosto/2025 — R$ 956,7K):** Maior caso individual. Um único fornecedor de medicamentos recebeu R$ 956.700 em um único mês por meio de 41 empenhos separados. O valor médio de R$ 23,3 mil por empenho é consistente com a estratégia de manter cada nota abaixo do limite de dispensa. Sem uma ata de registro de preços ou pregão que ampare o volume total, a operação não tem base legal.

**Piancó / ALLFAMED (recorrência 2023-2025):** O município de Piancó apresenta o mesmo fornecedor em pelo menos 5 meses distintos ao longo de 3 anos, com totais mensais acima de R$ 660 mil. A persistência do padrão ao longo do tempo reforça a suspeita de irregularidade estrutural nas contratações de medicamentos do município.

**Areia / ALUSKA MARIA TAVARES (setembro/2025 — R$ 752,3K):** Pessoa física (CPF 49.990.588/...) classificada como fornecedora de Material de Consumo, com 34 empenhos e R$ 752,3 mil em um único mês. Pagamentos de alto volume a pessoa física em elemento de material de consumo são atípicos e merecem verificação específica da natureza do objeto contratado.

**Rio Tinto / Posto Nova Mamanguape (dezembro/2024 — R$ 729,9K):** 89 empenhos de combustível em um único mês para um único posto. A média de R$ 8,2 mil por empenho sugere registro de cada abastecimento separadamente. Embora abastecimento diário de frota seja operacionalmente plausível, o volume total justifica verificar se há processo licitatório ou dispensa formal registrada.

**Cabedelo / LINK CARD (maio/2021 — R$ 623,3K):** Empresa administradora de benefícios recebendo R$ 623 mil classificados como Material de Consumo em 68 empenhos. A natureza do fornecedor (administração de benefícios, possivelmente vale-alimentação ou similar) pode explicar o volume, mas a classificação no elemento Material de Consumo e a ausência de licitação merecem verificação.

---

## 5. Limitacoes e Alertas Metodologicos

1. **Contratos de fornecimento continuo:** Medicamentos e combustíveis fornecidos sob contratos administrativos regulares naturalmente geram múltiplos empenhos mensais. A detecção por Q77 captura esses casos junto com os irregulares. A diferenciação requer verificação manual da existência de contrato ou ata de registro de preços nos sistemas de transparência.

2. **Empenhos por tipo de despesa:** Alguns elementos de despesa, como Material de Consumo, são usados para registrar objetos heterogêneos. A classificação incorreta de serviços como material, ou vice-versa, pode gerar falsos positivos ou mascarar irregularidades.

3. **Limite temporal de referência:** Os limites de dispensa de licitação foram atualizados ao longo do período analisado (2018-2026). O critério de R$ 50.000 por empenho reflete o limite vigente em 2024-2025. Para anos anteriores, o limite era menor, o que tornaria alguns padrões ainda mais suspeitos do que a análise atual indica.

4. **Granularidade do agrupamento:** O agrupamento por mês/ano é conservador — fracionamentos que se distribuem por dois ou mais meses consecutivos no mesmo fornecedor/elemento não são capturados por esta query. O total real de operações suspeitas pode ser maior.

5. **Fornecedores com nomes similares:** Variações no cadastro do mesmo fornecedor (ex.: com e sem sufixo "LTDA", com CNPJ diferente de filiais) podem subestimar a concentração em um único grupo econômico.

---

## 6. Recomendações

1. **TCE-PB:** Priorizar auditorias nas relações fornecedor-município com recorrência em múltiplos meses, especialmente Piancó/ALLFAMED (5+ ocorrências no top 20) e os municípios com volumes acima de R$ 700 mil em um único mês.
2. **TCE-PB / CGE-PB:** Verificar a existência de processos licitatórios ou dispensas formalizadas que amparem os volumes mensais identificados, consultando os sistemas SAGRES e SIGA.
3. **Ministério Publico:** Os casos de pessoa física (Areia/ALUSKA MARIA TAVARES) e de fornecedores classificados em elemento atípico para sua atividade (Cabedelo/LINK CARD) merecem apuração prioritária.
4. **Transparencia:** Publicar os dados consolidados por município e fornecedor como ferramenta de controle social, permitindo que vereadores e cidadãos identifiquem padrões nas suas localidades.
5. **Sistema:** Implementar no SAGRES alerta automático quando o total de empenhos para o mesmo fornecedor/elemento/mês ultrapassar o limite de dispensa, exigindo justificativa do ordenador de despesas.

---

## Fontes

1. **TCE-PB SAGRES:** Despesas municipais 2018-2026 (tce_pb_despesa)
2. **Lei 8.666/1993:** Art. 23 — limites de dispensa de licitação
3. **Lei 14.133/2021:** Art. 75 — novos limites de dispensa de licitação
4. **Decretos 9.412/2018 a 12.807/2025:** Atualização dos limites de dispensa por ano
5. **Query Q77:** Detecção de fracionamento por agrupamento mensal fornecedor/elemento/município
