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
    sql_full_dated: str = ""
    timeout_sec: int = 30
    title_lay: str = ""
    description_lay: str = ""
    explainer_lay: str = ""


# ── Queries modo cidade ──────────────────────────────────────────
# Cada query recebe %(municipio)s como parametro.
# Variantes _dated recebem tambem %(data_inicio)s, %(data_fim)s,
# %(ano_inicio)s, %(ano_fim)s, %(ano_mes_inicio)s, %(ano_mes_fim)s.

CIDADE_QUERIES: dict[str, QueryDef] = {}


# ── Traducoes leigas das queries ─────────────────────────────────
# Versoes para o Modo Cidadao. Quando vazio, mostra o titulo tecnico.
_LAY_TEXT: dict[str, dict[str, str]] = {
    "Q65": {
        "title": "Empresas proibidas de contratar que receberam da prefeitura",
        "desc": "Empresas com sancao ativa do governo federal (CEIS, CNEP ou Inidoneidade) — por fraude, descumprimento contratual, documentacao irregular ou corrupcao. Esta cidade pagou a elas mesmo assim.",
        "explainer": (
            "CEIS, CNEP e Inidoneidade sao listas oficiais de empresas com sancoes ativas. Os motivos variam: fraude em licitacao, descumprimento de contrato, nao apresentar documentos, corrupcao (CNEP), entre outros — nem toda sancao e por fraude. "
            "Quando a prefeitura paga uma empresa dessas durante a vigencia da punicao, e um indicio de falha de controle (ou, em casos extremos, conluio). "
            "Ao investigar, compare as datas: pagamentos feitos depois do inicio da sancao sao os mais graves. Inidoneidade tem bloqueio nacional; Impedimento CEIS costuma ser restrito ao ente sancionador."
        ),
    },
    "Q67": {
        "title": "Empresas devendo impostos federais que receberam da prefeitura",
        "desc": "Empresas com divida ativa na Uniao (inscritas na PGFN) recebendo dinheiro publico municipal.",
        "explainer": (
            "A PGFN (Procuradoria-Geral da Fazenda Nacional) mantem o cadastro de empresas com dividas de impostos federais ja inscritas em divida ativa — ou seja, o governo ja cobrou e nao foi pago. "
            "Pela Lei 14.133/2021 e pela antiga 8.666/93, contratar essas empresas so e permitido se elas apresentarem certidao negativa ou tiverem suas dividas parceladas/suspensas. "
            "Volumes altos pagos a devedores cronicos podem indicar certidoes falsas, favorecimento, ou controle fragil."
        ),
    },
    "Q70": {
        "title": "Empresas fechadas ou inaptas que continuaram recebendo",
        "desc": "Empresas com situacao irregular na Receita Federal (suspensas, inaptas ou baixadas) que mesmo assim receberam pagamentos da prefeitura.",
        "explainer": (
            "Toda empresa tem um status na Receita Federal: Ativa, Suspensa, Inapta ou Baixada. "
            "Contratar e pagar uma empresa Suspensa, Inapta ou Baixada e irregular — a empresa pode nem existir mais de verdade, ou estar bloqueada por irregularidade fiscal. "
            "E um indicio classico de uso de empresas 'fantasmas' ou 'de fachada' para escoar dinheiro publico sem entregar servico de fato."
        ),
    },
    "Q69": {
        "title": "Todas as licitacoes do municipio",
        "desc": "Lista completa das licitacoes realizadas pela prefeitura, com valor, tipo e quantos fornecedores participaram.",
        "explainer": (
            "Licitacao e o processo que a lei exige para o governo comprar — ela traz concorrencia, que reduz o preco. "
            "Olhe com mais atencao para as modalidades 'Dispensa' e 'Inexigibilidade' (compras sem concorrencia) e para licitacoes com so 1 participante. "
            "Se a maioria dos contratos de um orgao foi feita sem disputa, ha risco elevado de direcionamento."
        ),
    },
    "Q71": {
        "title": "Fornecedores que compartilham o mesmo endereco",
        "desc": "Empresas diferentes registradas no mesmo endereco que receberam da prefeitura. Pode ser coincidencia — ou indicio de empresas 'fantasmas' ligadas entre si.",
        "explainer": (
            "Varias empresas com o mesmo endereco (CEP + logradouro + numero) podem ser coincidencia (um predio comercial, um shopping) — ou indicio de empresas criadas pelo mesmo grupo para simular concorrencia em licitacoes. "
            "O padrao suspeito e: 3 empresas do mesmo dono se inscrevem no mesmo pregao, dao propostas combinadas, e a 'escolhida' vence com preco artificialmente alto — o que caracteriza fraude a licitacao. "
            "Cruze com socios em comum e com datas de abertura proximas para confirmar."
        ),
    },
    "Q77": {
        "title": "Compras fatiadas (fracionamento de despesa)",
        "desc": "Varios contratos pequenos com o mesmo fornecedor logo em sequencia. Pode ser pratica para evitar licitacao — cada compra fica abaixo do limite legal.",
        "explainer": (
            "A lei obriga licitacao acima de certos valores (hoje, cerca de R$ 59 mil para compras em geral). "
            "Dividir uma compra grande em varias pequenas do mesmo fornecedor, em curto intervalo de tempo, para ficar abaixo desse limite e contratar por Dispensa, e crime de fraude a licitacao (art. 337-I, CP). "
            "Sinais: mesmo fornecedor, mesmo objeto, valores logo abaixo do limite, contratos muito proximos no tempo."
        ),
    },
    "Q61": {
        "title": "Diferenca entre o que foi prometido e o que foi pago",
        "desc": "Contratos em que a prefeitura reservou (empenhou) muito mais do que efetivamente pagou. Investigar se ha entrega, atraso ou cancelamento.",
        "explainer": (
            "Empenho e a reserva do dinheiro no orcamento; pago e o que realmente saiu do cofre. Empenhar muito e pagar pouco pode ter causa legitima (cancelamento, reducao de escopo, atraso). "
            "Mas tambem pode indicar servico ou obra nao entregue, contrato superestimado, ou cancelamento sem devolucao do recurso. "
            "Grandes divergencias em contratos de obras costumam ser sinal de problema na execucao."
        ),
    },
}


