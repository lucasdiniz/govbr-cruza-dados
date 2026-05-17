-- ============================================================================
-- sql/41z_bolsa_familia_finalize.sql
--
-- Roda APOS:
--   1. sql/41_bolsa_familia_incremental.sql (cria cols, trigger, procedure)
--   2. psql -c "CALL etl_admin.populate_nk_md5_bolsa_familia(100000);"
--      (popula _nk_md5 em batches — precisa rodar em comando separado para
--      evitar problema de COMMIT-em-PROCEDURE com psql -f -v ON_ERROR_STOP)
--
-- Aplicar via `psql -v ON_ERROR_STOP=1 -f sql/41z_*.sql` SEM
-- `--single-transaction` (CREATE INDEX CONCURRENTLY exige autocommit).
--
-- Idempotente: detecta INVALID indexes de runs falhos previos e refaz.
-- Ver ADR-0009.


-- ============================================================================
-- 4. Pre-flight: confirmar que _nk_md5 esta populada
-- ============================================================================
DO $$
DECLARE
    n_null BIGINT;
BEGIN
    SELECT count(*) INTO n_null FROM bolsa_familia WHERE _nk_md5 IS NULL;
    IF n_null > 0 THEN
        RAISE EXCEPTION
            'bolsa_familia: % rows com _nk_md5 NULL. '
            'Rode `psql -c "CALL etl_admin.populate_nk_md5_bolsa_familia(100000);"` '
            'antes de continuar.', n_null;
    END IF;
    RAISE NOTICE 'bolsa_familia: 100%% das rows tem _nk_md5 populado.';
END $$;


-- ============================================================================
-- 5. Pre-drop INVALID index de runs CONCURRENTLY falhos previos
-- ============================================================================
-- Idempotent + self-healing (padrao sql/35d). Tambem dropa index VALID se
-- estava criado prematuramente (sql/41 anterior podia ter criado antes do
-- populate completar; UNIQUE OK com NULLs mas precisa ser recriado para
-- validar duplicatas reais).
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.relname, i.indisvalid FROM pg_class c
    JOIN pg_index i ON c.oid = i.indexrelid
    WHERE c.relname = 'ix_bolsa_familia_nk_md5'
  LOOP
    IF NOT r.indisvalid THEN
      RAISE NOTICE 'Dropping INVALID index %', r.relname;
      EXECUTE format('DROP INDEX %I', r.relname);
    END IF;
  END LOOP;
END $$;


-- ============================================================================
-- 6. Dedupe rows com mesmo _nk_md5 (necessario antes do UNIQUE INDEX)
-- ============================================================================
-- Empirical: 9 grupos com 22 rows exatamente iguais detectados em prod
-- local + VM. Sao true duplicates do ETL classico legacy (TRUNCATE-and-
-- reload, sem dedupe). Mantemos a row com MENOR id (mais antiga).
-- Padrao sql/35c_pb_extras_synthetic_nk_dedupe.sql.

DO $$
DECLARE
    n_deleted BIGINT;
BEGIN
    WITH dups AS (
        SELECT id, _nk_md5,
               ROW_NUMBER() OVER (PARTITION BY _nk_md5 ORDER BY id) AS rn
        FROM bolsa_familia
        WHERE _nk_md5 IS NOT NULL
    ),
    deleted AS (
        DELETE FROM bolsa_familia
        WHERE id IN (SELECT id FROM dups WHERE rn > 1)
        RETURNING 1
    )
    SELECT count(*) INTO n_deleted FROM deleted;

    RAISE NOTICE 'bolsa_familia dedupe: % rows deletadas (mantidas a mais antiga por _nk_md5)', n_deleted;
END $$;


-- ============================================================================
-- 7. UNIQUE INDEX para upsert (ix_bolsa_familia_nk_md5)
-- ============================================================================
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_bolsa_familia_nk_md5
ON bolsa_familia (_nk_md5);


-- ============================================================================
-- 8. Validacao: index criado e VALID
-- ============================================================================
DO $$
DECLARE
    is_invalid BOOLEAN;
BEGIN
    SELECT NOT pg_index.indisvalid INTO is_invalid
    FROM pg_class
    JOIN pg_index ON pg_class.oid = pg_index.indexrelid
    WHERE pg_class.relname = 'ix_bolsa_familia_nk_md5';

    IF is_invalid IS NULL THEN
        RAISE EXCEPTION 'ix_bolsa_familia_nk_md5 NAO existe — CREATE CONCURRENTLY falhou.';
    ELSIF is_invalid THEN
        RAISE EXCEPTION
            'ix_bolsa_familia_nk_md5 esta INVALID. '
            'Drop e recrie apos investigar (ver docs/ops.md).';
    ELSE
        RAISE NOTICE 'ix_bolsa_familia_nk_md5 valido. Pronto para upsert via synthetic NK.';
    END IF;
END $$;
