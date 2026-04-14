"""Registry de queries para deep-dive por modo."""

from dataclasses import dataclass


@dataclass
class QueryDef:
    id: str
    title: str
    description: str
    category: str
    sql_count: str
    sql_full: str
    timeout_sec: int = 30


# ── Queries modo cidade ──────────────────────────────────────────
# Cada query recebe %(municipio)s como parametro

CIDADE_QUERIES: dict[str, QueryDef] = {}


def _reg(qid, title, desc, cat, sql_full, timeout=30):
    sql_count = f"SELECT COUNT(*) FROM ({sql_full}) _q"
    CIDADE_QUERIES[qid] = QueryDef(
        id=qid, title=title, description=desc, category=cat,
        sql_count=sql_count, sql_full=sql_full, timeout_sec=timeout,
    )


# ── Conflito de Interesses ───────────────────────────────────────

_reg("Q87", "Socio de contratada estadual e servidor municipal",
     "Servidor municipal que e socio de empresa com contrato estadual",
     "Conflito de Interesses",
     """
SELECT pc.nome_contratado, pc.cpfcnpj_contratado,
       pc.objeto_contrato, pc.valor_original,
       s.nome AS nome_socio, s.cpf_cnpj_norm AS cpf_socio_6dig,
       s.qualificacao,
       sv.municipio, sv.nome_servidor, sv.descricao_cargo,
       sv.salario
FROM pb_contrato pc
JOIN socio s ON s.cnpj_basico = pc.cnpj_basico AND s.tipo_socio = 2
JOIN (
    SELECT cpf_digitos_6, nome_upper, municipio, nome_servidor, descricao_cargo,
           MAX(valor_vantagem) AS salario
    FROM tce_pb_servidor
    WHERE ano_mes >= '2022-01'
      AND municipio = %(municipio)s
    GROUP BY cpf_digitos_6, nome_upper, municipio, nome_servidor, descricao_cargo
) sv ON sv.cpf_digitos_6 = s.cpf_cnpj_norm
    AND sv.nome_upper = UPPER(TRIM(s.nome))
WHERE pc.cnpj_basico IS NOT NULL
  AND s.cpf_cnpj_norm IS NOT NULL AND s.cpf_cnpj_norm != ''
ORDER BY pc.valor_original DESC
LIMIT 500
""", timeout=30)


_reg("Q88", "Servidor municipal que recebe pagamento estadual como PF",
     "Duplo vinculo: servidor em municipio e credor no governo estadual",
     "Conflito de Interesses",
     """
SELECT sv.municipio, sv.nome_servidor, sv.cpf_cnpj AS cpf_servidor,
       sv.descricao_cargo, sv.valor_vantagem AS salario,
       pp.nome_credor AS nome_credor_estado, pp.cpfcnpj_credor,
       SUM(pp.valor_pagamento) AS total_recebido_estado,
       COUNT(*) AS qtd_pagamentos_estado,
       pp.tipo_despesa
FROM tce_pb_servidor sv
JOIN pb_pagamento pp ON sv.cpf_digitos_6 = pp.cpf_digitos_6
    AND sv.nome_upper = pp.nome_upper
WHERE sv.cpf_digitos_6 IS NOT NULL AND sv.cpf_digitos_6 != ''
  AND pp.cpf_digitos_6 IS NOT NULL
  AND LENGTH(pp.cpfcnpj_credor) = 11
  AND sv.ano_mes >= '2024-01'
  AND sv.municipio = %(municipio)s
GROUP BY sv.municipio, sv.nome_servidor, sv.cpf_cnpj,
         sv.descricao_cargo, salario,
         pp.nome_credor, pp.cpfcnpj_credor, pp.tipo_despesa
HAVING SUM(pp.valor_pagamento) > 5000
ORDER BY total_recebido_estado DESC
LIMIT 500
""", timeout=30)


# ── Licitacao e Concorrencia ─────────────────────────────────────

