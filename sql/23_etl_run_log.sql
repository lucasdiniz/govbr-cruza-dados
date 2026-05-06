-- ETL Incremental Framework — Onda PB POC (Phase 1a)
-- Migration: etl_run_log
--
-- Tabela de tracking por execução do orchestrator (run).
-- Uma run pode processar múltiplos arquivos de múltiplas (source, table).
-- Cada arquivo gera uma row em etl_phase_log linkada via run_id.
--
-- Princípios:
--   P3 AUDITÁVEL: imutável após status terminal; só etl_admin via SECURITY
--      DEFINER pode mudar status. ETL role tem apenas SELECT (e INSERT em
--      etl_admin.start_run que é o único path para INSERT).
--   P4 ERROR RESILIENT: heartbeat permite preflight detectar runs zumbis;
--      auto-abort após N min sem heartbeat (controlled by orchestrator/preflight).
--   D7 HEARTBEAT FENCE: rowcount=0 em UPDATE WHERE status='running' ⇒ run foi
--      fenced, main thread aborts.

CREATE TABLE IF NOT EXISTS etl_run_log (
    run_id           UUID PRIMARY KEY,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at      TIMESTAMPTZ,
    last_heartbeat   TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- Run mode
    --   'full'         = legacy full-reload (DROP+recreate)
    --   'incremental'  = framework incremental (não-destrutivo)
    --   'bootstrap'    = bootstrap watermark (manual)
    --   'manual_reset' = etl_admin.reset_watermark log entry
    mode             TEXT NOT NULL,
    triggered_by     TEXT,                   -- 'gha:run_id', 'cli:user', etc
    -- Status
    --   'pending'  = enfileirada, ainda não rodando (futuro: queue)
    --   'running'  = ativa, heartbeat válido
    --   'success'  = terminou OK
    --   'failed'   = erro fatal
    --   'partial'  = alguns arquivos OK, outros falharam
    --   'aborted'  = preflight auto-abort ou manual abort
    status           TEXT NOT NULL,
    error_message    TEXT,
    -- Deploy correlation (set by GHA deploy step, NÃO pelo ETL)
    commit_sha_start TEXT,
    commit_sha_end   TEXT,
    -- Free-form notes (full_reload_detected, fenced, etc)
    notes            TEXT,
    CHECK (mode IN ('full', 'incremental', 'manual_reset', 'bootstrap')),
    CHECK (status IN ('pending', 'running', 'success', 'failed', 'partial', 'aborted')),
    -- Sanity: finished_at >= started_at quando setado
    CHECK (finished_at IS NULL OR finished_at >= started_at),
    -- last_heartbeat sanity
    CHECK (last_heartbeat >= started_at)
);

COMMENT ON TABLE etl_run_log IS
    'Cabeçalho de cada execução do ETL incremental. Status transitions controladas por etl_admin.finish_run. Plan v7 P3.';
COMMENT ON COLUMN etl_run_log.last_heartbeat IS
    'Atualizado a cada 30s pelo heartbeat thread daemon. Preflight aborta runs com last_heartbeat > 5min.';
COMMENT ON COLUMN etl_run_log.commit_sha_start IS
    'Setado pelo deploy step (GHA), não pelo ETL Python. Permite correlacionar run com release.';

-- Index parcial para preflight rápido (varredura de runs zumbis)
CREATE INDEX IF NOT EXISTS idx_etl_run_log_running ON etl_run_log(last_heartbeat)
    WHERE status = 'running';

-- Index para queries históricas por mode/status
CREATE INDEX IF NOT EXISTS idx_etl_run_log_mode_status_started
    ON etl_run_log(mode, status, started_at DESC);