def _reg(qid, title, desc, cat, sql_full, timeout=30, sql_dated=None, title_lay="", desc_lay=""):
    sql_count = f"SELECT COUNT(*) FROM ({sql_full}) _q"
    lay = _LAY_TEXT.get(qid, {})
    CIDADE_QUERIES[qid] = QueryDef(
        id=qid, title=title, description=desc, category=cat,
        sql_count=sql_count, sql_full=sql_full,
        sql_full_dated=sql_dated or "",
        timeout_sec=timeout,
        title_lay=title_lay or lay.get("title", ""),
        description_lay=desc_lay or lay.get("desc", ""),
        explainer_lay=lay.get("explainer", ""),
    )


def _skip(*_args, **_kwargs):
    """No-op: query desativada temporariamente."""
    pass


# ── Fornecedores Irregulares ─────────────────────────────────────

_reg("Q65", "Fornecedor sancionado (CEIS/CNEP) recebendo",
     "Empresas que receberam pagamentos durante periodo de sancao vigente. Inclui abrangencia da sancao: Inidoneidade tem bloqueio nacional, Impedimento eh restrito ao ente sancionador.",
     "Fornecedores Irregulares",
     """
SELECT san.nome_sancionado, san.cpf_cnpj_sancionado,
       san.categoria_sancao, san.origem,
       CASE
           WHEN san.categoria_sancao ILIKE '%%inidone%%' THEN 'Nacional (Inidoneidade)'
           WHEN san.abrangencia = 'Todas as Esferas em todos os Poderes' THEN san.abrangencia
           ELSE COALESCE(san.abrangencia, 'Sem Informação')
                || ' (' || COALESCE(san.orgao, '?')
                || COALESCE(' - ' || san.uf, '') || ')'
       END AS abrangencia,
       san.dt_inicio_sancao, san.dt_final_sancao,
       d.municipio, d.nome_credor,
       SUM(d.valor_pago) AS total_pago, COUNT(*) AS qtd_empenhos
FROM (
    SELECT nome_sancionado, cpf_cnpj_sancionado, categoria_sancao,
           dt_inicio_sancao, dt_final_sancao, 'CEIS' AS origem,
           esfera_orgao_sancionador AS esfera,
           orgao_sancionador AS orgao, uf_orgao_sancionador AS uf,
           abrangencia_sancao AS abrangencia
    FROM ceis_sancao
    UNION ALL
    SELECT nome_sancionado, cpf_cnpj_sancionado, categoria_sancao,
           dt_inicio_sancao, dt_final_sancao, 'CNEP' AS origem,
           esfera_orgao_sancionador AS esfera,
           orgao_sancionador AS orgao, uf_orgao_sancionador AS uf,
           abrangencia_sancao AS abrangencia
    FROM cnep_sancao
) san
JOIN tce_pb_despesa d ON LEFT(san.cpf_cnpj_sancionado, 8) = d.cnpj_basico
    AND EXISTS (SELECT 1 FROM estabelecimento est WHERE est.cnpj_completo = d.cpf_cnpj)
WHERE d.cnpj_basico IS NOT NULL
  AND d.data_empenho >= san.dt_inicio_sancao
  AND (san.dt_final_sancao IS NULL OR d.data_empenho <= san.dt_final_sancao)
  AND d.valor_pago > 0
  AND d.municipio = %(municipio)s
GROUP BY san.nome_sancionado, san.cpf_cnpj_sancionado,
         san.categoria_sancao, san.origem,
         san.abrangencia, san.orgao, san.uf,
         san.dt_inicio_sancao, san.dt_final_sancao,
         d.municipio, d.nome_credor
ORDER BY CASE
    WHEN san.categoria_sancao ILIKE '%%inidone%%' THEN 1
    WHEN san.abrangencia = 'Todas as Esferas em todos os Poderes' THEN 1
    ELSE 2
END, total_pago DESC
LIMIT 500
""", timeout=90, sql_dated="""
SELECT san.nome_sancionado, san.cpf_cnpj_sancionado,
       san.categoria_sancao, san.origem,
       CASE
           WHEN san.categoria_sancao ILIKE '%%inidone%%' THEN 'Nacional (Inidoneidade)'
           WHEN san.abrangencia = 'Todas as Esferas em todos os Poderes' THEN san.abrangencia
           ELSE COALESCE(san.abrangencia, 'Sem Informação')
                || ' (' || COALESCE(san.orgao, '?')
                || COALESCE(' - ' || san.uf, '') || ')'
       END AS abrangencia,
       san.dt_inicio_sancao, san.dt_final_sancao,
       d.municipio, d.nome_credor,
       SUM(d.valor_pago) AS total_pago, COUNT(*) AS qtd_empenhos
FROM (
    SELECT nome_sancionado, cpf_cnpj_sancionado, categoria_sancao,
           dt_inicio_sancao, dt_final_sancao, 'CEIS' AS origem,
           esfera_orgao_sancionador AS esfera,
           orgao_sancionador AS orgao, uf_orgao_sancionador AS uf,
           abrangencia_sancao AS abrangencia
    FROM ceis_sancao
    UNION ALL
    SELECT nome_sancionado, cpf_cnpj_sancionado, categoria_sancao,
           dt_inicio_sancao, dt_final_sancao, 'CNEP' AS origem,
           esfera_orgao_sancionador AS esfera,
           orgao_sancionador AS orgao, uf_orgao_sancionador AS uf,
           abrangencia_sancao AS abrangencia
    FROM cnep_sancao
) san
JOIN tce_pb_despesa d ON LEFT(san.cpf_cnpj_sancionado, 8) = d.cnpj_basico
    AND EXISTS (SELECT 1 FROM estabelecimento est WHERE est.cnpj_completo = d.cpf_cnpj)
WHERE d.cnpj_basico IS NOT NULL
  AND d.data_empenho >= san.dt_inicio_sancao
  AND (san.dt_final_sancao IS NULL OR d.data_empenho <= san.dt_final_sancao)
  AND d.valor_pago > 0
  AND d.municipio = %(municipio)s
  AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
GROUP BY san.nome_sancionado, san.cpf_cnpj_sancionado,
         san.categoria_sancao, san.origem,
         san.abrangencia, san.orgao, san.uf,
         san.dt_inicio_sancao, san.dt_final_sancao,
         d.municipio, d.nome_credor
ORDER BY CASE
    WHEN san.categoria_sancao ILIKE '%%inidone%%' THEN 1
    WHEN san.abrangencia = 'Todas as Esferas em todos os Poderes' THEN 1
    ELSE 2
END, total_pago DESC
LIMIT 500
""")


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
""", timeout=90, sql_dated="""
WITH desp AS (
    SELECT cnpj_basico, MAX(cpf_cnpj) AS cpf_cnpj, MAX(nome_credor) AS nome_credor,
           SUM(valor_pago) AS total_pago, COUNT(*) AS qtd_empenhos
    FROM tce_pb_despesa
    WHERE cnpj_basico IS NOT NULL AND valor_pago > 0
      AND data_empenho >= %(data_inicio)s AND data_empenho <= %(data_fim)s
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
""")


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
  AND EXISTS (SELECT 1 FROM estabelecimento est2 WHERE est2.cnpj_completo = d.cpf_cnpj)
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, d.cpf_cnpj, d.nome_credor,
         est.situacao_cadastral, est.dt_situacao, e.razao_social
HAVING SUM(d.valor_pago) > 10000
ORDER BY total_pago DESC
LIMIT 500
""", timeout=15, sql_dated="""
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
  AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
  AND LENGTH(REPLACE(d.cpf_cnpj, '.', '')) >= 14
  AND EXISTS (SELECT 1 FROM estabelecimento est2 WHERE est2.cnpj_completo = d.cpf_cnpj)
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, d.cpf_cnpj, d.nome_credor,
         est.situacao_cadastral, est.dt_situacao, e.razao_social
HAVING SUM(d.valor_pago) > 10000
ORDER BY total_pago DESC
LIMIT 500
""")


