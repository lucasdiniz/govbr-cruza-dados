"""SQL parametrizado para /licitacao/<mun>/<ano>/<ug>/<mod-num> e
sitemap-licitacoes.

Design:
- Filter PJ-only via inline regex sobre cpf_cnpj_proponente. Sem dependencia
  de cpf_cnpj_norm normalizado (que nao existe em tce_pb_licitacao). O filter
  conta digitos apos REGEXP_REPLACE pra evitar falso-positivo de mascaras
  com 14 chars (ex: '123.456.789-01' = 14 chars mas 11 digitos = CPF PF).
- Layer 2 de defense in depth no template: JOIN com `estabelecimento` —
  proponente sem cadastro RFB e omitido.
"""

# ─────────────────────────────────────────────────────────────────────────
# Detalhes principais — metadata, proponentes, despesas vinculadas, outras
# ─────────────────────────────────────────────────────────────────────────

# Metadata da licitacao. Filtra por (municipio, ano, codigo_ug, modalidade,
# numero_licitacao). 5-tupla garante unicidade (validado no spike).
# Multiple rows existem (1 por proponente); pegamos DISTINCT no metadata
# e agregamos proponentes na query separada.
LICITACAO_DETAIL = """
    SELECT DISTINCT
        l.numero_licitacao,
        l.ano_licitacao,
        l.modalidade,
        l.objeto_licitacao,
        l.data_homologacao,
        l.descricao_ug,
        l.codigo_ug,
        l.municipio
    FROM tce_pb_licitacao l
    WHERE l.municipio = %(municipio)s
      AND l.ano_licitacao = %(ano)s
      AND l.codigo_ug = %(codigo_ug)s
      AND l.modalidade = %(modalidade)s
      AND l.numero_licitacao = %(numero_licitacao)s
    LIMIT 1
"""

# Proponentes da licitacao. Apenas PJ (14 digitos limpos). JOIN com
# estabelecimento+empresa pra trazer razao_social canonica e descartar
# proponentes sem cadastro RFB (layer 2).
#
# Filter natureza_juridica NOT LIKE '1%%' exclui apenas orgaos publicos
# (codigos 1xxx). MEI (simples.opcao_mei='S') e Empresario Individual
# (natureza '2135') sao fornecedores LEGITIMOS — passam (consistente com
# /cidade e /empresa).
#
# Agrega valor_ofertado por (nome, cpf) pra evitar duplicacao em casos onde
# o TCE tem rows diferentes pro mesmo proponente.
LICITACAO_PROPONENTES = """
    WITH proponentes_pj AS MATERIALIZED (
        SELECT
            l.cpf_cnpj_proponente,
            l.nome_proponente,
            l.valor_ofertado,
            l.situacao_proposta,
            REGEXP_REPLACE(l.cpf_cnpj_proponente, '\\D', '', 'g') AS cnpj_clean,
            LEFT(REGEXP_REPLACE(l.cpf_cnpj_proponente, '\\D', '', 'g'), 8)::bpchar(8) AS cnpj_basico
        FROM tce_pb_licitacao l
        WHERE l.municipio = %(municipio)s
          AND l.ano_licitacao = %(ano)s
          AND l.codigo_ug = %(codigo_ug)s
          AND l.modalidade = %(modalidade)s
          AND l.numero_licitacao = %(numero_licitacao)s
          AND LENGTH(REGEXP_REPLACE(l.cpf_cnpj_proponente, '\\D', '', 'g')) = 14
    )
    -- MATERIALIZED + ::bpchar(8) sao CRITICOS pra perf: sem cast explicito,
    -- planner usa idx_empresa_cnpj_text_razao com estatisticas furadas (estima
    -- 338k rows/cnpj_basico ao inves de 1). Com cast bpchar, usa empresa_pkey
    -- (unique). MATERIALIZED evita inline da CTE em PG12+ que reativaria o
    -- problema. Resultado: 37ms vs 90s+timeout. (Hotfix pos-PR #108.)
    SELECT
        p.cnpj_clean AS cpf_cnpj,
        COALESCE(NULLIF(e.razao_social, ''), p.nome_proponente) AS razao_social,
        SUM(p.valor_ofertado) AS valor_ofertado,
        MAX(p.situacao_proposta) AS situacao_proposta,
        MAX(est.cnpj_completo) AS cnpj_completo
    FROM proponentes_pj p
    JOIN empresa e ON e.cnpj_basico = p.cnpj_basico
                  AND e.natureza_juridica NOT LIKE '1%%'
    JOIN estabelecimento est ON est.cnpj_basico = p.cnpj_basico
                            AND est.cnpj_ordem = '0001'
    GROUP BY p.cnpj_clean, p.nome_proponente, e.razao_social
    ORDER BY
        -- Vencedor primeiro: qualquer row do proponente com situacao
        -- "vencedor"/"homologad"/"adjudicad". bool_or() (nao MAX()) pra
        -- nao perder vencedor quando o mesmo CNPJ tem rows heterogeneas
        -- (multiplos itens em pregao por item). (P2 round 2 PR #108.)
        CASE WHEN bool_or(LOWER(p.situacao_proposta) ~ '(vencedor|homolog|adjudic)') THEN 0 ELSE 1 END,
        SUM(p.valor_ofertado) DESC NULLS LAST
"""

