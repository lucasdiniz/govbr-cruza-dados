"""SQL parametrizado para modo cidade."""

# Fragmento reusavel: flags que verificam se o empenho DESTE municipio ocorreu
# dentro do periodo de uma sancao que afeta contratos com este municipio.
# Usado em TOP_FORNECEDORES* (PB) onde tf.cnpj_basico esta disponivel.
_FLAGS_SANCAO_DURANTE_PB = """,
       EXISTS (
           SELECT 1
           FROM tce_pb_despesa d2
           JOIN ceis_sancao cs ON LEFT(cs.cpf_cnpj_sancionado, 8) = d2.cnpj_basico
                              AND LENGTH(cs.cpf_cnpj_sancionado) = 14
           WHERE d2.municipio = %(municipio)s
             AND d2.cnpj_basico = tf.cnpj_basico
             AND d2.valor_empenhado > 0
             AND d2.data_empenho IS NOT NULL
             AND d2.data_empenho >= cs.dt_inicio_sancao
             AND (cs.dt_final_sancao IS NULL OR d2.data_empenho <= cs.dt_final_sancao)
             AND cs.categoria_sancao ILIKE '%%inidone%%'
       ) AS flag_recebeu_durante_inidoneidade,
       EXISTS (
           SELECT 1
           FROM tce_pb_despesa d2
           JOIN (
               SELECT LEFT(cpf_cnpj_sancionado, 8) AS cb,
                      dt_inicio_sancao, dt_final_sancao,
                      categoria_sancao, abrangencia_sancao,
                      esfera_orgao_sancionador, orgao_sancionador
               FROM ceis_sancao WHERE LENGTH(cpf_cnpj_sancionado) = 14
               UNION ALL
               SELECT LEFT(cpf_cnpj_sancionado, 8),
                      dt_inicio_sancao, dt_final_sancao,
                      categoria_sancao, abrangencia_sancao,
                      esfera_orgao_sancionador, orgao_sancionador
               FROM cnep_sancao WHERE LENGTH(cpf_cnpj_sancionado) = 14
           ) san ON san.cb = d2.cnpj_basico
           WHERE d2.municipio = %(municipio)s
             AND d2.cnpj_basico = tf.cnpj_basico
             AND d2.valor_empenhado > 0
             AND d2.data_empenho IS NOT NULL
             AND d2.data_empenho >= san.dt_inicio_sancao
             AND (san.dt_final_sancao IS NULL OR d2.data_empenho <= san.dt_final_sancao)
             AND (
                 san.categoria_sancao ILIKE '%%inidone%%'
                 OR san.abrangencia_sancao = 'Todas as Esferas em todos os Poderes'
                 OR (san.esfera_orgao_sancionador = 'MUNICIPAL'
                     AND UPPER(san.orgao_sancionador) LIKE '%%' || UPPER(%(municipio)s) || '%%')
             )
       ) AS flag_recebeu_durante_sancao_aplicavel"""

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

# Agregados da Paraiba inteira — usados para contexto comparativo na narrativa.
# Cached em memoria por 6h (ver get_pb_medias em web/routes/cidade.py).
PB_MEDIAS = """
SELECT
    COUNT(*)::int                                        AS n_municipios,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY risco_score)         AS mediana_risco,
    AVG(risco_score)                                     AS media_risco,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pct_sem_licitacao)   AS mediana_pct_sem_licitacao,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pct_folha_receita)   AS mediana_pct_folha,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pct_proponente_unico) AS mediana_pct_proponente_unico,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_pago)          AS mediana_total_pago
FROM mv_municipio_pb_risco
WHERE risco_score IS NOT NULL
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
       (SELECT SUM(valor) FROM tce_pb_receita
        WHERE unaccent(municipio) = unaccent(%(municipio)s)
          AND tipo_atualizacao_receita ILIKE 'Lançamento de Receita'
          AND ano >= %(ano_inicio)s AND ano <= %(ano_fim)s
       ) AS receita_arrecadada,
       (SELECT SUM(valor_vantagem) FROM tce_pb_servidor
        WHERE unaccent(municipio) = unaccent(%(municipio)s)
          AND ano_mes >= REPLACE(%(ano_mes_inicio)s, '-', '')
          AND ano_mes <= REPLACE(%(ano_mes_fim)s, '-', '')
       ) AS total_folha,
       (SELECT ROUND(100.0 * COALESCE(
            (SELECT SUM(valor_vantagem) FROM tce_pb_servidor
             WHERE unaccent(municipio) = unaccent(%(municipio)s)
               AND ano_mes >= REPLACE(%(ano_mes_inicio)s, '-', '')
               AND ano_mes <= REPLACE(%(ano_mes_fim)s, '-', '')), 0)
          / NULLIF(
            (SELECT SUM(valor) FROM tce_pb_receita
             WHERE unaccent(municipio) = unaccent(%(municipio)s)
               AND tipo_atualizacao_receita ILIKE 'Lançamento de Receita'
               AND ano >= %(ano_inicio)s AND ano <= %(ano_fim)s), 0), 1)
       ) AS pct_folha_receita,
       NULL::numeric AS risco_score
FROM tce_pb_despesa d
WHERE d.municipio = %(municipio)s
  AND d.data_empenho >= %(data_inicio)s
  AND d.data_empenho <= %(data_fim)s
  AND d.valor_empenhado > 0
"""

