# Relatório de Auditoria: Padrões Suspeitos em Itens de Licitação (PNCP)

**Data de Geração:** 4 de Abril de 2026
**Base de Dados:** pncp_item | pncp_contratacao | pncp_contrato (Portal Nacional de Contratações Públicas)
**Metodologia:** Três consultas analíticas (Q93, Q96, Q98) sobre a base PNCP local, identificando padrões estatísticos anômalos em itens de licitação — fracassos repetidos, orçamento sigiloso de alto valor e preços unitários idênticos entre órgãos independentes.

> **Disclaimer:** Este relatório apresenta indicadores estatísticos de risco, não conclusões de irregularidade ou ilicitude. Os padrões identificados podem ter explicações legítimas (preço-teto desatualizado, ausência de fornecedores na região, tabela de preços de referência compartilhada, sigilo amparado em legislação específica, etc.). A apuração de eventual irregularidade compete exclusivamente aos órgãos competentes (CGU, TCU, MPF/MPE, TCEs estaduais).

---

## 1. Resumo Executivo

Esta auditoria analisa **três dimensões de risco** em compras públicas registradas no PNCP: (1) itens que fracassam ou são desertos repetidamente no mesmo órgão, sugerindo especificação direcionada ou preço-teto inviável; (2) compras de alto valor com orçamento sigiloso, que impedem comparação de preço pelos licitantes; e (3) preços unitários não-redondos idênticos em múltiplos órgãos independentes, padrão consistente com coordenação de preços (cartel).

**Resultados consolidados:**

| Consulta | Achado | Volume identificado |
|----------|--------|-------------------|
| Q93 | Grupos item+órgão com 3+ fracassos/deserções | 7.291 grupos |
| Q96 | Itens homologados com orçamento sigiloso >= R$ 500 mil | 445 itens |
| Q98 | Combinações item+preço (não-redondo) em 5+ órgãos e 10+ contratações | 306 combinações |

Os casos de maior gravidade incluem uma secretaria estadual com **974 licitações fracassadas para arroz** em 19 meses, uma entidade de saúde pública com **R$ 563 milhões em submissões com descrição "PLANILHA SEM ITENS"**, e um item de limpeza com preço não-redondo idêntico replicado em **17 órgãos distintos**.

---

## 2. Metodologia

### 2.1. Q93 — Itens Fracassados ou Desertos Repetidos (fraude_pncp_item.sql, linhas 57–77)

A consulta agrupa itens pelo par `(cnpj_orgao, descricao_normalizada)`, filtrando apenas itens com situação `Fracassado` ou `Deserto`. São retornados apenas grupos com **3 ou mais contratações distintas** no estado de fracasso/deserção. Métricas calculadas: total de ocorrências, preço médio estimado, data da primeira e última tentativa.

**Limiar de corte:** `COUNT(DISTINCT numero_controle_pncp) >= 3`

### 2.2. Q96 — Orçamento Sigiloso em Compras de Alto Valor (linhas 160–188)

Filtra itens com flag `orcamento_sigiloso = TRUE`, situação `Homologado` (portanto efetivamente contratados), e valor total do item ou do contrato maior ou igual a **R$ 500 mil**. O cruzamento com a tabela de contratos (`pncp_contrato`) permite identificar o fornecedor vencedor e o valor contratado final.

**Limiar de corte:** `valor_total >= 500.000 OR valor_global (contrato) >= 500.000`

### 2.3. Q98 — Preços Unitários Idênticos Não-Redondos (linhas 241–273)

Agrupa itens homologados pelo par `(descricao_normalizada, valor_unitario_estimado)`, excluindo deliberadamente preços inteiros e preços com apenas uma casa decimal (que ocorrem naturalmente por arredondamento). São retidos apenas grupos com **5 ou mais órgãos distintos** e **10 ou mais contratações distintas**.

**Filtro anti-ruído:** `preco <> ROUND(preco, 0) AND preco <> ROUND(preco, 1)`

---

## 3. Achados Principais

### 3.1. Q93 — Fracassos e Deserções Repetidas

Foram identificados **7.291 grupos** de par item+órgão com três ou mais fracassos ou deserções registrados no PNCP. Esse volume é expressivo: indica que milhares de demandas públicas não conseguem ser supridas via licitação, seja por ausência de concorrência, especificações excessivamente restritivas ou preço-teto incompatível com o mercado.

**Distribuição por natureza do problema (hipóteses não excludentes):**

| Hipótese | Indicadores típicos |
|----------|-------------------|
| Preço-teto irrealista | Fracassos concentrados em período de inflação setorial; sem adjudicação mesmo após relicitação |
| Especificação direcionada | Itens com características muito específicas; único fornecedor potencial no mercado regional |
| Ausência de mercado local | Órgãos em municípios pequenos; itens de nicho técnico |
| Fraude por reserva de dotação | Descrições genéricas ou vazias; valores estimados altos sem especificação real |

### 3.2. Q96 — Orçamento Sigiloso em Alto Valor

