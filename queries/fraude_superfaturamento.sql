-- Q43: Sobrepreço direto — valor homologado muito acima do estimado
-- Detecta contratações onde o valor final excede significativamente a estimativa do órgão
-- Exclui valores estimados muito baixos (< R$1000) que podem ser placeholders
SELECT cc.numero_controle_pncp,
       cc.orgao_razao_social, cc.cnpj_orgao,
       cc.esfera, cc.uf, cc.municipio_nome,
       cc.modalidade_nome,
       cc.objeto,
       cc.valor_estimado,
       cc.valor_homologado,
       ROUND((cc.valor_homologado / cc.valor_estimado - 1) * 100, 1) AS pct_sobrepreco,
       cc.dt_publicacao_pncp
FROM pncp_contratacao cc
WHERE cc.valor_estimado >= 1000
  AND cc.valor_homologado > cc.valor_estimado * 1.25
  AND cc.valor_homologado > 50000
ORDER BY (cc.valor_homologado - cc.valor_estimado) DESC;

-- Q44: Aditivos suspeitos — valor global muito acima do valor inicial do contrato
-- Detecta contratos que foram inflados após assinatura via termos aditivos
-- Exclui contratos de concessionárias (energia/água) que têm valor_inicial simbólico
SELECT pc.numero_controle_pncp,
       pc.orgao_razao_social, pc.cnpj_orgao,
       pc.esfera, pc.uf, pc.municipio_nome,
       pc.tipo_contrato, pc.nome_fornecedor, pc.ni_fornecedor,
       pc.objeto,
       pc.valor_inicial,
       pc.valor_global,
       ROUND((pc.valor_global / pc.valor_inicial - 1) * 100, 1) AS pct_aditivo,
       pc.dt_assinatura, pc.dt_vigencia_fim
FROM pncp_contrato pc
WHERE pc.valor_inicial >= 10000
  AND pc.valor_global > pc.valor_inicial * 1.25
  AND pc.valor_global > 100000
ORDER BY (pc.valor_global - pc.valor_inicial) DESC;

-- Q53: Capital social mínimo ganhando contratos de alto valor
-- Detecta empresas com capital social desproporcional ao valor contratado (possíveis laranjas)
SELECT e.razao_social, e.cnpj_basico, e.capital_social,
       e.natureza_juridica,
       est.uf AS uf_empresa, est.municipio AS municipio_empresa,
       est.dt_inicio_atividade,
       pc.uf AS uf_orgao, pc.municipio_nome AS municipio_orgao,
       pc.objeto, pc.valor_global, pc.dt_assinatura,
       ROUND(pc.valor_global / NULLIF(e.capital_social, 0), 0) AS ratio_contrato_capital
FROM pncp_contrato pc
JOIN empresa e ON e.cnpj_basico = pc.cnpj_basico_fornecedor
JOIN estabelecimento est ON est.cnpj_basico = e.cnpj_basico
  AND est.matriz_filial = 1
WHERE e.capital_social > 0 AND e.capital_social < 50000
  AND pc.valor_global > 500000
ORDER BY ratio_contrato_capital DESC;

-- Q51: Proporção anormal de dispensas por órgão
-- Detecta órgãos que usam dispensa excessivamente em vez de licitação competitiva
-- Foco em municípios (esfera M) e estados (esfera E) com volume significativo
SELECT cc.cnpj_orgao, cc.orgao_razao_social,
       cc.esfera, cc.uf, cc.municipio_nome,
       COUNT(*) AS total_contratacoes,
       SUM(CASE WHEN cc.modalidade_nome = 'Dispensa' THEN 1 ELSE 0 END) AS qtd_dispensas,
       SUM(CASE WHEN cc.modalidade_nome = 'Inexigibilidade' THEN 1 ELSE 0 END) AS qtd_inexigibilidade,
       SUM(CASE WHEN cc.modalidade_nome IN ('Pregão - Eletrônico', 'Pregão - Presencial',
           'Concorrência - Eletrônica', 'Concorrência - Presencial') THEN 1 ELSE 0 END) AS qtd_competitivas,
       ROUND(SUM(CASE WHEN cc.modalidade_nome = 'Dispensa' THEN 1 ELSE 0 END) * 100.0
             / COUNT(*), 1) AS pct_dispensas,
       SUM(cc.valor_estimado) FILTER (WHERE cc.modalidade_nome = 'Dispensa') AS valor_dispensas,
       SUM(cc.valor_estimado) AS valor_total
