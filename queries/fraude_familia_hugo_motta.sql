-- =============================================
-- Queries de investigação: Rede empresarial da família Hugo Motta
-- Presidente da Câmara dos Deputados (Republicanos-PB)
-- Nome completo: Hugo Motta Wanderley da Nóbrega (CPF: 04796249419)
--
-- Fontes cruzadas: socio, empresa, estabelecimento, pb_empenho,
--                  tce_pb_despesa, tse_receita_candidato, tse_candidato,
--                  ceis_sancao, cnep_sancao, pgfn_divida, pb_contrato,
--                  pb_aditivo_contrato, pncp_contrato
-- =============================================

-- ============================================================
-- PARTE 1: MAPEAMENTO DA REDE FAMILIAR E EMPRESARIAL
-- ============================================================

-- Q201: Árvore familiar — todos os membros identificados como sócios
-- Família nuclear + extensa, com vínculo e empresas
-- Membros mapeados via base RFB (socio) e pesquisa pública:
--   Hugo Motta W.N. (deputado federal)
--   Luana Medeiros Motta (esposa)
--   Hugo Motta W.N. Filho e Paola Medeiros Motta Wanderley (filhos)
--   Olivia Motta W.N. (irmã, médica, cotada p/ ALPB 2026)
--   Nabor W.N. Filho (pai, prefeito de Patos)
--   Ilanna Araújo Motta (mãe, ex-chefe de gabinete Patos, presa Op. Veiculação 2016)
--   Francisca Gomes Araújo Mota (avó materna, dep. estadual 6 mandatos, ex-prefeita Patos)
--   Helena W.N. Lima de Farias (tia/parente, sócia rádio/agropecuária)
--   Severino Medeiros Ramos Neto (sogro, réu por fraude a licitação em Cabedelo)
--   Maria Eliane de Araújo Medeiros (sogra, réu por fraude a licitação)
--   Bianca Araújo Medeiros (cunhada, empréstimo R$22M Banco Master)
--   Luciano/Ricardo Vilar Wanderley Nóbrega (primos, clínicas de diagnóstico)

WITH familia_cnpj AS (
    VALUES
    -- Hugo Motta (próprio)
    ('33722496', 'Hugo Motta (proprio)', 'HUGO M WANDERLEY DA NOBREGA LTDA'),
    -- Esposa + filhos
    ('32830711', 'Luana Medeiros Motta (esposa) + filhos', 'MEDEIROS & MEDEIROS LTDA'),
    ('08181087', 'Luana + Bianca (esposa/cunhada)', 'FRONTEIRA IND. E COM. DE MINERAIS LTDA'),
    -- Irmã Olivia
    ('58830248', 'Olivia Motta W.N. (irma)', 'DUTRA SMART INCORPORACAO SPE LTDA'),
    ('55514713', 'Olivia Motta W.N. (irma)', 'DUTRA BEACH RESORT INCORPORACAO SPE LTDA'),
    ('53041627', 'Olivia Motta W.N. (irma)', 'DUTRA RESORT ISIDRO GOMES SPE LTDA'),
    ('55444808', 'Olivia Motta W.N. (irma)', 'MW EMPREENDIMENTOS IMOBILIARIOS LTDA'),
    ('64082599', 'Olivia Motta W.N. (irma)', 'MW HOLDING PATRIMONIAL LTDA'),
    ('49221790', 'Olivia Motta W.N. (irma)', 'CENTRO EDUCACIONAL DE PATOS LTDA'),
    ('28214987', 'Olivia Motta W.N. (irma)', 'OMW SERVICOS MEDICOS ESPECIALIZADOS LTDA'),
    ('59079522', 'Olivia Motta W.N. (irma)', 'MWN CONSULTORIA E GESTAO LTDA'),
    -- Família materna (mãe + avó) — mídia
    ('10765196', 'Olivia/Ilanna/Francisca (mae/avo)', 'RADIO FM ITATIUNGA LTDA'),
    ('11984747', 'Olivia/Ilanna/Francisca (mae/avo)', 'SISTEMA ITATIUNGA DE COMUNICACAO LTDA'),
    -- Pai Nabor
    ('17065074', 'Nabor W.N. Filho (pai, prefeito Patos)', 'LIMPTRANSERV COLETA DE RESIDUOS'),
    ('64199173', 'Nabor W.N. Filho (pai)', 'WN HOLDING LTDA'),
    ('08332413', 'Nabor/Helena (familia paterna)', 'AGRO PECUARIA MARIA PAZ NORTE SA'),
    -- Sogros / Cunhada
    ('05307555', 'Maria Eliane Medeiros (sogra)', 'RESIDUOS SOLIDOS SERVICOS LTDA'),
    ('46253251', 'Bianca Araujo Medeiros (cunhada)', 'AJC PARTICIPACOES LTDA'),
    ('28548708', 'Bianca Araujo Medeiros (cunhada)', 'PEDREIRA VITORIA MINERIOS LTDA'),
    -- Primos Vilar Wanderley Nóbrega (clínicas de diagnóstico)
    ('08716557', 'Luciano/Ricardo Vilar W.N. (primos)', 'CLINICA RADIOLOGICA DR. WANDERLEY LTDA'),
    ('04489715', 'Luciano Vilar W.N. (primo)', 'NOVA DIAGNOSTICO POR IMAGEM LTDA'),
    ('11149864', 'Luciano Vilar W.N. (primo)', 'WANDERLEY MEDICINA DIAGNOSTICA LTDA'),
    ('19161889', 'Luciano Vilar W.N. (primo)', 'WANDERLEY DIAGNOSTICOS LTDA')
)
SELECT f.column2 AS vinculo_familiar,
       f.column3 AS empresa,
       f.column1 AS cnpj_basico,
       e.capital_social,
       est.uf,
       est.municipio
