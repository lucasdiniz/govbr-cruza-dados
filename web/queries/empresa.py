"""SQL parametrizado para o perfil publico de empresa (/empresa/<cnpj>) e
para o endpoint /api/fornecedor/detalhes (dialog).

As 8 primeiras constantes (CEIS, CNEP, ESTABELECIMENTO, MATRIZ, SOCIOS,
PGFN, LENIENCIA, EFEITOS) reproduzem byte-a-byte os SQLs que viviam
inline em web/routes/cidade.py:1746-1992. Foram extraidas pra que a rota
nova /empresa/{cnpj} consuma a mesma fonte canonica e o dialog continue
identico.
"""

# ─────────────────────────────────────────────────────────────────────────
# Cadastro RFB (estabelecimento + empresa)
# ─────────────────────────────────────────────────────────────────────────

EMPRESA_ESTABELECIMENTO_BY_CNPJ_COMPLETO = """
                    SELECT
                        est.situacao_cadastral, est.dt_situacao,
                        est.cnpj_completo, est.cnae_principal,
                        dcnae.descricao AS desc_cnae_principal,
                        est.uf,
                        COALESCE(dm.descricao, est.municipio) AS municipio,
                        est.matriz_filial, est.nome_fantasia,
                        est.dt_inicio_atividade,
                        est.tipo_logradouro, est.logradouro, est.numero,
                        est.complemento, est.bairro, est.cep,
                        est.ddd1, est.telefone1, est.email,
                        e.razao_social, e.capital_social, e.porte,
                        e.natureza_juridica,
                        dnj.descricao AS desc_natureza_juridica,
                        e.ente_federativo
                    FROM estabelecimento est
                    LEFT JOIN empresa e ON e.cnpj_basico = est.cnpj_basico
                    LEFT JOIN dom_municipio dm ON dm.codigo = est.municipio
                    LEFT JOIN dom_cnae dcnae ON dcnae.codigo = est.cnae_principal
                    LEFT JOIN dom_natureza_juridica dnj ON dnj.codigo = e.natureza_juridica
                    WHERE est.cnpj_completo = %s
                """

EMPRESA_MATRIZ_BY_BASICO = """
                        SELECT est.cnpj_completo,
                               est.tipo_logradouro, est.logradouro, est.numero,
                               est.complemento, est.bairro, est.cep,
                               est.ddd1, est.telefone1, est.email,
                               COALESCE(dm.descricao, est.municipio) AS municipio,
                               est.uf, est.nome_fantasia,
                               est.dt_inicio_atividade
                        FROM estabelecimento est
                        LEFT JOIN dom_municipio dm ON dm.codigo = est.municipio
                        WHERE est.cnpj_basico = %s AND est.cnpj_ordem = '0001'
                    """

EMPRESA_SOCIOS_BY_BASICO = """
                    SELECT s.tipo_socio, s.nome, s.cpf_cnpj_socio,
                           s.qualificacao,
                           dq.descricao AS desc_qualificacao,
                           s.dt_entrada, s.pais, s.faixa_etaria,
                           s.nome_representante, s.cpf_representante,
                           s.qualif_representante,
                           dqr.descricao AS desc_qualif_representante
                    FROM socio s
                    LEFT JOIN dom_qualificacao dq ON dq.codigo = s.qualificacao
                    LEFT JOIN dom_qualificacao dqr ON dqr.codigo = s.qualif_representante
                    WHERE s.cnpj_basico = %s
                    ORDER BY s.tipo_socio, s.dt_entrada DESC
                """

# ─────────────────────────────────────────────────────────────────────────
# Sancoes (CEIS / CNEP) e dividas (PGFN) — chave: cpf_cnpj_norm = 14 digitos
# Usadas pelo dialog (cidade.py /api/fornecedor/detalhes), onde o usuario
# clica num pagamento especifico do municipio e queremos as sancoes do
# estabelecimento exato que recebeu aquele empenho.
# ─────────────────────────────────────────────────────────────────────────

EMPRESA_SANCOES_CEIS_BY_CNPJ = """
                    SELECT cpf_cnpj_norm AS cpf_cnpj_sancionado,
                           categoria_sancao, dt_inicio_sancao, dt_final_sancao,
                           orgao_sancionador, esfera_orgao_sancionador, fundamentacao_legal,
                           abrangencia_sancao
                    FROM ceis_sancao
                    WHERE cpf_cnpj_norm = %s
                    ORDER BY dt_inicio_sancao DESC
                """

