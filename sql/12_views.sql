-- =============================================================================
-- Materialized Views para govbr-cruza-dados
-- 6 MVs + 2 Views de risco
-- Pré-requisito: todas as fases ETL (1-8) + normalização (fase 14) completas
-- =============================================================================

-- Drop em ordem reversa de dependência
DROP VIEW IF EXISTS v_risk_score_pb CASCADE;
DROP VIEW IF EXISTS v_risk_score_empresa CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_rede_pb CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_empresa_pb CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_servidor_pb_risco CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_servidor_pb_base CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_municipio_pb_mapa CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_municipio_pb_risco CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_pessoa_pb CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_empresa_governo CASCADE;
-- Views legadas
DROP MATERIALIZED VIEW IF EXISTS mv_fornecedor_perfil CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_empresa_fontes CASCADE;

-- =============================================================================
-- LAYER 1: MVs independentes (sem dependências entre si)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. mv_empresa_governo: Perfil 360° de empresas em fontes governamentais
--    Agrega totais de 9 fontes + flags de risco (inativa, sancionada, dívida)
--    ~2-4M rows estimado
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW mv_empresa_governo AS
WITH
pncp_agg AS (
    SELECT cnpj_basico_fornecedor AS cnpj_basico,
           SUM(valor_global) AS total, COUNT(*) AS qtd
    FROM pncp_contrato
    WHERE cnpj_basico_fornecedor IS NOT NULL
    GROUP BY 1
),
emenda_agg AS (
    SELECT cnpj_basico_favorecido AS cnpj_basico,
           SUM(valor_recebido) AS total, COUNT(*) AS qtd
    FROM emenda_favorecido
    WHERE cnpj_basico_favorecido IS NOT NULL
    GROUP BY 1
),
cpgf_agg AS (
    SELECT LEFT(REGEXP_REPLACE(cnpj_cpf_favorecido, '[^0-9]', '', 'g'), 8) AS cnpj_basico,
           SUM(valor_transacao) AS total, COUNT(*) AS qtd
    FROM cpgf_transacao
    WHERE LENGTH(REGEXP_REPLACE(cnpj_cpf_favorecido, '[^0-9]', '', 'g')) >= 14
    GROUP BY 1
),
bndes_agg AS (
    SELECT LEFT(REGEXP_REPLACE(cnpj, '[^0-9]', '', 'g'), 8) AS cnpj_basico,
           SUM(valor_contratado) AS total, COUNT(*) AS qtd
    FROM bndes_contrato
    WHERE cnpj IS NOT NULL
      AND LENGTH(REGEXP_REPLACE(cnpj, '[^0-9]', '', 'g')) >= 14
    GROUP BY 1
),
tce_agg AS (
    SELECT cnpj_basico,
           SUM(valor_pago) AS total, COUNT(*) AS qtd,
           COUNT(DISTINCT municipio) AS qtd_municipios
    FROM tce_pb_despesa
    WHERE cnpj_basico IS NOT NULL AND valor_pago > 0
    GROUP BY 1
),
pb_emp_agg AS (
    SELECT cnpj_basico,
           SUM(valor_empenho) AS total, COUNT(*) AS qtd
    FROM pb_empenho
    WHERE cnpj_basico IS NOT NULL
    GROUP BY 1
),
pb_ctr_agg AS (
    SELECT cnpj_basico,
           SUM(valor_original) AS total, COUNT(*) AS qtd
    FROM pb_contrato
    WHERE cnpj_basico IS NOT NULL
    GROUP BY 1
),
pb_sau_agg AS (
    SELECT cnpj_basico,
           SUM(valor_lancamento) AS total, COUNT(*) AS qtd
    FROM pb_saude
    WHERE cnpj_basico IS NOT NULL
    GROUP BY 1
),
pb_conv_agg AS (
    SELECT cnpj_basico,
           SUM(valor_concedente) AS total, COUNT(*) AS qtd
    FROM pb_convenio
    WHERE cnpj_basico IS NOT NULL
    GROUP BY 1
),
divida_agg AS (
    SELECT LEFT(cpf_cnpj_norm, 8) AS cnpj_basico,
           SUM(valor_consolidado) AS total, COUNT(*) AS qtd
    FROM pgfn_divida
    WHERE tipo_pessoa IN ('PJ', 'Pessoa jurídica', 'J') AND cpf_cnpj_norm IS NOT NULL
    GROUP BY 1
),
ceis_agg AS (
    SELECT LEFT(cpf_cnpj_norm, 8) AS cnpj_basico,
           COUNT(*) AS qtd,
           BOOL_OR(dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE) AS vigente
    FROM ceis_sancao
    WHERE tipo_pessoa IN ('PJ', 'Pessoa jurídica', 'J') AND cpf_cnpj_norm IS NOT NULL
    GROUP BY 1
),
cnep_agg AS (
    SELECT LEFT(cpf_cnpj_norm, 8) AS cnpj_basico,
           COUNT(*) AS qtd,
           BOOL_OR(dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE) AS vigente
    FROM cnep_sancao
    WHERE tipo_pessoa IN ('PJ', 'Pessoa jurídica', 'J') AND cpf_cnpj_norm IS NOT NULL
    GROUP BY 1
),
all_cnpj AS (
    SELECT cnpj_basico FROM pncp_agg
    UNION SELECT cnpj_basico FROM emenda_agg
    UNION SELECT cnpj_basico FROM cpgf_agg
    UNION SELECT cnpj_basico FROM bndes_agg
    UNION SELECT cnpj_basico FROM tce_agg
    UNION SELECT cnpj_basico FROM pb_emp_agg
    UNION SELECT cnpj_basico FROM pb_ctr_agg
    UNION SELECT cnpj_basico FROM pb_sau_agg
    UNION SELECT cnpj_basico FROM pb_conv_agg
)
SELECT
    a.cnpj_basico,
    e.razao_social,
    e.natureza_juridica,
    e.capital_social,
    e.porte,
    est.situacao_cadastral,
    est.dt_situacao,
    est.dt_inicio_atividade,
    est.cnae_principal,
    est.uf,
    est.municipio,
    -- Totais por fonte
    COALESCE(pncp.total, 0)   AS total_pncp,
    COALESCE(pncp.qtd, 0)     AS qtd_pncp,
    COALESCE(em.total, 0)     AS total_emendas,
    COALESCE(em.qtd, 0)       AS qtd_emendas,
    COALESCE(cpgf.total, 0)   AS total_cpgf,
    COALESCE(cpgf.qtd, 0)     AS qtd_cpgf,
    COALESCE(bn.total, 0)     AS total_bndes,
    COALESCE(bn.qtd, 0)       AS qtd_bndes,
    COALESCE(tce.total, 0)    AS total_tce_pb,
    COALESCE(tce.qtd, 0)      AS qtd_tce_pb,
    COALESCE(tce.qtd_municipios, 0) AS qtd_municipios_tce,
    COALESCE(pbe.total, 0)    AS total_pb_empenho,
    COALESCE(pbe.qtd, 0)      AS qtd_pb_empenho,
    COALESCE(pbc.total, 0)    AS total_pb_contrato,
    COALESCE(pbc.qtd, 0)      AS qtd_pb_contrato,
    COALESCE(pbs.total, 0)    AS total_pb_saude,
    COALESCE(pbs.qtd, 0)      AS qtd_pb_saude,
    COALESCE(pbv.total, 0)    AS total_pb_convenio,
    COALESCE(pbv.qtd, 0)      AS qtd_pb_convenio,
    COALESCE(div.total, 0)    AS total_divida_pgfn,
    COALESCE(div.qtd, 0)      AS qtd_divida_pgfn,
    -- Flags de risco
    (est.situacao_cadastral IS NULL OR est.situacao_cadastral <> 2) AS flag_inativa,
    div.cnpj_basico IS NOT NULL AS flag_divida_pgfn,
    COALESCE(ceis.vigente, FALSE) AS flag_ceis_vigente,
    COALESCE(cnep.vigente, FALSE) AS flag_cnep_vigente,
    COALESCE(ceis.qtd, 0) + COALESCE(cnep.qtd, 0) AS qtd_sancoes,
    (est.dt_inicio_atividade >= CURRENT_DATE - INTERVAL '2 years') AS flag_empresa_recente,
    -- Qtd fontes governo
    (CASE WHEN pncp.cnpj_basico IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN em.cnpj_basico IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN cpgf.cnpj_basico IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN bn.cnpj_basico IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN tce.cnpj_basico IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN pbe.cnpj_basico IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN pbc.cnpj_basico IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN pbs.cnpj_basico IS NOT NULL THEN 1 ELSE 0 END
   + CASE WHEN pbv.cnpj_basico IS NOT NULL THEN 1 ELSE 0 END
    )::SMALLINT AS qtd_fontes_governo,
    -- Total geral recebido do governo
    COALESCE(pncp.total, 0) + COALESCE(em.total, 0) + COALESCE(cpgf.total, 0)
    + COALESCE(bn.total, 0) + COALESCE(tce.total, 0) + COALESCE(pbe.total, 0)
    + COALESCE(pbc.total, 0) + COALESCE(pbs.total, 0) + COALESCE(pbv.total, 0)
    AS total_governo
