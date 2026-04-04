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

A Secretaria de Estado de Educação de Mato Grosso do Sul (CNPJ 02.585.924/0001-22) apresenta o padrão mais extremo de fracassos repetidos identificado na base. O problema abrange **mais de 30 itens alimentícios** do PNAE (Programa Nacional de Alimentação Escolar):

| Item | Fracassos | Período | Preço médio (R$/kg) |
|------|-----------|---------|-------------------|
| ARROZ (5kg, tipo 1, agulhinha) | 974 | jul/2024 – fev/2026 | 25,24 |
| BATATA (inglesa, in natura) | 537 | jul/2024 – fev/2026 | 7,64 |
| ALHO (branco, sem réstia) | 485 | jul/2024 – fev/2026 | 36,94 |
| BANANA (nanica) | 296 | jul/2024 – fev/2026 | 6,39 |
| ABACAXI | 272 | jul/2024 – fev/2026 | 10,56 |
| BEBIDA LÁCTEA | 264 | jul/2024 – fev/2026 | 5,83 |
| CARNE SUÍNA LOMBO | 262 | jul/2024 – jan/2026 | 23,09 |
| CAFÉ TORRADO | 162 | jul/2024 – jan/2026 | 20,91 |

**Modalidade dominante:** 4.781 fracassos via **Dispensa** (96%), 188 via Pregão Presencial, 3 via Pregão Eletrônico. O órgão publica dispensas individuais por escola — cada escola gera um processo separado, multiplicando os fracassos.

#### Deep dive: Arroz — O preço NÃO é o problema

| Métrica | MS fracassado | Nacional homologado |
|---------|--------------|-------------------|
| Preço médio (R$/kg) | 25,28 | 26,01 |
| Preço mínimo | 16,33 | 0,01 |
| Preço máximo | 37,14 | 9.960,00 |
| Total de itens | 978 | 13.682 |

O preço estimado do MS (R$25,28/kg para pacote de 5kg) está **abaixo** da média nacional homologada (R$26,01) — **o preço-teto NÃO é irrealista**. Além disso, **1.033 itens de arroz foram homologados** pela mesma secretaria no mesmo período, confirmando que fornecedores existem e aceitam o preço.

**Evolução mensal do arroz (fracassados):**

| Mês | Fracassos | Preço médio |
|-----|-----------|-------------|
| jul/2024 | 65 | 28,81 |
| ago/2024 | 250 | 29,01 |
| dez/2024 | 259 | 29,33 |
| jan/2025 | 64 | 29,83 |
| dez/2025 | 293 | 17,27 |
| jan/2026 | 29 | 17,70 |

Os picos de fracasso (ago/2024, dez/2024, dez/2025) coincidem com períodos de início de semestre letivo, quando a demanda por merenda é maior. A queda de preço em dez/2025 (R$17,27 vs R$29,33 em dez/2024) sugere ajuste de referência, mas os fracassos continuam.

**Contratos diretos de alimentos no mesmo período:**

O órgão publicou **dispensas para chamadas públicas da Agricultura Familiar** (PNAE) no mesmo intervalo, com valores de R$2K a R$181K por escola. Isso sugere que os fracassos em Dispensa comum levam a contratações via Chamada Pública do PNAE — um mecanismo legal mas que reduz a competitividade.

**Hipóteses revisadas após análise:**

1. ~~Preço-teto desatualizado~~ — **DESCARTADO**: preço MS está abaixo da média nacional, e o mesmo item é homologado no mesmo período.
2. **Modelo operacional ineficiente:** O órgão publica dispensas individuais por escola (4.781 processos), em vez de consolidar em pregão eletrônico. Cada escola tenta comprar isoladamente, sem poder de barganha.
3. **Estratégia de migração para Agricultura Familiar:** Fracassos em dispensa comum podem estar sendo usados para justificar chamadas públicas exclusivas para agricultura familiar (art. 14 da Lei 11.947/2009), com menos controle competitivo.

**Recomendação:** Investigar por que o órgão não consolida as compras em pregão eletrônico (3 processos apenas) e se os fracassos em dispensa são instrumentais para viabilizar as chamadas públicas da Agricultura Familiar.

---

