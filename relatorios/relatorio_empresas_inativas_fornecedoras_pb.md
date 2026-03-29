# Relatório de Auditoria: Empresas Inativas ou Inaptas Recebendo Pagamentos Municipais na Paraíba

**Data de Geração:** 28 de Março de 2026
**Base de Dados:** mv_empresa_governo — cruzamento de 9 fontes governamentais × cadastro RFB
**Metodologia:** Identificação de empresas com situação cadastral "Baixada" (8) ou "Inapta" (4) na Receita Federal que constam como credoras em despesas municipais da Paraíba (SAGRES/TCE-PB).

> **Disclaimer:** Este relatório apresenta cruzamentos automatizados de dados públicos. Os achados representam **anomalias estatísticas** que merecem apuração. A situação cadastral na RFB pode não refletir o momento da contratação (empresa pode ter sido baixada após o contrato). Algumas "empresas" são na verdade órgãos públicos com CNPJ baixado por reestruturação. A apuração compete aos órgãos de controle.

---

## 1. Resumo Executivo

Das 690.734 empresas presentes em fontes governamentais, **155.535 (22,5%)** possuem situação cadastral diferente de "Ativa" na Receita Federal. Entre estas, foram identificadas empresas que receberam pagamentos significativos de municípios paraibanos mesmo estando baixadas ou inaptas.

---

## 2. Maiores Credoras Inativas/Inaptas em Municípios PB

### 2.1. Delegacia da Receita Federal de Campina Grande — R$ 266,7M
- **CNPJ:** 02.494.312/XXXX-XX | **Situação:** Baixada (8)
- **Total recebido (TCE-PB):** R$ 266.681.177
- **Municípios atendidos:** 109
- **Análise:** Órgão público federal com CNPJ baixado por reestruturação. Recebimentos são provavelmente repasses obrigatórios, não contratos. **Falso positivo**.

### 2.2. Energisa Borborema — R$ 215,1M
- **CNPJ:** 08.826.596/XXXX-XX | **Situação:** Baixada (8) | **Início:** 1967
- **Total recebido (TCE-PB):** R$ 131.052.177 | **PNCP:** R$ 16.690 | **PB Empenho:** R$ 48.680.546
- **Municípios atendidos:** 21
- **5 fontes governamentais**
- **Análise:** Distribuidora de energia com CNPJ baixado provavelmente por incorporação/fusão corporativa. Pagamentos são contas de energia. **Falso positivo**.

### 2.3. Gráfica e Editora Rocha Ltda — R$ 26,8M
- **CNPJ:** 00.412.019/XXXX-XX | **Situação:** Inapta (4) | **Início:** 1995
- **Total recebido (TCE-PB):** R$ 26.774.812
- **Municípios atendidos:** 2
- **Análise:** Gráfica inapta que recebeu R$26M de apenas 2 municípios. Merece investigação.

### 2.4. GL Araújo Combustíveis Ltda — R$ 17,2M
- **CNPJ:** 10.632.526/XXXX-XX | **Situação:** Baixada (8) | **Capital:** R$ 200.000 | **Início:** 2009
- **Total recebido (TCE-PB):** R$ 15.477.575 | **PNCP:** R$ 1.704.046
- **Municípios atendidos:** 4
- **Análise:** Posto de combustível baixado mas que recebeu R$15M de 4 municípios e ainda tem contratos no PNCP. Inconsistência cadastral.

### 2.5. SM Serviços de Construções Ltda — R$ 12M
- **CNPJ:** 07.177.669/XXXX-XX | **Situação:** Inapta (4) | **Capital:** R$ 1.800.000 | **Início:** 2005
- **Total recebido (TCE-PB):** R$ 11.999.017
- **Municípios atendidos:** 8
- **Análise:** Construtora inapta fornecendo para 8 municípios. Capital de R$1,8M sugere empresa de porte médio.

### 2.6. MJ Comércio de Artigos Médicos — R$ 20,5M
- **CNPJ:** 22.465.640/XXXX-XX | **Situação:** Baixada (8) | **Capital:** R$ 60.000 | **Início:** 2015
- **Total recebido (TCE-PB):** R$ 9.837.798 | **PB Empenho:** R$ 9.287.397
- **Municípios atendidos:** 33
- **4 fontes governamentais**
- **Análise:** Empresa de material médico com capital de R$60K que recebeu R$20M de 33 municípios. Baixada mas ativa em 4 fontes governamentais.