HEATMAP_MENSAL = """
SELECT ano::int AS ano,
       LEFT(mes, 2)::int AS mes,
       SUM(valor_empenhado) AS total_empenhado,
       SUM(valor_pago) AS total_pago,
       COUNT(*) AS qtd
FROM tce_pb_despesa
WHERE municipio = %(municipio)s
  AND ano >= 2022
  AND mes IS NOT NULL
  AND valor_empenhado > 0
GROUP BY ano, LEFT(mes, 2)
ORDER BY ano, mes
"""

HEATMAP_MES_RESUMO = """
SELECT COALESCE(SUM(valor_empenhado), 0) AS total_empenhado,
       COALESCE(SUM(valor_pago), 0) AS total_pago,
       COUNT(*) AS qtd_empenhos,
       COUNT(DISTINCT cpf_cnpj) AS qtd_fornecedores
FROM tce_pb_despesa
WHERE municipio = %(municipio)s
  AND ano = %(ano)s
  AND LEFT(mes, 2) = %(mes)s
  AND valor_empenhado > 0
"""

HEATMAP_MES_FORNECEDORES = """
SELECT d.cpf_cnpj,
       MAX(d.nome_credor) AS nome_credor,
       SUM(d.valor_empenhado) AS total_empenhado,
       SUM(d.valor_pago) AS total_pago,
       COUNT(*) AS qtd_empenhos,
       EXISTS (
           SELECT 1 FROM estabelecimento e
           WHERE e.cnpj_completo = d.cpf_cnpj
       ) AS eh_pj
FROM tce_pb_despesa d
WHERE d.municipio = %(municipio)s
  AND d.ano = %(ano)s
  AND LEFT(d.mes, 2) = %(mes)s
  AND d.valor_empenhado > 0
  AND d.cpf_cnpj IS NOT NULL
GROUP BY d.cpf_cnpj
ORDER BY total_empenhado DESC
LIMIT 20
"""

HEATMAP_MES_ELEMENTOS = """
SELECT elemento_despesa,
       SUM(valor_empenhado) AS total_empenhado,
       SUM(valor_pago) AS total_pago,
       COUNT(*) AS qtd_empenhos
FROM tce_pb_despesa
WHERE municipio = %(municipio)s
  AND ano = %(ano)s
  AND LEFT(mes, 2) = %(mes)s
  AND valor_empenhado > 0
  AND elemento_despesa IS NOT NULL
GROUP BY elemento_despesa
ORDER BY total_empenhado DESC
LIMIT 10
"""

HEATMAP_MES_FUNCOES = """
SELECT COALESCE(funcao, 'Nao informada') AS funcao,
       COALESCE(programa, 'Nao informado') AS programa,
       SUM(valor_empenhado) AS total_empenhado,
       SUM(valor_pago) AS total_pago,
       COUNT(*) AS qtd_empenhos
FROM tce_pb_despesa
WHERE municipio = %(municipio)s
  AND ano = %(ano)s
  AND LEFT(mes, 2) = %(mes)s
  AND valor_empenhado > 0
GROUP BY COALESCE(funcao, 'Nao informada'), COALESCE(programa, 'Nao informado')
ORDER BY total_empenhado DESC
LIMIT 10
"""