EMPRESA_SANCOES_CNEP_BY_CNPJ = """
                    SELECT cpf_cnpj_norm AS cpf_cnpj_sancionado,
                           categoria_sancao, dt_inicio_sancao, dt_final_sancao,
                           orgao_sancionador, esfera_orgao_sancionador, fundamentacao_legal, valor_multa,
                           abrangencia_sancao
                    FROM cnep_sancao
                    WHERE cpf_cnpj_norm = %s
                    ORDER BY dt_inicio_sancao DESC
                """

EMPRESA_PGFN_BY_CNPJ = """
                    SELECT numero_inscricao, situacao_inscricao,
                           receita_principal, valor_consolidado,
                           dt_inscricao, indicador_ajuizado
                    FROM pgfn_divida
                    WHERE cpf_cnpj_norm = %s
                    ORDER BY valor_consolidado DESC
                """

EMPRESA_LENIENCIA_BY_CNPJ = """
                    SELECT al.cnpj_sancionado, al.razao_social_rfb, al.situacao_acordo,
                           al.orgao_sancionador, al.dt_inicio_acordo, al.dt_fim_acordo,
                           al.numero_processo, al.id_acordo
                    FROM acordo_leniencia al
                    WHERE al.cnpj_norm = %s
                    ORDER BY al.dt_inicio_acordo DESC
                """

EMPRESA_LENIENCIA_EFEITOS_BY_ID = """
                            SELECT efeito, complemento FROM acordo_efeito
                            WHERE id_acordo = %s
                        """

# ─────────────────────────────────────────────────────────────────────────
# Versoes _BY_BASICO — usadas pela pagina /empresa/{cnpj} (perfil agregado
# da empresa raiz, alinhado com mv_empresa_pb que tambem agrega por
# cnpj_basico). Garantem coerencia entre KPIs (que vem da MV agregada por
# basico) e listagens detalhadas.
#
# Os filtros foram alinhados com os indices parciais existentes em
# sql/19_indices_queries.sql:
#   - CEIS/CNEP: idx_ceis/cnep_cnpj_basico_j ON (LEFT(cpf_cnpj_norm,8))
#                WHERE tipo_pessoa = 'J' — usar `tipo_pessoa = 'J'` strict
#                (CGU normaliza pra 'J', valor unico em pratica).
#   - PGFN: idx_pgfn_cnpj_basico_norm ON (LEFT(cpf_cnpj_norm,8))
#           WHERE LENGTH(cpf_cnpj_norm) = 14 — usar LENGTH=14 (exclui CPFs
#           cujo prefixo de 8 caracteres poderia colidir).
#   - LENIENCIA: tabela pequena (~80 acordos historicos), seq scan trivial.
# Sem esses filtros casando com os indices, o warmer rodaria seq scan em
# tabelas de milhoes de rows × 45K empresas — risco de derrubar o DB
# justamente no rollout que deveria evitar isso (P1 do GPT 5.5 review).
# ─────────────────────────────────────────────────────────────────────────

EMPRESA_SANCOES_CEIS_BY_BASICO = """
    SELECT cpf_cnpj_norm AS cpf_cnpj_sancionado,
           categoria_sancao, dt_inicio_sancao, dt_final_sancao,
           orgao_sancionador, esfera_orgao_sancionador, fundamentacao_legal,
           abrangencia_sancao
    FROM ceis_sancao
    WHERE LEFT(cpf_cnpj_norm, 8) = %s
      AND tipo_pessoa = 'J'
      AND cpf_cnpj_norm IS NOT NULL
    ORDER BY dt_inicio_sancao DESC
"""

EMPRESA_SANCOES_CNEP_BY_BASICO = """
    SELECT cpf_cnpj_norm AS cpf_cnpj_sancionado,
           categoria_sancao, dt_inicio_sancao, dt_final_sancao,
           orgao_sancionador, esfera_orgao_sancionador, fundamentacao_legal, valor_multa,
           abrangencia_sancao
    FROM cnep_sancao
    WHERE LEFT(cpf_cnpj_norm, 8) = %s
      AND tipo_pessoa = 'J'
      AND cpf_cnpj_norm IS NOT NULL
    ORDER BY dt_inicio_sancao DESC
"""

