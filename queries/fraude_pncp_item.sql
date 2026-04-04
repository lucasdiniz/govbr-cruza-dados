-- =============================================
-- Queries de fraude usando pncp_item (4.71M itens)
-- Join path: pncp_item → pncp_contratacao (numero_controle_pncp)
--            pncp_contratacao → pncp_contrato (numero_controle_pncp = numero_controle_contratacao)
-- =============================================

-- Q92: Sobrepreço por item — preço unitário muito acima da média nacional
-- Duas fases: (1) calcula estatísticas por grupo de descrição (temp table),
-- (2) join com itens individuais via hash MD5 da descrição.
-- NOTA: versão com window functions estoura memória/tempo em 2.7M itens.
-- Filtro de sanidade: valor_total <= R$1B (exclui erros de digitação óbvios).

-- Fase 1: estatísticas por grupo de descrição
CREATE TEMP TABLE tmp_item_stats AS
SELECT
    MD5(UPPER(TRIM(descricao)) || material_ou_servico) AS desc_hash,
    UPPER(TRIM(descricao)) AS desc_norm,
    material_ou_servico,
    AVG(valor_unitario_estimado) AS media,
    STDDEV(valor_unitario_estimado) AS desvio,
    COUNT(*) AS n_grupo
FROM pncp_item
WHERE situacao_item_nome = 'Homologado' AND valor_unitario_estimado > 0
GROUP BY UPPER(TRIM(descricao)), material_ou_servico
HAVING COUNT(*) >= 10;

CREATE INDEX ON tmp_item_stats(desc_hash);

-- Fase 2: itens outlier vs grupo
SELECT
    i.numero_controle_pncp,
    i.descricao,
    i.valor_unitario_estimado,
    i.quantidade,
    i.valor_total,
    ca.cnpj_orgao,
    ca.orgao_razao_social,
    ca.uf,
    ca.municipio_nome,
    ROUND(s.media::numeric, 2)    AS media_nacional,
    ROUND((i.valor_unitario_estimado / NULLIF(s.media, 0))::numeric, 1) AS vezes_media,
    s.n_grupo
FROM pncp_item i
JOIN tmp_item_stats s ON MD5(UPPER(TRIM(i.descricao)) || i.material_ou_servico) = s.desc_hash
JOIN pncp_contratacao ca ON ca.numero_controle_pncp = i.numero_controle_pncp
WHERE i.situacao_item_nome = 'Homologado'
  AND s.media >= 1
  AND i.valor_total >= 10000
  AND i.valor_total <= 1000000000      -- sanidade: exclui erros de digitação > R$1B
  AND i.valor_unitario_estimado > s.media + 3 * COALESCE(NULLIF(s.desvio, 0), s.media)
ORDER BY i.valor_total DESC
LIMIT 200;

DROP TABLE tmp_item_stats;


-- Q93: Itens desertos ou fracassados repetidos no mesmo órgão
-- Quando o mesmo órgão publica item idêntico que fracassa/deserta 3+ vezes,
-- pode indicar especificação direcionada (sob medida para fornecedor específico)
-- ou mercado sem competição para aquele item.
SELECT
    i.cnpj_orgao,
    ca.orgao_razao_social,
    ca.uf,
    UPPER(TRIM(i.descricao)) AS desc_norm,
    COUNT(*)                 AS vezes_fracassou,
    COUNT(DISTINCT i.numero_controle_pncp) AS contratacoes_distintas,
    ROUND(AVG(i.valor_unitario_estimado)::numeric, 2) AS preco_medio_estimado,
    MIN(i.dt_inclusao::date) AS primeira_tentativa,
    MAX(i.dt_inclusao::date) AS ultima_tentativa
FROM pncp_item i
JOIN pncp_contratacao ca ON ca.numero_controle_pncp = i.numero_controle_pncp
WHERE i.situacao_item_nome IN ('Fracassado', 'Deserto')
GROUP BY i.cnpj_orgao, ca.orgao_razao_social, ca.uf, UPPER(TRIM(i.descricao))
HAVING COUNT(DISTINCT i.numero_controle_pncp) >= 3
ORDER BY vezes_fracassou DESC
LIMIT 200;


-- Q94: Variação de preço entre UFs para mesmo item
-- Compara mediana de preço de itens idênticos (descrição exata) entre estados.
-- Razão > 5× entre UFs pode indicar sobrepreço regional.
-- Usa PERCENTILE_CONT(0.5) (mediana) — mais robusta que AVG contra outliers.
-- Duas fases com temp table para viabilizar PERCENTILE_CONT em escala.

