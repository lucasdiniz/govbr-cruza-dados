# Relatório: Contratos Públicos com Empresas em Situação Cadastral Irregular na PB

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Arquivo `q15_empresa_inativa_que_recebe_pagamentos.csv`)
**Municípios:** Princesa Isabel e Riacho dos Cavalos (PB)

> **Nota:** Este relatório apresenta cruzamentos automatizados de dados públicos. Os achados representam anomalias estatísticas que merecem apuração, não conclusões de irregularidade.

---

## 1. Resumo

O cruzamento entre a situação cadastral de CNPJs na Receita Federal e os contratos publicados no Portal Nacional de Contratações Públicas (PNCP) identificou casos em que prefeituras do interior da Paraíba firmaram contratos com empresas cujo CNPJ constava como "Baixado" (situação cadastral 8) na data da contratação.

## 2. Caso 1: Princesa Isabel/PB — Serviços de Sonorização e Eventos

A prefeitura firmou contrato de **R$ 58.500,00** para locação de estruturas de som e shows musicais com a empresa Roberlandia Andrelino (nome fantasia: Diniz Som).

**Situação cadastral do CNPJ utilizado no contrato:**

- **CNPJ 30.848.514/0001-62** (Diniz Som) — Aberto em julho/2018 — Situação cadastral: **Baixada** (código 8) desde 15/08/2023.

**CNPJ subsequente da mesma titular:**

- **CNPJ 53.123.983/0001-10** (Roberlandia Andrelino) — Aberto em 06/12/2023 — Situação cadastral: **Ativa**.

A sequência cronológica indica que o primeiro CNPJ foi baixado em agosto/2023 e um novo CNPJ foi aberto pela mesma pessoa em dezembro/2023, que passou a receber contratos subsequentes (R$ 60.000,00 em 2025).

## 3. Caso 2: Riacho dos Cavalos/PB — Serviços Gráficos

A prefeitura firmou, via Dispensa de Licitação nº 00016/2025, contrato de **R$ 49.060,00** para serviços de confecção e artefatos gráficos com a empresa Samara Saldanha de Oliveira (S. S. Gráfica e Brindes). O CNPJ utilizado no contrato constava como Baixado na Receita Federal.

**Histórico de CNPJs da mesma titular:**

- **CNPJ 37.259.260/0001-96** — Aberto em maio/2020 — Situação cadastral: **Baixada**. *(CNPJ utilizado no contrato de 2025)*.
- **CNPJ 59.299.825/0001-00** — Aberto em fevereiro/2025 — Situação cadastral: **Baixada**.
- **CNPJ 64.672.335/0001-39** — Aberto em janeiro/2026 — Situação cadastral: **Ativa**. *(Novo contrato de R$ 61.997,50 publicado no Diário Oficial em 25/02/2026)*.

A mesma pessoa física abriu três CNPJs em sequência, com os dois primeiros já baixados e o terceiro atualmente ativo.

## 4. Observações

- A emissão de empenhos e pagamentos a CNPJs com situação cadastral "Baixada" indica falha nos controles de validação cadastral dos sistemas contábeis municipais, que poderiam bloquear automaticamente essas operações.
- A abertura sequencial de CNPJs por um mesmo titular, com os anteriores sendo baixados, é um padrão que merece atenção dos órgãos de controle.
- Até a data deste relatório, não foram identificados inquéritos ou procedimentos do MPPB ou TCE-PB especificamente sobre estes casos.
- A verificação dos fatos descritos depende de confirmação pelos órgãos competentes, que possuem acesso a informações complementares não disponíveis em bases públicas.

## Fontes e Referências

1. **Portal Nacional de Contratações Públicas (PNCP):** Contrato de 2025 da Samara Saldanha. [Acesse o Contrato no PNCP](https://pncp.gov.br/app/contratos/08921876000182/2025/19).
2. **Portal da Transparência (Riacho dos Cavalos):** [Contrato 010/2026 de R$ 61.997,50](https://riachodoscavalos.pb.gov.br/images/arquivos/documentos/1772130459.pdf).
3. **Portal da Transparência (Princesa Isabel):** Contratos e publicações de licitação.
4. **Receita Federal / Consulta Pública:** Verificação do status cadastral e histórico de todos os CNPJs listados.
5. **Arquivos do Projeto:** `resultados\q15_empresa_inativa_que_recebe_pagamentos.csv`
