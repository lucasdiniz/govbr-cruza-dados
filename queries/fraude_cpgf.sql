-- Q09: Portador com gastos concentrados em único favorecido
SELECT cpf_portador, nome_portador,
       cnpj_cpf_favorecido, nome_favorecido,
       COUNT(*) AS qtd_transacoes,
       SUM(valor_transacao) AS total_gasto,
       MIN(dt_transacao) AS primeira, MAX(dt_transacao) AS ultima
FROM cpgf_transacao
WHERE valor_transacao > 0
GROUP BY cpf_portador, nome_portador, cnpj_cpf_favorecido, nome_favorecido
HAVING SUM(valor_transacao) > 50000 AND COUNT(*) > 10
ORDER BY total_gasto DESC;

-- Q10: Portador de cartão que é sócio de empresa fornecedora
SELECT ct.nome_portador, ct.cpf_portador,
       s.cnpj_basico, e.razao_social,
       est.uf AS uf_empresa, est.municipio AS municipio_empresa,
       SUM(ct.valor_transacao) AS gasto_cartao,
       COUNT(*) AS transacoes
FROM cpgf_transacao ct
JOIN socio s ON ct.cpf_portador_digitos = s.cpf_cnpj_norm
  AND s.tipo_socio = 2
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_basico = s.cnpj_basico
  AND est.cnpj_ordem = '0001' AND est.situacao_cadastral = '2'
WHERE ct.valor_transacao > 0
  AND ct.cpf_portador_digitos IS NOT NULL AND ct.cpf_portador_digitos != '000000'
GROUP BY ct.nome_portador, ct.cpf_portador, s.cnpj_basico, e.razao_social,
         est.uf, est.municipio
HAVING SUM(ct.valor_transacao) > 10000
ORDER BY gasto_cartao DESC;

-- Q11: Favorecido do CPGF é empresa inativa ou recém-criada
SELECT ct.cnpj_cpf_favorecido, ct.nome_favorecido,
       est.uf, est.municipio,
       est.situacao_cadastral, est.dt_inicio_atividade,
       SUM(ct.valor_transacao) AS total_recebido,
       COUNT(*) AS transacoes
FROM cpgf_transacao ct
JOIN estabelecimento est ON est.cnpj_completo = ct.cnpj_cpf_favorecido
WHERE est.situacao_cadastral IN (3, 4, 8)
   OR (ct.dt_transacao - est.dt_inicio_atividade) < 90
GROUP BY ct.cnpj_cpf_favorecido, ct.nome_favorecido,
         est.uf, est.municipio, est.situacao_cadastral, est.dt_inicio_atividade
ORDER BY total_recebido DESC;

-- Q19: Fracionamento de despesa (valores logo abaixo de limites)
SELECT cpf_portador, nome_portador,
       codigo_unidade_gestora, nome_unidade_gestora,
       dt_transacao, COUNT(*) AS transacoes_no_dia,
       SUM(valor_transacao) AS total_dia,
       AVG(valor_transacao) AS media_transacao
FROM cpgf_transacao
WHERE valor_transacao BETWEEN 700 AND 999
GROUP BY cpf_portador, nome_portador, codigo_unidade_gestora,
         nome_unidade_gestora, dt_transacao
HAVING COUNT(*) >= 3
ORDER BY total_dia DESC;