EMPRESA_PGFN_BY_BASICO = """
    SELECT numero_inscricao, situacao_inscricao,
           receita_principal, valor_consolidado,
           dt_inscricao, indicador_ajuizado
    FROM pgfn_divida
    WHERE LEFT(cpf_cnpj_norm, 8) = %s
      AND LENGTH(cpf_cnpj_norm) = 14
    ORDER BY valor_consolidado DESC
"""

EMPRESA_LENIENCIA_BY_BASICO = """
    SELECT al.cnpj_sancionado, al.razao_social_rfb, al.situacao_acordo,
           al.orgao_sancionador, al.dt_inicio_acordo, al.dt_fim_acordo,
           al.numero_processo, al.id_acordo
    FROM acordo_leniencia al
    WHERE LEFT(al.cnpj_norm, 8) = %s
    ORDER BY al.dt_inicio_acordo DESC
"""

# ─────────────────────────────────────────────────────────────────────────
# Pagamentos publicos PB (agregados + por municipio + top elementos)
# Usados apenas pela pagina /empresa/{cnpj}.
# ─────────────────────────────────────────────────────────────────────────

EMPRESA_AGREGADOS_PB_BY_BASICO = """
    SELECT *
    FROM mv_empresa_pb
    WHERE cnpj_basico = %s
"""

# CPF-padding contamination guard:
# TCE-PB envia 'cpf_cnpj' sempre com 14 chars; CPFs (11 digitos validos)
# vem com padding de zeros a esquerda (ex: '00014020752435' = CPF
# '140.207.524-35' com '000' colado no inicio). LEFT(cpf_cnpj, 8) =
# '00014020' pode coincidir com cnpj_basico de empresa real (ex:
# AVICOLA CHESTER MONGAGUA LTDA), contaminando o perfil dela com empenhos
# de pessoas fisicas.
#
# Fix: filtrar empenhos onde cpf_cnpj EXISTE como cnpj_completo no RFB
# (matriz + filiais). CPFs padded nunca casam (RFB so tem PJ). Usa
# idx_estab_cnpj_completo pra perf.
#
# Por que NAO filtrar por cpf_cnpj = est.cnpj_completo na matriz so:
# isso perderia filiais (ordens != 0001) que recebem do governo —
# pra BB (raiz 00000000), filiais somam 93% dos empenhos.

EMPRESA_MUNICIPIOS_PAGANTES_BY_BASICO = """
    SELECT municipio,
           SUM(valor_pago) AS total_pago,
           COUNT(*) AS qtd_empenhos
    FROM tce_pb_despesa d
    WHERE d.cnpj_basico = %s
      AND d.valor_pago > 0
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
    GROUP BY municipio
    ORDER BY total_pago DESC
"""

EMPRESA_TOP_ELEMENTOS_GLOBAL_BY_BASICO = """
    SELECT elemento_despesa,
           SUM(valor_pago) AS total_elemento,
           COUNT(*) AS qtd
    FROM tce_pb_despesa d
    WHERE d.cnpj_basico = %s
      AND d.valor_pago > 0
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
    GROUP BY elemento_despesa
    ORDER BY SUM(valor_pago) DESC
    LIMIT 5
"""

# ─────────────────────────────────────────────────────────────────────────
# Detalhe (cnpj × municipio) — alimenta /empresa/<cnpj>/<municipio_slug>
# e tambem a secao "Pagamentos detalhados" da pagina global. Replicam
# a logica que o dialog de fornecedor faz inline em cidade.py
# (/api/fornecedor/detalhes), mas filtram por cnpj_basico (em vez de
# cpf_cnpj exato) para coerencia com mv_empresa_pb e
# EMPRESA_MUNICIPIOS_PAGANTES_BY_BASICO. Diferenca esperada: filiais
# do mesmo grupo (ordens != 0001) que recebam no mesmo municipio
# entram juntas, alinhado com a visao "perfil da empresa raiz".
# ─────────────────────────────────────────────────────────────────────────