-- Fase 1: mediana por (descrição, material_ou_servico, UF)
DROP TABLE IF EXISTS tmp_uf_prices;
CREATE TEMP TABLE tmp_uf_prices AS
SELECT
    MD5(UPPER(TRIM(i.descricao)) || i.material_ou_servico) AS desc_hash,
    UPPER(TRIM(i.descricao))    AS desc_norm,
    i.material_ou_servico,
    ca.uf,
    COUNT(*)                     AS n_itens,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY i.valor_unitario_estimado) AS mediana_uf,
    AVG(i.valor_unitario_estimado) AS media_uf
FROM pncp_item i
JOIN pncp_contratacao ca ON ca.numero_controle_pncp = i.numero_controle_pncp
WHERE i.situacao_item_nome = 'Homologado'
  AND i.valor_unitario_estimado > 0
  AND i.valor_unitario_estimado <= 10000000   -- sanidade
GROUP BY UPPER(TRIM(i.descricao)), i.material_ou_servico, ca.uf,
         MD5(UPPER(TRIM(i.descricao)) || i.material_ou_servico)
HAVING COUNT(*) >= 5;

CREATE INDEX ON tmp_uf_prices(desc_hash, material_ou_servico);

-- Fase 2: pares de UFs com razão de mediana > 5×
SELECT
    a.desc_norm,
    a.uf            AS uf_cara,
    ROUND(a.mediana_uf::numeric, 2)  AS mediana_cara,
    ROUND(a.media_uf::numeric, 2)    AS media_cara,
    a.n_itens       AS n_caro,
    b.uf            AS uf_barata,
    ROUND(b.mediana_uf::numeric, 2)  AS mediana_barata,
    ROUND(b.media_uf::numeric, 2)    AS media_barata,
    b.n_itens       AS n_barato,
    ROUND((a.mediana_uf / NULLIF(b.mediana_uf, 0))::numeric, 1) AS razao_mediana
FROM tmp_uf_prices a
JOIN tmp_uf_prices b
    ON a.desc_hash = b.desc_hash
   AND a.material_ou_servico = b.material_ou_servico
   AND a.uf < b.uf                    -- evitar pares duplicados
WHERE a.mediana_uf > 5 * b.mediana_uf -- razão mínima 5× na mediana
  AND b.mediana_uf >= 1               -- baseline mínimo R$1
  AND a.mediana_uf * a.n_itens >= 100000 -- impacto financeiro mínimo R$100K
ORDER BY (a.mediana_uf - b.mediana_uf) * a.n_itens DESC
LIMIT 200;

DROP TABLE tmp_uf_prices;


-- Q95: Fornecedor dominante por tipo de item — concentração de mercado
-- Identifica fornecedores que vencem >50% dos itens de uma descrição específica.
-- Alta concentração em item padronizado pode indicar cartel ou direcionamento.
-- FIX #15: deduplificar contrato por contratação para evitar inflação quando há múltiplos lotes
WITH contrato_dedup AS (
    SELECT DISTINCT numero_controle_contratacao, ni_fornecedor, nome_fornecedor
    FROM pncp_contrato
),
item_wins AS (
    SELECT
        UPPER(TRIM(i.descricao))    AS desc_norm,
        co.ni_fornecedor,
        co.nome_fornecedor,
        COUNT(*)                     AS itens_ganhos,
        SUM(i.valor_total)          AS valor_total_ganho
    FROM pncp_item i
    JOIN pncp_contratacao ca ON ca.numero_controle_pncp = i.numero_controle_pncp
    JOIN contrato_dedup co  ON co.numero_controle_contratacao = ca.numero_controle_pncp
    WHERE i.situacao_item_nome = 'Homologado'
      AND i.valor_total > 0
    GROUP BY UPPER(TRIM(i.descricao)), co.ni_fornecedor, co.nome_fornecedor
),
item_totals AS (
    SELECT desc_norm, SUM(itens_ganhos) AS total_itens, SUM(valor_total_ganho) AS total_valor
    FROM item_wins
    GROUP BY desc_norm
    HAVING SUM(itens_ganhos) >= 20  -- mínimo de 20 itens para relevância
)
SELECT
    w.desc_norm,
    w.ni_fornecedor,
    w.nome_fornecedor,
    w.itens_ganhos,
    ROUND(w.valor_total_ganho::numeric, 2)      AS valor_ganho,
    t.total_itens,
    ROUND((100.0 * w.itens_ganhos / t.total_itens)::numeric, 1) AS pct_mercado,
    ROUND(t.total_valor::numeric, 2)             AS valor_total_mercado
