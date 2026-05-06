-- ETL Incremental Framework — Onda PB POC (Phase 1a)
-- Migration: schema etl_staging
--
-- Schema dedicado para staging tables temporárias do incremental_load.
-- Defesa em camadas (P1 NÃO-DESTRUTIVO):
--   - etl_incremental tem CREATE/USAGE em etl_staging
--   - etl_incremental NÃO tem CREATE em public (REVOKE em sql/28_etl_role_grants.sql)
--   - Janitor (etl_admin.cleanup_orphan_staging) só toca em etl_staging.*
--   - Static check de CI: identifier interpolation em DDL de staging usa apenas
--     etl_staging schema
--
-- Convenção de nomes (D12 staging_name helper):
--   etl_staging._stg_<source>_<table>_<run_id_8chars>_<seq>_<kind>
--   onde kind ∈ {raw, typed, final}
--   Ex: etl_staging._stg_tce_pb_despesa_a1b2c3d4_1_raw

CREATE SCHEMA IF NOT EXISTS etl_staging;

COMMENT ON SCHEMA etl_staging IS
    'Staging tables temporárias do ETL incremental. etl_incremental tem CREATE só aqui (não em public).';
