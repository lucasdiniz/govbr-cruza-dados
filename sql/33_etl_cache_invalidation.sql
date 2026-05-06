-- Cache invalidation queue: hooks pro warm cache integrar com incremental ETL
--
-- Quando incremental load advance watermark com >0 rows inserted/updated,
-- enfileira invalidations para web_cache. Web warm pode consumir.
--
-- POC: cria tabela + hook em set_watermark. Web consumption fica pra próxima
-- iteração — operadores podem usar query SQL pra ver fila.

CREATE TABLE IF NOT EXISTS etl_cache_invalidation_queue (
    id           BIGSERIAL PRIMARY KEY,
    run_id       UUID NOT NULL,
    source       TEXT NOT NULL,
    table_name   TEXT NOT NULL,
    bucket_id    TEXT,
    rows_inserted BIGINT NOT NULL,
    rows_updated BIGINT NOT NULL,
    pattern      TEXT,                          -- 'PERFIL,KPI_INATIVAS' style hint pra warm_cache
    queued_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_etl_cache_invalidation_pending
ON etl_cache_invalidation_queue(queued_at) WHERE processed_at IS NULL;

COMMENT ON TABLE etl_cache_invalidation_queue IS
    'Fila de cache invalidations causadas por incremental load. Consumidor: web/warm_cache.py (próx iteração).';
COMMENT ON COLUMN etl_cache_invalidation_queue.pattern IS
    'Hint pra warm_cache: lista CSV de query_id prefixes/substrings (e.g., PERFIL,KPI). Vazio = invalidate all keys.';


-- View pra operadores ver o que está pendente
CREATE OR REPLACE VIEW v_etl_cache_pending AS
SELECT
    source, table_name,
    count(*) AS pending_count,
    sum(rows_inserted) AS total_inserted,
    min(queued_at) AS oldest_pending,
    string_agg(DISTINCT bucket_id, ',' ORDER BY bucket_id) AS buckets
FROM etl_cache_invalidation_queue
WHERE processed_at IS NULL
GROUP BY source, table_name;

COMMENT ON VIEW v_etl_cache_pending IS
    'Cache invalidations pendentes. Consumir via web/warm_cache.py.';


-- ── SECURITY DEFINER: enqueue_cache_invalidation ────────────────────
CREATE OR REPLACE FUNCTION etl_admin.enqueue_cache_invalidation(
    p_run_id UUID,
    p_source TEXT,
    p_table TEXT,
    p_bucket_id TEXT,
    p_rows_inserted BIGINT,
    p_rows_updated BIGINT,
    p_pattern TEXT DEFAULT NULL
) RETURNS BIGINT
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER AS
$func$
DECLARE
    v_id BIGINT;
BEGIN
    -- Skip se rows_inserted + rows_updated = 0 (no-op)
    IF (COALESCE(p_rows_inserted,0) + COALESCE(p_rows_updated,0)) = 0 THEN
        RETURN NULL;
    END IF;
    INSERT INTO etl_cache_invalidation_queue (
        run_id, source, table_name, bucket_id,
        rows_inserted, rows_updated, pattern
    ) VALUES (
        p_run_id, p_source, p_table, p_bucket_id,
        COALESCE(p_rows_inserted, 0), COALESCE(p_rows_updated, 0), p_pattern
    ) RETURNING id INTO v_id;
    RETURN v_id;
END;
$func$;

COMMENT ON FUNCTION etl_admin.enqueue_cache_invalidation IS
    'Enfileira invalidation no etl_cache_invalidation_queue. Skip se 0 rows changed.';


-- Mark processed (para web/warm_cache.py consumer)
CREATE OR REPLACE FUNCTION etl_admin.mark_cache_invalidation_processed(
    p_ids BIGINT[]
) RETURNS INT
SET search_path = pg_catalog, etl_admin, public
LANGUAGE plpgsql SECURITY DEFINER AS
$func$
DECLARE
    v_count INT;
BEGIN
    UPDATE etl_cache_invalidation_queue
    SET processed_at = now()
    WHERE id = ANY(p_ids) AND processed_at IS NULL;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END;
$func$;

COMMENT ON FUNCTION etl_admin.mark_cache_invalidation_processed IS
    'Marca invalidations como processed. Idempotent.';


-- Grants
GRANT SELECT ON etl_cache_invalidation_queue TO etl_incremental;
GRANT SELECT ON v_etl_cache_pending TO etl_incremental;
GRANT EXECUTE ON FUNCTION etl_admin.enqueue_cache_invalidation TO etl_incremental;
GRANT EXECUTE ON FUNCTION etl_admin.mark_cache_invalidation_processed TO etl_incremental;
