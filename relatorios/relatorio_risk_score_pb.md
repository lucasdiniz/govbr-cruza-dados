# Relatório de Auditoria: Score de Risco Unificado de Entidades na Paraíba

**Data de Geração:** 3 de Abril de 2026
**Base de Dados:** v_risk_score_pb (view unificada) | mv_servidor_pb_risco (materialized view servidores) | mv_empresa_pb (materialized view empresas)
**Metodologia:** Score de 0-100 baseado em fatores de risco ponderados. Entidades classificadas como EMPRESA, SERVIDOR ou PESSOA_PF. Dados federais (CNPJ, CEIS, PGFN, BNDES, TSE, Bolsa Família, SIAPE) cruzados com dados estaduais (TCE-PB/SAGRES).

> **Disclaimer:** Este relatório apresenta indicadores estatísticos de risco, não conclusões de irregularidade ou ilicitude. Scores altos indicam padrões que merecem atenção dos órgãos de controle, mas podem ter explicações legítimas (acúmulo de cargo permitido por lei, dívida fiscal parcelada, inatividade empresarial por motivos regulatórios, etc.). A apuração de eventual irregularidade compete exclusivamente aos órgãos competentes (CGE-PB, TCE-PB, CGU, MPF/MPE).

---

## 1. Resumo Executivo

Foram avaliadas **135.237 entidades** vinculadas à Paraíba — 104.234 empresas (CNPJ), 31.002 servidores públicos e 1 pessoa física avulsa — por meio de um score de risco composto que integra mais de 15 fontes de dados federais e estaduais.

O score varia de 0 a 100. A distribuição é fortemente concentrada na faixa baixa (0-39), o que é esperado: a maioria das entidades não apresenta combinações de fatores de risco. Entretanto, **8.056 entidades** (6,0% do total) atingem score igual ou superior a 40, faixa que recomenda atenção.

**Distribuição por faixa de risco:**

| Tipo | Total avaliado | Alto (>= 70) | Medio (40-69) | Baixo (1-39) | Score medio |
|------|---------------|-------------|--------------|-------------|-------------|
| EMPRESA | 104.234 | 8 | 3.430 | 100.796 | 22,0 |
| SERVIDOR | 31.002 | 73 | 2.545 | 28.384 | 17,8 |
| PESSOA_PF | 1 | 0 | 0 | 1 | 15,0 |
| **Total** | **135.237** | **81** | **5.975** | **129.181** | — |

Adicionalmente, 322.175 servidores cadastrados no SIAPE/PB possuem score zero (ausencia de quaisquer flags de risco), totalizando **353.177 servidores** avaliados na view mv_servidor_pb_risco.

**Destaques quantitativos:**
- **2.618 servidores** apresentam conflito de interesses (vinculo ativo com empresa que contratou o poder publico)
- **25.883 servidores** recebem Bolsa Familia concomitantemente ao salario publico
- **1.033 servidores** sao socios de 3 ou mais empresas simultaneamente

---

## 2. Metodologia — Pesos do Score

### 2.1. Score de Empresas (mv_empresa_pb)

| Fator de risco | Flag | Pontos |
|---------------|------|--------|
| Empresa inativa no CNPJ | flag_inativa | 20 |
| Constante no CEIS (sancoes vigentes) | flag_ceis_vigente | 25 |
| Capital social desproporcional ao faturamento publico | flag_capital_desproporcional | 15 |
| Contratada por multiplos municipios (> 1) | flag_multi_municipal | 10 |
| Predominancia de contratos sem licitacao | flag_predomina_sem_licitacao | 15 |
| Divida ativa na PGFN | flag_divida_pgfn | 15 |
| **Total maximo** | | **100** |

### 2.2. Score de Servidores (mv_servidor_pb_risco)

| Fator de risco | Flag | Pontos |
|---------------|------|--------|
| Conflito de interesses (socio de empresa contratante) | flag_conflito_interesses | 40 |
| Socio de multiplas empresas (>= 3) | flag_multi_empresa | 10 |
| Recebe Bolsa Familia | flag_bolsa_familia | 15 |
| Duplo vinculo com o estado (acumulacao) | flag_duplo_vinculo_estado | 15 |
| Alto salario como socio em empresa contratante | flag_alto_salario_socio | 20 |
| **Total maximo** | | **100** |