# ── Conflito de Interesses ───────────────────────────────────────

# DISABLED: 0 municipios com resultado no web_cache
_skip("Q87", "Socio de contratada estadual e servidor municipal",
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
""", timeout=30, sql_dated="""
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
    WHERE ano_mes >= %(ano_mes_inicio)s AND ano_mes <= %(ano_mes_fim)s
      AND municipio = %(municipio)s
    GROUP BY cpf_digitos_6, nome_upper, municipio, nome_servidor, descricao_cargo
) sv ON sv.cpf_digitos_6 = s.cpf_cnpj_norm
    AND sv.nome_upper = UPPER(TRIM(s.nome))
WHERE pc.cnpj_basico IS NOT NULL
  AND s.cpf_cnpj_norm IS NOT NULL AND s.cpf_cnpj_norm != ''
ORDER BY pc.valor_original DESC
LIMIT 500
""")


# DISABLED: 1 municipio com resultado no web_cache
_skip("Q88", "Servidor municipal que recebe pagamento estadual como PF",
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
""", timeout=30, sql_dated="""
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
  AND sv.ano_mes >= %(ano_mes_inicio)s AND sv.ano_mes <= %(ano_mes_fim)s
  AND sv.municipio = %(municipio)s
GROUP BY sv.municipio, sv.nome_servidor, sv.cpf_cnpj,
         sv.descricao_cargo, salario,
         pp.nome_credor, pp.cpfcnpj_credor, pp.tipo_despesa
HAVING SUM(pp.valor_pagamento) > 5000
ORDER BY total_recebido_estado DESC
LIMIT 500
""")