FROM all_cnpj a
LEFT JOIN empresa e ON e.cnpj_basico = a.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_basico = a.cnpj_basico AND est.cnpj_ordem = '0001'
LEFT JOIN pncp_agg pncp ON pncp.cnpj_basico = a.cnpj_basico
LEFT JOIN emenda_agg em ON em.cnpj_basico = a.cnpj_basico
LEFT JOIN cpgf_agg cpgf ON cpgf.cnpj_basico = a.cnpj_basico
LEFT JOIN bndes_agg bn ON bn.cnpj_basico = a.cnpj_basico
LEFT JOIN tce_agg tce ON tce.cnpj_basico = a.cnpj_basico
LEFT JOIN pb_emp_agg pbe ON pbe.cnpj_basico = a.cnpj_basico
LEFT JOIN pb_ctr_agg pbc ON pbc.cnpj_basico = a.cnpj_basico
LEFT JOIN pb_sau_agg pbs ON pbs.cnpj_basico = a.cnpj_basico
LEFT JOIN pb_conv_agg pbv ON pbv.cnpj_basico = a.cnpj_basico
LEFT JOIN divida_agg div ON div.cnpj_basico = a.cnpj_basico
LEFT JOIN ceis_agg ceis ON ceis.cnpj_basico = a.cnpj_basico
LEFT JOIN cnep_agg cnep ON cnep.cnpj_basico = a.cnpj_basico;

CREATE UNIQUE INDEX idx_mv_eg_cnpj ON mv_empresa_governo(cnpj_basico);
CREATE INDEX idx_mv_eg_fontes ON mv_empresa_governo(qtd_fontes_governo) WHERE qtd_fontes_governo >= 3;
CREATE INDEX idx_mv_eg_inativa ON mv_empresa_governo(cnpj_basico) WHERE flag_inativa;
CREATE INDEX idx_mv_eg_ceis ON mv_empresa_governo(cnpj_basico) WHERE flag_ceis_vigente;
CREATE INDEX idx_mv_eg_uf ON mv_empresa_governo(uf);


-- -----------------------------------------------------------------------------
-- 2. mv_pessoa_pb: PFs do estado PB com CPF completo (âncora: pb_pagamento)
--    Cross-ref com sócio, servidor municipal/federal, candidato, BF, sanções
--    ~200-400k rows estimado
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW mv_pessoa_pb AS
WITH
pf_base AS (
    SELECT cpfcnpj_credor AS cpf,
           cpf_digitos_6,
           MAX(nome_upper) AS nome_upper,
           MAX(nome_credor) AS nome_credor,
           SUM(valor_pagamento) AS total_recebido_estado,
           COUNT(*) AS qtd_pagamentos_estado
    FROM pb_pagamento
    WHERE LENGTH(cpfcnpj_credor) = 11
      AND cpfcnpj_credor ~ '^[0-9]+$'
      AND cpf_digitos_6 IS NOT NULL
    GROUP BY cpfcnpj_credor, cpf_digitos_6
),
-- Sócio: pre-filter only CPFs that exist in pf_base
socio_match AS (
    SELECT s.cpf_cnpj_norm AS cpf_digitos_6,
           UPPER(TRIM(s.nome)) AS nome_upper,
           COUNT(DISTINCT s.cnpj_basico) AS qtd_empresas,
           ARRAY_AGG(DISTINCT s.cnpj_basico ORDER BY s.cnpj_basico) AS cnpjs_socio,
           BOOL_OR(EXISTS (
               SELECT 1 FROM pb_empenho pe WHERE pe.cnpj_basico = s.cnpj_basico
           )) AS socio_empresa_credor_estado
    FROM socio s
    WHERE s.tipo_socio = 2
      AND s.cpf_cnpj_norm IS NOT NULL
      AND LENGTH(s.cpf_cnpj_norm) = 6
      AND EXISTS (SELECT 1 FROM pf_base pf WHERE pf.cpf_digitos_6 = s.cpf_cnpj_norm)
    GROUP BY s.cpf_cnpj_norm, UPPER(TRIM(s.nome))
),
-- Servidor municipal: pre-filter
servidor_mun AS (
    SELECT cpf_digitos_6,
           nome_upper,
           COUNT(DISTINCT municipio) AS qtd_municipios,
           MAX(valor_vantagem) AS maior_salario,
           ARRAY_AGG(DISTINCT municipio ORDER BY municipio) AS municipios
    FROM tce_pb_servidor
    WHERE cpf_digitos_6 IS NOT NULL AND nome_upper IS NOT NULL
      AND ano_mes >= '2022-01'
      AND EXISTS (SELECT 1 FROM pf_base pf WHERE pf.cpf_digitos_6 = tce_pb_servidor.cpf_digitos_6)
    GROUP BY cpf_digitos_6, nome_upper
),
-- Servidor federal: pre-filter
servidor_fed AS (
    SELECT cpf_digitos AS cpf_digitos_6,
           UPPER(TRIM(nome)) AS nome_upper,
           MAX(descricao_cargo) AS cargo_federal,
           MAX(org_exercicio) AS orgao_federal
    FROM siape_cadastro
    WHERE cpf_digitos IS NOT NULL
      AND EXISTS (SELECT 1 FROM pf_base pf WHERE pf.cpf_digitos_6 = siape_cadastro.cpf_digitos)
    GROUP BY cpf_digitos, UPPER(TRIM(nome))
),
-- Bolsa Familia: pre-filter
bf_match AS (
    SELECT cpf_digitos AS cpf_digitos_6,
           UPPER(TRIM(nm_favorecido)) AS nome_upper,
           SUM(valor_parcela) AS total_bf,
           COUNT(*) AS qtd_bf
    FROM bolsa_familia
    WHERE cpf_digitos IS NOT NULL
      AND EXISTS (SELECT 1 FROM pf_base pf WHERE pf.cpf_digitos_6 = bolsa_familia.cpf_digitos)
    GROUP BY cpf_digitos, UPPER(TRIM(nm_favorecido))
),
ceis_pf AS (
    SELECT cpf_digitos_6,
           UPPER(TRIM(nome_sancionado)) AS nome_upper,
           COUNT(*) AS qtd_sancoes,
           BOOL_OR(dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE) AS vigente
    FROM ceis_sancao
    WHERE tipo_pessoa IN ('PF', 'Pessoa física', 'F') AND cpf_digitos_6 IS NOT NULL
    GROUP BY cpf_digitos_6, UPPER(TRIM(nome_sancionado))
),
-- TSE: pre-filter only CPFs in pf_base
tse_ultimo AS (
    SELECT DISTINCT ON (tc.cpf) tc.cpf, tc.nm_candidato, tc.sg_partido, tc.ds_cargo, tc.ano_eleicao
    FROM tse_candidato tc
    WHERE tc.cpf IS NOT NULL AND LENGTH(tc.cpf) = 11
      AND EXISTS (SELECT 1 FROM pf_base pf WHERE pf.cpf = tc.cpf)
    ORDER BY tc.cpf, tc.ano_eleicao DESC
)
SELECT
    pf.cpf,
    pf.cpf_digitos_6,
    pf.nome_upper,
    pf.nome_credor,
    pf.total_recebido_estado,
    pf.qtd_pagamentos_estado,
    -- Sócio
    COALESCE(sm.qtd_empresas, 0) AS qtd_empresas_socio,
    sm.cnpjs_socio,
    -- Servidor municipal
    COALESCE(srv.qtd_municipios, 0) AS qtd_municipios_servidor,
    srv.maior_salario AS salario_servidor_municipal,
    srv.municipios AS municipios_servidor,
    -- Servidor federal
    sf.cargo_federal,
    sf.orgao_federal,
    -- Bolsa Familia
    COALESCE(bf.total_bf, 0) AS total_bolsa_familia,
    COALESCE(bf.qtd_bf, 0) AS qtd_bolsa_familia,
    -- Candidato TSE (match exato CPF 11 dígitos)
    tc.nm_candidato AS nome_candidato_tse,
    tc.sg_partido AS partido_tse,
    tc.ds_cargo AS cargo_tse,
    tc.ano_eleicao AS ano_eleicao_tse,
    -- Sanções
    COALESCE(ceis.qtd_sancoes, 0) AS qtd_sancoes_ceis,
    COALESCE(ceis.vigente, FALSE) AS flag_sancionado_ceis,
    -- Flags compostos
    (sm.socio_empresa_credor_estado IS TRUE) AS flag_auto_contratacao_potencial,
    (srv.cpf_digitos_6 IS NOT NULL) AS flag_duplo_vinculo_mun_est,
    (sf.cpf_digitos_6 IS NOT NULL) AS flag_duplo_vinculo_fed_est,
    (bf.cpf_digitos_6 IS NOT NULL AND pf.total_recebido_estado > 10000) AS flag_bf_com_renda_estado,
    (ceis.vigente IS TRUE) AS flag_sancionado,
    (tc.cpf IS NOT NULL) AS flag_candidato