### 2.7. Aleff Souza de Andrade (MEI) — R$ 9,8M
- **CNPJ:** 27.220.692/XXXX-XX | **Situação:** Baixada (8) | **Capital:** R$ 30.000 | **Início:** 2017
- **Total recebido (TCE-PB):** R$ 9.643.963
- **Municípios atendidos:** 22
- **3 fontes governamentais**
- **Análise:** Pessoa física como MEI, capital de R$30K, baixada, mas que recebeu R$9,6M de 22 municípios. Desproporção significativa.

### 2.8. Rosildo de Lima Silva — R$ 12,3M
- **CNPJ:** 23.821.927/XXXX-XX | **Situação:** Inapta (4) | **Capital:** R$ 50.000 | **Início:** 2015
- **Total recebido (TCE-PB):** R$ 8.737.741
- **Municípios atendidos:** 13
- **Análise:** Empresa individual inapta que forneceu para 13 municípios.

### 2.9. Edilane Carvalho Araújo — R$ 8,5M
- **CNPJ:** 12.710.916/XXXX-XX | **Situação:** Baixada (8) | **Capital:** R$ 100.000 | **Início:** 2010
- **Total recebido (TCE-PB):** R$ 8.451.831
- **Municípios atendidos:** 144
- **Análise:** 144 municípios em um estado com 223 — cobertura de 65%. Capital de R$100K. Empresa individual baixada com penetração estadual atípica.

### 2.10. Estanislau Chaves Neto — R$ 8,1M
- **CNPJ:** 32.236.303/XXXX-XX | **Situação:** Inapta (4) | **Capital:** R$ 80.000 | **Início:** 2018
- **Total recebido (TCE-PB):** R$ 8.089.641
- **Municípios atendidos:** 5
- **Análise:** Empresa individual recente (2018), inapta, capital R$80K, R$8M de 5 municípios.

---

## 3. Padrões Observados

1. **Falsos positivos por reestruturação**: Delegacia RFB e Energisa estão baixadas por reestruturação corporativa, não por irregularidade. Representam ~R$480M dos R$500M+ identificados
2. **Empresas individuais com alto volume**: Aleff Souza, Rosildo de Lima, Edilane Carvalho e Estanislau Chaves são empresas de pessoa física que receberam R$8-12M cada de múltiplos municípios, estando inaptas ou baixadas
3. **Penetração estadual atípica**: Edilane Carvalho atende 144 de 223 municípios — sugere contrato estadual ou intermediação de algum serviço padronizado
4. **Material médico com capital desproporcional**: MJ Comércio (R$60K capital, R$20M recebidos, 33 municípios) repete o padrão de empresa de saúde com capital desproporcional visto no relatório de capital mínimo

---

## 4. Enquadramento Legal

- **Lei 14.133/21, art. 62, I**: Vedada a contratação de empresa com situação irregular perante a Receita Federal
- **IN RFB 2.119/22, art. 39**: Empresa inapta tem CNPJ com restrição para emissão de notas fiscais
- **Nota:** A Lei 14.133/21 exige regularidade fiscal no momento da contratação. Empresa que se torna inapta após a assinatura do contrato pode continuar recebendo pagamentos de contratos vigentes.

---

## 5. Recomendações

1. **TCE-PB**: Incluir verificação automática de situação cadastral RFB no momento da liquidação de empenhos
2. **Prefeituras**: Implementar consulta ao CNPJ antes de novos pagamentos a credores com situação irregular
3. **Investigação específica**: Apurar os casos de Edilane Carvalho (144 municípios) e MJ Comércio (33 municípios, material médico) que apresentam maior risco de irregularidade

## Fontes
1. **Receita Federal:** Dados cadastrais de empresas (situação cadastral, capital social)
2. **TCE-PB SAGRES:** Despesas municipais 2018-2026
3. **PNCP:** Contratos públicos
4. **mv_empresa_governo:** View materializada com cruzamento de 9 fontes
