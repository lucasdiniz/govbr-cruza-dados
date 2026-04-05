# Dicionário de Dados - Portal Dados PB

Fonte: https://dados.pb.gov.br/app/
API: `https://dados.pb.gov.br/getcsv?nome=DATASET&exercicio=ANO&mes=MES`

## Datasets Prioritários

### 1. empenho_original (SIAF - Notas de Empenho)
- **Período disponível**: 2000-2026
- **Granularidade**: mensal
- **Colunas**:
  - EXERCICIO, CODIGO_UNIDADE_GESTORA
  - NUMERO_EMPENHO, NUMERO_EMPENHO_ORIGEM, DATA_EMPENHO
  - HISTORICO_EMPENHO (texto livre descritivo)
  - CODIGO_SITUACAO_EMPENHO, NOME_SITUACAO_EMPENHO
  - CODIGO_TIPO_EMPENHO, DESCRICAO_TIPO_EMPENHO
  - VALOR_EMPENHO
  - CODIGO_MODALIDADE_LICITACAO, CODIGO_MOTIVO_DISPENSA_LICITACAO
  - CODIGO_TIPO_CREDITO, NOME_TIPO_CREDITO
  - DESTINO_DIARIAS, DATA_SAIDA_DIARIAS, DATA_CHEGADA_DIARIAS
  - NOME_CREDOR, CPFCNPJ_CREDOR, TIPO_CREDOR
  - CODIGO_MUNICIPIO, NOME_MUNICIPIO
  - NUMERO_PROCESSO_PAGAMENTO, NUMERO_CONTRATO
  - CODIGO_UNIDADE_ORCAMENTARIA
  - CODIGO_FUNCAO, CODIGO_SUBFUNCAO, CODIGO_PROGRAMA, CODIGO_ACAO
  - CODIGO_FONTE_RECURSO, CODIGO_NATUREZA_DESPESA
  - CODIGO_CATEGORIA_ECONOMICA_DESPESA, CODIGO_GRUPO_NATUREZA_DESPESA
  - CODIGO_MODALIDADE_APLICACAO_DESPESA, CODIGO_ELEMENTO_DESPESA
  - CODIGO_ITEM_DESPESA
  - CODIGO_FINALIDADE_FIXACAO, NOME__FINALIDADE_FIXACAO
  - CODIGO_LICITACAO, ORCAMENTO_DEMOCRATICO
- **Cruzamentos**: CPFCNPJ_CREDOR × empresa/socio/PGFN/CEIS. NUMERO_CONTRATO × contratos.

### 2. Diarias (SIAF - Notas de Empenho - Diárias)
- **Período disponível**: 2000-2026
- **Granularidade**: mensal (case-sensitive: "Diarias" com D maiúsculo)
- **Colunas**: mesma estrutura do empenho_original, mas filtrado para diárias
  - EXERCICIO, CODIGO_UNIDADE_GESTORA
  - NUMERO_EMPENHO, NUMERO_EMPENHO_ORIGEM, DATA_EMPENHO
  - HISTORICO_EMPENHO
  - CODIGO_SITUACAO_EMPENHO, CODIGO_TIPO_EMPENHO, DESCRICAO_TIPO_EMPENHO, NOME_SITUACAO_EMPENHO
  - VALOR_EMPENHO
  - CODIGO_MODALIDADE_LICITACAO, CODIGO_MOTIVO_DISPENSA_LICITACAO
  - CODIGO_TIPO_CREDITO, NOME_TIPO_CREDITO
  - **DESTINO_DIARIAS, DATA_SAIDA_DIARIAS, DATA_CHEGADA_DIARIAS** (campos-chave)
  - NOME_CREDOR, CPFCNPJ_CREDOR, TIPO_CREDOR
  - CODIGO_MUNICIPIO, NOME_MUNICIPIO
  - NUMERO_PROCESSO_PAGAMENTO, NUMERO_CONTRATO
  - CODIGO_UNIDADE_ORCAMENTARIA, CODIGO_FUNCAO, CODIGO_SUBFUNCAO
  - CODIGO_PROGRAMA, CODIGO_ACAO, CODIGO_FONTE_RECURSO
  - CODIGO_NATUREZA_DESPESA, CODIGO_CATEGORIA_ECONOMICA_DESPESA
  - CODIGO_GRUPO_NATUREZA_DESPESA, CODIGO_MODALIDADE_APLICACAO_DESPESA
  - CODIGO_ELEMENTO_DESPESA, CODIGO_ITEM_DESPESA
