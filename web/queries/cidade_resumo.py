"""SQL parametrizado para /cidade/<slug>/<yyyy>-<mm> — resumo mensal.

Design:
- Agregacoes mensais sobre tce_pb_despesa e tce_pb_licitacao por
  (municipio, ano, mes) — sem exposicao individual de PF.
- Top empenhos lista ITEM-A-ITEM no template precisa filter PJ inline,
  similar ao licitacao.py (LENGTH digits = 14 + JOIN estabelecimento).
- Mes derivado de EXTRACT(YEAR/MONTH FROM data_empenho) (ano contabil
  real, NAO ano_arquivo). Documentado no template.
"""

# ─────────────────────────────────────────────────────────────────────────
# Agregacoes principais do mes
# ─────────────────────────────────────────────────────────────────────────

# KPIs hero: totais agregados pro (municipio, ano, mes). Tudo agregado,
# zero PF.
RESUMO_AGGS_MES = """
    SELECT
        COUNT(*) AS qtd_empenhos,
        COUNT(DISTINCT cpf_cnpj) AS qtd_fornecedores_unicos,
        COALESCE(SUM(valor_empenhado), 0) AS total_empenhado,
        COALESCE(SUM(valor_liquidado), 0) AS total_liquidado,
        COALESCE(SUM(valor_pago), 0) AS total_pago,
        COUNT(*) FILTER (
            WHERE numero_licitacao IS NULL
               OR numero_licitacao = ''
               OR numero_licitacao = '000000000'
               OR modalidade_licitacao ILIKE '%sem licit%'
        ) AS qtd_sem_licitacao,
        COALESCE(SUM(valor_pago) FILTER (
            WHERE numero_licitacao IS NULL
               OR numero_licitacao = ''
               OR numero_licitacao = '000000000'
               OR modalidade_licitacao ILIKE '%sem licit%'
        ), 0) AS total_sem_licitacao
    FROM tce_pb_despesa
    WHERE municipio = %(municipio)s
      AND EXTRACT(YEAR FROM data_empenho) = %(ano)s
      AND EXTRACT(MONTH FROM data_empenho) = %(mes)s
      AND valor_pago > 0
"""

# Top 20 fornecedores do mes. Apenas PJ (LENGTH digits = 14). JOIN
# estabelecimento+empresa pra trazer cnpj_completo + razao_social canonica.
# Filter natureza_juridica NOT LIKE '1%%' exclui orgaos publicos (1xxx) —
# consistente com /cidade TOP_FORNECEDORES.
RESUMO_TOP_FORNECEDORES = """
    WITH despesas_pj AS MATERIALIZED (
        SELECT
            d.cpf_cnpj,
            d.nome_credor,
            d.valor_pago,
            d.cnpj_basico::bpchar(8) AS cnpj_basico
        FROM tce_pb_despesa d
        WHERE d.municipio = %(municipio)s
          AND EXTRACT(YEAR FROM d.data_empenho) = %(ano)s
          AND EXTRACT(MONTH FROM d.data_empenho) = %(mes)s
          AND d.valor_pago > 0
          AND d.cnpj_basico IS NOT NULL
    )
    SELECT
        dp.cnpj_basico,
        dp.cpf_cnpj AS cnpj_clean,
        COALESCE(NULLIF(e.razao_social, ''), MAX(dp.nome_credor)) AS razao_social,
        SUM(dp.valor_pago) AS total_pago,
        COUNT(*) AS qtd_empenhos,
        est.cnpj_completo
    FROM despesas_pj dp
    JOIN empresa e ON e.cnpj_basico = dp.cnpj_basico
                  AND e.natureza_juridica NOT LIKE '1%%'
    JOIN estabelecimento est ON est.cnpj_basico = dp.cnpj_basico
                            AND est.cnpj_ordem = '0001'
    GROUP BY dp.cnpj_basico, dp.cpf_cnpj, e.razao_social, est.cnpj_completo
    ORDER BY SUM(dp.valor_pago) DESC NULLS LAST
    LIMIT 20
"""

