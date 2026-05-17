-- SELECT body de _tmp_bf compartilhado entre:
--   1. sql/12_views.sql (CREATE TABLE _tmp_bf AS <este body>) — usado em
--      etl_phase=sql / etl_phase=all (full rebuild da MV).
--   2. etl/refresh_post_incremental.py (INSERT INTO _tmp_bf <este body>) —
--      usado em etl_phase=incremental apos carga incremental.
--
-- CRITICO: este body PRECISA bater EXATAMENTE com o de sql/12_views.sql.
-- Quando voce alterar este arquivo, tambem altere a query inline em
-- sql/12_views.sql:565-584 (e vice-versa). Drift entre os dois deixa
-- mv_servidor_pb_risco com dados inconsistentes dependendo do caminho
-- de refresh.
--
-- Por que nao DROP TABLE _tmp_bf?
--   PostgreSQL registra dependencia de metadata entre mv_servidor_pb_risco
--   e _tmp_bf (criada via SELECT sobre ela). DROP falha com:
--     "cannot drop table _tmp_bf because other objects depend on it"
--   Solucao: TRUNCATE + INSERT atomic em transacao (padrao
--   sql/15c_rebuild_tmp_for_servidor.sql).
--
-- Schema esperado em _tmp_bf (definido por sql/12_views.sql):
--   cpf_digitos_6 TEXT,
--   nome_upper    TEXT,
--   total_bf      NUMERIC

WITH vinculo AS (
    SELECT cpf_digitos_6, nome_upper,
           COALESCE(TO_CHAR(MIN(data_admissao), 'YYYYMM'), MIN(ano_mes)) AS inicio,
           MAX(ano_mes) AS fim
    FROM tce_pb_servidor
    WHERE cpf_digitos_6 IS NOT NULL AND nome_upper IS NOT NULL
      AND ano_mes >= '2022-01'
    GROUP BY cpf_digitos_6, nome_upper
)
SELECT srv.cpf_digitos_6,
       srv.nome_upper,
       SUM(bf.valor_parcela) AS total_bf
FROM mv_servidor_pb_base srv
JOIN vinculo v ON v.cpf_digitos_6 = srv.cpf_digitos_6 AND v.nome_upper = srv.nome_upper
JOIN bolsa_familia bf ON bf.cpf_digitos = srv.cpf_digitos_6
    AND UPPER(TRIM(bf.nm_favorecido)) = srv.nome_upper
    AND bf.mes_competencia >= v.inicio
    AND bf.mes_competencia <= v.fim
GROUP BY srv.cpf_digitos_6, srv.nome_upper;