FROM familia_cnpj f
JOIN empresa e ON e.cnpj_basico = f.column1
LEFT JOIN estabelecimento est ON est.cnpj_basico = f.column1 AND est.cnpj_ordem = '0001'
ORDER BY e.capital_social DESC;

-- Q202: Empresas da família que RECEBEM dinheiro público (estado + municípios PB)
WITH familia_cnpj AS (
    VALUES
    ('33722496'), ('32830711'), ('08181087'),
    ('58830248'), ('55514713'), ('53041627'), ('55444808'), ('64082599'),
    ('49221790'), ('28214987'), ('59079522'),
    ('10765196'), ('11984747'),
    ('17065074'), ('64199173'), ('08332413'),
    ('05307555'), ('46253251'), ('28548708'),
    ('08716557'), ('04489715'), ('11149864'), ('19161889')
)
SELECT e.razao_social,
       f.column1 AS cnpj_basico,
       COALESCE(emp.total_empenhado, 0) AS empenhado_estado,
       COALESCE(emp.qtd, 0) AS qtd_empenhos_estado,
       COALESCE(mun.total_empenhado_mun, 0) AS empenhado_municipal,
       COALESCE(mun.qtd, 0) AS qtd_empenhos_municipal,
       COALESCE(mun.municipios, '') AS municipios_atendidos
FROM familia_cnpj f
JOIN empresa e ON e.cnpj_basico = f.column1
LEFT JOIN (
    SELECT cnpj_basico, SUM(valor_empenho) AS total_empenhado, COUNT(*) AS qtd
    FROM pb_empenho WHERE cnpj_basico IS NOT NULL AND valor_empenho > 0
    GROUP BY cnpj_basico
) emp ON emp.cnpj_basico = f.column1
LEFT JOIN (
    SELECT LEFT(cpf_cnpj, 8) AS cnpj_basico,
           SUM(valor_empenhado) AS total_empenhado_mun,
           COUNT(*) AS qtd,
           STRING_AGG(DISTINCT municipio, '; ') AS municipios
    FROM tce_pb_despesa
    WHERE valor_empenhado > 0 AND LENGTH(cpf_cnpj) >= 14
    GROUP BY LEFT(cpf_cnpj, 8)
) mun ON mun.cnpj_basico = f.column1
WHERE COALESCE(emp.total_empenhado, 0) > 0 OR COALESCE(mun.total_empenhado_mun, 0) > 0
ORDER BY COALESCE(emp.total_empenhado, 0) + COALESCE(mun.total_empenhado_mun, 0) DESC;

-- ============================================================
-- PARTE 2: CRUZAMENTOS DE RISCO
-- ============================================================

-- Q203: Doações TSE para Hugo Motta — quem financia suas campanhas
SELECT r.nm_doador,
       r.cpf_cnpj_doador,
       r.vr_receita,
       r.ds_fonte_receita,
       r.ano_eleicao,
       r.sg_partido
FROM tse_receita_candidato r
WHERE r.nm_candidato LIKE '%HUGO MOTTA%'
ORDER BY r.vr_receita DESC;

