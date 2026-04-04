-- =============================================
-- Queries de fraude: Bolsa Familia
-- Fontes: bolsa_familia, siape_cadastro, socio, empresa
-- =============================================

-- Q38: Servidor federal recebendo Bolsa Familia
-- Detecta: fraude — servidor publico com renda nao deveria receber BF
-- Match por nome + 6 dígitos centrais do CPF + UF
-- Requer: etl.15_normalizar (cpf_digitos em bolsa_familia e siape_cadastro)
SELECT bf.nm_favorecido, bf.cpf_favorecido, bf.uf, bf.nm_municipio,
       bf.valor_parcela,
       sc.nome AS nome_servidor, sc.cpf, sc.org_exercicio,
       sr.remuneracao_basica_bruta
FROM bolsa_familia bf
JOIN siape_cadastro sc ON UPPER(TRIM(bf.nm_favorecido)) = UPPER(TRIM(sc.nome))
    AND bf.cpf_digitos = sc.cpf_digitos
LEFT JOIN siape_remuneracao sr ON sr.id_servidor_portal = sc.id_servidor_portal
WHERE bf.uf = sc.uf_exercicio
  AND bf.cpf_digitos IS NOT NULL AND bf.cpf_digitos != ''
ORDER BY sr.remuneracao_basica_bruta DESC NULLS LAST
LIMIT 500;

-- Q39: Sócio de empresa ativa recebendo Bolsa Familia
-- Detecta: pessoa com participação societária em empresa comercial ativa não deveria receber BF
-- Match por nome + 6 dígitos centrais do CPF (ambas fontes mascaram CPF)
-- Filtra: apenas empresas ativas (situacao_cadastral=2), exclui associações/cooperativas/etc
SELECT bf.nm_favorecido, bf.cpf_favorecido, bf.uf, bf.nm_municipio,
       bf.valor_parcela,
       est.cnpj_completo,
       e.razao_social, e.capital_social,
       CASE e.porte
           WHEN 1 THEN 'Nao informado'
           WHEN 3 THEN 'Micro/Pequena'
           WHEN 5 THEN 'Demais (media/grande)'
           ELSE 'Porte ' || e.porte
       END AS porte,
       dnj.descricao AS natureza_juridica
FROM bolsa_familia bf
JOIN socio s ON UPPER(TRIM(bf.nm_favorecido)) = UPPER(TRIM(s.nome))
    AND bf.cpf_digitos = s.cpf_cnpj_norm
    AND s.tipo_socio = 2  -- pessoa fisica
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN estabelecimento est ON est.cnpj_basico = e.cnpj_basico
    AND est.cnpj_ordem = '0001'  -- matriz
    AND est.situacao_cadastral = '2'  -- ativa
LEFT JOIN dom_natureza_juridica dnj ON dnj.codigo = e.natureza_juridica
WHERE e.porte IN (3, 5)  -- medio ou grande porte
  AND bf.cpf_digitos IS NOT NULL AND bf.cpf_digitos != ''
  AND e.natureza_juridica NOT IN ('3999', '4090', '4120', '3085', '3069', '3220')
ORDER BY e.capital_social DESC NULLS LAST
LIMIT 500;

-- Q40: Beneficiário Bolsa Familia que também recebe CPGF (cartão corporativo)
-- Detecta: uso indevido — mesma pessoa recebendo benefício social e usando cartão do governo
-- Match por nome + 6 dígitos centrais do CPF
-- Requer: etl.15_normalizar (cpf_digitos em bolsa_familia, cpf_portador_digitos em cpgf)
-- FIX #16: pre-agregar BF para evitar duplicação por valor_parcela distinto
WITH bf_agg AS (
    SELECT nm_favorecido, cpf_favorecido, uf, cpf_digitos,
           MAX(valor_parcela) AS ultima_parcela,
           COUNT(*) AS meses_bf
    FROM bolsa_familia
    WHERE cpf_digitos IS NOT NULL AND cpf_digitos != ''
    GROUP BY nm_favorecido, cpf_favorecido, uf, cpf_digitos
)
SELECT bf.nm_favorecido, bf.cpf_favorecido, bf.uf,
       bf.ultima_parcela, bf.meses_bf,
       ct.nome_portador, ct.cpf_portador,
       COUNT(*) AS qtd_transacoes_cpgf,
       SUM(ct.valor_transacao) AS total_cpgf
FROM bf_agg bf
JOIN cpgf_transacao ct ON UPPER(TRIM(bf.nm_favorecido)) = UPPER(TRIM(ct.nome_portador))
    AND bf.cpf_digitos = ct.cpf_portador_digitos
GROUP BY bf.nm_favorecido, bf.cpf_favorecido, bf.uf,
         bf.ultima_parcela, bf.meses_bf,
         ct.nome_portador, ct.cpf_portador
ORDER BY total_cpgf DESC;

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
-- FIX #12: join por cpf_digitos (antes era só nome+UF, gerando falsos positivos massivos)
SELECT bf.nm_favorecido, bf.cpf_favorecido, bf.uf, bf.valor_parcela,
       tc.nm_candidato, tc.ds_cargo, tc.sg_partido, tc.ano_eleicao,
       COALESCE(pb.total_bens, 0) AS patrimonio_declarado
FROM bolsa_familia bf
JOIN tse_candidato tc ON bf.cpf_digitos = tc.cpf_digitos
    AND bf.uf = tc.sg_uf
LEFT JOIN (
    SELECT sq_candidato, ano_eleicao, SUM(valor_bem) AS total_bens
    FROM tse_bem_candidato GROUP BY sq_candidato, ano_eleicao
) pb ON pb.sq_candidato = tc.sq_candidato AND pb.ano_eleicao = tc.ano_eleicao
WHERE bf.cpf_digitos IS NOT NULL AND bf.cpf_digitos != ''
  AND tc.cpf_digitos IS NOT NULL AND tc.cpf_digitos != '000000'
  AND pb.total_bens > 50000  -- patrimonio > 50k e recebe BF
ORDER BY pb.total_bens DESC
LIMIT 500;
