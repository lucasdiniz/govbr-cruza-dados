-- =============================================
-- Queries de fraude: TCE-PB (dados municipais consolidados)
-- Fontes: tce_pb_despesa, tce_pb_servidor, tce_pb_licitacao, tce_pb_receita
-- Cruzamentos: empresa, estabelecimento, socio, tse_receita, tse_candidato,
--              bolsa_familia, ceis_sancao, cnep_sancao, pgfn_divida
-- Requer: normalização Fases 5-6 (cnpj_basico, cpf_digitos_6, nome_upper, ano)
-- =============================================

-- Q59: Servidor municipal que é sócio de empresa fornecedora do mesmo município
-- Detecta conflito de interesses direto: servidor público com participação societária
-- em empresa que recebe pagamentos do mesmo município onde trabalha.
-- Match por cpf_digitos_6 + nome (6 dígitos centrais, ambas fontes mascaram CPF)
SELECT DISTINCT
       sv.municipio,
       sv.nome_servidor, sv.cpf_cnpj AS cpf_servidor,
       sv.descricao_cargo, sv.tipo_cargo,
       sv.valor_vantagem,
       e.razao_social, est.cnpj_completo,
       e.capital_social,
       s.qualificacao AS qualificacao_socio,
       SUM(d.valor_pago) AS total_recebido_municipio,
       COUNT(DISTINCT d.numero_empenho) AS qtd_empenhos
FROM tce_pb_servidor sv
JOIN socio s ON sv.cpf_digitos_6 = s.cpf_cnpj_norm
    AND s.tipo_socio = 2
    AND sv.nome_upper = UPPER(TRIM(s.nome))
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN estabelecimento est ON est.cnpj_basico = e.cnpj_basico
    AND est.cnpj_ordem = '0001'
    AND est.situacao_cadastral = '2'
JOIN tce_pb_despesa d ON d.cnpj_basico = e.cnpj_basico
    AND d.municipio = sv.municipio
    AND d.ano >= LEFT(sv.ano_mes, 4)::INT
WHERE sv.cpf_digitos_6 IS NOT NULL AND sv.cpf_digitos_6 != ''
  AND sv.ano_mes >= '2022-01'
GROUP BY sv.municipio, sv.nome_servidor, sv.cpf_cnpj, sv.descricao_cargo,
         sv.tipo_cargo, sv.valor_vantagem,
         e.razao_social, est.cnpj_completo, e.capital_social, s.qualificacao
ORDER BY total_recebido_municipio DESC;

-- Q60: Fornecedor recebendo pagamentos "Sem Licitação" em múltiplos municípios PB
-- Detecta empresas que sistematicamente recebem sem processo licitatório em vários municípios
-- Indicativo de cartel ou influência política regional
SELECT d.cpf_cnpj, d.nome_credor,
       e.razao_social,
       est.uf AS uf_empresa, est.municipio AS municipio_empresa,
       COUNT(DISTINCT d.municipio) AS qtd_municipios,
       ARRAY_AGG(DISTINCT d.municipio ORDER BY d.municipio) AS municipios,
       SUM(d.valor_pago) AS total_pago,
       COUNT(*) AS qtd_empenhos
FROM tce_pb_despesa d
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
LEFT JOIN estabelecimento est ON est.cnpj_basico = d.cnpj_basico
    AND est.cnpj_ordem = '0001'
WHERE d.cnpj_basico IS NOT NULL
  AND d.modalidade_licitacao ILIKE '%sem licit%'
  AND d.valor_pago > 0
GROUP BY d.cpf_cnpj, d.nome_credor, e.razao_social, est.uf, est.municipio
HAVING COUNT(DISTINCT d.municipio) >= 5
ORDER BY qtd_municipios DESC, total_pago DESC;

-- Q61: Divergência empenhado vs pago — empenhos com valor pago muito menor que empenhado
-- Detecta possíveis anulações parciais ou superfaturamento no empenho com execução menor
-- Agrupado por município + credor para mostrar padrão
SELECT d.municipio, d.cpf_cnpj, d.nome_credor,
       COUNT(*) AS qtd_empenhos,
       SUM(d.valor_empenhado) AS total_empenhado,
       SUM(d.valor_pago) AS total_pago,
       SUM(d.valor_empenhado) - SUM(d.valor_pago) AS diferenca,
       ROUND((1 - SUM(d.valor_pago) / NULLIF(SUM(d.valor_empenhado), 0)) * 100, 1) AS pct_nao_pago
