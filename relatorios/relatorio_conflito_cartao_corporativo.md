# Relatório de Investigação: Conflito de Interesses - Servidores Federais e o Cartão Corporativo (CPGF)

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Arquivo `q10_portador_de_cart_o_que_s_cio_de_empresa_fornecedora.csv`)
**Foco:** Agentes públicos com poder de despesa possuindo empresas/ONGs financiadas com dinheiro público na Paraíba.

---

## 1. Resumo Executivo
O algoritmo Q10 realiza o cruzamento de um dos crimes mais silenciosos da máquina pública: quando o servidor federal que detém a posse do Cartão de Pagamentos do Governo Federal (CPGF) é, ao mesmo tempo, proprietário oculto ou sócio de empresas privadas (ou ONGs) que recebem repasses do governo. A auditoria na base identificou dois casos graves envolvendo a Paraíba, indicando forte potencial para lavagem de dinheiro, autocontratação e peculato.

## 2. O Caso CBTU: O "Rei do Cartão" e a ONG de Juripiranga
O servidor **Josué Oliveira Gomes** atua na Companhia Brasileira de Trens Urbanos (CBTU).
* **O Perfil de Gastos:** O cruzamento do Portal da Transparência mostra que ele utilizou o cartão corporativo do governo federal de forma massiva, com 1.559 transações registradas, drenando quase **R$ 1 Milhão** (R$ 906.887,51) dos cofres da estatal de trens.
* **O Conflito Oculto:** O robô identificou que, na vida privada, ele gerencia uma teia de CNPJs no interior da Paraíba que já recebeu **R$ 887.305,34** em contratos e repasses (um valor que espelha os seus gastos com o cartão). Ele é dirigente da **ASSOCIAÇÃO CAPELA SANTO ANTONIO (ACSA)** em Juripiranga/PB e sócio de uma empresa recente chamada **RASP BR LTDA** (registrada em um box de coworking em Cabedelo/PB).
* **O Risco Sistêmico:** A posse do cartão de suprimento de fundos somada à propriedade de ONGs e empresas "de gaveta" é o cenário primário para fraudes onde o servidor forja serviços inexistentes, passa o cartão do governo na máquina da sua própria empresa/associação, e saca o dinheiro público "limpo" no CNPJ privado.

## 3. O Caso ICMBio: O Fiscal Ambiental Fazendeiro
O servidor **Fábio Adônis Gouveia Carneiro da Cunha** atua como Analista Ambiental de carreira no Instituto Chico Mendes de Conservação da Biodiversidade (ICMBio), vinculado ao Centro de Mamíferos Aquáticos.
* **O Conflito de Competência:** Como analista, ele detém o poder de Estado para fiscalizar, multar e atuar no licenciamento de áreas e unidades de conservação (com vasta atuação geográfica na Paraíba e Pernambuco). O banco de dados confirmou que ele é portador de CPGF.
* **A Empresa:** O algoritmo cruzou o CPF do fiscal e descobriu que ele é dono/sócio da **FAZENDA FREI ANTONIO SA** e da *PASTOREIO COMERCIO E CONSULTORIA AGROPECUARIOS LTDA*, propriedades com sede na Paraíba.
* **O Faturamento Público:** A Fazenda e a consultoria acumulam **R$ 380.188,97** em contratos e recebimentos do poder público. 
* **O Risco Sistêmico:** Um agente federal de fiscalização ambiental que possui fazendas (S/A) na mesma região onde atua, e que vende serviços agropecuários ao governo, fere o princípio da moralidade e impessoalidade. O risco de tráfico de influência para beneficiar a própria fazenda em zoneamentos ou para garantir vitórias em licitações de compras de terras e produtos agrícolas locais é extremo.

## 4. Conclusão
Os cruzamentos do Q10 não apontam necessariamente que os servidores compraram de si mesmos com o próprio cartão corporativo (embora essa seja a tipologia de lavagem mais provável no Caso CBTU). A irregularidade primordial aqui reside na quebra do Estatuto do Servidor Público Federal (Lei 8.112/90), que proíbe terminantemente que o servidor participe de gerência ou administração de sociedade privada que transacione com o Estado. A posse do CPGF apenas atesta o alto nível de confiança e poder de manobra financeira que esses indivíduos possuem dentro da engrenagem do Estado.

## Fontes e Referências
1. **Portal da Transparência (CPGF):** Extrato de gastos com cartão de pagamento em nome de Josué Oliveira Gomes (1.559 transações) e Fábio Adônis.
2. **Receita Federal (QSA):** Comprovação societária vinculando o CPF dos servidores à Fazenda Frei Antônio S/A, RASP BR LTDA e Associação Capela Santo Antônio.
3. **Diários Oficiais:** Publicações confirmando o cargo efetivo dos servidores no ICMBio e CBTU.
4. **Arquivos Locais:** `resultados\q10_portador_de_cart_o_que_s_cio_de_empresa_fornecedora.csv`

## Fontes e Refer?ncias
1. **Portal da Transpar?ncia (CPGF):** Extrato de gastos com cart?o de pagamento em nome de F?bio Ad?nis (ICMBio). [P?gina Oficial do Servidor e Gastos CPGF](https://portaldatransparencia.gov.br/servidores/1284341)
2. **Portal da Transpar?ncia (CPGF):** Extrato de gastos em nome de Josu? Oliveira Gomes (CBTU). [P?gina de Busca de Servidor](https://portaldatransparencia.gov.br/servidores/busca?termo=JOSUE%20OLIVEIRA%20GOMES)
3. **Receita Federal (QSA):** Consulta de Quadro Societ?rio. [Acesso ? Base RFB](https://solucoes.receita.fazenda.gov.br/Servicos/cnpjreva/Cnpjreva_Solicitacao.asp)
4. **Arquivos Locais:** 
esultados\q10_portador_de_cart_o_que_s_cio_de_empresa_fornecedora.csv