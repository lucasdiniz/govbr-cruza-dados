# Relatório de Análise: Rede Societária e de Relacionamentos na Paraíba

**Data de Geração:** 3 de Abril de 2026
**Base de Dados:** mv_rede_pb — grafo de relacionamentos com 1.682.085 arestas e 5 tipos de vínculo
**Metodologia:** Grafo bipartido construído pela união de vínculos de fornecimento municipal (TCE-PB SAGRES), servidores municipais (TCE-PB SAGRES), credores estaduais (PGE-PB), sócios de empresas (Receita Federal CNPJ) e doadores de campanha (TSE). Cada aresta representa um vínculo ativo em pelo menos uma base de dados.

> **Disclaimer:** Este relatório apresenta a estrutura de relacionamentos identificados em bases de dados públicas, não conclusões de irregularidade. A existência de múltiplos vínculos entre pessoas e entidades — ser sócio de uma empresa que também fornece ao setor público, por exemplo — é permitida por lei na maioria dos casos. As situações descritas merecem atenção analítica, mas a apuração de irregularidades compete aos órgãos de controle (TCE-PB, CGE-PB, MPE-PB).

---

## 1. Resumo Executivo

A base **mv_rede_pb** mapeia **1.682.085 arestas** de relacionamento entre pessoas físicas, pessoas jurídicas e entes públicos na Paraíba. São 5 tipos de vínculo: fornecimento a municípios, vínculo empregatício como servidor municipal, crédito com o estado, sociedade empresarial e doação a campanhas eleitorais.

A densidade do grafo revela que a administração pública paraibana está interligada a uma rede extensa de atores privados. O segmento mais expressivo é o de fornecedores municipais (774.114 arestas), seguido por servidores municipais (592.777 arestas). Juntos, esses dois tipos representam **81,8% de todos os vínculos**.

A análise identifica três padrões de atenção: (1) hubs individuais com participação societária em dezenas de empresas; (2) atores multi-papel que acumulam simultaneamente vínculos de servidor público, sócio de empresa e credor estadual; e (3) sobreposição de vínculos de servidores que são também sócios de empresas que podem fornecer a entes públicos.

---

## 2. Metodologia

A rede foi construída como um **grafo não-direcionado** com dois tipos de nós: pessoas (CPF) e entidades (CNPJ ou código de órgão). As arestas foram geradas pela união de cinco fontes:

| Fonte | Tipo de Aresta | Descrição |
|-------|---------------|-----------|
| TCE-PB SAGRES (despesas) | FORNECEDOR_MUNICIPAL | Empresa com ao menos um empenho pago por município paraibano |
| TCE-PB SAGRES (RH) | SERVIDOR_MUNICIPAL | Pessoa física com vínculo de servidor em município paraibano |
| PGE-PB / Sistema estadual | CREDOR_ESTADUAL_PF | Pessoa física credora do estado da Paraíba |
| Receita Federal CNPJ | SOCIO | Pessoa física como sócia ou administradora de empresa |
| TSE (prestações de contas) | DOADOR_CAMPANHA | Pessoa física doadora de campanha eleitoral na Paraíba |

A identidade de pessoas físicas entre as fontes foi resolvida por CPF normalizado. Duplicatas dentro do mesmo tipo de aresta foram eliminadas — o que significa que cada aresta representa um relacionamento único (pessoa-entidade por tipo), independentemente do número de transações subjacentes.

---

## 3. Estrutura da Rede

### 3.1. Volume por Tipo de Aresta

| Tipo de Aresta | Quantidade | % do Total |
|----------------|-----------|------------|
| FORNECEDOR_MUNICIPAL | 774.114 | 46,0% |
| SERVIDOR_MUNICIPAL | 592.777 | 35,2% |
| CREDOR_ESTADUAL_PF | 206.219 | 12,3% |
| SOCIO | 99.294 | 5,9% |
| DOADOR_CAMPANHA | 9.681 | 0,6% |
| **Total** | **1.682.085** | **100%** |

### 3.2. Observações sobre a Estrutura

O maior segmento, **FORNECEDOR_MUNICIPAL** (774 mil arestas), reflete a amplitude do cadastro de fornecedores dos 223 municípios paraibanos. Cada CNPJ que emitiu ao menos uma nota fiscal a um município gera uma aresta por município contratante, o que explica o volume elevado.

O segmento **SERVIDOR_MUNICIPAL** (592 mil arestas) inclui todos os vínculos de RH registrados no SAGRES, incluindo cargos comissionados e contratos temporários. O volume sugere que muitos servidores acumulam vínculos em mais de um município — fenômeno relevante na análise de atores multi-papel.

