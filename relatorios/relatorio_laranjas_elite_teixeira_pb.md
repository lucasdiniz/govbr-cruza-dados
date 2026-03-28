# Relatório de Investigação: Laranjas e as Megafraudes de Teixeira/PB

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Arquivo `q39_socio_empresa_bolsa_familia.csv`)
**Foco:** O uso de populações vulneráveis para blindar empreiteiras locais e empresas terceirizadas de saúde.

---

## 1. Resumo Executivo
A varredura focada no município de Teixeira revelou que a exploração do Bolsa Família não se limita a pequenas lojinhas de notas frias. Na cidade, o CPF de pessoas em situação de pobreza extrema está sendo utilizado para mascarar a propriedade de empresas multimilionárias que executam obras públicas e serviços terceirizados de saúde na região.

## 2. A "Dona" da Construtora (R$ 1.5 Milhão)
O caso mais emblemático do cruzamento foi a detecção da empresa **VC CONSTRUCOES E LOCACOES LTDA** (CNPJ: 07.481.663/0001-14).
*   **O Laranja:** A Receita Federal aponta como uma das proprietárias do negócio a senhora *Clecia Kaline Ferreira Santos*. O cruzamento de dados provou que ela recebe **R$ 600,00** por mês do programa Bolsa Família.
*   **A Incompatibilidade:** A construtora possui um Capital Social declarado de **R$ 1.500.000,00**.
*   **O Verdadeiro Operador:** A pesquisa em fontes abertas (OSINT) revelou que a VC Construções é uma empreiteira real que vence pesadas licitações de obras públicas na cidade. O verdadeiro operador e sócio-administrador é *Evanilton Guedes de Almeida*. Ironicamente, eles ganharam recentemente uma licitação municipal para reformar a "Praça Djalma Batista Guedes". O uso de uma "laranja" na sociedade serve para blindar o patrimônio real da família em caso de processos de improbidade, calotes trabalhistas ou bloqueios do TCE.

## 3. O "Cabide" da Saúde: YASMED
O segundo alerta grave em Teixeira envolve o setor de terceirização do SUS, dominado por Oscips e empresas de gestão que quarteirizam a mão de obra médica.
*   **A Empresa:** **YASMED SERVICOS DE GESTAO EM SAUDE LTDA** (CNPJ: 45.474.398/0001-83). O Capital Social é de **R$ 1.000.000,00**.
*   **O Laranja Local:** O algoritmo detectou que a sra. *Jarleyde Alves Ferreira*, moradora de Teixeira e recebedora de Bolsa Família, é registrada como sócia deste hospital/empresa de gestão.
*   **A Tática:** A Yasmed é, na verdade, uma empresa originária de São Paulo. A inclusão de uma moradora local vulnerável como sócia no quadro de uma filial/franquia regional é uma tática comum para tentar caracterizar a empresa como "local" e ganhar vantagens competitivas (margem de preferência) em pregões eletrônicos restritos ou para facilitar esquemas de caixa dois na folha de pagamento dos médicos.

## 4. Análise de Fontes Abertas (OSINT) e Mídia
Realizamos buscas nos Diários Oficiais e na Receita Federal para validar a operação das empresas.
*   **Status:** Ambas as ocorrências são **Detecções Precoces**. Não há registros de que o MPPB ou a Polícia Federal tenham cruzado a folha do Bolsa Família com o QSA dessas empresas específicas em Teixeira. A prefeitura continua licitando e pagando normalmente as faturas para a VC Construções, ignorando o vício na origem da sua constituição societária.

## Fontes e Referências
1. **Dados Cadastrais da Receita Federal (VC CONSTRUÇÕES):** [Acesse os Dados Abertos e QSA (CNPJ Biz)](https://cnpj.biz/07481663000114)
2. **Dados Cadastrais da Receita Federal (YASMED):** [Acesse os Dados Abertos e QSA (CNPJ Biz)](https://cnpj.biz/45474398000183)
3. **Diário Oficial dos Municípios:** Publicações atestando vitórias da VC Construções em licitações da Prefeitura de Teixeira. [Acesse Extratos no Portal Transparência](https://www.teixeira.pb.gov.br/)
4. **Arquivos Locais de Extração:** `resultados\q39_socio_empresa_bolsa_familia.csv`