FROM tce_pb_despesa d
WHERE d.valor_empenhado > 10000
  AND d.valor_pago > 0
  AND d.valor_pago < d.valor_empenhado * 0.5
  AND d.ano >= 2022
GROUP BY d.municipio, d.cpf_cnpj, d.nome_credor
HAVING SUM(d.valor_empenhado) > 100000
ORDER BY diferenca DESC;

-- Q62: Mesmo fornecedor ganhando licitação em muitos municípios PB (possível cartel estadual)
-- Detecta empresas com presença desproporcional em licitações de múltiplos municípios
SELECT l.cpf_cnpj_proponente, l.nome_proponente,
       e.razao_social,
       est.uf AS uf_empresa, est.municipio AS municipio_empresa,
       COUNT(DISTINCT l.municipio) AS qtd_municipios,
       COUNT(DISTINCT l.numero_licitacao) AS qtd_licitacoes,
       SUM(l.valor_ofertado) AS total_ofertado,
       COUNT(*) FILTER (WHERE l.situacao_proposta ILIKE '%vencedor%'
                           OR l.situacao_proposta ILIKE '%classific%') AS propostas_vencedoras
FROM tce_pb_licitacao l
JOIN empresa e ON e.cnpj_basico = l.cnpj_basico_proponente
LEFT JOIN estabelecimento est ON est.cnpj_basico = l.cnpj_basico_proponente
    AND est.cnpj_ordem = '0001'
WHERE l.cnpj_basico_proponente IS NOT NULL
  AND l.ano_licitacao >= 2022
GROUP BY l.cpf_cnpj_proponente, l.nome_proponente,
         e.razao_social, est.uf, est.municipio
HAVING COUNT(DISTINCT l.municipio) >= 10
ORDER BY qtd_municipios DESC, total_ofertado DESC;

-- Q63: Servidor municipal com salário alto que é sócio de empresa
-- Detecta conflito de interesses: servidor com remuneração significativa tendo
-- participação societária em empresas ativas (independente de ser fornecedor)
SELECT sv.municipio, sv.nome_servidor, sv.cpf_cnpj,
       sv.descricao_cargo, sv.tipo_cargo,
       sv.valor_vantagem,
       e.razao_social, est.cnpj_completo,
       e.capital_social,
       s.qualificacao,
       est.uf AS uf_empresa, est.municipio AS municipio_empresa
FROM tce_pb_servidor sv
JOIN socio s ON sv.cpf_digitos_6 = s.cpf_cnpj_norm
    AND s.tipo_socio = 2
    AND sv.nome_upper = UPPER(TRIM(s.nome))
JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
JOIN estabelecimento est ON est.cnpj_basico = e.cnpj_basico
    AND est.cnpj_ordem = '0001'
    AND est.situacao_cadastral = '2'
WHERE sv.valor_vantagem > 10000
  AND sv.cpf_digitos_6 IS NOT NULL AND sv.cpf_digitos_6 != ''
  AND sv.ano_mes >= '2022-01'
ORDER BY sv.valor_vantagem DESC
LIMIT 500;

-- Q64: Cruzamento despesa TCE-PB × contrato PNCP — verificar valores divergentes
-- Detecta discrepâncias entre o valor contratado (PNCP) e o efetivamente pago (TCE-PB)
-- JOIN via cnpj_basico do fornecedor + cnpj do órgão contratante
SELECT d.municipio,
       pc.orgao_razao_social, pc.cnpj_orgao,
       pc.nome_fornecedor, pc.ni_fornecedor,
       pc.objeto,
       pc.valor_global AS valor_contrato_pncp,
       SUM(d.valor_pago) AS total_pago_tce,
       SUM(d.valor_pago) - pc.valor_global AS diferenca,
       pc.dt_assinatura, pc.dt_vigencia_fim
FROM pncp_contrato pc
JOIN tce_pb_despesa d ON d.cnpj_basico = pc.cnpj_basico_fornecedor
    AND LEFT(pc.cnpj_orgao, 8) = LEFT(d.codigo_ug, 8)