-- Q204: Doações TSE DE membros da família — para quais candidatos doam
SELECT r.nm_doador,
       r.cpf_cnpj_doador,
       r.nm_candidato,
       r.sg_partido,
       r.sg_uf,
       r.ds_cargo,
       r.vr_receita,
       r.ano_eleicao
FROM tse_receita_candidato r
WHERE r.nm_doador LIKE '%WANDERLEY%NOBREGA%'
   OR r.nm_doador LIKE '%MOTTA WANDERLEY%'
   OR r.nm_doador LIKE '%ILANNA%MOTTA%'
   OR r.nm_doador LIKE '%SEVERINO MEDEIROS%RAMOS%'
   OR r.nm_doador LIKE '%LUANA MEDEIROS%'
ORDER BY r.vr_receita DESC;

-- Q205: Empresas da família com sanções (CEIS/CNEP)
WITH familia_cnpj AS (
    VALUES ('33722496'), ('32830711'), ('08181087'),
    ('58830248'), ('55514713'), ('53041627'), ('55444808'), ('64082599'),
    ('49221790'), ('28214987'), ('59079522'),
    ('10765196'), ('11984747'),
    ('17065074'), ('64199173'), ('08332413'),
    ('05307555'), ('46253251'), ('28548708'),
    ('08716557'), ('04489715'), ('11149864'), ('19161889')
)
SELECT e.razao_social, f.column1 AS cnpj_basico,
       s.nome_sancionado, s.categoria_sancao, s.orgao_sancionador,
       s.dt_inicio_sancao, s.dt_final_sancao, 'CEIS' AS origem
FROM familia_cnpj f
JOIN empresa e ON e.cnpj_basico = f.column1
JOIN ceis_sancao s ON LEFT(s.cpf_cnpj_norm, 8) = f.column1 AND s.tipo_pessoa = 'J'

UNION ALL

SELECT e.razao_social, f.column1,
       s.nome_sancionado, s.categoria_sancao, s.orgao_sancionador,
       s.dt_inicio_sancao, s.dt_final_sancao, 'CNEP'
FROM familia_cnpj f
JOIN empresa e ON e.cnpj_basico = f.column1
JOIN cnep_sancao s ON LEFT(s.cpf_cnpj_norm, 8) = f.column1 AND s.tipo_pessoa = 'J';

