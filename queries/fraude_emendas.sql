-- Q06: Favorecido de emenda que também recebe contratos PNCP via mesmo sócio
SELECT ef.nome_autor, ef.codigo_emenda, ef.tipo_emenda,
       ef.nome_favorecido, ef.codigo_favorecido,
       SUM(ef.valor_recebido) AS total_emenda,
       s.nome AS socio,
       pc.ni_fornecedor, SUM(pc.valor_global) AS total_contratos
FROM emenda_favorecido ef
JOIN socio s ON LEFT(ef.codigo_favorecido, 8) = s.cnpj_basico
JOIN pncp_contrato pc ON LEFT(pc.ni_fornecedor, 8) = s.cnpj_basico
GROUP BY ef.nome_autor, ef.codigo_emenda, ef.tipo_emenda,
         ef.nome_favorecido, ef.codigo_favorecido, s.nome, pc.ni_fornecedor
HAVING SUM(ef.valor_recebido) > 100000
ORDER BY total_emenda DESC;

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
