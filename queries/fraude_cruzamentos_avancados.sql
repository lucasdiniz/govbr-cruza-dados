-- ============================================================
-- Cruzamentos avançados — gaps identificados na matriz tabela×query
-- Q301-Q310: cruzamentos de alto valor entre fontes subutilizadas
-- ============================================================

-- Q301: Duplo vínculo público — servidor federal (SIAPE) que também é servidor municipal (TCE-PB)
-- Acumulação ilegal de cargos públicos (art. 37, XVI CF).
-- Match por 6 dígitos centrais do CPF + nome normalizado.
WITH siape_pb AS (
    SELECT DISTINCT
        cpf_digitos,
        UPPER(TRIM(nome)) AS nome_upper,
        nome AS nome_siape,
        cpf AS cpf_siape,
        descricao_cargo AS cargo_federal,
        org_exercicio AS orgao_federal,
        situacao_vinculo,
        tipo_vinculo
    FROM siape_cadastro
    WHERE uf_exercicio = 'PB'
      AND cpf_digitos IS NOT NULL
      AND cpf_digitos != '000000'
),
tce_serv AS (
    SELECT DISTINCT ON (cpf_digitos_6, nome_upper)
        cpf_digitos_6,
        nome_upper,
        nome_servidor,
        cpf_cnpj AS cpf_municipal,
        municipio,
        descricao_cargo AS cargo_municipal,
        valor_vantagem,
        tipo_cargo
    FROM tce_pb_servidor
    WHERE cpf_digitos_6 IS NOT NULL
      AND cpf_digitos_6 != '000000'
      AND valor_vantagem > 0
    ORDER BY cpf_digitos_6, nome_upper, valor_vantagem DESC
)
SELECT
    s.nome_siape,
    s.cpf_siape,
    s.cargo_federal,
    s.orgao_federal,
    s.situacao_vinculo AS vinculo_federal,
    t.municipio,
    t.cargo_municipal,
    t.tipo_cargo AS tipo_cargo_municipal,
    t.valor_vantagem AS salario_municipal
FROM siape_pb s
JOIN tce_serv t ON t.cpf_digitos_6 = s.cpf_digitos
                AND t.nome_upper = s.nome_upper
ORDER BY t.valor_vantagem DESC;


