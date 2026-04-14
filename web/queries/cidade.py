"""SQL parametrizado para modo cidade."""

PERFIL_MUNICIPIO = """
SELECT municipio,
       qtd_empenhos, total_empenhado, total_pago, qtd_fornecedores,
       qtd_sem_licitacao, pct_sem_licitacao,
       qtd_dezembro, pct_dezembro,
       qtd_licitacoes, qtd_proponente_unico, pct_proponente_unico,
       pct_nao_executado,
       receita_arrecadada, total_folha, pct_folha_receita,
       risco_score
FROM mv_municipio_pb_risco
WHERE UPPER(unaccent(TRIM(municipio))) = UPPER(unaccent(TRIM(%(municipio)s)))
LIMIT 1
"""

PERFIL_MUNICIPIO_LIVE = """
SELECT %(municipio)s AS municipio,
       COUNT(*) AS qtd_empenhos,
       SUM(d.valor_empenhado) AS total_empenhado,
       SUM(d.valor_pago) AS total_pago,
       COUNT(DISTINCT d.cnpj_basico) FILTER (WHERE d.cnpj_basico IS NOT NULL) AS qtd_fornecedores,
       COUNT(*) FILTER (WHERE d.numero_licitacao = '000000000'
           OR d.modalidade_licitacao ILIKE '%%sem licit%%') AS qtd_sem_licitacao,
       ROUND(100.0 * COUNT(*) FILTER (WHERE d.numero_licitacao = '000000000'
           OR d.modalidade_licitacao ILIKE '%%sem licit%%')
           / NULLIF(COUNT(*), 0), 1) AS pct_sem_licitacao,
       COUNT(*) FILTER (WHERE d.mes = '12') AS qtd_dezembro,
       ROUND(100.0 * COUNT(*) FILTER (WHERE d.mes = '12')
           / NULLIF(COUNT(*), 0), 1) AS pct_dezembro,
       NULL::bigint AS qtd_licitacoes,
       NULL::bigint AS qtd_proponente_unico,
       NULL::numeric AS pct_proponente_unico,
       ROUND(100.0 * (1 - SUM(d.valor_pago) / NULLIF(SUM(d.valor_empenhado), 0)), 1) AS pct_nao_executado,
       NULL::numeric AS receita_arrecadada,
       NULL::numeric AS total_folha,
       NULL::numeric AS pct_folha_receita,
       NULL::numeric AS risco_score
FROM tce_pb_despesa d
WHERE d.municipio = %(municipio)s
  AND d.data_empenho >= %(data_inicio)s
  AND d.data_empenho <= %(data_fim)s
  AND d.valor_empenhado > 0
"""

PERFIL_MUNICIPIO_PNCP = """
SELECT
    %(municipio)s AS municipio,
    COUNT(*) AS qtd_contratos,
    SUM(valor_global) AS total_contratado,
    COUNT(DISTINCT cnpj_basico_fornecedor) AS qtd_fornecedores,
    MIN(dt_assinatura) AS contrato_mais_antigo,
    MAX(dt_assinatura) AS contrato_mais_recente
FROM pncp_contrato
WHERE municipio_nome = %(municipio)s AND uf = %(uf)s
"""

