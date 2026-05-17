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
-- ESTRATEGIA: 2 UPDATEs separados por tabela usando DV check matematico:
--   1. ANULAR cnpj_basico onde nao existe em estabelecimento (qualquer doc
--      14-char nao-RFB — inclui CPF padded, MEI nao-sincronizado e CNPJs
--      malformados).
--   2. EXTRAIR cpf_digitos APENAS quando doc NAO eh CNPJ matematicamente
--      valido E os 11 chars apos posicao 4 SAO CPF valido. Isso garante
--      que MEIs com DV CNPJ valido (nao sincronizados em RFB ainda) NAO
--      virem "CPFs sinteticos" — eles esperam o RFB sync e ETL idempotente
--      retroativamente populara cnpj_basico depois.
--
-- POR QUE DV CHECK (em vez de prefix heuristico tipo LEFT '000'):
-- Validacao empirica em 16/05/2026 mostrou que docs nao-RFB com prefix
-- diferentes de '000' (ex: 65494241000180 MEI Andre Japiassu) tem DV CNPJ
-- VALIDO — sao CNPJs reais nao-sincronizados, nao "lixo". Heurística por
-- prefix '000' rejeitaria esses corretamente, mas tambem rejeitaria CPFs
-- legitimos com primeiro digito != 0 (raro mas possivel). DV check eh o
-- discriminator definitivo.
--
-- Impacto medido (DB local) — rows que terao cnpj_basico anulado:
--   tce_pb_despesa:  5.8M empenhos (36.7% de 16M)
--   pb_empenho:      1022 docs (5.2% de 19,740 distintos)
--   pb_saude:        34 docs (1.4%)
--   pb_contrato:     1 doc
--
-- IDEMPOTENCIA: UPDATE 1 WHERE cnpj_basico IS NOT NULL; UPDATE 2 WHERE
-- cpf_digitos IS NULL. Segunda execucao nao encontra rows pra processar.
-- ALTER TABLE IF NOT EXISTS + CREATE OR REPLACE FUNCTION + CREATE INDEX
-- CONCURRENTLY IF NOT EXISTS sao idempotentes.
--
-- DOWNTIME: ZERO. UPDATE nao bloqueia SELECT (MVCC). MVs continuam servindo
-- dados velhos durante o UPDATE (snapshots independentes). Apos UPDATE,
-- rodar REFRESH MATERIALIZED VIEW CONCURRENTLY em cada MV afetada.
--
-- TEMPO ESTIMADO (B4): 30-60 min total (DV check eh ~2x mais lento que prefix
-- heuristico — 5.8M rows em tce_pb_despesa). WAL crescera ~5GB temporario.
--
-- REQUER:
--   - Tabela estabelecimento populada (vem do RFB, fase 3 do ETL).
--   - Indice idx_estab_cnpj_completo em estabelecimento(cnpj_completo).
--   - PostgreSQL 11+ (procedures + array indexing).
--
-- USO:
--   psql -d govbr -f sql/15a_fix_cnpj_basico_contamination.sql
--   ou via workflow: deploy.yml com input run_normalize_fix=true
-- =============================================================================

\timing on

-- ── Funcoes DV check ──
-- IMMUTABLE: planner pode cachear chamadas. Usadas no WHERE de UPDATE 2.
-- Validam algoritmo modulo 11 (oficial RFB) para CPF (11 dig) e CNPJ (14 dig).
-- Rejeitam strings vazias, com chars nao-numericos, ou todos digitos iguais.

CREATE OR REPLACE FUNCTION is_valid_cpf(doc TEXT) RETURNS BOOLEAN AS $$
DECLARE
    d INT[];
    i INT;
    sum1 INT := 0;
    sum2 INT := 0;
    dv1 INT;
    dv2 INT;
    all_same BOOLEAN;