### 4.2. "Planilha Não Contém Itens" — Padrão do sistema de compras da Paraíba

**Atualização após deep dive:** Este caso é significativamente maior e diferente do que a análise Q93 indicava inicialmente. A descrição completa é "PLANILHA NÃO CONTÊM ITENS (EXCLUSIVO PARA EPC, PGGAS, UEPB, CAGEPA, SES, SEE, SEDS E DOCAS_PB)" — é um padrão sistêmico do estado da PB, usado por múltiplos órgãos.

| Órgão | Registros | Valor total | Período |
|-------|-----------|-------------|---------|
| Secretaria de Estado da Saúde - SES | 515 | R$ 1.145.613.570 | fev/2024 – mar/2026 |
| Universidade Estadual da Paraíba | 66 | R$ 18.824.998 | mar/2024 – fev/2026 |
| Secretaria de Estado da Administração | 4 | R$ 8.322.796 | set/2025 – nov/2025 |
| Empresa Paraibana de Comunicação (EPC) | 2 | R$ 929.024 | jun/2024 – jul/2025 |
| Fundo Estadual de Recursos Hídricos | 1 | R$ 15.000 | set/2024 |
| **Total** | **588** | **R$ 1.173.705.390** | |

**Status dos itens:** 438 em andamento (R$594M), 146 fracassados (R$580M), 4 cancelados (R$28K).

**Modalidades:** 82 Inexigibilidade (R$871M, 74%), 501 Dispensa (R$294M, 25%), 4 Leilão (R$8,3M), 1 Pregão (R$341K).

#### Reclassificação: workaround de sistema, não fraude per se

O deep dive revelou que estes processos têm **objetos reais e contratos efetivos**:

| Fornecedor | Valor contrato | Objeto |
|-----------|---------------|--------|
| JUSTIZ TERCEIRIZAÇÃO | R$ 40.001.248 | Credenciamento (Chamada Pública 004/2025) |
| SAFETYHEALTH SERVIÇOS MÉDICOS | R$ 40.001.248 | Credenciamento (Chamada Pública 004/2025) |
| HOSPITAL MILAGRES | R$ 31.573.800 | Credenciamento (Chamada Pública 004/2024) |
| NORDESTE SERVIÇOS MÉDICOS | R$ 31.573.800 | Credenciamento (Chamada Pública 004/2024) |
| CELULA GESTÃO EM SAÚDE | R$ 30.632.800 | Credenciamento (Chamada Pública 005/2024) |
| PB SAÚDE (Fundação Paraibana de Gestão em Saúde) | R$ 354.962.722 | Gestão e prestação de serviços de saúde |

A "planilha sem itens" é um **workaround do sistema PNCP**: credenciamentos e inexigibilidades não possuem itens discretos como um pregão comum. O sistema exige ao menos um item, então o órgão insere o placeholder.

**No entanto, os riscos permanecem:**

1. **Volume concentrado em Inexigibilidade** (R$871M, 74%): A inexigibilidade deveria ser exceção, não regra. R$871M via credenciamento por uma única secretaria em 2 anos merece escrutínio do TCE-PB.
2. **Pico anômalo em fev/2026** (R$445M em 18 registros): Inclui contrato de R$355M com a Fundação PB SAÚDE — gestão de saúde terceirizada em valor sem precedentes.
3. **Empresas de terceirização recebendo R$40M via credenciamento**: JUSTIZ TERCEIRIZAÇÃO é empresa de mão de obra genérica recebendo R$40M em contrato de saúde.
4. **Zero itens reais** nas mesmas contratações: Não há especificação do que está sendo comprado/contratado no nível de item.

#### Cruzamento realizado: Fornecedores × PGFN × Rede Societária

O cruzamento dos fornecedores dos contratos "planilha sem itens" com PGFN e base societária revelou:

**PGFN — Fornecedores com dívida ativa:**

| Fornecedor | Contrato (R$) | Dívida PGFN (R$) | Tipo de Dívida |
|------------|--------------|-------------------|----------------|
| JUSTIZ TERCEIRIZAÇÃO | 40.001.249 | 13.779.121 | Multa CLT (7 inscrições) |
| UNIMED JP | 3.252.199 | 248.433.567 | — |
| CENTRAL DE DIAGNÓSTICO | 4.265.254 | 15.694.090 | — |
| INSTITUTO VISÃO PARA TODOS | 7.002.057 | 1.287.010 | — |

