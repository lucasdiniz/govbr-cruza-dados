-- =============================================================================
-- mv_empresa_pb — atomic swap update (PR follow-up de #151)
-- =============================================================================
-- Aplica EXISTS(estabelecimento) guard em tce_agg, pb_emp_agg, pb_ctr_agg,
-- pb_sau_agg, pb_conv_agg e pb_cnpj. Sem o guard, o agregado contava
-- empenhos de CPFs padded compartilhando prefixo cnpj_basico com PJs
-- reais — KPIs do header em /empresa/<cnpj> ficavam inflados.
--
-- Convencao do framework (etl/mv_swap.py): identifiers usam sufixo `_swap`,
-- que sera removido pelo swap atomico.
-- =============================================================================

CREATE MATERIALIZED VIEW mv_empresa_pb_swap AS
WITH
pb_cnpj AS (
    -- Todos os CNPJs que aparecem em qualquer fonte PB.
    -- Guard EXISTS(estabelecimento) em tce_pb_despesa filtra CPFs padded
    -- (LEFT(cpf_cnpj, 8) sem validacao de origem). Demais fontes PB
    -- (pb_empenho/pb_contrato/etc) ja sao 100% PJ pela coleta.
    SELECT DISTINCT cnpj_basico FROM tce_pb_despesa d
      WHERE cnpj_basico IS NOT NULL
        AND EXISTS (
            SELECT 1 FROM estabelecimento est
            WHERE est.cnpj_completo = d.cpf_cnpj
        )
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
           ARRAY_AGG(DISTINCT municipio ORDER BY municipio)
              FILTER (WHERE municipio IS NOT NULL) AS municipios,
           COUNT(*) FILTER (WHERE numero_licitacao IS NULL OR numero_licitacao = '' OR numero_licitacao = '0' OR numero_licitacao = '000000000' OR modalidade_licitacao ILIKE '%sem licit%') AS qtd_sem_licitacao
    FROM tce_pb_despesa d
    WHERE cnpj_basico IS NOT NULL AND valor_pago > 0
      -- Guard contra CPF padded: so contar empenhos onde cpf_cnpj eh
      -- CNPJ legitimo no RFB. Sem isso, AVICOLA CHESTER (cnpj_basico
      -- 00014020) tem 5786 empenhos de CPFs comecando com 000140207...
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
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
    -- Licitacoes TCE
    COALESCE(lic.qtd_propostas, 0) AS qtd_lic_propostas,
    COALESCE(lic.qtd_homologadas, 0) AS qtd_lic_homologadas,
    COALESCE(lic.total_homologado, 0) AS total_lic_homologado,
    -- Divida e sancoes
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

CREATE UNIQUE INDEX idx_mv_epb_cnpj_swap ON mv_empresa_pb_swap(cnpj_basico);
CREATE INDEX idx_mv_epb_inativa_swap ON mv_empresa_pb_swap(cnpj_basico) WHERE flag_inativa;
CREATE INDEX idx_mv_epb_ceis_swap ON mv_empresa_pb_swap(cnpj_basico) WHERE flag_ceis_vigente;
CREATE INDEX idx_mv_epb_capital_swap ON mv_empresa_pb_swap(cnpj_basico) WHERE flag_capital_desproporcional;
CREATE INDEX idx_mv_epb_multi_swap ON mv_empresa_pb_swap(cnpj_basico) WHERE flag_multi_municipal;
CREATE INDEX idx_mv_epb_endereco_swap ON mv_empresa_pb_swap(logradouro, numero) WHERE logradouro IS NOT NULL;