_reg("Q60", "Fornecedor 'Sem Licitacao' em multiplos municipios",
     "Empresas que recebem sem licitacao em 5+ municipios PB",
     "Licitacao e Concorrencia",
     """
SELECT d.cpf_cnpj, d.nome_credor, e.razao_social,
       COUNT(DISTINCT d.municipio) AS qtd_municipios,
       ARRAY_AGG(DISTINCT d.municipio ORDER BY d.municipio) AS municipios,
       SUM(d.valor_pago) AS total_pago, COUNT(*) AS qtd_empenhos
FROM tce_pb_despesa d
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
    AND e.natureza_juridica NOT LIKE '1%%'
WHERE d.cnpj_basico IS NOT NULL
  AND d.modalidade_licitacao ILIKE '%%sem licit%%'
  AND d.valor_pago > 0
  AND d.municipio = %(municipio)s
GROUP BY d.cpf_cnpj, d.nome_credor, e.razao_social
ORDER BY total_pago DESC
LIMIT 500
""", timeout=30)


_reg("Q62", "Fornecedor vencedor em muitos municipios",
     "Empresa ganhando licitacoes em 10+ municipios PB",
     "Licitacao e Concorrencia",
     """
SELECT l.cpf_cnpj_proponente, l.nome_proponente, e.razao_social,
       COUNT(DISTINCT l.municipio) AS qtd_municipios,
       COUNT(DISTINCT l.numero_licitacao) AS qtd_licitacoes,
       SUM(l.valor_ofertado) AS total_ofertado
FROM tce_pb_licitacao l
JOIN empresa e ON e.cnpj_basico = l.cnpj_basico_proponente
WHERE l.cnpj_basico_proponente IS NOT NULL
  AND l.ano_licitacao >= 2022
  AND l.municipio = %(municipio)s
GROUP BY l.cpf_cnpj_proponente, l.nome_proponente, e.razao_social
ORDER BY total_ofertado DESC
LIMIT 500
""", timeout=30)


_reg("Q68", "Licitacao com proponente unico",
     "Licitacoes onde apenas 1 empresa participou — possivel direcionamento",
     "Licitacao e Concorrencia",
     """
SELECT l.municipio, l.numero_licitacao, l.ano_licitacao,
       l.modalidade, l.objeto_licitacao,
       l.nome_proponente, l.cpf_cnpj_proponente,
       l.valor_ofertado, l.situacao_proposta
FROM tce_pb_licitacao l
WHERE l.ano_licitacao >= 2022
  AND l.municipio = %(municipio)s
  AND l.numero_licitacao IN (
      SELECT l2.numero_licitacao
      FROM tce_pb_licitacao l2
      WHERE l2.municipio = %(municipio)s
        AND l2.ano_licitacao = l.ano_licitacao
      GROUP BY l2.numero_licitacao
      HAVING COUNT(DISTINCT l2.cpf_cnpj_proponente) = 1
  )
  AND l.valor_ofertado > 50000
ORDER BY l.valor_ofertado DESC
LIMIT 500
""", timeout=30)


_reg("Q71", "Fornecedores com mesmo endereco",
     "Empresas no mesmo endereco recebendo do municipio — possivel laranja",
     "Licitacao e Concorrencia",
     """
SELECT d.municipio,
       est.tipo_logradouro || ' ' || est.logradouro || ', ' || est.numero AS endereco,
       est.municipio AS municipio_empresa,
       COUNT(DISTINCT d.cnpj_basico) AS qtd_empresas,
       ARRAY_AGG(DISTINCT e.razao_social ORDER BY e.razao_social) AS empresas,
       SUM(d.valor_pago) AS total_pago
FROM tce_pb_despesa d
JOIN estabelecimento est ON est.cnpj_basico = d.cnpj_basico
    AND est.cnpj_ordem = '0001' AND est.situacao_cadastral = '2'
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
WHERE d.cnpj_basico IS NOT NULL AND d.valor_pago > 0
  AND d.ano >= 2022
  AND est.logradouro IS NOT NULL AND est.logradouro != ''
  AND est.numero IS NOT NULL AND est.numero != ''
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, est.tipo_logradouro, est.logradouro, est.numero, est.municipio
HAVING COUNT(DISTINCT d.cnpj_basico) >= 3
ORDER BY qtd_empresas DESC, total_pago DESC
LIMIT 500
""", timeout=30)


_reg("Q77", "Fracionamento de despesa",
     "Mesmo credor+elemento+mes com empenhos fracionados acima de R$50k",
     "Licitacao e Concorrencia",
     """
SELECT d.municipio, d.cpf_cnpj, d.nome_credor,
       d.elemento_despesa, d.ano, d.mes,
       COUNT(*) AS qtd_empenhos,
       SUM(d.valor_empenhado) AS total_empenhado,
       MAX(d.valor_empenhado) AS maior_empenho
FROM tce_pb_despesa d
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
    AND e.natureza_juridica NOT LIKE '1%%'
WHERE d.ano >= 2022 AND d.valor_empenhado > 0
  AND d.valor_empenhado < 50000
  AND d.cnpj_basico IS NOT NULL
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, d.cpf_cnpj, d.nome_credor, d.elemento_despesa, d.ano, d.mes
HAVING COUNT(*) >= 3 AND SUM(d.valor_empenhado) > 50000
ORDER BY total_empenhado DESC
LIMIT 500
""", timeout=45)