HEATMAP_MES_MODALIDADES = """
SELECT COALESCE(NULLIF(TRIM(modalidade_licitacao), ''), 'Sem licitacao informada') AS modalidade,
       SUM(valor_empenhado) AS total_empenhado,
       COUNT(*) AS qtd_empenhos,
       COUNT(DISTINCT numero_licitacao) FILTER (WHERE numero_licitacao IS NOT NULL AND TRIM(numero_licitacao) <> '') AS qtd_licitacoes
FROM tce_pb_despesa
WHERE municipio = %(municipio)s
  AND ano = %(ano)s
  AND LEFT(mes, 2) = %(mes)s
  AND valor_empenhado > 0
GROUP BY COALESCE(NULLIF(TRIM(modalidade_licitacao), ''), 'Sem licitacao informada')
ORDER BY total_empenhado DESC
"""

HEATMAP_MES_EMPENHOS = """
SELECT id,
       numero_empenho,
       data_empenho,
       nome_credor,
       cpf_cnpj,
       elemento_despesa,
       funcao,
       programa,
       modalidade_licitacao,
       numero_licitacao,
       valor_empenhado,
       valor_liquidado,
       valor_pago,
       LEFT(COALESCE(historico, ''), 160) AS historico_resumo
FROM tce_pb_despesa
WHERE municipio = %(municipio)s
  AND ano = %(ano)s
  AND LEFT(mes, 2) = %(mes)s
  AND valor_empenhado > 0
ORDER BY valor_empenhado DESC
LIMIT 50
"""

PERFIL_MUNICIPIO_PNCP = None  # deprecated: non-PB removed from frontend

TOP_FORNECEDORES = """
WITH top_forn AS (
    SELECT d.cnpj_basico, d.nome_credor,
           MAX(d.cpf_cnpj) AS cpf_cnpj,
           SUM(d.valor_pago) AS total_pago,
           COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos
    FROM tce_pb_despesa d
    JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
        AND e.natureza_juridica NOT LIKE '1%%'
    WHERE d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND d.cnpj_basico IS NOT NULL
      AND EXISTS (SELECT 1 FROM estabelecimento est WHERE est.cnpj_completo = d.cpf_cnpj)
    GROUP BY d.cnpj_basico, d.nome_credor
    ORDER BY SUM(d.valor_pago) DESC
    LIMIT 200
)
SELECT * FROM (
    SELECT tf.cnpj_basico, tf.nome_credor,
       CASE WHEN est.cnpj_completo IS NOT NULL THEN e.razao_social END AS razao_social,
       COALESCE(est.cnpj_completo, tf.cpf_cnpj) AS cnpj_completo,
       tf.total_pago, tf.qtd_empenhos,
       COALESCE(meg.flag_ceis_vigente, FALSE) AS flag_ceis,
       COALESCE(meg.flag_cnep_vigente, FALSE) AS flag_cnep,
       EXISTS(
           SELECT 1 FROM ceis_sancao cs
           WHERE LEFT(cs.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND LENGTH(cs.cpf_cnpj_sancionado) = 14
             AND (cs.dt_final_sancao IS NULL OR cs.dt_final_sancao >= CURRENT_DATE)
             AND cs.categoria_sancao ILIKE '%%inidone%%'
       ) AS flag_inidoneidade,
       COALESCE(meg.flag_divida_pgfn, FALSE) AS flag_pgfn,
       COALESCE(meg.flag_inativa, FALSE) AS flag_inativa,
       EXISTS(
           SELECT 1 FROM acordo_leniencia al
           WHERE LEFT(al.cnpj_norm, 8) = tf.cnpj_basico
             AND al.situacao_acordo NOT IN ('Cumprido', 'Encerrado')
       ) AS flag_acordo_leniencia,
       (
           SELECT CASE
               WHEN san.categoria_sancao ILIKE '%%inidone%%'
                   THEN '!Nacional (Inidoneidade)'
               WHEN san.abrangencia_sancao = 'Todas as Esferas em todos os Poderes'
                   THEN '!' || san.abrangencia_sancao
               WHEN san.esfera_orgao_sancionador = 'MUNICIPAL'
                    AND UPPER(san.orgao_sancionador) LIKE '%%' || UPPER(%(municipio)s) || '%%'
                   THEN '!' || COALESCE(san.abrangencia_sancao, 'Sem Informação')
                        || ' (' || san.orgao_sancionador || ')'
               ELSE COALESCE(san.abrangencia_sancao, 'Sem Informação')
                    || ' (' || COALESCE(san.orgao_sancionador, '?')
                    || COALESCE(' - ' || san.uf_orgao_sancionador, '') || ')'
           END
           FROM (
               SELECT LEFT(cpf_cnpj_sancionado, 8) AS cb,
                      categoria_sancao, abrangencia_sancao,
                      orgao_sancionador, uf_orgao_sancionador,
                      esfera_orgao_sancionador
               FROM ceis_sancao
               WHERE LENGTH(cpf_cnpj_sancionado) = 14
               UNION ALL
               SELECT LEFT(cpf_cnpj_sancionado, 8),
                      categoria_sancao, abrangencia_sancao,
                      orgao_sancionador, uf_orgao_sancionador,
                      esfera_orgao_sancionador
               FROM cnep_sancao
               WHERE LENGTH(cpf_cnpj_sancionado) = 14
           ) san
           WHERE san.cb = tf.cnpj_basico
           ORDER BY CASE
               WHEN san.categoria_sancao ILIKE '%%inidone%%' THEN 1
               WHEN san.abrangencia_sancao = 'Todas as Esferas em todos os Poderes' THEN 2
               WHEN san.esfera_orgao_sancionador = 'MUNICIPAL' THEN 3
               ELSE 4
           END
           LIMIT 1
       ) AS abrangencia_sancao_info,
       CASE est.situacao_cadastral::text
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE COALESCE('Sit. ' || est.situacao_cadastral::text, '-')
       END AS desc_situacao
FROM top_forn tf
LEFT JOIN mv_empresa_governo meg ON meg.cnpj_basico = tf.cnpj_basico
LEFT JOIN empresa e ON e.cnpj_basico = tf.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_completo = tf.cpf_cnpj
) q
ORDER BY q.abrangencia_sancao_info IS NOT NULL DESC, q.total_pago DESC
"""

