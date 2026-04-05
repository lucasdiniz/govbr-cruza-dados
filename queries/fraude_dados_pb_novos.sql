-- =============================================
-- Queries de fraude: novos datasets dados.pb.gov.br (sessao 34)
-- Fontes novas: pb_aditivo_contrato, pb_aditivo_convenio, pb_liquidacao_despesa,
--               pb_liquidacao_cge, pb_empenho_anulacao, pb_empenho_suplementacao,
--               pb_dotacao, pb_diaria, pb_unidade_gestora
-- Cruzamentos: empresa, socio, ceis_sancao, cnep_sancao, pgfn_divida,
--              tse_receita_candidato, viagem, pb_contrato, pb_convenio, pb_empenho
-- Requer: normalizacao (cnpj_basico nas novas tabelas)
-- =============================================

-- Q101: Aditivos abusivos — contratos cujo total de aditivos supera 50% do valor original
-- Red flag classico de superfaturamento por "salame": aditivos sucessivos que inflam
-- o valor do contrato muito alem do originalmente licitado.
SELECT c.codigo_contrato,
       c.numero_contrato,
       c.nome_contratado,
       c.cpfcnpj_contratado,
       c.objeto_contrato,
       c.valor_original,
       c.data_celebracao_contrato,
       c.data_termino_vigencia,
       agg.qtd_aditivos,
       agg.total_aditivos,
       ROUND(agg.total_aditivos / NULLIF(c.valor_original, 0) * 100, 1) AS pct_aditivo,
       agg.primeiro_aditivo,
       agg.ultimo_aditivo
FROM pb_contrato c
JOIN LATERAL (
    SELECT COUNT(*) AS qtd_aditivos,
           SUM(a.valor_aditivo) AS total_aditivos,
           MIN(a.data_celebracao_aditivo) AS primeiro_aditivo,
           MAX(a.data_celebracao_aditivo) AS ultimo_aditivo
    FROM pb_aditivo_contrato a
    WHERE a.codigo_contrato = c.codigo_contrato
) agg ON agg.qtd_aditivos > 0
WHERE c.valor_original > 0
  AND agg.total_aditivos > c.valor_original * 0.5
ORDER BY agg.total_aditivos DESC;

-- Q102: Fornecedor sancionado (CEIS/CNEP) recebendo pagamentos do estado da PB
-- Empresa com sancao federal vigente que continua recebendo do governo estadual.
-- Usa cnpj_basico para match (8 primeiros digitos).
SELECT pp.cnpj_basico,
       e.razao_social,
       SUM(pp.valor_pagamento) AS total_recebido,
       COUNT(*) AS qtd_pagamentos,
       MIN(pp.data_pagamento) AS primeiro_pagamento,
       MAX(pp.data_pagamento) AS ultimo_pagamento,
       s.nome_sancionado,
       s.categoria_sancao,
       s.orgao_sancionador,
       s.dt_inicio_sancao,
       s.dt_final_sancao,
       s.fundamentacao_legal,
       'CEIS' AS origem_sancao
FROM pb_pagamento pp
JOIN empresa e ON e.cnpj_basico = pp.cnpj_basico
JOIN ceis_sancao s ON LEFT(s.cpf_cnpj_norm, 8) = pp.cnpj_basico AND s.tipo_pessoa = 'J'
WHERE pp.cnpj_basico IS NOT NULL
  AND pp.valor_pagamento > 0
  AND (s.dt_final_sancao IS NULL OR s.dt_final_sancao >= pp.data_pagamento)
GROUP BY pp.cnpj_basico, e.razao_social,
         s.nome_sancionado, s.categoria_sancao, s.orgao_sancionador,
         s.dt_inicio_sancao, s.dt_final_sancao, s.fundamentacao_legal

UNION ALL

SELECT pp.cnpj_basico,
       e.razao_social,
       SUM(pp.valor_pagamento),
       COUNT(*),
       MIN(pp.data_pagamento),
       MAX(pp.data_pagamento),
       s.nome_sancionado,
       s.categoria_sancao,
       s.orgao_sancionador,
       s.dt_inicio_sancao,
       s.dt_final_sancao,
       s.fundamentacao_legal,
       'CNEP'