FROM pncp_contratacao cc
WHERE cc.esfera IN ('E', 'M')
GROUP BY cc.cnpj_orgao, cc.orgao_razao_social, cc.esfera, cc.uf, cc.municipio_nome
HAVING COUNT(*) >= 20
   AND SUM(CASE WHEN cc.modalidade_nome = 'Dispensa' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) > 80
ORDER BY pct_dispensas DESC, valor_total DESC;

-- Q45: Fracionamento de contratação — mesmo órgão + mesmo fornecedor + múltiplas dispensas
-- Detecta possível fracionamento para ficar abaixo do limite de dispensa (Lei 14.133/21)
-- Agrega dispensas do mesmo órgão para o mesmo fornecedor no mesmo ano
SELECT pc.cnpj_orgao, pc.orgao_razao_social,
       pc.esfera, pc.uf, pc.municipio_nome,
       pc.ni_fornecedor, pc.nome_fornecedor,
       pc.ano_contrato,
       COUNT(*) AS qtd_contratos,
       SUM(pc.valor_global) AS total_contratado,
       MAX(pc.valor_global) AS maior_contrato,
       ARRAY_AGG(DISTINCT pc.objeto ORDER BY pc.objeto) AS objetos
FROM pncp_contrato pc
JOIN pncp_contratacao cc ON cc.numero_controle_pncp = pc.numero_controle_contratacao
WHERE cc.modalidade_nome = 'Dispensa'
  AND pc.valor_global > 0
  AND pc.ano_contrato >= 2022
GROUP BY pc.cnpj_orgao, pc.orgao_razao_social, pc.esfera, pc.uf, pc.municipio_nome,
         pc.ni_fornecedor, pc.nome_fornecedor, pc.ano_contrato
HAVING COUNT(*) >= 3 AND SUM(pc.valor_global) > 100000
ORDER BY total_contratado DESC;

-- Q46: Queima de orçamento — pico de contratações em novembro-dezembro
-- Detecta órgãos que concentram contratos nos dois últimos meses do ano
-- Indicativo de execução orçamentária de fachada para não devolver verba
SELECT pc.cnpj_orgao, pc.orgao_razao_social,
       pc.esfera, pc.uf, pc.municipio_nome,
       pc.ano_contrato,
       COUNT(*) AS total_contratos_ano,
       SUM(pc.valor_global) AS total_valor_ano,
       COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM pc.dt_assinatura) IN (11, 12)) AS contratos_nov_dez,
       SUM(pc.valor_global) FILTER (WHERE EXTRACT(MONTH FROM pc.dt_assinatura) IN (11, 12)) AS valor_nov_dez,
       ROUND(SUM(pc.valor_global) FILTER (WHERE EXTRACT(MONTH FROM pc.dt_assinatura) IN (11, 12)) * 100.0
             / NULLIF(SUM(pc.valor_global), 0), 1) AS pct_nov_dez
FROM pncp_contrato pc
WHERE pc.ano_contrato >= 2022
  AND pc.valor_global > 0
  AND pc.dt_assinatura IS NOT NULL
GROUP BY pc.cnpj_orgao, pc.orgao_razao_social, pc.esfera, pc.uf, pc.municipio_nome, pc.ano_contrato
HAVING COUNT(*) >= 10
   AND SUM(pc.valor_global) FILTER (WHERE EXTRACT(MONTH FROM pc.dt_assinatura) IN (11, 12)) * 100.0
       / NULLIF(SUM(pc.valor_global), 0) > 50
ORDER BY pct_nov_dez DESC, valor_nov_dez DESC;

