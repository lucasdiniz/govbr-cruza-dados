-- =============================================
-- Queries de fraude: dados.pb.gov.br (dados estaduais PB)
-- Fontes: pb_pagamento (CPF COMPLETO), pb_empenho, pb_contrato, pb_saude, pb_convenio
-- Cruzamentos: empresa, estabelecimento, socio, tse_candidato, tse_receita,
--              bolsa_familia, ceis_sancao, cnep_sancao, pgfn_divida, siape_cadastro,
--              tce_pb_despesa, tce_pb_servidor
-- Requer: normalização Fases 7-8 (cnpj_basico, cpf_digitos_6, nome_upper)
-- DIFERENCIAL: pb_pagamento tem CPF COMPLETO (11 dígitos) → match exato
-- =============================================

-- Q78: Auto-contratação — PF que recebe do estado é sócio de empresa que também recebe
-- Detecta: pessoa física recebe pagamento estadual E é sócio de PJ que também recebe.
-- Match por cpf_digitos_6 + nome_upper (socio tem CPF mascarado, não dá match exato).
-- Indica possível conflito de interesses ou empresa de fachada.
SELECT pf.nome_credor AS nome_pf,
       pf.cpfcnpj_credor AS cpf_pf,
       SUM(pf.valor_pagamento) AS total_recebido_pf,
       COUNT(*) AS qtd_pagamentos_pf,
       s.qualificacao AS qualificacao_socio,
       e.razao_social AS empresa,
       est.cnpj_completo,
       e.capital_social,
       pj_agg.total_recebido_pj,
       pj_agg.qtd_pagamentos_pj
FROM pb_pagamento pf
JOIN socio s ON pf.cpf_digitos_6 = s.cpf_cnpj_norm
    AND s.tipo_socio = 2
    AND pf.nome_upper = UPPER(TRIM(s.nome))
    AND pf.cpf_digitos_6 IS NOT NULL
    AND LENGTH(pf.cpfcnpj_credor) = 11
    AND pf.cpfcnpj_credor NOT LIKE '***%'
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN estabelecimento est ON est.cnpj_basico = e.cnpj_basico
    AND est.cnpj_ordem = '0001'
    AND est.situacao_cadastral = '2'
JOIN LATERAL (
    SELECT SUM(pj.valor_pagamento) AS total_recebido_pj,
           COUNT(*) AS qtd_pagamentos_pj
    FROM pb_pagamento pj
    WHERE pj.cnpj_basico = e.cnpj_basico
) pj_agg ON pj_agg.total_recebido_pj > 0
GROUP BY pf.nome_credor, pf.cpfcnpj_credor,
         s.qualificacao, e.razao_social, est.cnpj_completo,
         e.capital_social, pj_agg.total_recebido_pj, pj_agg.qtd_pagamentos_pj
ORDER BY SUM(pf.valor_pagamento) + pj_agg.total_recebido_pj DESC
LIMIT 500;

-- Q79: Credor PF do estado é candidato ou doador TSE
-- Detecta conexão política direta: pessoa que recebe pagamento estadual
-- é/foi candidato ou doou para campanha. CPF completo permite match exato.
-- Parte A: credor = candidato
SELECT pp.nome_credor, pp.cpfcnpj_credor AS cpf_credor,
       SUM(pp.valor_pagamento) AS total_recebido_estado,
       tc.nm_candidato, tc.ds_cargo, tc.sg_partido,
       tc.ano_eleicao, tc.ds_sit_tot_turno,
       tc.nm_ue AS municipio_candidatura
FROM pb_pagamento pp
JOIN tse_candidato tc ON pp.cpfcnpj_credor = tc.cpf
WHERE LENGTH(pp.cpfcnpj_credor) = 11
  AND pp.cpfcnpj_credor NOT LIKE '***%'
  AND pp.valor_pagamento > 0
GROUP BY pp.nome_credor, pp.cpfcnpj_credor,
         tc.nm_candidato, tc.ds_cargo, tc.sg_partido,
         tc.ano_eleicao, tc.ds_sit_tot_turno, tc.nm_ue
ORDER BY total_recebido_estado DESC
LIMIT 500;