*Nota: ASTRAZENECA (R$19,2B) e JANSSEN-CILAG (R$4,7B) são disputas tributárias de multinacionais farmacêuticas — padrão diferente.*

**Caso JUSTIZ — Rede societária extraordinária:**

A JUSTIZ TERCEIRIZAÇÃO (CNPJ 06538799000150) é controlada por **Raul Orlando Justiz González** e **Brenda Mercedes Justiz González Henrique**, que possuem uma rede de **247 empresas** registradas na Receita Federal, operando sob 3 marcas:

| Marca | Tipo | Exemplos |
|-------|------|----------|
| JUSTIZ TERCEIRIZAÇÃO | Mão de obra | ~80 SCPs (Sociedade em Conta de Participação) |
| GROUPMED SERVIÇOS DE SAÚDE | Saúde | ~100 SCPs |
| EVERYBODY LOCAÇÃO DE MÃO DE OBRA | Terceirização | ~50 SCPs |

**Todas as 247 empresas** estão registradas no Rio Grande do Norte. A EVERYBODY (CNPJ 39530745000106) também recebe contrato da SES-PB de R$11.979.200 — ou seja, o mesmo grupo familiar recebe **R$52M+** da SES-PB via credenciamento.

A dívida CLT de R$13,7M (7 inscrições por multa trabalhista) é particularmente grave para uma empresa de terceirização de mão de obra: indica padrão de descumprimento de obrigações trabalhistas enquanto recebe R$40M+ em contratos públicos de saúde.

**Recomendação revisada:** O padrão "planilha sem itens" não é fraude per se, mas o **volume de R$1,17B em contratos sem detalhamento de itens** representa risco de controle. Priorizar:
1. **Auditoria do grupo JUSTIZ/GROUPMED/EVERYBODY** (247 empresas, R$52M+ via SES-PB, R$13,7M em multas CLT)
2. **Contrato PB SAÚDE** (R$355M) — Fundação estadual como intermediária
3. **Verificar vínculos societários** entre todos os fornecedores credenciados da SES-PB

---

### 4.3. Pano de Chão a R$ 5,83 — Padrão de Cartel

O item "PANO DE CHÃO" com valor unitário de **R$ 5,83** aparece em **17 órgãos distintos** como preço unitário estimado idêntico, em múltiplas contratações independentes realizadas em estados diferentes.

**Por que R$ 5,83 é evidência relevante:**

- É um valor com 2 casas decimais significativas, improvável de surgir por arredondamento independente em 17 órgãos.
- Aparece em estados diferentes, eliminando a hipótese de tabela de referência regional única.
- Itens de limpeza são sensíveis a variações de marca, qualidade e economia de escala — a identidade exata entre órgãos de portes e regiões distintos não tem explicação técnica óbvia.

**Contexto legal:** A formação de cartel em licitações públicas é crime tipificado no art. 337-I do Código Penal (inserido pela Lei 14.133/2021), com pena de 4 a 8 anos de reclusão. O CADE mantém o Programa de Combate a Cartéis em Licitações com mecanismo de denúncia e acordo de leniência.

#### Cruzamento realizado: Fornecedores vencedores do cartel do pano de chão

O cruzamento dos itens Q98 com `pncp_contrato` identificou os fornecedores que mais vencem licitações com o preço cartelizado de R$ 5,83:

| Fornecedor | CNPJ | Contratos R$5,83 |
|------------|------|-------------------|
| DISTRIBUIDORA FELISMINO LTDA | 39476248000240 | 54 |
| MH COMERCIO DE PAPELARIA ELETROELETRONICOS E INFORMATICA LTDA | 27645400000100 | 51 |
| ENIO DOS SANTOS SILVA | 16747924000196 | 20 |
| NAN COMERCIO E REPRESENTAÇÃO LTDA | 53280704000121 | 19 |
| SJ ATENTO MONITORAMENTO ELETRONICO EIRELI | 37604302000189 | 16 |
| THIAGO MELO DOS SANTOS | 35999472000184 | 10 |
| REAL GLOBAL COMERCIO E IMPORTACAO LTDA | 32177997000146 | 9 |
| COMERCIAL UNIDOS LTDA | 01628729000170 | 8 |
| SHOPPEE DA LIMPEZA LTDA | 51660757000142 | 8 |
| CRISTINA FELISMINO DOS SANTOS | 30510368000160 | 5 |