WHERE pc.uf = 'PB'
  AND pc.valor_global > 50000
  AND d.ano >= 2022
GROUP BY d.municipio, pc.orgao_razao_social, pc.cnpj_orgao,
         pc.nome_fornecedor, pc.ni_fornecedor, pc.objeto,
         pc.valor_global, pc.dt_assinatura, pc.dt_vigencia_fim
HAVING ABS(SUM(d.valor_pago) - pc.valor_global) > pc.valor_global * 0.25
ORDER BY ABS(SUM(d.valor_pago) - pc.valor_global) DESC
LIMIT 500;

-- Q65: Fornecedor sancionado (CEIS/CNEP) recebendo pagamento municipal
-- Detecta empresa com sanção ativa no CEIS que continua recebendo de municípios PB
-- Irregularidade objetiva: empresa impedida de contratar com poder público
SELECT cs.nome_sancionado, cs.cpf_cnpj_sancionado,
       cs.categoria_sancao, cs.dt_inicio_sancao, cs.dt_final_sancao,
       cs.orgao_sancionador,
       d.municipio, d.nome_credor,
       SUM(d.valor_pago) AS total_pago,
       COUNT(*) AS qtd_empenhos,
       MIN(d.data_empenho) AS primeiro_empenho,
       MAX(d.data_empenho) AS ultimo_empenho
FROM ceis_sancao cs
JOIN tce_pb_despesa d ON LEFT(cs.cpf_cnpj_sancionado, 8) = d.cnpj_basico
WHERE d.cnpj_basico IS NOT NULL
  AND d.data_empenho >= cs.dt_inicio_sancao
  AND (cs.dt_final_sancao IS NULL OR d.data_empenho <= cs.dt_final_sancao)
  AND d.valor_pago > 0
GROUP BY cs.nome_sancionado, cs.cpf_cnpj_sancionado,
         cs.categoria_sancao, cs.dt_inicio_sancao, cs.dt_final_sancao,
         cs.orgao_sancionador, d.municipio, d.nome_credor
ORDER BY total_pago DESC;

-- Q66: Empenhos concentrados em dezembro (queima de orçamento municipal)
-- Detecta municípios com proporção anormal de despesas no último mês do exercício
-- Indicativo de execução orçamentária de fachada
SELECT d.municipio, d.ano,
       SUM(d.valor_empenhado) AS total_empenhado_ano,
       SUM(d.valor_empenhado) FILTER (WHERE d.mes = '12') AS empenhado_dezembro,
       ROUND(SUM(d.valor_empenhado) FILTER (WHERE d.mes = '12') * 100.0
             / NULLIF(SUM(d.valor_empenhado), 0), 1) AS pct_dezembro,
       COUNT(*) FILTER (WHERE d.mes = '12') AS qtd_empenhos_dez,
       COUNT(*) AS qtd_empenhos_ano
FROM tce_pb_despesa d
WHERE d.ano >= 2022
  AND d.valor_empenhado > 0
GROUP BY d.municipio, d.ano
HAVING SUM(d.valor_empenhado) > 1000000
   AND SUM(d.valor_empenhado) FILTER (WHERE d.mes = '12') * 100.0
       / NULLIF(SUM(d.valor_empenhado), 0) > 30
ORDER BY pct_dezembro DESC;

-- Q67: Fornecedor com dívida ativa PGFN recebendo pagamento municipal
-- Detecta empresas que devem à União mas continuam recebendo de municípios PB
SELECT d.cpf_cnpj, d.nome_credor,
       d.municipio,
       pg.numero_inscricao, pg.tipo_devedor, pg.situacao_inscricao,
       pg.valor_consolidado AS divida_pgfn,
       SUM(d.valor_pago) AS total_pago_municipio,
       COUNT(*) AS qtd_empenhos
FROM tce_pb_despesa d
JOIN pgfn_divida pg ON d.cnpj_basico = LEFT(pg.cpf_cnpj_norm, 8)
WHERE d.cnpj_basico IS NOT NULL
  AND LENGTH(pg.cpf_cnpj_norm) = 14
  AND d.valor_pago > 0
  AND d.ano >= 2022
