# Relatório de Investigação: Conflito de Interesses - Servidores Federais e o Cartão Corporativo (CPGF)

**Data de Geração:** 28 de Março de 2026 (v2 — validada com CPF + nome)
**Base de Dados:** Repositório `govbr-cruza-dados` — Query Q10
**Metodologia:** Cruzamento CPF (6 dígitos centrais) + nome completo entre portadores CPGF e quadro societário RFB. Validação por nome elimina falsos positivos por colisão de CPF parcial (redução de ~16K para 979 matches na v1 → v2).

> **Disclaimer:** Este relatório apresenta cruzamentos automatizados de dados públicos. Os achados representam **anomalias estatísticas** que merecem apuração, não conclusões de irregularidade. A participação societária pode ser inativa, formal, ou anterior ao ingresso no serviço público. Nenhuma das pessoas citadas foi investigada ou condenada pelos fatos aqui descritos, salvo quando explicitamente indicado.

---

## 1. Resumo Executivo

O algoritmo Q10 identifica servidores federais que detêm o Cartão de Pagamentos do Governo Federal (CPGF) e que, simultaneamente, constam como sócios ou administradores de empresas privadas na Receita Federal. Isso viola o art. 117, X da Lei 8.112/90, que proíbe o servidor de "participar de gerência ou administração de sociedade privada".

**Números agregados (validados):**
- **979 matches** únicos portador-empresa (após filtragem CPF+nome)
- **~1.722 portadores** distintos vinculados a **2.193 empresas**
- **R$ 44,2 milhões** em gastos CPGF acumulados por esses portadores
- 943 empresas **ativas**, 956 **baixadas**, 278 **inaptas**, 12 suspensas

**Nota metodológica:** A v1 deste relatório (21/Mar) continha dois casos (CBTU/ICMBio) que foram **falsos positivos** — identificados por colisão de CPF parcial sem validação de nome. Esta v2 corrige o algoritmo e apresenta apenas matches confirmados por CPF + nome completo.

---

## 2. Os Maiores Gastadores com Conflito Societário