TOP_FORNECEDORES_FALLBACK = """
WITH top_forn AS (
    SELECT d.cnpj_basico, d.nome_credor,
           MAX(d.cpf_cnpj) AS cpf_cnpj,
           SUM(d.valor_pago) AS total_pago,
           COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos
    FROM tce_pb_despesa d
    JOIN empresa e2 ON e2.cnpj_basico = d.cnpj_basico
        AND e2.natureza_juridica NOT LIKE '1%%'
    WHERE d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND d.cnpj_basico IS NOT NULL
      AND EXISTS (SELECT 1 FROM estabelecimento est WHERE est.cnpj_completo = d.cpf_cnpj)
    GROUP BY d.cnpj_basico, d.nome_credor
    ORDER BY SUM(d.valor_pago) DESC
    LIMIT 200
)
SELECT * FROM (
    SELECT tf.cnpj_basico, tf.nome_credor,
       CASE WHEN est.cnpj_completo IS NOT NULL THEN e.razao_social END AS razao_social,
       COALESCE(est.cnpj_completo, tf.cpf_cnpj) AS cnpj_completo,
       tf.total_pago, tf.qtd_empenhos,
       EXISTS(
           SELECT 1
           FROM ceis_sancao cs
           WHERE LEFT(cs.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND LENGTH(cs.cpf_cnpj_sancionado) = 14
             AND (cs.dt_final_sancao IS NULL OR cs.dt_final_sancao >= CURRENT_DATE)
       ) AS flag_ceis,
       EXISTS(
           SELECT 1
           FROM cnep_sancao cn
           WHERE LEFT(cn.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND LENGTH(cn.cpf_cnpj_sancionado) = 14
             AND (cn.dt_final_sancao IS NULL OR cn.dt_final_sancao >= CURRENT_DATE)
       ) AS flag_cnep,
       EXISTS(
           SELECT 1 FROM ceis_sancao cs2
           WHERE LEFT(cs2.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND LENGTH(cs2.cpf_cnpj_sancionado) = 14
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
           SELECT 1 FROM acordo_leniencia al
           WHERE LEFT(al.cnpj_norm, 8) = tf.cnpj_basico
             AND al.situacao_acordo NOT IN ('Cumprido', 'Encerrado')
       ) AS flag_acordo_leniencia,
       (
           SELECT CASE
               WHEN san.categoria_sancao ILIKE '%%inidone%%'
                   THEN '!Nacional (Inidoneidade)'
               WHEN san.abrangencia_sancao = 'Todas as Esferas em todos os Poderes'
                   THEN '!' || san.abrangencia_sancao
               WHEN san.esfera_orgao_sancionador = 'MUNICIPAL'
                    AND UPPER(san.orgao_sancionador) LIKE '%%' || UPPER(%(municipio)s) || '%%'
                   THEN '!' || COALESCE(san.abrangencia_sancao, 'Sem Informação')
                        || ' (' || san.orgao_sancionador || ')'
               ELSE COALESCE(san.abrangencia_sancao, 'Sem Informação')
                    || ' (' || COALESCE(san.orgao_sancionador, '?')
                    || COALESCE(' - ' || san.uf_orgao_sancionador, '') || ')'
           END
           FROM (
               SELECT LEFT(cpf_cnpj_sancionado, 8) AS cb,
                      categoria_sancao, abrangencia_sancao,
                      orgao_sancionador, uf_orgao_sancionador,
                      esfera_orgao_sancionador
               FROM ceis_sancao
               WHERE LENGTH(cpf_cnpj_sancionado) = 14
               UNION ALL
               SELECT LEFT(cpf_cnpj_sancionado, 8),
                      categoria_sancao, abrangencia_sancao,
                      orgao_sancionador, uf_orgao_sancionador,
                      esfera_orgao_sancionador
               FROM cnep_sancao
               WHERE LENGTH(cpf_cnpj_sancionado) = 14
           ) san
           WHERE san.cb = tf.cnpj_basico
           ORDER BY CASE
               WHEN san.categoria_sancao ILIKE '%%inidone%%' THEN 1
               WHEN san.abrangencia_sancao = 'Todas as Esferas em todos os Poderes' THEN 2
               WHEN san.esfera_orgao_sancionador = 'MUNICIPAL' THEN 3
               ELSE 4
           END
           LIMIT 1
       ) AS abrangencia_sancao_info,
       CASE est.situacao_cadastral::text
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE COALESCE('Sit. ' || est.situacao_cadastral::text, '-')
       END AS desc_situacao
FROM top_forn tf
LEFT JOIN empresa e ON e.cnpj_basico = tf.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_completo = tf.cpf_cnpj
) q
ORDER BY q.abrangencia_sancao_info IS NOT NULL DESC, q.total_pago DESC
"""

