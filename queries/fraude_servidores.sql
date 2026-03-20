-- Q21: Servidor federal que é sócio de empresa fornecedora do seu próprio órgão
SELECT sc.nome, sc.cpf, sc.org_exercicio, sc.descricao_cargo,
       s.cnpj_basico, e.razao_social,
       pc.objeto, pc.valor_global, pc.cnpj_orgao
FROM siape_cadastro sc
JOIN socio s ON s.cpf_cnpj_socio LIKE '%' || SUBSTRING(sc.cpf, 5, 6) || '%'
  AND s.tipo_socio = 2
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN pncp_contrato pc ON LEFT(pc.ni_fornecedor, 8) = s.cnpj_basico
WHERE sc.situacao_vinculo = 'ATIVO PERMANENTE'
  AND SUBSTRING(sc.cpf, 5, 6) != '000000'
  AND pc.valor_global > 10000
ORDER BY pc.valor_global DESC
LIMIT 20;

-- Q22: Servidor que usa cartão corporativo em empresa onde é sócio
SELECT sc.nome, sc.cpf, sc.org_exercicio,
       ct.cnpj_cpf_favorecido, ct.nome_favorecido,
       s.cnpj_basico, e.razao_social,
       SUM(ct.valor_transacao) AS total_gasto
FROM siape_cadastro sc
JOIN cpgf_transacao ct ON SUBSTRING(sc.cpf, 5, 6) = SUBSTRING(ct.cpf_portador, 5, 6)
  AND SUBSTRING(sc.cpf, 5, 6) != '000000'
JOIN socio s ON s.cpf_cnpj_socio LIKE '%' || SUBSTRING(sc.cpf, 5, 6) || '%'
  AND s.tipo_socio = 2
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
WHERE LEFT(ct.cnpj_cpf_favorecido, 8) = s.cnpj_basico
GROUP BY sc.nome, sc.cpf, sc.org_exercicio,
         ct.cnpj_cpf_favorecido, ct.nome_favorecido,
         s.cnpj_basico, e.razao_social
ORDER BY total_gasto DESC;

-- Q23: Servidores com remuneração acima do teto constitucional
SELECT sc.nome, sc.cpf, sc.descricao_cargo, sc.org_exercicio,
       sr.remuneracao_basica_bruta,
       sr.remuneracao_apos_deducoes,
       sr.total_verbas_indenizatorias,
       (sr.remuneracao_basica_bruta + COALESCE(sr.total_verbas_indenizatorias, 0)) AS total_bruto
FROM siape_remuneracao sr
JOIN siape_cadastro sc ON sc.id_servidor_portal = sr.id_servidor_portal
WHERE sr.remuneracao_basica_bruta > 46000  -- teto ~R$46k em 2024
ORDER BY total_bruto DESC
LIMIT 20;

-- Q24: Servidor favorecido por emenda parlamentar
SELECT sc.nome, sc.cpf, sc.org_exercicio, sc.descricao_cargo,
       ef.nome_autor, ef.codigo_emenda,
       ef.valor_recebido, ef.nome_favorecido
FROM siape_cadastro sc
JOIN emenda_favorecido ef ON ef.codigo_favorecido LIKE '%' || SUBSTRING(sc.cpf, 5, 6) || '%'
  AND ef.tipo_favorecido ILIKE '%FISICA%'
  AND SUBSTRING(sc.cpf, 5, 6) != '000000'
WHERE sc.situacao_vinculo = 'ATIVO PERMANENTE'
  AND ef.valor_recebido > 10000
ORDER BY ef.valor_recebido DESC
LIMIT 20;