# ── Politico-Eleitoral ──────────────────────────────────────────

# DISABLED: 0 municipios com resultado no web_cache
_skip("Q72", "Doador de campanha recebendo do municipio",
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
    AND EXISTS (SELECT 1 FROM estabelecimento est WHERE est.cnpj_completo = d.cpf_cnpj)
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
""", timeout=45, sql_dated="""
SELECT tc.nm_candidato AS prefeito, d.municipio,
       tr.nm_doador, tr.cpf_cnpj_doador AS cnpj_doador,
       tr.vr_receita AS valor_doacao,
       SUM(d.valor_pago) AS total_recebido, COUNT(*) AS qtd_empenhos
FROM tse_candidato tc
JOIN tse_receita_candidato tr ON tr.sq_candidato = tc.sq_candidato
    AND tr.cpf_cnpj_doador IS NOT NULL AND LENGTH(tr.cpf_cnpj_doador) >= 14
JOIN tce_pb_despesa d ON d.cnpj_basico = LEFT(REGEXP_REPLACE(tr.cpf_cnpj_doador, '[^0-9]', '', 'g'), 8)
    AND EXISTS (SELECT 1 FROM estabelecimento est WHERE est.cnpj_completo = d.cpf_cnpj)
WHERE tc.ds_cargo = 'PREFEITO'
  AND tc.ds_sit_tot_turno IN ('ELEITO', 'ELEITO POR MEDIA', 'ELEITO POR QP')
  AND tc.sg_uf = 'PB'
  AND UPPER(TRIM(d.municipio)) = UPPER(TRIM(tc.nm_ue))
  AND d.ano >= CAST(tc.ano_eleicao AS INT)
  AND d.valor_pago > 0
  AND d.municipio = %(municipio)s
  AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
GROUP BY tc.nm_candidato, d.municipio, tr.nm_doador, tr.cpf_cnpj_doador, tr.vr_receita
ORDER BY total_recebido DESC
LIMIT 500
""")


# ── Licitacao e Concorrencia ─────────────────────────────────────

# DISABLED: pertence a view estadual, sempre QTD_MUNICIPIOS=1
_skip("Q60", "Fornecedor 'Sem Licitacao' em multiplos municipios",
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
""", timeout=30, sql_dated="""
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
  AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
GROUP BY d.cpf_cnpj, d.nome_credor, e.razao_social
ORDER BY total_pago DESC
LIMIT 500
""")