EMPRESA_EMPENHOS_RECENTES_BY_MUN = """
    SELECT id, numero_empenho, data_empenho, elemento_despesa,
           valor_empenhado, valor_pago,
           modalidade_licitacao, numero_licitacao
    FROM tce_pb_despesa d
    WHERE d.cnpj_basico = %(cnpj_basico)s
      AND d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
    ORDER BY data_empenho DESC NULLS LAST, id DESC
    LIMIT 50
"""

# ─────────────────────────────────────────────────────────────────────────
# Empenhos paginados + filtraveis (data + busca textual). Alimentam o
# endpoint /api/empresa/empenhos para paginacao live (page 2+ ou qualquer
# filtro). Page 1 sem filtros eh servido do warmer cache (campo `empenhos`
# em EMPRESA_PERFIL_MUN/EMPRESA_PERFIL).
#
# Filtros opcionais via padrao "param IS NULL OR coluna OP param" — isso
# permite uma unica query servir todos os casos (com/sem data, com/sem
# busca) sem string concat. PG otimiza bem esse padrao quando os params
# sao todos NULL (planner pode pular).
#
# Busca textual: ILIKE em 4 colunas (numero, elemento, historico,
# modalidade). Sem FTS por ora — ILIKE funciona bem com WHERE ja restrito
# por cnpj_basico/municipio (poucos milhares de rows). Frontend exige
# min 2 chars.
#
# ORDER BY data_empenho DESC NULLS LAST, id DESC: estavel para
# paginacao (id desempata datas iguais).
# ─────────────────────────────────────────────────────────────────────────

EMPRESA_EMPENHOS_PAGINATED_BY_MUN = """
    SELECT id, numero_empenho, data_empenho, elemento_despesa,
           valor_empenhado, valor_pago,
           modalidade_licitacao, numero_licitacao
    FROM tce_pb_despesa d
    WHERE d.cnpj_basico = %(cnpj_basico)s
      AND d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
      AND (%(data_inicio)s IS NULL OR data_empenho >= %(data_inicio)s::date)
      AND (%(data_fim)s IS NULL OR data_empenho <= %(data_fim)s::date)
      AND (
          %(q)s IS NULL OR (
              numero_empenho ILIKE %(q_pat)s
              OR elemento_despesa ILIKE %(q_pat)s
              OR COALESCE(historico, '') ILIKE %(q_pat)s
              OR COALESCE(modalidade_licitacao, '') ILIKE %(q_pat)s
          )
      )
    ORDER BY data_empenho DESC NULLS LAST, id DESC
    LIMIT %(limit)s OFFSET %(offset)s
"""

EMPRESA_EMPENHOS_COUNT_BY_MUN = """
    SELECT COUNT(*)
    FROM tce_pb_despesa d
    WHERE d.cnpj_basico = %(cnpj_basico)s
      AND d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
      AND (%(data_inicio)s IS NULL OR data_empenho >= %(data_inicio)s::date)
      AND (%(data_fim)s IS NULL OR data_empenho <= %(data_fim)s::date)
      AND (
          %(q)s IS NULL OR (
              numero_empenho ILIKE %(q_pat)s
              OR elemento_despesa ILIKE %(q_pat)s
              OR COALESCE(historico, '') ILIKE %(q_pat)s
              OR COALESCE(modalidade_licitacao, '') ILIKE %(q_pat)s
          )
      )
"""

# Variantes globais (sem filtro de municipio) — usadas pela pagina
# /empresa/<cnpj> (perfil global). Warmer popula primeira pagina;
# pages 2+ ou filtros sao live.
EMPRESA_EMPENHOS_PAGINATED_GLOBAL = """
    SELECT id, numero_empenho, data_empenho, municipio, elemento_despesa,
           valor_empenhado, valor_pago,
           modalidade_licitacao, numero_licitacao
    FROM tce_pb_despesa d
    WHERE d.cnpj_basico = %(cnpj_basico)s
      AND d.valor_pago > 0
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
      AND (%(data_inicio)s IS NULL OR data_empenho >= %(data_inicio)s::date)
      AND (%(data_fim)s IS NULL OR data_empenho <= %(data_fim)s::date)
      AND (
          %(q)s IS NULL OR (
              numero_empenho ILIKE %(q_pat)s
              OR elemento_despesa ILIKE %(q_pat)s
              OR COALESCE(historico, '') ILIKE %(q_pat)s
              OR COALESCE(modalidade_licitacao, '') ILIKE %(q_pat)s
              OR municipio ILIKE %(q_pat)s
          )
      )
    ORDER BY data_empenho DESC NULLS LAST, id DESC
    LIMIT %(limit)s OFFSET %(offset)s
"""

