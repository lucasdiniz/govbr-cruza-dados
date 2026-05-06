-- ETL Incremental Framework — Onda PB POC (Phase 1a)
-- Migration: etl_rejected_rows (DLQ)
--
-- Dead Letter Queue. Rows rejeitadas pelo pre-parser, type validation, NK NULL.
-- ESCRITA via dlq_conn em AUTOCOMMIT separada do main_conn (P6): garantida
-- persistência mesmo se main TX rollback.
--
-- LIST partitioning by source (R6 BLOCKING fix vs range-by-month):
--   - Range por month deixava retries cross-month duplicarem (snapshots mensais
--     reprocessados → DLQ inflava linearmente).
--   - List by source dedupe é cross-time WITHIN source — alinha com triagem
--     operacional (operadores investigam por fonte, não por mês).
--   - DEFAULT partition pega novos sources sem precisar redeploy.
--   - file_path/line_number NOT NULL para unique constraint funcionar (R6: PG
--     trata NULL como distinct, deixando dedup ineficaz com nullable cols).
--
-- Princípios:
--   P3 AUDITÁVEL: append-only via INSERT direto pelo etl_incremental role
--     (volume alto, justifica não usar SECURITY DEFINER aqui). DELETE proibido
--     via trigger.
--   P6 ZERO TOLERANCE: linha rejeitada DEVE persistir mesmo em rollback do
--     main_conn — por isso autocommit conn separada.
--   D4 R6 BLOCKING fix: list partition + NOT NULL columns para dedup eficaz.

CREATE TABLE IF NOT EXISTS etl_rejected_rows (
    id            BIGSERIAL,
    run_id        UUID NOT NULL,
    source        TEXT NOT NULL,
    table_name    TEXT NOT NULL,
    -- file_path NOT NULL com sentinel default para unique funcionar
    file_path     TEXT NOT NULL DEFAULT '<no-path>',
    -- line_number NOT NULL com sentinel -1 para errors sem line context (e.g.,
    -- file-level encoding error)
    line_number   BIGINT NOT NULL DEFAULT -1,
    raw_line      TEXT,
    raw_line_hash TEXT NOT NULL,                -- sha256(raw_line) — sempre setado
    -- Reason taxonomy:
    --   col_count_mismatch — pre-parser detectou contagem errada
    --   encoding_error     — UnicodeDecodeError em pre-parser
    --   unterminated_quote — RFC 4180 quoted field não fechado
    --   field_too_large    — max_field_size excedido
    --   type_validation    — cast falhou em staging_typed
    --   NK_NULL            — natural_key column é NULL após coerce
    --   header_drift       — csv_header_hash diferge do esperado
    reason        TEXT NOT NULL,
    rejected_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Composite PK incluindo source (partition key)
    PRIMARY KEY (source, id)
) PARTITION BY LIST (source);

COMMENT ON TABLE etl_rejected_rows IS
    'DLQ list-partitioned by source. Append-only autocommit. Veja plan v7 D4.';

-- DEFAULT partition (catch-all, evita INSERT failure se source novo for adicionado)
CREATE TABLE IF NOT EXISTS etl_rejected_rows_default
    PARTITION OF etl_rejected_rows DEFAULT;

-- POC partitions: tce_pb e dados_pb
CREATE TABLE IF NOT EXISTS etl_rejected_rows_tce_pb
    PARTITION OF etl_rejected_rows FOR VALUES IN ('tce_pb');

CREATE TABLE IF NOT EXISTS etl_rejected_rows_dados_pb
    PARTITION OF etl_rejected_rows FOR VALUES IN ('dados_pb');

-- ──────────────────────────────────────────────────────────────────────────────
-- Unique constraint: dedup cross-time within source.
-- Aplicado a TODAS partitions (PG 16+ propaga automaticamente em LIST partition
-- com chave incluída).
-- file_path e line_number são NOT NULL (sentinels), garantindo que ON CONFLICT
-- DO NOTHING funcione mesmo para errors sem contexto.
-- ──────────────────────────────────────────────────────────────────────────────
CREATE UNIQUE INDEX IF NOT EXISTS idx_etl_rejected_dedupe
    ON etl_rejected_rows (source, table_name, file_path, line_number, raw_line_hash);

-- Index para queries de triagem (sem partition pruning otimizado — fine pra POC)
CREATE INDEX IF NOT EXISTS idx_etl_rejected_run
    ON etl_rejected_rows (run_id, source);

CREATE INDEX IF NOT EXISTS idx_etl_rejected_recent
    ON etl_rejected_rows (rejected_at DESC);

-- ──────────────────────────────────────────────────────────────────────────────
-- Trigger: bloquear DELETE para etl_incremental role (DLQ append-only).
-- Operações de retention (drop partition) feitas por etl_admin via cron.
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.protect_dlq_no_delete()
RETURNS TRIGGER
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql AS
$func$
BEGIN
    IF current_user = 'etl_incremental' THEN
        RAISE EXCEPTION 'etl_rejected_rows: DELETE forbidden for etl_incremental role';
    END IF;
    RETURN OLD;
END;
$func$;

DROP TRIGGER IF EXISTS etl_rejected_default_no_delete ON etl_rejected_rows_default;
CREATE TRIGGER etl_rejected_default_no_delete
    BEFORE DELETE ON etl_rejected_rows_default
    FOR EACH ROW EXECUTE FUNCTION etl_admin.protect_dlq_no_delete();

DROP TRIGGER IF EXISTS etl_rejected_tce_pb_no_delete ON etl_rejected_rows_tce_pb;
CREATE TRIGGER etl_rejected_tce_pb_no_delete
    BEFORE DELETE ON etl_rejected_rows_tce_pb
    FOR EACH ROW EXECUTE FUNCTION etl_admin.protect_dlq_no_delete();

DROP TRIGGER IF EXISTS etl_rejected_dados_pb_no_delete ON etl_rejected_rows_dados_pb;
CREATE TRIGGER etl_rejected_dados_pb_no_delete
    BEFORE DELETE ON etl_rejected_rows_dados_pb
    FOR EACH ROW EXECUTE FUNCTION etl_admin.protect_dlq_no_delete();
