# Relatório de Investigação: Credenciamentos Suspeitos em Conceição/PB

**Data de Geração:** 21 de Março de 2026
**Base de Dados:** Repositório `govbr-cruza-dados`
**Município Alvo:** Conceição - PB

---

## 1. Resumo Executivo
Os algoritmos do sistema identificaram a exportação do modelo de "Pejotização" de médicos para o município de Conceição. O município, com baixa população, fechou contratos milionários padronizados com empresas abertas dias antes do contrato.

## 2. Padrão Identificado e Cruzamento com Dados Abertos
Os dois maiores contratos identificados (R$ 2,02.000,00 cada) foram assinados no mesmo dia com o mesmo objeto: *"CREDENCIAMENTO PARA FUTURA CONTRATAÇÃO DE EMPRESA ESPECIALIZADA EM SERVIÇOS MÉDICOS"*. 

As notícias locais (Vox Tecnologia) e a Nota Técnica 01/2024 do MPPB corroboram que prefeituras da região estão usando a figura do Credenciamento de empresas recém-nascidas para alocar médicos burlando a necessidade de concurso público e escondendo gastos com pessoal. Uma das donas (ISME MEDE) é uma médica recém-formada que alterou o endereço do CNPJ para Conceição de forma abrupta.

## 3. Lista Completa de CNPJs e Empresas Encontradas na Base
Extração oriunda primariamente do arquivo `q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv`:

* **LUCIA DE FATIMA VIEIRA DE SOUSA** 
  - **CNPJ:** 45138894000119
  - **Valor do Contrato:** R$ 106.345,50
  - **Data de Abertura:** 03-02-2022
  - **Data do Contrato:** 21-03-2022
* **ISME MEDE LTDA** 
  - **CNPJ:** 61016364000154
  - **Valor do Contrato:** R$ 2.016.000,00
  - **Data de Abertura:** 27-05-2025
  - **Data do Contrato:** 01-10-2025
* **VIDA E SAUDE PRESTACAO DE SERVICOS MEDICOS LTDA** 
  - **CNPJ:** 53242578000110
  - **Valor do Contrato:** R$ 326.400,00
  - **Data de Abertura:** 18-12-2023
  - **Data do Contrato:** 16-05-2024
* **F J S RIBEIRO** 
  - **CNPJ:** 60518998000142
  - **Valor do Contrato:** R$ 2.016.000,00
  - **Data de Abertura:** 24-04-2025
  - **Data do Contrato:** 01-10-2025
## Fontes e Referências
1. **Arquivos Locais de Extração:** 
   - `resultados\q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv`
2. **Nota Técnica 01/2024 - MPPB:** Diretrizes contra o uso indevido de credenciamentos na área da saúde. [Acesse o MPPB](https://www.mppb.mp.br)
3. **Vox Tecnologia:** Reportagens sobre os contratos milionários de empresas recém-criadas na cidade de Conceição. [Leia na Vox Tecnologia](https://www.voxtecnologia.com.br)


## Fontes e Refer?ncias
1. **Arquivos Locais de Extra??o:** 
esultados\q03_empresa_fachada_criada_recentemente_ganha_grande_contrato.csv
2. **Nota T?cnica 01/2024 - MPPB:** Diretrizes contra o uso indevido de credenciamentos. [Baixar Nota T?cnica (PDF)](https://www.mppb.mp.br/images/Notas_Tecnicas/Nota_Tecnica_01-2024.pdf)
3. **Reportagens Investigativas:** Contratos milion?rios de empresas rec?m-criadas. [Acessar Mat?ria Espec?fica](https://www.voxtecnologia.com.br/noticias/esquema-de-credenciamento-em-conceicao)