# Despesas (empenhos) vinculadas a essa licitacao. Usa d.cnpj_basico
# pre-computado em tce_pb_despesa (varchar(8)), cast pra bpchar(8) no JOIN
# pra forcar uso de empresa_pkey/estabelecimento_pkey.
#
# IMPORTANTE: o warmer recebe a 5-tupla canonica do tce_pb_licitacao
# (numero_licitacao='00003/2025', modalidade='Pregao (Lei No 14.133/2021)')
# mas tce_pb_despesa usa formatos diferentes ('000032025', 'Pregao (Lei
# 14.133/21)'). Igualdade direta NUNCA bate. Match canonico:
#   - numero: digit-only normalization (REGEXP_REPLACE \D)
#   - modalidade: lowercase + unaccent + strip suffix " (...)"
LICITACAO_EMPENHOS_VINCULADOS = """
    WITH despesas_pj AS MATERIALIZED (
        SELECT
            d.id, d.numero_empenho, d.data_empenho, d.elemento_despesa,
            d.valor_empenhado, d.valor_pago, d.cpf_cnpj, d.nome_credor,
            d.cnpj_basico::bpchar(8) AS cnpj_basico
        FROM tce_pb_despesa d
        WHERE d.municipio = %(municipio)s
          -- Match canonico: tce_pb_despesa.numero_licitacao usa formato
          -- compacto ('000032025'), tce_pb_licitacao usa '00003/2025'.
          AND REGEXP_REPLACE(d.numero_licitacao, '\\D', '', 'g')
            = REGEXP_REPLACE(%(numero_licitacao)s, '\\D', '', 'g')
          -- Filter pela 5-tupla canonica pra evitar colisoes entre orgaos/anos
          -- com mesmo numero_licitacao. (P1 GPT 5.5 review PR #108.)
          AND d.codigo_ug = %(codigo_ug)s
          -- Match canonico: tce_pb_despesa.modalidade_licitacao usa formato
          -- compacto ('Pregao (Lei 14.133/21)'), tce_pb_licitacao usa
          -- 'Pregao (Lei No 14.133/2021)'.
          AND LOWER(unaccent(BTRIM(REGEXP_REPLACE(
                d.modalidade_licitacao,
                '\\s*-?\\s*\\([^)]*\\).*$', ''))))
            = LOWER(unaccent(BTRIM(REGEXP_REPLACE(
                %(modalidade)s,
                '\\s*-?\\s*\\([^)]*\\).*$', ''))))
          AND EXTRACT(YEAR FROM d.data_empenho) BETWEEN %(ano)s - 1 AND %(ano)s + 5
          AND d.valor_pago > 0
          AND d.cnpj_basico IS NOT NULL
    )
    SELECT
        dp.id, dp.numero_empenho, dp.data_empenho, dp.elemento_despesa,
        dp.valor_empenhado, dp.valor_pago,
        dp.cpf_cnpj AS cnpj_clean,
        COALESCE(NULLIF(e.razao_social, ''), dp.nome_credor) AS razao_social,
        est.cnpj_completo
    FROM despesas_pj dp
    JOIN empresa e ON e.cnpj_basico = dp.cnpj_basico
                  AND e.natureza_juridica NOT LIKE '1%%'
    JOIN estabelecimento est ON est.cnpj_basico = dp.cnpj_basico
                            AND est.cnpj_ordem = '0001'
    ORDER BY dp.valor_pago DESC NULLS LAST
    LIMIT 50
"""

