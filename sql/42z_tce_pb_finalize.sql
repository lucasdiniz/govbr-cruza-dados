-- ============================================================================
-- sql/42z_tce_pb_finalize.sql
--
-- Roda APOS:
--   1. sql/42_tce_pb_synthetic_nk.sql (cols, funcoes de hash, triggers)
--   2. python -m etl.refresh_post_incremental --source tce_pb --populate-only
--      (popula _nk_md5 em batches via psycopg2 autocommit — psql -c/-f wrappa
--      CALL em transacao implicita no PG 16; ver ADR-0010/ADR-0014.)
--
-- Aplicar via `psql -v ON_ERROR_STOP=1 -f sql/42z_*.sql` SEM
-- `--single-transaction` (CREATE INDEX CONCURRENTLY exige autocommit).
--
-- Idempotente: detecta INVALID index de runs falhos previos e refaz.
--
-- Dedupe esperado em prod (rows byte-a-byte identicas, true legacy dups):
--   despesa: 0 | servidor: ~23 | licitacao: ~93 | receita: 0
-- (DELETE inline em DO-block, statement unico — sem CALL/COMMIT-em-PROCEDURE,
--  evita o quirk PG16. Mantem a row de menor id.)
--
-- Ver ADR-0014.


-- ── Pre-flight: _nk_md5 populado em todas as 4 tabelas ──────────────────────
DO $$
DECLARE
    t text;
    n_null bigint;
BEGIN
    FOREACH t IN ARRAY ARRAY['tce_pb_despesa','tce_pb_servidor','tce_pb_licitacao','tce_pb_receita']
    LOOP
        EXECUTE format('SELECT count(*) FROM %I WHERE _nk_md5 IS NULL', t) INTO n_null;
        IF n_null > 0 THEN
            RAISE EXCEPTION
                '%: % rows com _nk_md5 NULL. Rode '
                '`python -m etl.refresh_post_incremental --source tce_pb --populate-only` '
                'antes (NAO psql -c "CALL" — PG16 quirk; ver ADR-0014).', t, n_null;
        END IF;
        RAISE NOTICE '%: 100%% das rows tem _nk_md5 populado.', t;
    END LOOP;
END $$;


-- ── Pre-drop INVALID indexes de runs CONCURRENTLY falhos previos ────────────
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.relname FROM pg_class c
    JOIN pg_index i ON c.oid = i.indexrelid
    WHERE c.relname IN (
      'ix_tce_pb_despesa_nk_md5','ix_tce_pb_servidor_nk_md5',
      'ix_tce_pb_licitacao_nk_md5','ix_tce_pb_receita_nk_md5'
    ) AND NOT i.indisvalid
  LOOP
    RAISE NOTICE 'Dropping INVALID index % de run previo', r.relname;
    EXECUTE format('DROP INDEX %I', r.relname);
  END LOOP;
END $$;


-- ── Dedupe por _nk_md5 (keep min(id)); skip se UNIQUE INDEX ja existe ────────
DO $$
DECLARE
    t text;
    idx text;
    n_deleted bigint;
    pair text[];
    pairs text[][] := ARRAY[
        ['tce_pb_despesa','ix_tce_pb_despesa_nk_md5'],
        ['tce_pb_servidor','ix_tce_pb_servidor_nk_md5'],
        ['tce_pb_licitacao','ix_tce_pb_licitacao_nk_md5'],
        ['tce_pb_receita','ix_tce_pb_receita_nk_md5']
    ];
    i int;
BEGIN
    FOR i IN 1 .. array_length(pairs, 1) LOOP
        t := pairs[i][1];
        idx := pairs[i][2];
        IF EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = idx) THEN
            RAISE NOTICE '% dedupe: skip (UNIQUE INDEX % ja garante invariante)', t, idx;
            CONTINUE;
        END IF;
        EXECUTE format($q$
            WITH dups AS (
                SELECT id, ROW_NUMBER() OVER (PARTITION BY _nk_md5 ORDER BY id) AS rn
                FROM %I WHERE _nk_md5 IS NOT NULL
            ),
            deleted AS (
                DELETE FROM %I WHERE id IN (SELECT id FROM dups WHERE rn > 1) RETURNING 1
            )
            SELECT count(*) FROM deleted
        $q$, t, t) INTO n_deleted;
        RAISE NOTICE '% dedupe: % rows deletadas (mantida a mais antiga por _nk_md5)', t, n_deleted;
    END LOOP;
END $$;


-- ── UNIQUE INDEX CONCURRENTLY (1 por statement, fora de transacao) ───────────
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_tce_pb_despesa_nk_md5
  ON tce_pb_despesa (_nk_md5);
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_tce_pb_servidor_nk_md5
  ON tce_pb_servidor (_nk_md5);
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_tce_pb_licitacao_nk_md5
  ON tce_pb_licitacao (_nk_md5);
CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS ix_tce_pb_receita_nk_md5
  ON tce_pb_receita (_nk_md5);


-- ── Validacao: todos os 4 indexes existem e estao VALID ─────────────────────
DO $$
DECLARE bad int;
BEGIN
  SELECT count(*) INTO bad FROM pg_class c
  JOIN pg_index i ON c.oid = i.indexrelid
  WHERE c.relname LIKE 'ix_tce_pb_%_nk_md5' AND NOT i.indisvalid;
  IF bad > 0 THEN
    RAISE EXCEPTION '% index(es) _nk_md5 INVALID; investigue duplicatas antes de re-rodar', bad;
  END IF;

  IF (SELECT count(*) FROM pg_indexes WHERE indexname LIKE 'ix_tce_pb_%_nk_md5') < 4 THEN
    RAISE EXCEPTION 'Esperado 4 indexes ix_tce_pb_*_nk_md5; algum CREATE CONCURRENTLY falhou.';
  END IF;
  RAISE NOTICE 'Todos os 4 UNIQUE INDEX _nk_md5 validos. Pronto para upsert via synthetic NK.';
END $$;