O score de conflito de interesses e o de maior peso (40 pts) por ser o indicador de maior potencial lesivo direto ao erario: o servidor e simultaneamente beneficiario de contratos que deveria fiscalizar ou influenciar.

---

## 3. Distribuicao de Risco

### 3.1. Empresas

Das 104.234 empresas avaliadas, apenas **3.438** (3,3%) atingem score >= 40. O score medio de 22,0 indica que a maioria das empresas acumula apenas 1 ou 2 flags isoladas (ex.: inatividade no CNPJ sem outros agravantes).

As 8 empresas com score >= 70 combinam pelo menos 3 flags graves, tipicamente: inatividade + sancao CEIS + divida PGFN. Esse padrao sugere empresas que continuaram contratando mesmo apos sancoes, ou que acumularam dividas fiscais sem encerramento formal.

### 3.2. Servidores

Dos 353.177 servidores analisados, **91,2% (322.175)** tem score zero. Entre os que possuem algum flag:

| Faixa | Servidores | % do total |
|-------|-----------|------------|
| Alto risco (>= 70) | 73 | 0,02% |
| Medio risco (40-69) | 2.545 | 0,72% |
| Baixo risco (1-39) | 28.384 | 8,04% |
| Score zero | 322.175 | 91,22% |

Os 2.618 servidores com conflito de interesses (flag_conflito_interesses = true) sao o subconjunto mais critico: sao profissionais que acumulam remuneracao publica e participacao societaria em empresas que receberam pagamentos publicos no estado da Paraiba.

---

## 4. Entidades de Maior Risco

### 4.1. Empresas — Score >= 70

| Empresa | Score | Flags | Contratado (total) |
|---------|-------|-------|-------------------|
| ABBC - ASSOCIACAO BRASILEIRA DE BENEFICENCIA COMUNITARIA | 75 | INATIVA, CEIS, CAPITAL_DESPROPORCIONAL, DIVIDA_PGFN | R$ 47,7M |
| MAPA MIX COMERCIO LTDA | 70 | INATIVA, CEIS, MULTI_MUNICIPAL, DIVIDA_PGFN | R$ 501K |
| MODERNA HOSPITALAR COMERCIO DE MATERIAIS MEDICOS E ORTOPEDICOS LTDA | 70 | INATIVA, CEIS, MULTI_MUNICIPAL, DIVIDA_PGFN | R$ 5M |
| PREVIX PRODUTOS PARA SAUDE LTDA | 70 | INATIVA, CEIS, MULTI_MUNICIPAL, DIVIDA_PGFN | R$ 80K |

**Analise:** A ABBC, com score mais alto (75) e R$ 47,7M contratados, combina 4 flags: inatividade cadastral, sancao vigente no CEIS, capital social desproporcional ao volume contratado e divida com a Uniao. E a entidade com maior potencial de prejuizo ao erario paraibano entre as avaliadas. As demais empresas seguem o padrao de fornecedores de materiais medicos e hospitalares — setor historicamente critico em auditorias de compras publicas — com combinacao de inatividade + CEIS + atuacao em multiplos municipios + divida PGFN.

### 4.2. Servidores — Score >= 70

Os 73 servidores de alto risco sao quase exclusivamente medicos. Abaixo os casos com maior volume financeiro associado ao conflito de interesses:

**REGIS COSTA BOMFIM — MEDICO | Score: 70**
- Flags: CONFLITO_INTERESSES, MULTI_EMPRESA, ALTO_SALARIO_SOCIO
- Numero de empresas como socio: 10
- Volume de contratos publicos das suas empresas: R$ 1,38M
- Municipios com conflito identificado: Joao Pessoa, Santa Rita

**NARAYANE DE OLIVEIRA SILVA SOARES — MEDICO PLANTONISTA | Score: 70**
- Flags: CONFLITO_INTERESSES, MULTI_EMPRESA, ALTO_SALARIO_SOCIO
- Numero de empresas como socio: 3
- Volume de contratos publicos das suas empresas: R$ 4,29M
- Municipios com conflito identificado: Amparo, Caraúbas, Sume, Zabele