# ── Fornecedores Irregulares ─────────────────────────────────────

_reg("Q65", "Fornecedor sancionado (CEIS) recebendo",
     "Empresa com sancao ativa no CEIS recebendo pagamento do municipio",
     "Fornecedores Irregulares",
     """
SELECT cs.nome_sancionado, cs.cpf_cnpj_sancionado,
       cs.categoria_sancao, cs.dt_inicio_sancao, cs.dt_final_sancao,
       d.municipio, d.nome_credor,
       SUM(d.valor_pago) AS total_pago, COUNT(*) AS qtd_empenhos
FROM ceis_sancao cs
JOIN tce_pb_despesa d ON LEFT(cs.cpf_cnpj_sancionado, 8) = d.cnpj_basico
WHERE d.cnpj_basico IS NOT NULL
  AND d.data_empenho >= cs.dt_inicio_sancao
  AND (cs.dt_final_sancao IS NULL OR d.data_empenho <= cs.dt_final_sancao)
  AND d.valor_pago > 0
  AND d.municipio = %(municipio)s
GROUP BY cs.nome_sancionado, cs.cpf_cnpj_sancionado,
         cs.categoria_sancao, cs.dt_inicio_sancao, cs.dt_final_sancao,
         d.municipio, d.nome_credor
ORDER BY total_pago DESC
LIMIT 500
""", timeout=15)


_reg("Q67", "Fornecedor com divida PGFN recebendo",
     "Empresa com divida ativa na Uniao recebendo do municipio",
     "Fornecedores Irregulares",
     """
WITH desp AS (
    SELECT cnpj_basico, MAX(cpf_cnpj) AS cpf_cnpj, MAX(nome_credor) AS nome_credor,
           SUM(valor_pago) AS total_pago, COUNT(*) AS qtd_empenhos
    FROM tce_pb_despesa
    WHERE cnpj_basico IS NOT NULL AND valor_pago > 0 AND ano >= 2022
      AND municipio = %(municipio)s
    GROUP BY cnpj_basico
    HAVING SUM(valor_pago) > 50000
),
pgfn_agg AS (
    SELECT LEFT(cpf_cnpj_norm, 8) AS cnpj_basico,
           MAX(situacao_inscricao) AS situacao_inscricao,
           SUM(valor_consolidado) AS divida_pgfn
    FROM pgfn_divida
    WHERE LENGTH(cpf_cnpj_norm) = 14
      AND LEFT(cpf_cnpj_norm, 8) IN (SELECT cnpj_basico FROM desp)
    GROUP BY LEFT(cpf_cnpj_norm, 8)
)
SELECT d.cpf_cnpj, d.nome_credor, %(municipio)s AS municipio,
       pg.situacao_inscricao,
       pg.divida_pgfn,
       d.total_pago, d.qtd_empenhos
FROM desp d
JOIN pgfn_agg pg ON pg.cnpj_basico = d.cnpj_basico
ORDER BY pg.divida_pgfn DESC
LIMIT 500
""", timeout=90)


_reg("Q70", "Empresa inativa recebendo pagamento",
     "Empresa com situacao cadastral diferente de ativa na RFB recebendo do municipio",
     "Fornecedores Irregulares",
     """
SELECT d.municipio, d.cpf_cnpj, d.nome_credor,
       CASE est.situacao_cadastral
           WHEN '1' THEN 'Nula' WHEN '3' THEN 'Suspensa'
           WHEN '4' THEN 'Inapta' WHEN '8' THEN 'Baixada'
           ELSE 'Sit. ' || est.situacao_cadastral
       END AS desc_situacao,
       est.dt_situacao, e.razao_social,
       SUM(d.valor_pago) AS total_pago, COUNT(*) AS qtd_empenhos
FROM tce_pb_despesa d
JOIN estabelecimento est ON est.cnpj_basico = d.cnpj_basico
    AND est.cnpj_ordem = '0001' AND est.situacao_cadastral != '2'
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
WHERE d.cnpj_basico IS NOT NULL AND d.valor_pago > 0
  AND d.data_empenho > est.dt_situacao
  AND LENGTH(REPLACE(d.cpf_cnpj, '.', '')) >= 14
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, d.cpf_cnpj, d.nome_credor,
         est.situacao_cadastral, est.dt_situacao, e.razao_social
HAVING SUM(d.valor_pago) > 10000
ORDER BY total_pago DESC
LIMIT 500
""", timeout=15)


