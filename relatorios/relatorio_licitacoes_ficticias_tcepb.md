# Relatório: Licitações com Proponente Único e Anomalias de Dados no TCE-PB

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Arquivo `q68_licitacao_tce_pb_com_proponente_unico...`)
**Foco:** Licitações com participante único e inconsistências de valores na base Sagres/TCE-PB.

> **Nota:** Este relatório apresenta cruzamentos automatizados de dados públicos. Os achados representam anomalias estatísticas que merecem apuração, não conclusões de irregularidade.

---

## 1. Resumo

O cruzamento da base de licitações do Tribunal de Contas do Estado da Paraíba (TCE-PB) identificou dois padrões: (a) licitações de alto valor com apenas um proponente e (b) registros com valores inconsistentes que indicam falhas de validação no sistema Sagres.

## 2. Licitações de Alto Valor com Proponente Único em João Pessoa

A prefeitura de João Pessoa realizou licitações para o "Complexo Viário Altiplano" (obras de viadutos e requalificação viária) em que apenas um consórcio apresentou proposta em cada certame:

- **Concorrência nº 99902/2025:** Vencida pelo *Consórcio Mobilidade João Pessoa* pelo valor de **R$ 128.390.000,00**. Proponente único.
- **Concorrência nº 99003/2025:** Vencida pelo *Consórcio Altiplano* pelo valor de **R$ 106.790.217,60**. Proponente único.

As duas obras somam aproximadamente R$ 235 milhões. A ocorrência de proponente único em licitações dessa magnitude é um indicador que os órgãos de controle costumam monitorar, pois pode refletir tanto características específicas do mercado (como a complexidade técnica da obra) quanto possíveis restrições indevidas no edital. A causa específica depende de análise detalhada do edital e das condições de mercado.

## 3. Inconsistências de Valores na Base Sagres (Erros de Digitação)

O algoritmo também identificou registros na base do TCE-PB com valores evidentemente inconsistentes, indicando erros de entrada de dados:

- **Nova Palmeira/PB:** Registro de pregão para material elétrico no valor de **R$ 16.389.998.361,00** (dezesseis bilhões), com proponente único (JSA Comércio e Serviços Ltda). O valor é incompatível com o porte do município e do objeto licitado.
- **Monteiro/PB:** Registro de pregão para combustíveis no valor de **R$ 768.200.000,00** (setecentos e sessenta e oito milhões), com proponente único (Lucas & Saraiva Comércio de Combustíveis Ltda). O valor é igualmente inconsistente.

Esses registros evidenciam a ausência de validações automáticas no sistema Sagres que impeçam a inserção de valores fora de faixas plausíveis. Trata-se de uma fragilidade sistêmica que pode dificultar auditorias automatizadas e comprometer a confiabilidade dos dados abertos.

## 4. Cobertura em Fontes Abertas

Até a data de fechamento deste relatório, não foram encontradas matérias jornalísticas ou procedimentos do MPPB/TCE-PB questionando especificamente a ocorrência de proponente único nas licitações dos viadutos do Complexo Viário Altiplano, nem os erros de digitação nos registros de municípios do interior.

## Fontes e Referências

1. **Portal da Transparência de João Pessoa:** Consulta de licitações. [Portal de Compras - JP](https://transparencia.joaopessoa.pb.gov.br/licitacoes/)
2. **Tribunal de Contas do Estado (TCE-PB):** Dados Abertos do sistema Sagres (Módulo Licitações). [Acesse o Repositório de Licitações (Sagres-PB)](https://sagres.tce.pb.gov.br/dados_abertos.php)
3. **Arquivos do Projeto:** `resultados\q68_licitacao_tce_pb_com_proponente_unico_competicao_ficticia.csv`