# ── Variantes com filtro temporal (dated) ───────────────────────

TOP_FORNECEDORES_DATED = """
WITH top_forn AS (
    SELECT d.cnpj_basico, d.nome_credor,
           MAX(d.cpf_cnpj) AS cpf_cnpj,
           SUM(d.valor_pago) AS total_pago,
           COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos
    FROM tce_pb_despesa d
    JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
        AND e.natureza_juridica NOT LIKE '1%%'
    WHERE d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND d.cnpj_basico IS NOT NULL
      AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
      AND EXISTS (SELECT 1 FROM estabelecimento est WHERE est.cnpj_completo = d.cpf_cnpj)
    GROUP BY d.cnpj_basico, d.nome_credor
    ORDER BY SUM(d.valor_pago) DESC
    LIMIT 200
)
SELECT * FROM (
    SELECT tf.cnpj_basico, tf.nome_credor,
       CASE WHEN est.cnpj_completo IS NOT NULL THEN e.razao_social END AS razao_social,
       COALESCE(est.cnpj_completo, tf.cpf_cnpj) AS cnpj_completo,
       tf.total_pago, tf.qtd_empenhos,
       COALESCE(meg.flag_ceis_vigente, FALSE) AS flag_ceis,
       COALESCE(meg.flag_cnep_vigente, FALSE) AS flag_cnep,
       EXISTS(
           SELECT 1 FROM ceis_sancao cs
           WHERE LEFT(cs.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND LENGTH(cs.cpf_cnpj_sancionado) = 14
             AND (cs.dt_final_sancao IS NULL OR cs.dt_final_sancao >= CURRENT_DATE)
             AND cs.categoria_sancao ILIKE '%%inidone%%'
       ) AS flag_inidoneidade,
       COALESCE(meg.flag_divida_pgfn, FALSE) AS flag_pgfn,
       COALESCE(meg.flag_inativa, FALSE) AS flag_inativa,
       EXISTS(
           SELECT 1 FROM acordo_leniencia al
           WHERE LEFT(al.cnpj_norm, 8) = tf.cnpj_basico
             AND al.situacao_acordo NOT IN ('Cumprido', 'Encerrado')
       ) AS flag_acordo_leniencia,
       (
           SELECT CASE
               WHEN san.categoria_sancao ILIKE '%%inidone%%'
                   THEN '!Nacional (Inidoneidade)'
               WHEN san.abrangencia_sancao = 'Todas as Esferas em todos os Poderes'
                   THEN '!' || san.abrangencia_sancao
               WHEN san.esfera_orgao_sancionador = 'MUNICIPAL'
                    AND UPPER(san.orgao_sancionador) LIKE '%%' || UPPER(%(municipio)s) || '%%'
                   THEN '!' || COALESCE(san.abrangencia_sancao, 'Sem Informação')
                        || ' (' || san.orgao_sancionador || ')'
               ELSE COALESCE(san.abrangencia_sancao, 'Sem Informação')
                    || ' (' || COALESCE(san.orgao_sancionador, '?')
                    || COALESCE(' - ' || san.uf_orgao_sancionador, '') || ')'
           END
           FROM (
               SELECT LEFT(cpf_cnpj_sancionado, 8) AS cb,
                      categoria_sancao, abrangencia_sancao,
                      orgao_sancionador, uf_orgao_sancionador,
                      esfera_orgao_sancionador
               FROM ceis_sancao
               WHERE LENGTH(cpf_cnpj_sancionado) = 14
               UNION ALL
               SELECT LEFT(cpf_cnpj_sancionado, 8),
                      categoria_sancao, abrangencia_sancao,
                      orgao_sancionador, uf_orgao_sancionador,
                      esfera_orgao_sancionador
               FROM cnep_sancao
               WHERE LENGTH(cpf_cnpj_sancionado) = 14
           ) san
           WHERE san.cb = tf.cnpj_basico
           ORDER BY CASE
               WHEN san.categoria_sancao ILIKE '%%inidone%%' THEN 1
               WHEN san.abrangencia_sancao = 'Todas as Esferas em todos os Poderes' THEN 2
               WHEN san.esfera_orgao_sancionador = 'MUNICIPAL' THEN 3
               ELSE 4
           END
           LIMIT 1
       ) AS abrangencia_sancao_info,
       CASE est.situacao_cadastral::text
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE COALESCE('Sit. ' || est.situacao_cadastral::text, '-')
       END AS desc_situacao
FROM top_forn tf
LEFT JOIN mv_empresa_governo meg ON meg.cnpj_basico = tf.cnpj_basico
LEFT JOIN empresa e ON e.cnpj_basico = tf.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_completo = tf.cpf_cnpj
) q
ORDER BY q.abrangencia_sancao_info IS NOT NULL DESC, q.total_pago DESC
"""