-- Q80: Credor PF do estado recebe Bolsa Família — valores altos = suspeito
-- Detecta fraude BF: pessoa que recebe pagamentos estaduais significativos
-- e ao mesmo tempo é beneficiária do Bolsa Família.
-- Match por cpf_digitos_6 + nome (BF tem 6 dígitos, pb_pagamento tem CPF completo)
SELECT pp.nome_credor, pp.cpfcnpj_credor,
       SUM(pp.valor_pagamento) AS total_recebido_estado,
       COUNT(*) AS qtd_pagamentos,
       bf.nm_favorecido, bf.cpf_favorecido, bf.nm_municipio,
       bf.valor_parcela
FROM pb_pagamento pp
JOIN bolsa_familia bf ON pp.cpf_digitos_6 = bf.cpf_digitos
    AND pp.nome_upper = UPPER(TRIM(bf.nm_favorecido))
WHERE pp.cpf_digitos_6 IS NOT NULL
  AND LENGTH(pp.cpfcnpj_credor) = 11
GROUP BY pp.nome_credor, pp.cpfcnpj_credor,
         bf.nm_favorecido, bf.cpf_favorecido, bf.nm_municipio, bf.valor_parcela
HAVING SUM(pp.valor_pagamento) > 10000
ORDER BY total_recebido_estado DESC
LIMIT 500;

-- Q81: Credor PF sancionado (CEIS/CNEP) recebendo pagamento estadual
-- Match exato: CPF 11 dígitos do pb_pagamento = cpf_cnpj_norm do CEIS
-- Irregularidade objetiva: pessoa sancionada não deveria receber do poder público
SELECT pp.nome_credor, pp.cpfcnpj_credor,
       SUM(pp.valor_pagamento) AS total_recebido,
       COUNT(*) AS qtd_pagamentos,
       MIN(pp.data_pagamento) AS primeiro_pagamento,
       MAX(pp.data_pagamento) AS ultimo_pagamento,
       cs.categoria_sancao, cs.dt_inicio_sancao, cs.dt_final_sancao,
       cs.orgao_sancionador,
       'CEIS' AS fonte_sancao
FROM pb_pagamento pp
JOIN ceis_sancao cs ON pp.cpfcnpj_credor = cs.cpf_cnpj_norm
WHERE LENGTH(pp.cpfcnpj_credor) = 11
  AND pp.cpfcnpj_credor NOT LIKE '***%'
  AND pp.data_pagamento >= cs.dt_inicio_sancao
  AND (cs.dt_final_sancao IS NULL OR pp.data_pagamento <= cs.dt_final_sancao)
GROUP BY pp.nome_credor, pp.cpfcnpj_credor,
         cs.categoria_sancao, cs.dt_inicio_sancao, cs.dt_final_sancao,
         cs.orgao_sancionador
UNION ALL
SELECT pp.nome_credor, pp.cpfcnpj_credor,
       SUM(pp.valor_pagamento) AS total_recebido,
       COUNT(*) AS qtd_pagamentos,
       MIN(pp.data_pagamento) AS primeiro_pagamento,
       MAX(pp.data_pagamento) AS ultimo_pagamento,
       cn.categoria_sancao, cn.dt_inicio_sancao, cn.dt_final_sancao,
       cn.orgao_sancionador,
       'CNEP' AS fonte_sancao
FROM pb_pagamento pp
JOIN cnep_sancao cn ON pp.cpfcnpj_credor = cn.cpf_cnpj_norm
WHERE LENGTH(pp.cpfcnpj_credor) = 11
  AND pp.cpfcnpj_credor NOT LIKE '***%'
  AND pp.data_pagamento >= cn.dt_inicio_sancao
  AND (cn.dt_final_sancao IS NULL OR pp.data_pagamento <= cn.dt_final_sancao)
GROUP BY pp.nome_credor, pp.cpfcnpj_credor,
         cn.categoria_sancao, cn.dt_inicio_sancao, cn.dt_final_sancao,
         cn.orgao_sancionador
ORDER BY total_recebido DESC;

-- Q82: Credor PF do estado é servidor federal SIAPE — acúmulo irregular
-- Detecta pessoa que recebe do governo do estado PB e também é servidor federal
-- Match por cpf_digitos_6 + nome (SIAPE tem CPF parcial)
SELECT pp.nome_credor, pp.cpfcnpj_credor,
       SUM(pp.valor_pagamento) AS total_recebido_estado,
       COUNT(*) AS qtd_pagamentos,
       sc.nome AS nome_servidor_siape, sc.cpf AS cpf_siape,
       sc.org_exercicio,
       sr.remuneracao_basica_bruta
FROM pb_pagamento pp
JOIN siape_cadastro sc ON pp.cpf_digitos_6 = sc.cpf_digitos
    AND pp.nome_upper = UPPER(TRIM(sc.nome))
