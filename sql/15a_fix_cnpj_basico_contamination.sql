-- =============================================================================
-- sql/15a_fix_cnpj_basico_contamination.sql
-- =============================================================================
-- Migration one-off pra cleanup retroativo de cnpj_basico contaminado +
-- extracao de cpf_digitos pra queries futuras de pessoa fisica.
--
-- CONTEXTO: ETL anterior populava cnpj_basico = LEFT(doc, 8) sem validar se
-- doc era um CNPJ real do RFB. CPFs (11 dig) sao armazenados em
-- cpf_cnpj/cpfcnpj_* com prefixo de zeros (ex: CPF 140.207.524-35 ->
-- 00014020752435), e LEFT(..., 8) gera "cnpj_basico" que colide com PJ real
-- (ex: AVICOLA CHESTER MONGAGUA, CNPJ 00.014.020/0001-11).
--
-- ESTRATEGIA: 2 UPDATEs separados por tabela (achado em GPT-5.5 re-review):
--   1. ANULAR cnpj_basico onde nao existe em estabelecimento (qualquer doc
--      14-char nao-RFB — inclui CPF padded e tambem CNPJs malformados tipo
--      SEFAZ '04000000062504').
--   2. EXTRAIR cpf_digitos apenas pra docs que comecam com '000' (CPF
--      padded "verdadeiro"). Filtro LEFT '000' evita popular cpf_digitos
--      com lixo de CNPJ malformado.
--
-- POR QUE 2 UPDATEs:
-- Em cargas futuras (apos esta migration + EXISTS guard preventivo em
-- etl/15_normalizar.py), CPFs padded entram com cnpj_basico=NULL desde o
-- inicio. Um UPDATE combinado WHERE cnpj_basico IS NOT NULL nao alcancaria
-- essas rows pra popular cpf_digitos. UPDATE 2 com WHERE cpf_digitos IS
-- NULL cobre tanto retroativo quanto incremental.
--
-- Impacto medido (DB local) — rows que terao cnpj_basico anulado:
--   tce_pb_despesa:  5.8M empenhos (36.7% de 16M)
--   pb_empenho:      1022 docs (5.2% de 19,740 distintos)
--   pb_saude:        34 docs (1.4%)
--   pb_contrato:     1 doc
--
-- IDEMPOTENCIA: UPDATE 1 WHERE cnpj_basico IS NOT NULL; UPDATE 2 WHERE
-- cpf_digitos IS NULL. Segunda execucao nao encontra rows pra processar.
-- ALTER TABLE IF NOT EXISTS + CREATE INDEX CONCURRENTLY IF NOT EXISTS
-- sao idempotentes.
--
-- DOWNTIME: ZERO. UPDATE nao bloqueia SELECT (MVCC). MVs continuam servindo
-- dados velhos durante o UPDATE (snapshots independentes). Apos UPDATE,
-- rodar REFRESH MATERIALIZED VIEW CONCURRENTLY em cada MV afetada.
--
-- TEMPO ESTIMADO (B4): 20-50 min total (2 UPDATEs por tabela + creates de
-- indice). WAL crescera ~5GB temporario.
--
-- REQUER:
--   - Tabela estabelecimento populada (vem do RFB, fase 3 do ETL).
--   - Indice idx_estab_cnpj_completo em estabelecimento(cnpj_completo).
--
-- USO:
--   psql -d govbr -f sql/15a_fix_cnpj_basico_contamination.sql
--   ou via workflow: deploy.yml com input run_normalize_fix=true
-- =============================================================================

\timing on

-- ── ADD COLUMN cpf_digitos em todas as tabelas afetadas ──
-- VARCHAR(11) pra armazenar os 11 digitos do CPF extraidos de doc 14-char padded.
ALTER TABLE tce_pb_despesa            ADD COLUMN IF NOT EXISTS cpf_digitos VARCHAR(11);
ALTER TABLE pb_pagamento              ADD COLUMN IF NOT EXISTS cpf_digitos VARCHAR(11);
ALTER TABLE pb_empenho                ADD COLUMN IF NOT EXISTS cpf_digitos VARCHAR(11);
ALTER TABLE pb_contrato               ADD COLUMN IF NOT EXISTS cpf_digitos VARCHAR(11);
ALTER TABLE pb_saude                  ADD COLUMN IF NOT EXISTS cpf_digitos VARCHAR(11);
ALTER TABLE pb_convenio               ADD COLUMN IF NOT EXISTS cpf_digitos VARCHAR(11);
ALTER TABLE pb_liquidacao_despesa     ADD COLUMN IF NOT EXISTS cpf_digitos VARCHAR(11);
ALTER TABLE pb_empenho_anulacao       ADD COLUMN IF NOT EXISTS cpf_digitos VARCHAR(11);
ALTER TABLE pb_empenho_suplementacao  ADD COLUMN IF NOT EXISTS cpf_digitos VARCHAR(11);
ALTER TABLE pb_diaria                 ADD COLUMN IF NOT EXISTS cpf_digitos VARCHAR(11);