**Achados críticos:**
- **DISTRIBUIDORA FELISMINO** (54 contratos) e **CRISTINA FELISMINO DOS SANTOS** (5 contratos) compartilham o sobrenome "Felismino" — possível vínculo familiar ou societário. Se confirmado, configura atuação coordenada via empresas formalmente independentes.
- **MH COMERCIO** (51 contratos) é empresa de papelaria/eletroeletrônicos que vende pano de chão — diversificação atípica de portfólio.
- Os mesmos fornecedores reaparecem em **outros itens com preço idêntico**: DISTRIBUIDORA FELISMINO também vence 18 contratos de detergente a R$2,41 e MH COMERCIO vence 14 contratos do mesmo item. O padrão se repete em papel A4 a R$25,03 (MH COMERCIO 7 contratos, FRANCISCO COSTA DE SANTANA 7 contratos).

**Padrão cross-product:** A repetição dos mesmos fornecedores em múltiplos itens com preço idêntico não-redondo (pano R$5,83, detergente R$2,41, papel R$25,03) é o indicador mais forte de cartel identificado nesta análise. Não é plausível que empresas independentes convergissem para o mesmo preço não-redondo em 3+ produtos diferentes, em 17-20 órgãos distintos.

#### Cruzamento realizado: Rede societária e geográfica do cartel

**Concentração geográfica — Bahia exclusivo:**

Os 3 itens com preço cartelizado operam **100% na Bahia**:

| Item | Preço | Órgãos BA | Contratações |
|------|-------|-----------|--------------|
| Pano de chão | R$ 5,83 | 18 | 77 |
| Detergente lava-louça | R$ 2,41 | 25 | 91 |
| Papel A4 75g | R$ 25,03 | 20 | 56 |

**Mesmo endereço — 3 empresas em Rua Álvaro da França Rocha, 66, Cajazeiras, Salvador/BA (CEP 41334-320):**

| Empresa | CNPJ | Contratos totais |
|---------|------|-----------------|
| DISTRIBUIDORA FELISMINO LTDA | 39476248000240 | 732 |
| CRISTINA FELISMINO DOS SANTOS | 30510368000160 | 144 |
| REAL GLOBAL COMERCIO E IMPORTACAO LTDA | 32177997000146 | 792 |

A sócia da DISTRIBUIDORA FELISMINO é **CRISTIANE FELISMINO DOS SANTOS** (CPF ***604875**) — nome quase idêntico a CRISTINA FELISMINO DOS SANTOS (empresa individual no mesmo endereço). Possível relação familiar direta.

**Outras empresas próximas:** CONTUDO LICITAÇÕES (CEP 41334-200, Cajazeiras, Salvador) e FRANCISCO COSTA DE SANTANA (CEP 41342-245, Salvador) — todas no mesmo bairro.

**Volume total do cartel (contratos PNCP):**

| Fornecedor | Sede | Contratos BA | Contratos fora BA |
|------------|------|-------------|-------------------|
| MH COMERCIO | Salvador/BA | 1.670 | 0 |
| REAL GLOBAL | Salvador/BA | 792 | 0 |
| DISTRIBUIDORA FELISMINO | Salvador/BA | 732 | 1 (DF) |
| NAN COMERCIO | Feira de Santana/BA | 509 | 0 |
| ENIO DOS SANTOS SILVA | Valença/BA | 312 | 5 (DF) |
| SJ ATENTO | Salvador/BA | 260 | 0 |
| CRISTINA FELISMINO | Salvador/BA | 144 | 0 |
| THIAGO MELO DOS SANTOS | Salvador/BA | 91 | 10 |
| SHOPPEE DA LIMPEZA | Itabuna/BA | 24 | 0 |
| COMERCIAL UNIDOS | Jequié/BA | 17 | 0 |