FROM pf_base pf
LEFT JOIN socio_match sm ON sm.cpf_digitos_6 = pf.cpf_digitos_6 AND sm.nome_upper = pf.nome_upper
LEFT JOIN servidor_mun srv ON srv.cpf_digitos_6 = pf.cpf_digitos_6 AND srv.nome_upper = pf.nome_upper
LEFT JOIN servidor_fed sf ON sf.cpf_digitos_6 = pf.cpf_digitos_6 AND sf.nome_upper = pf.nome_upper
LEFT JOIN bf_match bf ON bf.cpf_digitos_6 = pf.cpf_digitos_6 AND bf.nome_upper = pf.nome_upper
LEFT JOIN ceis_pf ceis ON ceis.cpf_digitos_6 = pf.cpf_digitos_6 AND ceis.nome_upper = pf.nome_upper
LEFT JOIN tse_ultimo tc ON tc.cpf = pf.cpf;

CREATE UNIQUE INDEX idx_mv_ppb_cpf ON mv_pessoa_pb(cpf);
CREATE INDEX idx_mv_ppb_digitos ON mv_pessoa_pb(cpf_digitos_6);
CREATE INDEX idx_mv_ppb_auto ON mv_pessoa_pb(cpf) WHERE flag_auto_contratacao_potencial;
CREATE INDEX idx_mv_ppb_duplo_mun ON mv_pessoa_pb(cpf) WHERE flag_duplo_vinculo_mun_est;
CREATE INDEX idx_mv_ppb_duplo_fed ON mv_pessoa_pb(cpf) WHERE flag_duplo_vinculo_fed_est;
CREATE INDEX idx_mv_ppb_bf ON mv_pessoa_pb(cpf) WHERE flag_bf_com_renda_estado;


-- -----------------------------------------------------------------------------
-- 3. mv_municipio_pb_risco: Score de risco por município PB
--    Métricas: % sem licitação, % dezembro, proponente único, divergência
--    ~237 rows (municípios PB)
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW mv_municipio_pb_risco AS
WITH
desp AS (
    SELECT d.municipio,
           COUNT(*) AS qtd_empenhos,
           SUM(d.valor_empenhado) AS total_empenhado,
           SUM(d.valor_pago) AS total_pago,
           COUNT(*) FILTER (WHERE d.numero_licitacao IS NULL OR d.numero_licitacao = '' OR d.numero_licitacao = '0' OR d.numero_licitacao = '000000000' OR d.modalidade_licitacao ILIKE '%sem licit%') AS qtd_sem_licitacao,
           COUNT(*) FILTER (WHERE d.mes LIKE '12%') AS qtd_dezembro,
           COUNT(DISTINCT d.cnpj_basico) AS qtd_fornecedores
    FROM tce_pb_despesa d
    JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
        AND e.natureza_juridica NOT LIKE '1%'
    WHERE d.cnpj_basico IS NOT NULL AND d.ano >= 2022
    GROUP BY d.municipio
),
lic_proponente AS (
    SELECT municipio, numero_licitacao,
           COUNT(DISTINCT cpf_cnpj_proponente) AS num_proponentes
    FROM tce_pb_licitacao
    WHERE ano_licitacao >= 2022
    GROUP BY municipio, numero_licitacao
),
lic AS (
    SELECT lp.municipio,
           COUNT(DISTINCT lp.numero_licitacao) AS qtd_licitacoes,
           SUM(CASE WHEN lp.num_proponentes = 1 THEN 1 ELSE 0 END) AS qtd_proponente_unico
    FROM lic_proponente lp
    GROUP BY lp.municipio
),
receita AS (
    SELECT municipio,
           SUM(valor) FILTER (WHERE tipo_atualizacao_receita ILIKE 'Lançamento de Receita') AS receita_arrecadada
    FROM tce_pb_receita
    WHERE ano >= 2022
    GROUP BY municipio
),
folha AS (
    SELECT municipio,
           SUM(valor_vantagem) AS total_folha
    FROM tce_pb_servidor
    WHERE ano_mes >= '2022-01'
    GROUP BY municipio
)
SELECT
    d.municipio,
    d.qtd_empenhos,
    d.total_empenhado,
    d.total_pago,
    d.qtd_fornecedores,
    d.qtd_sem_licitacao,
    ROUND(100.0 * d.qtd_sem_licitacao / NULLIF(d.qtd_empenhos, 0), 1) AS pct_sem_licitacao,
    d.qtd_dezembro,
    ROUND(100.0 * d.qtd_dezembro / NULLIF(d.qtd_empenhos, 0), 1) AS pct_dezembro,
    COALESCE(l.qtd_licitacoes, 0) AS qtd_licitacoes,
    COALESCE(l.qtd_proponente_unico, 0) AS qtd_proponente_unico,
    ROUND(100.0 * COALESCE(l.qtd_proponente_unico, 0) / NULLIF(l.qtd_licitacoes, 0), 1) AS pct_proponente_unico,
    ROUND(100.0 * (d.total_empenhado - d.total_pago) / NULLIF(d.total_empenhado, 0), 1) AS pct_nao_executado,
    COALESCE(r.receita_arrecadada, 0) AS receita_arrecadada,
    COALESCE(f.total_folha, 0) AS total_folha,
    ROUND(100.0 * COALESCE(f.total_folha, 0) / NULLIF(r.receita_arrecadada, 0), 1) AS pct_folha_receita,
    -- Score composto (0-100)
    (
        -- Sem licitação (peso 30): > 50% = 30pts, linear abaixo
        LEAST(30, ROUND(30.0 * COALESCE(d.qtd_sem_licitacao, 0) / NULLIF(d.qtd_empenhos * 0.5, 0)))
        -- Proponente único (peso 25): > 40% = 25pts
      + LEAST(25, ROUND(25.0 * COALESCE(l.qtd_proponente_unico, 0) / NULLIF(l.qtd_licitacoes * 0.4, 0)))
        -- Concentração dezembro (peso 20): > 20% = 20pts (8.33% seria uniforme)
      + LEAST(20, ROUND(20.0 * COALESCE(d.qtd_dezembro, 0) / NULLIF(d.qtd_empenhos * 0.2, 0)))
        -- Não executado (peso 15): > 30% = 15pts
      + LEAST(15, ROUND(15.0 * ABS(d.total_empenhado - d.total_pago) / NULLIF(d.total_empenhado * 0.3, 0)))
        -- Folha/receita (peso 10): > 70% = 10pts
      + LEAST(10, ROUND(10.0 * COALESCE(f.total_folha, 0) / NULLIF(r.receita_arrecadada * 0.7, 0)))
    )::SMALLINT AS risco_score
