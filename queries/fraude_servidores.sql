-- Q21: Servidor federal que é sócio de empresa fornecedora do seu próprio órgão
SELECT sc.nome, sc.cpf, sc.org_exercicio, sc.descricao_cargo,
       s.cnpj_basico, e.razao_social,
       pc.uf AS uf_contrato, pc.municipio_nome AS municipio_contrato,
       pc.objeto, pc.valor_global, pc.cnpj_orgao
FROM siape_cadastro sc
JOIN socio s ON sc.cpf_digitos = s.cpf_cnpj_norm
  AND s.tipo_socio = 2
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN pncp_contrato pc ON pc.cnpj_basico_fornecedor = s.cnpj_basico
WHERE sc.situacao_vinculo = 'ATIVO PERMANENTE'
  AND sc.cpf_digitos IS NOT NULL AND sc.cpf_digitos != '000000'
  AND pc.valor_global > 10000
ORDER BY pc.valor_global DESC
LIMIT 20;

-- Q22: Servidor que usa cartão corporativo em empresa onde é sócio
SELECT sc.nome, sc.cpf, sc.org_exercicio,
       ct.cnpj_cpf_favorecido, ct.nome_favorecido,
       s.cnpj_basico, e.razao_social,
       est.uf AS uf_empresa, est.municipio AS municipio_empresa,
       SUM(ct.valor_transacao) AS total_gasto
FROM siape_cadastro sc
JOIN cpgf_transacao ct ON sc.cpf_digitos = ct.cpf_portador_digitos
  AND sc.cpf_digitos IS NOT NULL AND sc.cpf_digitos != '000000'
JOIN socio s ON sc.cpf_digitos = s.cpf_cnpj_norm
  AND s.tipo_socio = 2
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_basico = s.cnpj_basico
  AND est.cnpj_ordem = '0001' AND est.situacao_cadastral = '2'
WHERE LEFT(ct.cnpj_cpf_favorecido, 8) = s.cnpj_basico
GROUP BY sc.nome, sc.cpf, sc.org_exercicio,
         ct.cnpj_cpf_favorecido, ct.nome_favorecido,
         s.cnpj_basico, e.razao_social, est.uf, est.municipio
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
-- Match por nome + 6 dígitos centrais do CPF (emenda PF tem CPF mascarado)
SELECT sc.nome, sc.cpf, sc.org_exercicio, sc.descricao_cargo,
       sc.uf_exercicio,
       ef.nome_autor, ef.codigo_emenda,
       ef.valor_recebido, ef.nome_favorecido
FROM siape_cadastro sc
JOIN emenda_favorecido ef ON UPPER(TRIM(sc.nome)) = UPPER(TRIM(ef.nome_favorecido))
  AND sc.cpf_digitos = REGEXP_REPLACE(ef.codigo_favorecido, '[^0-9]', '', 'g')
  AND ef.tipo_favorecido = 'Pessoa Fisica'
WHERE sc.situacao_vinculo = 'ATIVO PERMANENTE'
  AND sc.cpf_digitos IS NOT NULL AND sc.cpf_digitos <> ''
  AND ef.valor_recebido > 10000
ORDER BY ef.valor_recebido DESC
LIMIT 500;
