-- ETL Incremental Framework — Onda PB POC (Phase 1a)
-- Migration: roles + grants
--
-- Defesa em camadas P1 NÃO-DESTRUTIVO. DB-level enforcement é a defesa primária
-- (não regex, não lint). Permissão negada pelo PG não é evadível.
--
-- Roles:
--   etl_admin        — owner das funções SECURITY DEFINER (NOLOGIN)
--   etl_incremental  — runtime do ETL (LOGIN, NOINHERIT)
--
-- Princípios:
--   - etl_incremental: SELECT/INSERT/UPDATE em targets PB; SEM DELETE/TRUNCATE/DROP
--   - etl_incremental: SELECT only em audit tables; INSERT só via etl_admin functions
--   - etl_incremental: CREATE só em etl_staging (não em public)
--   - etl_incremental: search_path locked
--   - etl_incremental: statement_timeout + lock_timeout

-- ──────────────────────────────────────────────────────────────────────────────
-- Roles
-- ──────────────────────────────────────────────────────────────────────────────

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etl_admin') THEN
        CREATE ROLE etl_admin NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'etl_incremental') THEN
        -- Senha vem via deploy time. Local dev usa 'etl_incremental_dev'.
        CREATE ROLE etl_incremental NOINHERIT LOGIN PASSWORD 'etl_incremental_dev';
    END IF;
END $$;

-- Schemas
GRANT USAGE ON SCHEMA public TO etl_incremental;
GRANT USAGE, CREATE ON SCHEMA etl_staging TO etl_incremental;
GRANT USAGE ON SCHEMA etl_admin TO etl_incremental;

-- CRÍTICO: REVOKE CREATE em public (defesa contra criar tables sombreando views)
REVOKE CREATE ON SCHEMA public FROM etl_incremental;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- ──────────────────────────────────────────────────────────────────────────────
-- Search path + timeouts (role-level defaults)
-- ──────────────────────────────────────────────────────────────────────────────
ALTER ROLE etl_incremental SET search_path = public, etl_staging, pg_catalog;
ALTER ROLE etl_incremental SET statement_timeout = '30min';
ALTER ROLE etl_incremental SET lock_timeout = '5min';

-- ──────────────────────────────────────────────────────────────────────────────
-- Targets POC: SELECT/INSERT/UPDATE only
-- DELETE, TRUNCATE, DROP não grantados — defesa primária P1.
-- ──────────────────────────────────────────────────────────────────────────────

-- TCE-PB
GRANT SELECT, INSERT, UPDATE ON
    public.tce_pb_despesa,
    public.tce_pb_servidor,
    public.tce_pb_licitacao,
    public.tce_pb_receita
TO etl_incremental;

-- Dados-PB (17 tables)
GRANT SELECT, INSERT, UPDATE ON
    public.pb_pagamento,
    public.pb_empenho,
    public.pb_contrato,
    public.pb_saude,
    public.pb_convenio,
    public.pb_pagamento_anulacao,
    public.pb_liquidacao_despesa,
    public.pb_liquidacao_desconto,
    public.pb_empenho_anulacao,
    public.pb_empenho_suplementacao,
    public.pb_dotacao,
    public.pb_liquidacao_cge,
    public.pb_aditivo_contrato,
    public.pb_aditivo_convenio,
    public.pb_diaria,
    public.pb_unidade_gestora
TO etl_incremental;

-- Novo Bolsa Familia (Portal da Transparencia) — ADR-0009
-- Snapshots mensais acumulativos via framework incremental.
-- SEM DELETE/TRUNCATE/DROP (mesmo principio P1 dos targets PB).
GRANT SELECT, INSERT, UPDATE ON
    public.bolsa_familia
TO etl_incremental;

-- Sequences (BIGSERIAL/SERIAL precisa USAGE para nextval)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO etl_incremental;

-- ──────────────────────────────────────────────────────────────────────────────
-- Audit tables
-- - SELECT only para queries de status (operadores)
-- - INSERT só via etl_admin SECURITY DEFINER functions
-- - UPDATE/DELETE NUNCA grantados em audit tables
-- ──────────────────────────────────────────────────────────────────────────────

GRANT SELECT ON
    etl_watermark,
    etl_run_log,
    etl_phase_log,
    etl_rejected_rows,
    etl_rejected_rows_default,
    etl_rejected_rows_tce_pb,
    etl_rejected_rows_dados_pb
TO etl_incremental;

-- DLQ: INSERT direto permitido (volume alto, justifica não passar por SECDEF)
-- Trigger protect_dlq_no_delete bloqueia DELETE para etl_incremental.
GRANT INSERT ON
    etl_rejected_rows,
    etl_rejected_rows_default,
    etl_rejected_rows_tce_pb,
    etl_rejected_rows_dados_pb
TO etl_incremental;

-- ──────────────────────────────────────────────────────────────────────────────
-- SECURITY DEFINER functions: EXECUTE
-- ──────────────────────────────────────────────────────────────────────────────

GRANT EXECUTE ON FUNCTION
    etl_admin.start_run(TEXT, TEXT, TEXT),
    etl_admin.heartbeat_run(UUID),
    etl_admin.is_run_alive(UUID),
    etl_admin.finish_run(UUID, TEXT, TEXT),
    etl_admin.abort_stale_runs(INT),
    etl_admin.set_watermark(UUID, TEXT, TEXT, UUID, TEXT, TEXT, TEXT, BIGINT),
    etl_admin.reset_watermark(TEXT, TEXT, TEXT, TEXT, TEXT),
    etl_admin.insert_phase_log(
        UUID, INT, TEXT, TEXT, TEXT, INT, TEXT,
        TIMESTAMPTZ, TIMESTAMPTZ,
        BIGINT, BIGINT, BIGINT, BIGINT, BIGINT,
        BIGINT, BIGINT, BIGINT, BIGINT,
        TEXT, TEXT, TEXT, TEXT, TEXT
    ),
    etl_admin.cleanup_orphan_staging()
TO etl_incremental;

-- ──────────────────────────────────────────────────────────────────────────────
-- Staging schema: tudo permitido (mas só dentro de etl_staging)
-- ──────────────────────────────────────────────────────────────────────────────

-- Default privileges para tabelas criadas pelo etl_incremental no etl_staging
ALTER DEFAULT PRIVILEGES FOR ROLE etl_incremental IN SCHEMA etl_staging
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO etl_incremental;

-- Note: etl_incremental criou as tabelas em etl_staging, então é dono delas.
-- Pode DROP suas próprias tabelas (correto — é o ciclo de vida).

-- ──────────────────────────────────────────────────────────────────────────────
-- etl_admin: deve poder dropar staging tables (janitor)
-- ──────────────────────────────────────────────────────────────────────────────

GRANT USAGE ON SCHEMA etl_staging TO etl_admin;
ALTER DEFAULT PRIVILEGES FOR ROLE etl_incremental IN SCHEMA etl_staging
    GRANT ALL ON TABLES TO etl_admin;

-- Lock conn precisa pg_advisory_lock — built-in, todo role tem EXECUTE por default
-- (não precisa grant explícito).

-- ──────────────────────────────────────────────────────────────────────────────
-- Diagnostic: dump grants para validation
-- ──────────────────────────────────────────────────────────────────────────────
-- Querying after migration:
--   SELECT grantee, privilege_type, table_name
--   FROM information_schema.role_table_grants
--   WHERE grantee = 'etl_incremental' ORDER BY table_name, privilege_type;
