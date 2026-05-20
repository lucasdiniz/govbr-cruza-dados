from web.kpis.cidade import compute_cidade_kpis
from web.queries.cidade import (
    TOP_FORNECEDORES,
    TOP_FORNECEDORES_DATED,
    TOP_SERVIDORES_RISCO,
    TOP_SERVIDORES_RISCO_DATED,
)


def _kpis_por_id(summary: dict) -> dict:
    return {k["id"]: k for k in summary["kpis"]}


def test_kpis_de_sancao_usam_pagamento_durante_sancao_quando_disponivel():
    summary = compute_cidade_kpis(
        perfil={"total_pago": 1000},
        fornecedores=[
            {
                "total_pago": 100,
                "flag_ceis": True,
                "flag_recebeu_durante_sancao_qualquer": False,
                "flag_recebeu_durante_sancao_aplicavel": False,
                "flag_recebeu_durante_inidoneidade": False,
            },
            {
                "total_pago": 100,
                "flag_recebeu_durante_sancao_qualquer": True,
                "flag_recebeu_durante_sancao_aplicavel": False,
                "flag_recebeu_durante_inidoneidade": False,
            },
            {
                "total_pago": 100,
                "flag_recebeu_durante_sancao_qualquer": True,
                "flag_recebeu_durante_sancao_aplicavel": True,
                "flag_recebeu_durante_inidoneidade": False,
            },
        ],
        servidores=[],
    )

    kpis = _kpis_por_id(summary)
    assert kpis["kpi-sancao-qualquer"]["value"] == 2
    assert kpis["kpi-sancao-municipio"]["value"] == 1


def test_kpis_de_sancao_mantem_fallback_para_cache_antigo():
    summary = compute_cidade_kpis(
        perfil={"total_pago": 1000},
        fornecedores=[{"total_pago": 100, "flag_ceis": True}],
        servidores=[],
    )

    kpis = _kpis_por_id(summary)
    assert kpis["kpi-sancao-qualquer"]["value"] == 1


def test_sancao_qualquer_inclui_aplicavel_em_cache_parcialmente_antigo():
    summary = compute_cidade_kpis(
        perfil={"total_pago": 1000},
        fornecedores=[
            {
                "total_pago": 100,
                "flag_ceis": False,
                "flag_cnep": False,
                "flag_inidoneidade": False,
                "flag_acordo_leniencia": False,
                "flag_recebeu_durante_sancao_aplicavel": True,
            }
        ],
        servidores=[],
    )

    kpis = _kpis_por_id(summary)
    assert kpis["kpi-sancao-municipio"]["value"] == 1
    assert kpis["kpi-sancao-qualquer"]["value"] == 1


def test_top_fornecedores_dated_filtra_flags_de_sancao_pelo_periodo():
    assert "flag_recebeu_durante_sancao_qualquer" in TOP_FORNECEDORES_DATED
    assert TOP_FORNECEDORES_DATED.count("d2.data_empenho >= %(data_inicio)s") >= 3
    assert TOP_FORNECEDORES_DATED.count("d2.data_empenho <= %(data_fim)s") >= 3
    assert "%(data_inicio)s" not in TOP_FORNECEDORES


def test_top_servidores_dated_filtra_pagamentos_bf_e_salario_pelo_periodo():
    assert TOP_SERVIDORES_RISCO_DATED.count("d.data_empenho >= %(data_inicio)s") >= 2
    assert TOP_SERVIDORES_RISCO_DATED.count("d.data_empenho <= %(data_fim)s") >= 2
    assert "_periodo._maior_salario AS maior_salario" in TOP_SERVIDORES_RISCO_DATED
    # `flag_bolsa_familia` recortada pelo periodo. Usa EXISTS correlacionado
    # com bolsa_familia (apelido bf_periodo) em vez de CTE materializada,
    # porque mes_competencia nao tem indice e o DISTINCT da janela inteira
    # estourava o statement_timeout (deploy run 186, todas as 223 munis PB).
    assert "FROM bolsa_familia bf_periodo" in TOP_SERVIDORES_RISCO_DATED
    assert (
        "bf_periodo.cpf_digitos = mv_servidor_pb_risco.cpf_digitos_6"
        in TOP_SERVIDORES_RISCO_DATED
    )
    assert (
        "bf_periodo.mes_competencia >= REPLACE(%(ano_mes_inicio)s, '-', '')"
        in TOP_SERVIDORES_RISCO_DATED
    )
    assert (
        "bf_periodo.mes_competencia <= REPLACE(%(ano_mes_fim)s, '-', '')"
        in TOP_SERVIDORES_RISCO_DATED
    )
    assert ") AS flag_bolsa_familia" in TOP_SERVIDORES_RISCO_DATED
    # Garante que NAO voltou para CTE materializada (regressao do bug).
    assert "bf_periodo AS (" not in TOP_SERVIDORES_RISCO_DATED
    assert "%(data_inicio)s" not in TOP_SERVIDORES_RISCO