TOP_FORNECEDORES = """
WITH top_forn AS (
    SELECT d.cnpj_basico, d.nome_credor,
           SUM(d.valor_pago) AS total_pago,
           COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos
    FROM tce_pb_despesa d
    JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
        AND e.natureza_juridica NOT LIKE '1%%'
    WHERE d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND d.cnpj_basico IS NOT NULL
    GROUP BY d.cnpj_basico, d.nome_credor
    ORDER BY SUM(d.valor_pago) DESC
    LIMIT 200
)
SELECT tf.cnpj_basico, tf.nome_credor, e.razao_social,
       est.cnpj_completo,
       tf.total_pago, tf.qtd_empenhos,
       COALESCE(meg.flag_ceis_vigente, FALSE) AS flag_ceis,
       COALESCE(meg.flag_cnep_vigente, FALSE) AS flag_cnep,
       EXISTS(
           SELECT 1 FROM ceis_sancao cs
           WHERE LEFT(cs.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND (cs.dt_final_sancao IS NULL OR cs.dt_final_sancao >= CURRENT_DATE)
             AND cs.categoria_sancao ILIKE '%%inidone%%'
       ) AS flag_inidoneidade,
       COALESCE(meg.flag_divida_pgfn, FALSE) AS flag_pgfn,
       COALESCE(meg.flag_inativa, FALSE) AS flag_inativa,
       EXISTS(
           SELECT 1 FROM tce_pb_despesa d2
           JOIN (
               SELECT LEFT(cpf_cnpj_sancionado, 8) AS cb, dt_inicio_sancao, dt_final_sancao FROM ceis_sancao
               UNION ALL
               SELECT LEFT(cpf_cnpj_sancionado, 8), dt_inicio_sancao, dt_final_sancao FROM cnep_sancao
           ) san ON san.cb = d2.cnpj_basico
           WHERE d2.cnpj_basico = tf.cnpj_basico
             AND d2.municipio = %(municipio)s
             AND d2.valor_pago > 0
             AND d2.data_empenho >= san.dt_inicio_sancao
             AND (san.dt_final_sancao IS NULL OR d2.data_empenho <= san.dt_final_sancao)
       ) AS flag_recebeu_durante_sancao,
       CASE est.situacao_cadastral::text
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE COALESCE('Sit. ' || est.situacao_cadastral::text, '-')
       END AS desc_situacao
FROM top_forn tf
LEFT JOIN mv_empresa_governo meg ON meg.cnpj_basico = tf.cnpj_basico
LEFT JOIN empresa e ON e.cnpj_basico = tf.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_basico = tf.cnpj_basico AND est.cnpj_ordem = '0001'
ORDER BY flag_recebeu_durante_sancao DESC, tf.total_pago DESC
"""

TOP_FORNECEDORES_FALLBACK = """
WITH top_forn AS (
    SELECT d.cnpj_basico, d.nome_credor,
           SUM(d.valor_pago) AS total_pago,
           COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos
    FROM tce_pb_despesa d
    JOIN empresa e2 ON e2.cnpj_basico = d.cnpj_basico
        AND e2.natureza_juridica NOT LIKE '1%%'
    WHERE d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND d.cnpj_basico IS NOT NULL
    GROUP BY d.cnpj_basico, d.nome_credor
    ORDER BY SUM(d.valor_pago) DESC
    LIMIT 200
)
SELECT tf.cnpj_basico, tf.nome_credor, e.razao_social,
       est.cnpj_completo,
       tf.total_pago, tf.qtd_empenhos,
       EXISTS(
           SELECT 1
           FROM ceis_sancao cs
           WHERE LEFT(cs.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND (cs.dt_final_sancao IS NULL OR cs.dt_final_sancao >= CURRENT_DATE)
       ) AS flag_ceis,
       EXISTS(
           SELECT 1
           FROM cnep_sancao cn
           WHERE LEFT(cn.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND (cn.dt_final_sancao IS NULL OR cn.dt_final_sancao >= CURRENT_DATE)
       ) AS flag_cnep,
       EXISTS(
           SELECT 1 FROM ceis_sancao cs2
           WHERE LEFT(cs2.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND (cs2.dt_final_sancao IS NULL OR cs2.dt_final_sancao >= CURRENT_DATE)
             AND cs2.categoria_sancao ILIKE '%%inidone%%'
       ) AS flag_inidoneidade,
       EXISTS(
           SELECT 1
           FROM pgfn_divida pg
           WHERE LEFT(pg.cpf_cnpj_norm, 8) = tf.cnpj_basico
             AND LENGTH(pg.cpf_cnpj_norm) = 14
       ) AS flag_pgfn,
       COALESCE(est.situacao_cadastral != '2', FALSE) AS flag_inativa,
       EXISTS(
           SELECT 1 FROM tce_pb_despesa d2
           JOIN (
               SELECT LEFT(cpf_cnpj_sancionado, 8) AS cb, dt_inicio_sancao, dt_final_sancao FROM ceis_sancao
               UNION ALL
               SELECT LEFT(cpf_cnpj_sancionado, 8), dt_inicio_sancao, dt_final_sancao FROM cnep_sancao
           ) san ON san.cb = d2.cnpj_basico
           WHERE d2.cnpj_basico = tf.cnpj_basico
             AND d2.municipio = %(municipio)s
             AND d2.valor_pago > 0
             AND d2.data_empenho >= san.dt_inicio_sancao
             AND (san.dt_final_sancao IS NULL OR d2.data_empenho <= san.dt_final_sancao)
       ) AS flag_recebeu_durante_sancao,
       CASE est.situacao_cadastral::text
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE COALESCE('Sit. ' || est.situacao_cadastral::text, '-')
       END AS desc_situacao
FROM top_forn tf
LEFT JOIN empresa e ON e.cnpj_basico = tf.cnpj_basico
LEFT JOIN estabelecimento est
    ON est.cnpj_basico = tf.cnpj_basico
   AND est.cnpj_ordem = '0001'
ORDER BY flag_recebeu_durante_sancao DESC, tf.total_pago DESC
"""

