-- ETL Incremental Framework — Onda PB POC (Phase 1a)
-- Migration: etl_phase_log
--
-- Tabela de tracking por arquivo dentro de uma run.
-- Granularidade: 1 arquivo = 1 phase = 1 invocação de _incremental_load.
-- Stats agregadas (rows_inserted/updated/failed/coerced) ficam aqui, não em
-- etl_watermark.rows_loaded (que foi removido como counter — D1 trade-off).
--
-- Princípios:
--   P3 AUDITÁVEL: append-only via etl_admin.insert_phase_log SECURITY DEFINER;
--      ETL role só tem SELECT. Trigger imutabilidade em started_at, csv_header_hash.
--   FK ON DELETE NO ACTION (R6 BLOCKING fix): preserva audit mesmo se run_log
--      row for purgada. Run_log NUNCA deve ser deleted (apenas finished).
--   file_path_hash: md5 do file_path. file_path pode ser muito longo (deep ZIP
--      paths), btree teria tuple > 2700 bytes; hash limita.

CREATE TABLE IF NOT EXISTS etl_phase_log (
    id                          BIGSERIAL,
    run_id                      UUID NOT NULL,
    attempt                     INT NOT NULL DEFAULT 1,
    source                      TEXT NOT NULL,
    table_name                  TEXT NOT NULL,
    -- File identity
    file_path                   TEXT,                   -- pode ser longo
    file_path_hash              TEXT,                   -- md5(file_path) para uniqueness
    file_sequence               INT,                    -- ordem dentro do bucket
    -- Timing
    started_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at                 TIMESTAMPTZ,
    -- Status
    --   'running'  = ativa
    --   'success'  = OK, todos rows aplicados
    --   'failed'   = erro fatal pré-UPSERT
    --   'partial'  = teve rows_failed > 0 (target NÃO foi modificado, P6)
    status                      TEXT NOT NULL,
    -- Stats (R6 fix: derivar via SUM(etl_phase_log) é a fonte de verdade,
    -- não etl_watermark.rows_loaded)
    rows_streamed               BIGINT NOT NULL DEFAULT 0,  -- total lidas do CSV
    rows_inserted               BIGINT NOT NULL DEFAULT 0,
    rows_updated                BIGINT NOT NULL DEFAULT 0,
    rows_skipped_dup            BIGINT NOT NULL DEFAULT 0,  -- ON CONFLICT DO NOTHING hit
    rows_skipped_stale          BIGINT NOT NULL DEFAULT 0,  -- freshness predicate falso
    rows_failed                 BIGINT NOT NULL DEFAULT 0,  -- foram para DLQ
    rows_rejected_null_key      BIGINT NOT NULL DEFAULT 0,  -- NK NULL → DLQ
    rows_coerced_null           BIGINT NOT NULL DEFAULT 0,  -- D6 sentinel coerce
    rows_conflict_diff_payload  BIGINT NOT NULL DEFAULT 0,  -- UPSERT_DO_NOTHING + payload diff detected
    -- Watermark progression (audit trail)
    watermark_before            TEXT,
    watermark_after             TEXT,
    -- Drift detection
    spec_hash                   TEXT,                   -- LoaderSpec.spec_hash
    csv_header_hash             TEXT,                   -- sha256(header line)
    -- Error
    error_message               TEXT,
    PRIMARY KEY (id),
    -- Uniqueness por (run_id, source, table, file, attempt)
    UNIQUE (run_id, source, table_name, file_path_hash, attempt),
    -- FK ON DELETE NO ACTION (preserva audit)
    FOREIGN KEY (run_id) REFERENCES etl_run_log(run_id) ON DELETE NO ACTION,
    CHECK (status IN ('running', 'success', 'failed', 'partial')),
    CHECK (rows_streamed >= 0 AND rows_inserted >= 0 AND rows_updated >= 0
           AND rows_skipped_dup >= 0 AND rows_skipped_stale >= 0
           AND rows_failed >= 0 AND rows_rejected_null_key >= 0
           AND rows_coerced_null >= 0 AND rows_conflict_diff_payload >= 0),
    CHECK (attempt >= 1),
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);