# Top elementos de despesa (agregado, sem PF). Categoria do gasto: ex.
# "Material de Consumo", "Servicos de Terceiros Pessoa Juridica".
RESUMO_TOP_ELEMENTOS = """
    SELECT
        elemento_despesa,
        SUM(valor_pago) AS total_pago,
        COUNT(*) AS qtd_empenhos
    FROM tce_pb_despesa
    WHERE municipio = %(municipio)s
      AND EXTRACT(YEAR FROM data_empenho) = %(ano)s
      AND EXTRACT(MONTH FROM data_empenho) = %(mes)s
      AND valor_pago > 0
      AND elemento_despesa IS NOT NULL
      AND elemento_despesa != ''
    GROUP BY elemento_despesa
    ORDER BY SUM(valor_pago) DESC NULLS LAST
    LIMIT 20
"""

# Distribuicao por modalidade de licitacao (chart). Agregado.
RESUMO_MODALIDADES = """
    SELECT
        COALESCE(NULLIF(modalidade_licitacao, ''), 'Sem licitacao') AS modalidade,
        SUM(valor_pago) AS total_pago,
        COUNT(*) AS qtd_empenhos
    FROM tce_pb_despesa
    WHERE municipio = %(municipio)s
      AND EXTRACT(YEAR FROM data_empenho) = %(ano)s
      AND EXTRACT(MONTH FROM data_empenho) = %(mes)s
      AND valor_pago > 0
    GROUP BY COALESCE(NULLIF(modalidade_licitacao, ''), 'Sem licitacao')
    ORDER BY SUM(valor_pago) DESC NULLS LAST
"""

# Top 20 empenhos do mes (item-por-item). Apenas PJ credor. NAO expoe PF.
# Inclui link pra /empresa/<cnpj_completo>.
RESUMO_TOP_EMPENHOS = """
    WITH despesas_pj AS MATERIALIZED (
        SELECT
            d.id, d.numero_empenho, d.data_empenho, d.elemento_despesa,
            d.valor_empenhado, d.valor_pago, d.modalidade_licitacao,
            d.numero_licitacao, d.cpf_cnpj, d.nome_credor,
            d.cnpj_basico::bpchar(8) AS cnpj_basico
        FROM tce_pb_despesa d
        WHERE d.municipio = %(municipio)s
          AND EXTRACT(YEAR FROM d.data_empenho) = %(ano)s
          AND EXTRACT(MONTH FROM d.data_empenho) = %(mes)s
          AND d.valor_pago > 0
          AND d.cnpj_basico IS NOT NULL
    )
    SELECT
        dp.id, dp.numero_empenho, dp.data_empenho, dp.elemento_despesa,
        dp.valor_empenhado, dp.valor_pago, dp.modalidade_licitacao,
        dp.numero_licitacao,
        dp.cpf_cnpj AS cnpj_clean,
        COALESCE(NULLIF(e.razao_social, ''), dp.nome_credor) AS razao_social,
        est.cnpj_completo
    FROM despesas_pj dp
    JOIN empresa e ON e.cnpj_basico = dp.cnpj_basico
                  AND e.natureza_juridica NOT LIKE '1%%'
    JOIN estabelecimento est ON est.cnpj_basico = dp.cnpj_basico
                            AND est.cnpj_ordem = '0001'
    ORDER BY dp.valor_pago DESC NULLS LAST
    LIMIT 20
"""

