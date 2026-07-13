-- =============================================================================
-- mv_empresa_tce_pb — atomic swap (ADR-0014)
-- =============================================================================
-- Agregado por cnpj_basico de processos/decisoes do TCE-PB.
-- Source: tce_pb_decisao + tce_pb_decisao_cnpj (populadas por etl/23_tce_pb_doe.py).
--
-- Convencao do framework (etl/mv_swap.py): identifiers usam sufixo `_swap`,
-- que sera removido pelo swap atomico.
-- =============================================================================

CREATE MATERIALIZED VIEW mv_empresa_tce_pb_swap AS
WITH base AS (
    SELECT
        LEFT(dc.cnpj, 8)              AS cnpj_basico,
        d._nk_md5,
        d.hash_publicacao,
        d.num_processo,
        d.ano_processo,
        d.tipo_decisao,
        d.orgao_julgador,
        d.fase,
        d.data_sessao,
        d.tipo_materia,
        d.resultado,
        d.aplicou_multa,
        d.imputou_debito,
        COALESCE(d.valor_multa_rs, 0)  AS valor_multa_rs,
        COALESCE(d.valor_debito_rs, 0) AS valor_debito_rs,
        d.municipio_inferido
    FROM tce_pb_decisao d
    JOIN tce_pb_decisao_cnpj dc ON dc.decisao_md5 = d._nk_md5
    WHERE d.tipo_materia <> 'atos_pessoal'
      AND EXISTS (
          SELECT 1 FROM estabelecimento e
          WHERE e.cnpj_basico = LEFT(dc.cnpj, 8)
      )
),
processos AS (
    SELECT
        cnpj_basico,
        num_processo,
        ano_processo,
        MAX(tipo_materia)               AS tipo_materia,
        MAX(orgao_julgador)             AS orgao,
        MAX(municipio_inferido)         AS municipio,
        MAX(data_sessao)                AS ultima_sessao,
        COUNT(*)                        AS qtd_decisoes,
        MIN(CASE resultado
              WHEN 'irregular'        THEN 1
              WHEN 'regular_ressalva' THEN 2
              WHEN 'regular'          THEN 3
              ELSE 4
            END)                        AS pior_resultado_rank,
        bool_or(aplicou_multa)          AS tem_multa,
        bool_or(imputou_debito)         AS tem_debito,
        SUM(valor_multa_rs)             AS multa_total_rs,
        SUM(valor_debito_rs)            AS debito_total_rs,
        jsonb_agg(
            jsonb_build_object(
                'hash',   hash_publicacao,
                'fase',   fase,
                'data',   data_sessao,
                'result', resultado
            )
            ORDER BY data_sessao DESC NULLS LAST
        )                               AS decisoes_json
    FROM base
    GROUP BY cnpj_basico, num_processo, ano_processo
)
SELECT
    p.cnpj_basico,
    COUNT(*)::int                                                  AS qtd_processos,
    SUM(p.qtd_decisoes)::int                                       AS qtd_decisoes,
    COUNT(*) FILTER (WHERE p.pior_resultado_rank = 1)::int         AS qtd_processos_irregular,
    COUNT(*) FILTER (WHERE p.tem_multa)::int                       AS qtd_processos_multa,
    COUNT(*) FILTER (WHERE p.tem_debito)::int                      AS qtd_processos_debito,
    COALESCE(SUM(p.multa_total_rs), 0)::numeric(14,2)              AS multa_total_rs,
    COALESCE(SUM(p.debito_total_rs), 0)::numeric(14,2)             AS debito_total_rs,
    MAX(p.ultima_sessao)                                           AS ultima_decisao_em,
    (
        SELECT jsonb_agg(row_to_json(top20)::jsonb)
        FROM (
            SELECT
                p2.num_processo,
                p2.ano_processo,
                p2.tipo_materia,
                p2.orgao,
                p2.municipio,
                p2.ultima_sessao,
                p2.qtd_decisoes,
                CASE p2.pior_resultado_rank
                    WHEN 1 THEN 'irregular'
                    WHEN 2 THEN 'regular_ressalva'
                    WHEN 3 THEN 'regular'
                    ELSE        'indef'
                END                        AS pior_resultado,
                p2.tem_multa,
                p2.tem_debito,
                p2.decisoes_json           AS decisoes
            FROM processos p2
            WHERE p2.cnpj_basico = p.cnpj_basico
            ORDER BY p2.ultima_sessao DESC NULLS LAST,
                     p2.ano_processo DESC,
                     p2.num_processo DESC
            LIMIT 20
        ) top20
    )                                                              AS processos_json
FROM processos p
GROUP BY p.cnpj_basico;

CREATE UNIQUE INDEX idx_mv_empresa_tce_pb_cnpj_swap ON mv_empresa_tce_pb_swap(cnpj_basico);
CREATE INDEX idx_mv_empresa_tce_pb_irregular_swap  ON mv_empresa_tce_pb_swap(cnpj_basico)
    WHERE qtd_processos_irregular > 0;
CREATE INDEX idx_mv_empresa_tce_pb_multa_swap      ON mv_empresa_tce_pb_swap(cnpj_basico)
    WHERE qtd_processos_multa > 0 OR qtd_processos_debito > 0;
