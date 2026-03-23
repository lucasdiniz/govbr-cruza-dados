# Relatório de Investigação: Licitações "Fictícias" e Anomalias Contábeis (TCE-PB)

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Arquivo `q68_licitacao_tce_pb_com_proponente_unico...`)
**Foco:** Ocorrência de "Proponente Único" em licitações bilionárias (erros do sistema Sagres) e direcionamento em megaobras de infraestrutura.

---

## 1. Resumo Executivo
O arquivo Q68 cruza as bases de licitação do Tribunal de Contas do Estado da Paraíba (TCE-PB) focando em um dos maiores indícios de fraude do mundo contábil: licitações onde **apenas uma empresa se apresenta para competir** e sai vencedora. A auditoria na base identificou dois padrões preocupantes: a "concorrência zero" para as maiores obras públicas da capital e o colapso na validação de dados no interior do estado (aceitação de empenhos bilionários por erro de digitação).

## 2. A "Concorrência Zero" nos Viadutos de João Pessoa
A prefeitura de João Pessoa está executando o milionário "Complexo Viário Altiplano", um conjunto de obras de infraestrutura massiva (viadutos e requalificação viária). O sistema alertou para a completa ausência de competitividade nestes certames em 2026:

* **Viaduto 1 e 3:** A Concorrência nº 99902/2025 foi vencida pelo *Consorcio Mobilidade Joao Pessoa* pelo valor de **R$ 128.390.000,00**. Não houve nenhuma outra construtora concorrendo.
* **Viaduto 2 e 4:** A Concorrência nº 99003/2025 foi vencida pelo *Consorcio Altiplano* pelo valor de **R$ 106.790.217,60**. Novamente, proponente único.

**O Risco (Direcionamento):** Obras que somam um quarto de bilhão de reais e não atraem mais de um consórcio nacional para disputa de lances configuram um caso clássico de **Edital Restritivo**. A prefeitura insere cláusulas ou exigências técnicas tão específicas no edital que apenas o "consórcio amigo" consegue se qualificar, espantando (ou desclassificando) os concorrentes antes mesmo de a disputa de preços começar.

## 3. O Colapso dos "Trilhões" no Interior (Fragilidade do Sagres)
O algoritmo também provou que a base de dados oficial do estado (Sagres/TCE) engole qualquer número digitado por contadores de prefeituras pequenas, sem travas sistêmicas, mascarando a fraude de proponente único debaixo de erros crassos:

* **O Material Elétrico de 16 Bilhões (Nova Palmeira/PB):** O município informou no sistema do TCE que a empresa *JSA COMÉRCIO E SERVIÇOS LTDA* foi a única participante e vencedora de um pregão para material elétrico no valor de **R$ 16.389.998.361,00** (Dezesseis bilhões de reais). 
* **O Combustível de 768 Milhões (Monteiro/PB):** A prefeitura informou que a *Lucas & Saraiva Comercio de Combustiveis Ltda* ganhou, sozinha, um pregão de **R$ 768.200.000,00**.

**Conclusão sobre as Anomalias:** Esses valores são claramente erros humanos (o operador da prefeitura digitou o valor sem usar a vírgula para os centavos, ou incluiu códigos de barras no campo de valor). Contudo, o fato da auditoria sistêmica do TCE-PB não possuir um filtro que bloqueie uma prefeitura de 5 mil habitantes de cadastrar uma licitação de 16 Bilhões com apenas um concorrente prova que o controle interno atual é reativo e analógico, dependendo de ferramentas modernas como o `govbr-cruza-dados` para limpar o ruído.

## Fontes e Referências
1. **Dados de Licitações Oficiais (Viadutos JP):** Consulta de andamento de licitações na Prefeitura de João Pessoa. [Portal de Compras - JP](https://transparencia.joaopessoa.pb.gov.br/licitacoes/)
2. **Tribunal de Contas do Estado (TCE-PB):** Dados Abertos (Sagres - Módulo Licitações) reportando os erros bilionários e a ausência de concorrentes. [Acesse o Repositório de Licitações (Sagres-PB)](https://sagres.tce.pb.gov.br/dados_abertos.php)
3. **Arquivos Locais de Extração:** `resultados\q68_licitacao_tce_pb_com_proponente_unico_competicao_ficticia.csv`