BEGIN
    -- Tamanho exato 11 + so digitos
    IF doc IS NULL OR LENGTH(doc) <> 11 OR doc !~ '^[0-9]{11}$' THEN
        RETURN FALSE;
    END IF;

    -- Array de digitos (1-indexed em PG)
    FOR i IN 1..11 LOOP
        d[i] := SUBSTRING(doc FROM i FOR 1)::INT;
    END LOOP;

    -- Rejeita sequencias triviais (000000000-00, 111111111-11, etc — DV passa
    -- matematicamente mas Receita marca como invalidos).
    all_same := TRUE;
    FOR i IN 2..11 LOOP
        IF d[i] <> d[1] THEN
            all_same := FALSE;
            EXIT;
        END IF;
    END LOOP;
    IF all_same THEN RETURN FALSE; END IF;

    -- DV1: sum(d[i] * (10 - (i-1))) for i in 1..9 = sum(d[i] * (11-i))
    FOR i IN 1..9 LOOP
        sum1 := sum1 + d[i] * (11 - i);
    END LOOP;
    dv1 := 11 - (sum1 % 11);
    IF dv1 >= 10 THEN dv1 := 0; END IF;
    IF dv1 <> d[10] THEN RETURN FALSE; END IF;

    -- DV2: sum(d[i] * (11-i)) for i in 1..10, com pesos shiftados
    FOR i IN 1..10 LOOP
        sum2 := sum2 + d[i] * (12 - i);
    END LOOP;
    dv2 := 11 - (sum2 % 11);
    IF dv2 >= 10 THEN dv2 := 0; END IF;

    RETURN dv2 = d[11];
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;


CREATE OR REPLACE FUNCTION is_valid_cnpj(doc TEXT) RETURNS BOOLEAN AS $$
DECLARE
    d INT[];
    i INT;
    sum1 INT := 0;
    sum2 INT := 0;
    dv1 INT;
    dv2 INT;
    pesos1 INT[] := ARRAY[5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    pesos2 INT[] := ARRAY[6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    all_same BOOLEAN;
BEGIN
    -- Tamanho exato 14 + so digitos
    IF doc IS NULL OR LENGTH(doc) <> 14 OR doc !~ '^[0-9]{14}$' THEN
        RETURN FALSE;
    END IF;

    -- Array de digitos
    FOR i IN 1..14 LOOP
        d[i] := SUBSTRING(doc FROM i FOR 1)::INT;
    END LOOP;

    -- Rejeita sequencias triviais
    all_same := TRUE;
    FOR i IN 2..14 LOOP
        IF d[i] <> d[1] THEN
            all_same := FALSE;
            EXIT;
        END IF;
    END LOOP;
    IF all_same THEN RETURN FALSE; END IF;

    -- DV1
    FOR i IN 1..12 LOOP
        sum1 := sum1 + d[i] * pesos1[i];
    END LOOP;
    dv1 := 11 - (sum1 % 11);
    IF dv1 >= 10 THEN dv1 := 0; END IF;
    IF dv1 <> d[13] THEN RETURN FALSE; END IF;

    -- DV2
    FOR i IN 1..13 LOOP
        sum2 := sum2 + d[i] * pesos2[i];
    END LOOP;
    dv2 := 11 - (sum2 % 11);
    IF dv2 >= 10 THEN dv2 := 0; END IF;

    RETURN dv2 = d[14];
END;
$$ LANGUAGE plpgsql IMMUTABLE STRICT;


-- ── ADD COLUMN cpf_digitos em todas as tabelas afetadas ──
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
-- nao-RFB (CPF padded, MEI nao-sincronizado, CNPJ malformado, lixo).

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

-- ── UPDATE 2: extrair cpf_digitos quando doc nao eh CNPJ matematico ──
-- Discriminator:
--   - Se NOT is_valid_cnpj(doc): doc nao eh CNPJ valido → pode ser CPF padded.
--   - Se is_valid_cpf(SUBSTRING(doc FROM 4 FOR 11)): os 11 digitos apos os 3
--     iniciais sao CPF valido → confirmado CPF padded → extrair.
-- Garantia: MEIs e CNPJs reais nao-sincronizados em RFB (DV CNPJ valido)
-- NUNCA virem "CPFs sinteticos". Eles esperam RFB sync; ETL idempotente
-- retroativamente populara cnpj_basico via Fase 5/7 quando estabelecimento
-- for atualizado.
-- Idempotente: WHERE cpf_digitos IS NULL.

UPDATE tce_pb_despesa SET cpf_digitos = SUBSTRING(cpf_cnpj FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpf_cnpj) = 14
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpf_cnpj)
   AND NOT is_valid_cnpj(cpf_cnpj)
   AND is_valid_cpf(SUBSTRING(cpf_cnpj FROM 4 FOR 11));

UPDATE pb_pagamento SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor)
   AND NOT is_valid_cnpj(cpfcnpj_credor)
   AND is_valid_cpf(SUBSTRING(cpfcnpj_credor FROM 4 FOR 11));

