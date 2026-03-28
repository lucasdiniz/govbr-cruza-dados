# Relatório de Cruzamento de Dados: Credenciamentos em Conceição/PB

> **Aviso:** Este relatório apresenta cruzamentos automatizados de dados públicos. Os achados representam anomalias estatísticas que merecem apuração, não conclusões de irregularidade.

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados`
**Município:** Conceição - PB

---

## 1. Resumo

O cruzamento automatizado de dados do PNCP e da Receita Federal identificou contratos de credenciamento na área de saúde firmados pelo Município de Conceição com empresas recém-constituídas. Os valores contratados são desproporcionais ao capital social declarado pelas empresas.

## 2. Padrão Identificado

Dois contratos de R$ 2.016.000,00 cada foram assinados na mesma data (01/10/2025) com o mesmo objeto: *"CREDENCIAMENTO PARA FUTURA CONTRATAÇÃO DE EMPRESA ESPECIALIZADA EM SERVIÇOS MÉDICOS"*.

As duas empresas contratadas foram constituídas poucos meses antes da assinatura:

| Empresa | CNPJ | Capital Social | Data de Constituição | Valor do Contrato | Data do Contrato |
|---|---|---|---|---|---|
| ISME MEDE LTDA | 61016364 | R$ 15.000,00 | 27/05/2025 | R$ 2.016.000,00 | 01/10/2025 |
| F J S RIBEIRO | 60518998 | R$ 20.000,00 | 24/04/2025 | R$ 2.016.000,00 | 01/10/2025 |

A desproporção entre o capital social declarado (R$ 15.000 e R$ 20.000) e o valor dos contratos (R$ 2.016.000 cada) é significativa. A Nota Técnica 01/2024 do MPPB aborda diretrizes sobre o uso de credenciamentos na área da saúde por prefeituras da região.

## 3. Demais Contratos Identificados

Extração oriunda do arquivo `q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv`:

| Empresa | CNPJ | Valor do Contrato | Data de Abertura | Data do Contrato |
|---|---|---|---|---|
| LUCIA DE FATIMA VIEIRA DE SOUSA | 45138894000119 | R$ 106.345,50 | 03/02/2022 | 21/03/2022 |
| VIDA E SAUDE PRESTACAO DE SERVICOS MEDICOS LTDA | 53242578000110 | R$ 326.400,00 | 18/12/2023 | 16/05/2024 |

## Fontes e Referências

1. **Arquivos Locais de Extração:** `resultados\q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv`
2. **Nota Técnica 01/2024 - MPPB:** Diretrizes sobre o uso de credenciamentos na área da saúde. [Acesse o MPPB](https://www.mppb.mp.br)
3. **Vox Tecnologia:** Reportagens sobre contratos de credenciamento em Conceição. [Leia na Vox Tecnologia](https://www.voxtecnologia.com.br)
