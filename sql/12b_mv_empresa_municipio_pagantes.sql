-- ─────────────────────────────────────────────────────────────────────────
-- mv_empresa_municipio_pagantes
--
-- Materializa pares DISTINCT (cnpj_completo, municipio) onde a empresa
-- recebeu pagamentos > 0 em algum municipio PB. Substitui o GROUP BY
-- pesado em ~16M rows do tce_pb_despesa que era feito on-demand pelo
-- endpoint /sitemap-empresas-municipios-{n}.xml e o COUNT pelo
-- /sitemap.xml — esses davam timeout >30s no Google Search Console
-- pos-restart (cache em memoria limpo).
--
-- Tamanho estimado: ~775K rows. Refresh: ~1-2min em B4.
--
-- Indices:
--   - UNIQUE (cnpj_completo, municipio) pra REFRESH CONCURRENTLY
--   - (total_pago DESC) pra ORDER BY estavel da paginacao (sitemap shards)
-- ─────────────────────────────────────────────────────────────────────────

DROP MATERIALIZED VIEW IF EXISTS mv_empresa_municipio_pagantes CASCADE;

CREATE MATERIALIZED VIEW mv_empresa_municipio_pagantes AS
SELECT
    est.cnpj_basico || est.cnpj_ordem || est.cnpj_dv AS cnpj_completo,
    d.municipio,
    SUM(d.valor_pago) AS total_pago
FROM tce_pb_despesa d
JOIN mv_empresa_pb epb ON epb.cnpj_basico = d.cnpj_basico
JOIN estabelecimento est
    ON est.cnpj_basico = epb.cnpj_basico
   AND est.cnpj_ordem = '0001'
WHERE d.cnpj_basico IS NOT NULL
  AND d.municipio IS NOT NULL
  AND d.valor_pago > 0
GROUP BY est.cnpj_basico, est.cnpj_ordem, est.cnpj_dv, d.municipio;

CREATE UNIQUE INDEX idx_mv_empmunpag_cnpj_mun
    ON mv_empresa_municipio_pagantes (cnpj_completo, municipio);

CREATE INDEX idx_mv_empmunpag_total
    ON mv_empresa_municipio_pagantes (total_pago DESC NULLS LAST);

ANALYZE mv_empresa_municipio_pagantes;

-- Para refresh futuro (sem bloquear leituras):
--   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_empresa_municipio_pagantes;
