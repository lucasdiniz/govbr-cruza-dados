-- =============================================
-- Queries de fraude usando pncp_item (4.71M itens)
-- Join path: pncp_item → pncp_contratacao (numero_controle_pncp)
--            pncp_contratacao → pncp_contrato (numero_controle_pncp = numero_controle_contratacao)
-- =============================================

-- Q92: Sobrepreço por item — preço unitário muito acima da média nacional
-- Usa window functions para calcular média+desvio por descrição exata.
-- Flagga itens com preço > média + 3×desvio (mínimo 10 itens no grupo).
-- Filtro de sanidade: valor_total <= R$1B (exclui erros de digitação óbvios).
WITH ranked AS (
    SELECT
        numero_controle_pncp,
        numero_item,
        descricao,
        valor_unitario_estimado,
        quantidade,
        valor_total,
        material_ou_servico,
        cnpj_orgao,
        AVG(valor_unitario_estimado) OVER w   AS media_grupo,
        STDDEV(valor_unitario_estimado) OVER w AS desvio_grupo,
        COUNT(*) OVER w                        AS n_grupo
    FROM pncp_item
    WHERE situacao_item_nome = 'Homologado' AND valor_unitario_estimado > 0
    WINDOW w AS (PARTITION BY UPPER(TRIM(descricao)), material_ou_servico)
)
SELECT
    r.numero_controle_pncp,
    r.descricao,
    r.valor_unitario_estimado,
    r.quantidade,
    r.valor_total,
    ca.cnpj_orgao,
    ca.orgao_razao_social,
    ca.uf,
    ca.municipio_nome,
    ROUND(r.media_grupo::numeric, 2)    AS media_nacional,
    ROUND((r.valor_unitario_estimado / NULLIF(r.media_grupo, 0))::numeric, 1) AS vezes_media,
    r.n_grupo
FROM ranked r
JOIN pncp_contratacao ca ON ca.numero_controle_pncp = r.numero_controle_pncp
WHERE r.n_grupo >= 10
  AND r.media_grupo >= 1
  AND r.valor_total >= 10000
  AND r.valor_total <= 1000000000      -- sanidade: exclui erros de digitação > R$1B
  AND r.valor_unitario_estimado > r.media_grupo + 3 * COALESCE(NULLIF(r.desvio_grupo, 0), r.media_grupo)
ORDER BY r.valor_total DESC
LIMIT 200;


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
-- Compara preço médio de itens idênticos (descrição exata) entre estados.
-- Razão > 5× entre UFs pode indicar sobrepreço regional.
-- Usa AVG em vez de PERCENTILE_CONT por performance.
WITH uf_prices AS (
    SELECT
        UPPER(TRIM(i.descricao))    AS desc_norm,
        i.material_ou_servico,
        ca.uf,
        COUNT(*)                     AS n_itens,
        AVG(i.valor_unitario_estimado) AS media_uf
    FROM pncp_item i
    JOIN pncp_contratacao ca ON ca.numero_controle_pncp = i.numero_controle_pncp
    WHERE i.situacao_item_nome = 'Homologado'
      AND i.valor_unitario_estimado > 0
      AND i.valor_unitario_estimado <= 10000000   -- sanidade
    GROUP BY UPPER(TRIM(i.descricao)), i.material_ou_servico, ca.uf
    HAVING COUNT(*) >= 5
)
SELECT
    a.desc_norm,
    a.uf            AS uf_cara,
    ROUND(a.media_uf::numeric, 2)    AS preco_caro,
    a.n_itens       AS n_caro,
    b.uf            AS uf_barata,
    ROUND(b.media_uf::numeric, 2)    AS preco_barato,
    b.n_itens       AS n_barato,
    ROUND((a.media_uf / NULLIF(b.media_uf, 0))::numeric, 1) AS razao
FROM uf_prices a
JOIN uf_prices b
    ON a.desc_norm = b.desc_norm
   AND a.material_ou_servico = b.material_ou_servico
   AND a.uf < b.uf                    -- evitar pares duplicados
WHERE a.media_uf > 5 * b.media_uf     -- razão mínima 5×
  AND b.media_uf >= 1                  -- baseline mínimo R$1
  AND a.media_uf * a.n_itens >= 100000 -- impacto financeiro mínimo R$100K
ORDER BY (a.media_uf - b.media_uf) * a.n_itens DESC
LIMIT 200;


-- Q95: Fornecedor dominante por tipo de item — concentração de mercado
-- Identifica fornecedores que vencem >50% dos itens de uma descrição específica.
-- Alta concentração em item padronizado pode indicar cartel ou direcionamento.
WITH item_wins AS (
    SELECT
        UPPER(TRIM(i.descricao))    AS desc_norm,
        co.ni_fornecedor,
        co.nome_fornecedor,
        COUNT(*)                     AS itens_ganhos,
        SUM(i.valor_total)          AS valor_total_ganho
    FROM pncp_item i
    JOIN pncp_contratacao ca ON ca.numero_controle_pncp = i.numero_controle_pncp
    JOIN pncp_contrato co   ON co.numero_controle_contratacao = ca.numero_controle_pncp
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
