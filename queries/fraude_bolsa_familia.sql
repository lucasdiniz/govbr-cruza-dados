-- =============================================
-- Queries de fraude: Bolsa Familia
-- Fontes: bolsa_familia, siape_cadastro, socio, empresa
-- =============================================

-- Q38: Servidor federal recebendo Bolsa Familia
-- Detecta: fraude — servidor publico com renda nao deveria receber BF
-- Match por nome + 6 dígitos centrais do CPF + UF
SELECT bf.nm_favorecido, bf.cpf_favorecido, bf.uf, bf.nm_municipio,
       bf.valor_parcela,
       sc.nome AS nome_servidor, sc.cpf_servidor, sc.org_exercicio,
       sr.remuneracao_basica
FROM bolsa_familia bf
JOIN siape_cadastro sc ON UPPER(TRIM(bf.nm_favorecido)) = UPPER(TRIM(sc.nome))
    AND REGEXP_REPLACE(bf.cpf_favorecido, '[^0-9]', '', 'g')
      = REGEXP_REPLACE(sc.cpf, '[^0-9]', '', 'g')
LEFT JOIN siape_remuneracao sr ON sr.id_servidor_portal = sc.id_servidor_portal
WHERE bf.uf = sc.uf_exercicio
  AND bf.cpf_favorecido IS NOT NULL AND bf.cpf_favorecido != ''
ORDER BY sr.remuneracao_basica DESC NULLS LAST
LIMIT 500;

-- Q39: Sócio de empresa recebendo Bolsa Familia
-- Detecta: pessoa com participação societária em empresa comercial não deveria receber BF
-- Match por nome + 6 dígitos centrais do CPF (ambas fontes mascaram CPF)
-- Exclui associações, cooperativas, produtores rurais, condominios (sócio não implica renda)
-- Resultado: 59.168 casos (2026-03-21)
SELECT bf.nm_favorecido, bf.cpf_favorecido, bf.uf, bf.nm_municipio,
       bf.valor_parcela,
       s.nome AS nome_socio, s.cnpj_basico,
       e.razao_social, e.porte, e.natureza_juridica
FROM bolsa_familia bf
JOIN socio s ON UPPER(TRIM(bf.nm_favorecido)) = UPPER(TRIM(s.nome))
    AND REGEXP_REPLACE(bf.cpf_favorecido, '[^0-9]', '', 'g')
      = REGEXP_REPLACE(s.cpf_cnpj_socio, '[^0-9]', '', 'g')
    AND s.tipo_socio = 2  -- pessoa fisica
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
WHERE e.porte IN (3, 5)  -- medio ou grande porte
  AND bf.cpf_favorecido IS NOT NULL AND bf.cpf_favorecido != ''
  AND e.natureza_juridica NOT IN ('3999', '4090', '4120', '3085', '3069', '3220')
ORDER BY e.porte DESC, bf.nm_favorecido
LIMIT 500;

-- Q40: Beneficiário Bolsa Familia que também recebe CPGF (cartão corporativo)
-- Detecta: uso indevido — mesma pessoa recebendo benefício social e usando cartão do governo
-- Match por nome + 6 dígitos centrais do CPF
SELECT bf.nm_favorecido, bf.cpf_favorecido, bf.uf, bf.valor_parcela,
       ct.nome_portador, ct.cpf_portador,
       COUNT(*) AS qtd_transacoes_cpgf,
       SUM(ct.valor_transacao) AS total_cpgf
FROM bolsa_familia bf
JOIN cpgf_transacao ct ON UPPER(TRIM(bf.nm_favorecido)) = UPPER(TRIM(ct.nome_portador))
    AND REGEXP_REPLACE(bf.cpf_favorecido, '[^0-9]', '', 'g')
      = REGEXP_REPLACE(ct.cpf_portador, '[^0-9]', '', 'g')
WHERE bf.cpf_favorecido IS NOT NULL AND bf.cpf_favorecido != ''
GROUP BY bf.nm_favorecido, bf.cpf_favorecido, bf.uf, bf.valor_parcela,
         ct.nome_portador, ct.cpf_portador
ORDER BY total_cpgf DESC
LIMIT 500;

-- Q41: Municipios com maior concentracao de Bolsa Familia per capita
-- Detecta: possível fraude sistêmica municipal
SELECT bf.uf, bf.nm_municipio, bf.cd_municipio_siafi,
       COUNT(*) AS qtd_beneficiarios,
       SUM(bf.valor_parcela) AS total_pago,
       ROUND(AVG(bf.valor_parcela), 2) AS media_parcela
FROM bolsa_familia bf
GROUP BY bf.uf, bf.nm_municipio, bf.cd_municipio_siafi
ORDER BY qtd_beneficiarios DESC
LIMIT 100;

-- Q42: Candidato a vereador/prefeito que recebe Bolsa Familia
-- Detecta: incompatibilidade — candidato com patrimônio declarado recebendo BF
SELECT bf.nm_favorecido, bf.cpf_favorecido, bf.uf, bf.valor_parcela,
       tc.nm_candidato, tc.ds_cargo, tc.sg_partido, tc.ano_eleicao,
       COALESCE(pb.total_bens, 0) AS patrimonio_declarado
FROM bolsa_familia bf
JOIN tse_candidato tc ON UPPER(TRIM(bf.nm_favorecido)) = UPPER(TRIM(tc.nm_candidato))
    AND bf.uf = tc.sg_uf
LEFT JOIN (
    SELECT sq_candidato, ano_eleicao, SUM(valor_bem) AS total_bens
    FROM tse_bem_candidato GROUP BY sq_candidato, ano_eleicao
) pb ON pb.sq_candidato = tc.sq_candidato AND pb.ano_eleicao = tc.ano_eleicao
WHERE pb.total_bens > 50000  -- patrimonio > 50k e recebe BF
ORDER BY pb.total_bens DESC
LIMIT 500;
