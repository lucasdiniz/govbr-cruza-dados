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
       COALESCE(meg.flag_divida_pgfn, FALSE) AS flag_pgfn,
       COALESCE(meg.flag_inativa, FALSE) AS flag_inativa,
       CASE est.situacao_cadastral
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE 'Sit. ' || COALESCE(est.situacao_cadastral, '?')
       END AS desc_situacao
FROM top_forn tf
LEFT JOIN mv_empresa_governo meg ON meg.cnpj_basico = tf.cnpj_basico
LEFT JOIN empresa e ON e.cnpj_basico = tf.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_basico = tf.cnpj_basico AND est.cnpj_ordem = '0001'
ORDER BY tf.total_pago DESC
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
           FROM pgfn_divida pg
           WHERE LEFT(pg.cpf_cnpj_norm, 8) = tf.cnpj_basico
             AND LENGTH(pg.cpf_cnpj_norm) = 14
       ) AS flag_pgfn,
       COALESCE(est.situacao_cadastral != '2', FALSE) AS flag_inativa,
       CASE est.situacao_cadastral
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE 'Sit. ' || COALESCE(est.situacao_cadastral, '?')
       END AS desc_situacao
FROM top_forn tf
LEFT JOIN empresa e ON e.cnpj_basico = tf.cnpj_basico
LEFT JOIN estabelecimento est
    ON est.cnpj_basico = tf.cnpj_basico
   AND est.cnpj_ordem = '0001'
ORDER BY tf.total_pago DESC
"""

TOP_FORNECEDORES_BASIC = """
SELECT d.cnpj_basico, d.nome_credor, e.razao_social,
       est.cnpj_completo,
       SUM(d.valor_pago) AS total_pago,
       COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos,
       FALSE AS flag_ceis,
       FALSE AS flag_pgfn,
       FALSE AS flag_inativa,
       CASE est.situacao_cadastral
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE 'Sit. ' || COALESCE(est.situacao_cadastral, '?')
       END AS desc_situacao
FROM tce_pb_despesa d
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
    AND e.natureza_juridica NOT LIKE '1%%'
LEFT JOIN estabelecimento est ON est.cnpj_basico = d.cnpj_basico AND est.cnpj_ordem = '0001'
WHERE d.municipio = %(municipio)s
  AND d.valor_pago > 0
  AND d.cnpj_basico IS NOT NULL
GROUP BY d.cnpj_basico, d.nome_credor, e.razao_social, est.cnpj_completo, est.situacao_cadastral
ORDER BY SUM(d.valor_pago) DESC
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
           SELECT 1 FROM pgfn_divida pg
           WHERE LEFT(pg.cpf_cnpj_norm, 8) = pc.cnpj_basico_fornecedor
             AND LENGTH(pg.cpf_cnpj_norm) = 14
       ) AS flag_pgfn,
       COALESCE(est.situacao_cadastral != '2', FALSE) AS flag_inativa,
       CASE est.situacao_cadastral
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE 'Sit. ' || COALESCE(est.situacao_cadastral, '?')
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
ORDER BY total_contratado DESC
LIMIT 200
"""

TOP_SERVIDORES_RISCO = """
SELECT cpf_digitos_6, nome_upper, nome_servidor,
       municipios, maior_salario, cargo,
       qtd_empresas_socio, cnpjs_socio,
       flag_conflito_interesses, flag_multi_empresa,
       flag_bolsa_familia, flag_duplo_vinculo_estado,
       flag_alto_salario_socio,
       risco_score
FROM mv_servidor_pb_risco
WHERE %(municipio)s = ANY(municipios)
ORDER BY risco_score DESC
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