# DISABLED: pertence a view estadual, sempre QTD_MUNICIPIOS=1
_skip("Q62", "Fornecedor vencedor em muitos municipios",
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
""", timeout=30, sql_dated="""
SELECT l.cpf_cnpj_proponente, l.nome_proponente, e.razao_social,
       COUNT(DISTINCT l.municipio) AS qtd_municipios,
       COUNT(DISTINCT l.numero_licitacao) AS qtd_licitacoes,
       SUM(l.valor_ofertado) AS total_ofertado
FROM tce_pb_licitacao l
JOIN empresa e ON e.cnpj_basico = l.cnpj_basico_proponente
WHERE l.cnpj_basico_proponente IS NOT NULL
  AND l.ano_licitacao >= %(ano_inicio)s AND l.ano_licitacao <= %(ano_fim)s
  AND l.municipio = %(municipio)s
GROUP BY l.cpf_cnpj_proponente, l.nome_proponente, e.razao_social
ORDER BY total_ofertado DESC
LIMIT 500
""")


_skip("Q68", "Licitacao com proponente unico",
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
""", timeout=30, sql_dated="""
SELECT l.municipio, l.numero_licitacao, l.ano_licitacao,
       l.modalidade, l.objeto_licitacao,
       l.nome_proponente, l.cpf_cnpj_proponente,
       l.valor_ofertado, l.situacao_proposta
FROM tce_pb_licitacao l
WHERE l.ano_licitacao >= %(ano_inicio)s AND l.ano_licitacao <= %(ano_fim)s
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
""")


