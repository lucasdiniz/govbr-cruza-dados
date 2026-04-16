-- mv_municipio_pb_mapa: metricas agregadas para o mapa coropletico PB
-- 5 camadas: risco composto, % irregulares, % sem licitacao, HHI top-5, per capita
-- Depende de: mv_municipio_pb_risco, tce_pb_despesa, estabelecimento,
--             ceis_sancao, cnep_sancao, pgfn_divida

DROP MATERIALIZED VIEW IF EXISTS mv_municipio_pb_mapa CASCADE;

CREATE MATERIALIZED VIEW mv_municipio_pb_mapa AS
WITH
-- CNPJs irregulares (uniao: sancionado vigente + PGFN + inativo RFB)
cnpj_irregular AS MATERIALIZED (
    SELECT DISTINCT cnpj_basico FROM (
        SELECT LEFT(cpf_cnpj_sancionado, 8) AS cnpj_basico
        FROM ceis_sancao
        WHERE LENGTH(cpf_cnpj_sancionado) = 14
          AND (dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE - INTERVAL '3 years')
        UNION ALL
        SELECT LEFT(cpf_cnpj_sancionado, 8)
        FROM cnep_sancao
        WHERE LENGTH(cpf_cnpj_sancionado) = 14
          AND (dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE - INTERVAL '3 years')
        UNION ALL
        SELECT LEFT(cpf_cnpj_norm, 8)
        FROM pgfn_divida
        WHERE LENGTH(cpf_cnpj_norm) = 14
        UNION ALL
        SELECT cnpj_basico
        FROM estabelecimento
        WHERE cnpj_ordem = '0001' AND situacao_cadastral != '2'
    ) u
),
-- Agregado (municipio, cnpj_basico) filtrando CPF/CNPJ collision via JOIN em estabelecimento
forn_mun AS MATERIALIZED (
    SELECT d.municipio, d.cnpj_basico,
           SUM(d.valor_pago) AS pago
    FROM tce_pb_despesa d
    JOIN estabelecimento est ON est.cnpj_completo = d.cpf_cnpj
    WHERE d.cnpj_basico IS NOT NULL
      AND d.ano >= 2022
      AND d.valor_pago > 0
    GROUP BY d.municipio, d.cnpj_basico
),
hhi AS (
    SELECT municipio,
           SUM(pago) AS total_pago_pj,
           ROUND(
             100.0 * SUM(pago) FILTER (WHERE rn <= 5) / NULLIF(SUM(pago), 0),
             1
           ) AS pct_top5
    FROM (
        SELECT municipio, pago,
               ROW_NUMBER() OVER (PARTITION BY municipio ORDER BY pago DESC) AS rn
        FROM forn_mun
    ) x
    GROUP BY municipio
),
irreg AS (
    SELECT f.municipio,
           SUM(f.pago) AS pago_irregular
    FROM forn_mun f
    JOIN cnpj_irregular i USING (cnpj_basico)
    GROUP BY f.municipio
)
SELECT
    r.municipio,
    r.risco_score,
    r.pct_sem_licitacao,
    r.total_pago,
    COALESCE(h.pct_top5, 0) AS pct_top5,
    ROUND(
      100.0 * COALESCE(i.pago_irregular, 0) / NULLIF(h.total_pago_pj, 0),
      1
    ) AS pct_irregulares,
    COALESCE(i.pago_irregular, 0) AS pago_irregular,
    COALESCE(h.total_pago_pj, 0) AS total_pago_pj
FROM mv_municipio_pb_risco r
LEFT JOIN hhi h ON h.municipio = r.municipio
LEFT JOIN irreg i ON i.municipio = r.municipio;

CREATE UNIQUE INDEX idx_mv_mun_mapa_municipio ON mv_municipio_pb_mapa(municipio);
