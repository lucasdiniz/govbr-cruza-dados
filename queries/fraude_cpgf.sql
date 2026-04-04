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
  AND UPPER(TRIM(ct.nome_portador)) = UPPER(TRIM(s.nome))
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

-- Q19: Fracionamento de despesa (valores logo abaixo de limites legais por período)
-- Limites de pronto pagamento (pequeno vulto) por período:
--   Até 2018:    R$800   (1% do Convite R$80k, Portaria MF 95/2002)
--   2018-2021:   R$880   (0.5% do Convite R$176k, Decreto 9.412/18)
--   Abr/2021:    R$10.000   (20% de R$50k, Lei 14.133/21)
--   2022:        R$10.604   (Decreto 10.922/21)
--   2023:        R$11.441   (Decreto 11.317/22)
--   2024:        R$11.981   (Decreto 11.871/23)
--   2025:        R$12.545   (Decreto 12.343/24)
--   2026:        R$13.098   (Decreto 12.807/25)
-- Limites de dispensa compras/servicos (art.75 II):
--   Até 2018: R$17.600 | 2018-2021: R$17.600 | Abr/2021: R$50.000
--   2022: R$54.020 | 2023: R$57.208 | 2024: R$59.906
--   2025: R$62.725 | 2026: R$65.492
-- Detecta transacoes entre 60-100% do limite vigente, agrupadas por dia e mes
-- Tambem inclui faixa fixa R$700-999 (pequeno vulto historico, suspeito em qualquer periodo)
WITH limites AS (
  SELECT dt_transacao,
    CASE
      WHEN dt_transacao < '2018-06-01' THEN 800.00
      WHEN dt_transacao < '2021-04-01' THEN 880.00
      WHEN dt_transacao < '2022-01-01' THEN 10000.00
      WHEN dt_transacao < '2023-01-01' THEN 10804.08
      WHEN dt_transacao < '2024-01-01' THEN 11441.66
      WHEN dt_transacao < '2025-01-01' THEN 11981.20
      WHEN dt_transacao < '2026-01-01' THEN 12545.11
      ELSE 13098.42
    END AS lim_pronto_pgto,
    CASE
      WHEN dt_transacao < '2021-04-01' THEN 17600.00
      WHEN dt_transacao < '2022-01-01' THEN 50000.00
      WHEN dt_transacao < '2023-01-01' THEN 54020.41
      WHEN dt_transacao < '2024-01-01' THEN 57208.33
      WHEN dt_transacao < '2025-01-01' THEN 59906.02
      WHEN dt_transacao < '2026-01-01' THEN 62725.59
      ELSE 65492.11
    END AS lim_dispensa,
    cpf_portador, nome_portador, cnpj_cpf_favorecido, nome_favorecido,
    codigo_unidade_gestora, nome_unidade_gestora, valor_transacao
  FROM cpgf_transacao
  WHERE valor_transacao > 0
    AND cpf_portador IS NOT NULL AND cpf_portador != ''  -- FIX #5: excluir transações sigilosas
)
SELECT * FROM (
  SELECT 'dia' AS granularidade,
         cpf_portador, nome_portador,
         cnpj_cpf_favorecido, nome_favorecido,
         codigo_unidade_gestora, nome_unidade_gestora,
         dt_transacao::text AS periodo,
         COUNT(*) AS transacoes,
         SUM(valor_transacao) AS total,
         AVG(valor_transacao) AS media_transacao,
         MAX(lim_pronto_pgto) AS limite_pronto_pgto,
         MAX(lim_dispensa) AS limite_dispensa,
         CASE
             WHEN AVG(valor_transacao) BETWEEN 700 AND 999 THEN 'abaixo_1k_fixo'
             WHEN AVG(valor_transacao) >= MAX(lim_pronto_pgto) * 0.60
                  AND AVG(valor_transacao) < MAX(lim_pronto_pgto) THEN 'abaixo_pronto_pgto'
             WHEN AVG(valor_transacao) >= MAX(lim_dispensa) * 0.60
                  AND AVG(valor_transacao) < MAX(lim_dispensa) THEN 'abaixo_dispensa'
             ELSE 'outra_faixa'
         END AS faixa_suspeita
  FROM limites
  WHERE dt_transacao IS NOT NULL
  GROUP BY cpf_portador, nome_portador, cnpj_cpf_favorecido, nome_favorecido,
           codigo_unidade_gestora, nome_unidade_gestora, dt_transacao
  HAVING COUNT(*) >= 3
    AND (AVG(valor_transacao) BETWEEN 700 AND 999
         OR (AVG(valor_transacao) >= MAX(lim_pronto_pgto) * 0.60 AND AVG(valor_transacao) < MAX(lim_pronto_pgto))
         OR (AVG(valor_transacao) >= MAX(lim_dispensa) * 0.60 AND AVG(valor_transacao) < MAX(lim_dispensa)))

  UNION ALL

  SELECT 'mes' AS granularidade,
         cpf_portador, nome_portador,
         cnpj_cpf_favorecido, nome_favorecido,
         codigo_unidade_gestora, nome_unidade_gestora,
         to_char(dt_transacao, 'YYYY-MM') AS periodo,
         COUNT(*) AS transacoes,
         SUM(valor_transacao) AS total,
         AVG(valor_transacao) AS media_transacao,
         MAX(lim_pronto_pgto) AS limite_pronto_pgto,
         MAX(lim_dispensa) AS limite_dispensa,
         CASE
             WHEN AVG(valor_transacao) BETWEEN 700 AND 999 THEN 'abaixo_1k_fixo'
             WHEN AVG(valor_transacao) >= MAX(lim_pronto_pgto) * 0.60
                  AND AVG(valor_transacao) < MAX(lim_pronto_pgto) THEN 'abaixo_pronto_pgto'
             WHEN AVG(valor_transacao) >= MAX(lim_dispensa) * 0.60
                  AND AVG(valor_transacao) < MAX(lim_dispensa) THEN 'abaixo_dispensa'
             ELSE 'outra_faixa'
         END AS faixa_suspeita
  FROM limites
  WHERE dt_transacao IS NOT NULL
  GROUP BY cpf_portador, nome_portador, cnpj_cpf_favorecido, nome_favorecido,
           codigo_unidade_gestora, nome_unidade_gestora, to_char(dt_transacao, 'YYYY-MM')
  HAVING COUNT(*) >= 2
    AND (AVG(valor_transacao) BETWEEN 700 AND 999
         OR (AVG(valor_transacao) >= MAX(lim_pronto_pgto) * 0.60 AND AVG(valor_transacao) < MAX(lim_pronto_pgto))
         OR (AVG(valor_transacao) >= MAX(lim_dispensa) * 0.60 AND AVG(valor_transacao) < MAX(lim_dispensa)))
) sub
ORDER BY total DESC;