-- ── UPDATE 1: anular cnpj_basico contaminado (retroativo) ──
-- Idempotente: WHERE cnpj_basico IS NOT NULL. Cobre TODOS os docs 14-char
-- nao-RFB (CPF padded ou CNPJ malformado).

UPDATE tce_pb_despesa SET cnpj_basico = NULL
 WHERE cnpj_basico IS NOT NULL
   AND LENGTH(cpf_cnpj) = 14
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpf_cnpj);

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

-- ── UPDATE 2: extrair cpf_digitos pra CPFs padded "verdadeiros" (LEFT '000') ──
-- Idempotente: WHERE cpf_digitos IS NULL. Cobre rows velhas (retroativo) E
-- rows novas (cargas incrementais que entram com cnpj_basico=NULL gracas ao
-- EXISTS guard preventivo em etl/15_normalizar.py).
-- Filtro LEFT '000' garante que docs malformados (ex: SEFAZ) nao virem
-- "CPFs" sinteticos.

UPDATE tce_pb_despesa SET cpf_digitos = SUBSTRING(cpf_cnpj FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpf_cnpj) = 14
   AND LEFT(cpf_cnpj, 3) = '000'
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpf_cnpj);

UPDATE pb_pagamento SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND LEFT(cpfcnpj_credor, 3) = '000'
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

UPDATE pb_empenho SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND LEFT(cpfcnpj_credor, 3) = '000'
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

UPDATE pb_contrato SET cpf_digitos = SUBSTRING(cpfcnpj_contratado FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_contratado) = 14
   AND LEFT(cpfcnpj_contratado, 3) = '000'
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_contratado);

UPDATE pb_saude SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND LEFT(cpfcnpj_credor, 3) = '000'
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

UPDATE pb_convenio SET cpf_digitos = SUBSTRING(cnpj_convenente FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cnpj_convenente) = 14
   AND LEFT(cnpj_convenente, 3) = '000'
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cnpj_convenente);

UPDATE pb_liquidacao_despesa SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND LEFT(cpfcnpj_credor, 3) = '000'
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

UPDATE pb_empenho_anulacao SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND LEFT(cpfcnpj_credor, 3) = '000'
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

UPDATE pb_empenho_suplementacao SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND LEFT(cpfcnpj_credor, 3) = '000'
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

UPDATE pb_diaria SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND LEFT(cpfcnpj_credor, 3) = '000'
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor);

-- ── Indices parciais em cpf_digitos pra queries de PF ──
-- Indice parcial WHERE cpf_digitos IS NOT NULL evita inchar com rows-de-CNPJ.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tce_pb_despesa_cpf_digitos
    ON tce_pb_despesa (cpf_digitos) WHERE cpf_digitos IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_pagamento_cpf_digitos
    ON pb_pagamento (cpf_digitos) WHERE cpf_digitos IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_empenho_cpf_digitos
    ON pb_empenho (cpf_digitos) WHERE cpf_digitos IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_contrato_cpf_digitos
    ON pb_contrato (cpf_digitos) WHERE cpf_digitos IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_saude_cpf_digitos
    ON pb_saude (cpf_digitos) WHERE cpf_digitos IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_convenio_cpf_digitos
    ON pb_convenio (cpf_digitos) WHERE cpf_digitos IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_liquidacao_despesa_cpf_digitos
    ON pb_liquidacao_despesa (cpf_digitos) WHERE cpf_digitos IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_empenho_anulacao_cpf_digitos
    ON pb_empenho_anulacao (cpf_digitos) WHERE cpf_digitos IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_empenho_suplementacao_cpf_digitos
    ON pb_empenho_suplementacao (cpf_digitos) WHERE cpf_digitos IS NOT NULL;
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_pb_diaria_cpf_digitos
    ON pb_diaria (cpf_digitos) WHERE cpf_digitos IS NOT NULL;

-- Report final: confirma que cnpj_basico foi limpo e cpf_digitos foi populado
SELECT
  'tce_pb_despesa' AS tbl,
  COUNT(*) FILTER (WHERE cnpj_basico IS NOT NULL) AS com_basico_cnpj_real,
  COUNT(*) FILTER (WHERE cnpj_basico IS NULL AND cpf_digitos IS NOT NULL) AS com_cpf_pf,
  COUNT(*) FILTER (WHERE cnpj_basico IS NULL AND cpf_digitos IS NULL AND LENGTH(cpf_cnpj) = 14) AS sem_id_lixo
FROM tce_pb_despesa;
