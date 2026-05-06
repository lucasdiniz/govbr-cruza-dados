-- Views read-only para observabilidade do ETL incremental
-- Permite operadores verem status sem queries ad-hoc.

-- ── v_etl_status: 1 row per (source, table) com último estado ────────
CREATE OR REPLACE VIEW v_etl_status AS
SELECT
    w.source,
    w.table_name,
    w.last_value AS watermark,
    w.watermark_type,
    w.last_run_at,
    w.bucket_token,
    w.bootstrap_target_count,
    w.expected_target_count,
    w.error_count,
    w.last_error,
    -- Last run from phase_log
    pl.last_run_status,
    pl.last_run_started_at,
    pl.last_run_finished_at,
    pl.last_run_inserted,
    pl.last_run_streamed,
    pl.last_run_failed,
    pl.last_run_rejected_null_key
FROM etl_watermark w
LEFT JOIN LATERAL (
    SELECT
        status AS last_run_status,
        started_at AS last_run_started_at,
        finished_at AS last_run_finished_at,
        rows_inserted AS last_run_inserted,
        rows_streamed AS last_run_streamed,
        rows_failed AS last_run_failed,
        rows_rejected_null_key AS last_run_rejected_null_key
    FROM etl_phase_log
    WHERE source = w.source AND table_name = w.table_name
    ORDER BY started_at DESC
    LIMIT 1
) pl ON TRUE
ORDER BY w.source, w.table_name;

COMMENT ON VIEW v_etl_status IS
    'Estado atual do ETL incremental por (source, table). 1 row per spec.';


-- ── v_etl_dlq_summary: distribuição de DLQ por (source, table, reason) ───
CREATE OR REPLACE VIEW v_etl_dlq_summary AS
SELECT
    source,
    table_name,
    reason,
    count(*) AS dlq_count,
    min(rejected_at) AS first_rejection,
    max(rejected_at) AS last_rejection,
    count(DISTINCT run_id) AS distinct_runs,
    count(DISTINCT file_path) AS distinct_files
FROM etl_rejected_rows
GROUP BY source, table_name, reason
ORDER BY source, table_name, count(*) DESC;

COMMENT ON VIEW v_etl_dlq_summary IS
    'Sumario do Dead Letter Queue por reason. Util para triagem operacional.';


-- ── v_etl_load_summary: rows carregados por bucket nas últimas N runs ────
CREATE OR REPLACE VIEW v_etl_load_summary AS
SELECT
    source,
    table_name,
    file_path,
    file_sequence,
    status,
    rows_streamed,
    rows_inserted,
    rows_updated,
    rows_skipped_dup,
    rows_failed,
    rows_rejected_null_key,
    rows_coerced_null,
    started_at,
    finished_at - started_at AS duration,
    error_message
FROM etl_phase_log
WHERE started_at > now() - INTERVAL '7 days'
ORDER BY started_at DESC
LIMIT 1000;

COMMENT ON VIEW v_etl_load_summary IS
    'Loads recentes (7 dias). Para análise de performance e errors.';


-- ── v_etl_run_summary: resumo de runs ────────────────────────────────
CREATE OR REPLACE VIEW v_etl_run_summary AS
SELECT
    r.run_id,
    r.mode,
    r.status,
    r.triggered_by,
    r.started_at,
    r.finished_at,
    r.finished_at - r.started_at AS duration,
    r.commit_sha_start,
    r.error_message,
    -- Aggregate phase log
    coalesce(p.n_buckets, 0) AS n_buckets,
    coalesce(p.success_buckets, 0) AS success_buckets,
    coalesce(p.partial_buckets, 0) AS partial_buckets,
    coalesce(p.failed_buckets, 0) AS failed_buckets,
    coalesce(p.total_inserted, 0) AS total_inserted,
    coalesce(p.total_streamed, 0) AS total_streamed
FROM etl_run_log r
LEFT JOIN LATERAL (
    SELECT
        count(*) AS n_buckets,
        count(*) FILTER (WHERE status='success') AS success_buckets,
        count(*) FILTER (WHERE status='partial') AS partial_buckets,
        count(*) FILTER (WHERE status='failed') AS failed_buckets,
        sum(rows_inserted) AS total_inserted,
        sum(rows_streamed) AS total_streamed
    FROM etl_phase_log WHERE run_id = r.run_id
) p ON TRUE
WHERE r.started_at > now() - INTERVAL '30 days'
ORDER BY r.started_at DESC
LIMIT 200;

COMMENT ON VIEW v_etl_run_summary IS
    'Runs ETL recentes (30 dias) com agregação de phase log. Util pra dashboard.';


-- Grants para etl_incremental ler as views
GRANT SELECT ON v_etl_status, v_etl_dlq_summary, v_etl_load_summary, v_etl_run_summary TO etl_incremental;