FROM desp d
LEFT JOIN lic l ON l.municipio = d.municipio
LEFT JOIN receita r ON r.municipio = d.municipio
LEFT JOIN folha f ON f.municipio = d.municipio;

CREATE UNIQUE INDEX idx_mv_mun_municipio ON mv_municipio_pb_risco(municipio);
CREATE INDEX idx_mv_mun_risco ON mv_municipio_pb_risco(risco_score DESC);


-- -----------------------------------------------------------------------------
-- 4a. mv_servidor_pb_base: Servidores municipais PB dedup (base para risco)
--     Separado para evitar re-scan de 21M rows em cada CTE
--     ~50-200k rows estimado
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW mv_servidor_pb_base AS
SELECT cpf_digitos_6,
       nome_upper,
       MAX(nome_servidor) AS nome_servidor,
       COUNT(DISTINCT municipio) AS qtd_municipios,
       ARRAY_AGG(DISTINCT municipio ORDER BY municipio) AS municipios,
       MAX(valor_vantagem) AS maior_salario,
       MAX(descricao_cargo) AS cargo,
       MAX(ano_mes) AS ultimo_registro
FROM tce_pb_servidor
WHERE cpf_digitos_6 IS NOT NULL AND nome_upper IS NOT NULL
  AND ano_mes >= '2022-01'
GROUP BY cpf_digitos_6, nome_upper;

CREATE UNIQUE INDEX idx_mv_srvb_cpf_nome ON mv_servidor_pb_base(cpf_digitos_6, nome_upper);

-- -----------------------------------------------------------------------------
-- 4b. mv_servidor_pb_risco: Enriquece base com cross-refs e flags
--     IMPORTANTE: Abordagem stepwise com tabelas regulares.
--     A versão CTE-única causa timeout porque:
--     - BOOL_OR(EXISTS(subquery)) executa subquery correlacionada por grupo (~10min+)
--     - PostgreSQL escolhe plano catastrófico quando todas CTEs combinadas
--     Solução: materializar cada step como tabela com índice, depois montar a MV.
-- -----------------------------------------------------------------------------

-- Step 1: Sócio-empresas (sem flag fornecedor — o BOOL_OR(EXISTS) é o gargalo)
DROP TABLE IF EXISTS _tmp_socio_empresas;
CREATE TABLE _tmp_socio_empresas AS
SELECT srv.cpf_digitos_6,
       srv.nome_upper,
       COUNT(DISTINCT s.cnpj_basico) AS qtd_empresas,
       ARRAY_AGG(DISTINCT s.cnpj_basico ORDER BY s.cnpj_basico) AS cnpjs
FROM mv_servidor_pb_base srv
JOIN socio s ON s.cpf_cnpj_norm = srv.cpf_digitos_6
    AND UPPER(TRIM(s.nome)) = srv.nome_upper
    AND s.tipo_socio = 2
JOIN estabelecimento est ON est.cnpj_basico = s.cnpj_basico
    AND est.cnpj_ordem = '0001'
    AND est.situacao_cadastral = 2
GROUP BY srv.cpf_digitos_6, srv.nome_upper;

CREATE INDEX idx_tmp_se_cpf ON _tmp_socio_empresas(cpf_digitos_6, nome_upper);

-- Step 2: Flag fornecedor_governo via JOIN (não correlated EXISTS)
DROP TABLE IF EXISTS _tmp_fornecedor_gov;
CREATE TABLE _tmp_fornecedor_gov AS
SELECT DISTINCT se.cpf_digitos_6, se.nome_upper
FROM _tmp_socio_empresas se,
     LATERAL unnest(se.cnpjs) AS cnpj(cnpj_basico)
JOIN tce_pb_despesa d ON d.cnpj_basico = cnpj.cnpj_basico AND d.valor_pago > 0;

-- Step 3: Conflito de interesses (empresa do sócio fornece ao mesmo município)
DROP TABLE IF EXISTS _tmp_conflito;
CREATE TABLE _tmp_conflito AS
SELECT se.cpf_digitos_6, se.nome_upper,
       COUNT(DISTINCT d.cnpj_basico) AS qtd_conflitos,
       SUM(d.total_pago) AS total_conflito
FROM _tmp_socio_empresas se
CROSS JOIN LATERAL unnest(se.cnpjs) AS cnpj(cnpj_basico)
JOIN (
    SELECT cnpj_basico, municipio, SUM(valor_pago) AS total_pago
    FROM tce_pb_despesa WHERE valor_pago > 0
    GROUP BY cnpj_basico, municipio
) d ON d.cnpj_basico = cnpj.cnpj_basico
JOIN mv_servidor_pb_base srv ON srv.cpf_digitos_6 = se.cpf_digitos_6
    AND srv.nome_upper = se.nome_upper
    AND d.municipio = ANY(srv.municipios)
GROUP BY se.cpf_digitos_6, se.nome_upper;

-- Step 4: Bolsa Família match (apenas durante vínculo ativo)
DROP TABLE IF EXISTS _tmp_bf;
CREATE TABLE _tmp_bf AS
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

