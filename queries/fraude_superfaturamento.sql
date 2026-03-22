-- Q43: Sobrepreço direto — valor homologado muito acima do estimado
-- Detecta contratações onde o valor final excede significativamente a estimativa do órgão
-- Exclui valores estimados muito baixos (< R$1000) que podem ser placeholders
SELECT cc.numero_controle_pncp,
       cc.orgao_razao_social, cc.cnpj_orgao,
       cc.esfera, cc.uf, cc.municipio_nome,
       cc.modalidade_nome,
       cc.objeto,
       cc.valor_estimado,
       cc.valor_homologado,
       ROUND((cc.valor_homologado / cc.valor_estimado - 1) * 100, 1) AS pct_sobrepreco,
       cc.dt_publicacao_pncp
FROM pncp_contratacao cc
WHERE cc.valor_estimado >= 1000
  AND cc.valor_homologado > cc.valor_estimado * 1.25
  AND cc.valor_homologado > 50000
ORDER BY (cc.valor_homologado - cc.valor_estimado) DESC;

-- Q44: Aditivos suspeitos — valor global muito acima do valor inicial do contrato
-- Detecta contratos que foram inflados após assinatura via termos aditivos
-- Exclui contratos de concessionárias (energia/água) que têm valor_inicial simbólico
SELECT pc.numero_controle_pncp,
       pc.orgao_razao_social, pc.cnpj_orgao,
       pc.esfera, pc.uf, pc.municipio_nome,
       pc.tipo_contrato, pc.nome_fornecedor, pc.ni_fornecedor,
       pc.objeto,
       pc.valor_inicial,
       pc.valor_global,
       ROUND((pc.valor_global / pc.valor_inicial - 1) * 100, 1) AS pct_aditivo,
       pc.dt_assinatura, pc.dt_vigencia_fim
FROM pncp_contrato pc
WHERE pc.valor_inicial >= 10000
  AND pc.valor_global > pc.valor_inicial * 1.25
  AND pc.valor_global > 100000
ORDER BY (pc.valor_global - pc.valor_inicial) DESC;

-- Q53: Capital social mínimo ganhando contratos de alto valor
-- Detecta empresas com capital social desproporcional ao valor contratado (possíveis laranjas)
SELECT e.razao_social, e.cnpj_basico, e.capital_social,
       e.natureza_juridica,
       est.uf AS uf_empresa, est.municipio AS municipio_empresa,
       est.dt_inicio_atividade,
       pc.uf AS uf_orgao, pc.municipio_nome AS municipio_orgao,
       pc.objeto, pc.valor_global, pc.dt_assinatura,
       ROUND(pc.valor_global / NULLIF(e.capital_social, 0), 0) AS ratio_contrato_capital
FROM pncp_contrato pc
JOIN empresa e ON e.cnpj_basico = pc.cnpj_basico_fornecedor
JOIN estabelecimento est ON est.cnpj_basico = e.cnpj_basico
  AND est.matriz_filial = 1
WHERE e.capital_social > 0 AND e.capital_social < 50000
  AND pc.valor_global > 500000
ORDER BY ratio_contrato_capital DESC;

-- Q51: Proporção anormal de dispensas por órgão
-- Detecta órgãos que usam dispensa excessivamente em vez de licitação competitiva
-- Foco em municípios (esfera M) e estados (esfera E) com volume significativo
SELECT cc.cnpj_orgao, cc.orgao_razao_social,
       cc.esfera, cc.uf, cc.municipio_nome,
       COUNT(*) AS total_contratacoes,
       SUM(CASE WHEN cc.modalidade_nome = 'Dispensa' THEN 1 ELSE 0 END) AS qtd_dispensas,
       SUM(CASE WHEN cc.modalidade_nome = 'Inexigibilidade' THEN 1 ELSE 0 END) AS qtd_inexigibilidade,
       SUM(CASE WHEN cc.modalidade_nome IN ('Pregão - Eletrônico', 'Pregão - Presencial',
           'Concorrência - Eletrônica', 'Concorrência - Presencial') THEN 1 ELSE 0 END) AS qtd_competitivas,
       ROUND(SUM(CASE WHEN cc.modalidade_nome = 'Dispensa' THEN 1 ELSE 0 END) * 100.0
             / COUNT(*), 1) AS pct_dispensas,
       SUM(cc.valor_estimado) FILTER (WHERE cc.modalidade_nome = 'Dispensa') AS valor_dispensas,
       SUM(cc.valor_estimado) AS valor_total
FROM pncp_contratacao cc
WHERE cc.esfera IN ('E', 'M')
GROUP BY cc.cnpj_orgao, cc.orgao_razao_social, cc.esfera, cc.uf, cc.municipio_nome
HAVING COUNT(*) >= 20
   AND SUM(CASE WHEN cc.modalidade_nome = 'Dispensa' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) > 80
ORDER BY pct_dispensas DESC, valor_total DESC;
