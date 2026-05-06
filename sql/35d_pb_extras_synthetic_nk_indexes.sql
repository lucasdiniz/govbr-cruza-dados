-- sql/35d_pb_extras_synthetic_nk_indexes.sql
--
-- Phase D: CREATE UNIQUE INDEX CONCURRENTLY em _nk_md5 para 7 tabelas.
--
-- CONCURRENTLY: não bloqueia INSERTs/UPDATEs/DELETEs durante criação. Demora
-- ~2-5x mais que CREATE INDEX comum, mas seguro para tabelas em uso.
--
-- IMPORTANT: cada CREATE INDEX CONCURRENTLY deve estar em sua própria transação
-- (não dentro de BEGIN/COMMIT explícito). Rode com `psql -f` (não com `-c "..."`)
-- para que psql trate cada statement separadamente.
--
-- PRÉ-REQUISITOS:
-- 1. sql/35a (coluna + triggers) ✓
-- 2. sql/35b (populate _nk_md5) ✓ todos os _nk_md5 NOT NULL
-- 3. sql/35c (dedupe) ✓ sem dups
--
-- Se sql/35c não rodou completamente, CREATE INDEX vai FALHAR com:
--   ERRO: não foi possível criar o índice único "ix_pb_X_nk_md5"
--   DETALHE: Chave (_nk_md5)=(...) está duplicada.
-- Nesse caso o índice fica INVALID; rode `DROP INDEX ix_pb_X_nk_md5;` e re-rode 35c.
--
-- IDEMPOTENT: IF NOT EXISTS evita erro se index já existe.

-- IDEMPOTENT + SELF-HEALING: pre-drop any INVALID index from a previous failed
-- CONCURRENTLY build before retrying. PG marks failed CONCURRENTLY indexes as
-- indisvalid=false but keeps the catalog entry, which would cause IF NOT EXISTS
-- to silently skip recreation, leaving the uniqueness guarantee absent.

DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.relname FROM pg_class c
    JOIN pg_index i ON c.oid = i.indexrelid
    WHERE c.relname IN (
      'ix_pb_liquidacao_desconto_nk_md5',
      'ix_pb_empenho_anulacao_nk_md5',
      'ix_pb_empenho_suplementacao_nk_md5',
      'ix_pb_diaria_nk_md5',
      'ix_pb_dotacao_nk_md5',
      'ix_pb_aditivo_contrato_nk_md5',
      'ix_pb_aditivo_convenio_nk_md5'
    ) AND NOT i.indisvalid
  LOOP
    RAISE NOTICE 'Dropping INVALID index % from prior failed run', r.relname;
    EXECUTE format('DROP INDEX %I', r.relname);
  END LOOP;
END $$;


CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_liquidacao_desconto_nk_md5
  ON pb_liquidacao_desconto (_nk_md5);

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_empenho_anulacao_nk_md5
  ON pb_empenho_anulacao (_nk_md5);

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_empenho_suplementacao_nk_md5
  ON pb_empenho_suplementacao (_nk_md5);

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_diaria_nk_md5
  ON pb_diaria (_nk_md5);

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_dotacao_nk_md5
  ON pb_dotacao (_nk_md5);

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_aditivo_contrato_nk_md5
  ON pb_aditivo_contrato (_nk_md5);

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_pb_aditivo_convenio_nk_md5
  ON pb_aditivo_convenio (_nk_md5);


-- Validation: assert all 7 indexes are VALID after creation. If any returns
-- false here, a uniqueness violation occurred (re-run sql/35c first).
DO $$
DECLARE bad int;
BEGIN
  SELECT count(*) INTO bad FROM pg_class c
  JOIN pg_index i ON c.oid = i.indexrelid
  WHERE c.relname LIKE 'ix_pb_%_nk_md5' AND NOT i.indisvalid;
  IF bad > 0 THEN
    RAISE EXCEPTION '% _nk_md5 index(es) are INVALID; check duplicates before retrying', bad;
  END IF;
END $$;
