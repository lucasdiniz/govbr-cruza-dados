-- =============================================================================
-- mv_municipio_pb_risco — atomic swap update
-- =============================================================================
-- Adiciona total_pago_licitavel, total_pago_sem_licitacao e
-- pct_valor_sem_licitacao: % do valor pago em despesa LICITAVEL (exclui
-- pessoal, encargos, divida, transferencias, tributos, sentencas e
-- indenizacoes) que saiu sem licitacao. A narrativa da pagina de
-- cidade dizia "Desse dinheiro, X% saiu em compras sem concorrencia" usando
-- pct_sem_licitacao, que eh % da CONTAGEM de empenhos — nao do dinheiro.
-- risco_score NAO muda (recalibracao fica para a issue #141).
--
-- Definicao identica a sql/12_views.sql (fonte de verdade para rebuild
-- completo). Dependentes (mv_municipio_pb_kpi_score, mv_municipio_pb_mapa)
-- sao recriados e re-populados pelo framework apos o swap.
--
-- Convencao do framework (etl/mv_swap.py): identifiers usam sufixo `_swap`,
-- que sera removido pelo swap atomico.
-- =============================================================================

CREATE MATERIALIZED VIEW mv_municipio_pb_risco_swap AS
WITH
desp AS (
    SELECT d.municipio,
           COUNT(*) AS qtd_empenhos,
           SUM(d.valor_empenhado) AS total_empenhado,
           SUM(d.valor_pago) AS total_pago,
           COUNT(*) FILTER (WHERE d.numero_licitacao IS NULL OR d.numero_licitacao = '' OR d.numero_licitacao = '0' OR d.numero_licitacao = '000000000' OR d.modalidade_licitacao ILIKE '%sem licit%') AS qtd_sem_licitacao,
           -- Valor pago em despesa LICITAVEL: exclui elementos que por natureza
           -- nao passam por licitacao (pessoal/encargos/beneficios 01-16,46,49,59,
           -- 94,96; divida 21-25,71-77; transferencias/contribuicoes 41-48,81;
           -- tributos 47; sentencas 91; indenizacoes/restituicoes 93). Codigo
           -- ausente conta como licitavel. Base da narrativa "Das compras e
           -- servicos, X% ...": com pessoal/divida no denominador o % por valor
           -- era dominado por folha paga a credor PJ (consignado, encargos).
           SUM(d.valor_pago) FILTER (WHERE COALESCE(LPAD(TRIM(d.codigo_elemento_despesa), 2, '0'), '') NOT IN ('01','03','04','05','07','08','09','11','12','13','14','15','16','21','22','23','24','25','41','43','45','46','47','48','49','59','71','72','73','74','75','76','77','81','91','93','94','96')) AS total_pago_licitavel,
           SUM(d.valor_pago) FILTER (WHERE (d.numero_licitacao IS NULL OR d.numero_licitacao = '' OR d.numero_licitacao = '0' OR d.numero_licitacao = '000000000' OR d.modalidade_licitacao ILIKE '%sem licit%')
               AND COALESCE(LPAD(TRIM(d.codigo_elemento_despesa), 2, '0'), '') NOT IN ('01','03','04','05','07','08','09','11','12','13','14','15','16','21','22','23','24','25','41','43','45','46','47','48','49','59','71','72','73','74','75','76','77','81','91','93','94','96')) AS total_pago_sem_licitacao,
           COUNT(*) FILTER (WHERE d.mes LIKE '12%') AS qtd_dezembro,
           COUNT(DISTINCT d.cnpj_basico) AS qtd_fornecedores
    FROM tce_pb_despesa d
    JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
        AND e.natureza_juridica NOT LIKE '1%'
    WHERE d.cnpj_basico IS NOT NULL AND d.ano >= 2022
      AND d.municipio IS NOT NULL  -- ~35k rows fantasma sem atribuicao municipal
    GROUP BY d.municipio
),
lic_proponente AS (
    SELECT municipio, numero_licitacao,
           COUNT(DISTINCT cpf_cnpj_proponente) AS num_proponentes
    FROM tce_pb_licitacao
    WHERE ano_licitacao >= 2022
      AND municipio IS NOT NULL
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
      AND municipio IS NOT NULL
    GROUP BY municipio
),
folha AS (
    SELECT municipio,
           SUM(valor_vantagem) AS total_folha
    FROM tce_pb_servidor
    WHERE ano_mes >= '2022-01'
      AND municipio IS NOT NULL
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
    COALESCE(d.total_pago_licitavel, 0) AS total_pago_licitavel,
    COALESCE(d.total_pago_sem_licitacao, 0) AS total_pago_sem_licitacao,
    ROUND(100.0 * COALESCE(d.total_pago_sem_licitacao, 0) / NULLIF(d.total_pago_licitavel, 0), 1) AS pct_valor_sem_licitacao,
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

CREATE UNIQUE INDEX idx_mv_mun_municipio_swap ON mv_municipio_pb_risco_swap(municipio);
CREATE INDEX idx_mv_mun_risco_swap ON mv_municipio_pb_risco_swap(risco_score DESC);
