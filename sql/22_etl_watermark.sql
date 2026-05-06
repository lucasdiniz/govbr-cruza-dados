-- ETL Incremental Framework — Onda PB POC (Phase 1a)
-- Migration: etl_watermark
--
-- Tabela de tracking do cursor (watermark) por (source, table_name).
-- Mantém DUAS baselines:
--   1. bootstrap_*: imutável, capturada uma única vez no bootstrap. Trigger
--      garante imutabilidade. Serve como "última baseline aprovada" + fallback.
--   2. expected_*: evolui após cada set_watermark sucesso. Usada em divergence
--      detection. Permite incremental append legítimo sem trigger false-positive
--      de "full reload detected" (R5/R6 BLOCKING fix).
--
-- bucket_token UUID = idempotency token determinístico (uuid5 do bucket_id).
-- Se mesmo token = NO-OP em set_watermark (idempotent across crash recovery).
--
-- Conformidade com princípios:
--   P1 NÃO-DESTRUTIVO: trigger BEFORE UPDATE protege bootstrap_*; bootstrapped_at
--   imutável; tentativa de UPDATE direto raise.
--   P2 SEPARAÇÃO: bucket_token + monotonic last_value (type-aware via
--      etl_admin.set_watermark) garante que full e incremental não corrompam.
--   P3 VALIDAÇÃO: target_schema_hash detecta DDL drift entre runs.
--   P5 SCHEMA DRIFT GUARD: target_schema_hash recalculado a cada run.
--   P6 ZERO TOLERANCE: watermark NUNCA avança em failure (controlado pelo
--      orchestrator via etl_admin.set_watermark fence check).

CREATE TABLE IF NOT EXISTS etl_watermark (
    source                 TEXT NOT NULL,
    table_name             TEXT NOT NULL,
    -- Cursor state
    last_value             TEXT,
    watermark_type         TEXT NOT NULL DEFAULT 'string',
    last_run_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Idempotency token: deterministic uuid5(namespace, source||table||bucket_id)
    -- Same token in set_watermark = NO-OP (handles crash between data commit and
    -- watermark commit).
    bucket_token           UUID,
    -- Error tracking
    error_count            INT NOT NULL DEFAULT 0,
    last_error             TEXT,
    -- Bootstrap baseline (immutable após primeiro INSERT — trigger enforce)
    bootstrap_target_max   TEXT,
    bootstrap_target_count BIGINT,
    bootstrapped_at        TIMESTAMPTZ,
    bootstrapped_by        TEXT,
    -- Evolutionary baseline (D3 — atualizada a cada set_watermark sucesso)
    expected_target_max    TEXT,
    expected_target_count  BIGINT,
    -- Schema fingerprint (P5 SCHEMA DRIFT GUARD)
    target_schema_hash     TEXT,
    PRIMARY KEY (source, table_name),
    CHECK (watermark_type IN ('timestamp', 'integer', 'string')),
    CHECK (error_count >= 0)
);

COMMENT ON TABLE etl_watermark IS
    'Cursor de incremental ETL por (source, table_name). bootstrap_* immutable, expected_* evolutiva. Veja plan v7 D3.';
COMMENT ON COLUMN etl_watermark.bucket_token IS
    'Idempotency token determinístico (uuid5 do bucket_id). Mesmo token em set_watermark = NO-OP.';
COMMENT ON COLUMN etl_watermark.bootstrap_target_max IS
    'Imutável após bootstrap. Reescrita exige etl_admin.rebootstrap_baseline (não implementado em POC).';
COMMENT ON COLUMN etl_watermark.expected_target_max IS
    'Evolutiva. Atualizada por etl_admin.set_watermark a cada bucket sucesso. Usada em divergence detection.';

-- ──────────────────────────────────────────────────────────────────────────────
-- Schema etl_admin: dono dos triggers/funções SECURITY DEFINER.
-- Criado aqui pois protect_bootstrap_fields trigger depende dele.
-- ──────────────────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS etl_admin;

-- ──────────────────────────────────────────────────────────────────────────────
-- Trigger: protege bootstrap_* fields contra UPDATE direto.
--
-- bootstrap_target_max/count e bootstrapped_at só podem ser setados em INSERT
-- (primeiro bootstrap). UPDATE que tente alterar = ERROR.
-- Fluxo legítimo de re-bootstrap usa etl_admin.rebootstrap_baseline (não em POC).
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.protect_bootstrap_fields()
RETURNS TRIGGER
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql AS
$func$
BEGIN
    -- bootstrap_target_max: imutável após primeiro INSERT
    IF OLD.bootstrap_target_max IS NOT NULL
       AND NEW.bootstrap_target_max IS DISTINCT FROM OLD.bootstrap_target_max THEN
        RAISE EXCEPTION
            'etl_watermark.bootstrap_target_max is immutable (was %, attempted %); use etl_admin.rebootstrap_baseline',
            OLD.bootstrap_target_max, NEW.bootstrap_target_max;
    END IF;

    -- bootstrap_target_count: imutável
    IF OLD.bootstrap_target_count IS NOT NULL
       AND NEW.bootstrap_target_count IS DISTINCT FROM OLD.bootstrap_target_count THEN
        RAISE EXCEPTION
            'etl_watermark.bootstrap_target_count is immutable (was %, attempted %)',
            OLD.bootstrap_target_count, NEW.bootstrap_target_count;
    END IF;

    -- bootstrapped_at: imutável
    IF OLD.bootstrapped_at IS NOT NULL
       AND NEW.bootstrapped_at IS DISTINCT FROM OLD.bootstrapped_at THEN
        RAISE EXCEPTION
            'etl_watermark.bootstrapped_at is immutable';
    END IF;

    -- bootstrapped_by: imutável
    IF OLD.bootstrapped_by IS NOT NULL
       AND NEW.bootstrapped_by IS DISTINCT FROM OLD.bootstrapped_by THEN
        RAISE EXCEPTION
            'etl_watermark.bootstrapped_by is immutable';
    END IF;

    RETURN NEW;
END;
$func$;

DROP TRIGGER IF EXISTS etl_watermark_protect_bootstrap ON etl_watermark;
CREATE TRIGGER etl_watermark_protect_bootstrap
    BEFORE UPDATE ON etl_watermark
    FOR EACH ROW
    EXECUTE FUNCTION etl_admin.protect_bootstrap_fields();