# ── Orcamento e Financeiro ───────────────────────────────────────

_reg("Q61", "Divergencia empenhado vs pago",
     "Credores com valor pago muito menor que empenhado no municipio",
     "Orcamento e Financeiro",
     """
SELECT d.municipio, d.cpf_cnpj, d.nome_credor,
       COUNT(*) AS qtd_empenhos,
       SUM(d.valor_empenhado) AS total_empenhado,
       SUM(d.valor_pago) AS total_pago,
       SUM(d.valor_empenhado) - SUM(d.valor_pago) AS diferenca,
       ROUND((1 - SUM(d.valor_pago) / NULLIF(SUM(d.valor_empenhado), 0)) * 100, 1) AS pct_nao_pago
FROM tce_pb_despesa d
WHERE d.valor_empenhado > 10000 AND d.valor_pago > 0
  AND d.valor_pago < d.valor_empenhado * 0.5
  AND d.ano >= 2022
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, d.cpf_cnpj, d.nome_credor
HAVING SUM(d.valor_empenhado) > 100000
ORDER BY diferenca DESC
LIMIT 500
""", timeout=15)


_reg("Q66", "Empenhos concentrados em dezembro",
     "Queima de orcamento: proporcao anormal de despesas em dezembro",
     "Orcamento e Financeiro",
     """
SELECT d.municipio, d.ano,
       SUM(d.valor_empenhado) AS total_empenhado_ano,
       SUM(d.valor_empenhado) FILTER (WHERE d.mes = '12') AS empenhado_dezembro,
       ROUND(SUM(d.valor_empenhado) FILTER (WHERE d.mes = '12') * 100.0
             / NULLIF(SUM(d.valor_empenhado), 0), 1) AS pct_dezembro,
       COUNT(*) FILTER (WHERE d.mes = '12') AS qtd_empenhos_dez
FROM tce_pb_despesa d
WHERE d.ano >= 2022 AND d.valor_empenhado > 0
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, d.ano
HAVING SUM(d.valor_empenhado) > 1000000
   AND SUM(d.valor_empenhado) FILTER (WHERE d.mes = '12') * 100.0
       / NULLIF(SUM(d.valor_empenhado), 0) > 30
ORDER BY pct_dezembro DESC
LIMIT 500
""", timeout=15)


_reg("Q64", "Despesa TCE-PB x contrato PNCP divergente",
     "Discrepancia > 25%% entre valor contratado PNCP e valor pago TCE-PB",
     "Orcamento e Financeiro",
     """
SELECT d.municipio,
       pc.orgao_razao_social, pc.cnpj_orgao,
       pc.nome_fornecedor, pc.objeto,
       pc.valor_global AS valor_contrato_pncp,
       SUM(d.valor_pago) AS total_pago_tce,
       SUM(d.valor_pago) - pc.valor_global AS diferenca
FROM pncp_contrato pc
JOIN tce_pb_despesa d ON d.cnpj_basico = pc.cnpj_basico_fornecedor
    AND d.codigo_ug = pc.cnpj_orgao
WHERE pc.uf = 'PB' AND pc.valor_global > 50000 AND d.ano >= 2022
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, pc.orgao_razao_social, pc.cnpj_orgao,
         pc.nome_fornecedor, pc.objeto, pc.valor_global
HAVING ABS(SUM(d.valor_pago) - pc.valor_global) > pc.valor_global * 0.25
ORDER BY ABS(SUM(d.valor_pago) - pc.valor_global) DESC
LIMIT 500
""", timeout=30)


# ── Politico-Eleitoral ──────────────────────────────────────────