-- Q47: Contratos assinados em fim de semana ou feriado
-- Contratos assinados em sábado/domingo levantam suspeita de irregularidade processual
-- DOW: 0=domingo, 6=sábado
SELECT pc.numero_controle_pncp,
       pc.orgao_razao_social, pc.cnpj_orgao,
       pc.esfera, pc.uf, pc.municipio_nome,
       pc.nome_fornecedor, pc.ni_fornecedor,
       pc.objeto, pc.valor_global,
       pc.dt_assinatura,
       CASE EXTRACT(DOW FROM pc.dt_assinatura)
           WHEN 0 THEN 'Domingo'
           WHEN 6 THEN 'Sabado'
       END AS dia_semana
FROM pncp_contrato pc
WHERE EXTRACT(DOW FROM pc.dt_assinatura) IN (0, 6)
  AND pc.valor_global > 50000
  AND pc.dt_assinatura >= '2022-01-01'
ORDER BY pc.valor_global DESC;

-- Q48: Pico de contratações pré-eleição (ano eleitoral, 1º semestre)
-- Lei Eleitoral (Lei 9.504/97, art. 73) restringe gastos em ano eleitoral
-- Eleições municipais: 2024; estaduais/federais: 2022, 2026
-- Foco: contratos assinados nos 6 meses antes da eleição
SELECT pc.cnpj_orgao, pc.orgao_razao_social,
       pc.esfera, pc.uf, pc.municipio_nome,
       pc.ano_contrato,
       COUNT(*) AS qtd_contratos,
       SUM(pc.valor_global) AS total_contratado,
       COUNT(*) FILTER (WHERE EXTRACT(MONTH FROM pc.dt_assinatura) BETWEEN 4 AND 9) AS contratos_pre_eleicao,
       SUM(pc.valor_global) FILTER (WHERE EXTRACT(MONTH FROM pc.dt_assinatura) BETWEEN 4 AND 9) AS valor_pre_eleicao,
       ROUND(SUM(pc.valor_global) FILTER (WHERE EXTRACT(MONTH FROM pc.dt_assinatura) BETWEEN 4 AND 9) * 100.0
             / NULLIF(SUM(pc.valor_global), 0), 1) AS pct_pre_eleicao
FROM pncp_contrato pc
WHERE pc.ano_contrato IN (2022, 2024, 2026)
  AND pc.valor_global > 0
  AND pc.dt_assinatura IS NOT NULL
  AND pc.esfera IN ('E', 'M')
GROUP BY pc.cnpj_orgao, pc.orgao_razao_social, pc.esfera, pc.uf, pc.municipio_nome, pc.ano_contrato
HAVING COUNT(*) >= 10
   AND SUM(pc.valor_global) FILTER (WHERE EXTRACT(MONTH FROM pc.dt_assinatura) BETWEEN 4 AND 9) * 100.0
       / NULLIF(SUM(pc.valor_global), 0) > 70
ORDER BY valor_pre_eleicao DESC;

-- Q49: Fornecedor de outro estado ganhando contratos (possível empresa fachada)
-- Detecta fornecedores sediados em UF diferente do órgão contratante
-- Foco em dispensas/inexigibilidades de alto valor (não faz sentido em pregão eletrônico)
SELECT pc.cnpj_orgao, pc.orgao_razao_social,
       pc.uf AS uf_orgao, pc.municipio_nome,
       pc.nome_fornecedor, pc.ni_fornecedor,
       est.uf AS uf_fornecedor, est.municipio AS municipio_fornecedor,
       pc.objeto, pc.valor_global,
       pc.dt_assinatura, pc.tipo_contrato,
       cc.modalidade_nome
FROM pncp_contrato pc
JOIN estabelecimento est ON est.cnpj_basico = pc.cnpj_basico_fornecedor
    AND est.cnpj_ordem = '0001'
JOIN pncp_contratacao cc ON cc.numero_controle_pncp = pc.numero_controle_contratacao
WHERE pc.uf != est.uf
  AND cc.modalidade_nome IN ('Dispensa', 'Inexigibilidade')
  AND pc.valor_global > 100000
  AND pc.dt_assinatura >= '2022-01-01'
ORDER BY pc.valor_global DESC;