Foram identificados **445 itens homologados** com orçamento sigiloso e valor igual ou superior a R$ 500 mil. O uso de orçamento sigiloso é permitido por lei (art. 24, Lei 14.133/2021) em situações específicas — defesa nacional, segurança pública, propriedade intelectual — mas seu uso em compras de bens e serviços comuns de alto valor levanta questionamentos.

**Top 2 contratos com orçamento sigiloso por valor contratado:**

| UF | Fornecedor | Valor contratado |
|----|-----------|-----------------|
| MA | Telefonica Brasil S.A. | R$ 18.900.000 |
| CE | Convergint Technologies | R$ 18.800.000 |

**Impacto do sigilo:** Em contratos desta magnitude, esconder o valor estimado impede que licitantes formulem propostas competitivas com base em referências de mercado, concentrando a vantagem de informação no órgão contratante — o que pode beneficiar fornecedores com acesso privilegiado ao valor interno estimado.

### 3.3. Q98 — Preços Unitários Idênticos (Não-Redondos)

Foram identificadas **306 combinações** de item+preço onde um valor unitário não-redondo idêntico aparece em pelo menos 5 órgãos distintos e 10 contratações independentes. Preços não-redondos (ex.: R$ 5,83 em vez de R$ 5,80 ou R$ 6,00) raramente convergem por coincidência em mercados competitivos.

**Mecanismos possíveis:**

| Mecanismo | Avaliação |
|-----------|-----------|
| Tabela de referência única (PNCP, BEC-SP, SIASG) | Explica convergência, mas não justifica identidade exata em órgãos de estados diferentes |
| Formação de cartel (acordo entre fornecedores) | Preço idêntico não-redondo em múltiplos estados é padrão clássico de coordenação |
| Replicação de edital sem atualização de preço | Possível para itens similares; menos provável em 17+ órgãos independentes |

---

## 4. Casos de Destaque

### 4.1. Secretaria de Educação do Mato Grosso do Sul — Merenda Escolar

A Secretaria de Educação do Mato Grosso do Sul apresenta o padrão mais extremo de fracassos repetidos identificado na base:

| Item | Licitações fracassadas | Período coberto |
|------|----------------------|----------------|
| ARROZ | 974 | jan/2024 – jul/2025 (19 meses) |
| BATATA | 537 | — |
| FEIJÃO | 463 | — |

Trata-se de alimentos básicos da merenda escolar, itens de ampla disponibilidade comercial. O volume de **974 fracassos para um único item em 19 meses** — média de mais de 50 tentativas frustradas por mês — é estatisticamente improvável em mercado funcionando normalmente.

**Hipóteses investigativas:**

1. **Preço-teto desatualizado:** A secretaria pode estar usando valores de referência defasados em relação à inflação alimentar do período (2024–2025), gerando fracassos sistemáticos e previsíveis.
2. **Especificação técnica restritiva:** Requisitos como marca, procedência geográfica ou certificações específicas podem estar eliminando todos os fornecedores disponíveis na região.
3. **Estratégia para contratação direta:** Fracassos repetidos habilitam contratação direta por inexigibilidade ou emergência (art. 74–75, Lei 14.133/2021). Se esse for o objetivo real, os fracassos são instrumentais, não acidentais.

**Recomendação:** Auditoria presencial na secretaria, confrontando os editais fracassados com os preços de mercado atacadista vigentes (CEASA/MS, CONAB) e as contratações diretas realizadas no mesmo período para os mesmos itens.

---

### 4.2. SES-PB (Secretaria Estadual de Saúde da Paraíba) — "Planilha sem Itens"

Este é o caso de maior potencial de irregularidade identificado na análise:

| Métrica | Valor |
|---------|-------|
| Submissões com descrição "PLANILHA SEM ITENS" | 114 |
| Preço médio estimado por submissão | R$ 4.900.000 |
| Valor total acumulado | R$ 563.000.000 |
| Período coberto | 595 dias |
| Situação registrada no PNCP | Fracassado |

A descrição "PLANILHA SEM ITENS" é um indicador grave: o campo de descrição do item foi submetido sem especificação real do bem ou serviço. O PNCP registra o processo formalmente, mas sem detalhamento do objeto licitado.

**Por que é suspeito:**

- **Reserva de dotação orçamentária:** O registro de processo licitatório — mesmo fracassado — pode ser usado para bloquear dotações, impedindo remanejamento para outras despesas e criando massa orçamentária cativa.
- **Lastro para contratação direta:** Uma série de fracassos formais em processos sem objeto definido cria precedente burocrático para contratações emergenciais subsequentes, dispensando a licitação.
- **Valor médio atípico:** R$ 4,9 milhões por submissão sem descrição de objeto não tem paralelo em boa prática administrativa. Esse padrão não ocorre por erro operacional isolado — 114 repetições indicam sistemática.

**Recomendação:** Cruzamento imediato dos 114 processos com as contratações emergenciais e diretas da SES-PB no mesmo período (595 dias). Identificar se os CNPJs beneficiados nas contratações diretas subsequentes têm relação societária com servidores da secretaria.