# Top 10 licitacoes homologadas no mes (cross-link pra /licitacao). Filter
# PJ vencedor via JOIN com proponentes (mesma logica).
# Agrega por 5-tupla canonica pro path.
RESUMO_TOP_LICITACOES = """
    WITH lic_unique AS (
        SELECT DISTINCT
            l.municipio,
            l.ano_licitacao,
            l.codigo_ug,
            l.descricao_ug,
            l.modalidade,
            l.numero_licitacao,
            l.objeto_licitacao,
            l.data_homologacao
        FROM tce_pb_licitacao l
        WHERE l.municipio = %(municipio)s
          AND EXTRACT(YEAR FROM l.data_homologacao) = %(ano)s
          AND EXTRACT(MONTH FROM l.data_homologacao) = %(mes)s
          AND EXISTS (
              SELECT 1
              FROM tce_pb_licitacao l2
              JOIN empresa e2 ON e2.cnpj_basico = LEFT(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g'), 8)::bpchar(8)
                             AND e2.natureza_juridica NOT LIKE '1%%'
              JOIN estabelecimento est ON est.cnpj_basico = e2.cnpj_basico
                                      AND est.cnpj_ordem = '0001'
              WHERE l2.municipio = l.municipio
                AND l2.ano_licitacao = l.ano_licitacao
                AND l2.codigo_ug = l.codigo_ug
                AND l2.modalidade = l.modalidade
                AND l2.numero_licitacao = l.numero_licitacao
                AND LENGTH(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g')) = 14
          )
    )
    SELECT lu.*, COALESCE(SUM(l.valor_ofertado), 0) AS valor_total
    FROM lic_unique lu
    LEFT JOIN tce_pb_licitacao l ON l.municipio = lu.municipio
                                AND l.ano_licitacao = lu.ano_licitacao
                                AND l.codigo_ug = lu.codigo_ug
                                AND l.modalidade = lu.modalidade
                                AND l.numero_licitacao = lu.numero_licitacao
    GROUP BY lu.municipio, lu.ano_licitacao, lu.codigo_ug, lu.descricao_ug,
             lu.modalidade, lu.numero_licitacao, lu.objeto_licitacao,
             lu.data_homologacao
    ORDER BY COALESCE(SUM(l.valor_ofertado), 0) DESC NULLS LAST
    LIMIT 10
"""

# Comparativo: total pago no mes anterior + mesmo mes do ano anterior.
# Usado pra calcular delta % no hero.
RESUMO_COMPARATIVO = """
    SELECT
        SUM(CASE WHEN EXTRACT(YEAR FROM data_empenho) = %(ano_prev_mes)s
                  AND EXTRACT(MONTH FROM data_empenho) = %(mes_prev_mes)s
                 THEN valor_pago ELSE 0 END) AS total_mes_anterior,
        SUM(CASE WHEN EXTRACT(YEAR FROM data_empenho) = %(ano_prev_yr)s
                  AND EXTRACT(MONTH FROM data_empenho) = %(mes_prev_yr)s
                 THEN valor_pago ELSE 0 END) AS total_mesmo_mes_ano_anterior
    FROM tce_pb_despesa
    WHERE municipio = %(municipio)s
      AND valor_pago > 0
      AND data_empenho >= MAKE_DATE(%(ano_prev_yr)s::int, %(mes_prev_yr)s::int, 1)
      AND data_empenho < (MAKE_DATE(%(ano_prev_mes)s::int, %(mes_prev_mes)s::int, 1) + INTERVAL '1 month')
"""

# ─────────────────────────────────────────────────────────────────────────
# Sitemap qualifying — todos os (municipio, ano, mes) com >=1 empenho PJ
# ─────────────────────────────────────────────────────────────────────────

# Lista pra sitemap. Filter qtd_empenhos > 0 evita meses vazios entrarem
# no sitemap (servem com noindex mas nao desperdicam crawl budget).
# ORDER BY estavel pra paginacao bater entre warmer e sitemap.
CIDADE_RESUMO_QUALIFICADOS_LIST = """
    SELECT
        municipio,
        EXTRACT(YEAR FROM data_empenho)::int AS ano,
        EXTRACT(MONTH FROM data_empenho)::int AS mes,
        COUNT(*) AS qtd_empenhos
    FROM tce_pb_despesa
    WHERE municipio IS NOT NULL
      AND data_empenho IS NOT NULL
      AND valor_pago > 0
    GROUP BY municipio, EXTRACT(YEAR FROM data_empenho), EXTRACT(MONTH FROM data_empenho)
    HAVING COUNT(*) > 0
    ORDER BY municipio, ano DESC, mes DESC
"""
