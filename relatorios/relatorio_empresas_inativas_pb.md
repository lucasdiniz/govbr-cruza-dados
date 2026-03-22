# Relatório de Investigação: Contratos com Empresas "Mortas" (Inativas) no Interior da PB

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados` (Arquivo `q15_empresa_inativa_que_recebe_pagamentos.csv`)
**Municípios Alvo:** Princesa Isabel e Riacho dos Cavalos (PB)

---

## 1. Resumo Executivo
A análise cruzada entre a situação cadastral de CNPJs na Receita Federal e as publicações do Portal Nacional de Contratações Públicas (PNCP) revelou fraudes crassas no interior da Paraíba. Prefeituras estão empenhando e pagando recursos públicos a **empresas legalmente inexistentes ("Baixadas" ou "Inaptas")**, uma prática que tipicamente mascara esquemas de notas frias para desvio direto de dinheiro dos cofres municipais.

## 2. O Golpe dos Shows em Princesa Isabel/PB
O setor de eventos é historicamente vulnerável por entregar produtos "imateriais". O cruzamento flagrou que a Prefeitura assinou um contrato de **R$ 58.500,00** para "locação de estruturas de som e shows musicais" com a empresa *Roberlandia Andrelino (Nome Fantasia: Diniz Som)* usando um CNPJ que já estava legalmente **BAIXADO**.

**Vínculos Políticos e OSINT:** Uma investigação aprofundada revelou que Roberlandia não é servidora pública, mas uma "fornecedora serial" da prefeitura via Dispensa de Licitação. O nome fantasia do seu CNPJ baixado, **Diniz Som**, aponta para ligações com a família Diniz, um dos tradicionais clãs políticos que disputam o controle da cidade. Ela continuou a faturar novos contratos de R$ 60.000,00 na gestão do atual prefeito Ednaldo "Garrancho", simplesmente trocando de CNPJ.

### Histórico de CNPJs (A Tática de Descarte):
* **CNPJ 1:** 30.848.514/0001-62 (Diniz Som) - Aberto em Jul/2018 - Status: **Baixada**. *(CNPJ "morto" usado no contrato de 2024)*.
* **CNPJ 2:** 53.123.983/0001-10 (Roberlandia Andrelino) - Aberto em Dez/2023 - Status: **Ativa**. *(Novo CNPJ criado para receber os contratos de 2025)*.

## 3. O Esquema Gráfico em Riacho dos Cavalos/PB
A prefeitura usou a Dispensa de Licitação nº 00016/2025 para firmar um contrato de **R$ 49.060,00** para "serviços de confecção e artefatos gráficos" com a empresa *Samara Saldanha de Oliveira (S. S. Grafica e Brindes)*. O CNPJ utilizado no contrato já constava como Inativo/Baixado.

**Vínculos e a Tática "Abre e Ganha":** A pesquisa OSINT revelou que Samara atua como fornecedora contumaz da gestão do prefeito Arthur Vieira Carneiro. Para driblar bloqueios fiscais, ela opera um verdadeiro esquema de "CNPJs descartáveis".

### Histórico de CNPJs (A Tática de Descarte):
A consulta direta à base de dados da Receita Federal expôs que a mesma pessoa opera abrindo e fechando firmas individuais sistematicamente:
* **CNPJ 1:** 37.259.260/0001-96 - Aberto em Mai/2020 - Status: **Baixada**. *(O CNPJ morto que pegou o contrato de 2025)*.
* **CNPJ 2:** 59.299.825/0001-00 - Aberto em Fev/2025 - Status: **Baixada**. *(CNPJ de vida curtíssima, aberto e já baixado/descartado em seguida)*.
* **CNPJ 3:** 64.672.335/0001-39 - Aberto em Jan/2026 - Status: **Ativa**. *(A "roupagem" mais recente, criada apenas 30 dias antes de ganhar o novo contrato de R$ 61.997,50 no Diário Oficial de 25/02/2026).*

## 4. Status de Investigação (Detecção Precoce)
Uma pesquisa profunda (OSINT) cruzando o nome das proprietárias com as bases do MPPB e TCE-PB confirmou que **não existem inquéritos ou operações deflagradas** contra elas até a presente data. O algoritmo realizou uma "Detecção Precoce". A ocultação de vínculo em folha de pagamento e o fracionamento de valores mantiveram a fraude abaixo do radar.

## 5. Conclusão
O empenho de notas fiscais de CNPJs baixados deveria ser bloqueado automaticamente por sistemas contábeis básicos. A aprovação manual aponta para dolo dos ordenadores de despesa, utilizando "Dispensas de Licitação" para direcionar verbas a aliados e pulverizar gastos através do uso de múltiplos CNPJs descartáveis ("eu-presas").

## Fontes e Referências
1. **Portal Nacional de Contratações Públicas (PNCP):** Link direto para o contrato de 2025 da Samara (CNPJ Baixado). [Acesse o Contrato no PNCP](https://pncp.gov.br/app/contratos/08921876000182/2025/19).
2. **Portal da Transparência (Riacho dos Cavalos):** [Acesse o PDF Oficial do Contrato 010/2026 de R$ 61.997,50 (Novo CNPJ)](https://riachodoscavalos.pb.gov.br/images/arquivos/documentos/1772130459.pdf).
3. **Portal da Transparência (Princesa Isabel):** Contratos e publicações de licitação comprovando a contratação da Diniz Som via dispensa.
4. **Receita Federal / Consulta Pública:** Verificação do status e do histórico completo de criação/baixa de todos os 5 CNPJs listados no relatório.
5. **Arquivos do Projeto:** `resultados\q15_empresa_inativa_que_recebe_pagamentos.csv`