EMPRESA_EMPENHOS_COUNT_GLOBAL = """
    SELECT COUNT(*)
    FROM tce_pb_despesa d
    WHERE d.cnpj_basico = %(cnpj_basico)s
      AND d.valor_pago > 0
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
      AND (%(data_inicio)s IS NULL OR data_empenho >= %(data_inicio)s::date)
      AND (%(data_fim)s IS NULL OR data_empenho <= %(data_fim)s::date)
      AND (
          %(q)s IS NULL OR (
              numero_empenho ILIKE %(q_pat)s
              OR elemento_despesa ILIKE %(q_pat)s
              OR COALESCE(historico, '') ILIKE %(q_pat)s
              OR COALESCE(modalidade_licitacao, '') ILIKE %(q_pat)s
              OR municipio ILIKE %(q_pat)s
          )
      )
"""

# Variantes para fornecedor (cpf_cnpj exato em vez de cnpj_basico) — o
# dialog de fornecedor em /cidade/ usa identidade exata pra evitar
# colisao CPF/CNPJ por prefixo de 8 digitos (ver cidade.py:1655).
EMPRESA_EMPENHOS_PAGINATED_BY_DOC_MUN = """
    SELECT id, numero_empenho, data_empenho, elemento_despesa,
           valor_empenhado, valor_pago,
           modalidade_licitacao, numero_licitacao
    FROM tce_pb_despesa
    WHERE cpf_cnpj = %(cpf_cnpj)s
      AND municipio = %(municipio)s
      AND valor_pago > 0
      AND (%(data_inicio)s IS NULL OR data_empenho >= %(data_inicio)s::date)
      AND (%(data_fim)s IS NULL OR data_empenho <= %(data_fim)s::date)
      AND (
          %(q)s IS NULL OR (
              numero_empenho ILIKE %(q_pat)s
              OR elemento_despesa ILIKE %(q_pat)s
              OR COALESCE(historico, '') ILIKE %(q_pat)s
              OR COALESCE(modalidade_licitacao, '') ILIKE %(q_pat)s
          )
      )
    ORDER BY data_empenho DESC NULLS LAST, id DESC
    LIMIT %(limit)s OFFSET %(offset)s
"""

EMPRESA_EMPENHOS_COUNT_BY_DOC_MUN = """
    SELECT COUNT(*)
    FROM tce_pb_despesa
    WHERE cpf_cnpj = %(cpf_cnpj)s
      AND municipio = %(municipio)s
      AND valor_pago > 0
      AND (%(data_inicio)s IS NULL OR data_empenho >= %(data_inicio)s::date)
      AND (%(data_fim)s IS NULL OR data_empenho <= %(data_fim)s::date)
      AND (
          %(q)s IS NULL OR (
              numero_empenho ILIKE %(q_pat)s
              OR elemento_despesa ILIKE %(q_pat)s
              OR COALESCE(historico, '') ILIKE %(q_pat)s
              OR COALESCE(modalidade_licitacao, '') ILIKE %(q_pat)s
          )
      )
"""

EMPRESA_STATS_BY_MUN = """
    SELECT COUNT(*) AS qtd_empenhos,
           COALESCE(SUM(valor_empenhado), 0) AS total_empenhado,
           COALESCE(SUM(valor_pago), 0) AS total_pago,
           MIN(data_empenho) AS primeiro_empenho,
           MAX(data_empenho) AS ultimo_empenho,
           COUNT(*) FILTER (
               WHERE numero_licitacao IS NULL
                  OR numero_licitacao = '000000000'
                  OR modalidade_licitacao ILIKE '%%sem licit%%'
           ) AS qtd_sem_licitacao
    FROM tce_pb_despesa d
    WHERE d.cnpj_basico = %(cnpj_basico)s
      AND d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
"""

