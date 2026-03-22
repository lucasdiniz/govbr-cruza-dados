-- =============================================
-- Queries de fraude: TSE (Eleicoes)
-- Fontes: tse_candidato, tse_bem_candidato, tse_receita_candidato, tse_despesa_candidato
-- =============================================

-- Q33: Candidato que é sócio de empresa fornecedora do governo
-- Detecta: conflito de interesse — político com participação em empresa que recebe contratos
SELECT tc.nm_candidato, tc.cpf, tc.ds_cargo, tc.sg_partido, tc.sg_uf, tc.ano_eleicao,
       s.cnpj_basico, e.razao_social,
       pc.uf AS uf_contrato, pc.municipio_nome AS municipio_contrato,
       COUNT(DISTINCT pc.numero_controle_pncp) AS qtd_contratos,
       SUM(pc.valor_global) AS total_contratos
FROM tse_candidato tc
JOIN socio s ON s.cpf_cnpj_socio = tc.cpf
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN pncp_contrato pc ON pc.cnpj_basico_fornecedor = s.cnpj_basico
WHERE tc.cpf IS NOT NULL AND tc.cpf NOT IN ('-1', '-4', '')
GROUP BY tc.nm_candidato, tc.cpf, tc.ds_cargo, tc.sg_partido, tc.sg_uf, tc.ano_eleicao,
         s.cnpj_basico, e.razao_social, pc.uf, pc.municipio_nome
HAVING SUM(pc.valor_global) > 100000
ORDER BY total_contratos DESC;

-- Q34: Doador de campanha que também é fornecedor do governo
-- Detecta: quid pro quo — empresa doa para candidato e recebe contratos
SELECT tr.nm_candidato, tr.nr_cpf_candidato, tr.ds_cargo, tr.sg_partido,
       tr.cpf_cnpj_doador, tr.nm_doador,
       SUM(tr.vr_receita) AS total_doado,
       COUNT(DISTINCT pc.numero_controle_pncp) AS qtd_contratos,
       SUM(pc.valor_global) AS total_contratos
FROM tse_receita_candidato tr
JOIN pncp_contrato pc ON LEFT(pc.ni_fornecedor, 14) = tr.cpf_cnpj_doador
WHERE tr.cpf_cnpj_doador IS NOT NULL
  AND LENGTH(tr.cpf_cnpj_doador) >= 14  -- CNPJ
  AND tr.cpf_cnpj_doador NOT IN ('-1', '-4', '')
GROUP BY tr.nm_candidato, tr.nr_cpf_candidato, tr.ds_cargo, tr.sg_partido,
         tr.cpf_cnpj_doador, tr.nm_doador
HAVING SUM(pc.valor_global) > 500000
ORDER BY total_contratos DESC;

-- Q35: Patrimônio declarado incompatível com renda
-- Detecta: enriquecimento ilícito — crescimento patrimonial desproporcional entre eleições
SELECT tc1.nm_candidato, tc1.cpf, tc1.ds_cargo AS cargo_anterior,
       tc2.ds_cargo AS cargo_atual,
       tc1.ano_eleicao AS ano_anterior, tc2.ano_eleicao AS ano_atual,
       p1.total_bens AS patrimonio_anterior,
       p2.total_bens AS patrimonio_atual,
       p2.total_bens - p1.total_bens AS crescimento,
       CASE WHEN p1.total_bens > 0
            THEN ROUND(((p2.total_bens - p1.total_bens) / p1.total_bens) * 100, 1)
            ELSE NULL END AS pct_crescimento
FROM tse_candidato tc1
JOIN tse_candidato tc2 ON tc1.cpf = tc2.cpf AND tc2.ano_eleicao > tc1.ano_eleicao
JOIN (
    SELECT sq_candidato, ano_eleicao, SUM(valor_bem) AS total_bens
    FROM tse_bem_candidato GROUP BY sq_candidato, ano_eleicao
) p1 ON p1.sq_candidato = tc1.sq_candidato AND p1.ano_eleicao = tc1.ano_eleicao
JOIN (
    SELECT sq_candidato, ano_eleicao, SUM(valor_bem) AS total_bens
    FROM tse_bem_candidato GROUP BY sq_candidato, ano_eleicao
) p2 ON p2.sq_candidato = tc2.sq_candidato AND p2.ano_eleicao = tc2.ano_eleicao
WHERE tc1.cpf IS NOT NULL AND tc1.cpf NOT IN ('-1', '-4', '')
  AND p1.total_bens > 0
  AND p2.total_bens > p1.total_bens * 5  -- cresceu mais de 500%
ORDER BY crescimento DESC
LIMIT 200;

-- Q36: Candidato com sanção ativa (CEIS/CNEP) ainda concorrendo
-- Detecta: candidato que deveria estar impedido
SELECT tc.nm_candidato, tc.cpf, tc.ds_cargo, tc.sg_partido, tc.sg_uf, tc.ano_eleicao,
       tc.ds_situacao_candidatura,
       cs.categoria_sancao, cs.codigo_sancao, cs.orgao_sancionador,
       cs.dt_inicio_sancao, cs.dt_final_sancao
FROM tse_candidato tc
JOIN socio s ON s.cpf_cnpj_socio = tc.cpf
JOIN ceis_sancao cs ON LEFT(cs.cpf_cnpj_sancionado, 8) = s.cnpj_basico
WHERE tc.cpf IS NOT NULL AND tc.cpf NOT IN ('-1', '-4', '')
ORDER BY tc.ano_eleicao DESC, tc.nm_candidato;

-- Q37: Candidato que recebeu emendas parlamentares para empresas onde é sócio
-- Detecta: auto-benefício via emendas
SELECT tc.nm_candidato, tc.cpf, tc.ds_cargo, tc.sg_partido, tc.sg_uf,
       s.cnpj_basico, e.razao_social,
       ef.nome_autor AS autor_emenda,
       ef.uf_favorecido, ef.municipio_favorecido,
       SUM(ef.valor_recebido) AS total_emendas
FROM tse_candidato tc
JOIN socio s ON s.cpf_cnpj_socio = tc.cpf
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN emenda_favorecido ef ON ef.cnpj_basico_favorecido = s.cnpj_basico
WHERE tc.cpf IS NOT NULL AND tc.cpf NOT IN ('-1', '-4', '')
  AND ef.cnpj_basico_favorecido IS NOT NULL
GROUP BY tc.nm_candidato, tc.cpf, tc.ds_cargo, tc.sg_partido, tc.sg_uf,
         s.cnpj_basico, e.razao_social, ef.nome_autor,
         ef.uf_favorecido, ef.municipio_favorecido
HAVING SUM(ef.valor_recebido) > 100000
ORDER BY total_emendas DESC;