-- Q50: Fornecedor com mesmo endereço do órgão contratante
-- Detecta empresa operando no mesmo endereço do órgão — possível empresa de fachada
-- controlada por servidor do próprio órgão
SELECT pc.cnpj_orgao, pc.orgao_razao_social,
       pc.uf AS uf_orgao, pc.municipio_nome,
       pc.nome_fornecedor, pc.ni_fornecedor,
       est_forn.logradouro AS logradouro_forn, est_forn.numero AS numero_forn,
       est_forn.municipio AS municipio_forn, est_forn.uf AS uf_forn,
       est_org.logradouro AS logradouro_orgao, est_org.numero AS numero_orgao,
       pc.objeto, pc.valor_global, pc.dt_assinatura
FROM pncp_contrato pc
JOIN estabelecimento est_forn ON est_forn.cnpj_basico = pc.cnpj_basico_fornecedor
    AND est_forn.cnpj_ordem = '0001'
JOIN estabelecimento est_org ON est_org.cnpj_basico = LEFT(pc.cnpj_orgao, 8)
    AND est_org.cnpj_ordem = '0001'
WHERE UPPER(TRIM(est_forn.logradouro)) = UPPER(TRIM(est_org.logradouro))
  AND TRIM(est_forn.numero) = TRIM(est_org.numero)
  AND est_forn.logradouro IS NOT NULL AND est_forn.logradouro != ''
  AND est_forn.numero IS NOT NULL AND est_forn.numero != ''
  AND pc.valor_global > 10000
  AND pc.cnpj_basico_fornecedor != LEFT(pc.cnpj_orgao, 8)
ORDER BY pc.valor_global DESC;

-- Q54: CNAE incompatível com objeto contratado
-- Detecta empresas cujo CNAE principal não é compatível com o que fornecem
-- Exemplo: padaria ganhando contrato de TI, empresa de limpeza fornecendo equipamento médico
-- Foco nos maiores contratos onde CNAE sugere atividade muito diferente do objeto
SELECT pc.nome_fornecedor, pc.ni_fornecedor,
       est.cnae_principal,
       e.razao_social,
       pc.orgao_razao_social, pc.uf, pc.municipio_nome,
       pc.objeto, pc.valor_global, pc.dt_assinatura,
       est.dt_inicio_atividade,
       e.capital_social
FROM pncp_contrato pc
JOIN empresa e ON e.cnpj_basico = pc.cnpj_basico_fornecedor
JOIN estabelecimento est ON est.cnpj_basico = pc.cnpj_basico_fornecedor
    AND est.cnpj_ordem = '0001'
WHERE pc.valor_global > 500000
  AND pc.dt_assinatura >= '2022-01-01'
  AND est.cnae_principal IS NOT NULL
  -- CNAE grupo 47 (comércio varejista) ou 56 (alimentação) ganhando contratos de obra/TI
  AND (
      (est.cnae_principal LIKE '56%' AND pc.objeto ILIKE '%constru%')
   OR (est.cnae_principal LIKE '56%' AND pc.objeto ILIKE '%tecnologia%')
   OR (est.cnae_principal LIKE '47%' AND pc.objeto ILIKE '%obra%')
   OR (est.cnae_principal LIKE '47%' AND pc.objeto ILIKE '%engenharia%')
   OR (est.cnae_principal LIKE '81%' AND pc.objeto ILIKE '%medic%')
   OR (est.cnae_principal LIKE '81%' AND pc.objeto ILIKE '%hospitalar%')
   OR (est.cnae_principal LIKE '96%' AND pc.objeto ILIKE '%constru%')
   OR (est.cnae_principal LIKE '01%' AND pc.objeto ILIKE '%tecnologia%')
  )
ORDER BY pc.valor_global DESC;