---

### 4.3. Pano de Chão a R$ 5,83 — Padrão de Cartel

O item "PANO DE CHÃO" com valor unitário de **R$ 5,83** aparece em **17 órgãos distintos** como preço unitário estimado idêntico, em múltiplas contratações independentes realizadas em estados diferentes.

**Por que R$ 5,83 é evidência relevante:**

- É um valor com 2 casas decimais significativas, improvável de surgir por arredondamento independente em 17 órgãos.
- Aparece em estados diferentes, eliminando a hipótese de tabela de referência regional única.
- Itens de limpeza são sensíveis a variações de marca, qualidade e economia de escala — a identidade exata entre órgãos de portes e regiões distintos não tem explicação técnica óbvia.

**Contexto legal:** A formação de cartel em licitações públicas é crime tipificado no art. 337-I do Código Penal (inserido pela Lei 14.133/2021), com pena de 4 a 8 anos de reclusão. O CADE mantém o Programa de Combate a Cartéis em Licitações com mecanismo de denúncia e acordo de leniência.

**Recomendação:** Identificar os fornecedores vencedores nos 17 órgãos e verificar sobreposição societária. Encaminhar ao CADE via Formulário de Denúncia caso os mesmos fornecedores (ou empresas relacionadas) sejam recorrentes nos contratos.

---

## 5. Limitações e Próximos Passos

### 5.1. Limitações

| Limitação | Impacto |
|-----------|---------|
| Cobertura parcial do PNCP (nem todos os órgãos integram o portal) | Subestimação do volume real de fracassos e padrões de cartel |
| Normalização de descrições por `UPPER(TRIM())` não captura variações ortográficas | Grupos distintos podem descrever o mesmo item com grafias diferentes, fragmentando a análise |
| Q96 identifica apenas itens homologados — sigilo em fracassos não é capturado | Contratos sigilosos que nunca foram efetivados escapam da análise |
| Preços idênticos por tabela de referência (CATMAT, BEC-SP) podem gerar falsos positivos em Q98 | Necessário validação manual dos casos sinalizados |
| Q93 inclui fracassos por motivos técnicos (documentação incompleta) além de irregularidades | Requer análise dos editais para distinção entre causa técnica e estratégica |

### 5.2. Próximos Passos Recomendados

1. **[Prioritário] SES-PB "Planilha sem Itens":** Extrair os 114 números de processo e cruzar com contratações diretas e emergenciais da SES-PB no período. Identificar CNPJs beneficiados e verificar vínculo com servidores.

2. **[Prioritário] Secretaria de Educação MS:** Confrontar os editais fracassados de ARROZ com preços CONAB/CEASA-MS no mesmo período. Mapear contratações diretas de gêneros alimentícios no mesmo intervalo.

3. **[Médio prazo] Q96 — Maranhão e Ceará:** Solicitar aos TCEs estaduais a justificativa legal para sigilo do orçamento nos contratos com Telefonica Brasil e Convergint Technologies. Comparar valor contratado com benchmarks de mercado (painel de preços COMPRASNET).

4. **[Médio prazo] Q98 — Pano de chão R$ 5,83:** Compilar lista de fornecedores vencedores nos 17 órgãos. Se houver sobreposição de CNPJs ou de sócios, encaminhar denúncia formal ao CADE.

5. **[Análise futura] Combinação Q93 + Q96:** Órgãos que acumulam fracassos repetidos E usam orçamento sigiloso nas homologações subsequentes para os mesmos itens representam risco duplo e merecem prioridade de auditoria.

---

## 6. Conclusão

As três consultas analíticas aplicadas à base PNCP revelam padrões que, isoladamente, podem ter explicações técnicas, mas em conjunto formam um quadro que justifica investigação aprofundada pelos órgãos de controle.

O caso mais urgente é a **SES-PB com "Planilha sem Itens"**: R$ 563 milhões em processos sem descrição de objeto ao longo de 595 dias é uma anomalia que não encontra explicação técnica imediata e requer auditoria presencial prioritária pelo TCE-PB e CGU.

O padrão de **fracassos da merenda escolar no Mato Grosso do Sul** levanta questões sobre a gestão do processo licitatório — seja por negligência administrativa (preços desatualizados) ou por estratégia deliberada de acesso a modalidades de contratação direta.

Os **306 padrões de preço idêntico não-redondo** em múltiplos órgãos independentes constituem um conjunto de pistas para investigação de cartel, com o caso do pano de chão a R$ 5,83 sendo o mais robusto para encaminhamento ao CADE dada sua extensão geográfica (17 órgãos em estados distintos).

A base de dados local permite aprofundamento de qualquer dos casos identificados, incluindo extração dos números de controle PNCP, CNPJs dos fornecedores e valores contratados para todos os registros sinalizados.

---

*Relatório gerado pelo pipeline govbr-cruza-dados a partir de dados públicos do PNCP.*
*Queries de referência: `queries/fraude_pncp_item.sql` (Q93 linhas 57–77, Q96 linhas 160–188, Q98 linhas 241–273)*