-- Q206: Empresas da família com dívida ativa PGFN
WITH familia_cnpj AS (
    VALUES ('33722496'), ('32830711'), ('08181087'),
    ('58830248'), ('55514713'), ('53041627'), ('55444808'), ('64082599'),
    ('49221790'), ('28214987'), ('59079522'),
    ('10765196'), ('11984747'),
    ('17065074'), ('64199173'), ('08332413'),
    ('05307555'), ('46253251'), ('28548708'),
    ('08716557'), ('04489715'), ('11149864'), ('19161889')
),
pgfn_pj AS (
    SELECT LEFT(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g'), 8) AS cnpj_basico,
           COUNT(*) AS qtd_inscricoes,
           SUM(valor_consolidado) AS total_divida,
           STRING_AGG(DISTINCT receita_principal, '; ') AS tipos_divida
    FROM pgfn_divida
    WHERE tipo_pessoa LIKE '%jur%'
    GROUP BY LEFT(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g'), 8)
)
SELECT e.razao_social, f.column1 AS cnpj_basico,
       pgfn.qtd_inscricoes, pgfn.total_divida, pgfn.tipos_divida
FROM familia_cnpj f
JOIN empresa e ON e.cnpj_basico = f.column1
JOIN pgfn_pj pgfn ON pgfn.cnpj_basico = f.column1
ORDER BY pgfn.total_divida DESC;

-- Q207: Contratos estaduais (pb_contrato) com empresas da família
WITH familia_cnpj AS (
    VALUES ('33722496'), ('32830711'), ('08181087'),
    ('58830248'), ('55514713'), ('53041627'), ('55444808'), ('64082599'),
    ('49221790'), ('28214987'), ('59079522'),
    ('10765196'), ('11984747'),
    ('17065074'), ('64199173'), ('08332413'),
    ('05307555'), ('46253251'), ('28548708'),
    ('08716557'), ('04489715'), ('11149864'), ('19161889')
)
SELECT c.numero_contrato,
       c.nome_contratado,
       c.cpfcnpj_contratado,
       c.objeto_contrato,
       c.valor_original,
       c.data_celebracao_contrato,
       c.data_termino_vigencia,
       COALESCE(adi.qtd_aditivos, 0) AS qtd_aditivos,
       COALESCE(adi.total_aditivos, 0) AS total_aditivos
FROM pb_contrato c
LEFT JOIN (
    SELECT codigo_contrato, COUNT(*) AS qtd_aditivos, SUM(valor_aditivo) AS total_aditivos
    FROM pb_aditivo_contrato
    GROUP BY codigo_contrato
) adi ON adi.codigo_contrato = c.codigo_contrato
WHERE LEFT(c.cpfcnpj_contratado, 8) IN (SELECT column1 FROM familia_cnpj)
ORDER BY c.valor_original DESC;

-- Q208: Emendas parlamentares individuais destinadas a Patos
-- (reduto eleitoral da família — a família controla a prefeitura desde 1950)
SELECT nome_emenda, nome_ente, nome_favorecido, cnpj_favorecido,
       SUM(valor) AS total_valor, COUNT(*) AS qtd_parcelas,
       MIN(dt_transacao) AS primeira_parcela,
       MAX(dt_transacao) AS ultima_parcela
FROM emenda_tesouro
WHERE nome_ente = 'Patos' AND uf = 'PB'
GROUP BY nome_emenda, nome_ente, nome_favorecido, cnpj_favorecido
ORDER BY total_valor DESC;

-- Q209: Rede de segundo grau — empresas onde co-sócios da família também são sócios
-- Expande a rede: pega os co-sócios das empresas do núcleo familiar
-- e verifica se esses co-sócios têm OUTRAS empresas que recebem do estado/municípios
WITH nucleo AS (
    SELECT DISTINCT s.cnpj_basico
    FROM socio s
    WHERE s.nome IN (
        'HUGO MOTTA WANDERLEY DA NOBREGA',
        'OLIVIA MOTTA WANDERLEY DA NOBREGA',
        'HUGO MOTTA WANDERLEY DA NOBREGA FILHO',
        'LUANA MEDEIROS MOTTA',
        'NABOR WANDERLEY DA NOBREGA FILHO',
        'ILANNA ARAUJO MOTTA'
    )
),
co_socios AS (
    SELECT DISTINCT s2.nome AS co_socio, s2.cnpj_basico AS empresa_compartilhada
    FROM nucleo n
    JOIN socio s2 ON s2.cnpj_basico = n.cnpj_basico
    WHERE s2.nome NOT IN (
        'HUGO MOTTA WANDERLEY DA NOBREGA',
        'OLIVIA MOTTA WANDERLEY DA NOBREGA',
        'HUGO MOTTA WANDERLEY DA NOBREGA FILHO',
        'LUANA MEDEIROS MOTTA',
        'NABOR WANDERLEY DA NOBREGA FILHO',
        'ILANNA ARAUJO MOTTA',
        'FRANCISCA GOMES ARAUJO MOTA',
        'HELENA WANDERLEY DA NOBREGA LIMA DE FARIAS',
        'PAOLA MEDEIROS MOTTA WANDERLEY'
    )
    AND s2.tipo_socio = 2  -- apenas PF
),
outras_empresas AS (
    SELECT cs.co_socio, s3.cnpj_basico, e.razao_social
    FROM co_socios cs
    JOIN socio s3 ON s3.nome = cs.co_socio AND s3.cnpj_basico != cs.empresa_compartilhada
    JOIN empresa e ON e.cnpj_basico = s3.cnpj_basico
)
SELECT oe.co_socio,
       oe.razao_social,
       oe.cnpj_basico,
       emp.total_empenhado AS empenhado_estado,
       mun.total_empenhado_mun AS empenhado_municipal
FROM outras_empresas oe
LEFT JOIN (
    SELECT cnpj_basico, SUM(valor_empenho) AS total_empenhado
    FROM pb_empenho WHERE cnpj_basico IS NOT NULL AND valor_empenho > 0
    GROUP BY cnpj_basico
) emp ON emp.cnpj_basico = oe.cnpj_basico
LEFT JOIN (
    SELECT LEFT(cpf_cnpj, 8) AS cnpj_basico, SUM(valor_empenhado) AS total_empenhado_mun
    FROM tce_pb_despesa WHERE valor_empenhado > 0 AND LENGTH(cpf_cnpj) >= 14
    GROUP BY LEFT(cpf_cnpj, 8)
) mun ON mun.cnpj_basico = oe.cnpj_basico
WHERE emp.total_empenhado > 0 OR mun.total_empenhado_mun > 0
ORDER BY COALESCE(emp.total_empenhado, 0) + COALESCE(mun.total_empenhado_mun, 0) DESC
LIMIT 50;