TOP_FORNECEDORES_BASIC = """
SELECT d.cnpj_basico, d.nome_credor, e.razao_social,
       est.cnpj_completo,
       SUM(d.valor_pago) AS total_pago,
       COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos,
       FALSE AS flag_ceis,
       FALSE AS flag_cnep,
       FALSE AS flag_inidoneidade,
       FALSE AS flag_pgfn,
       FALSE AS flag_inativa,
       FALSE AS flag_recebeu_durante_sancao,
       CASE est.situacao_cadastral::text
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE COALESCE('Sit. ' || est.situacao_cadastral::text, '-')
       END AS desc_situacao
FROM tce_pb_despesa d
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
    AND e.natureza_juridica NOT LIKE '1%%'
LEFT JOIN estabelecimento est ON est.cnpj_basico = d.cnpj_basico AND est.cnpj_ordem = '0001'
WHERE d.municipio = %(municipio)s
  AND d.valor_pago > 0
  AND d.cnpj_basico IS NOT NULL
GROUP BY d.cnpj_basico, d.nome_credor, e.razao_social, est.cnpj_completo, est.situacao_cadastral
ORDER BY (COALESCE(est.situacao_cadastral::text != '2', FALSE))::int DESC, SUM(d.valor_pago) DESC
LIMIT 200
"""

# ── Variantes com filtro temporal (dated) ───────────────────────

TOP_FORNECEDORES_DATED = """
WITH top_forn AS (
    SELECT d.cnpj_basico, d.nome_credor,
           SUM(d.valor_pago) AS total_pago,
           COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos
    FROM tce_pb_despesa d
    JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
        AND e.natureza_juridica NOT LIKE '1%%'
    WHERE d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND d.cnpj_basico IS NOT NULL
      AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
    GROUP BY d.cnpj_basico, d.nome_credor
    ORDER BY SUM(d.valor_pago) DESC
    LIMIT 200
)
SELECT tf.cnpj_basico, tf.nome_credor, e.razao_social,
       est.cnpj_completo,
       tf.total_pago, tf.qtd_empenhos,
       COALESCE(meg.flag_ceis_vigente, FALSE) AS flag_ceis,
       COALESCE(meg.flag_cnep_vigente, FALSE) AS flag_cnep,
       EXISTS(
           SELECT 1 FROM ceis_sancao cs
           WHERE LEFT(cs.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND (cs.dt_final_sancao IS NULL OR cs.dt_final_sancao >= CURRENT_DATE)
             AND cs.categoria_sancao ILIKE '%%inidone%%'
       ) AS flag_inidoneidade,
       COALESCE(meg.flag_divida_pgfn, FALSE) AS flag_pgfn,
       COALESCE(meg.flag_inativa, FALSE) AS flag_inativa,
       EXISTS(
           SELECT 1 FROM tce_pb_despesa d2
           JOIN (
               SELECT LEFT(cpf_cnpj_sancionado, 8) AS cb, dt_inicio_sancao, dt_final_sancao FROM ceis_sancao
               UNION ALL
               SELECT LEFT(cpf_cnpj_sancionado, 8), dt_inicio_sancao, dt_final_sancao FROM cnep_sancao
           ) san ON san.cb = d2.cnpj_basico
           WHERE d2.cnpj_basico = tf.cnpj_basico
             AND d2.municipio = %(municipio)s
             AND d2.valor_pago > 0
             AND d2.data_empenho >= san.dt_inicio_sancao
             AND (san.dt_final_sancao IS NULL OR d2.data_empenho <= san.dt_final_sancao)
             AND d2.data_empenho >= %(data_inicio)s AND d2.data_empenho <= %(data_fim)s
       ) AS flag_recebeu_durante_sancao,
       CASE est.situacao_cadastral::text
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE COALESCE('Sit. ' || est.situacao_cadastral::text, '-')
       END AS desc_situacao
FROM top_forn tf
LEFT JOIN mv_empresa_governo meg ON meg.cnpj_basico = tf.cnpj_basico
LEFT JOIN empresa e ON e.cnpj_basico = tf.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_basico = tf.cnpj_basico AND est.cnpj_ordem = '0001'
ORDER BY flag_recebeu_durante_sancao DESC, tf.total_pago DESC
"""

