-- Q06: Favorecido de emenda que também recebe contratos PNCP (mesma empresa)
-- Primeiro agrega emendas e contratos por cnpj_basico, depois junta
SELECT ef_agg.nome_autor, ef_agg.nome_favorecido, ef_agg.codigo_favorecido,
       ef_agg.uf_favorecido, ef_agg.municipio_favorecido,
       ef_agg.total_emenda, ef_agg.qtd_emendas,
       pc_agg.total_contratos, pc_agg.qtd_contratos
FROM (
    SELECT cnpj_basico_favorecido, nome_autor, nome_favorecido, codigo_favorecido,
           uf_favorecido, municipio_favorecido,
           SUM(valor_recebido) AS total_emenda, COUNT(*) AS qtd_emendas
    FROM emenda_favorecido
    WHERE cnpj_basico_favorecido IS NOT NULL
    GROUP BY cnpj_basico_favorecido, nome_autor, nome_favorecido, codigo_favorecido,
             uf_favorecido, municipio_favorecido
    HAVING SUM(valor_recebido) > 100000
) ef_agg
JOIN (
    SELECT cnpj_basico_fornecedor,
           SUM(valor_global) AS total_contratos, COUNT(*) AS qtd_contratos
    FROM pncp_contrato
    WHERE cnpj_basico_fornecedor IS NOT NULL
    GROUP BY cnpj_basico_fornecedor
) pc_agg ON pc_agg.cnpj_basico_fornecedor = ef_agg.cnpj_basico_favorecido
ORDER BY ef_agg.total_emenda DESC;

-- Q07: Emenda direciona recurso para empresa com dívida ativa
SELECT ef.nome_autor, ef.codigo_emenda,
       ef.nome_favorecido, ef.codigo_favorecido,
       ef.uf_favorecido, ef.municipio_favorecido,
       SUM(ef.valor_recebido) AS total_emenda,
       pgfn.valor_consolidado AS divida_ativa,
       pgfn.tipo_situacao_inscricao
FROM emenda_favorecido ef
JOIN pgfn_divida pgfn ON pgfn.cpf_cnpj = ef.codigo_favorecido
WHERE pgfn.tipo_situacao_inscricao = 'EM COBRANCA'
GROUP BY ef.nome_autor, ef.codigo_emenda, ef.nome_favorecido,
         ef.codigo_favorecido, ef.uf_favorecido, ef.municipio_favorecido,
         pgfn.valor_consolidado, pgfn.tipo_situacao_inscricao
ORDER BY total_emenda DESC;

-- Q08: Concentração: mesmo autor beneficia repetidamente o mesmo favorecido
SELECT ef.nome_autor, ef.codigo_autor,
       ef.nome_favorecido, ef.codigo_favorecido,
       COUNT(DISTINCT ef.codigo_emenda) AS qtd_emendas,
       COUNT(DISTINCT ef.ano_mes) AS meses_distintos,
       SUM(ef.valor_recebido) AS total_recebido
FROM emenda_favorecido ef
GROUP BY ef.nome_autor, ef.codigo_autor, ef.nome_favorecido, ef.codigo_favorecido
HAVING COUNT(DISTINCT ef.codigo_emenda) >= 3
ORDER BY total_recebido DESC;

-- Q20: Picos de emendas em anos eleitorais
SELECT ef.nome_autor, ef.codigo_autor,
       ef.ano_mes, ef.tipo_emenda,
       COUNT(*) AS qtd_favorecidos,
       SUM(ef.valor_recebido) AS total_valor
FROM emenda_favorecido ef
WHERE ef.ano_mes LIKE '2024/%' OR ef.ano_mes LIKE '2022/%'
GROUP BY ef.nome_autor, ef.codigo_autor, ef.ano_mes, ef.tipo_emenda
HAVING SUM(ef.valor_recebido) > 5000000
ORDER BY total_valor DESC;
