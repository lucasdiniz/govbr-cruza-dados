-- =============================================================================
-- sql/15b_add_unique_index_mv_q67.sql
-- =============================================================================
-- mv_q67_dated_pb foi criada via hotfix (PR #54) sem UNIQUE INDEX, o que impede
-- REFRESH MATERIALIZED VIEW CONCURRENTLY. Pra propagar o fix de CPF padded
-- (via fix em sql/15a_fix_cnpj_basico_contamination.sql) sem downtime, esta MV
-- precisa de UNIQUE INDEX.
--
-- Chave natural da MV: (municipio, ano, cnpj_basico). Como cnpj_basico pode ser
-- NULL apos o fix retroativo, usamos COALESCE para garantir unicidade.
--
-- Validacao previa: SELECT (municipio, ano, COALESCE(cnpj_basico, ''))
-- e unico em mv_q67_dated_pb hoje.
--
-- CREATE INDEX CONCURRENTLY: nao bloqueia leituras. Custo: 1 scan completo
-- da MV + write do indice. Estimativa em prod (B4): 2-5 min.
--
-- USO:
--   psql -d govbr -f sql/15b_add_unique_index_mv_q67.sql
--   ou via workflow: deploy.yml step que roda antes do refresh_mvs
-- =============================================================================

CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS idx_mv_q67_dated_unique
    ON mv_q67_dated_pb (municipio, ano, COALESCE(cnpj_basico, ''));