O tipo **DOADOR_CAMPANHA** é o menos representado (9.681 arestas, 0,6%), o que é esperado: o universo de doadores formais de campanha é pequeno em comparação ao de servidores ou fornecedores.

---

## 4. Hubs de Maior Conexão Societária

Os indivíduos com maior número de empresas como sócio são os nós mais conectados do subgrafo de vínculos SOCIO.

| Pessoa | Empresas como Sócio |
|--------|-------------------|
| ROBERTO GERMANO BEZERRA CAVALCANTI | 28 |
| RICARDO DE BRITTO ALVES | 17 |
| RUY BEZERRA CAVALCANTI NETO | 16 |
| UBIRAJARA INDIO DO CEARA FILHO | 14 |
| THIAGO ARARUNA LUCENA | 14 |
| ITAMAR MANGUEIRA DE SOUZA JUNIOR | 14 |
| PRISCILA REGINA CANDIDO ESPINOLA UCHOA | 13 |
| WEBERTON DE ARAUJO BARRETO | 12 |
| RAFAEL PIRES COELHO | 12 |
| BEATRIZ LINS DE ALBUQUERQUE RIBEIRO | 12 |

**Nota:** Participação societária em múltiplas empresas é prática empresarial legítima. O relevante para fins de auditoria é verificar se essas empresas contratam com o poder público e se há impedimentos legais (como vedação a parentes de agentes políticos ou servidores em posição de conflito de interesse).

### 4.1. Padrão Familiar: Rede Cavalcanti

Dois dos dez maiores hubs societários compartilham o sobrenome Cavalcanti:

- **ROBERTO GERMANO BEZERRA CAVALCANTI** — sócio de 28 empresas, servidor municipal em 4 municípios
- **RUY BEZERRA CAVALCANTI NETO** — sócio de 16 empresas

A coincidência de sobrenomes e o elevado número de empresas em comum sugere uma rede de negócios familiar com ampla presença no mercado fornecedor do estado. A verificação dos CNPJs em comum entre as carteiras de Roberto e Ruy permitiria confirmar a sobreposição societária.

---

## 5. Atores Multi-Papel

Atores multi-papel são pessoas físicas que aparecem simultaneamente em 3 ou mais tipos de aresta distintos. São os nós de maior risco analítico, pois concentram vínculos que, em conjunto, podem configurar conflito de interesses.

### 5.1. Pessoas com 3 Tipos de Vínculo Simultâneos

| Nome | Papéis | Conexões Totais |
|------|--------|----------------|
| VALDEMIRO TAVARES LUCENA | Credor Estadual, Servidor Municipal, Sócio | 16 |
| RAFAEL LINDENBERG ANDRADE DA COSTA | Credor Estadual, Servidor Municipal, Sócio | 14 |
| WALESKA RODRIGUES BARBOSA | Credor Estadual, Servidor Municipal, Sócio | 14 |
| WESLLEY RENATO FLORIANO LUCAS | Credor Estadual, Servidor Municipal, Sócio | 14 |
| VITORIA LIGIA DE OLIVEIRA CASSIMIRO | Credor Estadual, Servidor Municipal, Sócio | 14 |

Todas as cinco pessoas identificadas com 3 papéis simultâneos acumulam exatamente os mesmos tipos de vínculo: **CREDOR_ESTADUAL_PF + SERVIDOR_MUNICIPAL + SOCIO**. Isso indica que este tríplice vínculo é o padrão mais comum de sobreposição — e não foi encontrado ninguém com 4 tipos simultâneos na amostra.

**Interpretação:** A ausência de DOADOR_CAMPANHA nos tríplices vínculos indica que doadores de campanha constituem uma população com baixa sobreposição com servidores e sócios de empresa — possivelmente porque doadores formais são empresários em sentido estrito, não servidores.

### 5.2. Servidores que São Também Sócios de Empresas

A sobreposição entre SERVIDOR_MUNICIPAL e SOCIO é o padrão de maior relevância para detecção de pejotização e conflito de interesses.

| Nome | Empresas como Sócio | Municípios como Servidor |
|------|-------------------|--------------------------|
| ROBERTO GERMANO BEZERRA CAVALCANTI | 28 | 4 |
| THALLIO ROSADO DE SA XAVIER | 16 | 6 |
| ROSINALVA GALDINO RIBEIRO | 14 | 1 |
| UBIRACI ANTONIO DA SILVA | 14 | 2 |
| RENAN CARDOZO DE VASCONCELOS | 12 | 10 |
| SERGIO RICARDO LEITE PEREIRA | 12 | 3 |