# Outras licitacoes do mesmo orgao no mesmo ano (sidebar/related).
# Filtra pra excluir a licitacao atual.
LICITACAO_OUTRAS_MESMO_ORGAO = """
    WITH lic_alvo AS (
        SELECT DISTINCT
            l.municipio, l.ano_licitacao, l.codigo_ug, l.modalidade,
            l.numero_licitacao, l.descricao_ug, l.objeto_licitacao,
            l.data_homologacao
        FROM tce_pb_licitacao l
        WHERE l.municipio = %(municipio)s
          AND l.ano_licitacao = %(ano)s
          AND l.codigo_ug = %(codigo_ug)s
          AND NOT (
               l.modalidade = %(modalidade)s
           AND l.numero_licitacao = %(numero_licitacao)s
          )
    ),
    qualificadas AS (
        SELECT DISTINCT la.municipio, la.ano_licitacao, la.codigo_ug,
                        la.modalidade, la.numero_licitacao
        FROM lic_alvo la
        JOIN tce_pb_licitacao l2
            ON l2.municipio = la.municipio
           AND l2.ano_licitacao = la.ano_licitacao
           AND l2.codigo_ug = la.codigo_ug
           AND l2.modalidade = la.modalidade
           AND l2.numero_licitacao = la.numero_licitacao
        JOIN empresa e2 ON e2.cnpj_basico = LEFT(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g'), 8)::bpchar(8)
                       AND e2.natureza_juridica NOT LIKE '1%%'
        JOIN estabelecimento est ON est.cnpj_basico = e2.cnpj_basico
                                AND est.cnpj_ordem = '0001'
        WHERE LENGTH(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g')) = 14
    )
    SELECT la.numero_licitacao, la.ano_licitacao, la.modalidade,
           la.codigo_ug, la.descricao_ug, la.objeto_licitacao,
           la.data_homologacao
    FROM lic_alvo la
    JOIN qualificadas q
      ON q.municipio = la.municipio
     AND q.ano_licitacao = la.ano_licitacao
     AND q.codigo_ug = la.codigo_ug
     AND q.modalidade = la.modalidade
     AND q.numero_licitacao = la.numero_licitacao
    ORDER BY la.data_homologacao DESC NULLS LAST
    LIMIT 5
"""

# Outras licitacoes da mesma modalidade no municipio (cross-orgao). Mais
# long-tail signal (busca "pregao presencial joao pessoa").
LICITACAO_OUTRAS_MESMA_MODALIDADE = """
    WITH lic_alvo AS (
        SELECT DISTINCT
            l.municipio, l.ano_licitacao, l.codigo_ug, l.modalidade,
            l.numero_licitacao, l.descricao_ug, l.objeto_licitacao,
            l.data_homologacao
        FROM tce_pb_licitacao l
        WHERE l.municipio = %(municipio)s
          AND l.modalidade = %(modalidade)s
          AND NOT (
               l.ano_licitacao = %(ano)s
           AND l.codigo_ug = %(codigo_ug)s
           AND l.numero_licitacao = %(numero_licitacao)s
          )
    ),
    qualificadas AS (
        SELECT DISTINCT la.municipio, la.ano_licitacao, la.codigo_ug,
                        la.modalidade, la.numero_licitacao
        FROM lic_alvo la
        JOIN tce_pb_licitacao l2
            ON l2.municipio = la.municipio
           AND l2.ano_licitacao = la.ano_licitacao
           AND l2.codigo_ug = la.codigo_ug
           AND l2.modalidade = la.modalidade
           AND l2.numero_licitacao = la.numero_licitacao
        JOIN empresa e2 ON e2.cnpj_basico = LEFT(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g'), 8)::bpchar(8)
                       AND e2.natureza_juridica NOT LIKE '1%%'
        JOIN estabelecimento est ON est.cnpj_basico = e2.cnpj_basico
                                AND est.cnpj_ordem = '0001'
        WHERE LENGTH(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g')) = 14
    )
    SELECT la.numero_licitacao, la.ano_licitacao, la.modalidade,
           la.codigo_ug, la.descricao_ug, la.objeto_licitacao,
           la.data_homologacao
    FROM lic_alvo la
    JOIN qualificadas q
      ON q.municipio = la.municipio
     AND q.ano_licitacao = la.ano_licitacao
     AND q.codigo_ug = la.codigo_ug
     AND q.modalidade = la.modalidade
     AND q.numero_licitacao = la.numero_licitacao
    ORDER BY la.data_homologacao DESC NULLS LAST
    LIMIT 5
"""