TOP_FORNECEDORES_FALLBACK_DATED = """
WITH top_forn AS (
    SELECT d.cnpj_basico, d.nome_credor,
           SUM(d.valor_pago) AS total_pago,
           COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos
    FROM tce_pb_despesa d
    JOIN empresa e2 ON e2.cnpj_basico = d.cnpj_basico
        AND e2.natureza_juridica NOT LIKE '1%%'
    WHERE d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND d.cnpj_basico IS NOT NULL
      AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
    GROUP BY d.cnpj_basico, d.nome_credor
    ORDER BY SUM(d.valor_pago) DESC
    LIMIT 200
)
SELECT tf.cnpj_basico, tf.nome_credor, e.razao_social,
       est.cnpj_completo,
       tf.total_pago, tf.qtd_empenhos,
       EXISTS(
           SELECT 1 FROM ceis_sancao cs
           WHERE LEFT(cs.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND (cs.dt_final_sancao IS NULL OR cs.dt_final_sancao >= CURRENT_DATE)
       ) AS flag_ceis,
       EXISTS(
           SELECT 1 FROM cnep_sancao cn
           WHERE LEFT(cn.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND (cn.dt_final_sancao IS NULL OR cn.dt_final_sancao >= CURRENT_DATE)
       ) AS flag_cnep,
       EXISTS(
           SELECT 1 FROM ceis_sancao cs2
           WHERE LEFT(cs2.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND (cs2.dt_final_sancao IS NULL OR cs2.dt_final_sancao >= CURRENT_DATE)
             AND cs2.categoria_sancao ILIKE '%%inidone%%'
       ) AS flag_inidoneidade,
       EXISTS(
           SELECT 1 FROM pgfn_divida pg
           WHERE LEFT(pg.cpf_cnpj_norm, 8) = tf.cnpj_basico
             AND LENGTH(pg.cpf_cnpj_norm) = 14
       ) AS flag_pgfn,
       COALESCE(est.situacao_cadastral != '2', FALSE) AS flag_inativa,
       EXISTS(
           SELECT 1 FROM tce_pb_despesa d2
           JOIN (
               SELECT LEFT(cpf_cnpj_sancionado, 8) AS cb, dt_inicio_sancao, dt_final_sancao FROM ceis_sancao
               UNION ALL
               SELECT LEFT(cpf_cnpj_sancionado, 8), dt_inicio_sancao, dt_final_sancao FROM cnep_sancao
           ) san ON san.cb = d2.cnpj_basico
           WHERE d2.cnpj_basico = tf.cnpj_basico
             AND d2.municipio = %(municipio)s
             AND d2.valor_pago > 0
             AND d2.data_empenho >= san.dt_inicio_sancao
             AND (san.dt_final_sancao IS NULL OR d2.data_empenho <= san.dt_final_sancao)
             AND d2.data_empenho >= %(data_inicio)s AND d2.data_empenho <= %(data_fim)s
       ) AS flag_recebeu_durante_sancao,
       CASE est.situacao_cadastral::text
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE COALESCE('Sit. ' || est.situacao_cadastral::text, '-')
       END AS desc_situacao
FROM top_forn tf
LEFT JOIN empresa e ON e.cnpj_basico = tf.cnpj_basico
LEFT JOIN estabelecimento est
    ON est.cnpj_basico = tf.cnpj_basico
   AND est.cnpj_ordem = '0001'
ORDER BY flag_recebeu_durante_sancao DESC, tf.total_pago DESC
"""

