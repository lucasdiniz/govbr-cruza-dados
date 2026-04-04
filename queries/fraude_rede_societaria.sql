-- Q16: Pessoa sócia de muitas empresas fornecedoras
SELECT s.nome, s.cpf_cnpj_socio,
       COUNT(DISTINCT s.cnpj_basico) AS qtd_empresas,
       COUNT(DISTINCT pc.numero_controle_pncp) AS qtd_contratos,
       SUM(pc.valor_global) AS total_contratos
FROM socio s
JOIN pncp_contrato pc ON pc.cnpj_basico_fornecedor = s.cnpj_basico
WHERE s.tipo_socio = 2
  AND s.cpf_cnpj_norm IS NOT NULL AND s.cpf_cnpj_norm != '000000'
GROUP BY s.nome, s.cpf_cnpj_socio
HAVING COUNT(DISTINCT s.cnpj_basico) >= 3
ORDER BY total_contratos DESC;

-- Q17: Cadeia de holdings: holding controla empresas que recebem de múltiplas fontes
SELECT hv.holding_razao_social, hv.holding_cnpj,
       COUNT(DISTINCT hv.cnpj_subsidiaria) AS subsidiarias,
       SUM(pncp_val) AS total_pncp,
       SUM(emenda_val) AS total_emendas,
       SUM(bndes_val) AS total_bndes
FROM holding_vinculo hv
LEFT JOIN (
    SELECT LEFT(ni_fornecedor, 8) AS cnpj8, SUM(valor_global) AS pncp_val
    FROM pncp_contrato GROUP BY 1
) p ON LEFT(hv.cnpj_subsidiaria, 8) = p.cnpj8
LEFT JOIN (
    SELECT LEFT(codigo_favorecido, 8) AS cnpj8, SUM(valor_recebido) AS emenda_val
    FROM emenda_favorecido GROUP BY 1
) e ON LEFT(hv.cnpj_subsidiaria, 8) = e.cnpj8
LEFT JOIN (
    SELECT LEFT(cnpj, 8) AS cnpj8, SUM(valor_contratado) AS bndes_val
    FROM bndes_contrato GROUP BY 1
) b ON LEFT(hv.cnpj_subsidiaria, 8) = b.cnpj8
GROUP BY hv.holding_razao_social, hv.holding_cnpj
HAVING SUM(COALESCE(pncp_val,0) + COALESCE(emenda_val,0) + COALESCE(bndes_val,0)) > 1000000
ORDER BY SUM(COALESCE(pncp_val,0) + COALESCE(emenda_val,0) + COALESCE(bndes_val,0)) DESC;

-- Q18: Sócios laranjas (faixa etária extrema em empresas fornecedoras)
-- FIX #15: pre-agregar contratos por empresa para evitar JOIN explosion (1 row por sócio)
WITH contratos_agg AS (
    SELECT cnpj_basico_fornecedor,
           COUNT(*) AS qtd_contratos,
           SUM(valor_global) AS total_contratos,
           MAX(valor_global) AS maior_contrato
    FROM pncp_contrato
    WHERE valor_global > 100000
    GROUP BY cnpj_basico_fornecedor
)
SELECT s.nome, s.cpf_cnpj_socio, s.faixa_etaria,
       e.razao_social, e.capital_social,
       est.uf AS uf_empresa, est.municipio AS municipio_empresa,
       ca.qtd_contratos, ca.total_contratos, ca.maior_contrato
FROM socio s
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_basico = s.cnpj_basico
  AND est.cnpj_ordem = '0001' AND est.situacao_cadastral = '2'
JOIN contratos_agg ca ON ca.cnpj_basico_fornecedor = s.cnpj_basico
WHERE s.faixa_etaria IN (1, 2, 9)
  AND s.tipo_socio = 2
ORDER BY ca.total_contratos DESC;