TOP_FORNECEDORES_FALLBACK_DATED = """
WITH top_forn AS (
    SELECT d.cnpj_basico, d.nome_credor,
           MAX(d.cpf_cnpj) AS cpf_cnpj,
           SUM(d.valor_pago) AS total_pago,
           COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos
    FROM tce_pb_despesa d
    JOIN empresa e2 ON e2.cnpj_basico = d.cnpj_basico
        AND e2.natureza_juridica NOT LIKE '1%%'
    WHERE d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND d.cnpj_basico IS NOT NULL
      AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
      AND EXISTS (SELECT 1 FROM estabelecimento est WHERE est.cnpj_completo = d.cpf_cnpj)
    GROUP BY d.cnpj_basico, d.nome_credor
    ORDER BY SUM(d.valor_pago) DESC
    LIMIT 200
)
SELECT * FROM (
    SELECT tf.cnpj_basico, tf.nome_credor,
       CASE WHEN est.cnpj_completo IS NOT NULL THEN e.razao_social END AS razao_social,
       COALESCE(est.cnpj_completo, tf.cpf_cnpj) AS cnpj_completo,
       tf.total_pago, tf.qtd_empenhos,
       EXISTS(
           SELECT 1 FROM ceis_sancao cs
           WHERE LEFT(cs.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND LENGTH(cs.cpf_cnpj_sancionado) = 14
             AND (cs.dt_final_sancao IS NULL OR cs.dt_final_sancao >= CURRENT_DATE)
       ) AS flag_ceis,
       EXISTS(
           SELECT 1 FROM cnep_sancao cn
           WHERE LEFT(cn.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND LENGTH(cn.cpf_cnpj_sancionado) = 14
             AND (cn.dt_final_sancao IS NULL OR cn.dt_final_sancao >= CURRENT_DATE)
       ) AS flag_cnep,
       EXISTS(
           SELECT 1 FROM ceis_sancao cs2
           WHERE LEFT(cs2.cpf_cnpj_sancionado, 8) = tf.cnpj_basico
             AND LENGTH(cs2.cpf_cnpj_sancionado) = 14
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
           SELECT 1 FROM acordo_leniencia al
           WHERE LEFT(al.cnpj_norm, 8) = tf.cnpj_basico
             AND al.situacao_acordo NOT IN ('Cumprido', 'Encerrado')
       ) AS flag_acordo_leniencia,
       (
           SELECT CASE
               WHEN san.categoria_sancao ILIKE '%%inidone%%'
                   THEN '!Nacional (Inidoneidade)'
               WHEN san.abrangencia_sancao = 'Todas as Esferas em todos os Poderes'
                   THEN '!' || san.abrangencia_sancao
               WHEN san.esfera_orgao_sancionador = 'MUNICIPAL'
                    AND UPPER(san.orgao_sancionador) LIKE '%%' || UPPER(%(municipio)s) || '%%'
                   THEN '!' || COALESCE(san.abrangencia_sancao, 'Sem Informação')
                        || ' (' || san.orgao_sancionador || ')'
               ELSE COALESCE(san.abrangencia_sancao, 'Sem Informação')
                    || ' (' || COALESCE(san.orgao_sancionador, '?')
                    || COALESCE(' - ' || san.uf_orgao_sancionador, '') || ')'
           END
           FROM (
               SELECT LEFT(cpf_cnpj_sancionado, 8) AS cb,
                      categoria_sancao, abrangencia_sancao,
                      orgao_sancionador, uf_orgao_sancionador,
                      esfera_orgao_sancionador
               FROM ceis_sancao
               WHERE LENGTH(cpf_cnpj_sancionado) = 14
               UNION ALL
               SELECT LEFT(cpf_cnpj_sancionado, 8),
                      categoria_sancao, abrangencia_sancao,
                      orgao_sancionador, uf_orgao_sancionador,
                      esfera_orgao_sancionador
               FROM cnep_sancao
               WHERE LENGTH(cpf_cnpj_sancionado) = 14
           ) san
           WHERE san.cb = tf.cnpj_basico
           ORDER BY CASE
               WHEN san.categoria_sancao ILIKE '%%inidone%%' THEN 1
               WHEN san.abrangencia_sancao = 'Todas as Esferas em todos os Poderes' THEN 2
               WHEN san.esfera_orgao_sancionador = 'MUNICIPAL' THEN 3
               ELSE 4
           END
           LIMIT 1
       ) AS abrangencia_sancao_info,
       CASE est.situacao_cadastral::text
           WHEN '1' THEN 'Nula' WHEN '2' THEN 'Ativa' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE COALESCE('Sit. ' || est.situacao_cadastral::text, '-')
       END AS desc_situacao
FROM top_forn tf
LEFT JOIN empresa e ON e.cnpj_basico = tf.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_completo = tf.cpf_cnpj
) q
ORDER BY q.abrangencia_sancao_info IS NOT NULL DESC, q.total_pago DESC
"""

