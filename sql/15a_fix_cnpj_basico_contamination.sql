-- =============================================================================
-- sql/15a_fix_cnpj_basico_contamination.sql
-- =============================================================================
-- Migration one-off pra cleanup retroativo de cnpj_basico contaminado.
--
-- CONTEXTO: ETL anterior (etl/15_normalizar.py pre-PR feat/etl-cnpj-basico-fix)
-- populava cnpj_basico = LEFT(doc, 8) sem validar se doc era um CNPJ real do RFB.
-- CPFs (11 dig) sao armazenados em cpf_cnpj/cpfcnpj_* com prefixo de zeros (ex:
-- CPF 140.207.524-35 -> 00014020752435), e LEFT(..., 8) gera "cnpj_basico" que
-- colide com PJ real (ex: AVICOLA CHESTER MONGAGUA, CNPJ 00.014.020/0001-11).
--
-- Impacto medido (DB local):
--   tce_pb_despesa:  5.8M empenhos contaminados (36.7% de 16M)
--   pb_empenho:      1022 docs (5.2% de 19,740 distintos)
--   pb_saude:        34 docs (1.4%)
--   pb_contrato:     1 doc
--   pb_pagamento, pb_liquidacao_despesa, pb_empenho_*, pb_diaria: TBD em prod
--
-- ESTRATEGIA: setar cnpj_basico = NULL onde o doc completo nao existe em
-- estabelecimento (RFB). Com isso, todas as MVs e queries que filtram por
-- "WHERE cnpj_basico IS NOT NULL" automaticamente excluem CPFs padded —
-- sem precisar adicionar EXISTS guard em cada MV/query.
--
-- IDEMPOTENCIA: WHERE cnpj_basico IS NOT NULL + NOT EXISTS = segunda execucao
-- nao encontra rows pra anular (ja foram anulados ou eram CNPJs reais).
--
-- DOWNTIME: ZERO. UPDATE nao bloqueia SELECT (MVCC). MVs continuam servindo
-- dados velhos durante o UPDATE (snapshots independentes). Apos UPDATE,
-- rodar REFRESH MATERIALIZED VIEW CONCURRENTLY em cada MV afetada.
--
-- TEMPO ESTIMADO (B4): 10-30 min total. Maior parte em tce_pb_despesa (5.8M).
-- WAL crescera ~5GB temporario.
--
-- DEPENDENCIAS:
--   - Tabela estabelecimento populada (vem do RFB, fase 3 do ETL).
--   - Indice idx_estab_cnpj_completo em estabelecimento(cnpj_completo).
--
-- USO:
--   psql -d govbr -f sql/15a_fix_cnpj_basico_contamination.sql
--   ou via workflow: deploy.yml com input run_normalize_fix=true
-- =============================================================================

\timing on

-- TCE-PB (maior tabela, 5.8M rows previstos de UPDATE)
UPDATE tce_pb_despesa SET cnpj_basico = NULL
WHERE cnpj_basico IS NOT NULL
  AND LENGTH(cpf_cnpj) = 14
  AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpf_cnpj);

-- dados.pb (estadual)
UPDATE pb_pagamento SET cnpj_basico = NULL
WHERE cnpj_basico IS NOT NULL
  AND LENGTH(cpfcnpj_credor) = 14
  AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

UPDATE pb_empenho SET cnpj_basico = NULL
WHERE cnpj_basico IS NOT NULL
  AND LENGTH(cpfcnpj_credor) = 14
  AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

UPDATE pb_contrato SET cnpj_basico = NULL
WHERE cnpj_basico IS NOT NULL
  AND LENGTH(cpfcnpj_contratado) = 14
  AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_contratado);

UPDATE pb_saude SET cnpj_basico = NULL
WHERE cnpj_basico IS NOT NULL
  AND LENGTH(cpfcnpj_credor) = 14
  AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

UPDATE pb_convenio SET cnpj_basico = NULL
WHERE cnpj_basico IS NOT NULL
  AND LENGTH(cnpj_convenente) = 14
  AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cnpj_convenente);

UPDATE pb_liquidacao_despesa SET cnpj_basico = NULL
WHERE cnpj_basico IS NOT NULL
  AND LENGTH(cpfcnpj_credor) = 14
  AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

UPDATE pb_empenho_anulacao SET cnpj_basico = NULL
WHERE cnpj_basico IS NOT NULL
  AND LENGTH(cpfcnpj_credor) = 14
  AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

UPDATE pb_empenho_suplementacao SET cnpj_basico = NULL
WHERE cnpj_basico IS NOT NULL
  AND LENGTH(cpfcnpj_credor) = 14
  AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

UPDATE pb_diaria SET cnpj_basico = NULL
WHERE cnpj_basico IS NOT NULL
  AND LENGTH(cpfcnpj_credor) = 14
  AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

-- Report final
SELECT
  'tce_pb_despesa' AS tbl,
  COUNT(*) FILTER (WHERE cnpj_basico IS NOT NULL) AS com_basico,
  COUNT(*) FILTER (WHERE cnpj_basico IS NULL AND LENGTH(cpf_cnpj) = 14) AS null_de_cpf_padded
FROM tce_pb_despesa;