FROM item_wins w
JOIN item_totals t ON t.desc_norm = w.desc_norm
WHERE w.itens_ganhos::float / t.total_itens > 0.5  -- >50% do mercado
  AND t.total_valor >= 100000                        -- mercado >= R$100K
ORDER BY w.valor_total_ganho DESC
LIMIT 200;


-- Q96: Orçamento sigiloso em compras de alto valor
-- Itens com orcamento_sigiloso=TRUE escondem o valor estimado dos licitantes.
-- Em compras de alto valor, isso pode ser usado para evitar comparação de preço.
-- Cruza com contrato para ver o valor efetivamente contratado.
SELECT
    i.numero_controle_pncp,
    i.descricao,
    i.material_ou_servico,
    i.quantidade,
    i.unidade_medida,
    i.valor_unitario_estimado,
    i.valor_total,
    ca.orgao_razao_social,
    ca.cnpj_orgao,
    ca.uf,
    ca.modalidade_nome,
    ca.objeto,
    co.nome_fornecedor,
    co.ni_fornecedor,
    co.valor_global        AS valor_contrato,
    ca.dt_publicacao_pncp
FROM pncp_item i
JOIN pncp_contratacao ca ON ca.numero_controle_pncp = i.numero_controle_pncp
LEFT JOIN pncp_contrato co ON co.numero_controle_contratacao = ca.numero_controle_pncp
WHERE i.orcamento_sigiloso = TRUE
  AND i.situacao_item_nome = 'Homologado'
  AND (i.valor_total >= 500000 OR co.valor_global >= 500000)
ORDER BY COALESCE(co.valor_global, i.valor_total) DESC
LIMIT 200;


-- Q97: Jogo de planilha — item com preço outlier dentro da mesma contratação
-- Detecta contratações onde um item tem preço unitário muito acima (>10×)
-- da média dos demais itens da mesma compra. Fornecedor pode jogar planilha:
-- reduz preço de itens de baixa quantidade e infla itens de alta quantidade.
-- Usa EXCLUDE CURRENT ROW para não poluir a média com o próprio outlier.
WITH contratacao_items AS (
    SELECT
        numero_controle_pncp,
        numero_item,
        descricao,
        valor_unitario_estimado,
        quantidade,
        valor_total,
        AVG(valor_unitario_estimado) OVER (
            PARTITION BY numero_controle_pncp
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
            EXCLUDE CURRENT ROW
        ) AS media_outros,
        COUNT(*) OVER (PARTITION BY numero_controle_pncp) AS n_itens,
        SUM(valor_total) OVER (PARTITION BY numero_controle_pncp) AS valor_total_contratacao
    FROM pncp_item
    WHERE situacao_item_nome = 'Homologado'
      AND valor_unitario_estimado > 0
)
SELECT
    ci.numero_controle_pncp,
    ci.numero_item,
    ci.descricao,
    ci.valor_unitario_estimado,
    ci.quantidade,
    ci.valor_total,
    ROUND(ci.media_outros::numeric, 2)   AS media_demais_itens,
    ROUND((ci.valor_unitario_estimado / NULLIF(ci.media_outros, 0))::numeric, 1) AS vezes_media,
    ci.n_itens,
    ROUND(ci.valor_total_contratacao::numeric, 2) AS valor_total_contratacao,
    ROUND((100.0 * ci.valor_total / NULLIF(ci.valor_total_contratacao, 0))::numeric, 1) AS pct_do_total,
    ca.orgao_razao_social,
    ca.uf
FROM contratacao_items ci
JOIN pncp_contratacao ca ON ca.numero_controle_pncp = ci.numero_controle_pncp
WHERE ci.n_itens >= 5
  AND ci.media_outros >= 1
  AND ci.valor_unitario_estimado > 10 * ci.media_outros
  AND ci.valor_total >= 50000
  AND ci.valor_total <= 1000000000     -- sanidade: exclui erros de digitação > R$1B
  AND ci.valor_total > 0.3 * ci.valor_total_contratacao  -- item domina >30% do valor
ORDER BY ci.valor_total DESC
LIMIT 200;