TOP_FORNECEDORES_PNCP = None  # deprecated: non-PB removed from frontend

TOP_SERVIDORES_RISCO = """
WITH cnpjs_sancionados AS (
    SELECT DISTINCT LEFT(cpf_cnpj_sancionado, 8) AS cb FROM ceis_sancao
    WHERE (dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE)
      AND LENGTH(cpf_cnpj_sancionado) = 14
    UNION
    SELECT DISTINCT LEFT(cpf_cnpj_sancionado, 8) FROM cnep_sancao
    WHERE (dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE)
      AND LENGTH(cpf_cnpj_sancionado) = 14
),
cnpjs_inidoneidade AS (
    SELECT DISTINCT LEFT(cpf_cnpj_sancionado, 8) AS cb FROM ceis_sancao
    WHERE (dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE)
      AND categoria_sancao ILIKE '%%inidone%%'
      AND LENGTH(cpf_cnpj_sancionado) = 14
),
ceaf_expulsos AS (
    SELECT DISTINCT cpf_cnpj_norm AS cpf6, UPPER(unaccent(nome_sancionado)) AS nome
    FROM ceaf_expulsao
),
empresa_pagamentos AS (
    SELECT d.cnpj_basico, SUM(d.valor_pago) AS total_pago
    FROM tce_pb_despesa d
    WHERE d.municipio = %(municipio)s AND d.valor_pago > 0
    GROUP BY d.cnpj_basico
),
vinculo_datas AS (
    SELECT cpf_digitos_6, nome_upper,
           COALESCE(MIN(data_admissao), TO_DATE(MIN(ano_mes), 'YYYYMM')) AS dt_ini,
           TO_DATE(MAX(ano_mes), 'YYYYMM') + INTERVAL '1 month' - INTERVAL '1 day' AS dt_fim
    FROM tce_pb_servidor
    WHERE municipio = %(municipio)s
      AND cpf_digitos_6 IS NOT NULL AND nome_upper IS NOT NULL
    GROUP BY cpf_digitos_6, nome_upper
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
       ) AS flag_socio_inidoneidade,
       EXISTS(
           SELECT 1 FROM ceaf_expulsos ce
           WHERE ce.cpf6 = mv_servidor_pb_risco.cpf_digitos_6
             AND ce.nome = mv_servidor_pb_risco.nome_upper
       ) AS flag_ceaf_expulso,
       COALESCE((
           SELECT SUM(ep.total_pago)
           FROM unnest(cnpjs_socio) AS cs(cnpj)
           JOIN empresa_pagamentos ep ON ep.cnpj_basico = TRIM(cs.cnpj)
       ), 0) AS total_pago_empresas,
       COALESCE((
           SELECT SUM(d.valor_pago)
           FROM unnest(cnpjs_socio) AS cs(cnpj)
           JOIN tce_pb_despesa d ON d.cnpj_basico = TRIM(cs.cnpj)
               AND d.municipio = %(municipio)s
               AND d.valor_pago > 0
           JOIN vinculo_datas vd ON vd.cpf_digitos_6 = mv_servidor_pb_risco.cpf_digitos_6
               AND vd.nome_upper = mv_servidor_pb_risco.nome_upper
           WHERE d.data_empenho >= vd.dt_ini AND d.data_empenho <= vd.dt_fim
       ), 0) AS total_pago_durante_vinculo
FROM mv_servidor_pb_risco
WHERE %(municipio)s = ANY(municipios)
ORDER BY flag_ceaf_expulso DESC, flag_socio_inidoneidade DESC, flag_socio_sancionado DESC, flag_bolsa_familia DESC, risco_score DESC
LIMIT 200
"""