- **Cruzamentos**: CPFCNPJ_CREDOR × viagem federal (mesma pessoa, mesma data = dupla diária)

### 3. contratos (SIGA - Contratos)
- **Período disponível**: até 2023 (2024-2026 vazios)
- **Granularidade**: anual (sem parâmetro mes)
- **Colunas**:
  - CODIGO_CONTRATO, NUMERO_REGISTRO_CGE, NUMERO_CONTRATO
  - NOME_CONTRATANTE
  - NUMERO_PROCESSO_LICITATORIO
  - OBJETO_CONTRATO, COMPLEMENTO_OBJETO_CONTRATO
  - NOME_CONTRATADO, CPFCNPJ_CONTRATADO
  - DATA_CELEBRACAO_CONTRATO, DATA_PUBLICACAO
  - DATA_INICIO_VIGENCIA, DATA_TERMINO_VIGENCIA
  - VALOR_ORIGINAL
  - NOME_MUNICIPIO, OUTROS_MUNICIPIOS
  - NOME_GESTOR_CONTRATO
  - NUMERO_PORTARIA, DATA_PUBLICACAO_PORTARIA
  - URL_CONTRATO
- **Cruzamentos**: CPFCNPJ_CONTRATADO × empresa/socio. CODIGO_CONTRATO × aditivos.
- **Nota**: Já temos pb_contrato no banco — verificar se é a mesma fonte.

### 4. aditivos_contrato (SIGA - Contratos Aditivos)
- **Período disponível**: 2000-2026
- **Granularidade**: mensal
- **Colunas**:
  - CODIGO_ADITIVO_CONTRATO, CODIGO_CONTRATO
  - MOTIVO_ADITIVACAO
  - NUMERO_ADITIVO_CONTRATO
  - DATA_INICIO_VIGENCIA, DATA_TERMINO_VIGENCIA
  - VALOR_ADITIVO
  - OBJETO_ADITIVO
  - DATA_CELEBRACAO_ADITIVO, DATA_PUBLICACAO, DATA_REPUBLICACAO
  - URL_ADITIVO_CONTRATO
- **Cruzamentos**: CODIGO_CONTRATO → contratos. VALOR_ADITIVO vs VALOR_ORIGINAL (% de aditivo).

### 5. resumo_folha (FOPAG - Resumo Folha de Pagamento)
- **Período disponível**: até 2022 (2023+ vazio)
- **Granularidade**: mensal
- **Colunas**:
  - EXERCICIO, MES
  - QUADRO (ATIVOS, PENSIONISTAS, etc.)
  - PODER, ADMINISTRACAO
  - ORGAO, SECRETARIA, UNIDADE_TRABALHO
  - NOME_MUNICIPIO
  - GRUPO, REGIME
  - QUANTIDADE (nº servidores)
  - SOMA_SALARIO_BRUTO
- **Nota**: Dados agregados (não individuais). Útil para detectar picos anômalos na folha.

