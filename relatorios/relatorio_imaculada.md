# Relatório: Contratações por Dispensa de Licitação em Imaculada/PB

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados`
**Município:** Imaculada - PB

> **Nota:** Este relatório apresenta cruzamentos automatizados de dados públicos. Os achados representam anomalias estatísticas que merecem apuração, não conclusões de irregularidade.

---

## 1. Resumo

O cruzamento de dados identificou contratos firmados pelo município de Imaculada/PB com empresas constituídas em data recente em relação à data de contratação. Ambos os contratos foram realizados por dispensa de licitação.

## 2. Empresas Identificadas

Extração oriunda do arquivo `q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv`:

### 2.1 Instituto Saúde Express

- **CNPJ:** 58694763000160
- **Valor do Contrato:** R$ 240.450,00
- **Data de Abertura da Empresa:** 26/12/2024
- **Data do Contrato:** 20/06/2025
- **Intervalo entre abertura e contrato:** aproximadamente 6 meses

**Atuação em outros municípios (verificada no PNCP):** A empresa também possui contratos registrados em Juru/PB (R$ 160.300,00), Itaporanga/PB (R$ 170.960,00), Ouricuri/PE (R$ 983.445,00) e na Assembleia Legislativa de Pernambuco (R$ 2.624.904,00). O fato de operar em múltiplos municípios e estados indica atuação regional no setor de saúde.

### 2.2 Fixar Editora Ltda

- **CNPJ:** 59744645000181
- **Valor do Contrato:** R$ 322.200,00
- **Data de Abertura da Empresa:** 05/03/2025
- **Data do Contrato:** 28/07/2025
- **Intervalo entre abertura e contrato:** aproximadamente 5 meses

**Atuação em outros municípios (verificada no PNCP):** A empresa também possui contratos registrados em Teixeira/PB, Matureia/PB, Tuparetama/PE e Pau dos Ferros/RN.

## 3. Observações

- Ambas as empresas foram constituídas poucos meses antes de receberem contratos por dispensa de licitação, o que constitui um padrão identificado pelo algoritmo de cruzamento.
- O TCE-PB possui histórico de alertas sobre o uso de dispensas emergenciais e unidades móveis de saúde em municípios do interior, tema que merece acompanhamento.
- A constatação de empresa recém-criada recebendo contrato público não é, por si só, evidência de irregularidade, mas é um indicador que justifica análise detalhada pelos órgãos de controle.

## Fontes e Referências

1. **Arquivos Locais de Extração:** `resultados\q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv`
2. **Tribunal de Contas do Estado da Paraíba (TCE-PB):** [Acesse o TCE-PB](https://tce.pb.gov.br)
3. **Portal Nacional de Contratações Públicas (PNCP):** Verificação de contratos das empresas em outros municípios.
4. **Diário Oficial dos Municípios:** Publicação das dispensas e contratos de Imaculada.