-- Q55: Empresa fênix PB — empresa baixada com nova empresa no mesmo endereço
-- Detecta possível uso de empresa fênix para escapar de sanções/dívidas:
-- empresa fechada + nova empresa no mesmo endereço com mesmos sócios.
-- NOTA: self-join em estabelecimento (70M rows) exige filtro por UF.
-- Sem filtro UF o custo é ~21M (inviável). Com UF='PB' roda em ~30s.
-- Para rodar em outro estado, troque 'PB' nas duas cláusulas WHERE.
-- Ver Q99 para versão nacional (temp tables com hash).
SELECT e_old.razao_social AS empresa_baixada,
       est_old.cnpj_completo AS cnpj_baixado,
       est_old.dt_situacao AS data_baixa,
       e_new.razao_social AS empresa_nova,
       est_new.cnpj_completo AS cnpj_novo,
       est_new.dt_inicio_atividade AS data_abertura_nova,
       est_new.dt_inicio_atividade - est_old.dt_situacao AS dias_entre,
       s_old.nome AS socio_comum,
       s_old.cpf_cnpj_norm AS cpf_socio,
       UPPER(TRIM(est_old.logradouro)) || ', ' || est_old.numero AS endereco,
       est_old.municipio, est_old.uf,
       e_new.capital_social AS capital_nova
FROM estabelecimento est_old
JOIN estabelecimento est_new ON UPPER(TRIM(est_old.logradouro)) = UPPER(TRIM(est_new.logradouro))
    AND TRIM(est_old.numero) = TRIM(est_new.numero)
    AND est_old.uf = est_new.uf
    AND est_old.cnpj_basico <> est_new.cnpj_basico
JOIN empresa e_old ON e_old.cnpj_basico = est_old.cnpj_basico
JOIN empresa e_new ON e_new.cnpj_basico = est_new.cnpj_basico
JOIN socio s_old ON s_old.cnpj_basico = est_old.cnpj_basico AND s_old.tipo_socio = 2
JOIN socio s_new ON s_new.cnpj_basico = est_new.cnpj_basico AND s_new.tipo_socio = 2
    AND s_old.cpf_cnpj_norm = s_new.cpf_cnpj_norm
WHERE est_old.cnpj_ordem = '0001' AND est_new.cnpj_ordem = '0001'
  AND est_old.uf = 'PB' AND est_new.uf = 'PB'  -- OBRIGATÓRIO: filtro por UF
  AND est_old.situacao_cadastral IN (8, 4)  -- baixada ou inapta
  AND est_new.situacao_cadastral = 2  -- ativa
  AND est_new.dt_inicio_atividade > est_old.dt_situacao
  AND est_new.dt_inicio_atividade - est_old.dt_situacao < 365
  AND est_old.logradouro IS NOT NULL AND est_old.logradouro <> ''
  AND est_old.numero IS NOT NULL AND est_old.numero <> ''
ORDER BY est_new.dt_inicio_atividade DESC;

-- Q56: Doador de campanha → contrato PNCP
-- Detecta quid pro quo: empresa doou para candidato e depois recebeu contrato público
-- Match por CNPJ do doador = CNPJ do fornecedor no PNCP
SELECT tr.nm_candidato, tr.sg_partido, tr.ds_cargo,
       tr.ano_eleicao, tr.sg_uf,
       tr.nm_doador, tr.cpf_cnpj_doador,
       tr.vr_receita AS valor_doacao,
       pc.orgao_razao_social, pc.uf AS uf_contrato, pc.municipio_nome,
       pc.objeto, pc.valor_global, pc.dt_assinatura,
       pc.nome_fornecedor
FROM tse_receita_candidato tr
JOIN pncp_contrato pc ON pc.cnpj_basico_fornecedor = LEFT(REGEXP_REPLACE(tr.cpf_cnpj_doador, '[^0-9]', '', 'g'), 8)
WHERE LENGTH(REGEXP_REPLACE(tr.cpf_cnpj_doador, '[^0-9]', '', 'g')) >= 14
  AND tr.vr_receita > 10000
  AND pc.valor_global > 100000
  AND pc.dt_assinatura > MAKE_DATE(tr.ano_eleicao, 1, 1)
ORDER BY pc.valor_global DESC;