GROUP BY d.cpf_cnpj, d.nome_credor, d.municipio,
         pg.numero_inscricao, pg.tipo_devedor, pg.situacao_inscricao,
         pg.valor_consolidado
HAVING SUM(d.valor_pago) > 50000
ORDER BY pg.valor_consolidado DESC
LIMIT 500;

-- Q68: Licitação TCE-PB com proponente único (competição fictícia)
-- Detecta licitações onde apenas um proponente participou — pode indicar
-- direcionamento, restrição indevida no edital, ou conluio
SELECT l.municipio, l.numero_licitacao, l.ano_licitacao,
       l.modalidade, l.objeto_licitacao,
       l.nome_proponente, l.cpf_cnpj_proponente,
       l.valor_ofertado, l.situacao_proposta,
       l.data_homologacao
FROM tce_pb_licitacao l
WHERE l.ano_licitacao >= 2022
  AND l.numero_licitacao IN (
      SELECT l2.numero_licitacao
      FROM tce_pb_licitacao l2
      WHERE l2.municipio = l.municipio
        AND l2.ano_licitacao = l.ano_licitacao
      GROUP BY l2.numero_licitacao
      HAVING COUNT(DISTINCT l2.cpf_cnpj_proponente) = 1
  )
  AND l.valor_ofertado > 50000
ORDER BY l.valor_ofertado DESC
LIMIT 500;

-- Q70: Empresa inativa/baixada recebendo pagamento municipal
-- Irregularidade objetiva: empresa com situação cadastral diferente de "ativa" na RFB
-- mas ainda recebendo pagamentos de municípios PB
SELECT d.municipio, d.cpf_cnpj, d.nome_credor,
       est.situacao_cadastral,
       CASE est.situacao_cadastral
           WHEN '1' THEN 'Nula'
           WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta'
           WHEN '8' THEN 'Baixada'
           ELSE 'Situação ' || est.situacao_cadastral
       END AS desc_situacao,
       est.dt_situacao,
       e.razao_social,
       SUM(d.valor_pago) AS total_pago,
       COUNT(*) AS qtd_empenhos,
       MIN(d.data_empenho) AS primeiro_empenho,
       MAX(d.data_empenho) AS ultimo_empenho
FROM tce_pb_despesa d
JOIN estabelecimento est ON est.cnpj_basico = d.cnpj_basico
    AND est.cnpj_ordem = '0001'
    AND est.situacao_cadastral != '2'
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
WHERE d.cnpj_basico IS NOT NULL
  AND d.valor_pago > 0
  AND d.data_empenho > est.dt_situacao
GROUP BY d.municipio, d.cpf_cnpj, d.nome_credor,
         est.situacao_cadastral, est.dt_situacao, e.razao_social
HAVING SUM(d.valor_pago) > 10000
ORDER BY total_pago DESC;

-- Q71: Fornecedores com mesmo endereço comercial recebendo no mesmo município
-- Detecta empresas "fachada" que compartilham endereço — possível laranja/conluio
-- Agrupa por endereço + município para encontrar clusters suspeitos
SELECT d.municipio,
       est.tipo_logradouro || ' ' || est.logradouro || ', ' || est.numero AS endereco,
       est.municipio AS municipio_empresa,
       est.uf AS uf_empresa,
       COUNT(DISTINCT d.cnpj_basico) AS qtd_empresas,
       ARRAY_AGG(DISTINCT e.razao_social ORDER BY e.razao_social) AS empresas,
       SUM(d.valor_pago) AS total_pago_conjunto,
       COUNT(*) AS qtd_empenhos
FROM tce_pb_despesa d
JOIN estabelecimento est ON est.cnpj_basico = d.cnpj_basico
    AND est.cnpj_ordem = '0001'
    AND est.situacao_cadastral = '2'
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
WHERE d.cnpj_basico IS NOT NULL
  AND d.valor_pago > 0
  AND d.ano >= 2022
  AND est.logradouro IS NOT NULL AND est.logradouro != ''
  AND est.numero IS NOT NULL AND est.numero != ''
GROUP BY d.municipio, est.tipo_logradouro, est.logradouro, est.numero,
         est.municipio, est.uf
HAVING COUNT(DISTINCT d.cnpj_basico) >= 3
ORDER BY qtd_empresas DESC, total_pago_conjunto DESC;

