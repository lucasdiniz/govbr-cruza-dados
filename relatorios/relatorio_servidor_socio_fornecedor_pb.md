# Relatório de Auditoria: Servidores Municipais Sócios de Empresas Fornecedoras na Paraíba

**Data de Geração:** 28 de Março de 2026
**Base de Dados:** Query Q59 — cruzamento tce_pb_servidor × socio × tce_pb_despesa
**Metodologia:** Identificação de servidores municipais cujo CPF (6 dígitos centrais) e nome completo coincidem com sócios de empresas que recebem pagamentos do mesmo município.

> **Disclaimer:** Este relatório apresenta cruzamentos automatizados de dados públicos. Os achados representam **anomalias estatísticas** que merecem apuração. A participação societária de servidor público em empresa fornecedora pode ter explicações legais (empresa familiar pré-existente, sociedade passiva sem gestão). A existência do vínculo societário é fato objetivo (dados da Receita Federal); a apuração de eventual conflito de interesses compete aos órgãos de controle.

---

## 1. Resumo Executivo

O cruzamento identificou servidores municipais da Paraíba que simultaneamente:
1. Constam na folha de pagamento municipal (TCE-PB SAGRES, 2024-2026)
2. São sócios de empresas ativas na Receita Federal
3. Essas empresas recebem pagamentos do **mesmo município** onde o servidor trabalha

Os maiores volumes concentram-se em empresas de intermediação de serviços médicos, configurando um padrão sistêmico de **contratação indireta de profissionais de saúde via pessoa jurídica** (pejotização).

---

## 2. Caso Principal: I2 Serviços Saúde Ltda (CNPJ 35.996.035/0001-07)

### 2.1. Dados da Empresa
- **Razão Social:** I2 SERVICOS SAUDE LTDA
- **CNPJ:** 35.996.035/0001-07
- **CNAE Principal:** 8660-7/00 (Atividades de apoio à gestão de saúde)
- **Capital Social:** R$ 600.000,00
- **Início de Atividade:** 14/01/2020
- **Situação Cadastral:** Ativa
- **Sede:** João Pessoa/PB
- **Número de Sócios:** 198 (todos com qualificação 22 — sócio-administrador)

### 2.2. Volume de Pagamentos Municipais

| Município | Total Pago | Empenhos |
|-----------|-----------|----------|
| Bayeux | R$ 23.265.093,58 | 98 |
| Alagoa Grande | R$ 10.360.407,61 | 194 |
| Mamanguape | R$ 9.822.600,00 | 130 |
| Juazeirinho | R$ 3.738.716,69 | 54 |
| Gurinhém | R$ 3.431.554,95 | 69 |
| Sumé | R$ 2.893.700,00 | 39 |
| Pedra Lavrada | R$ 2.838.587,80 | 86 |
| Junco do Seridó | R$ 2.670.694,68 | 106 |
| Ingá | R$ 2.157.236,84 | 24 |
| Itaporanga | R$ 1.491.000,00 | 22 |
| São José do Sabugi | R$ 1.452.308,00 | 29 |
| Pilar | R$ 1.451.850,00 | 35 |
| Outros (4 municípios) | R$ 194.080,00 | 25 |
| **Total** | **R$ 65.767.830,15** | **911** |

### 2.3. Padrão de Incorporação de Sócios

O quadro societário da I2 Saúde apresenta um padrão de crescimento por lotes:
- **Mai/2022:** 2 sócios fundadores + 5 adições
- **Out/2023:** 10 novas entradas
- **Out/2024:** 30+ novas entradas
- **Mar/2025:** 7 novas entradas
- **Dez/2025:** 150+ novas entradas (lote massivo)

Esse padrão é consistente com um modelo onde **cada médico contratado pelo município é incorporado como sócio da empresa**, formalizando a relação via CNPJ em vez de contrato direto com a prefeitura.

### 2.4. Exemplos de Duplo Vínculo (Servidor + Sócio)

| Servidor | Município | Cargo | Remuneração |
|----------|-----------|-------|-------------|
| Maximiano Machado Albino de Souza | Mamanguape | Médico Clínico Geral | R$ 11.800 |
| Nayanne Tavares Dantas | Mamanguape | Médico Ultrassonografista | R$ 9.600 |
| Gisele Isaias Lima do Nascimento | Mamanguape | Médico Clínico Geral | R$ 2.500 |
| Francisco Cavalcanti Braz | Sumé | Médico SSA | R$ 21.328 |
| Marcus Vinicius Roberto da Silva | Sumé | Médico SSA | R$ 22.263 |
| Vanessa Cabral de Souza | Ingá | Médico - Excepcional Int. Público | R$ 161 |

Todos os servidores acima aparecem simultaneamente na folha do TCE-PB como contratados por excepcional interesse público ou efetivos, e no quadro societário da I2 Saúde como sócios-administradores (qualificação 22) na Receita Federal.

---

## 3. Outros Casos Relevantes