_reg("Q69", "Todas as licitacoes do municipio",
     "Lista completa de licitacoes registradas com quantidade de vencedores e maior valor ofertado",
     "Licitacao e Concorrencia",
     """
SELECT l.numero_licitacao, l.ano_licitacao,
       l.modalidade,
       MAX(l.objeto_licitacao) AS objeto_licitacao,
       COUNT(DISTINCT l.cpf_cnpj_proponente) AS qtd_vencedores,
       MAX(l.valor_ofertado) AS maior_valor,
       MAX(l.data_homologacao) AS data_homologacao
FROM tce_pb_licitacao l
WHERE l.ano_licitacao >= 2022
  AND l.municipio = %(municipio)s
GROUP BY l.numero_licitacao, l.ano_licitacao, l.modalidade
ORDER BY l.ano_licitacao DESC, MAX(l.valor_ofertado) DESC
LIMIT 500
""", timeout=30, sql_dated="""
SELECT l.numero_licitacao, l.ano_licitacao,
       l.modalidade,
       MAX(l.objeto_licitacao) AS objeto_licitacao,
       COUNT(DISTINCT l.cpf_cnpj_proponente) AS qtd_vencedores,
       MAX(l.valor_ofertado) AS maior_valor,
       MAX(l.data_homologacao) AS data_homologacao
FROM tce_pb_licitacao l
WHERE l.ano_licitacao >= %(ano_inicio)s AND l.ano_licitacao <= %(ano_fim)s
  AND l.municipio = %(municipio)s
GROUP BY l.numero_licitacao, l.ano_licitacao, l.modalidade
ORDER BY l.ano_licitacao DESC, MAX(l.valor_ofertado) DESC
LIMIT 500
""")


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
  AND EXISTS (SELECT 1 FROM estabelecimento est2 WHERE est2.cnpj_completo = d.cpf_cnpj)
  AND est.logradouro IS NOT NULL AND est.logradouro != ''
  AND est.numero IS NOT NULL AND est.numero != ''
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, est.tipo_logradouro, est.logradouro, est.numero, est.municipio
HAVING COUNT(DISTINCT d.cnpj_basico) >= 3
ORDER BY qtd_empresas DESC, total_pago DESC
LIMIT 500
""", timeout=30, sql_dated="""
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
  AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
  AND EXISTS (SELECT 1 FROM estabelecimento est2 WHERE est2.cnpj_completo = d.cpf_cnpj)
  AND est.logradouro IS NOT NULL AND est.logradouro != ''
  AND est.numero IS NOT NULL AND est.numero != ''
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, est.tipo_logradouro, est.logradouro, est.numero, est.municipio
HAVING COUNT(DISTINCT d.cnpj_basico) >= 3
ORDER BY qtd_empresas DESC, total_pago DESC
LIMIT 500
""")


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
  AND EXISTS (SELECT 1 FROM estabelecimento est WHERE est.cnpj_completo = d.cpf_cnpj)
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, d.cpf_cnpj, d.nome_credor, d.elemento_despesa, d.ano, d.mes
HAVING COUNT(*) >= 3 AND SUM(d.valor_empenhado) > 50000
ORDER BY total_empenhado DESC
LIMIT 500
""", timeout=45, sql_dated="""
SELECT d.municipio, d.cpf_cnpj, d.nome_credor,
       d.elemento_despesa, d.ano, d.mes,
       COUNT(*) AS qtd_empenhos,
       SUM(d.valor_empenhado) AS total_empenhado,
       MAX(d.valor_empenhado) AS maior_empenho
FROM tce_pb_despesa d
JOIN empresa e ON e.cnpj_basico = d.cnpj_basico
    AND e.natureza_juridica NOT LIKE '1%%'
WHERE d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
  AND d.valor_empenhado > 0
  AND d.valor_empenhado < 50000
  AND d.cnpj_basico IS NOT NULL
  AND EXISTS (SELECT 1 FROM estabelecimento est WHERE est.cnpj_completo = d.cpf_cnpj)
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, d.cpf_cnpj, d.nome_credor, d.elemento_despesa, d.ano, d.mes
HAVING COUNT(*) >= 3 AND SUM(d.valor_empenhado) > 50000
ORDER BY total_empenhado DESC
LIMIT 500
""")


# ── Cruzamento Estado x Municipio ────────────────────────────────

