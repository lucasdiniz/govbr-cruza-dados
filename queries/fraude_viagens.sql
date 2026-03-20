-- Q29: Servidor que viaja para cidade onde empresa dele tem sede
SELECT v.nome_viajante, v.cpf_viajante, v.cargo,
       v.nome_orgao_solicitante, v.destinos, v.dt_inicio,
       v.valor_diarias + COALESCE(v.valor_passagens, 0) AS custo_viagem,
       e.razao_social, est.uf, est.municipio
FROM viagem v
JOIN socio s ON s.cpf_cnpj_socio LIKE '%' || SUBSTRING(v.cpf_viajante, 5, 6) || '%'
  AND s.tipo_socio = 2
  AND SUBSTRING(v.cpf_viajante, 5, 6) != '000000'
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN estabelecimento est ON est.cnpj_basico = s.cnpj_basico
WHERE v.destinos ILIKE '%' || est.uf || '%'
  AND v.valor_diarias > 500
ORDER BY custo_viagem DESC
LIMIT 20;

-- Q30: Servidor que mais gasta com viagens
SELECT cpf_viajante, nome_viajante, cargo,
       nome_orgao_solicitante,
       COUNT(*) AS qtd_viagens,
       SUM(valor_diarias) AS total_diarias,
       SUM(valor_passagens) AS total_passagens,
       SUM(valor_diarias + COALESCE(valor_passagens, 0)) AS custo_total
FROM viagem
WHERE valor_diarias > 0
GROUP BY cpf_viajante, nome_viajante, cargo, nome_orgao_solicitante
HAVING SUM(valor_diarias + COALESCE(valor_passagens, 0)) > 100000
ORDER BY custo_total DESC
LIMIT 20;

-- Q31: Viagens urgentes com alto valor (possivel fraude para evitar licitacao de passagem)
SELECT nome_viajante, cpf_viajante, cargo,
       nome_orgao_solicitante, destinos, motivo,
       dt_inicio, valor_diarias, valor_passagens,
       justificativa_urgencia
FROM viagem
WHERE viagem_urgente = 'SIM'
  AND (valor_diarias + COALESCE(valor_passagens, 0)) > 10000
ORDER BY (valor_diarias + COALESCE(valor_passagens, 0)) DESC
LIMIT 20;

-- Q32: Servidor expulso (CEAF) que ainda faz viagens a servico
SELECT ce.nome_sancionado, ce.cpf_cnpj_sancionado,
       ce.categoria_sancao, ce.dt_inicio_sancao,
       v.nome_viajante, v.destinos, v.dt_inicio AS dt_viagem,
       v.valor_diarias
FROM ceaf_expulsao ce
JOIN viagem v ON SUBSTRING(REGEXP_REPLACE(ce.cpf_cnpj_sancionado, '[^0-9]', '', 'g'), 4, 6)
               = SUBSTRING(v.cpf_viajante, 5, 6)
  AND SUBSTRING(v.cpf_viajante, 5, 6) != '000000'
WHERE v.dt_inicio > ce.dt_inicio_sancao
ORDER BY v.dt_inicio DESC
LIMIT 20;