-- Q98: Preço unitário idêntico (não-redondo) em múltiplas contratações independentes
-- Quando fornecedores combinam preços (cartel), os valores tendem a ser
-- idênticos entre licitações independentes. Filtra preços redondos que
-- ocorrem naturalmente (inteiros e com 1 casa decimal).
WITH preco_freq AS (
    SELECT
        UPPER(TRIM(i.descricao))    AS desc_norm,
        i.valor_unitario_estimado   AS preco,
        COUNT(DISTINCT ca.cnpj_orgao) AS orgaos_distintos,
        COUNT(DISTINCT i.numero_controle_pncp) AS contratacoes,
        COUNT(*) AS ocorrencias,
        ARRAY_AGG(DISTINCT ca.uf ORDER BY ca.uf) AS ufs
    FROM pncp_item i
    JOIN pncp_contratacao ca ON ca.numero_controle_pncp = i.numero_controle_pncp
    WHERE i.situacao_item_nome = 'Homologado'
      AND i.valor_unitario_estimado >= 1   -- excluir placeholders (R$0.01)
      -- Filtrar preços "redondos" que ocorrem naturalmente
      AND i.valor_unitario_estimado <> ROUND(i.valor_unitario_estimado, 0)
      AND i.valor_unitario_estimado <> ROUND(i.valor_unitario_estimado, 1)
    GROUP BY UPPER(TRIM(i.descricao)), i.valor_unitario_estimado
    HAVING COUNT(DISTINCT ca.cnpj_orgao) >= 5
       AND COUNT(DISTINCT i.numero_controle_pncp) >= 10
)
SELECT
    desc_norm,
    preco,
    orgaos_distintos,
    contratacoes,
    ocorrencias,
    ufs
FROM preco_freq
ORDER BY contratacoes DESC
LIMIT 200;

-- Q100: Série temporal de preços — evolução semestral por item
-- Detecta variações anômalas de preço ao longo do tempo para os itens mais
-- comprados. Usa PERCENTILE_CONT (mediana) para robustez contra outliers.
-- Fase 1: calcular mediana por item × semestre
DROP TABLE IF EXISTS tmp_price_series;
CREATE TEMP TABLE tmp_price_series AS
SELECT
    MD5(UPPER(TRIM(i.descricao)) || i.material_ou_servico) AS desc_hash,
    UPPER(TRIM(i.descricao))    AS desc_norm,
    i.material_ou_servico,
    EXTRACT(YEAR FROM ca.dt_publicacao_pncp)::INT AS ano,
    CASE WHEN EXTRACT(MONTH FROM ca.dt_publicacao_pncp) <= 6 THEN 1 ELSE 2 END AS semestre,
    COUNT(*)                     AS n_itens,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY i.valor_unitario_estimado) AS mediana,
    AVG(i.valor_unitario_estimado) AS media,
    MIN(i.valor_unitario_estimado) AS minimo,
    MAX(i.valor_unitario_estimado) AS maximo
FROM pncp_item i
JOIN pncp_contratacao ca ON ca.numero_controle_pncp = i.numero_controle_pncp
WHERE i.situacao_item_nome = 'Homologado'
  AND i.valor_unitario_estimado > 0
  AND i.valor_unitario_estimado <= 10000000
  AND ca.dt_publicacao_pncp IS NOT NULL
GROUP BY MD5(UPPER(TRIM(i.descricao)) || i.material_ou_servico),
         UPPER(TRIM(i.descricao)), i.material_ou_servico,
         EXTRACT(YEAR FROM ca.dt_publicacao_pncp)::INT,
         CASE WHEN EXTRACT(MONTH FROM ca.dt_publicacao_pncp) <= 6 THEN 1 ELSE 2 END
HAVING COUNT(*) >= 10;
CREATE INDEX ON tmp_price_series(desc_hash, ano, semestre);

-- Fase 2: detectar saltos de preço > 2× entre semestres consecutivos
SELECT
    a.desc_norm,
    a.ano AS ano_anterior,
    a.semestre AS sem_anterior,
    a.mediana AS mediana_anterior,
    a.n_itens AS n_anterior,
    b.ano AS ano_atual,
    b.semestre AS sem_atual,
    b.mediana AS mediana_atual,
    b.n_itens AS n_atual,
    ROUND((b.mediana / NULLIF(a.mediana, 0))::NUMERIC, 2) AS razao
FROM tmp_price_series a
JOIN tmp_price_series b ON a.desc_hash = b.desc_hash
WHERE ((a.semestre = 1 AND b.ano = a.ano AND b.semestre = 2)
    OR (a.semestre = 2 AND b.ano = a.ano + 1 AND b.semestre = 1))
  AND b.mediana > 2 * a.mediana
  AND a.n_itens >= 20
  AND b.n_itens >= 20
ORDER BY b.mediana - a.mediana DESC
LIMIT 100;

DROP TABLE tmp_price_series;