_skip("Q83", "Empresa dominante estado + municipio",
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
""", timeout=45, sql_dated="""
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
      AND data_empenho >= %(data_inicio)s AND data_empenho <= %(data_fim)s
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
""")


_skip("Q89", "Convenio estado com despesas suspeitas",
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
""", timeout=90, sql_dated="""
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
      AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
      AND d.valor_empenhado > 0
) tce_agg ON tce_agg.total_empenhado_periodo > cv.valor_concedente * 0.5
WHERE cv.valor_concedente > 100000
  AND UPPER(unaccent(cv.nome_municipio)) = UPPER(unaccent(%(municipio)s))
ORDER BY tce_agg.total_empenhado_periodo DESC
LIMIT 500
""")


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
""", timeout=15, sql_dated="""
SELECT d.municipio, d.cpf_cnpj, d.nome_credor,
       COUNT(*) AS qtd_empenhos,
       SUM(d.valor_empenhado) AS total_empenhado,
       SUM(d.valor_pago) AS total_pago,
       SUM(d.valor_empenhado) - SUM(d.valor_pago) AS diferenca,
       ROUND((1 - SUM(d.valor_pago) / NULLIF(SUM(d.valor_empenhado), 0)) * 100, 1) AS pct_nao_pago
FROM tce_pb_despesa d
WHERE d.valor_empenhado > 10000 AND d.valor_pago > 0
  AND d.valor_pago < d.valor_empenhado * 0.5
  AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, d.cpf_cnpj, d.nome_credor
HAVING SUM(d.valor_empenhado) > 100000
ORDER BY diferenca DESC
LIMIT 500
""")


# DISABLED: 0 municipios com resultado no web_cache
_skip("Q66", "Empenhos concentrados em dezembro",
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
""", timeout=15, sql_dated="""
SELECT d.municipio, d.ano,
       SUM(d.valor_empenhado) AS total_empenhado_ano,
       SUM(d.valor_empenhado) FILTER (WHERE d.mes = '12') AS empenhado_dezembro,
       ROUND(SUM(d.valor_empenhado) FILTER (WHERE d.mes = '12') * 100.0
             / NULLIF(SUM(d.valor_empenhado), 0), 1) AS pct_dezembro,
       COUNT(*) FILTER (WHERE d.mes = '12') AS qtd_empenhos_dez
FROM tce_pb_despesa d
WHERE d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
  AND d.valor_empenhado > 0
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, d.ano
HAVING SUM(d.valor_empenhado) > 1000000
   AND SUM(d.valor_empenhado) FILTER (WHERE d.mes = '12') * 100.0
       / NULLIF(SUM(d.valor_empenhado), 0) > 30
ORDER BY pct_dezembro DESC
LIMIT 500
""")


# DISABLED: 0 municipios com resultado no web_cache
_skip("Q64", "Despesa TCE-PB x contrato PNCP divergente",
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
""", timeout=30, sql_dated="""
SELECT d.municipio,
       pc.orgao_razao_social, pc.cnpj_orgao,
       pc.nome_fornecedor, pc.objeto,
       pc.valor_global AS valor_contrato_pncp,
       SUM(d.valor_pago) AS total_pago_tce,
       SUM(d.valor_pago) - pc.valor_global AS diferenca
FROM pncp_contrato pc
JOIN tce_pb_despesa d ON d.cnpj_basico = pc.cnpj_basico_fornecedor
    AND d.codigo_ug = pc.cnpj_orgao
WHERE pc.uf = 'PB' AND pc.valor_global > 50000
  AND d.data_empenho >= %(data_inicio)s AND d.data_empenho <= %(data_fim)s
  AND d.municipio = %(municipio)s
GROUP BY d.municipio, pc.orgao_razao_social, pc.cnpj_orgao,
         pc.nome_fornecedor, pc.objeto, pc.valor_global
HAVING ABS(SUM(d.valor_pago) - pc.valor_global) > pc.valor_global * 0.25
ORDER BY ABS(SUM(d.valor_pago) - pc.valor_global) DESC
LIMIT 500
""")


def get_categories() -> list[tuple[str, list[QueryDef]]]:
    """Retorna queries agrupadas por categoria."""
    cats: dict[str, list[QueryDef]] = {}
    for q in CIDADE_QUERIES.values():
        cats.setdefault(q.category, []).append(q)
    return list(cats.items())