LEFT JOIN siape_remuneracao sr ON sr.id_servidor_portal = sc.id_servidor_portal
WHERE pp.cpf_digitos_6 IS NOT NULL
  AND LENGTH(pp.cpfcnpj_credor) = 11
GROUP BY pp.nome_credor, pp.cpfcnpj_credor,
         sc.nome, sc.cpf, sc.org_exercicio, sr.remuneracao_basica_bruta
HAVING SUM(pp.valor_pagamento) > 10000
ORDER BY total_recebido_estado DESC
LIMIT 500;

-- Q83: Empresa dominante — recebe do estado E de municípios via cnpj_basico
-- Detecta empresas com presença em AMBOS os níveis: empenhos estaduais (pb_empenho)
-- E despesas municipais (TCE-PB). Possível cartel com influência em todo o estado.
-- pb_pagamento é 99% PF (CPF); pb_empenho tem 666k com CNPJ → 9.8k CNPJs em comum com TCE-PB.
WITH pb_agg AS (
    SELECT cnpj_basico,
           SUM(valor_empenho) AS total_estado,
           COUNT(*) AS qtd_empenhos_estado
    FROM pb_empenho
    WHERE cnpj_basico IS NOT NULL
    GROUP BY cnpj_basico
    HAVING SUM(valor_empenho) > 100000
),
tce_agg AS (
    SELECT cnpj_basico,
           SUM(valor_pago) AS total_municipal,
           COUNT(DISTINCT municipio) AS qtd_municipios,
           COUNT(*) AS qtd_empenhos_municipal
    FROM tce_pb_despesa
    WHERE cnpj_basico IS NOT NULL AND valor_pago > 0
    GROUP BY cnpj_basico
    HAVING SUM(valor_pago) > 100000
)
SELECT e.razao_social, e.cnpj_basico, est.cnpj_completo,
       e.capital_social,
       est.uf AS uf_empresa, est.municipio AS municipio_empresa,
       pb.total_estado, pb.qtd_empenhos_estado,
       tce.total_municipal, tce.qtd_municipios, tce.qtd_empenhos_municipal,
       pb.total_estado + tce.total_municipal AS total_combinado
FROM pb_agg pb
JOIN tce_agg tce ON tce.cnpj_basico = pb.cnpj_basico
JOIN empresa e ON e.cnpj_basico = pb.cnpj_basico
JOIN estabelecimento est ON est.cnpj_basico = pb.cnpj_basico
    AND est.cnpj_ordem = '0001'
ORDER BY total_combinado DESC
LIMIT 500;

-- Q84: Contratada estadual inativa/inapta na RFB
-- Irregularidade objetiva: empresa com contrato estadual mas situação cadastral
-- diferente de "ativa" no CNPJ da Receita Federal
SELECT pc.nome_contratado, pc.cpfcnpj_contratado,
       pc.objeto_contrato, pc.valor_original,
       pc.nome_contratante,
       pc.data_celebracao_contrato, pc.data_termino_vigencia,
       est.situacao_cadastral,
       CASE est.situacao_cadastral
           WHEN '1' THEN 'Nula'
           WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta'
           WHEN '8' THEN 'Baixada'
           ELSE 'Situação ' || est.situacao_cadastral
       END AS desc_situacao,
       est.dt_situacao,
       e.razao_social
FROM pb_contrato pc
JOIN estabelecimento est ON est.cnpj_basico = pc.cnpj_basico
    AND est.cnpj_ordem = '0001'
    AND est.situacao_cadastral != '2'
JOIN empresa e ON e.cnpj_basico = pc.cnpj_basico
WHERE pc.cnpj_basico IS NOT NULL
ORDER BY pc.valor_original DESC;

-- Q85: Fornecedor estadual com dívida ativa PGFN
-- Detecta empresas que devem à União (dívida ativa) mas recebem pagamentos do estado PB
SELECT pp.cpfcnpj_credor, pp.nome_credor,
       SUM(pp.valor_pagamento) AS total_recebido_estado,
       COUNT(*) AS qtd_pagamentos,
       pg.numero_inscricao, pg.tipo_devedor, pg.situacao_inscricao,
       pg.valor_consolidado AS divida_pgfn