-- Q72: Doador de campanha → prefeito eleito → pagamento municipal
-- Detecta quid pro quo: empresa doou para campanha do prefeito e depois recebeu
-- pagamentos do município onde ele foi eleito
-- Match: CNPJ doador = CNPJ credor, município = município do prefeito eleito
SELECT tc.nm_candidato AS prefeito,
       tc.nm_ue AS municipio_tse,
       d.municipio,
       tr.nr_cnpj_prestador AS cnpj_campanha,
       tr.nm_doador, tr.cpf_cnpj_doador AS cnpj_doador,
       tr.vr_receita AS valor_doacao,
       tr.ds_receita AS desc_doacao,
       SUM(d.valor_pago) AS total_recebido_municipio,
       COUNT(*) AS qtd_empenhos
FROM tse_candidato tc
JOIN tse_receita_candidato tr ON tr.sq_candidato = tc.sq_candidato
    AND tr.cpf_cnpj_doador IS NOT NULL
    AND LENGTH(tr.cpf_cnpj_doador) >= 14
JOIN tce_pb_despesa d ON d.cnpj_basico = LEFT(REGEXP_REPLACE(tr.cpf_cnpj_doador, '[^0-9]', '', 'g'), 8)
WHERE tc.ds_cargo = 'PREFEITO'
  AND tc.ds_sit_tot_turno IN ('ELEITO', 'ELEITO POR MÉDIA', 'ELEITO POR QP')
  AND tc.sg_uf = 'PB'
  AND UPPER(TRIM(d.municipio)) = UPPER(TRIM(tc.nm_ue))
  AND d.ano >= CAST(tc.ano_eleicao AS INT)
  AND d.valor_pago > 0
GROUP BY tc.nm_candidato, tc.nm_ue, d.municipio,
         tr.nr_cnpj_prestador, tr.nm_doador, tr.cpf_cnpj_doador,
         tr.vr_receita, tr.ds_receita
ORDER BY total_recebido_municipio DESC
LIMIT 500;

-- Q74: Servidor municipal recebendo Bolsa Família
-- Detecta possível fraude BF: servidor público (com renda) que não deveria receber benefício social
-- Match por cpf_digitos_6 + nome_upper
SELECT DISTINCT
       sv.municipio, sv.nome_servidor, sv.cpf_cnpj,
       sv.descricao_cargo, sv.tipo_cargo, sv.valor_vantagem,
       bf.nm_favorecido, bf.cpf_favorecido, bf.nm_municipio AS municipio_bf,
       bf.valor_parcela
FROM tce_pb_servidor sv
JOIN bolsa_familia bf ON sv.cpf_digitos_6 = bf.cpf_digitos
    AND sv.nome_upper = UPPER(TRIM(bf.nm_favorecido))
WHERE sv.cpf_digitos_6 IS NOT NULL AND sv.cpf_digitos_6 != ''
  AND sv.valor_vantagem > 1500
  AND sv.ano_mes >= '2024-01'
ORDER BY sv.valor_vantagem DESC
LIMIT 500;

-- Q77: Fracionamento de despesa municipal — mesmo credor, mesmo elemento, mesmo mês
-- Detecta possível fracionamento para evitar licitação: múltiplos empenhos pequenos
-- que somados excedem o limite de dispensa (R$50k após Lei 14.133/21)
SELECT d.municipio, d.cpf_cnpj, d.nome_credor,
       d.elemento_despesa,
       d.ano, d.mes,
       COUNT(*) AS qtd_empenhos,
       SUM(d.valor_empenhado) AS total_empenhado,
       MAX(d.valor_empenhado) AS maior_empenho,
       MIN(d.valor_empenhado) AS menor_empenho,
       ROUND(AVG(d.valor_empenhado), 2) AS media_empenho
FROM tce_pb_despesa d
WHERE d.ano >= 2022
  AND d.valor_empenhado > 0
  AND d.valor_empenhado < 50000
  AND d.cnpj_basico IS NOT NULL
GROUP BY d.municipio, d.cpf_cnpj, d.nome_credor, d.elemento_despesa, d.ano, d.mes
HAVING COUNT(*) >= 3
   AND SUM(d.valor_empenhado) > 50000
ORDER BY total_empenhado DESC
LIMIT 500;