-- Q57: Ciclo emenda parlamentar → doação TSE
-- Detecta possível ciclo: empresa recebe emenda parlamentar e depois doa para campanha
-- do mesmo autor ou partido — possível devolução de dinheiro público via caixa dois
SELECT ef.nome_autor AS autor_emenda,
       ef.tipo_emenda,
       ef.nome_favorecido AS empresa_favorecida,
       ef.codigo_favorecido AS cnpj_favorecido,
       SUM(ef.valor_recebido) AS total_emenda,
       tr.nm_candidato, tr.sg_partido, tr.ds_cargo,
       tr.ano_eleicao,
       tr.cpf_cnpj_doador, tr.nm_doador,
       SUM(tr.vr_receita) AS total_doacao
FROM emenda_favorecido ef
JOIN tse_receita_candidato tr ON LEFT(REGEXP_REPLACE(tr.cpf_cnpj_doador, '[^0-9]', '', 'g'), 8) = ef.cnpj_basico_favorecido
WHERE ef.cnpj_basico_favorecido IS NOT NULL
  AND LENGTH(REGEXP_REPLACE(tr.cpf_cnpj_doador, '[^0-9]', '', 'g')) >= 14
  AND tr.vr_receita > 5000
  AND ef.valor_recebido > 50000
GROUP BY ef.nome_autor, ef.tipo_emenda, ef.nome_favorecido, ef.codigo_favorecido,
         tr.nm_candidato, tr.sg_partido, tr.ds_cargo, tr.ano_eleicao,
         tr.cpf_cnpj_doador, tr.nm_doador
ORDER BY total_emenda DESC;

-- Q58: Fornecedores com mesmo endereço participando da mesma contratação PNCP
-- Detecta possível simulação de concorrência (bid rigging): empresas no mesmo endereço
-- competindo na mesma licitação — indica propriedade comum ou conluio
SELECT cc.numero_controle_pncp,
       cc.orgao_razao_social, cc.uf, cc.municipio_nome,
       cc.objeto, cc.modalidade_nome,
       cc.valor_estimado,
       e1.razao_social AS empresa_1, est1.cnpj_completo AS cnpj_1,
       e2.razao_social AS empresa_2, est2.cnpj_completo AS cnpj_2,
       UPPER(TRIM(est1.logradouro)) || ', ' || est1.numero AS endereco_comum,
       est1.municipio AS municipio_empresa, est1.uf AS uf_empresa
FROM pncp_contrato pc1
JOIN pncp_contrato pc2 ON pc1.numero_controle_contratacao = pc2.numero_controle_contratacao
    AND pc1.cnpj_basico_fornecedor < pc2.cnpj_basico_fornecedor
JOIN estabelecimento est1 ON est1.cnpj_basico = pc1.cnpj_basico_fornecedor AND est1.cnpj_ordem = '0001'
JOIN estabelecimento est2 ON est2.cnpj_basico = pc2.cnpj_basico_fornecedor AND est2.cnpj_ordem = '0001'
JOIN empresa e1 ON e1.cnpj_basico = pc1.cnpj_basico_fornecedor
JOIN empresa e2 ON e2.cnpj_basico = pc2.cnpj_basico_fornecedor
JOIN pncp_contratacao cc ON cc.numero_controle_pncp = pc1.numero_controle_contratacao
  WHERE UPPER(TRIM(est1.logradouro)) = UPPER(TRIM(est2.logradouro))
    AND TRIM(est1.numero) = TRIM(est2.numero)
    AND est1.uf = est2.uf
    AND est1.logradouro IS NOT NULL AND est1.logradouro != ''
    AND est1.numero IS NOT NULL AND est1.numero != ''
    AND est2.logradouro IS NOT NULL AND est2.logradouro != ''
    AND est2.numero IS NOT NULL AND est2.numero != ''
    AND cc.valor_estimado > 50000
  ORDER BY cc.valor_estimado DESC
  LIMIT 500;


-- Q99: Empresa fênix — versão NACIONAL com temp tables
-- Mesma lógica da Q55 (mesmo endereço + mesmo sócio + <365 dias), mas viabilizada
-- para escala nacional via temp tables pré-filtradas + hash indexes.
-- Filtro temporal: baixas a partir de 2020 (15.7M fechadas nesse período).
-- Sem esse filtro seriam 39M baixadas — excessivo para temp table.
-- Estimativa: ~5-10 min dependendo de I/O.

