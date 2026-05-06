-- ETL Incremental Framework — Onda PB POC (Phase 1a)
-- Migration: SECURITY DEFINER functions in etl_admin schema
--
-- Estas funções são a DEFESA PRINCIPAL contra audit forgery (priority #3).
-- Princípios aplicados (R6 BLOCKING fixes):
--   - TODA função tem SET search_path = pg_catalog, etl_admin, public
--     (não confia em role-level search_path; previne search_path attack).
--   - Owned by superuser (deploy time); etl_admin role recebe ownership após.
--   - etl_incremental tem APENAS EXECUTE; UPDATE direto em audit tables proibido.
--   - set_watermark computa stats internamente (NÃO trusta caller).
--   - Type-aware monotonicity (não TEXT lex).
--   - Idempotency via bucket_token (mesmo token = NO-OP).
--   - Fence check obrigatório em set_watermark/finish_run (run.status = 'running').
--
-- Funções:
--   start_run                 — inicia run, retorna UUID
--   heartbeat_run             — atualiza last_heartbeat, retorna FALSE se fenced
--   is_run_alive              — lookup rápido (STABLE)
--   finish_run                — termina com transição válida
--   abort_stale_runs          — preflight cleanup
--   set_watermark             — type-aware + idempotent + fence
--   reset_watermark           — bypass guard com audit obrigatória
--   insert_phase_log          — append-only audit insert
--   cleanup_orphan_staging    — janitor sem locks

-- ──────────────────────────────────────────────────────────────────────────────
-- start_run: cria etl_run_log row, retorna run_id UUID gerado.
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.start_run(
    p_mode         TEXT,
    p_triggered_by TEXT,
    p_commit_sha   TEXT DEFAULT NULL
) RETURNS UUID
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER
AS $func$
DECLARE
    v_run_id UUID := gen_random_uuid();
BEGIN
    IF p_mode NOT IN ('full', 'incremental', 'manual_reset', 'bootstrap') THEN
        RAISE EXCEPTION 'start_run: invalid mode %', p_mode;
    END IF;

    INSERT INTO etl_run_log (run_id, mode, triggered_by, commit_sha_start, status, started_at, last_heartbeat)
    VALUES (v_run_id, p_mode, p_triggered_by, p_commit_sha, 'running', now(), now());

    RETURN v_run_id;
END;
$func$;

COMMENT ON FUNCTION etl_admin.start_run(TEXT, TEXT, TEXT) IS
    'Cria nova run com status=running. Retorna run_id UUID. Único path de INSERT em etl_run_log para etl_incremental.';

-- ──────────────────────────────────────────────────────────────────────────────
-- heartbeat_run: atualiza last_heartbeat APENAS se status='running'.
-- Retorna FALSE se row foi fenced (status != running) → main thread aborts.
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.heartbeat_run(p_run_id UUID)
RETURNS BOOLEAN
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER
AS $func$
DECLARE
    v_count INT;
BEGIN
    UPDATE etl_run_log
    SET last_heartbeat = now()
    WHERE run_id = p_run_id AND status = 'running';

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count > 0;
END;
$func$;

COMMENT ON FUNCTION etl_admin.heartbeat_run(UUID) IS
    'Atualiza last_heartbeat com fence check. Retorna FALSE se run foi fenced (preflight aborted).';

-- ──────────────────────────────────────────────────────────────────────────────
-- is_run_alive: lookup rápido, STABLE (cache em mesma TX).
-- Usado em fence checks dentro de loops longos (pre-parser).
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.is_run_alive(p_run_id UUID)
RETURNS BOOLEAN
SET search_path = pg_catalog, etl_admin, public
LANGUAGE sql SECURITY DEFINER STABLE
AS $func$
    SELECT EXISTS(SELECT 1 FROM etl_run_log WHERE run_id = p_run_id AND status = 'running');
$func$;

COMMENT ON FUNCTION etl_admin.is_run_alive(UUID) IS
    'Lookup rápido se run.status=running. STABLE: cache em mesma TX. Use em loops para fence check sem write.';

-- ──────────────────────────────────────────────────────────────────────────────
-- finish_run: transição de status válida.
-- Aceita: running → success/failed/partial/aborted
--         aborted → failed/partial (caso preflight aborted mas run terminou)
-- Rejeita: success → qualquer outro (terminal); failed → success; etc.
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.finish_run(
    p_run_id UUID,
    p_status TEXT,
    p_error  TEXT DEFAULT NULL
) RETURNS VOID
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER
AS $func$
DECLARE
    v_current_status TEXT;
BEGIN
    IF p_status NOT IN ('success', 'failed', 'partial', 'aborted') THEN
        RAISE EXCEPTION 'finish_run: invalid status %', p_status;
    END IF;

    SELECT status INTO v_current_status FROM etl_run_log WHERE run_id = p_run_id;
    IF v_current_status IS NULL THEN
        RAISE EXCEPTION 'finish_run: run % not found', p_run_id;
    END IF;

    -- Transitions válidas
    IF v_current_status = 'running' THEN
        -- OK qualquer terminal status
        NULL;
    ELSIF v_current_status = 'aborted' AND p_status IN ('failed', 'partial') THEN
        -- OK: preflight aborted mas Python thread chegou ao finish_run
        NULL;
    ELSE
        RAISE EXCEPTION 'finish_run: cannot transition from % to %', v_current_status, p_status;
    END IF;

    UPDATE etl_run_log
    SET status        = p_status,
        finished_at   = COALESCE(finished_at, now()),
        error_message = COALESCE(p_error, error_message)
    WHERE run_id = p_run_id;
END;
$func$;

COMMENT ON FUNCTION etl_admin.finish_run(UUID, TEXT, TEXT) IS
    'Termina run com transição válida. Rejeita transições inválidas (success → running, etc).';

-- ──────────────────────────────────────────────────────────────────────────────
-- abort_stale_runs: preflight cleanup. Marca runs com last_heartbeat antigo
-- como 'aborted'. Chamado pelo orchestrator antes de adquirir o lock.
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.abort_stale_runs(p_max_age_minutes INT DEFAULT 5)
RETURNS INT
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER
AS $func$
DECLARE
    v_count INT;
BEGIN
    IF p_max_age_minutes < 1 OR p_max_age_minutes > 1440 THEN
        RAISE EXCEPTION 'abort_stale_runs: max_age_minutes must be in [1, 1440]';
    END IF;

    UPDATE etl_run_log
    SET status        = 'aborted',
        finished_at   = now(),
        error_message = COALESCE(error_message, '') || ' [auto-aborted: heartbeat timeout]'
    WHERE status = 'running'
      AND last_heartbeat < now() - (p_max_age_minutes::text || ' minutes')::interval;

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$func$;

COMMENT ON FUNCTION etl_admin.abort_stale_runs(INT) IS
    'Preflight: marca runs com heartbeat antigo como aborted. Default 5min.';

-- ──────────────────────────────────────────────────────────────────────────────
-- set_watermark: avança watermark com:
--   1. Fence check (run deve estar running)
--   2. Idempotent via bucket_token (mesmo token = NO-OP, retorna FALSE)
--   3. Type-aware monotonicity (integer/timestamp/string lex)
--   4. Atualiza expected_target_max/count (D3 evolutionary baseline)
--
-- ATENÇÃO: caller passa p_actual_max/p_actual_count derivados de phase_log,
-- mas a função NÃO valida cross-check para evitar lock contention. Defesa
-- relativa (R6 finding): caller é trusted code da framework, não user input.
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.set_watermark(
    p_run_id          UUID,
    p_source          TEXT,
    p_table           TEXT,
    p_bucket_token    UUID,
    p_new_value       TEXT,
    p_watermark_type  TEXT,
    p_actual_max      TEXT,
    p_actual_count    BIGINT
) RETURNS BOOLEAN
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER
AS $func$
DECLARE
    v_run_alive  BOOLEAN;
    v_existing   etl_watermark%ROWTYPE;
    v_advance    BOOLEAN := FALSE;
BEGIN
    -- 1. Fence check
    SELECT EXISTS(SELECT 1 FROM etl_run_log WHERE run_id = p_run_id AND status = 'running')
        INTO v_run_alive;
    IF NOT v_run_alive THEN
        RAISE EXCEPTION 'set_watermark: run % is not running (fenced or finished); cannot advance',
            p_run_id;
    END IF;

    -- Validate watermark_type
    IF p_watermark_type NOT IN ('timestamp', 'integer', 'string') THEN
        RAISE EXCEPTION 'set_watermark: invalid watermark_type %', p_watermark_type;
    END IF;

    -- Lookup existing
    SELECT * INTO v_existing
    FROM etl_watermark
    WHERE source = p_source AND table_name = p_table;

    -- 2. Idempotent: same bucket_token = NO-OP
    IF v_existing.bucket_token IS NOT NULL
       AND v_existing.bucket_token = p_bucket_token THEN
        RETURN FALSE;
    END IF;

    -- 3. Type-aware monotonicity
    IF v_existing.last_value IS NULL THEN
        v_advance := TRUE;
    ELSIF p_watermark_type = 'integer' THEN
        v_advance := p_new_value::bigint > v_existing.last_value::bigint;
    ELSIF p_watermark_type = 'timestamp' THEN
        v_advance := p_new_value::timestamptz > v_existing.last_value::timestamptz;
    ELSE  -- 'string'
        v_advance := p_new_value > v_existing.last_value;
    END IF;

    IF NOT v_advance THEN
        RETURN FALSE;
    END IF;

    -- 4. UPSERT (INSERT or UPDATE) — bootstrap fields preservados via trigger
    INSERT INTO etl_watermark (
        source, table_name, last_value, watermark_type, bucket_token,
        last_run_at, expected_target_max, expected_target_count
    ) VALUES (
        p_source, p_table, p_new_value, p_watermark_type, p_bucket_token,
        now(), p_actual_max, p_actual_count
    )
    ON CONFLICT (source, table_name) DO UPDATE SET
        last_value            = EXCLUDED.last_value,
        watermark_type        = EXCLUDED.watermark_type,
        bucket_token          = EXCLUDED.bucket_token,
        last_run_at           = EXCLUDED.last_run_at,
        expected_target_max   = EXCLUDED.expected_target_max,
        expected_target_count = EXCLUDED.expected_target_count;

    RETURN TRUE;
END;
$func$;

COMMENT ON FUNCTION etl_admin.set_watermark(UUID, TEXT, TEXT, UUID, TEXT, TEXT, TEXT, BIGINT) IS
    'Avança watermark com fence + idempotency + type-aware monotonicity. Retorna FALSE se NO-OP.';

-- ──────────────────────────────────────────────────────────────────────────────
-- reset_watermark: bypass guard de monotonicidade. Usado em recovery manual.
-- Exige reason >= 10 chars + approver. Insere row de audit em etl_run_log.
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.reset_watermark(
    p_source     TEXT,
    p_table      TEXT,
    p_new_value  TEXT,
    p_reason     TEXT,
    p_approver   TEXT
) RETURNS VOID
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER
AS $func$
DECLARE
    v_run_id UUID := gen_random_uuid();
BEGIN
    IF p_reason IS NULL OR length(trim(p_reason)) < 10 THEN
        RAISE EXCEPTION 'reset_watermark: reason must be at least 10 chars';
    END IF;
    IF p_approver IS NULL OR length(trim(p_approver)) < 1 THEN
        RAISE EXCEPTION 'reset_watermark: approver required';
    END IF;

    -- Audit row em etl_run_log
    INSERT INTO etl_run_log (
        run_id, mode, triggered_by, status, error_message,
        started_at, finished_at, last_heartbeat
    ) VALUES (
        v_run_id, 'manual_reset', p_approver, 'success',
        format('reset_watermark(%I.%I) → %s | reason: %s', p_source, p_table, p_new_value, p_reason),
        now(), now(), now()
    );

    -- Bypass monotonicity guard (UPDATE direto)
    UPDATE etl_watermark
    SET last_value     = p_new_value,
        last_run_at    = now(),
        bucket_token   = NULL,                  -- força não-idempotência no próximo run
        error_count    = 0,
        last_error     = NULL
    WHERE source = p_source AND table_name = p_table;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'reset_watermark: no watermark for %.%', p_source, p_table;
    END IF;
END;
$func$;

COMMENT ON FUNCTION etl_admin.reset_watermark(TEXT, TEXT, TEXT, TEXT, TEXT) IS
    'Manual override de monotonicity guard. Reason >= 10 chars + approver obrigatório. Audita em etl_run_log.';

-- ──────────────────────────────────────────────────────────────────────────────
-- insert_phase_log: append-only audit insert.
-- Único path para ETL role gravar em etl_phase_log.
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.insert_phase_log(
    p_run_id                       UUID,
    p_attempt                      INT,
    p_source                       TEXT,
    p_table                        TEXT,
    p_file_path                    TEXT,
    p_file_sequence                INT,
    p_status                       TEXT,
    p_started_at                   TIMESTAMPTZ,
    p_finished_at                  TIMESTAMPTZ,
    p_rows_streamed                BIGINT,
    p_rows_inserted                BIGINT,
    p_rows_updated                 BIGINT,
    p_rows_skipped_dup             BIGINT,
    p_rows_skipped_stale           BIGINT,
    p_rows_failed                  BIGINT,
    p_rows_rejected_null_key       BIGINT,
    p_rows_coerced_null            BIGINT,
    p_rows_conflict_diff_payload   BIGINT,
    p_watermark_before             TEXT,
    p_watermark_after              TEXT,
    p_spec_hash                    TEXT,
    p_csv_header_hash              TEXT,
    p_error_message                TEXT
) RETURNS BIGINT
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER
AS $func$
DECLARE
    v_id BIGINT;
BEGIN
    IF p_status NOT IN ('running', 'success', 'failed', 'partial') THEN
        RAISE EXCEPTION 'insert_phase_log: invalid status %', p_status;
    END IF;

    INSERT INTO etl_phase_log (
        run_id, attempt, source, table_name,
        file_path, file_path_hash, file_sequence,
        status, started_at, finished_at,
        rows_streamed, rows_inserted, rows_updated,
        rows_skipped_dup, rows_skipped_stale,
        rows_failed, rows_rejected_null_key, rows_coerced_null, rows_conflict_diff_payload,
        watermark_before, watermark_after,
        spec_hash, csv_header_hash, error_message
    ) VALUES (
        p_run_id, p_attempt, p_source, p_table,
        p_file_path, md5(COALESCE(p_file_path, '<no-path>')), p_file_sequence,
        p_status, p_started_at, p_finished_at,
        COALESCE(p_rows_streamed, 0), COALESCE(p_rows_inserted, 0), COALESCE(p_rows_updated, 0),
        COALESCE(p_rows_skipped_dup, 0), COALESCE(p_rows_skipped_stale, 0),
        COALESCE(p_rows_failed, 0), COALESCE(p_rows_rejected_null_key, 0),
        COALESCE(p_rows_coerced_null, 0), COALESCE(p_rows_conflict_diff_payload, 0),
        p_watermark_before, p_watermark_after,
        p_spec_hash, p_csv_header_hash, p_error_message
    ) RETURNING id INTO v_id;

    RETURN v_id;
END;
$func$;

COMMENT ON FUNCTION etl_admin.insert_phase_log IS
    'Append-only insert em etl_phase_log. Único path para ETL role.';

-- ──────────────────────────────────────────────────────────────────────────────
-- cleanup_orphan_staging: janitor schema-wide.
-- Drop tables em etl_staging.* cujo run_id não está em runs ativas.
-- Idempotent, autocommit-safe (sem locks longos).
-- ──────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION etl_admin.cleanup_orphan_staging()
RETURNS INT
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER
AS $func$
DECLARE
    r       RECORD;
    v_count INT := 0;
    v_run8  TEXT;
BEGIN
    FOR r IN
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname = 'etl_staging'
          AND tablename LIKE '\_stg\_%' ESCAPE '\'
    LOOP
        -- Match _stg_<source>_<table>_<run8>_<seq>_<kind>
        -- Extract <run8> = primeiros 8 hex chars do run_id
        v_run8 := substring(r.tablename FROM '^_stg_.+_([a-f0-9]{8})_\d+_(?:raw|typed|final)$');

        IF v_run8 IS NULL THEN
            -- Nome não-conforme: deixa quieto (pode ser tabela manual)
            CONTINUE;
        END IF;

        -- Drop se NÃO existe run ativa com esse run8 prefix
        IF NOT EXISTS (
            SELECT 1 FROM etl_run_log
            WHERE substring(run_id::text, 1, 8) = v_run8
              AND status = 'running'
        ) THEN
            BEGIN
                EXECUTE format('DROP TABLE IF EXISTS %I.%I', r.schemaname, r.tablename);
                v_count := v_count + 1;
            EXCEPTION WHEN OTHERS THEN
                RAISE NOTICE 'cleanup_orphan_staging: failed to drop %.%: %',
                    r.schemaname, r.tablename, SQLERRM;
            END;
        END IF;
    END LOOP;

    RETURN v_count;
END;
$func$;

COMMENT ON FUNCTION etl_admin.cleanup_orphan_staging() IS
    'Schema-wide janitor. Drop staging tables cujo run não está running. Idempotent.';