TOP_SERVIDORES_RISCO_DATED = TOP_SERVIDORES_RISCO.replace(
    "WHERE %(municipio)s = ANY(municipios)",
    """JOIN (
      SELECT DISTINCT s.cpf_digitos_6 AS _cpf6, s.nome_upper AS _nome
      FROM tce_pb_servidor s
      WHERE s.municipio = %(municipio)s
        AND s.ano_mes >= REPLACE(%(ano_mes_inicio)s, '-', '')
        AND s.ano_mes <= REPLACE(%(ano_mes_fim)s, '-', '')
  ) _periodo ON _periodo._cpf6 = mv_servidor_pb_risco.cpf_digitos_6
            AND _periodo._nome = mv_servidor_pb_risco.nome_upper
WHERE %(municipio)s = ANY(municipios)"""
)

AUTOCOMPLETE_MUNICIPIO = """
SELECT municipio AS nome, 'PB' AS uf, risco_score AS rank_val
FROM mv_municipio_pb_risco
WHERE unaccent(municipio) ILIKE unaccent(%(q)s) || '%%'
ORDER BY rank_val DESC NULLS LAST, nome
LIMIT %(limit)s
"""

# Injeta flags 'recebeu durante sancao' nas queries PB.
_PB_ANCHOR = ') AS flag_inidoneidade'
_PB_REPLACEMENT = ') AS flag_inidoneidade' + _FLAGS_SANCAO_DURANTE_PB
TOP_FORNECEDORES = TOP_FORNECEDORES.replace(_PB_ANCHOR, _PB_REPLACEMENT, 1)
TOP_FORNECEDORES_FALLBACK = TOP_FORNECEDORES_FALLBACK.replace(_PB_ANCHOR, _PB_REPLACEMENT, 1)
TOP_FORNECEDORES_DATED = TOP_FORNECEDORES_DATED.replace(_PB_ANCHOR, _PB_REPLACEMENT, 1)
TOP_FORNECEDORES_FALLBACK_DATED = TOP_FORNECEDORES_FALLBACK_DATED.replace(_PB_ANCHOR, _PB_REPLACEMENT, 1)

