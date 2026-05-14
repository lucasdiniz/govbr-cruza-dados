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
# estabelecimento pra trazer razao_social canonica e descartar proponentes
# sem cadastro RFB (layer 2 da defesa).
#
# Agrega valor_ofertado por (nome, cpf) pra evitar duplicacao em casos onde
# o TCE tem rows diferentes pro mesmo proponente.
LICITACAO_PROPONENTES = """
    WITH proponentes_pj AS (
        SELECT
            l.cpf_cnpj_proponente,
            l.nome_proponente,
            l.valor_ofertado,
            l.situacao_proposta,
            REGEXP_REPLACE(l.cpf_cnpj_proponente, '\\D', '', 'g') AS cnpj_clean
        FROM tce_pb_licitacao l
        WHERE l.municipio = %(municipio)s
          AND l.ano_licitacao = %(ano)s
          AND l.codigo_ug = %(codigo_ug)s
          AND l.modalidade = %(modalidade)s
          AND l.numero_licitacao = %(numero_licitacao)s
          AND LENGTH(REGEXP_REPLACE(l.cpf_cnpj_proponente, '\\D', '', 'g')) = 14
    )
    SELECT
        p.cnpj_clean AS cpf_cnpj,
        COALESCE(NULLIF(e.razao_social, ''), p.nome_proponente) AS razao_social,
        SUM(p.valor_ofertado) AS valor_ofertado,
        MAX(p.situacao_proposta) AS situacao_proposta,
        MAX(est.cnpj_completo) AS cnpj_completo
    FROM proponentes_pj p
    JOIN estabelecimento est ON est.cnpj_basico = LEFT(p.cnpj_clean, 8)
                            AND est.cnpj_ordem = '0001'
    JOIN empresa e ON e.cnpj_basico = LEFT(p.cnpj_clean, 8)
                  -- Layer 2 guard: PJ deve ter cadastro RFB completo.
                  -- Exclui Empresario Individual (natureza_juridica='2135') e MEI
                  -- (simples.opcao_mei='S') pra evitar exposicao de PF disfarcada
                  -- de PJ (razao_social = "NOME CIVIL CPF" eh convencao RFB).
                  -- P1-6 review Opus 4.7 PR #108.
                  AND e.natureza_juridica IS DISTINCT FROM '2135'
                  AND NOT EXISTS (
                      SELECT 1 FROM simples s
                      WHERE s.cnpj_basico = e.cnpj_basico AND s.opcao_mei = 'S'
                  )
    GROUP BY p.cnpj_clean, p.nome_proponente, e.razao_social
    ORDER BY
        -- Vencedor primeiro: situacao_proposta com "vencedor"/"homologad"/"adjudicad".
        -- Sem isso, ORDER BY valor escolhe maior valor como "vencedor" — errado
        -- em pregao menor preco (P2 GPT 5.5 review PR #108).
        CASE WHEN MAX(LOWER(p.situacao_proposta)) ~ '(vencedor|homolog|adjudic)' THEN 0 ELSE 1 END,
        SUM(p.valor_ofertado) DESC NULLS LAST
"""

# Despesas (empenhos) vinculadas a essa licitacao. Apenas PJ credores via
# mesmo filter. Top 50 ordenado por valor_pago. Page links pra /empresa.
LICITACAO_EMPENHOS_VINCULADOS = """
    SELECT
        d.id,
        d.numero_empenho,
        d.data_empenho,
        d.elemento_despesa,
        d.valor_empenhado,
        d.valor_pago,
        REGEXP_REPLACE(d.cpf_cnpj, '\\D', '', 'g') AS cnpj_clean,
        COALESCE(NULLIF(e.razao_social, ''), d.nome_credor) AS razao_social,
        est.cnpj_completo
    FROM tce_pb_despesa d
    JOIN estabelecimento est ON est.cnpj_basico = LEFT(REGEXP_REPLACE(d.cpf_cnpj, '\\D', '', 'g'), 8)
                            AND est.cnpj_ordem = '0001'
    JOIN empresa e ON e.cnpj_basico = LEFT(REGEXP_REPLACE(d.cpf_cnpj, '\\D', '', 'g'), 8)
                  -- Layer 2 + MEI/EI guard (P1-6 Opus PR #108)
                  AND e.natureza_juridica IS DISTINCT FROM '2135'
                  AND NOT EXISTS (
                      SELECT 1 FROM simples s
                      WHERE s.cnpj_basico = e.cnpj_basico AND s.opcao_mei = 'S'
                  )
    WHERE d.municipio = %(municipio)s
      AND d.numero_licitacao = %(numero_licitacao)s
      -- Filter pela 5-tupla canonica pra evitar colisoes entre orgaos/anos
      -- com mesmo numero_licitacao. (P1 GPT 5.5 review PR #108.)
      AND d.codigo_ug = %(codigo_ug)s
      AND d.modalidade_licitacao = %(modalidade)s
      AND EXTRACT(YEAR FROM d.data_empenho) BETWEEN %(ano)s - 1 AND %(ano)s + 5
      AND d.valor_pago > 0
      AND LENGTH(REGEXP_REPLACE(d.cpf_cnpj, '\\D', '', 'g')) = 14
    ORDER BY d.valor_pago DESC NULLS LAST
    LIMIT 50
"""

