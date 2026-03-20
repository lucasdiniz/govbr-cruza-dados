-- Views materializadas para queries de fraude frequentes

-- Perfil de cada fornecedor no PNCP
CREATE MATERIALIZED VIEW mv_fornecedor_perfil AS
SELECT ni_fornecedor,
       nome_fornecedor,
       COUNT(*) AS qtd_contratos,
       SUM(valor_global) AS total_contratos,
       MIN(dt_assinatura) AS primeiro_contrato,
       MAX(dt_assinatura) AS ultimo_contrato,
       COUNT(DISTINCT cnpj_orgao) AS orgaos_distintos
FROM pncp_contrato
WHERE valor_global > 0
GROUP BY ni_fornecedor, nome_fornecedor;

CREATE UNIQUE INDEX idx_mv_forn_ni ON mv_fornecedor_perfil(ni_fornecedor);

-- Visão consolidada de cada empresa em todas as fontes
CREATE MATERIALIZED VIEW mv_empresa_fontes AS
SELECT e.cnpj_basico,
       e.razao_social,
       COALESCE(p.total_pncp, 0) AS total_pncp,
       COALESCE(em.total_emendas, 0) AS total_emendas,
       COALESCE(cp.total_cpgf, 0) AS total_cpgf,
       COALESCE(bn.total_bndes, 0) AS total_bndes,
       COALESCE(pg.total_divida, 0) AS total_divida_pgfn
FROM empresa e
LEFT JOIN (
    SELECT LEFT(ni_fornecedor, 8) AS c, SUM(valor_global) AS total_pncp
    FROM pncp_contrato GROUP BY 1
) p ON p.c = e.cnpj_basico
LEFT JOIN (
    SELECT LEFT(codigo_favorecido, 8) AS c, SUM(valor_recebido) AS total_emendas
    FROM emenda_favorecido GROUP BY 1
) em ON em.c = e.cnpj_basico
LEFT JOIN (
    SELECT LEFT(cnpj_cpf_favorecido, 8) AS c, SUM(valor_transacao) AS total_cpgf
    FROM cpgf_transacao GROUP BY 1
) cp ON cp.c = e.cnpj_basico
LEFT JOIN (
    SELECT LEFT(cnpj, 8) AS c, SUM(valor_contratado) AS total_bndes
    FROM bndes_contrato GROUP BY 1
) bn ON bn.c = e.cnpj_basico
LEFT JOIN (
    SELECT LEFT(cpf_cnpj, 8) AS c, SUM(valor_consolidado) AS total_divida
    FROM pgfn_divida GROUP BY 1
) pg ON pg.c = e.cnpj_basico
WHERE COALESCE(p.total_pncp, 0) + COALESCE(em.total_emendas, 0)
    + COALESCE(cp.total_cpgf, 0) + COALESCE(bn.total_bndes, 0) > 0;

CREATE UNIQUE INDEX idx_mv_empresa_cnpj ON mv_empresa_fontes(cnpj_basico);