-- Step 5: Duplo vínculo estado (servidor municipal + credor estadual PF)
DROP TABLE IF EXISTS _tmp_duplo;
CREATE TABLE _tmp_duplo AS
SELECT srv.cpf_digitos_6,
       srv.nome_upper,
       SUM(pp.valor_pagamento) AS total_estado
FROM mv_servidor_pb_base srv
JOIN pb_pagamento pp ON pp.cpf_digitos_6 = srv.cpf_digitos_6
    AND pp.nome_upper = srv.nome_upper
    AND LENGTH(pp.cpfcnpj_credor) = 11
GROUP BY srv.cpf_digitos_6, srv.nome_upper;

-- Step 6: Montar MV final a partir das tabelas intermediárias
CREATE MATERIALIZED VIEW mv_servidor_pb_risco AS
SELECT
    srv.cpf_digitos_6,
    srv.nome_upper,
    srv.nome_servidor,
    srv.qtd_municipios,
    srv.municipios,
    srv.maior_salario,
    srv.cargo,
    srv.ultimo_registro,
    -- Sócio de empresas
    COALESCE(se.qtd_empresas, 0) AS qtd_empresas_socio,
    se.cnpjs AS cnpjs_socio,
    COALESCE(fg.cpf_digitos_6 IS NOT NULL, FALSE) AS socio_fornecedor_governo,
    -- Conflito de interesses (mesmo município)
    COALESCE(conf.qtd_conflitos, 0) AS qtd_conflitos_municipio,
    COALESCE(conf.total_conflito, 0) AS total_conflito_municipio,
    -- Bolsa Familia
    COALESCE(bf.total_bf, 0) AS total_bolsa_familia,
    -- Duplo vínculo estado
    COALESCE(de.total_estado, 0) AS total_recebido_estado,
    -- Flags
    (conf.cpf_digitos_6 IS NOT NULL) AS flag_conflito_interesses,
    (se.qtd_empresas >= 3) AS flag_multi_empresa,
    (bf.cpf_digitos_6 IS NOT NULL) AS flag_bolsa_familia,
    (de.cpf_digitos_6 IS NOT NULL) AS flag_duplo_vinculo_estado,
    (srv.maior_salario > 20000 AND se.qtd_empresas > 0) AS flag_alto_salario_socio,
    -- Score (0-100)
    (
        CASE WHEN conf.cpf_digitos_6 IS NOT NULL THEN 40 ELSE 0 END
      + CASE WHEN srv.maior_salario > 20000 AND se.qtd_empresas > 0 THEN 20 ELSE 0 END
      + CASE WHEN bf.cpf_digitos_6 IS NOT NULL THEN 15 ELSE 0 END
      + CASE WHEN de.cpf_digitos_6 IS NOT NULL THEN 15 ELSE 0 END
      + CASE WHEN se.qtd_empresas >= 3 THEN 10 ELSE 0 END
    )::SMALLINT AS risco_score
FROM mv_servidor_pb_base srv
LEFT JOIN _tmp_socio_empresas se ON se.cpf_digitos_6 = srv.cpf_digitos_6 AND se.nome_upper = srv.nome_upper
LEFT JOIN _tmp_fornecedor_gov fg ON fg.cpf_digitos_6 = srv.cpf_digitos_6 AND fg.nome_upper = srv.nome_upper
LEFT JOIN _tmp_conflito conf ON conf.cpf_digitos_6 = srv.cpf_digitos_6 AND conf.nome_upper = srv.nome_upper
LEFT JOIN _tmp_bf bf ON bf.cpf_digitos_6 = srv.cpf_digitos_6 AND bf.nome_upper = srv.nome_upper
LEFT JOIN _tmp_duplo de ON de.cpf_digitos_6 = srv.cpf_digitos_6 AND de.nome_upper = srv.nome_upper;

CREATE UNIQUE INDEX idx_mv_srv_cpf_nome ON mv_servidor_pb_risco(cpf_digitos_6, nome_upper);
CREATE INDEX idx_mv_srv_conflito ON mv_servidor_pb_risco(cpf_digitos_6) WHERE flag_conflito_interesses;
CREATE INDEX idx_mv_srv_risco ON mv_servidor_pb_risco(risco_score DESC) WHERE risco_score > 0;

-- Nota: _tmp_socio_empresas, _tmp_fornecedor_gov, _tmp_conflito, _tmp_bf, _tmp_duplo
-- não podem ser dropadas aqui. O PostgreSQL registra dependência de metadata entre
-- mv_servidor_pb_risco e essas tabelas (porque a MV foi criada via SELECT sobre elas),
-- e recusa o DROP com "cannot drop table X because other objects depend on it".
-- Elas ficam como backing storage da MV. Mesmo padrão aplicado a _tmp_rede_* abaixo.
-- Na próxima execução, o CASCADE no DROP MATERIALIZED VIEW libera as _tmp tables,
-- que são então dropadas pelos DROPs no início da seção "Fase 1" (linhas 469, 487...).


