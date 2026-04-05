# Relatório de Análise: Incompatibilidade entre Benefício Social e Participação Societária na Paraíba

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Query Q39 — cruzamento Bolsa Família × QSA Receita Federal)
**Foco:** Identificação de beneficiários de programas sociais que constam como sócios de empresas com capital social elevado.

> **Disclaimer:** Este relatório apresenta cruzamentos automatizados de dados públicos. Os achados representam **anomalias estatísticas** que merecem apuração, não conclusões de irregularidade. A presença do CPF de um beneficiário no QSA de uma empresa pode ter diversas explicações legítimas (inclusão sem conhecimento, sociedade formal sem participação efetiva, erro cadastral). Nenhuma das pessoas citadas foi investigada ou condenada pelos fatos aqui descritos, salvo quando explicitamente indicado por fonte externa.

---

## 1. Resumo Executivo
O cruzamento automático entre a base do Auxílio Brasil/Bolsa Família e o Quadro de Sócios e Administradores (QSA) da Receita Federal identificou casos na Paraíba onde beneficiários de programas sociais constam como sócios de empresas com capital social significativamente superior à sua renda declarada. Esse tipo de incompatibilidade pode indicar uso indevido de CPF (com ou sem consentimento do titular) para constituição de empresas.

## 2. Caso de Referência: Hidro Perfurações Ltda
O cruzamento apontou que a Sra. **Maria do Desterro Formiga Flavio** (São José da Lagoa Tapada/PB), beneficiária de R$ 600,00, consta como sócia da **HIDRO PERFURACOES LTDA** (CNPJ: 04.830.606/0001-05), com Capital Social de R$ 5.000.000,00.

**Corroboração por fontes externas:**
- **TCU (Acórdão 18200/2021):** A Hidro Perfurações foi objeto de processo por inexecução e pagamentos irregulares na construção de escolas (Proinfância) em Quixabá/PB.
- **CAGEPA (2019):** A empresa foi suspensa e impedida de licitar com a administração estadual por dois anos.
- **MPF:** Alvo de ação por improbidade em obras em Guarabira.

## 3. Outros Casos Identificados

* **João Pessoa/PB:**
  * **Janailda Maria da Silva:** Beneficiária de R$ 180,00, consta como sócia da **SUCATAS HOSPITALARES COMERCIO E RECICLAGEM LTDA** (CNPJ: 15.739.000/0001-76) com Capital Social de R$ 1.500.000,00.
  * **Aline Medeiros Correa de Oliveira:** Beneficiária de R$ 640,00, consta como sócia da **OLHO DAGUA DO CAPIM SPE LTDA** (CNPJ: 50.839.309/0001-08) com Capital de R$ 4.800.000,00.

* **Juarez Távora/PB:**
  * **Severino Alves de Andrade:** Beneficiário de R$ 600,00, consta como sócio da **ETHIC REPRESENTACOES COMERCIAIS LTDA** (CNPJ: 00.803.795/0001-00) com Capital de R$ 2.500.000,00.

* **Queimadas/PB:**
  * **Carlos Alberto de Luna Candido:** Beneficiário de R$ 600,00, consta como sócio de cinco empresas distintas com Capital de R$ 200.000,00 cada: *LUNA PUBLICIDADES LTDA*, *LIVRARIA LUNA LTDA*, *ALBERTO LUNA ASSISTENCIA TECNICA LTDA*, *LUNA SOLUCOES DIGITAIS LTDA* e *ADEGA LUNA LTDA*.

## 3. Estudo de Caso Local: Teixeira/PB

O recorte municipal de Teixeira, antes tratado em relatório separado, foi incorporado aqui por ter a mesma base metodológica da `Q39` e não justificar um arquivo autônomo.

* **VC Construções e Locações Ltda**
  * **CNPJ:** 07.481.663/0001-14
  * **Sócia identificada:** Clecia Kaline Ferreira Santos
  * **Benefício social:** R$ 600,00/mês
  * **Capital social:** R$ 1.500.000,00
  * **Leitura:** beneficiária de programa social inserida no quadro societário de construtora com capital milionário e atuação em obras públicas locais.

* **Yasmed Serviços de Gestão em Saúde Ltda**
  * **CNPJ:** 45.474.398/0001-83
  * **Sócia identificada:** Jarleyde Alves Ferreira
  * **Capital social:** R$ 1.000.000,00
  * **Leitura:** moradora de Teixeira/PB listada como sócia de empresa de gestão em saúde originária de outro estado, sinal compatível com sócia formal sem participação econômica real.

## 4. Nota Metodológica
A incompatibilidade entre benefício social e participação societária não constitui, por si só, prova de irregularidade. Possíveis explicações incluem:
- Uso do CPF do beneficiário sem seu conhecimento (fraude contra o titular)
- Inclusão formal como sócio sem participação efetiva na gestão
- Erro cadastral na Receita Federal
- Empresa constituída em período anterior ao recebimento do benefício

A apuração da situação concreta de cada caso compete aos órgãos de controle (CGU, MPF, TCU).

## Fontes
1. **Acórdão TCU (18200/2021):** Processo envolvendo a Hidro Perfurações.
2. **CGE-PB:** Cadastro de Fornecedores Impedidos (Sanção CAGEPA 2019).
3. **Ministério Público Federal:** Ações civis públicas em Guarabira/PB.
4. **Arquivos do Projeto:** `resultados/q39_socio_empresa_bolsa_familia.csv`