TOP_FORNECEDORES_BASIC_DATED = """
SELECT d.cnpj_basico, d.nome_credor, e.razao_social,
       est.cnpj_completo,
       SUM(d.valor_pago) AS total_pago,
       COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos,
       FALSE AS flag_ceis,
       FALSE AS flag_cnep,
       FALSE AS flag_inidoneidade,
       FALSE AS flag_pgfn,
       FALSE AS flag_inativa,
       FALSE AS flag_recebeu_durante_sancao,
       CASE est.situacao_cadastral::text
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE COALESCE('Sit. ' || est.situacao_cadastral::text, '-')
       END AS desc_situacao
FROM tce_pb_despesa d
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
    AND e.natureza_juridica NOT LIKE '1%%'
LEFT JOIN estabelecimento est ON est.cnpj_basico = d.cnpj_basico AND est.cnpj_ordem = '0001'
WHERE d.municipio = %(municipio)s
  AND d.valor_pago > 0
  AND d.cnpj_basico IS NOT NULL
  AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
GROUP BY d.cnpj_basico, d.nome_credor, e.razao_social, est.cnpj_completo, est.situacao_cadastral
ORDER BY (COALESCE(est.situacao_cadastral::text != '2', FALSE))::int DESC, SUM(d.valor_pago) DESC
LIMIT 200
"""

TOP_FORNECEDORES_PNCP = """
SELECT pc.cnpj_basico_fornecedor AS cnpj_basico,
       pc.nome_fornecedor AS nome_credor,
       e.razao_social,
       est.cnpj_completo,
       SUM(pc.valor_global) AS total_contratado,
       COUNT(*) AS qtd_contratos,
       EXISTS(
           SELECT 1 FROM ceis_sancao cs
           WHERE LEFT(cs.cpf_cnpj_sancionado, 8) = pc.cnpj_basico_fornecedor
             AND (cs.dt_final_sancao IS NULL OR cs.dt_final_sancao >= CURRENT_DATE)
       ) AS flag_ceis,
       EXISTS(
           SELECT 1 FROM cnep_sancao cn
           WHERE LEFT(cn.cpf_cnpj_sancionado, 8) = pc.cnpj_basico_fornecedor
             AND (cn.dt_final_sancao IS NULL OR cn.dt_final_sancao >= CURRENT_DATE)
       ) AS flag_cnep,
       EXISTS(
           SELECT 1 FROM ceis_sancao cs2
           WHERE LEFT(cs2.cpf_cnpj_sancionado, 8) = pc.cnpj_basico_fornecedor
             AND (cs2.dt_final_sancao IS NULL OR cs2.dt_final_sancao >= CURRENT_DATE)
             AND cs2.categoria_sancao ILIKE '%%inidone%%'
       ) AS flag_inidoneidade,
       EXISTS(
           SELECT 1 FROM pgfn_divida pg
           WHERE LEFT(pg.cpf_cnpj_norm, 8) = pc.cnpj_basico_fornecedor
             AND LENGTH(pg.cpf_cnpj_norm) = 14
       ) AS flag_pgfn,
       COALESCE(est.situacao_cadastral != '2', FALSE) AS flag_inativa,
       EXISTS(
           SELECT 1 FROM pncp_contrato pc2
           JOIN (
               SELECT LEFT(cpf_cnpj_sancionado, 8) AS cb, dt_inicio_sancao, dt_final_sancao FROM ceis_sancao
               UNION ALL
               SELECT LEFT(cpf_cnpj_sancionado, 8), dt_inicio_sancao, dt_final_sancao FROM cnep_sancao
           ) san ON san.cb = pc2.cnpj_basico_fornecedor
           WHERE pc2.cnpj_basico_fornecedor = pc.cnpj_basico_fornecedor
             AND pc2.municipio_nome = %(municipio)s AND pc2.uf = %(uf)s
             AND pc2.data_assinatura >= san.dt_inicio_sancao
             AND (san.dt_final_sancao IS NULL OR pc2.data_assinatura <= san.dt_final_sancao)
       ) AS flag_recebeu_durante_sancao,
       CASE est.situacao_cadastral::text
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE COALESCE('Sit. ' || est.situacao_cadastral::text, '-')
       END AS desc_situacao
FROM pncp_contrato pc
LEFT JOIN empresa e ON e.cnpj_basico = pc.cnpj_basico_fornecedor
LEFT JOIN estabelecimento est
    ON est.cnpj_basico = pc.cnpj_basico_fornecedor
   AND est.cnpj_ordem = '0001'
WHERE pc.municipio_nome = %(municipio)s AND pc.uf = %(uf)s
  AND pc.cnpj_basico_fornecedor IS NOT NULL
GROUP BY pc.cnpj_basico_fornecedor, pc.nome_fornecedor,
         e.razao_social, est.cnpj_completo, est.situacao_cadastral
ORDER BY flag_recebeu_durante_sancao DESC, total_contratado DESC
LIMIT 200
"""