-- =============================================================================
-- LAYER 2: MVs que dependem de Layer 1 para consistência conceitual
--          (não dependem tecnicamente, mas melhor criar após Layer 1)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 5. mv_empresa_pb: Empresas ativas em fontes PB (TCE + dados.pb)
--    Combina totais municipais e estaduais + flags
--    ~100-200k rows estimado
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW mv_empresa_pb AS
WITH
pb_cnpj AS (
    -- Todos os CNPJs que aparecem em qualquer fonte PB
    SELECT DISTINCT cnpj_basico FROM tce_pb_despesa WHERE cnpj_basico IS NOT NULL
    UNION SELECT DISTINCT cnpj_basico FROM pb_empenho WHERE cnpj_basico IS NOT NULL
    UNION SELECT DISTINCT cnpj_basico FROM pb_contrato WHERE cnpj_basico IS NOT NULL
    UNION SELECT DISTINCT cnpj_basico FROM pb_saude WHERE cnpj_basico IS NOT NULL
    UNION SELECT DISTINCT cnpj_basico FROM pb_convenio WHERE cnpj_basico IS NOT NULL
),
tce_agg AS (
    SELECT cnpj_basico,
           SUM(valor_pago) AS total_pago,
           SUM(valor_empenhado) AS total_empenhado,
           COUNT(*) AS qtd_empenhos,
           COUNT(DISTINCT municipio) AS qtd_municipios,
           ARRAY_AGG(DISTINCT municipio ORDER BY municipio) AS municipios,
           COUNT(*) FILTER (WHERE numero_licitacao IS NULL OR numero_licitacao = '' OR numero_licitacao = '0' OR numero_licitacao = '000000000' OR modalidade_licitacao ILIKE '%sem licit%') AS qtd_sem_licitacao
    FROM tce_pb_despesa
    WHERE cnpj_basico IS NOT NULL AND valor_pago > 0
    GROUP BY cnpj_basico
),
pb_emp_agg AS (
    SELECT cnpj_basico,
           SUM(valor_empenho) AS total_empenho,
           COUNT(*) AS qtd_empenhos
    FROM pb_empenho WHERE cnpj_basico IS NOT NULL
    GROUP BY cnpj_basico
),
pb_ctr_agg AS (
    SELECT cnpj_basico,
           SUM(valor_original) AS total_contrato,
           COUNT(*) AS qtd_contratos
    FROM pb_contrato WHERE cnpj_basico IS NOT NULL
    GROUP BY cnpj_basico
),
pb_sau_agg AS (
    SELECT cnpj_basico,
           SUM(valor_lancamento) AS total_saude,
           COUNT(*) AS qtd_saude
    FROM pb_saude WHERE cnpj_basico IS NOT NULL
    GROUP BY cnpj_basico
),
pb_conv_agg AS (
    SELECT cnpj_basico,
           SUM(valor_concedente) AS total_convenio,
           COUNT(*) AS qtd_convenios
    FROM pb_convenio WHERE cnpj_basico IS NOT NULL
    GROUP BY cnpj_basico
),
lic_agg AS (
    SELECT cnpj_basico_proponente AS cnpj_basico,
           COUNT(*) AS qtd_propostas,
           COUNT(*) FILTER (WHERE situacao_proposta = 'Homologado') AS qtd_homologadas,
           SUM(valor_ofertado) FILTER (WHERE situacao_proposta = 'Homologado') AS total_homologado
    FROM tce_pb_licitacao
    WHERE cnpj_basico_proponente IS NOT NULL
    GROUP BY cnpj_basico_proponente
),
divida_agg AS (
    SELECT LEFT(cpf_cnpj_norm, 8) AS cnpj_basico,
           SUM(valor_consolidado) AS total_divida
    FROM pgfn_divida
    WHERE tipo_pessoa IN ('PJ', 'Pessoa jurídica', 'J') AND cpf_cnpj_norm IS NOT NULL
    GROUP BY 1
),
ceis_agg AS (
    SELECT LEFT(cpf_cnpj_norm, 8) AS cnpj_basico,
           BOOL_OR(dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE) AS vigente
    FROM ceis_sancao
    WHERE tipo_pessoa IN ('PJ', 'Pessoa jurídica', 'J') AND cpf_cnpj_norm IS NOT NULL
    GROUP BY 1
)
SELECT
    pc.cnpj_basico,
    e.razao_social,
    e.capital_social,
    e.porte,
    est.situacao_cadastral,
    est.dt_inicio_atividade,
    est.cnae_principal,
    est.uf,
    est.logradouro,
    est.numero,
    est.municipio AS municipio_sede,
    -- TCE-PB (municipal)
    COALESCE(tce.total_pago, 0) AS total_tce_pago,
    COALESCE(tce.total_empenhado, 0) AS total_tce_empenhado,
    COALESCE(tce.qtd_empenhos, 0) AS qtd_tce_empenhos,
    COALESCE(tce.qtd_municipios, 0) AS qtd_tce_municipios,
    tce.municipios AS tce_municipios,
    COALESCE(tce.qtd_sem_licitacao, 0) AS qtd_tce_sem_licitacao,
    -- dados.pb (estadual)
    COALESCE(pbe.total_empenho, 0) AS total_pb_empenho,
    COALESCE(pbe.qtd_empenhos, 0) AS qtd_pb_empenhos,
    COALESCE(pbc.total_contrato, 0) AS total_pb_contrato,
    COALESCE(pbc.qtd_contratos, 0) AS qtd_pb_contratos,
    COALESCE(pbs.total_saude, 0) AS total_pb_saude,
    COALESCE(pbs.qtd_saude, 0) AS qtd_pb_saude,
    COALESCE(pbv.total_convenio, 0) AS total_pb_convenio,
    COALESCE(pbv.qtd_convenios, 0) AS qtd_pb_convenios,
    -- Licitações TCE
    COALESCE(lic.qtd_propostas, 0) AS qtd_lic_propostas,
    COALESCE(lic.qtd_homologadas, 0) AS qtd_lic_homologadas,
    COALESCE(lic.total_homologado, 0) AS total_lic_homologado,
    -- Dívida e sanções
    COALESCE(div.total_divida, 0) AS total_divida_pgfn,
    COALESCE(ceis.vigente, FALSE) AS flag_ceis_vigente,
    -- Flags
    (est.situacao_cadastral IS NULL OR est.situacao_cadastral <> 2) AS flag_inativa,
    (e.capital_social < 10000 AND COALESCE(tce.total_pago, 0) + COALESCE(pbe.total_empenho, 0) > 500000) AS flag_capital_desproporcional,
    (COALESCE(tce.qtd_municipios, 0) >= 3) AS flag_multi_municipal,
    (COALESCE(tce.qtd_sem_licitacao, 0) > COALESCE(tce.qtd_empenhos, 0) * 0.5) AS flag_predomina_sem_licitacao,
    -- Total PB (municipal + estadual)
    COALESCE(tce.total_pago, 0) + COALESCE(pbe.total_empenho, 0)
    + COALESCE(pbc.total_contrato, 0) + COALESCE(pbs.total_saude, 0)
    + COALESCE(pbv.total_convenio, 0) AS total_pb_geral
FROM pb_cnpj pc
LEFT JOIN empresa e ON e.cnpj_basico = pc.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_basico = pc.cnpj_basico AND est.cnpj_ordem = '0001'
LEFT JOIN tce_agg tce ON tce.cnpj_basico = pc.cnpj_basico
LEFT JOIN pb_emp_agg pbe ON pbe.cnpj_basico = pc.cnpj_basico
LEFT JOIN pb_ctr_agg pbc ON pbc.cnpj_basico = pc.cnpj_basico
LEFT JOIN pb_sau_agg pbs ON pbs.cnpj_basico = pc.cnpj_basico
LEFT JOIN pb_conv_agg pbv ON pbv.cnpj_basico = pc.cnpj_basico
LEFT JOIN lic_agg lic ON lic.cnpj_basico = pc.cnpj_basico
LEFT JOIN divida_agg div ON div.cnpj_basico = pc.cnpj_basico
LEFT JOIN ceis_agg ceis ON ceis.cnpj_basico = pc.cnpj_basico;

CREATE UNIQUE INDEX idx_mv_epb_cnpj ON mv_empresa_pb(cnpj_basico);
CREATE INDEX idx_mv_epb_inativa ON mv_empresa_pb(cnpj_basico) WHERE flag_inativa;
CREATE INDEX idx_mv_epb_ceis ON mv_empresa_pb(cnpj_basico) WHERE flag_ceis_vigente;
CREATE INDEX idx_mv_epb_capital ON mv_empresa_pb(cnpj_basico) WHERE flag_capital_desproporcional;
CREATE INDEX idx_mv_epb_multi ON mv_empresa_pb(cnpj_basico) WHERE flag_multi_municipal;
CREATE INDEX idx_mv_epb_endereco ON mv_empresa_pb(logradouro, numero) WHERE logradouro IS NOT NULL;


-- -----------------------------------------------------------------------------
-- 6. mv_rede_pb: Grafo de conexões PB
--    5 tipos de aresta: SOCIO, FORNECEDOR_MUNICIPAL, SERVIDOR_MUNICIPAL,
--    CREDOR_ESTADUAL_PF, DOADOR_CAMPANHA
--    ~500k-2M rows estimado
--    Sem UNIQUE INDEX → refresh non-concurrent
--
--    IMPORTANTE: Abordagem stepwise — query única com 5 UNION ALL de subqueries
--    pesadas causa timeout (30min+). Materializar cada tipo de aresta como tabela
--    e depois UNION ALL das tabelas é ~5min total.
-- -----------------------------------------------------------------------------

-- CNPJs ativos em PB (filtro compartilhado)
DROP TABLE IF EXISTS _tmp_pb_cnpjs;
CREATE TABLE _tmp_pb_cnpjs AS
SELECT DISTINCT cnpj_basico FROM (
    SELECT DISTINCT cnpj_basico FROM tce_pb_despesa WHERE cnpj_basico IS NOT NULL AND valor_pago > 0
    UNION
    SELECT DISTINCT cnpj_basico FROM pb_empenho WHERE cnpj_basico IS NOT NULL
) x;
CREATE INDEX idx_tmp_pb_cnpj ON _tmp_pb_cnpjs(cnpj_basico);