**GUSTAVO ANACLETO LOURENCO COELHO — MEDICO OFTALMOLOGISTA | Score: 70**
- Flags: CONFLITO_INTERESSES, MULTI_EMPRESA, ALTO_SALARIO_SOCIO
- Numero de empresas como socio: 3
- Volume de contratos publicos das suas empresas: R$ 1,95M
- Municipios com conflito identificado: Cajazeiras

**RAFAEL DE ARRUDA SOUSA PINTO — MEDICO | Score: 70**
- Flags: CONFLITO_INTERESSES, MULTI_EMPRESA, ALTO_SALARIO_SOCIO
- Numero de empresas como socio: 5
- Volume de contratos publicos das suas empresas: R$ 1,08M
- Municipios com conflito identificado: Cruz do Espirito Santo, Guarabira, Joao Pessoa, Sao Bento

**Outros servidores com score 70 (servidores publicos, nao medicos):**

| Servidor | Cargo/Vinculo | Flags | Contratado |
|----------|--------------|-------|-----------|
| ANTONIO COUTINHO MADRUGA NETO | Servidor | CONFLITO_INTERESSES, MULTI_EMPRESA, ALTO_SALARIO_SOCIO | R$ 27K |
| SILVIO ROMERO GONCALVES MONTEIRO SOBRINHO | Servidor | CONFLITO_INTERESSES, MULTI_EMPRESA, ALTO_SALARIO_SOCIO | R$ 28K |
| MELISSA MEDEIROS LEITE FERRANTTI | Servidor | CONFLITO_INTERESSES, MULTI_EMPRESA, ALTO_SALARIO_SOCIO | R$ 24K |
| ROSINETE GUEDES LOPES BARRETO | Servidor | CONFLITO_INTERESSES, MULTI_EMPRESA, ALTO_SALARIO_SOCIO | R$ 24K |

---

## 5. Padroes Identificados

### 5.1. Medicos como principal grupo de risco entre servidores

Quase a totalidade dos 73 servidores com score >= 70 sao medicos. Isso reflete uma particularidade estrutural da area de saude publica:

1. **Medicos com dupla atuacao:** E comum que medicos sejam simultaneamente servidores publicos de saude e socios de clinicas, operadoras ou distribuidores que contratam com prefeituras ou o estado. A legislacao admite acumulacao de cargos medicos em determinadas condicoes, mas nao afasta o risco de conflito de interesses quando a empresa do medico e contratada pela mesma entidade que o remunera como servidor.

2. **Capilaridade municipal:** Os casos identificados mostram medicos atuando em 3 a 10 municipios diferentes simultaneamente, maximizando o volume de contratos das suas empresas.

3. **Volume financeiro elevado:** O maior caso individual (NARAYANE DE OLIVEIRA SILVA SOARES) apresenta R$ 4,29M em contratos das suas empresas com municipios onde ela tambem e servidora — valor expressivo para municipios de pequeno porte como Sume e Zabele.

### 5.2. Empresas de materiais medicos e hospitalares

O padrao predominante entre empresas de alto risco e o de fornecedores de insumos e equipamentos medicos. Esses fornecedores:

- Acumulam contratos em multiplos municipios (flag_multi_municipal), indicando atuacao pulverizada no interior do estado
- Possuem sancoes CEIS vigentes, sugerindo que continuaram contratando apos penalidades administrativas
- Estao com CNPJ inativo, indicando que contratos podem ter sido firmados ou pagos mesmo apos encerramento ou irregularidade cadastral
- Acumulam divida com a PGFN, indicando inadimplencia fiscal concomitante a recebimento de recursos publicos

### 5.3. Servidores com Bolsa Familia

Os **25.883 servidores** que recebem Bolsa Familia (flag_bolsa_familia = true) representam 7,3% do total avaliado. Isoladamente, isso pode indicar:
- Cadastros desatualizados no CadUnico (renda familiar mudou apos ingresso no servico publico)
- Servidores temporarios ou de baixa remuneracao em situacao de vulnerabilidade genuina
- Casos de acumulacao indevida de beneficio social com remuneracao incompativel

Este grupo exige cruzamento adicional com o nivel de remuneracao para distinguir casos de efetiva irregularidade.

