-- =============================================================================
-- mv_municipio_pb_licitacao_valor — criacao/atualizacao via mv_swap
-- =============================================================================
-- MV nova (bootstrap no 1o deploy: etl.mv_swap cria o _swap e renomeia, sem
-- tocar em nenhuma MV existente). Definicao identica a sql/12_views.sql (3b),
-- fonte de verdade para rebuild completo — tests/test_cidade_narrativa.py
-- garante a paridade.
--
-- Convencao do framework (etl/mv_swap.py): identifiers usam sufixo `_swap`,
-- que sera removido pelo swap.
-- =============================================================================

CREATE MATERIALIZED VIEW mv_municipio_pb_licitacao_valor_swap AS
SELECT d.municipio,
       COALESCE(SUM(d.valor_pago) FILTER (WHERE COALESCE(LPAD(TRIM(d.codigo_elemento_despesa), 2, '0'), '') NOT IN ('01','03','04','05','07','08','09','11','12','13','14','15','16','21','22','23','24','25','41','43','45','46','47','48','49','59','71','72','73','74','75','76','77','81','91','93','94','96')), 0) AS total_pago_licitavel,
       COALESCE(SUM(d.valor_pago) FILTER (WHERE (d.numero_licitacao IS NULL OR d.numero_licitacao = '' OR d.numero_licitacao = '0' OR d.numero_licitacao = '000000000' OR d.modalidade_licitacao ILIKE '%sem licit%')
           AND COALESCE(LPAD(TRIM(d.codigo_elemento_despesa), 2, '0'), '') NOT IN ('01','03','04','05','07','08','09','11','12','13','14','15','16','21','22','23','24','25','41','43','45','46','47','48','49','59','71','72','73','74','75','76','77','81','91','93','94','96')), 0) AS total_pago_sem_licitacao,
       ROUND(100.0 * COALESCE(SUM(d.valor_pago) FILTER (WHERE (d.numero_licitacao IS NULL OR d.numero_licitacao = '' OR d.numero_licitacao = '0' OR d.numero_licitacao = '000000000' OR d.modalidade_licitacao ILIKE '%sem licit%')
           AND COALESCE(LPAD(TRIM(d.codigo_elemento_despesa), 2, '0'), '') NOT IN ('01','03','04','05','07','08','09','11','12','13','14','15','16','21','22','23','24','25','41','43','45','46','47','48','49','59','71','72','73','74','75','76','77','81','91','93','94','96')), 0)
           / NULLIF(SUM(d.valor_pago) FILTER (WHERE COALESCE(LPAD(TRIM(d.codigo_elemento_despesa), 2, '0'), '') NOT IN ('01','03','04','05','07','08','09','11','12','13','14','15','16','21','22','23','24','25','41','43','45','46','47','48','49','59','71','72','73','74','75','76','77','81','91','93','94','96')), 0), 1) AS pct_valor_sem_licitacao
FROM tce_pb_despesa d
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
    AND e.natureza_juridica NOT LIKE '1%'
WHERE d.cnpj_basico IS NOT NULL AND d.ano >= 2022
  AND d.municipio IS NOT NULL
GROUP BY d.municipio;

CREATE UNIQUE INDEX idx_mv_mun_licval_municipio_swap ON mv_municipio_pb_licitacao_valor_swap(municipio);
