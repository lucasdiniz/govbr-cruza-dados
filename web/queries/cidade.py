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

TOP_FORNECEDORES = """
WITH top_forn AS (
    SELECT d.cnpj_basico, d.nome_credor,
           SUM(d.valor_pago) AS total_pago,
           COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos
    FROM tce_pb_despesa d
    WHERE d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND d.cnpj_basico IS NOT NULL
    GROUP BY d.cnpj_basico, d.nome_credor
    ORDER BY SUM(d.valor_pago) DESC
    LIMIT 10
)
SELECT tf.cnpj_basico, tf.nome_credor, tf.total_pago, tf.qtd_empenhos,
       COALESCE(meg.flag_ceis_vigente, FALSE) AS flag_ceis,
       COALESCE(meg.flag_divida_pgfn, FALSE) AS flag_pgfn,
       COALESCE(meg.flag_inativa, FALSE) AS flag_inativa
FROM top_forn tf
LEFT JOIN mv_empresa_governo meg ON meg.cnpj_basico = tf.cnpj_basico
ORDER BY tf.total_pago DESC
"""

TOP_FORNECEDORES_FALLBACK = """
WITH top_forn AS (
    SELECT d.cnpj_basico, d.nome_credor,
           SUM(d.valor_pago) AS total_pago,
           COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos
    FROM tce_pb_despesa d
    WHERE d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND d.cnpj_basico IS NOT NULL
    GROUP BY d.cnpj_basico, d.nome_credor
    ORDER BY SUM(d.valor_pago) DESC
    LIMIT 10
)
SELECT tf.cnpj_basico, tf.nome_credor, tf.total_pago, tf.qtd_empenhos,
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
       COALESCE(est.situacao_cadastral != '2', FALSE) AS flag_inativa
FROM top_forn tf
LEFT JOIN estabelecimento est
    ON est.cnpj_basico = tf.cnpj_basico
   AND est.cnpj_ordem = '0001'
ORDER BY tf.total_pago DESC
"""

TOP_FORNECEDORES_BASIC = """
SELECT d.cnpj_basico, d.nome_credor,
       SUM(d.valor_pago) AS total_pago,
       COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos,
       FALSE AS flag_ceis,
       FALSE AS flag_pgfn,
       FALSE AS flag_inativa
FROM tce_pb_despesa d
WHERE d.municipio = %(municipio)s
  AND d.valor_pago > 0
  AND d.cnpj_basico IS NOT NULL
GROUP BY d.cnpj_basico, d.nome_credor
ORDER BY SUM(d.valor_pago) DESC
LIMIT 10
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
LIMIT 10
"""

AUTOCOMPLETE_MUNICIPIO = """
SELECT municipio
FROM mv_municipio_pb_risco
WHERE unaccent(municipio) ILIKE unaccent(%(q)s) || '%%'
ORDER BY risco_score DESC
LIMIT %(limit)s
"""