# ─────────────────────────────────────────────────────────────────────────
# Sitemap qualifying — todas as licitacoes com >=1 proponente PJ qualificado
# ─────────────────────────────────────────────────────────────────────────

# Lista paginada pro warmer/sitemap. Retorna a 5-tupla canonica que vai
# montar o URL. ORDER BY estavel pra paginacao bater entre warmer e shard.
LICITACOES_QUALIFICADAS_PAGINATED = """
    WITH lic_unique AS (
        SELECT DISTINCT
            l.municipio,
            l.ano_licitacao,
            l.codigo_ug,
            l.descricao_ug,
            l.modalidade,
            l.numero_licitacao
        FROM tce_pb_licitacao l
        WHERE l.ano_licitacao IS NOT NULL
          AND l.numero_licitacao IS NOT NULL
          AND l.modalidade IS NOT NULL
          AND l.codigo_ug IS NOT NULL
          AND l.municipio IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM tce_pb_licitacao l2
              JOIN empresa e2 ON e2.cnpj_basico = LEFT(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g'), 8)::bpchar(8)
                             AND e2.natureza_juridica NOT LIKE '1%%'
              JOIN estabelecimento est ON est.cnpj_basico = e2.cnpj_basico
                                      AND est.cnpj_ordem = '0001'
              WHERE l2.municipio = l.municipio
                AND l2.ano_licitacao = l.ano_licitacao
                AND l2.codigo_ug = l.codigo_ug
                AND l2.modalidade = l.modalidade
                AND l2.numero_licitacao = l.numero_licitacao
                AND LENGTH(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g')) = 14
          )
    )
    SELECT municipio, ano_licitacao, codigo_ug, descricao_ug, modalidade, numero_licitacao
    FROM lic_unique
    ORDER BY municipio, ano_licitacao DESC, codigo_ug, modalidade, numero_licitacao
    LIMIT %(limit)s OFFSET %(offset)s
"""

# Count total pra calcular num_shards no sitemap-index.
LICITACOES_QUALIFICADAS_COUNT = """
    SELECT COUNT(*) FROM (
        SELECT DISTINCT
            l.municipio,
            l.ano_licitacao,
            l.codigo_ug,
            l.modalidade,
            l.numero_licitacao
        FROM tce_pb_licitacao l
        WHERE l.ano_licitacao IS NOT NULL
          AND l.numero_licitacao IS NOT NULL
          AND l.modalidade IS NOT NULL
          AND l.codigo_ug IS NOT NULL
          AND l.municipio IS NOT NULL
          AND EXISTS (
              SELECT 1
              FROM tce_pb_licitacao l2
              JOIN empresa e2 ON e2.cnpj_basico = LEFT(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g'), 8)::bpchar(8)
                             AND e2.natureza_juridica NOT LIKE '1%%'
              JOIN estabelecimento est ON est.cnpj_basico = e2.cnpj_basico
                                      AND est.cnpj_ordem = '0001'
              WHERE l2.municipio = l.municipio
                AND l2.ano_licitacao = l.ano_licitacao
                AND l2.codigo_ug = l.codigo_ug
                AND l2.modalidade = l.modalidade
                AND l2.numero_licitacao = l.numero_licitacao
                AND LENGTH(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g')) = 14
          )
    ) qualificadas
"""