-- Aresta 1: SOCIO (pessoa → empresa ativa em PB)
DROP TABLE IF EXISTS _tmp_rede_socio;
CREATE TABLE _tmp_rede_socio (
    tipo_aresta TEXT, pessoa_id TEXT, pessoa_nome TEXT,
    entidade_id TEXT, entidade_nome TEXT, contexto TEXT
);
INSERT INTO _tmp_rede_socio
SELECT
    'SOCIO', s.cpf_cnpj_norm, UPPER(TRIM(s.nome)),
    s.cnpj_basico, e.razao_social, NULL
FROM socio s
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN _tmp_pb_cnpjs pb ON pb.cnpj_basico = s.cnpj_basico
WHERE s.tipo_socio = 2
  AND s.cpf_cnpj_norm IS NOT NULL
  AND LENGTH(s.cpf_cnpj_norm) = 6;

-- Aresta 2: FORNECEDOR_MUNICIPAL (empresa → município)
DROP TABLE IF EXISTS _tmp_rede_forn;
CREATE TABLE _tmp_rede_forn (
    tipo_aresta TEXT, pessoa_id TEXT, pessoa_nome TEXT,
    entidade_id TEXT, entidade_nome TEXT, contexto TEXT
);
INSERT INTO _tmp_rede_forn
SELECT
    'FORNECEDOR_MUNICIPAL', d.cnpj_basico, e.razao_social,
    d.municipio, d.municipio,
    'R$' || TO_CHAR(SUM(d.valor_pago), 'FM999,999,999.00')
FROM tce_pb_despesa d
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
WHERE d.cnpj_basico IS NOT NULL AND d.valor_pago > 0
GROUP BY d.cnpj_basico, e.razao_social, d.municipio;

-- Aresta 3: SERVIDOR_MUNICIPAL (pessoa → município)
DROP TABLE IF EXISTS _tmp_rede_srv;
CREATE TABLE _tmp_rede_srv (
    tipo_aresta TEXT, pessoa_id TEXT, pessoa_nome TEXT,
    entidade_id TEXT, entidade_nome TEXT, contexto TEXT
);
INSERT INTO _tmp_rede_srv
SELECT DISTINCT
    'SERVIDOR_MUNICIPAL', srv.cpf_digitos_6, srv.nome_upper,
    srv.municipio, srv.municipio, srv.descricao_cargo
FROM tce_pb_servidor srv
WHERE srv.cpf_digitos_6 IS NOT NULL AND srv.nome_upper IS NOT NULL
  AND srv.ano_mes >= '2022-01';

-- Aresta 4: CREDOR_ESTADUAL_PF (pessoa → estado)
DROP TABLE IF EXISTS _tmp_rede_cred;
CREATE TABLE _tmp_rede_cred (
    tipo_aresta TEXT, pessoa_id TEXT, pessoa_nome TEXT,
    entidade_id TEXT, entidade_nome TEXT, contexto TEXT
);
INSERT INTO _tmp_rede_cred
SELECT
    'CREDOR_ESTADUAL_PF', pp.cpf_digitos_6, pp.nome_upper,
    'ESTADO_PB', 'Estado da Paraíba',
    'R$' || TO_CHAR(SUM(pp.valor_pagamento), 'FM999,999,999.00')
FROM pb_pagamento pp
WHERE pp.cpf_digitos_6 IS NOT NULL
  AND pp.nome_upper IS NOT NULL
  AND LENGTH(pp.cpfcnpj_credor) = 11
  AND pp.cpfcnpj_credor ~ '^[0-9]+$'
GROUP BY pp.cpf_digitos_6, pp.nome_upper;

-- Aresta 5: DOADOR_CAMPANHA (empresa → candidato PB)
DROP TABLE IF EXISTS _tmp_rede_doador;
CREATE TABLE _tmp_rede_doador (
    tipo_aresta TEXT, pessoa_id TEXT, pessoa_nome TEXT,
    entidade_id TEXT, entidade_nome TEXT, contexto TEXT
);
INSERT INTO _tmp_rede_doador
SELECT
    'DOADOR_CAMPANHA',
    LEFT(REGEXP_REPLACE(tr.cpf_cnpj_doador, '[^0-9]', '', 'g'), 8),
    tr.nm_doador,
    tc.sq_candidato::TEXT,
    tc.nm_candidato || ' (' || tc.sg_partido || ')',
    'R$' || TO_CHAR(SUM(tr.vr_receita), 'FM999,999,999.00')
FROM tse_receita_candidato tr
JOIN tse_candidato tc ON tc.sq_candidato = tr.sq_candidato AND tc.ano_eleicao = tr.ano_eleicao
WHERE tc.sg_uf = 'PB'
  AND tr.cpf_cnpj_doador IS NOT NULL
  AND LENGTH(REGEXP_REPLACE(tr.cpf_cnpj_doador, '[^0-9]', '', 'g')) >= 14
GROUP BY LEFT(REGEXP_REPLACE(tr.cpf_cnpj_doador, '[^0-9]', '', 'g'), 8),
         tr.nm_doador, tc.sq_candidato, tc.nm_candidato, tc.sg_partido;

-- Montar MV a partir das tabelas (rápido, sem re-scan)
CREATE MATERIALIZED VIEW mv_rede_pb AS
SELECT * FROM _tmp_rede_socio
UNION ALL SELECT * FROM _tmp_rede_forn
UNION ALL SELECT * FROM _tmp_rede_srv
UNION ALL SELECT * FROM _tmp_rede_cred
UNION ALL SELECT * FROM _tmp_rede_doador;

CREATE INDEX idx_mv_rede_tipo ON mv_rede_pb(tipo_aresta);
CREATE INDEX idx_mv_rede_pessoa ON mv_rede_pb(pessoa_id);
CREATE INDEX idx_mv_rede_entidade ON mv_rede_pb(entidade_id);

-- Nota: _tmp tables não podem ser dropadas pois mv_rede_pb depende delas.
-- O PostgreSQL mantém dependência de referência mesmo após materialização.
-- Estas tabelas ficam como backing storage da MV.


-- -----------------------------------------------------------------------------
-- 7. mv_municipio_pb_mapa: Métricas agregadas para o mapa coroplético PB
--    5 camadas: risco composto, % irregulares, % sem licitação, HHI top-5, per capita
--    Depende de: mv_municipio_pb_risco, tce_pb_despesa, estabelecimento,
--                ceis_sancao, cnep_sancao, pgfn_divida
-- -----------------------------------------------------------------------------
CREATE MATERIALIZED VIEW mv_municipio_pb_mapa AS
WITH
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