-- Fase 1: matrizes baixadas/inaptas (2020+) com endereço válido
DROP TABLE IF EXISTS tmp_fenix_closed;
CREATE TEMP TABLE tmp_fenix_closed AS
SELECT est.cnpj_basico, est.cnpj_completo, est.uf, est.municipio,
       est.dt_situacao,
       UPPER(TRIM(est.logradouro)) AS logradouro_norm,
       TRIM(est.numero) AS numero_norm,
       MD5(UPPER(TRIM(est.logradouro)) || '|' || TRIM(est.numero) || '|' || est.uf) AS addr_hash
FROM estabelecimento est
WHERE est.cnpj_ordem = '0001'
  AND est.situacao_cadastral IN (4, 8)  -- baixada ou inapta
  AND est.dt_situacao >= '2020-01-01'   -- últimos ~6 anos
  AND est.logradouro IS NOT NULL AND est.logradouro <> ''
  AND est.numero IS NOT NULL AND est.numero <> ''
  AND est.dt_situacao IS NOT NULL;

CREATE INDEX ON tmp_fenix_closed(addr_hash);
CREATE INDEX ON tmp_fenix_closed(cnpj_basico);

-- Fase 2: matrizes ativas abertas a partir de 2020 com endereço válido
DROP TABLE IF EXISTS tmp_fenix_active;
CREATE TEMP TABLE tmp_fenix_active AS
SELECT est.cnpj_basico, est.cnpj_completo, est.uf, est.municipio,
       est.dt_inicio_atividade,
       UPPER(TRIM(est.logradouro)) AS logradouro_norm,
       TRIM(est.numero) AS numero_norm,
       MD5(UPPER(TRIM(est.logradouro)) || '|' || TRIM(est.numero) || '|' || est.uf) AS addr_hash
FROM estabelecimento est
WHERE est.cnpj_ordem = '0001'
  AND est.situacao_cadastral = 2  -- ativa
  AND est.dt_inicio_atividade >= '2020-01-01'
  AND est.logradouro IS NOT NULL AND est.logradouro <> ''
  AND est.numero IS NOT NULL AND est.numero <> ''
  AND est.dt_inicio_atividade IS NOT NULL;

CREATE INDEX ON tmp_fenix_active(addr_hash);
CREATE INDEX ON tmp_fenix_active(cnpj_basico);

-- Fase 3: join via hash de endereço + sócio em comum + janela de 365 dias
SELECT
    e_old.razao_social        AS empresa_baixada,
    c.cnpj_completo           AS cnpj_baixado,
    c.dt_situacao              AS data_baixa,
    e_new.razao_social        AS empresa_nova,
    a.cnpj_completo           AS cnpj_novo,
    a.dt_inicio_atividade      AS data_abertura_nova,
    a.dt_inicio_atividade - c.dt_situacao AS dias_entre,
    s_old.nome                 AS socio_comum,
    s_old.cpf_cnpj_norm        AS cpf_socio,
    c.logradouro_norm || ', ' || c.numero_norm AS endereco,
    c.municipio, c.uf,
    e_new.capital_social       AS capital_nova
FROM tmp_fenix_closed c
JOIN tmp_fenix_active a
    ON c.addr_hash = a.addr_hash
   AND c.cnpj_basico <> a.cnpj_basico
JOIN empresa e_old ON e_old.cnpj_basico = c.cnpj_basico
JOIN empresa e_new ON e_new.cnpj_basico = a.cnpj_basico
JOIN socio s_old ON s_old.cnpj_basico = c.cnpj_basico AND s_old.tipo_socio = 2
JOIN socio s_new ON s_new.cnpj_basico = a.cnpj_basico AND s_new.tipo_socio = 2
    AND s_old.cpf_cnpj_norm = s_new.cpf_cnpj_norm
WHERE a.dt_inicio_atividade > c.dt_situacao
  AND a.dt_inicio_atividade - c.dt_situacao < 365
ORDER BY a.dt_inicio_atividade DESC;

DROP TABLE tmp_fenix_closed;
DROP TABLE tmp_fenix_active;