TOP_SERVIDORES_RISCO = """
WITH cnpjs_sancionados AS (
    SELECT DISTINCT LEFT(cpf_cnpj_sancionado, 8) AS cb FROM ceis_sancao
    WHERE dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE
    UNION
    SELECT DISTINCT LEFT(cpf_cnpj_sancionado, 8) FROM cnep_sancao
    WHERE dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE
),
cnpjs_inidoneidade AS (
    SELECT DISTINCT LEFT(cpf_cnpj_sancionado, 8) AS cb FROM ceis_sancao
    WHERE (dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE)
      AND categoria_sancao ILIKE '%%inidone%%'
)
SELECT cpf_digitos_6, nome_upper, nome_servidor,
       municipios, maior_salario, cargo,
       qtd_empresas_socio, cnpjs_socio,
       flag_conflito_interesses, flag_multi_empresa,
       flag_bolsa_familia, flag_duplo_vinculo_estado,
       flag_alto_salario_socio,
       risco_score,
       EXISTS(
           SELECT 1 FROM unnest(cnpjs_socio) AS cs(cnpj)
           JOIN cnpjs_sancionados san ON san.cb = TRIM(cs.cnpj)
       ) AS flag_socio_sancionado,
       EXISTS(
           SELECT 1 FROM unnest(cnpjs_socio) AS cs(cnpj)
           JOIN cnpjs_inidoneidade ini ON ini.cb = TRIM(cs.cnpj)
       ) AS flag_socio_inidoneidade
FROM mv_servidor_pb_risco
WHERE %(municipio)s = ANY(municipios)
ORDER BY flag_socio_sancionado DESC, risco_score DESC
LIMIT 200
"""

AUTOCOMPLETE_MUNICIPIO_FALLBACK = """
SELECT municipio_nome AS nome, uf, 0 AS rank_val
FROM pncp_municipio
WHERE unaccent(municipio_nome) ILIKE unaccent(%(q)s) || '%%'
ORDER BY nome
LIMIT %(limit)s
"""

AUTOCOMPLETE_MUNICIPIO = """
(
    SELECT municipio AS nome, 'PB' AS uf, risco_score AS rank_val
    FROM mv_municipio_pb_risco
    WHERE unaccent(municipio) ILIKE unaccent(%(q)s) || '%%'
)
UNION
(
    SELECT municipio_nome AS nome, uf, 0 AS rank_val
    FROM pncp_municipio
    WHERE unaccent(municipio_nome) ILIKE unaccent(%(q)s) || '%%'
      AND NOT EXISTS (
          SELECT 1 FROM mv_municipio_pb_risco m
          WHERE m.municipio = pncp_municipio.municipio_nome AND pncp_municipio.uf = 'PB'
      )
    LIMIT 50
)
ORDER BY rank_val DESC, nome
LIMIT %(limit)s
"""
