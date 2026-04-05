# Relatório de Análise: Concentração de Repasses ao Terceiro Setor na Paraíba

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Queries Q59 e Q60 — TCE-PB e DadosPB)
**Foco:** Concentração de repasses municipais em organizações do terceiro setor e potenciais conflitos de interesse.

> **Disclaimer:** Este relatório apresenta cruzamentos automatizados de dados públicos. Os achados representam **anomalias estatísticas** que merecem apuração, não conclusões de irregularidade. Repasses a entidades filantrópicas e hospitais do terceiro setor são, em muitos casos, instrumentos legítimos e necessários de política pública. A concentração de repasses em uma entidade pode refletir sua posição como prestador essencial de serviços, não necessariamente irregularidade.

---

## 1. Resumo Executivo
O cruzamento de dados identificou uma concentração significativa de repasses municipais em uma única entidade do terceiro setor na Paraíba: o **Instituto Walfredo Guedes Pereira**, que recebeu R$ 183,1 milhões de 158 dos 223 municípios do estado. Adicionalmente, foi identificado um potencial conflito de interesse envolvendo uma servidora municipal no quadro diretivo da entidade.

## 2. Concentração de Repasses
- **Entidade:** Instituto Walfredo Guedes Pereira (CNPJ 09.124.165/0001-40)
- **Volume total:** R$ 183.126.188,89
- **Abrangência:** 158 municípios (71% do estado)
- **Natureza dos repasses:** Subvenções, convênios e inexigibilidades, geralmente vinculados à prestação de serviços de saúde

**Contexto:** O Instituto administra complexos hospitalares como o Hospital São Vicente de Paulo. A concentração de repasses pode refletir sua posição como principal prestador de serviços hospitalares filantrópicos no estado.

## 3. Potencial Conflito de Interesse
A query Q59 identificou a Sra. **Maria Gerlane Carneiro Cavalcanti** no quadro diretivo do Instituto. O cruzamento com a folha de pagamento mostrou que ela é **Servidora Municipal Inativa** (Técnico de Comunicação Social) da Prefeitura de João Pessoa.

A presença de servidores municipais (ativos ou inativos) em diretorias de entidades que recebem repasses do mesmo município é uma situação que merece atenção do ponto de vista do princípio da impessoalidade, embora não constitua, por si só, irregularidade.

## 4. Histórico de Fiscalização
- **TCU (Acórdão 1060/2020):** Investigou parceria entre o Instituto e a Prefeitura de João Pessoa envolvendo uso de equipamentos de hemodiálise públicos sem licitação.
- **CRM-PB:** Notificação por escalas médicas incompletas no hospital gerido pelo Instituto.

## 5. Nota Metodológica
A análise de concentração de repasses não distingue automaticamente entre prestação legítima de serviços essenciais e eventual irregularidade. A apuração da regularidade dos convênios e repasses compete ao TCE-PB e ao Ministério Público.

## Fontes
1. **TCE-PB (Sagres):** Dados de subvenções e repasses a terceiro setor.
2. **Receita Federal (QSA):** Quadro diretivo do Instituto Walfredo Guedes Pereira.
3. **Arquivos do Projeto:** `resultados/q59_servidor_municipal...csv` e `resultados/q60_fornecedor_recebendo_pagamentos_sem_licitacao...csv`
