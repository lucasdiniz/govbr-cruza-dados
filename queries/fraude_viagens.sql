-- Q29: Servidor que viaja para cidade onde empresa dele tem sede
-- FIX #5: filtro qualificacao (sócio-administrador/sócio) para reduzir ruído
-- FIX #8: match por município (antes era só UF, gerando falsos positivos)
SELECT v.nome_viajante, v.cpf_viajante, v.cargo,
       v.nome_orgao_solicitante, v.destinos, v.dt_inicio,
       v.valor_diarias + COALESCE(v.valor_passagens, 0) AS custo_viagem,
       e.razao_social, est.uf, est.municipio
FROM viagem v
JOIN socio s ON v.cpf_viajante_digitos = s.cpf_cnpj_norm
  AND s.tipo_socio = 2
  AND s.qualificacao IN ('22', '49')  -- sócio-administrador, sócio
  AND v.cpf_viajante_digitos IS NOT NULL AND v.cpf_viajante_digitos != '000000'
  AND UPPER(TRIM(v.nome_viajante)) = UPPER(TRIM(s.nome))
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN estabelecimento est ON est.cnpj_basico = s.cnpj_basico
  AND est.cnpj_ordem = '0001' AND est.situacao_cadastral = '2'
WHERE v.destinos ILIKE '%' || est.municipio || '%'
  AND v.valor_diarias > 500
ORDER BY custo_viagem DESC;

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
ORDER BY custo_total DESC;

-- Q31: Viagens urgentes com alto valor (possivel fraude para evitar licitacao de passagem)
SELECT nome_viajante, cpf_viajante, cargo,
       nome_orgao_solicitante, destinos, motivo,
       dt_inicio, valor_diarias, valor_passagens,
       justificativa_urgencia
FROM viagem
WHERE viagem_urgente = 'SIM'
  AND (valor_diarias + COALESCE(valor_passagens, 0)) > 10000
ORDER BY (valor_diarias + COALESCE(valor_passagens, 0)) DESC;

-- Q32: Servidor expulso (CEAF) que ainda faz viagens a servico
-- FIX #6: adicionado match por nome para evitar falsos positivos em CPF 6-dígitos
SELECT ce.nome_sancionado, ce.cpf_cnpj_sancionado,
       ce.categoria_sancao, ce.dt_inicio_sancao,
       v.nome_viajante, v.destinos, v.dt_inicio AS dt_viagem,
       v.valor_diarias
FROM ceaf_expulsao ce
JOIN viagem v ON ce.cpf_cnpj_norm = v.cpf_viajante_digitos
  AND v.cpf_viajante_digitos IS NOT NULL AND v.cpf_viajante_digitos != '000000'
  AND UPPER(TRIM(ce.nome_sancionado)) = UPPER(TRIM(v.nome_viajante))
WHERE v.dt_inicio > ce.dt_inicio_sancao
ORDER BY v.dt_inicio DESC;
