-- Q12: Triplo benefício: empresa recebe BNDES + PNCP + emendas
SELECT e.razao_social, e.cnpj_basico,
       b.total_bndes, p.total_pncp, em.total_emendas,
       (b.total_bndes + p.total_pncp + em.total_emendas) AS total_geral
FROM empresa e
JOIN (
    SELECT LEFT(cnpj, 8) AS cnpj8, SUM(valor_contratado) AS total_bndes
    FROM bndes_contrato GROUP BY LEFT(cnpj, 8)
) b ON b.cnpj8 = e.cnpj_basico
JOIN (
    SELECT LEFT(ni_fornecedor, 8) AS cnpj8, SUM(valor_global) AS total_pncp
    FROM pncp_contrato GROUP BY LEFT(ni_fornecedor, 8)
) p ON p.cnpj8 = e.cnpj_basico
JOIN (
    SELECT LEFT(codigo_favorecido, 8) AS cnpj8, SUM(valor_recebido) AS total_emendas
    FROM emenda_favorecido WHERE tipo_favorecido != 'PESSOA FISICA'
    GROUP BY LEFT(codigo_favorecido, 8)
) em ON em.cnpj8 = e.cnpj_basico
ORDER BY total_geral DESC;

-- Q13: Fornecedor histórico: mesmo CNPJ no ComprasNet E no PNCP
SELECT cc.fornecedor_cnpj_cpf, cc.fornecedor_nome,
       MIN(cc.dt_assinatura) AS primeiro_comprasnet,
       MAX(pc.dt_assinatura) AS ultimo_pncp,
       COUNT(DISTINCT cc.id_comprasnet) AS qtd_comprasnet,
       COUNT(DISTINCT pc.numero_controle_pncp) AS qtd_pncp
FROM comprasnet_contrato cc
JOIN pncp_contrato pc ON pc.ni_fornecedor = cc.fornecedor_cnpj_cpf
GROUP BY cc.fornecedor_cnpj_cpf, cc.fornecedor_nome
HAVING COUNT(DISTINCT cc.id_comprasnet) + COUNT(DISTINCT pc.numero_controle_pncp) > 20
ORDER BY COUNT(DISTINCT cc.id_comprasnet) + COUNT(DISTINCT pc.numero_controle_pncp) DESC;

-- Q14: Empresa com renúncia fiscal milionária que é fornecedora do governo
SELECT rf.cnpj, rf.razao_social,
       SUM(rf.valor_renuncia) AS total_renuncia,
       pc.total_contratos, pc.qtd_contratos
FROM renuncia_fiscal rf
JOIN (
    SELECT ni_fornecedor, SUM(valor_global) AS total_contratos,
           COUNT(*) AS qtd_contratos
    FROM pncp_contrato GROUP BY ni_fornecedor
) pc ON pc.ni_fornecedor = rf.cnpj
WHERE rf.valor_renuncia > 0
GROUP BY rf.cnpj, rf.razao_social, pc.total_contratos, pc.qtd_contratos
HAVING SUM(rf.valor_renuncia) > 1000000
ORDER BY total_renuncia DESC;

-- Q15: Empresa inativa que recebe pagamentos
WITH empresas_inativas AS (
    SELECT cnpj_completo, cnpj_basico, uf, municipio, situacao_cadastral, dt_situacao
    FROM estabelecimento
    WHERE situacao_cadastral IN (3, 4, 8)
)
SELECT ei.cnpj_completo, ei.uf, ei.municipio, ei.situacao_cadastral, ei.dt_situacao,
       'PNCP' AS fonte, pc.objeto AS detalhe, pc.valor_global AS valor, pc.dt_assinatura AS data
FROM empresas_inativas ei
JOIN pncp_contrato pc ON pc.ni_fornecedor = ei.cnpj_completo
  AND pc.dt_assinatura > ei.dt_situacao
UNION ALL
SELECT ei.cnpj_completo, ei.uf, ei.municipio, ei.situacao_cadastral, ei.dt_situacao,
       'EMENDA', ef.nome_autor, ef.valor_recebido,
       TO_DATE(ef.ano_mes, 'YYYYMM') AS data
FROM empresas_inativas ei
JOIN emenda_favorecido ef ON ef.codigo_favorecido = ei.cnpj_completo
  AND TO_DATE(ef.ano_mes, 'YYYYMM') > ei.dt_situacao
UNION ALL
SELECT ei.cnpj_completo, ei.uf, ei.municipio, ei.situacao_cadastral, ei.dt_situacao,
       'CPGF', ct.nome_portador, ct.valor_transacao, ct.dt_transacao
FROM empresas_inativas ei
JOIN cpgf_transacao ct ON ct.cnpj_cpf_favorecido = ei.cnpj_completo
  AND ct.dt_transacao > ei.dt_situacao
ORDER BY valor DESC;