### 2.1. José João Mayer Amaraim — UFSM (R$ 459.841)
- **Órgão:** Universidade Federal de Santa Maria (Min. Educação)
- **CPGF:** 1.585 transações, totalizando **R$ 459.841,33**
- **Empresa:** STEIN & AMARAIM LTDA (CNPJ 03.973.449/****-**) — sócio-administrador (qualificação 22)
- **Status empresa:** Baixada (encerrada). Capital social R$ 0. UF: RS, município Santa Maria.
- **Análise:** O sobrenome "AMARAIM" na razão social confirma o vínculo familiar/pessoal. Mesmo com a empresa baixada, o volume de gastos CPGF (quase meio milhão) sem licitação merece escrutínio — especialmente se a empresa foi baixada durante ou após o período de gastos.

### 2.2. Adiel Coelho da Cunha — Hospital N. S. Conceição (R$ 355.834)
- **Órgão:** Hospital Nossa Senhora da Conceição S.A. (Min. Saúde)
- **CPGF:** 1.008 transações, **R$ 355.834,65**
- **Empresa:** CONFIANCA SUL COMERCIO DE ALIMENTOS LTDA (CNPJ 09.620.678/****-**) — sócio-administrador
- **Status empresa:** Baixada. Capital social R$ 10.000. UF: RS.
- **Análise:** Servidor de hospital público federal que era sócio de empresa de alimentos. A natureza do comércio (alimentos) e o local de trabalho (hospital) criam risco de autocontratação indireta para fornecimento de refeições ou insumos.

### 2.3. Carlos Silva dos Santos — INCRA (R$ 347.791)
- **Órgão:** Instituto Nacional de Colonização e Reforma Agrária (Min. Desenvolvimento Agrário)
- **CPGF:** 399 transações, **R$ 347.791,08**
- **Empresa:** IRMAOS SANTOS EMPREENDIMENTOS LTDA (CNPJ 13.426.260/****-**) — sócio-administrador
- **Status empresa:** **Ativa**. Capital social R$ 70.000. UF: TO.
- **Análise:** Servidor do INCRA (órgão que faz assentamentos e desapropriações) com empresa ativa de "empreendimentos" no Tocantins. Conflito de interesses direto: o INCRA negocia terras e contratos rurais, e o servidor administra empreendimentos na mesma região.

### 2.4. Alisson Vicente Pereira — Ministério da Defesa (R$ 285.563)
- **Órgão:** Ministério da Defesa (unidades com vínculo direto)
- **CPGF:** Apenas **53 transações**, totalizando **R$ 285.563,66** (média R$ 5.388/transação — extremamente alta)
- **Empresa:** DROGARIA DJORKAEFF E SARAH LTDA (CNPJ 59.886.508/****-**) — sócio-administrador
- **Status empresa:** **Ativa**. Capital social R$ 30.000. UF: DF.
- **Análise:** O padrão de gastos é o mais preocupante desta lista. 53 transações com valor médio de R$ 5.388 indicam compras de alto valor unitário. O detalhamento mostra que os favorecidos incluem **AGIMED** (R$ 52.826), **ETICA HOSPITALAR** (R$ 24.750), **LYON PRODUTOS PARA SAUDE** (R$ 20.500) — todos equipamentos médico-hospitalares. O servidor é dono de uma **drogaria ativa no DF** e usa o cartão corporativo do Ministério da Defesa para comprar exatamente nesse setor. Risco elevado de direcionamento de compras ou lavagem via cadeia de fornecedores do mesmo ramo.

### 2.5. Charles Costa Ribeiro — Banco Central (R$ 231.404)
- **Órgão:** Banco Central do Brasil
- **CPGF:** 318 transações, **R$ 231.404,36**
- **Empresa:** L. L GONCALVES RIBEIRO & CIA LTDA (CNPJ 26.980.532/****-**) — sócio-administrador
- **Status empresa:** **Ativa**. UF: DF.
- **Análise:** Servidor do Banco Central com empresa ativa no DF. O alto volume de gastos CPGF por um servidor de um órgão regulador financeiro, combinado com sociedade empresarial ativa, é um red flag para conflito de interesses regulatórios.

---

## 3. Padrão Sistêmico: Concentração por Órgão

| Ministério | Portadores com conflito | Gasto CPGF total |
|---|---|---|
| Educação | 354 | R$ 13,2 milhões |
| Planejamento e Orçamento | 323 | R$ 5,5 milhões |
| Defesa | 254 | R$ 4,2 milhões |
| Justiça e Segurança Pública | 185 | R$ 6,4 milhões |
| Meio Ambiente | 80 | R$ 2,1 milhões |
| Agricultura e Pecuária | 75 | R$ 1,6 milhões |
| Fazenda | 67 | R$ 2,0 milhões |
| Desenvolvimento Agrário | 52 | R$ 1,4 milhões |
| Minas e Energia | 45 | R$ 1,4 milhões |

O Ministério da Educação lidera com 354 portadores-sócios, refletindo a capilaridade das universidades federais (cada campus gera dezenas de portadores CPGF). O Ministério da Justiça tem o maior gasto médio por portador (R$ 34.718).

---

## 4. Casos Notáveis Adicionais

### Carlos Enock da Silva Martins — IBGE + Consultoria de Milhas (R$ 201.434)
Servidor do IBGE em Manaus/AM, sócio da **MILHAREMOS CONSULTORIA E GESTAO DE MILHAS LTDA** — empresa aberta em outubro de 2025, com capital de R$ 10.000 e CNAE 7490-1/99 (atividades profissionais não especificadas). 94% dos seus gastos CPGF (R$ 189.770) são classificados como "NÃO SE APLICA" (saques ou pagamentos sem identificação do favorecido). Padrão consistente com monetização de milhas aéreas acumuladas em viagens a serviço.

### Rhafael Sarom Pinheiro — EBSERH + Fazenda (R$ 178.509)
Servidor da Empresa Brasileira de Serviços Hospitalares, sócio da **FAZENDA SERRINHA LTDA** em Goiás. Servidor de hospital público federal com atividade agropecuária paralela.

### Leonardo Brasil de Matos Nunes — ICMBio + Associação de Servidores (R$ 160.519)
Servidor do ICMBio no RN, sócio da associação dos servidores do próprio Ministério do Meio Ambiente (CNPJ 31.409.679). Caso de menor gravidade — a empresa é uma associação de classe dos próprios servidores, não uma empresa comercial com fins lucrativos.

---

## 5. Conclusão e Recomendações

O cruzamento validado por CPF + nome confirma que **quase 1.000 servidores federais** portadores de CPGF mantêm vínculos societários com empresas privadas. Embora nem todos configurem fraude (sociedade em empresa familiar baixada, por exemplo), os casos com empresas **ativas no mesmo setor de atuação do órgão** (Alisson/Defesa+drogaria, Carlos/INCRA+empreendimentos) representam conflitos de interesse graves que violam o Estatuto do Servidor.

**Recomendações para investigação aprofundada:**
1. Cruzar os 943 casos com empresa ativa contra os favorecidos do CPGF — verificar se o portador pagou diretamente ou indiretamente para a própria empresa
2. Verificar o período de constituição das empresas versus o início da posse do CPGF
3. Priorizar os 278 casos com empresa inapta — empresa que não cumpre obrigações fiscais mas cujo sócio tem acesso a recursos públicos

## Fontes
1. **Portal da Transparência:** Base CPGF (gastos de cartão corporativo federal)
2. **Receita Federal (QSA):** Quadro de sócios e administradores, cadastro de empresas e estabelecimentos
3. **Query Q10:** `resultados/q10_portador_de_cart_o_que_s_cio_de_empresa_fornecedora.csv`
4. **Metodologia:** Validação dupla CPF parcial (6 dígitos centrais) + nome completo (UPPER TRIM)