# Outras licitacoes do mesmo orgao no mesmo ano (sidebar/related).
# Filtra pra excluir a licitacao atual.
LICITACAO_OUTRAS_MESMO_ORGAO = """
    SELECT DISTINCT
        l.numero_licitacao,
        l.ano_licitacao,
        l.modalidade,
        l.codigo_ug,
        l.descricao_ug,
        l.objeto_licitacao,
        l.data_homologacao
    FROM tce_pb_licitacao l
    WHERE l.municipio = %(municipio)s
      AND l.ano_licitacao = %(ano)s
      AND l.codigo_ug = %(codigo_ug)s
      AND NOT (
           l.modalidade = %(modalidade)s
       AND l.numero_licitacao = %(numero_licitacao)s
      )
      -- Mesmo filter de PJ qualificada do sitemap qualifying — evita
      -- gerar links de sidebar que retornam 503 (P2 Opus PR #108).
      AND EXISTS (
          SELECT 1
          FROM tce_pb_licitacao l2
          JOIN estabelecimento est
              ON est.cnpj_basico = LEFT(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g'), 8)
             AND est.cnpj_ordem = '0001'
          JOIN empresa e2 ON e2.cnpj_basico = est.cnpj_basico
                         AND e2.natureza_juridica IS DISTINCT FROM '2135'
                         AND NOT EXISTS (
                             SELECT 1 FROM simples s2
                             WHERE s2.cnpj_basico = e2.cnpj_basico AND s2.opcao_mei = 'S'
                         )
          WHERE l2.municipio = l.municipio
            AND l2.ano_licitacao = l.ano_licitacao
            AND l2.codigo_ug = l.codigo_ug
            AND l2.modalidade = l.modalidade
            AND l2.numero_licitacao = l.numero_licitacao
            AND LENGTH(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g')) = 14
      )
    ORDER BY l.data_homologacao DESC NULLS LAST
    LIMIT 5
"""

# Outras licitacoes da mesma modalidade no municipio (cross-orgao). Mais
# long-tail signal (busca "pregao presencial joao pessoa").
LICITACAO_OUTRAS_MESMA_MODALIDADE = """
    SELECT DISTINCT
        l.numero_licitacao,
        l.ano_licitacao,
        l.modalidade,
        l.codigo_ug,
        l.descricao_ug,
        l.objeto_licitacao,
        l.data_homologacao
    FROM tce_pb_licitacao l
    WHERE l.municipio = %(municipio)s
      AND l.modalidade = %(modalidade)s
      AND NOT (
           l.ano_licitacao = %(ano)s
       AND l.codigo_ug = %(codigo_ug)s
       AND l.numero_licitacao = %(numero_licitacao)s
      )
      AND EXISTS (
          SELECT 1
          FROM tce_pb_licitacao l2
          JOIN estabelecimento est
              ON est.cnpj_basico = LEFT(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g'), 8)
             AND est.cnpj_ordem = '0001'
          JOIN empresa e2 ON e2.cnpj_basico = est.cnpj_basico
                         AND e2.natureza_juridica IS DISTINCT FROM '2135'
                         AND NOT EXISTS (
                             SELECT 1 FROM simples s2
                             WHERE s2.cnpj_basico = e2.cnpj_basico AND s2.opcao_mei = 'S'
                         )
          WHERE l2.municipio = l.municipio
            AND l2.ano_licitacao = l.ano_licitacao
            AND l2.codigo_ug = l.codigo_ug
            AND l2.modalidade = l.modalidade
            AND l2.numero_licitacao = l.numero_licitacao
            AND LENGTH(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g')) = 14
      )
    ORDER BY l.data_homologacao DESC NULLS LAST
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
              JOIN estabelecimento est
                  ON est.cnpj_basico = LEFT(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g'), 8)
                 AND est.cnpj_ordem = '0001'
              JOIN empresa e2 ON e2.cnpj_basico = est.cnpj_basico
                             AND e2.natureza_juridica IS DISTINCT FROM '2135'
                             AND NOT EXISTS (
                                 SELECT 1 FROM simples s2
                                 WHERE s2.cnpj_basico = e2.cnpj_basico AND s2.opcao_mei = 'S'
                             )
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
              JOIN estabelecimento est
                  ON est.cnpj_basico = LEFT(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g'), 8)
                 AND est.cnpj_ordem = '0001'
              JOIN empresa e2 ON e2.cnpj_basico = est.cnpj_basico
                             AND e2.natureza_juridica IS DISTINCT FROM '2135'
                             AND NOT EXISTS (
                                 SELECT 1 FROM simples s2
                                 WHERE s2.cnpj_basico = e2.cnpj_basico AND s2.opcao_mei = 'S'
                             )
              WHERE l2.municipio = l.municipio
                AND l2.ano_licitacao = l.ano_licitacao
                AND l2.codigo_ug = l.codigo_ug
                AND l2.modalidade = l.modalidade
                AND l2.numero_licitacao = l.numero_licitacao
                AND LENGTH(REGEXP_REPLACE(l2.cpf_cnpj_proponente, '\\D', '', 'g')) = 14
          )
    ) qualificadas
"""