### 3.1. MaisMed Saúde Ltda (CNPJ 43.032.772/0001-18)
- **Sede:** João Pessoa/PB | **CNAE:** 8660-7/00 | **Capital:** R$ 300.000
- **Início:** 07/08/2021
- **Monteiro:** R$ 8.111.600,00 em 38 empenhos
- Servidores-sócios: Fillipe Nobrega (médico, R$13.450), Pammela Alves (médico, R$10.725), Carlos Vieira Junior (médico, R$11.563), Karynna Oliveira (médico, R$10.816)

### 3.2. MAG Saúde Serviços Médicos Ltda (CNPJ 51.245.708/0001-43)
- **Sede:** Fortaleza/CE | **CNAE:** 8610-1/01 | **Capital:** R$ 156.000
- **Início:** 30/06/2023
- **São João do Rio do Peixe:** R$ 3.697.289,11 em 81 empenhos
- Servidor-sócio: Manoel Almeida Gonçalves Junior (médico plantonista, R$16.500; qualificação 49 = sócio)

### 3.3. HSM2 Medicina e Saúde Ltda (CNPJ 31.635.476/0001-22)
- **Sede:** Campina Grande/PB | **CNAE:** 8630-5/02 | **Capital:** R$ 30.000
- **Início:** 28/09/2018
- **Campina Grande:** R$ 2.216.010,14 em 100 empenhos
- Servidor-sócio: Vitor Camboim Nobre (Coordenador Municipal GS1, cargo comissionado, R$12.178)
- **Nota:** Capital social de apenas R$30K para empresa que recebe R$2.2M é desproporcional

### 3.4. Serviços de Saúde Especializados Rosário de Maria Ltda (CNPJ 34.280.350/0001-70)
- **Sede:** João Pessoa/PB | **CNAE:** 8630-5/02 | **Capital:** R$ 50.000
- **Sapé:** R$ 2.913.130,00 em 24 empenhos
- Servidor-sócio: Mayra Waleska de Sousa e Silva (Técnico Administrativo, contratada, R$4.536)

### 3.5. Auto Posto Princesa do Cariri Ltda (CNPJ 28.649.502/0001-67)
- **Sede:** Monteiro/PB | **CNAE:** 4731-8/00 (Comércio varejista de combustíveis)
- **Monteiro:** R$ 4.371.293,07 em 471 empenhos
- Servidora-sócia: Silvia Lourdes Mendes Caldeira (Professora de Geografia, efetiva, R$9.940)
- **Nota:** Professora municipal é sócia de posto de combustível que recebeu R$4.3M do mesmo município em 471 empenhos

---

## 4. Análise do Padrão

### 4.1. Pejotização Médica Sistêmica
Os 4 primeiros casos (I2, MaisMed, MAG, HSM2, Rosário de Maria) seguem o mesmo modelo:
1. Empresa de intermediação de saúde sediada em capital (JP ou Fortaleza)
2. Médicos são "sócios-administradores" (qualif. 22) na Receita Federal
3. Os mesmos médicos aparecem na folha municipal como contratados por excepcional interesse público
4. A empresa recebe empenhos do município onde o médico-sócio atende

Este modelo pode configurar:
- **Fraude trabalhista**: Vínculo empregatício disfarçado de sociedade para evitar encargos (CLT, FGTS, INSS patronal)
- **Conflito de interesses**: Servidor público com interesse financeiro em empresa fornecedora do próprio órgão
- **Irregularidade licitatória**: Contratação de empresa cujos sócios já são servidores do órgão contratante

### 4.2. O Caso Atípico (Auto Posto)
O caso da professora de Monteiro difere por não ser da área de saúde. Uma professora efetiva é sócia de posto de combustível que fornece ao mesmo município — 471 empenhos (quase 2 por dia útil) sugere fornecimento contínuo de combustível para a frota municipal.

---

## 5. Enquadramento Legal

- **Lei 8.429/92 (Improbidade), art. 9, I**: Auferir vantagem patrimonial indevida em razão da função pública
- **Lei 14.133/21, art. 9, § 1º**: Impedimento de participar de licitação empresa cujo sócio seja servidor do órgão contratante
- **Lei 8.112/90, art. 117, X** (analogia): Proibição de participar de gerência de empresa privada incompatível com cargo público
- **CLT, art. 3º**: Configuração de vínculo empregatício quando há subordinação, habitualidade, onerosidade e pessoalidade, independente da forma jurídica

---

## 6. Recomendações

1. **TCE-PB**: Implementar cruzamento automático entre SAGRES (folha de servidores) e quadro societário da RFB para todos os municípios
2. **MP-PB**: Investigar se os médicos-sócios da I2 Saúde exercem atividade com subordinação e habitualidade (configurando vínculo empregatício disfarçado)
3. **Prefeituras**: Verificar se os processos licitatórios que contrataram estas empresas observaram o impedimento do art. 9, § 1º da Lei 14.133/21
4. **MPT**: Avaliar a configuração de fraude trabalhista no modelo de "médico-sócio" adotado pela I2 Saúde em 16 municípios

## Fontes
1. **TCE-PB SAGRES:** Folha de servidores municipais 2024-2026
2. **TCE-PB SAGRES:** Despesas municipais 2022-2026
3. **Receita Federal:** Quadro societário (base CNPJ), situação cadastral
4. **Query Q59:** `queries/fraude_tce_pb.sql`