-- =============================================================================
-- LAYER 3: Views normais (sempre atualizadas, leem das MVs)
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 7. v_risk_score_empresa: Score de risco nacional baseado em mv_empresa_governo
-- -----------------------------------------------------------------------------
CREATE VIEW v_risk_score_empresa AS
SELECT
    cnpj_basico,
    razao_social,
    uf,
    total_governo,
    qtd_fontes_governo,
    -- Score (0-100)
    (
        CASE WHEN flag_inativa THEN 20 ELSE 0 END
      + CASE WHEN flag_divida_pgfn THEN 15 ELSE 0 END
      + CASE WHEN flag_ceis_vigente THEN 25 ELSE 0 END
      + CASE WHEN flag_cnep_vigente THEN 15 ELSE 0 END
      + CASE WHEN flag_empresa_recente AND total_governo > 1000000 THEN 15 ELSE 0 END
      + CASE WHEN capital_social < 10000 AND total_governo > 500000 THEN 10 ELSE 0 END
    )::SMALLINT AS risco_score,
    -- Array de flags ativas
    ARRAY_REMOVE(ARRAY[
        CASE WHEN flag_inativa THEN 'INATIVA' END,
        CASE WHEN flag_divida_pgfn THEN 'DIVIDA_PGFN' END,
        CASE WHEN flag_ceis_vigente THEN 'CEIS_VIGENTE' END,
        CASE WHEN flag_cnep_vigente THEN 'CNEP_VIGENTE' END,
        CASE WHEN flag_empresa_recente THEN 'RECENTE' END,
        CASE WHEN capital_social < 10000 AND total_governo > 500000 THEN 'CAPITAL_DESPROPORCIONAL' END
    ], NULL) AS flags
FROM mv_empresa_governo
WHERE flag_inativa OR flag_divida_pgfn OR flag_ceis_vigente OR flag_cnep_vigente
   OR (flag_empresa_recente AND total_governo > 1000000)
   OR (capital_social < 10000 AND total_governo > 500000);


-- -----------------------------------------------------------------------------
-- 8. v_risk_score_pb: Score unificado PB (empresa + servidor + PF)
-- -----------------------------------------------------------------------------
CREATE VIEW v_risk_score_pb AS
-- Empresas PB
SELECT
    'EMPRESA'::TEXT AS tipo_entidade,
    epb.cnpj_basico AS identificador,
    epb.razao_social AS nome,
    (
        CASE WHEN epb.flag_inativa THEN 20 ELSE 0 END
      + CASE WHEN epb.flag_ceis_vigente THEN 25 ELSE 0 END
      + CASE WHEN epb.flag_capital_desproporcional THEN 15 ELSE 0 END
      + CASE WHEN epb.flag_multi_municipal THEN 10 ELSE 0 END
      + CASE WHEN epb.flag_predomina_sem_licitacao THEN 15 ELSE 0 END
      + CASE WHEN epb.total_divida_pgfn > 0 THEN 15 ELSE 0 END
    )::SMALLINT AS risco_total,
    ARRAY_REMOVE(ARRAY[
        CASE WHEN epb.flag_inativa THEN 'INATIVA' END,
        CASE WHEN epb.flag_ceis_vigente THEN 'CEIS' END,
        CASE WHEN epb.flag_capital_desproporcional THEN 'CAPITAL_DESPROPORCIONAL' END,
        CASE WHEN epb.flag_multi_municipal THEN 'MULTI_MUNICIPAL' END,
        CASE WHEN epb.flag_predomina_sem_licitacao THEN 'SEM_LICITACAO' END,
        CASE WHEN epb.total_divida_pgfn > 0 THEN 'DIVIDA_PGFN' END
    ], NULL) AS flags,
    epb.total_pb_geral AS total_valor
FROM mv_empresa_pb epb
WHERE epb.flag_inativa OR epb.flag_ceis_vigente OR epb.flag_capital_desproporcional
   OR epb.flag_multi_municipal OR epb.flag_predomina_sem_licitacao
   OR epb.total_divida_pgfn > 0

UNION ALL

-- Servidores PB
SELECT
    'SERVIDOR',
    srv.cpf_digitos_6 || ':' || srv.nome_upper,
    srv.nome_servidor,
    srv.risco_score,
    ARRAY_REMOVE(ARRAY[
        CASE WHEN srv.flag_conflito_interesses THEN 'CONFLITO_INTERESSES' END,
        CASE WHEN srv.flag_multi_empresa THEN 'MULTI_EMPRESA' END,
        CASE WHEN srv.flag_bolsa_familia THEN 'BOLSA_FAMILIA' END,
        CASE WHEN srv.flag_duplo_vinculo_estado THEN 'DUPLO_VINCULO' END,
        CASE WHEN srv.flag_alto_salario_socio THEN 'ALTO_SALARIO_SOCIO' END
    ], NULL) AS flags,
    srv.maior_salario
FROM mv_servidor_pb_risco srv
WHERE srv.risco_score > 0

UNION ALL

-- Pessoas PF (pb_pagamento)
SELECT
    'PESSOA_PF',
    ppb.cpf,
    ppb.nome_credor,
    (
        CASE WHEN ppb.flag_auto_contratacao_potencial THEN 30 ELSE 0 END
      + CASE WHEN ppb.flag_duplo_vinculo_mun_est THEN 15 ELSE 0 END
      + CASE WHEN ppb.flag_duplo_vinculo_fed_est THEN 15 ELSE 0 END
      + CASE WHEN ppb.flag_bf_com_renda_estado THEN 15 ELSE 0 END
      + CASE WHEN ppb.flag_sancionado THEN 25 ELSE 0 END
    )::SMALLINT,
    ARRAY_REMOVE(ARRAY[
        CASE WHEN ppb.flag_auto_contratacao_potencial THEN 'AUTO_CONTRATACAO' END,
        CASE WHEN ppb.flag_duplo_vinculo_mun_est THEN 'DUPLO_VINCULO_MUN' END,
        CASE WHEN ppb.flag_duplo_vinculo_fed_est THEN 'DUPLO_VINCULO_FED' END,
        CASE WHEN ppb.flag_bf_com_renda_estado THEN 'BF_COM_RENDA' END,
        CASE WHEN ppb.flag_sancionado THEN 'SANCIONADO' END
    ], NULL) AS flags,
    ppb.total_recebido_estado
FROM mv_pessoa_pb ppb
WHERE ppb.flag_auto_contratacao_potencial OR ppb.flag_duplo_vinculo_mun_est
   OR ppb.flag_duplo_vinculo_fed_est OR ppb.flag_bf_com_renda_estado
   OR ppb.flag_sancionado;


-- =============================================================================
-- TABELA AUXILIAR: pncp_municipio (lista distinta de municípios PNCP)
-- Usada pelo autocomplete do frontend — evita full scan em pncp_contrato
-- =============================================================================
DROP TABLE IF EXISTS pncp_municipio;
CREATE TABLE pncp_municipio AS
SELECT DISTINCT municipio_nome, uf
FROM pncp_contrato
WHERE municipio_nome IS NOT NULL AND uf IS NOT NULL;

CREATE INDEX idx_pncp_mun_trgm ON pncp_municipio USING gin (municipio_nome gin_trgm_ops);

GRANT SELECT ON pncp_municipio TO govbr;


-- =============================================================================
-- Notas de refresh
-- =============================================================================
-- Layer 1 (paralelo ou sequencial, ~45min total):
--   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_empresa_governo;
--   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_pessoa_pb;
--   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_municipio_pb_risco;
--   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_servidor_pb_base;
--   Para mv_servidor_pb_risco: DROP + re-executar steps 1-6 (não suporta REFRESH
--   porque depende de tabelas _tmp_ intermediárias — abordagem stepwise necessária)
--
-- Layer 2 (após Layer 1, ~20min):
--   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_empresa_pb
--   REFRESH MATERIALIZED VIEW CONCURRENTLY mv_municipio_pb_mapa
--   Para mv_rede_pb: DROP + re-executar steps (abordagem stepwise)
--
-- Layer 3: views normais, sempre atualizadas automaticamente