### 6. pagamento (SIAF - Autorizações de Pagamento)
- **Período disponível**: 2000-2026
- **Granularidade**: mensal
- **Colunas**:
  - EXERCICIO, CODIGO_UNIDADE_GESTORA
  - NUMERO_EMPENHO, NUMERO_AUTORIZACAO_PAGAMENTO
  - TIPO_DESPESA
  - DATA_PAGAMENTO, VALOR_PAGAMENTO
  - CODIGO_TIPO_DOCUMENTO, DESCRICAO_TIPO_DOCUMENTO
  - NOME_CREDOR, CPFCNPJ_CREDOR, TIPO_CREDOR
- **Cruzamentos**: NUMERO_EMPENHO → empenho_original. CPFCNPJ_CREDOR × empresa/socio.

## Datasets Média Prioridade (já encontrados)

| nome API | Dataset | Notas |
|----------|---------|-------|
| dotacao | CGE - Dotação Orçamentária | Orçado vs executado |
| liquidacao | CGE - Liquidação | Ciclo empenho→liquidação→pagamento |
| empenho_anulacao | SIAF - Empenho Anulação | Anulações de empenho |
| empenho_suplementacao | SIAF - Empenho Suplementação | Suplementações |
| aditivos_convenio | SIGA - Convênios Aditivos | Aditivos em convênios |
| dispensa_licitacao | DADOS-PB - Motivo Dispensa | Justificativas de dispensa |
| convenios | SIGA - Convênios Estado-Municípios | Convênios (já temos pb_convenio) |

### 7. pagamento_anulacao (SIAF - Anulações de Autorização de Pagamento)
- **Colunas**: EXERCICIO, CODIGO_UNIDADE_GESTORA, NUMERO_EMPENHO, NUMERO_GUIA_DEVOLUCAO, NUMERO_AUTORIZACAO_PAGAMENTO, DATA_DOCUMENTO, VALOR_DOCUMENTO, CODIGO_TIPO_DOCUMENTO, DESCRICAO_TIPO_DOCUMENTO
- **Cruzamentos**: NUMERO_EMPENHO → empenho_original. NUMERO_AUTORIZACAO_PAGAMENTO → pagamento.

### 8. liquidacaodespesa (SIAF - Liquidação de Despesa)
- **Colunas**: NU_EXERCICIO, DATA_MOV, CD_ORGAO, NU_EMPENHO, DOCUMENTO, DOCUMENTO_ORIGEM, ANO_DOC_ORIGEM_LD, TIPO_LIQUIDACAO, CD_CREDOR, CPF_CNPJ, TIPO_DOC_FISCAL, NUM_NOTAFISCAL, DATA_NF, CD_INSC_RP, ANO_INSC_RP, CD_ORGAO_EXTINTO, VALOR
- **Cruzamentos**: CPF_CNPJ × empresa/socio. NU_EMPENHO → empenho_original. Ciclo completo: empenho→liquidação→pagamento.

### 9. liquidacaodespesadescontos (SIAF - Descontos de Pagamento)
- **Colunas**: Exercicio, CD_Orgao, Num_Empenho, Num_Doc, DAT_PAGAMENTO, TP_PG, Cod_Desconto, Desconto, COD_ORGAO_PGT, VL_Desconto
- **Cruzamentos**: Num_Empenho → empenho_original.

### 10. unidade_gestora_dadospb (DADOS-PB - Unidade Gestora)
- **Granularidade**: anual (sem parâmetro mes)
- **Colunas**: EXERCICIO, CODIGO_UNIDADE_GESTORA, SIGLA_UNIDADE_GESTORA, NOME_UNIDADE_GESTORA, TIPO_ADMINISTRACAO_UNIDADE_GESTORA
- **Uso**: Tabela dimensão para decodificar CODIGO_UNIDADE_GESTORA nos outros datasets.

## Tabelas de domínio (referência)

| nome API | Dataset |
|----------|---------|
| grupo_financeiro | Grupo Financeiro |
| situacao_empenho | Situação Empenho |
| tipo_credito | Tipo de Crédito |
| receitas_execucao | Receitas - Execução |
| receitas_previsao | Receitas - Previsão |