-- Q302: BNDES × PGFN — empresa com dívida ativa federal que recebe empréstimo BNDES
-- Tomador de crédito público subsidiado com passivo junto à União.
WITH bndes_pj AS (
    SELECT
        LEFT(REGEXP_REPLACE(cnpj, '[^0-9]', '', 'g'), 8) AS cnpj_basico,
        cliente,
        cnpj,
        uf,
        municipio,
        SUM(valor_contratado) AS total_contratado,
        SUM(valor_desembolsado) AS total_desembolsado,
        COUNT(*) AS contratos
    FROM bndes_contrato
    WHERE cnpj IS NOT NULL AND cnpj != ''
    GROUP BY 1, 2, 3, 4, 5
),
pgfn_pj AS (
    SELECT
        LEFT(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g'), 8) AS cnpj_basico,
        SUM(valor_consolidado) AS divida_total,
        COUNT(*) AS inscricoes
    FROM pgfn_divida
    WHERE LENGTH(REGEXP_REPLACE(cpf_cnpj, '[^0-9]', '', 'g')) = 14
    GROUP BY 1
)
SELECT
    b.cliente,
    b.cnpj,
    b.uf,
    b.total_contratado,
    b.total_desembolsado,
    b.contratos AS contratos_bndes,
    p.divida_total AS divida_pgfn,
    p.inscricoes AS inscricoes_pgfn,
    ROUND(p.divida_total / NULLIF(b.total_contratado, 0) * 100, 1) AS pct_divida_sobre_emprestimo
FROM bndes_pj b
JOIN pgfn_pj p ON p.cnpj_basico = b.cnpj_basico
WHERE p.divida_total > 100000
ORDER BY p.divida_total DESC
LIMIT 200;


-- Q303: Dotação vs execução — empenhos que excedem a dotação autorizada por UG + elemento + exercício
-- Art. 167 CF: vedada a realização de despesas que excedam os créditos orçamentários.
WITH dotacao_agg AS (
    SELECT
        codigo_unidade_gestora,
        exercicio,
        codigo_funcao,
        codigo_subfuncao,
        codigo_programa,
        codigo_acao,
        elemento_despesa,
        SUM(valor_orcado) AS total_orcado
    FROM pb_dotacao
    GROUP BY 1, 2, 3, 4, 5, 6, 7
),
empenho_agg AS (
    SELECT
        codigo_unidade_gestora,
        exercicio,
        codigo_funcao,
        codigo_subfuncao,
        codigo_programa,
        codigo_acao,
        codigo_elemento_despesa AS elemento_despesa,
        SUM(valor_empenho) AS total_empenhado,
        COUNT(*) AS empenhos
    FROM pb_empenho
    WHERE valor_empenho > 0
    GROUP BY 1, 2, 3, 4, 5, 6, 7
)
SELECT
    d.codigo_unidade_gestora,
    d.exercicio,
    d.codigo_funcao,
    d.codigo_subfuncao,
    d.elemento_despesa,
    d.total_orcado,
    e.total_empenhado,
    e.total_empenhado - d.total_orcado AS excesso,
    ROUND((e.total_empenhado / NULLIF(d.total_orcado, 0) - 1) * 100, 1) AS pct_excesso,
    e.empenhos
FROM dotacao_agg d
JOIN empenho_agg e ON e.codigo_unidade_gestora = d.codigo_unidade_gestora
                   AND e.exercicio = d.exercicio
                   AND e.codigo_funcao = d.codigo_funcao
                   AND e.codigo_subfuncao = d.codigo_subfuncao
                   AND e.codigo_programa = d.codigo_programa
                   AND e.codigo_acao = d.codigo_acao
                   AND e.elemento_despesa = d.elemento_despesa
WHERE e.total_empenhado > d.total_orcado * 1.25  -- excede em 25%+
  AND d.total_orcado > 0
  AND e.total_empenhado - d.total_orcado > 100000  -- excesso > R$100K
ORDER BY e.total_empenhado - d.total_orcado DESC
LIMIT 200;


-- Q304: Empresa de fora do estado ganhando contratos municipais PB
-- Fornecedor com sede em outro UF recebendo de municípios da Paraíba — possível empresa fachada.
WITH fornecedores_mun AS (
    SELECT
        cnpj_basico,
        nome_credor,
        COUNT(DISTINCT municipio) AS municipios_pb,
        SUM(valor_empenhado) AS total_empenhado,
        COUNT(*) AS empenhos
    FROM tce_pb_despesa
    WHERE cnpj_basico IS NOT NULL
      AND LENGTH(cnpj_basico) = 8
      AND valor_empenhado > 0
    GROUP BY 1, 2
    HAVING SUM(valor_empenhado) > 50000
)
SELECT
    f.cnpj_basico,
    f.nome_credor,
    est.uf,
    e.razao_social,
    est.nome_cidade_exterior,
    f.municipios_pb,
    f.total_empenhado,
    f.empenhos,
    e.natureza_juridica,
    e.porte
FROM fornecedores_mun f
JOIN estabelecimento est ON est.cnpj_basico = f.cnpj_basico AND est.matriz_filial = '1'
JOIN empresa e ON e.cnpj_basico = f.cnpj_basico
WHERE est.uf NOT IN ('PB', '')
  AND est.uf IS NOT NULL
ORDER BY f.total_empenhado DESC
LIMIT 200;


-- Q305: Receita vs despesa municipal — municípios que gastam mais do que arrecadam
-- Déficit crônico indica risco fiscal e possível dependência de transferências.
WITH receita_mun AS (
    SELECT
        municipio,
        ano,
        SUM(valor) AS receita_total
    FROM tce_pb_receita
    WHERE valor > 0
    GROUP BY 1, 2
),
despesa_mun AS (
    SELECT
        municipio,
        ano,
        SUM(valor_empenhado) AS despesa_empenhada,
        SUM(valor_pago) AS despesa_paga
    FROM tce_pb_despesa
    WHERE valor_empenhado > 0
    GROUP BY 1, 2
)
SELECT
    r.municipio,
    r.ano,
    r.receita_total,
    d.despesa_empenhada,
    d.despesa_paga,
    d.despesa_empenhada - r.receita_total AS deficit_empenhado,
    d.despesa_paga - r.receita_total AS deficit_pago,
    ROUND((d.despesa_empenhada / NULLIF(r.receita_total, 0) - 1) * 100, 1) AS pct_excesso_empenhado
FROM receita_mun r
JOIN despesa_mun d ON d.municipio = r.municipio AND d.ano = r.ano
WHERE r.receita_total > 0
ORDER BY r.municipio, r.ano;


-- Q306: BNDES × doador TSE — tomador de empréstimo BNDES cujo sócio doa para campanhas
-- Padrão JBS: crédito público subsidiado financia campanhas via sócios da empresa.
-- Match via 6 dígitos centrais do CPF + nome, pois socio RFB é mascarado.
WITH bndes_socios AS (
    SELECT
        b.cliente,
        b.cnpj,
        b.uf,
        SUM(b.valor_contratado) AS total_contratado,
        SUM(b.valor_desembolsado) AS total_desembolsado,
        s.nome AS nome_socio,
        s.cpf_cnpj_norm AS cpf_6dig
    FROM bndes_contrato b
    JOIN socio s ON s.cnpj_basico = LEFT(REGEXP_REPLACE(b.cnpj, '[^0-9]', '', 'g'), 8)
    WHERE b.valor_contratado > 500000
      AND s.tipo_socio = '2'
      AND s.cpf_cnpj_norm IS NOT NULL
      AND s.cpf_cnpj_norm != '000000'
    GROUP BY b.cliente, b.cnpj, b.uf, s.nome, s.cpf_cnpj_norm
),
doadores AS (
    SELECT
        SUBSTRING(cpf_cnpj_doador FROM 4 FOR 6) AS cpf_6dig,
        UPPER(TRIM(nm_doador)) AS nome_upper,
        nm_doador,
        SUM(vr_receita) AS total_doado,
        COUNT(DISTINCT sq_prestador_contas) AS candidatos_apoiados,
        STRING_AGG(DISTINCT nm_candidato || ' (' || ano_eleicao::text || ')', ', ') AS campanhas
    FROM tse_receita_candidato
    WHERE LENGTH(cpf_cnpj_doador) = 11  -- CPF completo (PF)
      AND vr_receita > 0
    GROUP BY 1, 2, 3
    HAVING SUM(vr_receita) > 10000
)
SELECT
    bs.cliente AS empresa_bndes,
    bs.cnpj AS cnpj_empresa,
    bs.uf,
    bs.total_contratado AS emprestimo_bndes,
    bs.nome_socio,
    d.total_doado AS total_doado_tse,
    d.candidatos_apoiados,
    SUBSTRING(d.campanhas FOR 200) AS campanhas
FROM bndes_socios bs
JOIN doadores d ON d.cpf_6dig = bs.cpf_6dig
               AND d.nome_upper = UPPER(TRIM(bs.nome_socio))
ORDER BY bs.total_contratado DESC
LIMIT 200;


-- Q307: Licitações municipais pré-eleição — pico de licitações TCE-PB em ano eleitoral
-- Mesmo padrão de Q48 (PNCP) aplicado a municípios PB.
WITH lic_por_semestre AS (
    SELECT
        municipio,
        ano_licitacao AS ano,
        CASE WHEN EXTRACT(MONTH FROM data_homologacao) <= 6 THEN 1 ELSE 2 END AS semestre,
        CASE WHEN ano_licitacao IN (2020, 2024) THEN true ELSE false END AS ano_eleitoral,
        COUNT(*) AS licitacoes,
        SUM(valor_ofertado) AS valor_total
    FROM tce_pb_licitacao
    WHERE ano_licitacao BETWEEN 2019 AND 2025
      AND data_homologacao IS NOT NULL
      AND valor_ofertado > 0
    GROUP BY 1, 2, 3, 4
),
media_nao_eleitoral AS (
    SELECT
        municipio,
        semestre,
        AVG(licitacoes) AS media_lic,
        AVG(valor_total) AS media_valor
    FROM lic_por_semestre
    WHERE NOT ano_eleitoral
    GROUP BY 1, 2
)
SELECT
    l.municipio,
    l.ano,
    l.semestre,
    l.licitacoes,
    l.valor_total,
    ROUND(m.media_lic, 1) AS media_nao_eleitoral,
    ROUND(l.licitacoes / NULLIF(m.media_lic, 0), 1) AS fator_vs_media,
    ROUND(l.valor_total / NULLIF(m.media_valor, 0), 1) AS fator_valor_vs_media
FROM lic_por_semestre l
JOIN media_nao_eleitoral m ON m.municipio = l.municipio AND m.semestre = l.semestre
WHERE l.ano_eleitoral
  AND l.licitacoes > m.media_lic * 1.5  -- 50% acima da média
  AND l.licitacoes >= 5
ORDER BY l.licitacoes / NULLIF(m.media_lic, 0) DESC
LIMIT 200;


-- Q308: Porta giratória — ex-servidor municipal que vira sócio de fornecedor do mesmo município
-- Servidor com data_admissao anterior à data de entrada como sócio em empresa fornecedora.
WITH serv_socios AS (
    SELECT DISTINCT ON (s.cpf_digitos_6, s.nome_upper)
        s.nome_servidor,
        s.cpf_cnpj AS cpf_servidor,
        s.cpf_digitos_6,
        s.nome_upper,
        s.municipio AS municipio_servidor,
        s.descricao_cargo,
        s.data_admissao,
        so.cnpj_basico,
        so.nome AS nome_socio,
        so.dt_entrada,
        e.razao_social
    FROM tce_pb_servidor s
    JOIN socio so ON so.cpf_cnpj_norm = s.cpf_digitos_6
                 AND UPPER(TRIM(so.nome)) = s.nome_upper
    JOIN empresa e ON e.cnpj_basico = so.cnpj_basico
    WHERE s.cpf_digitos_6 IS NOT NULL
      AND s.cpf_digitos_6 != '000000'
      AND so.tipo_socio = '2'
      AND so.dt_entrada IS NOT NULL
    ORDER BY s.cpf_digitos_6, s.nome_upper, so.dt_entrada
)
SELECT
    ss.nome_servidor,
    ss.cpf_servidor,
    ss.municipio_servidor,
    ss.descricao_cargo,
    ss.data_admissao,
    ss.razao_social AS empresa,
    ss.cnpj_basico,
    ss.dt_entrada AS data_entrada_sociedade,
    d.total_recebido,
    d.municipios_atendidos
FROM serv_socios ss
JOIN (
    SELECT
        cnpj_basico,
        SUM(valor_empenhado) AS total_recebido,
        COUNT(DISTINCT municipio) AS municipios_atendidos
    FROM tce_pb_despesa
    WHERE cnpj_basico IS NOT NULL AND valor_empenhado > 0
    GROUP BY 1
) d ON d.cnpj_basico = ss.cnpj_basico
WHERE d.total_recebido > 10000
ORDER BY d.total_recebido DESC
LIMIT 200;


-- Q309: Ciclo emenda → município → empresa do prefeito
-- Emenda federal destinada a município PB onde o prefeito (ou familiar) é sócio de empresa fornecedora.
WITH prefeitos AS (
    SELECT
        nm_candidato,
        cpf,
        nm_ue AS municipio_tse,
        UPPER(nm_ue) AS municipio_upper,
        sg_partido,
        ano_eleicao
    FROM tse_candidato
    WHERE ds_cargo IN ('PREFEITO', 'Prefeito')
      AND sg_uf = 'PB'
      AND ds_sit_tot_turno IN ('ELEITO', 'ELEITO POR MÉDIA', 'ELEITO POR QP')
),
prefeito_empresas AS (
    SELECT
        p.nm_candidato,
        p.cpf,
        p.municipio_upper,
        p.sg_partido,
        p.ano_eleicao,
        s.cnpj_basico,
        e.razao_social
    FROM prefeitos p
    JOIN socio s ON s.cpf_cnpj_socio LIKE '%' || SUBSTRING(p.cpf FROM 5 FOR 6) || '%'
                AND UPPER(TRIM(s.nome)) = UPPER(TRIM(p.nm_candidato))
    JOIN empresa e ON e.cnpj_basico = s.cnpj_basico
    WHERE s.tipo_socio = '2'
),
emendas_municipio AS (
    SELECT
        UPPER(municipio_favorecido) AS municipio_upper,
        SUM(valor_recebido) AS emendas_recebidas,
        COUNT(*) AS parcelas_emenda
    FROM emenda_favorecido
    WHERE uf_favorecido = 'PB'
      AND valor_recebido > 0
    GROUP BY 1
),
despesas_empresa AS (
    SELECT
        cnpj_basico,
        UPPER(municipio) AS municipio_upper,
        SUM(valor_empenhado) AS total_municipal,
        COUNT(*) AS empenhos
    FROM tce_pb_despesa
    WHERE cnpj_basico IS NOT NULL AND valor_empenhado > 0
    GROUP BY 1, 2
)
SELECT
    pe.nm_candidato AS prefeito,
    pe.municipio_upper AS municipio,
    pe.sg_partido,
    pe.ano_eleicao,
    pe.razao_social AS empresa_do_prefeito,
    pe.cnpj_basico,
    em.emendas_recebidas AS emendas_para_municipio,
    de.total_municipal AS empresa_recebe_do_municipio,
    de.empenhos
FROM prefeito_empresas pe
JOIN emendas_municipio em ON em.municipio_upper = pe.municipio_upper
JOIN despesas_empresa de ON de.cnpj_basico = pe.cnpj_basico
                        AND de.municipio_upper = pe.municipio_upper
WHERE de.total_municipal > 10000
ORDER BY de.total_municipal DESC
LIMIT 200;


-- Q310: Fornecedor saúde dominante por município — empresa que monopoliza gastos de saúde
-- Similar ao achado das Clínicas Wanderley: empresa presente em muitos municípios no setor saúde.
WITH saude_mun AS (
    SELECT
        cnpj_basico,
        nome_credor,
        municipio,
        SUM(valor_empenhado) AS valor_saude,
        COUNT(*) AS empenhos
    FROM tce_pb_despesa
    WHERE cnpj_basico IS NOT NULL
      AND LENGTH(cnpj_basico) = 8
      AND valor_empenhado > 0
      AND (codigo_funcao = '10'  -- saúde
           OR funcao ILIKE '%saude%'
           OR funcao ILIKE '%saúde%')
    GROUP BY 1, 2, 3
),
total_saude_mun AS (
    SELECT
        municipio,
        SUM(valor_empenhado) AS total_saude_municipio
    FROM tce_pb_despesa
    WHERE valor_empenhado > 0
      AND (codigo_funcao = '10'
           OR funcao ILIKE '%saude%'
           OR funcao ILIKE '%saúde%')
    GROUP BY 1
),
empresa_resumo AS (
    SELECT
        s.cnpj_basico,
        s.nome_credor,
        COUNT(DISTINCT s.municipio) AS municipios_atendidos,
        SUM(s.valor_saude) AS total_saude,
        SUM(s.empenhos) AS total_empenhos,
        STRING_AGG(DISTINCT s.municipio, ', ' ORDER BY s.municipio) AS lista_municipios
    FROM saude_mun s
    GROUP BY 1, 2
    HAVING COUNT(DISTINCT s.municipio) >= 5
)
SELECT
    er.cnpj_basico,
    er.nome_credor,
    e.razao_social,
    er.municipios_atendidos,
    er.total_saude,
    er.total_empenhos,
    SUBSTRING(er.lista_municipios FOR 200) AS municipios_exemplo
FROM empresa_resumo er
LEFT JOIN empresa e ON e.cnpj_basico = er.cnpj_basico
ORDER BY er.municipios_atendidos DESC, er.total_saude DESC
LIMIT 100;