EMPRESA_PAGAMENTOS_MENSAIS_BY_MUN = """
    SELECT TO_CHAR(data_empenho, 'YYYY-MM') AS mes,
           SUM(valor_pago) AS total_mes
    FROM tce_pb_despesa d
    WHERE d.cnpj_basico = %(cnpj_basico)s
      AND d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
      AND data_empenho >= (CURRENT_DATE - INTERVAL '12 months')
    GROUP BY TO_CHAR(data_empenho, 'YYYY-MM')
    ORDER BY mes
"""

EMPRESA_TOP_ELEMENTOS_BY_MUN = """
    SELECT elemento_despesa,
           SUM(valor_pago) AS total_elemento,
           COUNT(*) AS qtd
    FROM tce_pb_despesa d
    WHERE d.cnpj_basico = %(cnpj_basico)s
      AND d.municipio = %(municipio)s
      AND d.valor_pago > 0
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
    GROUP BY elemento_despesa
    ORDER BY SUM(valor_pago) DESC
    LIMIT 5
"""

# Pagamentos durante sancao em OUTROS municipios (excluindo o atual).
# Usado quando a empresa tem sancoes registradas para destacar
# pagamentos em municipios alheios durante o periodo da sancao.
#
# IMPORTANTE: usa EXISTS em vez de JOIN+UNION pra evitar inflar COUNT/SUM.
# Bug original (P0 do Opus 4.7 review do PR #62): JOIN com UNION ALL de
# CEIS+CNEP fazia produto cartesiano — empresa com 2 sancoes ativas via
# COUNT/SUM dobrados. Com EXISTS, cada despesa entra UMA vez se houver
# qualquer sancao cobrindo a data.
EMPRESA_PAGAMENTOS_SANCAO_OUTROS = """
    SELECT d.municipio, COUNT(*) AS qtd_empenhos,
           SUM(d.valor_pago) AS total_pago
    FROM tce_pb_despesa d
    WHERE d.cnpj_basico = %(cnpj_basico)s
      AND d.municipio != %(municipio_atual)s
      AND d.valor_pago > 0
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
      AND EXISTS (
          SELECT 1
          FROM ceis_sancao s
          WHERE LEFT(s.cpf_cnpj_norm, 8) = %(cnpj_basico)s
            AND s.tipo_pessoa = 'J'
            AND d.data_empenho >= s.dt_inicio_sancao
            AND (s.dt_final_sancao IS NULL
                 OR d.data_empenho <= s.dt_final_sancao)
          UNION ALL
          SELECT 1
          FROM cnep_sancao s
          WHERE LEFT(s.cpf_cnpj_norm, 8) = %(cnpj_basico)s
            AND s.tipo_pessoa = 'J'
            AND d.data_empenho >= s.dt_inicio_sancao
            AND (s.dt_final_sancao IS NULL
                 OR d.data_empenho <= s.dt_final_sancao)
      )
    GROUP BY d.municipio
    ORDER BY total_pago DESC
"""

# Visao global (sem filtro de municipio) das pagamentos mensais,
# usado pelo chart "monthly" da pagina /empresa/<cnpj>.
EMPRESA_PAGAMENTOS_MENSAIS_GLOBAL_BY_BASICO = """
    SELECT TO_CHAR(data_empenho, 'YYYY-MM') AS mes,
           SUM(valor_pago) AS total_mes
    FROM tce_pb_despesa d
    WHERE d.cnpj_basico = %s
      AND d.valor_pago > 0
      AND EXISTS (
          SELECT 1 FROM estabelecimento est
          WHERE est.cnpj_completo = d.cpf_cnpj
      )
      AND data_empenho >= (CURRENT_DATE - INTERVAL '12 months')
    GROUP BY TO_CHAR(data_empenho, 'YYYY-MM')
    ORDER BY mes
"""

