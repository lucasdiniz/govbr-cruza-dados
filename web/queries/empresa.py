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

EMPRESA_MUNICIPIOS_PAGANTES_BY_BASICO = """
    SELECT municipio,
           SUM(valor_pago) AS total_pago,
           COUNT(*) AS qtd_empenhos
    FROM tce_pb_despesa
    WHERE cnpj_basico = %s
      AND valor_pago > 0
    GROUP BY municipio
    ORDER BY total_pago DESC
"""

EMPRESA_TOP_ELEMENTOS_GLOBAL_BY_BASICO = """
    SELECT elemento_despesa,
           SUM(valor_pago) AS total_elemento,
           COUNT(*) AS qtd
    FROM tce_pb_despesa
    WHERE cnpj_basico = %s
      AND valor_pago > 0
    GROUP BY elemento_despesa
    ORDER BY SUM(valor_pago) DESC
    LIMIT 5
"""

# ─────────────────────────────────────────────────────────────────────────
# Sitemap: empresas qualificadas (heuristica de filtro pra evitar ruido).
# Inclui CNPJs com pagamentos PB relevantes (>= R$ 10k), em CEIS vigente
# ou com divida PGFN > 0. Retorna (razao_social, cnpj_completo) onde
# cnpj_completo = basico+ordem(0001)+dv da matriz.
#
# LIMIT 45000: protocolo sitemap.org permite ate 50.000 URLs por arquivo.
# Cidades (~223) + estaticas (5) + 45k empresas = ~45.2k, com folga ate
# o limite. Quando passarmos disso, implementar sitemap index com chunks
# (TODO: web/routes/seo.py — sitemap-empresas-1.xml etc).
# ─────────────────────────────────────────────────────────────────────────

EMPRESAS_QUALIFICADAS_PARA_SITEMAP = """
    SELECT
        COALESCE(NULLIF(epb.razao_social, ''), 'Empresa ' || epb.cnpj_basico) AS razao_social,
        est.cnpj_basico || est.cnpj_ordem || est.cnpj_dv AS cnpj_completo
    FROM mv_empresa_pb epb
    JOIN estabelecimento est
        ON est.cnpj_basico = epb.cnpj_basico
       AND est.cnpj_ordem = '0001'
    WHERE epb.total_pb_geral >= 10000
       OR epb.flag_ceis_vigente
       OR epb.total_divida_pgfn > 0
    ORDER BY epb.total_pb_geral DESC NULLS LAST,
             epb.cnpj_basico
    LIMIT 45000
"""