FROM pb_pagamento pp
JOIN pgfn_divida pg ON pp.cnpj_basico = LEFT(pg.cpf_cnpj_norm, 8)
WHERE pp.cnpj_basico IS NOT NULL
  AND LENGTH(pg.cpf_cnpj_norm) = 14
  AND LENGTH(REPLACE(pp.cpfcnpj_credor, '.', '')) >= 14  -- FIX #13: only PJ creditors, exclude PF/CPF collision
  AND pp.valor_pagamento > 0
GROUP BY pp.cpfcnpj_credor, pp.nome_credor,
         pg.numero_inscricao, pg.tipo_devedor, pg.situacao_inscricao,
         pg.valor_consolidado
HAVING SUM(pp.valor_pagamento) > 50000
ORDER BY pg.valor_consolidado DESC
LIMIT 500;

-- Q86: Fornecedor saúde sancionado — pb_saude × CEIS
-- Setor saúde é alto risco para fraude. Detecta credores de saúde estadual
-- com sanção ativa no CEIS.
SELECT ps.nome_credor, ps.cpfcnpj_credor,
       ps.nome_organizacao_social,
       ps.nome_categoria_despesa,
       SUM(ps.valor_lancamento) AS total_saude,
       COUNT(*) AS qtd_lancamentos,
       cs.categoria_sancao, cs.dt_inicio_sancao, cs.dt_final_sancao,
       cs.orgao_sancionador
FROM pb_saude ps
JOIN ceis_sancao cs ON ps.cnpj_basico = LEFT(cs.cpf_cnpj_sancionado, 8)
WHERE ps.cnpj_basico IS NOT NULL
  AND LENGTH(cs.cpf_cnpj_sancionado) >= 14
  AND ps.data_lancamento >= cs.dt_inicio_sancao
  AND (cs.dt_final_sancao IS NULL OR ps.data_lancamento <= cs.dt_final_sancao)
GROUP BY ps.nome_credor, ps.cpfcnpj_credor,
         ps.nome_organizacao_social, ps.nome_categoria_despesa,
         cs.categoria_sancao, cs.dt_inicio_sancao, cs.dt_final_sancao,
         cs.orgao_sancionador
ORDER BY total_saude DESC;

-- Q87: Sócio de contratada estadual é servidor municipal
-- Detecta conflito: pessoa que é servidor municipal (TCE-PB) E sócio de empresa
-- com contrato estadual (dados.pb). Indica possível tráfico de influência.
SELECT pc.nome_contratado, pc.cpfcnpj_contratado,
       pc.objeto_contrato, pc.valor_original,
       s.nome AS nome_socio, s.cpf_cnpj_norm AS cpf_socio_6dig,
       s.qualificacao,
       sv.municipio, sv.nome_servidor, sv.descricao_cargo,
       sv.valor_vantagem
FROM pb_contrato pc
JOIN socio s ON s.cnpj_basico = pc.cnpj_basico
    AND s.tipo_socio = 2
JOIN tce_pb_servidor sv ON sv.cpf_digitos_6 = s.cpf_cnpj_norm
    AND sv.nome_upper = UPPER(TRIM(s.nome))
WHERE pc.cnpj_basico IS NOT NULL
  AND s.cpf_cnpj_norm IS NOT NULL AND s.cpf_cnpj_norm != ''
  AND sv.ano_mes >= '2022-01'
ORDER BY pc.valor_original DESC
LIMIT 500;

-- Q88: Servidor municipal que recebe pagamento estadual como PF
-- Detecta duplo vínculo: pessoa é servidor em município PB (TCE-PB)
-- E recebe pagamento do governo estadual como pessoa física.
-- Match por cpf_digitos_6 + nome_upper (ambas fontes normalizam)
SELECT sv.municipio, sv.nome_servidor, sv.cpf_cnpj AS cpf_servidor,
       sv.descricao_cargo, sv.tipo_cargo, sv.valor_vantagem,
       pp.nome_credor AS nome_credor_estado, pp.cpfcnpj_credor,
       SUM(pp.valor_pagamento) AS total_recebido_estado,
       COUNT(*) AS qtd_pagamentos_estado,
       pp.tipo_despesa
FROM tce_pb_servidor sv
JOIN pb_pagamento pp ON sv.cpf_digitos_6 = pp.cpf_digitos_6
    AND sv.nome_upper = pp.nome_upper
WHERE sv.cpf_digitos_6 IS NOT NULL AND sv.cpf_digitos_6 != ''
  AND pp.cpf_digitos_6 IS NOT NULL
  AND LENGTH(pp.cpfcnpj_credor) = 11
  AND sv.ano_mes >= '2024-01'