FROM pb_pagamento pp
JOIN empresa e ON e.cnpj_basico = pp.cnpj_basico
JOIN cnep_sancao s ON LEFT(s.cpf_cnpj_norm, 8) = pp.cnpj_basico AND s.tipo_pessoa = 'J'
WHERE pp.cnpj_basico IS NOT NULL
  AND pp.valor_pagamento > 0
  AND (s.dt_final_sancao IS NULL OR s.dt_final_sancao >= pp.data_pagamento)
GROUP BY pp.cnpj_basico, e.razao_social,
         s.nome_sancionado, s.categoria_sancao, s.orgao_sancionador,
         s.dt_inicio_sancao, s.dt_final_sancao, s.fundamentacao_legal
ORDER BY total_recebido DESC;

-- Q103: Fornecedor com divida ativa na PGFN recebendo do estado
-- Empresa devedora da Uniao que recebe pagamentos do governo da PB.
-- Pode indicar laranja, empresa de fachada, ou irregularidade na habilitacao.
-- Usa CTE para extrair cnpj_basico da PGFN uma unica vez.
WITH pgfn_pj AS (
    SELECT LEFT(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g'), 8) AS cnpj_basico,
           COUNT(*) AS qtd_inscricoes,
           SUM(valor_consolidado) AS total_divida,
           STRING_AGG(DISTINCT receita_principal, '; ') AS tipos_divida,
           STRING_AGG(DISTINCT situacao_inscricao, '; ') AS situacoes
    FROM pgfn_divida
    WHERE tipo_pessoa LIKE '%jur%'
    GROUP BY LEFT(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g'), 8)
)
SELECT pp.cnpj_basico,
       e.razao_social,
       SUM(pp.valor_pagamento) AS total_recebido_pb,
       COUNT(*) AS qtd_pagamentos,
       pgfn.qtd_inscricoes,
       pgfn.total_divida,
       pgfn.tipos_divida,
       pgfn.situacoes
FROM pb_pagamento pp
JOIN empresa e ON e.cnpj_basico = pp.cnpj_basico
JOIN pgfn_pj pgfn ON pgfn.cnpj_basico = pp.cnpj_basico
WHERE pp.cnpj_basico IS NOT NULL
  AND pp.valor_pagamento > 0
GROUP BY pp.cnpj_basico, e.razao_social,
         pgfn.qtd_inscricoes, pgfn.total_divida, pgfn.tipos_divida, pgfn.situacoes
HAVING SUM(pp.valor_pagamento) > 10000
ORDER BY pgfn.total_divida DESC;

-- Q104: Duplo pagamento — mesma nota fiscal liquidada mais de uma vez
-- Detecta NF duplicada na mesma unidade/exercicio (double billing).
-- Compara pb_liquidacao_despesa consigo mesma.
SELECT l1.exercicio,
       l1.codigo_orgao,
       l1.cpfcnpj_credor,
       l1.numero_nota_fiscal,
       l1.data_nota_fiscal,
       COUNT(*) AS qtd_liquidacoes,
       SUM(l1.valor_liquidacao) AS total_liquidado,
       STRING_AGG(DISTINCT l1.numero_empenho, ', ') AS empenhos,
       STRING_AGG(DISTINCT CAST(l1.data_movimentacao AS TEXT), ', ') AS datas_liquidacao
FROM pb_liquidacao_despesa l1
WHERE l1.numero_nota_fiscal IS NOT NULL
  AND l1.numero_nota_fiscal != ''
  AND l1.numero_nota_fiscal !~ '^0+$'
  AND l1.valor_liquidacao > 0
GROUP BY l1.exercicio, l1.codigo_orgao, l1.cpfcnpj_credor,
         l1.numero_nota_fiscal, l1.data_nota_fiscal
HAVING COUNT(*) > 1
ORDER BY SUM(l1.valor_liquidacao) DESC;

-- Q105: Ciclo empenho > anulacao > re-empenho no mesmo credor
-- Detecta padrao de anular empenho e re-empenhar para o mesmo credor,
-- possivelmente para evitar limites de dispensa ou mudar classificacao.
SELECT e.exercicio,
       e.cpfcnpj_credor,
       e.nome_credor,
       e.codigo_unidade_gestora,
       COUNT(DISTINCT e.numero_empenho) AS empenhos_originais,
       anulados.qtd_anulacoes,
       anulados.valor_anulado,
       SUM(e.valor_empenho) AS valor_empenhado_total,
       ROUND(anulados.valor_anulado / NULLIF(SUM(e.valor_empenho), 0) * 100, 1) AS pct_anulado
FROM pb_empenho e
JOIN LATERAL (
    SELECT COUNT(*) AS qtd_anulacoes,
           SUM(a.valor_empenho) AS valor_anulado
    FROM pb_empenho_anulacao a
    WHERE a.cpfcnpj_credor = e.cpfcnpj_credor
      AND a.exercicio = e.exercicio
      AND a.codigo_unidade_gestora = e.codigo_unidade_gestora
) anulados ON anulados.qtd_anulacoes > 0
WHERE e.valor_empenho > 0
GROUP BY e.exercicio, e.cpfcnpj_credor, e.nome_credor,
         e.codigo_unidade_gestora, anulados.qtd_anulacoes, anulados.valor_anulado
HAVING COUNT(DISTINCT e.numero_empenho) >= 3
   AND anulados.valor_anulado > 10000
ORDER BY anulados.valor_anulado DESC;

-- Q106: Diarias estaduais x viagens federais — sobreposicao de periodo
-- Servidor que recebe diaria estadual e viagem federal no mesmo periodo.
-- Match por CPF digitos (pb_diaria tem CPF mascarado em geral, mas tenta nome).
-- Usa destino_diarias (texto livre) e destinos (viagem federal).
SELECT d.nome_credor AS nome_servidor_pb,
       d.cpfcnpj_credor AS cpf_pb,
       d.destino_diarias,
       d.data_saida_diarias,
       d.data_chegada_diarias,
       d.valor_empenho AS valor_diaria_pb,
       d.historico_empenho,
       v.nome_viajante,
       v.destinos AS destino_federal,
       v.dt_inicio AS inicio_viagem_federal,
       v.dt_fim AS fim_viagem_federal,
       v.valor_diarias AS valor_diaria_federal,
       v.nome_orgao_solicitante AS orgao_federal
FROM pb_diaria d
JOIN viagem v ON UPPER(TRIM(d.nome_credor)) = UPPER(TRIM(v.nome_viajante))
WHERE d.data_saida_diarias IS NOT NULL
  AND v.dt_inicio IS NOT NULL
  AND d.data_saida_diarias <= v.dt_fim
  AND d.data_chegada_diarias >= v.dt_inicio
  AND d.valor_empenho > 0
ORDER BY d.valor_empenho + v.valor_diarias DESC;

-- Q107: Fornecedor PB que doa para campanha TSE (ciclo contrato > doacao)
-- Empresa que recebe pagamentos do estado e tambem doou para campanhas.
-- Indica possivel retorno politico: contrato estadual → doacao eleitoral.
SELECT pp.cnpj_basico,
       e.razao_social,
       SUM(pp.valor_pagamento) AS total_recebido_estado,
       COUNT(DISTINCT pp.exercicio) AS anos_recebimento,
       tse.qtd_doacoes,
       tse.total_doado,
       tse.candidatos_beneficiados,
       tse.partidos
FROM pb_pagamento pp
JOIN empresa e ON e.cnpj_basico = pp.cnpj_basico
JOIN LATERAL (
    SELECT COUNT(*) AS qtd_doacoes,
           SUM(r.vr_receita) AS total_doado,
           STRING_AGG(DISTINCT r.nm_candidato, '; ') AS candidatos_beneficiados,
           STRING_AGG(DISTINCT r.sg_partido, ', ') AS partidos
    FROM tse_receita_candidato r
    WHERE LEFT(r.cpf_cnpj_doador, 8) = pp.cnpj_basico
      AND r.sg_uf = 'PB'
) tse ON tse.qtd_doacoes > 0
WHERE pp.cnpj_basico IS NOT NULL
  AND pp.valor_pagamento > 0
GROUP BY pp.cnpj_basico, e.razao_social,
         tse.qtd_doacoes, tse.total_doado,
         tse.candidatos_beneficiados, tse.partidos
HAVING SUM(pp.valor_pagamento) > 50000
ORDER BY SUM(pp.valor_pagamento) DESC;

-- Q108: Convenio estadual com entidade devedora da Uniao (PGFN)
-- Entidade convenente que tem divida ativa federal — risco de desvio.
WITH pgfn_pj AS (
    SELECT LEFT(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g'), 8) AS cnpj_basico,
           COUNT(*) AS qtd_inscricoes,
           SUM(valor_consolidado) AS total_divida,
           STRING_AGG(DISTINCT receita_principal, '; ') AS tipos_divida
    FROM pgfn_divida
    WHERE tipo_pessoa LIKE '%jur%'
    GROUP BY LEFT(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g'), 8)
)
SELECT cv.codigo_convenio,
       cv.numero_convenio,
       cv.nome_convenente,
       cv.cnpj_convenente,
       cv.objetivo_convenio,
       cv.valor_concedente,
       cv.valor_contrapartida,
       cv.data_celebracao_convenio,
       cv.data_termino_vigencia,
       pgfn.qtd_inscricoes,
       pgfn.total_divida,
       pgfn.tipos_divida
FROM pb_convenio cv
JOIN pgfn_pj pgfn ON pgfn.cnpj_basico = LEFT(cv.cnpj_convenente, 8)
WHERE cv.cnpj_convenente IS NOT NULL
  AND cv.valor_concedente > 0
ORDER BY pgfn.total_divida DESC;

-- Q109: Servidor estadual (credor PF) e socio de empresa que tambem fornece ao estado
-- Similar a Q78, mas usando pb_diaria (que tem nome do servidor recebendo diaria)
-- cruzado com socio → empresa → pb_empenho.
SELECT d.nome_credor AS nome_servidor,
       d.cpfcnpj_credor AS cpf_servidor,
       COUNT(DISTINCT d.numero_empenho) AS qtd_diarias,
       SUM(d.valor_empenho) AS total_diarias,
       s.qualificacao AS qualificacao_socio,
       e.razao_social AS empresa_do_socio,
       e.cnpj_basico,
       e.capital_social,
       emp_agg.total_empenhado_empresa,
       emp_agg.qtd_empenhos_empresa
FROM pb_diaria d
JOIN socio s ON d.nome_upper = UPPER(TRIM(s.nome))
    AND s.tipo_socio = 2
    AND d.nome_upper IS NOT NULL
    AND LENGTH(d.nome_upper) > 5
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN LATERAL (
    SELECT SUM(pe.valor_empenho) AS total_empenhado_empresa,
           COUNT(*) AS qtd_empenhos_empresa
    FROM pb_empenho pe
    WHERE pe.cnpj_basico = e.cnpj_basico
) emp_agg ON emp_agg.total_empenhado_empresa > 0
GROUP BY d.nome_credor, d.cpfcnpj_credor,
         s.qualificacao, e.razao_social, e.cnpj_basico, e.capital_social,
         emp_agg.total_empenhado_empresa, emp_agg.qtd_empenhos_empresa
ORDER BY emp_agg.total_empenhado_empresa DESC;

-- Q110: Suplementacoes concentradas — credor que recebe muitas suplementacoes na mesma UG
-- Detecta fornecedor cujos empenhos sao frequentemente suplementados,
-- indicando possivel manipulacao orcamentaria ou contrato mal dimensionado.
SELECT s.exercicio,
       s.codigo_unidade_gestora,
       ug.nome_unidade_gestora AS nome_unidade,
       s.cpfcnpj_credor,
       s.nome_credor,
       COUNT(*) AS qtd_suplementacoes,
       SUM(s.valor_empenho) AS total_suplementado,
       emp.total_empenhado_original,
       ROUND(SUM(s.valor_empenho) / NULLIF(emp.total_empenhado_original, 0) * 100, 1) AS pct_suplementacao
FROM pb_empenho_suplementacao s
JOIN LATERAL (
    SELECT SUM(e.valor_empenho) AS total_empenhado_original
    FROM pb_empenho e
    WHERE e.cpfcnpj_credor = s.cpfcnpj_credor
      AND e.exercicio = s.exercicio
      AND e.codigo_unidade_gestora = s.codigo_unidade_gestora
) emp ON emp.total_empenhado_original > 0
LEFT JOIN (
    SELECT DISTINCT codigo_unidade_gestora, nome_unidade_gestora
    FROM pb_unidade_gestora
) ug ON ug.codigo_unidade_gestora = s.codigo_unidade_gestora
WHERE s.valor_empenho > 0
GROUP BY s.exercicio, s.codigo_unidade_gestora, ug.nome_unidade_gestora,
         s.cpfcnpj_credor, s.nome_credor, emp.total_empenhado_original
HAVING COUNT(*) >= 5
   AND SUM(s.valor_empenho) > 100000
ORDER BY SUM(s.valor_empenho) DESC;

-- Q111: View materializada — perfil 360 do fornecedor PB
-- Agrega por CNPJ: total recebido, contratos, aditivos, sancoes, divida PGFN, doacoes TSE.
-- Para uso em relatorios e dashboards.
DROP MATERIALIZED VIEW IF EXISTS mv_fornecedor_pb_perfil;
CREATE MATERIALIZED VIEW mv_fornecedor_pb_perfil AS
SELECT e.cnpj_basico,
       e.razao_social,
       est.cnpj_completo,
       est.uf,
       est.municipio,
       e.natureza_juridica,
       e.capital_social,
       -- Pagamentos estaduais
       COALESCE(pag.total_recebido, 0) AS total_recebido_estado,
       COALESCE(pag.qtd_pagamentos, 0) AS qtd_pagamentos,
       COALESCE(pag.anos_recebimento, 0) AS anos_recebimento,
       pag.primeiro_pagamento,
       pag.ultimo_pagamento,
       -- Empenhos
       COALESCE(emp.total_empenhado, 0) AS total_empenhado,
       COALESCE(emp.qtd_empenhos, 0) AS qtd_empenhos,
       -- Contratos
       COALESCE(ctr.qtd_contratos, 0) AS qtd_contratos,
       COALESCE(ctr.valor_contratos, 0) AS valor_contratos,
       -- Aditivos
       COALESCE(adi.qtd_aditivos, 0) AS qtd_aditivos,
       COALESCE(adi.valor_aditivos, 0) AS valor_aditivos,
       -- Sancoes
       COALESCE(san.tem_ceis, FALSE) AS tem_ceis,
       COALESCE(san.tem_cnep, FALSE) AS tem_cnep,
       -- Divida PGFN
       COALESCE(pgfn.total_divida, 0) AS divida_pgfn,
       COALESCE(pgfn.qtd_inscricoes_pgfn, 0) AS qtd_inscricoes_pgfn,
       -- Doacoes TSE
       COALESCE(tse.total_doado_tse, 0) AS total_doado_tse,
       COALESCE(tse.qtd_doacoes_tse, 0) AS qtd_doacoes_tse,
       -- Score de risco (quanto mais flags, maior)
       (CASE WHEN COALESCE(san.tem_ceis, FALSE) THEN 1 ELSE 0 END
        + CASE WHEN COALESCE(san.tem_cnep, FALSE) THEN 1 ELSE 0 END
        + CASE WHEN COALESCE(pgfn.total_divida, 0) > 100000 THEN 1 ELSE 0 END
        + CASE WHEN COALESCE(tse.total_doado_tse, 0) > 0 THEN 1 ELSE 0 END
        + CASE WHEN COALESCE(adi.valor_aditivos, 0) > COALESCE(ctr.valor_contratos, 0) * 0.5 THEN 1 ELSE 0 END
       ) AS score_risco
FROM empresa e
JOIN estabelecimento est ON est.cnpj_basico = e.cnpj_basico
    AND est.cnpj_ordem = '0001'
-- Pagamentos
LEFT JOIN (
    SELECT cnpj_basico,
           SUM(valor_pagamento) AS total_recebido,
           COUNT(*) AS qtd_pagamentos,
           COUNT(DISTINCT exercicio) AS anos_recebimento,
           MIN(data_pagamento) AS primeiro_pagamento,
           MAX(data_pagamento) AS ultimo_pagamento
    FROM pb_pagamento
    WHERE cnpj_basico IS NOT NULL AND valor_pagamento > 0
    GROUP BY cnpj_basico
) pag ON pag.cnpj_basico = e.cnpj_basico
-- Empenhos
LEFT JOIN (
    SELECT cnpj_basico,
           SUM(valor_empenho) AS total_empenhado,
           COUNT(*) AS qtd_empenhos
    FROM pb_empenho
    WHERE cnpj_basico IS NOT NULL AND valor_empenho > 0
    GROUP BY cnpj_basico
) emp ON emp.cnpj_basico = e.cnpj_basico
-- Contratos
LEFT JOIN (
    SELECT LEFT(cpfcnpj_contratado, 8) AS cnpj_basico,
           COUNT(*) AS qtd_contratos,
           SUM(valor_original) AS valor_contratos
    FROM pb_contrato
    WHERE LENGTH(cpfcnpj_contratado) = 14
    GROUP BY LEFT(cpfcnpj_contratado, 8)
) ctr ON ctr.cnpj_basico = e.cnpj_basico
-- Aditivos
LEFT JOIN (
    SELECT c.cnpj_basico,
           COUNT(*) AS qtd_aditivos,
           SUM(a.valor_aditivo) AS valor_aditivos
    FROM pb_aditivo_contrato a
    JOIN (SELECT codigo_contrato, LEFT(cpfcnpj_contratado, 8) AS cnpj_basico
          FROM pb_contrato WHERE LENGTH(cpfcnpj_contratado) = 14) c
        ON c.codigo_contrato = a.codigo_contrato
    GROUP BY c.cnpj_basico
) adi ON adi.cnpj_basico = e.cnpj_basico
-- Sancoes
LEFT JOIN (
    SELECT LEFT(cpf_cnpj_norm, 8) AS cnpj_basico,
           TRUE AS tem_ceis
    FROM ceis_sancao
    WHERE tipo_pessoa = 'J'
      AND (dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE)
    GROUP BY LEFT(cpf_cnpj_norm, 8)
) san ON san.cnpj_basico = e.cnpj_basico
LEFT JOIN (
    SELECT LEFT(cpf_cnpj_norm, 8) AS cnpj_basico,
           TRUE AS tem_cnep
    FROM cnep_sancao
    WHERE tipo_pessoa = 'J'
      AND (dt_final_sancao IS NULL OR dt_final_sancao >= CURRENT_DATE)
    GROUP BY LEFT(cpf_cnpj_norm, 8)
) san_cnep ON san_cnep.cnpj_basico = e.cnpj_basico
-- PGFN
LEFT JOIN (
    SELECT LEFT(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g'), 8) AS cnpj_basico,
           SUM(valor_consolidado) AS total_divida,
           COUNT(*) AS qtd_inscricoes_pgfn
    FROM pgfn_divida
    WHERE tipo_pessoa LIKE '%jur%'
    GROUP BY LEFT(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g'), 8)
) pgfn ON pgfn.cnpj_basico = e.cnpj_basico
-- TSE
LEFT JOIN (
    SELECT LEFT(cpf_cnpj_doador, 8) AS cnpj_basico,
           SUM(vr_receita) AS total_doado_tse,
           COUNT(*) AS qtd_doacoes_tse
    FROM tse_receita_candidato
    WHERE LENGTH(cpf_cnpj_doador) >= 14
    GROUP BY LEFT(cpf_cnpj_doador, 8)
) tse ON tse.cnpj_basico = e.cnpj_basico
-- Filtrar: so empresas que tem algum vinculo com PB
WHERE (pag.total_recebido > 0 OR emp.total_empenhado > 0 OR ctr.qtd_contratos > 0)
WITH NO DATA;

-- Para popular: REFRESH MATERIALIZED VIEW mv_fornecedor_pb_perfil;

-- Indice para consultas rapidas
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_forn_pb_cnpj ON mv_fornecedor_pb_perfil (cnpj_basico);
CREATE INDEX IF NOT EXISTS idx_mv_forn_pb_risco ON mv_fornecedor_pb_perfil (score_risco DESC);
CREATE INDEX IF NOT EXISTS idx_mv_forn_pb_recebido ON mv_fornecedor_pb_perfil (total_recebido_estado DESC);