### 5.4. Multi-empresa (socios de 3+ empresas)

Os **1.033 servidores** com flag_multi_empresa sao socios de 3 ou mais empresas simultaneamente. Esse padrao pode indicar estruturas para distribuicao de contratos entre empresas formalmente distintas mas sob controle comum — pratica conhecida como "empresa de fachada multipla".

---

## 6. Correlacao com Outros Achados

| Municipio | Casos identificados neste relatorio | Outros relatorios |
|-----------|------------------------------------|--------------------|
| Joao Pessoa | REGIS COSTA BOMFIM (R$1,38M), RAFAEL DE ARRUDA SOUSA PINTO (R$1,08M) | relatorio_risco_municipal_pb.md (score 49), Q47, Q53, Q59 |
| Santa Rita | REGIS COSTA BOMFIM (conflito) | relatorio_risco_municipal_pb.md (score 51), Q74 |
| Cajazeiras | GUSTAVO ANACLETO LOURENCO COELHO (R$1,95M) | — |
| Guarabira | RAFAEL DE ARRUDA SOUSA PINTO (conflito) | — |

---

## 7. Limitacoes

1. **Score binario por flag:** O modelo atual atribui pontuacao fixa por flag, sem gradacao pela intensidade (ex.: uma divida PGFN de R$1.000 recebe os mesmos 15 pontos que uma de R$10M). Ponderacao por valor melhoraria a discriminacao.

2. **Acumulacao de cargos legitima:** A legislacao brasileira permite acumulacao de cargos medicos em determinadas condicoes (art. 37, XVI, CF). O score nao distingue acumulacoes licitas de ilicitas — todos os casos de conflito identificado requerem verificacao individual.

3. **Desatualizacao cadastral:** Parte das empresas inativas pode ter situacao regularizada apos a data de extracao dos dados. O CNPJ e o CadUnico apresentam defasagem de atualizacao.

4. **Cobertura SAGRES:** Os dados de contratos cobrem o periodo disponibilizado pelo TCE-PB. Contratos anteriores ao periodo nao sao capturados.

5. **PESSOA_PF:** Apenas 1 entidade do tipo PESSOA_PF foi avaliada, o que indica subcobertura de pessoas fisicas contratadas diretamente. Este tipo de vinculo (RPA, MEI, etc.) pode estar sub-representado nas fontes cruzadas.

---

## 8. Recomendacoes

1. **CGE-PB:** Iniciar verificacao administrativa dos 73 servidores com score >= 70, priorizando os medicos com maior volume financeiro de conflito (especialmente os casos acima de R$1M).

2. **TCE-PB:** Auditar os contratos com as 8 empresas de score >= 70, verificando se os pagamentos foram efetuados apos a sancao CEIS ou a inatividade do CNPJ.

3. **MDS/Ministerio da Cidadania:** Cruzar os 25.883 servidores com Bolsa Familia com a folha de pagamentos para identificar beneficiarios com renda incompativel com o beneficio.

4. **CGU:** Aprofundar analise dos socios de 3+ empresas (1.033 servidores) para verificar estruturas de distribuicao artificial de contratos.

5. **Metodologia:** Evoluir o score para ponderacao continua por valor (divida PGFN, volume contratado em conflito), aumentando a discriminacao entre casos graves e leves.

---

## Fontes

1. **Receita Federal — CNPJ:** Situacao cadastral de empresas (inatividade, capital social)
2. **CGU — CEIS:** Cadastro de Empresas Inidôneas e Suspensas (sancoes vigentes)
3. **PGFN:** Divida ativa federal (contribuintes com inscricao em divida)
4. **SIAPE:** Folha de servidores federais e estaduais (remuneracao, vinculo)
5. **MDS — CadUnico/Bolsa Familia:** Beneficiarios de programas sociais
6. **Receita Federal — QSA:** Quadro Societario e Administradores (socios de empresas)
7. **TCE-PB SAGRES:** Contratos e empenhos municipais (conflito de interesses)
8. **mv_empresa_pb:** View materializada de score de risco de empresas
9. **mv_servidor_pb_risco:** View materializada de score de risco de servidores
10. **v_risk_score_pb:** View unificada de score de risco de entidades (empresas + servidores + PF)
