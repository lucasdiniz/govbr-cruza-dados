# Relatório de Investigação: Anomalias em Licitações de São Bento/PB

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados`
**Município Alvo:** São Bento - PB

---

## 1. Resumo Executivo
O município de São Bento demonstrou um vasto leque de contratos ganhos por empresas constituídas há menos de 180 dias. Os objetos variam de escritórios de advocacia até construção civil e padarias. A análise de dados locais, cruzada com inteligência de fontes abertas (OSINT), revela que o município já é alvo de pesadas investigações do Ministério Público por uso de "empresas de fachada" e superfaturamento.

## 2. O Padrão "Abre e Ganha" na Base de Dados
Os dados extraídos expõem um padrão sistêmico onde empresas vencem licitações ou são credenciadas em prazos recordes, demonstrando inviabilidade de análise prévia de atestado de capacidade técnica. Um exemplo gritante na base é a empresa *CONCRIAR ENGENHARIA*, que assinou um contrato de R$ 143.040,00 para "serviços técnicos de consultoria em escolas" apenas **26 dias** após a criação de seu CNPJ na Receita Federal.

## 3. Corroboração no Mundo Real: O Cerco do MPPB e TCE-PB
O padrão anômalo apontado pelos nossos algoritmos espelha exatamente a crise jurídica que a gestão de São Bento (sob o ex-prefeito Jarques Lúcio da Silva II) enfrenta atualmente. Pesquisas detalhadas nas fontes de notícias e órgãos de controle confirmam a gravidade da situação:

* **Inquérito Civil de Fraude e Nepotismo (MPPB):** O Ministério Público instaurou procedimento oficial para devassar todas as licitações da prefeitura após denúncias de fraude processual, "direcionamento" (bid rigging) e favorecimento de parentes (nepotismo). O MPPB exigiu o envio de cópias de todos os processos licitatórios e acionou o Tribunal de Contas para cruzar a folha de pagamento em busca de laços familiares ocultos.
* **O Caso da Empresa Fantasma "Isa Comércio" (Pandemia):** O MPPB ajuizou uma Ação Civil Pública por improbidade administrativa focada especificamente no uso de "Laranjas". A investigação apontou que a *Isa Comércio* foi usada como empresa de fachada (constituída por interposta pessoa) para fraudar a prefeitura na compra emergencial de máscaras PFF1 durante a pandemia, gerando sobrepreço e enriquecimento ilícito.
* **Auditorias do TCE-PB na Saúde e Contratos:** O ex-prefeito foi formalmente intimado pelo Tribunal de Contas do Estado a prestar esclarecimentos não apenas sobre contratações irregulares de pessoal, mas pelo uso abusivo de "inexigibilidade de licitação" (contratação direta sem disputa) para a alocação de serviços médicos.
* **Operação Recidiva (PF/CGU):** A cidade foi um dos alvos diretos de uma Força-Tarefa da Polícia Federal e da Controladoria-Geral da União que investigou uma máfia que desviava verbas públicas de obras contra a seca. O *Modus Operandi*? Uso de empresas de fachada que venciam licitações simuladas para a construção de açudes com sobrepreço.
* **O Contexto das Nossas Descobertas:** O histórico documentado acima pelas autoridades (uso de dispensas, laranjas e direcionamento) explica perfeitamente a enxurrada de "empresas recém-nascidas" que o nosso sistema flagrou ganhando contratos (como a *Concriar Engenharia* e a *Panificadora Gosto de Pão*). 

## 4. Lista Completa de CNPJs e Empresas Encontradas na Base
Extração baseada no arquivo `q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv`:

* **EMPREENDIMENTOS COMERCIAIS SAO BENTO LTDA** 
  - **CNPJ:** 57.549.843/0001-69
  - **Data de Abertura:** 03-10-2024
  - **Valores dos Contratos (Múltiplos):** R$ 344.466,01 (28-11-2024), R$ 344.466,01 (28-11-2024), R$ 197.000,00 (28-01-2025), R$ 364.171,35 (14-02-2025)
  - **Valor Total:** R$ 1.250.103,37
* **CONCRIAR ENGENHARIA CONSTRUCOES E REFORMAS LTDA** 
  - **CNPJ:** 58.962.715/0001-05
  - **Valor do Contrato:** R$ 143.040,00
  - **Data de Abertura:** 18-01-2025
  - **Data do Contrato:** 13-02-2025
* **PANIFICADORA GOSTO DE PAO LTDA** 
  - **CNPJ:** 58.449.144/0001-00
  - **Valor do Contrato:** R$ 206.900,00
  - **Data de Abertura:** 13-12-2024
  - **Data do Contrato:** 12-02-2025
* **J C DE ALMEIDA FILHO COMERCIO** 
  - **CNPJ:** 63.816.693/0001-05
  - **Valor do Contrato:** R$ 382.500,00
  - **Data de Abertura:** 26-11-2025
  - **Data do Contrato:** 28-01-2026
* **CARDIOCLINICA ANTONIO HELOISIO LIMEIRA PINHEIRO LTDA** 
  - **CNPJ:** 60.510.060/0001-86
  - **Valor do Contrato:** R$ 100.800,00
  - **Data de Abertura:** 23-04-2025
  - **Data do Contrato:** 27-08-2025
* **CARNES E LATICINIOS ARAUJO LTDA** 
  - **CNPJ:** 62.764.399/0001-34
  - **Valor do Contrato:** R$ 447.450,00
  - **Data de Abertura:** 17-09-2025
  - **Data do Contrato:** 28-01-2026
* **J C GARCIA AJALA  LTDA** 
  - **CNPJ:** 53.559.982/0001-12
  - **Valor do Contrato:** R$ 246.924,00
  - **Data de Abertura:** 18-01-2024
  - **Data do Contrato:** 09-07-2024

## 5. Anomalias Contábeis e Expansão Regional (Novo Achado TCE-PB)
As bases de dados do TCE-PB e DadosPB expuseram desdobramentos graves sobre as empresas laranjas flagradas neste município:
* **Inexecução ou Maquiagem Contábil:** A *CONCRIAR ENGENHARIA* apresentou uma divergência suspeitíssima no espelho do Tribunal de Contas. A Prefeitura de São Bento empenhou R$ 131.120,00 para a empresa recém-criada, mas liquidou/pagou oficialmente apenas R$ 11.920,00 (uma divergência de mais de 90%). Isso sugere a fabricação de "Restos a Pagar" fictícios ou o abafamento do contrato após pressões do MPPB.
* **A Expansão da Lojinha de Papel:** A empresa *EMPREENDIMENTOS COMERCIAIS SAO BENTO LTDA* (que acumula mais de 1 milhão em contratos locais) não atua apenas na sua cidade-sede. Os dados revelam que ela operou uma "metástase" para o município vizinho de **Teixeira**, onde abocanhou quase **R$ 1.000.000,00** vendendo de tudo (de alimentos a produtos de limpeza) sempre sob o manto de Dispensas de Licitação.

## Fontes e Referências
1. **Ministério Público da Paraíba (MPPB):** Ações civis e investigações sobre a gestão municipal de São Bento. [Acesse a Nota do MPPB](https://www.mppb.mp.br/index.php/pt/comunicacao/noticias/20-patrimonio-publico/19845-promotoria-vai-investigar-denuncias-de-irregularidades-em-sao-bento)
2. **Blog do Ninja / Portal Correio:** Reportagens cobrindo as ações do MPPB contra o ex-prefeito Jarques Lúcio e a empresa fantasma Isa Comércio. [Leia no Blog do Ninja](https://blogdoninja.com.br/jarques-lucio-e-alvo-de-acao-do-mppb-por-compra-superfaturada-de-mascaras-em-sao-bento/)
3. **IstoÉ Dinheiro:** Histórico da Operação Recidiva (PF) e desvios em obras na região. [Leia na IstoÉ](https://istoedinheiro.com.br/forca-tarefa-da-pf-e-cgu-investiga-desvios-milionarios-em-obras-contra-seca-na-pb/)
4. **Diário Oficial / Portal da Transparência:** Contratos publicados das empresas (Concriar e Gosto de Pão) apontadas pelo sistema. [Transparência São Bento](https://saobento.pb.gov.br/transparencia/)
5. **Paraíba Já:** Intimações do TCE-PB por irregularidades na contratação de pessoal e inexigibilidade de licitações. [Leia no Paraíba Já](https://paraibaja.com.br/tce-pb-intima-ex-prefeito-de-sao-bento-para-explicar-irregularidades/)