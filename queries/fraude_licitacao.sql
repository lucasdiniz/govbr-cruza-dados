-- Q01: Empresas do mesmo grupo (holding) em licitação concorrente (bid rigging)
SELECT h1.holding_razao_social, h1.holding_cnpj,
       c1.ni_fornecedor AS emp1, c1.nome_fornecedor AS nome1,
       c2.ni_fornecedor AS emp2, c2.nome_fornecedor AS nome2,
       cc.objeto, cc.numero_controle_pncp AS licitacao
FROM pncp_contrato c1
JOIN pncp_contrato c2
  ON c1.numero_controle_contratacao = c2.numero_controle_contratacao
  AND c1.ni_fornecedor < c2.ni_fornecedor
JOIN holding_vinculo h1 ON h1.cnpj_subsidiaria = c1.ni_fornecedor
JOIN holding_vinculo h2 ON h2.cnpj_subsidiaria = c2.ni_fornecedor
  AND h1.holding_cnpj = h2.holding_cnpj
JOIN pncp_contratacao cc ON cc.numero_controle_pncp = c1.numero_controle_contratacao;

-- Q02: Empresas com sócios em comum ganhando contratos do mesmo órgão
SELECT s1.cnpj_basico AS emp1, s2.cnpj_basico AS emp2,
       s1.nome AS socio_comum, s1.cpf_cnpj_socio,
       COUNT(DISTINCT pc.numero_controle_pncp) AS contratos_mesmo_orgao,
       SUM(pc.valor_global) AS valor_total
FROM socio s1
JOIN socio s2 ON s1.cpf_cnpj_socio = s2.cpf_cnpj_socio
  AND s1.cnpj_basico < s2.cnpj_basico
  AND s1.cpf_cnpj_socio NOT IN ('***000000**', '')
JOIN pncp_contrato pc ON LEFT(pc.ni_fornecedor, 8) IN (s1.cnpj_basico, s2.cnpj_basico)
GROUP BY s1.cnpj_basico, s2.cnpj_basico, s1.nome, s1.cpf_cnpj_socio
HAVING COUNT(DISTINCT pc.numero_controle_pncp) > 1
ORDER BY valor_total DESC;

-- Q03: Empresa-fachada: criada recentemente, ganha grande contrato
SELECT e.razao_social, est.cnpj_completo,
       est.uf AS uf_empresa, est.municipio AS municipio_empresa,
       pc.uf AS uf_orgao, pc.municipio_nome AS municipio_orgao,
       est.dt_inicio_atividade,
       e.capital_social, pc.objeto, pc.valor_global, pc.dt_assinatura,
       (pc.dt_assinatura - est.dt_inicio_atividade) AS dias_ate_contrato
FROM pncp_contrato pc
JOIN estabelecimento est ON est.cnpj_completo = pc.ni_fornecedor
JOIN empresa e ON e.cnpj_basico = est.cnpj_basico
WHERE est.dt_inicio_atividade IS NOT NULL
  AND pc.dt_assinatura IS NOT NULL
  AND (pc.dt_assinatura - est.dt_inicio_atividade) < 180
  AND pc.valor_global > 100000
ORDER BY dias_ate_contrato ASC;

-- Q04: Devedor PGFN que continua recebendo contratos
SELECT pgfn.nome_devedor, pgfn.cpf_cnpj, pgfn.valor_consolidado,
       pgfn.tipo_situacao_inscricao,
       pc.uf AS uf_orgao, pc.municipio_nome AS municipio_orgao,
       pc.objeto, pc.valor_global, pc.dt_assinatura
FROM pgfn_divida pgfn
JOIN pncp_contrato pc ON pc.ni_fornecedor = pgfn.cpf_cnpj
WHERE pgfn.tipo_situacao_inscricao IN ('EM COBRANCA', 'IRREGULAR')
  AND pc.valor_global > 50000
ORDER BY pc.valor_global DESC;

-- Q05: Fornecedor dominante num órgão
SELECT pc.cnpj_orgao, pc.nome_fornecedor, pc.ni_fornecedor,
       COUNT(*) AS qtd_contratos,
       SUM(pc.valor_global) AS total_valor,
       ROUND(SUM(pc.valor_global) * 100.0 /
         SUM(SUM(pc.valor_global)) OVER (PARTITION BY pc.cnpj_orgao), 2
       ) AS pct_do_orgao
FROM pncp_contrato pc
WHERE pc.valor_global > 0
GROUP BY pc.cnpj_orgao, pc.ni_fornecedor, pc.nome_fornecedor
HAVING COUNT(*) >= 5
ORDER BY pct_do_orgao DESC;