COMMENT ON TABLE etl_phase_log IS
    'Stats por arquivo. Append-only via etl_admin.insert_phase_log. Source of truth para métricas (não etl_watermark).';
COMMENT ON COLUMN etl_phase_log.file_path_hash IS
    'md5(file_path) — usado em UNIQUE constraint para evitar btree tuple overflow (file_path pode ser muito longo).';
COMMENT ON COLUMN etl_phase_log.csv_header_hash IS
    'sha256 do header CSV. Mismatch retroativo entre runs sinaliza schema drift.';

CREATE INDEX IF NOT EXISTS idx_etl_phase_log_source
    ON etl_phase_log(source, table_name, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_etl_phase_log_failed
    ON etl_phase_log(status, started_at DESC)
    WHERE status IN ('failed', 'partial');

CREATE INDEX IF NOT EXISTS idx_etl_phase_log_run
    ON etl_phase_log(run_id);

-- ──────────────────────────────────────────────────────────────────────────────
-- Trigger: preserva imutabilidade de campos críticos APÓS insert.
--
-- Stats (rows_*) podem ser atualizadas por insert_phase_log? NÃO — append-only.
-- Mas finished_at e error_message podem ser atualizados por finish_run path?
-- NÃO — phase_log é uma row final por arquivo. Atualização permitida APENAS
-- pelo orchestrator via SECURITY DEFINER (futuro).
-- POC: bloqueamos UPDATE inteiro para garantir append-only invariante.
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.protect_phase_log_immutability()
RETURNS TRIGGER
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql AS
$func$
BEGIN
    -- started_at, csv_header_hash, file_path, file_path_hash, run_id são
    -- sempre imutáveis. Outros campos (finished_at, status, rows_*, error_message)
    -- podem ser atualizados em update_phase_log_finalize (futuro).
    -- POC: bloqueamos qualquer UPDATE direto (sem usar SECURITY DEFINER path).
    -- Trigger só bloqueia UPDATEs feitos por etl_incremental role (não etl_admin).
    IF current_user = 'etl_incremental' THEN
        RAISE EXCEPTION
            'etl_phase_log is append-only via etl_admin SECURITY DEFINER. Direct UPDATE forbidden.';
    END IF;

    -- Mesmo via etl_admin: started_at e csv_header_hash são imutáveis
    IF NEW.started_at IS DISTINCT FROM OLD.started_at THEN
        RAISE EXCEPTION 'etl_phase_log.started_at is immutable';
    END IF;
    IF OLD.csv_header_hash IS NOT NULL
       AND NEW.csv_header_hash IS DISTINCT FROM OLD.csv_header_hash THEN
        RAISE EXCEPTION 'etl_phase_log.csv_header_hash is immutable once set';
    END IF;
    IF NEW.run_id IS DISTINCT FROM OLD.run_id THEN
        RAISE EXCEPTION 'etl_phase_log.run_id is immutable';
    END IF;

    RETURN NEW;
END;
$func$;

DROP TRIGGER IF EXISTS etl_phase_log_protect_immutability ON etl_phase_log;
CREATE TRIGGER etl_phase_log_protect_immutability
    BEFORE UPDATE ON etl_phase_log
    FOR EACH ROW
    EXECUTE FUNCTION etl_admin.protect_phase_log_immutability();

-- DELETE também bloqueado para etl_incremental
CREATE OR REPLACE FUNCTION etl_admin.protect_phase_log_no_delete()
RETURNS TRIGGER
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql AS
$func$
BEGIN
    IF current_user = 'etl_incremental' THEN
        RAISE EXCEPTION 'etl_phase_log: DELETE forbidden for etl_incremental role';
    END IF;
    RETURN OLD;
END;
$func$;

DROP TRIGGER IF EXISTS etl_phase_log_protect_no_delete ON etl_phase_log;
CREATE TRIGGER etl_phase_log_protect_no_delete
    BEFORE DELETE ON etl_phase_log
    FOR EACH ROW
    EXECUTE FUNCTION etl_admin.protect_phase_log_no_delete();