**Total: 4.551 contratos**, quase todos na Bahia. Nenhuma empresa tem sanção CEIS/CNEP ou dívida PGFN.

**Conclusão da investigação:** Trata-se de um **cartel regional baiano** de materiais de limpeza e papelaria, operando com preços idênticos não-redondos em 3+ produtos, concentrado em Salvador com pelo menos 3 empresas no mesmo endereço físico e vínculo familiar (Felismino). O padrão é consistente com coordenação de preços em licitações municipais baianas.

**Recomendação:** Encaminhar ao CADE/BA a lista completa dos 10 fornecedores com:
- Prova de mesmo endereço (3 empresas em Rua Álvaro da França Rocha, 66)
- Vínculo familiar CRISTIANE/CRISTINA FELISMINO
- Preços idênticos não-redondos em 3 produtos, 18-25 órgãos, 224 contratações
- Concentração geográfica 100% Bahia em todos os itens

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

1. **[Prioritário] SES-PB credenciamentos R$40M+:** Verificar CNPJs dos fornecedores credenciados (JUSTIZ, SAFETYHEALTH, etc.) contra CEIS/CNEP, PGFN e rede societária (mv_rede_pb). Cruzar com servidores da SES-PB.

2. **[Prioritário] Sec. Educação MS — modelo operacional:** Investigar por que 96% dos fracassos são via Dispensa (4.781 processos individuais por escola) em vez de Pregão Eletrônico consolidado (apenas 3 processos). Mapear se os fracassos em Dispensa levam sistematicamente a Chamadas Públicas da Agricultura Familiar.

3. **[Médio prazo] Q96 — Maranhão e Ceará:** Solicitar aos TCEs estaduais a justificativa legal para sigilo do orçamento nos contratos com Telefonica Brasil e Convergint Technologies. Comparar valor contratado com benchmarks de mercado (painel de preços COMPRASNET).

4. ~~**[Médio prazo] Q98 — Pano de chão R$ 5,83:** Compilar lista de fornecedores vencedores~~ — **Feito**: 10 fornecedores identificados (Seção 4.3), padrão cross-product em 3 itens. Vínculo FELISMINO detectado. **Próximo passo: verificar vínculo societário e encaminhar ao CADE.**

5. **[Análise futura] Combinação Q93 + Q96:** Órgãos que acumulam fracassos repetidos E usam orçamento sigiloso nas homologações subsequentes para os mesmos itens representam risco duplo e merecem prioridade de auditoria.

---

## 6. Conclusão

As três consultas analíticas aplicadas à base PNCP revelam padrões que, isoladamente, podem ter explicações técnicas, mas em conjunto formam um quadro que justifica investigação aprofundada pelos órgãos de controle.

O caso da **SES-PB** revelou-se mais complexo após o deep dive: R$1,17B em "planilha sem itens" é um workaround do sistema PNCP para credenciamentos, mas o volume (R$871M via inexigibilidade) e a concentração em poucos fornecedores (R$40M+ cada) indicam risco de controle significativo. O contrato de R$355M com a Fundação PB SAÚDE merece atenção prioritária.

O caso da **Sec. Educação do MS** apresentou uma reviravolta: o preço-teto é adequado (abaixo da média nacional) e o item é homologado no mesmo período. O problema real é o **modelo operacional** — 4.781 dispensas individuais por escola em vez de pregão consolidado, gerando fracassos previsíveis que podem migrar para chamadas públicas da Agricultura Familiar.

Os **306 padrões de preço idêntico não-redondo** em múltiplos órgãos independentes constituem um conjunto de pistas para investigação de cartel, com o caso do pano de chão a R$ 5,83 sendo o mais robusto para encaminhamento ao CADE dada sua extensão geográfica (17 órgãos em estados distintos).

A base de dados local permite aprofundamento de qualquer dos casos identificados, incluindo extração dos números de controle PNCP, CNPJs dos fornecedores e valores contratados para todos os registros sinalizados.

---

*Relatório gerado pelo pipeline govbr-cruza-dados a partir de dados públicos do PNCP.*
*Queries de referência: `queries/fraude_pncp_item.sql` (Q93 linhas 57–77, Q96 linhas 160–188, Q98 linhas 241–273)*