GROUP BY sv.municipio, sv.nome_servidor, sv.cpf_cnpj,
         sv.descricao_cargo, sv.tipo_cargo, sv.valor_vantagem,
         pp.nome_credor, pp.cpfcnpj_credor, pp.tipo_despesa
HAVING SUM(pp.valor_pagamento) > 5000
ORDER BY total_recebido_estado DESC
LIMIT 500;

-- Q89: Convênio estado→município com despesas suspeitas
-- Detecta municípios que receberam convênio estadual e tiveram despesas atípicas
-- no mesmo período (pico de gastos logo após liberação do convênio)
SELECT cv.nome_convenente AS municipio_convenente,
       cv.cnpj_convenente,
       cv.objetivo_convenio,
       cv.valor_concedente, cv.valor_contrapartida,
       cv.data_celebracao_convenio, cv.data_termino_vigencia,
       tce_agg.total_empenhado_periodo,
       tce_agg.qtd_empenhos,
       tce_agg.qtd_credores_distintos
FROM pb_convenio cv
JOIN LATERAL (
    SELECT SUM(d.valor_empenhado) AS total_empenhado_periodo,
           COUNT(*) AS qtd_empenhos,
           COUNT(DISTINCT d.cpf_cnpj) AS qtd_credores_distintos
    FROM tce_pb_despesa d
    -- FIX #17: usar unaccent para normalizar nomes de municípios entre fontes
    WHERE UPPER(TRIM(unaccent(d.municipio))) = UPPER(TRIM(unaccent(cv.nome_municipio)))
      AND d.data_empenho BETWEEN cv.data_celebracao_convenio
          AND COALESCE(cv.data_termino_vigencia, cv.data_celebracao_convenio + INTERVAL '1 year')
      AND d.valor_empenhado > 0
) tce_agg ON tce_agg.total_empenhado_periodo > cv.valor_concedente * 0.5
WHERE cv.valor_concedente > 100000
ORDER BY tce_agg.total_empenhado_periodo DESC
LIMIT 500;

-- Q90: Empenhos estaduais abaixo do limite de dispensa — fracionamento
-- Detecta padrão de empenhos estaduais com valor logo abaixo do limite de dispensa
-- para evitar licitação. Mesmo padrão do Q19 (CPGF) mas para empenho estadual.
-- Limites Lei 14.133/21: dispensa até R$50k (obras R$100k)
SELECT pe.nome_credor, pe.cpfcnpj_credor,
       pe.exercicio,
       pe.codigo_modalidade_licitacao,
       COUNT(*) AS qtd_empenhos,
       SUM(pe.valor_empenho) AS total_empenhado,
       MAX(pe.valor_empenho) AS maior_empenho,
       ROUND(AVG(pe.valor_empenho), 2) AS media_empenho
FROM pb_empenho pe
WHERE pe.valor_empenho > 0
  AND pe.valor_empenho < 50000
  AND pe.valor_empenho > 30000
  AND pe.exercicio >= 2022
  AND pe.cpfcnpj_credor IS NOT NULL
GROUP BY pe.nome_credor, pe.cpfcnpj_credor, pe.exercicio,
         pe.codigo_modalidade_licitacao
HAVING COUNT(*) >= 3
   AND SUM(pe.valor_empenho) > 100000
ORDER BY total_empenhado DESC
LIMIT 500;

-- Q91: Mesmo credor, múltiplos pagamentos no mesmo dia — possível splitting
-- Detecta pagamentos fracionados no mesmo dia para o mesmo credor (PF ou PJ)
-- Pode indicar splitting para evitar controles internos ou limites de alçada
SELECT pp.cpfcnpj_credor, pp.nome_credor,
       pp.data_pagamento,
       COUNT(*) AS qtd_pagamentos_dia,
       SUM(pp.valor_pagamento) AS total_dia,
       MAX(pp.valor_pagamento) AS maior_pagamento,
       MIN(pp.valor_pagamento) AS menor_pagamento,
       ARRAY_AGG(DISTINCT pp.tipo_despesa ORDER BY pp.tipo_despesa) AS tipos_despesa
FROM pb_pagamento pp
WHERE pp.valor_pagamento > 0
  AND pp.data_pagamento IS NOT NULL
GROUP BY pp.cpfcnpj_credor, pp.nome_credor, pp.data_pagamento
HAVING COUNT(*) >= 5
   AND SUM(pp.valor_pagamento) > 50000
ORDER BY total_dia DESC
LIMIT 500;