# ─────────────────────────────────────────────────────────────────────────
# Sitemap: TODAS as empresas em mv_empresa_pb que tem matriz cadastrada
# em estabelecimento (cnpj_ordem='0001'). Sem filtro de threshold de
# valor/sancao/divida — qualquer empresa que apareceu em fonte PB merece
# pagina indexavel.
#
# JOIN com estabelecimento eh OBRIGATORIO pra gerar CNPJ completo
# (basico+ordem+dv). Empresas em mv_empresa_pb sem matriz cadastrada na
# RFB (~12K) nao podem ter pagina (compute_empresa_perfil_dict 404 nelas)
# entao tambem ficam fora do sitemap. Skip esperado.
#
# SEM LIMIT — sitemap-index permite indexar tudo via paginacao
# (web/routes/seo.py: /sitemap-empresas-{n}.xml com LIMIT 49000 OFFSET).
#
# Warmer (web/warm_cache.py:_get_qualifying_empresas) consume sem LIMIT
# pra cachear todas, preservando ORDER BY estavel pra paginacao bater
# entre warmer e routes.
# ─────────────────────────────────────────────────────────────────────────

EMPRESAS_QUALIFICADAS_PARA_SITEMAP = """
    SELECT
        COALESCE(NULLIF(epb.razao_social, ''), 'Empresa ' || epb.cnpj_basico) AS razao_social,
        est.cnpj_basico || est.cnpj_ordem || est.cnpj_dv AS cnpj_completo
    FROM mv_empresa_pb epb
    JOIN estabelecimento est
        ON est.cnpj_basico = epb.cnpj_basico
       AND est.cnpj_ordem = '0001'
    ORDER BY epb.total_pb_geral DESC NULLS LAST,
             epb.cnpj_basico
"""

# Variante paginada usada pelos shards do sitemap. Aceita LIMIT/OFFSET via
# params nomeados (psycopg2): %(limit)s / %(offset)s. Mesmo ORDER BY pra
# garantir que warmer e shards do sitemap processem o mesmo conjunto
# deterministicamente.
EMPRESAS_QUALIFICADAS_PAGINATED = """
    SELECT
        COALESCE(NULLIF(epb.razao_social, ''), 'Empresa ' || epb.cnpj_basico) AS razao_social,
        est.cnpj_basico || est.cnpj_ordem || est.cnpj_dv AS cnpj_completo
    FROM mv_empresa_pb epb
    JOIN estabelecimento est
        ON est.cnpj_basico = epb.cnpj_basico
       AND est.cnpj_ordem = '0001'
    ORDER BY epb.total_pb_geral DESC NULLS LAST,
             epb.cnpj_basico
    LIMIT %(limit)s OFFSET %(offset)s
"""

# Conta total (usado por sitemap-index pra calcular num_shards e por
# deploy.yml Enable step pra calcular coverage gate).
EMPRESAS_QUALIFICADAS_COUNT = """
    SELECT COUNT(*)
    FROM mv_empresa_pb epb
    JOIN estabelecimento est
        ON est.cnpj_basico = epb.cnpj_basico
       AND est.cnpj_ordem = '0001'
"""

# ─────────────────────────────────────────────────────────────────────────
# Sitemap empresa × municipio: pares (cnpj_completo, municipio_nome).
# Cada par vira uma URL /empresa/<cnpj>/<municipio_slug>. Como o
# warmer cobre todos os municipios pagantes de cada empresa, o sitemap
# aqui REUSA exatamente a mesma fonte (mv_empresa_pb + estabelecimento
# + tce_pb_despesa GROUP BY) para ficar 1:1 com o cache populado.
#
# ORDER BY total desc estabiliza paginacao (mesma posicao no warmer
# e nos shards do sitemap).
# ─────────────────────────────────────────────────────────────────────────

EMPRESAS_MUNICIPIOS_QUALIFICADAS_PAGINATED = """
    SELECT cnpj_completo, municipio, total_pago AS total
    FROM mv_empresa_municipio_pagantes
    ORDER BY total_pago DESC NULLS LAST, cnpj_completo, municipio
    LIMIT %(limit)s OFFSET %(offset)s
"""

EMPRESAS_MUNICIPIOS_QUALIFICADAS_COUNT = """
    SELECT COUNT(*) FROM mv_empresa_municipio_pagantes
"""

# Versao sem LIMIT, usada pelo warmer (single shot, processa todos
# os pares de uma vez). Mantem mesmo ORDER BY do paginated.
EMPRESAS_MUNICIPIOS_QUALIFICADAS_TODOS = """
    SELECT cnpj_completo, municipio
    FROM mv_empresa_municipio_pagantes
    ORDER BY total_pago DESC NULLS LAST, cnpj_completo, municipio
"""