**Caso de destaque — RENAN CARDOZO DE VASCONCELOS:** Vinculado como servidor a **10 municípios diferentes** e sócio de **12 empresas**. O alcance geográfico de 10 municípios como servidor é excepcional — a média de servidores que aparecem em mais de um município é muito menor. Esse padrão pode indicar acúmulo irregular de cargos, contratos temporários simultâneos ou registro de lotação em múltiplos entes.

**Caso de destaque — THALLIO ROSADO DE SA XAVIER:** Servidor em 6 municípios e sócio de 16 empresas. A combinação de ampla presença como servidor com carteira societária diversificada merece verificação de eventual conflito entre as atividades empresariais e as funções públicas exercidas.

---

## 6. Padrões Identificados

### 6.1. Concentração Societária Familiar

A presença de ROBERTO GERMANO BEZERRA CAVALCANTI (28 empresas) e RUY BEZERRA CAVALCANTI NETO (16 empresas) no topo do ranking societário, combinada com a presença de Roberto como servidor em 4 municípios, configura um padrão de rede familiar com potencial acesso privilegiado a contratos públicos. Uma análise das sobreposições de CNPJ entre as carteiras dos dois permitiria mapear a extensão da rede.

### 6.2. Amplitude Geográfica como Indicador de Risco

O número de municípios em que uma pessoa aparece como servidor é um indicador de risco por si só. Servidores municipais são, por definição, vinculados a um único ente. A presença em múltiplos municípios indica contratos temporários simultâneos (permitidos em algumas situações) ou registros inconsistentes no SAGRES. Os casos de RENAN CARDOZO (10 municípios) e THALLIO ROSADO (6 municípios) merecem verificação.

### 6.3. Ausência de Doadores na Sobreposição Multi-Papel

Nenhum ator apresentou 4 tipos de vínculo simultâneos. O tipo DOADOR_CAMPANHA (0,6% das arestas) não aparece nos tríplices vínculos identificados, o que sugere que:
- O universo de doadores formais é pequeno e relativamente separado dos servidores e sócios; ou
- Doadores que são também servidores e sócios existem, mas em número abaixo do limiar de detecção desta análise.

Essa separação pode ser explorada em análise futura cruzando doadores com o cadastro de servidores.

### 6.4. Assimetria entre Fornecedores e Sócios

O tipo FORNECEDOR_MUNICIPAL (774 mil arestas) é 7,8 vezes maior que o tipo SOCIO (99 mil arestas). Isso indica que a maioria dos fornecedores municipais tem estrutura societária simples (1-2 sócios), enquanto um grupo restrito de pessoas concentra participação em muitas empresas. A análise de quais sócios dos hubs têm empresas no cadastro de fornecedores municipais é o próximo passo natural desta investigação.

---

## 7. Limitações

1. **Vínculos, não transações:** A mv_rede_pb registra a existência de um vínculo, não seu valor ou frequência. Uma empresa que fez um único empenho de R$ 500 e outra que faturou R$ 50 milhões geram o mesmo tipo de aresta FORNECEDOR_MUNICIPAL.

2. **Resolução de identidade:** A correspondência entre pessoas nas diferentes fontes é feita por CPF. Erros de digitação ou CPFs ausentes em alguma das bases podem gerar subcontagem de sobreposições ou falsos positivos por homonímia em casos sem CPF.

3. **Temporalidade:** A rede agrega vínculos de diferentes períodos (2018-2026 conforme a fonte). Um sócio que saiu da empresa em 2019 e um servidor que assumiu cargo em 2024 aparecem na mesma rede, mesmo que nunca tenham coexistido nos mesmos papéis.

4. **Legalidade dos vínculos:** A grande maioria dos vínculos identificados é perfeitamente legal. Ser sócio de uma empresa e também servidor público não é, por si só, irregular — depende do cargo, da natureza da empresa e das restrições específicas aplicáveis.

5. **Cobertura parcial de sócios:** A base de sócios da Receita Federal inclui apenas empresas com CNPJ ativo ou baixado registrado na base nacional. Participações por interpostas pessoas ou estruturas off-shore não são capturadas.

---

## 8. Fontes

1. **TCE-PB SAGRES:** Despesas e empenhos municipais — tipo FORNECEDOR_MUNICIPAL
2. **TCE-PB SAGRES:** Folha de pessoal e RH municipais — tipo SERVIDOR_MUNICIPAL
3. **PGE-PB / Sistema de credores estaduais:** Credores PF do estado da Paraíba — tipo CREDOR_ESTADUAL_PF
4. **Receita Federal — Dados Abertos CNPJ:** Quadro societário de empresas — tipo SOCIO
5. **TSE — Dados Abertos de Prestação de Contas:** Doadores de campanha — tipo DOADOR_CAMPANHA
6. **mv_rede_pb:** View materializada consolidando os 5 tipos de aresta, 1.682.085 registros