_reg("Q72", "Doador de campanha recebendo do municipio",
     "Empresa doou para prefeito eleito e depois recebeu pagamento municipal",
     "Politico-Eleitoral",
     """
SELECT tc.nm_candidato AS prefeito, d.municipio,
       tr.nm_doador, tr.cpf_cnpj_doador AS cnpj_doador,
       tr.vr_receita AS valor_doacao,
       SUM(d.valor_pago) AS total_recebido, COUNT(*) AS qtd_empenhos
FROM tse_candidato tc
JOIN tse_receita_candidato tr ON tr.sq_candidato = tc.sq_candidato
    AND tr.cpf_cnpj_doador IS NOT NULL AND LENGTH(tr.cpf_cnpj_doador) >= 14
JOIN tce_pb_despesa d ON d.cnpj_basico = LEFT(REGEXP_REPLACE(tr.cpf_cnpj_doador, '[^0-9]', '', 'g'), 8)
WHERE tc.ds_cargo = 'PREFEITO'
  AND tc.ds_sit_tot_turno IN ('ELEITO', 'ELEITO POR MEDIA', 'ELEITO POR QP')
  AND tc.sg_uf = 'PB'
  AND UPPER(TRIM(d.municipio)) = UPPER(TRIM(tc.nm_ue))
  AND d.ano >= CAST(tc.ano_eleicao AS INT)
  AND d.valor_pago > 0
  AND d.municipio = %(municipio)s
GROUP BY tc.nm_candidato, d.municipio, tr.nm_doador, tr.cpf_cnpj_doador, tr.vr_receita
ORDER BY total_recebido DESC
LIMIT 500
""", timeout=45)


# ── Cruzamento Estado x Municipio ────────────────────────────────

_reg("Q83", "Empresa dominante estado + municipio",
     "Empresa que recebe do estado E de municipios PB",
     "Cruzamento Estado x Municipio",
     """
WITH pb_agg AS (
    SELECT cnpj_basico, SUM(valor_empenho) AS total_estado, COUNT(*) AS qtd_estado
    FROM pb_empenho WHERE cnpj_basico IS NOT NULL
    GROUP BY cnpj_basico HAVING SUM(valor_empenho) > 100000
),
tce_agg AS (
    SELECT cnpj_basico, SUM(valor_pago) AS total_municipal, COUNT(*) AS qtd_municipal
    FROM tce_pb_despesa
    WHERE cnpj_basico IS NOT NULL AND valor_pago > 0
      AND municipio = %(municipio)s
    GROUP BY cnpj_basico HAVING SUM(valor_pago) > 10000
)
SELECT e.razao_social, e.cnpj_basico,
       pb.total_estado, tce.total_municipal,
       pb.total_estado + tce.total_municipal AS total_combinado
FROM pb_agg pb
JOIN tce_agg tce ON tce.cnpj_basico = pb.cnpj_basico
JOIN empresa e ON e.cnpj_basico = pb.cnpj_basico
ORDER BY total_combinado DESC
LIMIT 500
""", timeout=45)


_reg("Q89", "Convenio estado com despesas suspeitas",
     "Municipio recebeu convenio estadual e teve despesas atipicas no periodo",
     "Cruzamento Estado x Municipio",
     """
SELECT cv.cnpj_basico, cv.nome_convenente, cv.objetivo_convenio,
       cv.valor_concedente, cv.valor_contrapartida,
       cv.data_celebracao_convenio, cv.data_termino_vigencia,
       tce_agg.total_empenhado_periodo, tce_agg.qtd_empenhos
FROM pb_convenio cv
JOIN LATERAL (
    SELECT SUM(d.valor_empenhado) AS total_empenhado_periodo,
           COUNT(*) AS qtd_empenhos
    FROM tce_pb_despesa d
    WHERE d.municipio = %(municipio)s
      AND d.data_empenho BETWEEN cv.data_celebracao_convenio
          AND COALESCE(cv.data_termino_vigencia, cv.data_celebracao_convenio + INTERVAL '1 year')
      AND d.valor_empenhado > 0
) tce_agg ON tce_agg.total_empenhado_periodo > cv.valor_concedente * 0.5
WHERE cv.valor_concedente > 100000
  AND UPPER(unaccent(cv.nome_municipio)) = UPPER(unaccent(%(municipio)s))
ORDER BY tce_agg.total_empenhado_periodo DESC
LIMIT 500
""", timeout=90)


def get_categories() -> list[tuple[str, list[QueryDef]]]:
    """Retorna queries agrupadas por categoria."""
    cats: dict[str, list[QueryDef]] = {}
    for q in CIDADE_QUERIES.values():
        cats.setdefault(q.category, []).append(q)
    return list(cats.items())