UPDATE pb_empenho SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor)
   AND NOT is_valid_cnpj(cpfcnpj_credor)
   AND is_valid_cpf(SUBSTRING(cpfcnpj_credor FROM 4 FOR 11));

UPDATE pb_contrato SET cpf_digitos = SUBSTRING(cpfcnpj_contratado FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_contratado) = 14
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_contratado)
   AND NOT is_valid_cnpj(cpfcnpj_contratado)
   AND is_valid_cpf(SUBSTRING(cpfcnpj_contratado FROM 4 FOR 11));

UPDATE pb_saude SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor)
   AND NOT is_valid_cnpj(cpfcnpj_credor)
   AND is_valid_cpf(SUBSTRING(cpfcnpj_credor FROM 4 FOR 11));

UPDATE pb_convenio SET cpf_digitos = SUBSTRING(cnpj_convenente FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cnpj_convenente) = 14
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cnpj_convenente)
   AND NOT is_valid_cnpj(cnpj_convenente)
   AND is_valid_cpf(SUBSTRING(cnpj_convenente FROM 4 FOR 11));

UPDATE pb_liquidacao_despesa SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor)
   AND NOT is_valid_cnpj(cpfcnpj_credor)
   AND is_valid_cpf(SUBSTRING(cpfcnpj_credor FROM 4 FOR 11));

UPDATE pb_empenho_anulacao SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor)
   AND NOT is_valid_cnpj(cpfcnpj_credor)
   AND is_valid_cpf(SUBSTRING(cpfcnpj_credor FROM 4 FOR 11));

UPDATE pb_empenho_suplementacao SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor)
   AND NOT is_valid_cnpj(cpfcnpj_credor)
   AND is_valid_cpf(SUBSTRING(cpfcnpj_credor FROM 4 FOR 11));

UPDATE pb_diaria SET cpf_digitos = SUBSTRING(cpfcnpj_credor FROM 4 FOR 11)
 WHERE cpf_digitos IS NULL
   AND LENGTH(cpfcnpj_credor) = 14
   AND NOT EXISTS (SELECT 1 FROM estabelecimento e WHERE e.cnpj_completo = cpfcnpj_credor)
   AND NOT is_valid_cnpj(cpfcnpj_credor)
   AND is_valid_cpf(SUBSTRING(cpfcnpj_credor FROM 4 FOR 11));

-- ── Indices parciais em cpf_digitos pra queries de PF ──
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

-- Report final
SELECT
  'tce_pb_despesa' AS tbl,
  COUNT(*) FILTER (WHERE cnpj_basico IS NOT NULL) AS com_basico_cnpj_real,
  COUNT(*) FILTER (WHERE cnpj_basico IS NULL AND cpf_digitos IS NOT NULL) AS com_cpf_pf_validado,
  COUNT(*) FILTER (WHERE cnpj_basico IS NULL AND cpf_digitos IS NULL AND LENGTH(cpf_cnpj) = 14) AS aguardando_rfb_sync
FROM tce_pb_despesa;
