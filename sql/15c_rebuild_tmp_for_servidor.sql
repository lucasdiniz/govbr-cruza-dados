-- =============================================================================
-- sql/15c_rebuild_tmp_for_servidor.sql
-- =============================================================================
-- Rebuild atomico de _tmp_fornecedor_gov + _tmp_conflito (backing tables
-- de mv_servidor_pb_risco) pra propagar o fix de cnpj_basico contaminado
-- (aplicado em sql/15a) sem dropar a MV.
--
-- CONTEXTO:
-- mv_servidor_pb_risco depende de 5 tabelas auxiliares (_tmp_socio_empresas,
-- _tmp_fornecedor_gov, _tmp_conflito, _tmp_bf, _tmp_duplo). PostgreSQL registra
-- dependencia de metadata: nao da pra DROP essas tabelas sem CASCADE (que
-- dropa a MV). Mas TRUNCATE + INSERT preserva a dependencia.
--
-- Das 5 tabelas:
--   - _tmp_socio_empresas: lê socio (RFB, 100% PJ). Sem contaminacao. SKIP.
--   - _tmp_fornecedor_gov: lê tce_pb_despesa via cnpj_basico. CONTAMINADA.
--   - _tmp_conflito: lê _tmp_d_agg (de tce_pb_despesa). CONTAMINADA.
--   - _tmp_bf: lê bolsa_familia. Sem cnpj_basico. SKIP.
--   - _tmp_duplo: lê tce_pb_servidor + siape. Sem cnpj_basico. SKIP.
--
-- ESTRATEGIA:
-- 1. DROP+CREATE _tmp_d_agg e _tmp_se_unnest (auxiliares temporarias, sem
--    deps de MV — DROP normal funciona).
-- 2. TRUNCATE + INSERT em _tmp_fornecedor_gov e _tmp_conflito (preservando
--    dependencia com mv_servidor_pb_risco).
-- 3. ANALYZE pra planner ter stats frescas.
-- 4. Cleanup _tmp_d_agg + _tmp_se_unnest.
-- 5. Tudo em transacao atomica.
--
-- IMPORTANTE: este script duplica logica de sql/12_views.sql:495-561.
-- Se aquela secao mudar, ATUALIZE este script tambem (drift = bug
-- silencioso na MV). Em PR futura, refatorar pra extrair fragmento SQL
-- compartilhado.
--
-- LOCK IMPACT:
--   - TRUNCATE em _tmp_fornecedor_gov/_tmp_conflito: ACCESS EXCLUSIVE.
--     Mas web nao consulta essas tabelas direto (so mv_servidor_pb_risco
--     que e' snapshot independente). Trafego nao impactado.
--   - mv_servidor_pb_risco continua servindo dados velhos durante a
--     transacao. REFRESH CONCURRENTLY posterior promove dados novos.
--
-- TEMPO ESTIMADO (B4): 5-15 min. Maior parte em _tmp_d_agg scan
-- (~16M rows de tce_pb_despesa).
--
-- IDEMPOTENTE: pode rodar varias vezes.
--
-- USO:
--   psql -d govbr -f sql/15c_rebuild_tmp_for_servidor.sql
--   ou via workflow: deploy.yml step que roda antes de refresh de
--   mv_servidor_pb_risco
-- =============================================================================

\timing on

BEGIN;

-- ── 1. _tmp_d_agg: pre-agrega tce_pb_despesa por (cnpj_basico, municipio) ──
-- Sem deps de MV — DROP+CREATE normal. cnpj_basico IS NOT NULL filtra rows
-- contaminadas (apos fix em 15a).
DROP TABLE IF EXISTS _tmp_d_agg;
CREATE TABLE _tmp_d_agg AS
SELECT cnpj_basico, municipio, SUM(valor_pago) AS total_pago
FROM tce_pb_despesa
WHERE valor_pago > 0
  AND municipio IS NOT NULL
  AND cnpj_basico IS NOT NULL  -- filtra contaminacao por CPF padded
GROUP BY cnpj_basico, municipio;

ANALYZE _tmp_d_agg;

-- ── 2. _tmp_se_unnest: expande arrays de _tmp_socio_empresas ──
-- Sem deps de MV. Reusa _tmp_socio_empresas existente (lê socio do RFB, safe).
DROP TABLE IF EXISTS _tmp_se_unnest;
CREATE TABLE _tmp_se_unnest AS
SELECT se.cpf_digitos_6, se.nome_upper,
       m AS municipio, cnpj.cnpj_basico
FROM _tmp_socio_empresas se
JOIN mv_servidor_pb_base srv ON srv.cpf_digitos_6 = se.cpf_digitos_6
    AND srv.nome_upper = se.nome_upper
CROSS JOIN LATERAL unnest(se.cnpjs) AS cnpj(cnpj_basico)
CROSS JOIN LATERAL unnest(srv.municipios) AS m;

ANALYZE _tmp_se_unnest;

-- ── 3. _tmp_conflito: TRUNCATE + INSERT (preserva dep de mv_servidor_pb_risco) ──
-- Antes do TRUNCATE, garante que a estrutura e' a mesma da definicao original.
-- Se a definicao em sql/12_views.sql:549-556 mudar, atualize aqui tambem.
TRUNCATE TABLE _tmp_conflito;
INSERT INTO _tmp_conflito (cpf_digitos_6, nome_upper, qtd_conflitos, total_conflito)
SELECT u.cpf_digitos_6, u.nome_upper,
       COUNT(DISTINCT d.cnpj_basico) AS qtd_conflitos,
       SUM(d.total_pago) AS total_conflito
FROM _tmp_se_unnest u
JOIN _tmp_d_agg d ON d.cnpj_basico = u.cnpj_basico
    AND d.municipio = u.municipio
GROUP BY u.cpf_digitos_6, u.nome_upper;

ANALYZE _tmp_conflito;

-- ── 4. _tmp_fornecedor_gov: TRUNCATE + INSERT ──
-- Definicao original em sql/12_views.sql:497-501.
TRUNCATE TABLE _tmp_fornecedor_gov;
INSERT INTO _tmp_fornecedor_gov (cpf_digitos_6, nome_upper)
SELECT DISTINCT se.cpf_digitos_6, se.nome_upper
FROM _tmp_socio_empresas se,
     LATERAL unnest(se.cnpjs) AS cnpj(cnpj_basico)
JOIN tce_pb_despesa d ON d.cnpj_basico = cnpj.cnpj_basico AND d.valor_pago > 0;

ANALYZE _tmp_fornecedor_gov;

-- ── 5. Cleanup tabelas temporarias auxiliares ──
DROP TABLE _tmp_d_agg;
DROP TABLE _tmp_se_unnest;

COMMIT;

-- Report
SELECT 'rebuild complete' AS status,
       (SELECT COUNT(*) FROM _tmp_fornecedor_gov) AS fornecedor_gov_rows,
       (SELECT COUNT(*) FROM _tmp_conflito) AS conflito_rows;
