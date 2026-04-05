# Relatório de Dados: Empresas Recém-Constituídas com Contratos em São Bento/PB

> **Aviso:** Este documento apresenta dados extraídos de fontes públicas oficiais (PNCP, Receita Federal, TCE-PB) e referências a investigações conduzidas por órgãos competentes. A presença de uma empresa ou contrato neste relatório não implica irregularidade ou ilegalidade. Os achados representam anomalias estatísticas que podem ter explicações legítimas. Cabe exclusivamente aos órgãos de controle a apuração e o julgamento dos fatos.

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados`
**Município:** São Bento - PB

---

## 1. Resumo

A análise automatizada identificou sete empresas constituídas há menos de 180 dias que firmaram contratos com o município de São Bento/PB. Os objetos contratuais abrangem áreas diversas, incluindo serviços de engenharia, alimentação, saúde e advocacia. Separadamente, fontes públicas indicam que o município é objeto de investigações por parte do Ministério Público da Paraíba (MPPB) e de auditorias do Tribunal de Contas do Estado (TCE-PB).

## 2. Empresas com Curto Intervalo entre Abertura e Contratação

Os registros a seguir foram extraídos da consulta `q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv`. Em todos os casos, o intervalo entre a data de abertura do CNPJ e a assinatura do primeiro contrato municipal é inferior a 180 dias.

* **EMPREENDIMENTOS COMERCIAIS SAO BENTO LTDA**
  - **CNPJ:** 57.549.843/0001-69
  - **Data de Abertura:** 03-10-2024
  - **Contratos identificados:**
    - R$ 344.466,01 (28-11-2024)
    - R$ 344.466,01 (28-11-2024)
    - R$ 197.000,00 (28-01-2025)
    - R$ 364.171,35 (14-02-2025)
  - **Valor Total:** R$ 1.250.103,37
  - **Observação:** Contratos registrados também nos municípios de Teixeira e Matureia (limpeza, alimentícios, cestas básicas, kits escolares), totalizando mais de R$ 3 milhões em contratos na região.

* **CONCRIAR ENGENHARIA CONSTRUCOES E REFORMAS LTDA**
  - **CNPJ:** 58.962.715/0001-05
  - **Data de Abertura:** 18-01-2025
  - **Valor do Contrato:** R$ 143.040,00
  - **Data do Contrato:** 13-02-2025
  - **Intervalo abertura-contrato:** 26 dias

* **PANIFICADORA GOSTO DE PAO LTDA**
  - **CNPJ:** 58.449.144/0001-00
  - **Data de Abertura:** 13-12-2024
  - **Valor do Contrato:** R$ 206.900,00
  - **Data do Contrato:** 12-02-2025

* **J C DE ALMEIDA FILHO COMERCIO**
  - **CNPJ:** 63.816.693/0001-05
  - **Data de Abertura:** 26-11-2025
  - **Valor do Contrato:** R$ 382.500,00
  - **Data do Contrato:** 28-01-2026

* **CARDIOCLINICA ANTONIO HELOISIO LIMEIRA PINHEIRO LTDA**
  - **CNPJ:** 60.510.060/0001-86
  - **Data de Abertura:** 23-04-2025
  - **Valor do Contrato:** R$ 100.800,00
  - **Data do Contrato:** 27-08-2025

* **CARNES E LATICINIOS ARAUJO LTDA**
  - **CNPJ:** 62.764.399/0001-34
  - **Data de Abertura:** 17-09-2025
  - **Valor do Contrato:** R$ 447.450,00
  - **Data do Contrato:** 28-01-2026

* **J C GARCIA AJALA LTDA**
  - **CNPJ:** 53.559.982/0001-12
  - **Data de Abertura:** 18-01-2024
  - **Valor do Contrato:** R$ 246.924,00
  - **Data do Contrato:** 09-07-2024

## 3. Anomalia Contábil Identificada (TCE-PB)

Os dados do TCE-PB apresentam uma divergência no caso da CONCRIAR ENGENHARIA: o empenho registrado foi de R$ 131.120,00, porém o valor liquidado/pago consta como R$ 11.920,00 -- uma diferença superior a 90%. Essa divergência pode indicar restos a pagar, cancelamento parcial do empenho ou erro de registro, e merece verificação junto ao município.

## 4. Investigações Existentes Relacionadas ao Município

Fontes públicas indicam que o município de São Bento/PB é objeto de procedimentos em diferentes órgãos de controle:

* **Inquérito Civil (MPPB):** O Ministério Público da Paraíba instaurou procedimento para apurar denúncias de irregularidades em licitações da prefeitura, incluindo possível direcionamento de certames e nepotismo. O MPPB requisitou cópias de processos licitatórios e solicitou cruzamento de dados da folha de pagamento ao Tribunal de Contas.

* **Ação Civil Pública - Caso Isa Comércio (MPPB):** O MPPB ajuizou ação de improbidade administrativa relacionada a compras emergenciais durante a pandemia, envolvendo a empresa Isa Comércio e alegações de sobrepreço na aquisição de máscaras PFF1.

* **Auditorias do TCE-PB:** O ex-prefeito foi intimado pelo Tribunal de Contas a prestar esclarecimentos sobre contratações de pessoal e uso de inexigibilidade de licitação para serviços médicos.

* **Operação Recidiva (PF/CGU):** São Bento foi um dos municípios abrangidos por operação da Polícia Federal e da Controladoria-Geral da União que investigou desvios em obras de infraestrutura hídrica na região.

## 5. Fontes e Referências

1. **MPPB** - Investigação de irregularidades em São Bento: [mppb.mp.br](https://www.mppb.mp.br/index.php/pt/comunicacao/noticias/20-patrimonio-publico/19845-promotoria-vai-investigar-denuncias-de-irregularidades-em-sao-bento)
2. **Blog do Ninja** - Ação do MPPB sobre compra de máscaras: [blogdoninja.com.br](https://blogdoninja.com.br/jarques-lucio-e-alvo-de-acao-do-mppb-por-compra-superfaturada-de-mascaras-em-sao-bento/)
3. **IstoE Dinheiro** - Operacao Recidiva (PF/CGU): [istoedinheiro.com.br](https://istoedinheiro.com.br/forca-tarefa-da-pf-e-cgu-investiga-desvios-milionarios-em-obras-contra-seca-na-pb/)
4. **Portal da Transparencia de Sao Bento:** [saobento.pb.gov.br/transparencia](https://saobento.pb.gov.br/transparencia/)
5. **Paraiba Ja** - Intimacoes do TCE-PB: [paraibaja.com.br](https://paraibaja.com.br/tce-pb-intima-ex-prefeito-de-sao-bento-para-explicar-irregularidades/)
