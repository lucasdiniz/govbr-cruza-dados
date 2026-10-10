import re
from pathlib import Path

from web.queries.cidade import PB_MEDIAS, PERFIL_MUNICIPIO, PERFIL_MUNICIPIO_LIVE
from web.routes.cidade import build_narrative

_ROOT = Path(__file__).resolve().parent.parent


def _perfil(**overrides):
    perfil = {
        "municipio": "DESTERRO",
        "total_empenhado": 1000.0,
        "total_pago": 1000.0,
        "qtd_fornecedores": 10,
        "pct_sem_licitacao": 94.9,
        "pct_valor_sem_licitacao": 53.8,
    }
    perfil.update(overrides)
    return perfil


def test_narrativa_desse_dinheiro_usa_pct_por_valor():
    narrativa = build_narrative(_perfil())

    assert "Do que foi pago em compras e servi&ccedil;os, <a href=\"#licitacoes\"><strong>54%</strong>" in narrativa["citizen"]
    assert "95%" not in narrativa["citizen"]


def test_narrativa_compara_com_mediana_por_valor():
    narrativa = build_narrative(
        _perfil(),
        medias={"mediana_pct_sem_licitacao": 50.0, "mediana_pct_valor_sem_licitacao": 30.0},
    )

    assert "acima da m&eacute;dia da Para&iacute;ba (mediana: 30%)" in narrativa["citizen"]


def test_narrativa_cache_antigo_sem_pct_valor_usa_formulacao_por_contagem():
    perfil = _perfil()
    del perfil["pct_valor_sem_licitacao"]

    narrativa = build_narrative(perfil)

    assert "compras e servi&ccedil;os" not in narrativa["citizen"]
    assert "95%</strong> dos empenhos foram registrados sem licita&ccedil;&atilde;o" in narrativa["citizen"]
    assert "Sem licita&ccedil;&atilde;o: 95% dos empenhos" in narrativa["auditor"]


def test_narrativa_auditor_mostra_valor_e_contagem():
    narrativa = build_narrative(_perfil())

    assert "Sem licita&ccedil;&atilde;o: 54% do valor pago em compras/servi&ccedil;os</a> (95% dos empenhos)." in narrativa["auditor"]


def test_narrativa_omite_frase_quando_nada_pago_sem_licitacao():
    narrativa = build_narrative(_perfil(pct_sem_licitacao=0, pct_valor_sem_licitacao=0))

    assert "compras e servi&ccedil;os" not in narrativa["citizen"]
    assert "Sem licita" not in narrativa["auditor"]


def test_queries_de_perfil_expoem_pct_valor_sem_licitacao():
    assert "lv.pct_valor_sem_licitacao" in PERFIL_MUNICIPIO
    assert "AS pct_valor_sem_licitacao" in PERFIL_MUNICIPIO_LIVE
    assert "LEFT JOIN mv_municipio_pb_licitacao_valor lv" in PERFIL_MUNICIPIO
    assert "LEFT JOIN mv_municipio_pb_licitacao_valor lv" in PB_MEDIAS
    # Folha (11) e encargos (13) fora da base licitavel nos dois caminhos.
    for sql in (PERFIL_MUNICIPIO_LIVE, (_ROOT / "sql/12_views.sql").read_text()):
        assert "codigo_elemento_despesa" in sql and "'11','12','13'" in sql
    assert "AS mediana_pct_valor_sem_licitacao" in PB_MEDIAS


def test_queries_de_perfil_sem_percent_solto():
    """psycopg2 com params dict exige '%%' literal; um '%' solto (ate em
    comentario SQL) quebra com 'argument formats can't be mixed'."""
    for sql in (PERFIL_MUNICIPIO, PERFIL_MUNICIPIO_LIVE, PB_MEDIAS):
        assert not re.search(r"%(?!\()", sql.replace("%%", ""))


def test_mv_swap_identica_a_fonte_de_verdade():
    """deploy/mv_updates/mv_municipio_pb_licitacao_valor.sql deve ter a mesma
    definicao de sql/12_views.sql (sufixo _swap a parte), senao o proximo
    rebuild completo divergiria do que foi aplicado via swap."""
    views = (_ROOT / "sql/12_views.sql").read_text()
    inicio = views.index("CREATE MATERIALIZED VIEW mv_municipio_pb_licitacao_valor AS")
    fim = views.index("\n", views.index("CREATE UNIQUE INDEX idx_mv_mun_licval_municipio"))
    fonte = views[inicio:fim].strip()

    swap = (_ROOT / "deploy/mv_updates/mv_municipio_pb_licitacao_valor.sql").read_text()
    swap_body = swap[swap.index("CREATE MATERIALIZED VIEW"):].strip()

    assert "pct_valor_sem_licitacao" in fonte
    assert swap_body.replace("_swap", "") == fonte


def test_mv_municipio_pb_risco_nao_muda():
    """A MV com dependentes (mapa/kpi_score) nao pode ganhar colunas aqui:
    swap dela recria os dependentes vazios (ilegiveis) ate o REFRESH."""
    views = (_ROOT / "sql/12_views.sql").read_text()
    inicio = views.index("CREATE MATERIALIZED VIEW mv_municipio_pb_risco AS")
    fim = views.index("CREATE INDEX idx_mv_mun_risco")
    assert "pct_valor_sem_licitacao" not in views[inicio:fim]


def test_mv_nova_entra_no_refresh_pos_incremental():
    from etl.refresh_post_incremental import _TCE_PB_MVS_L1

    assert "mv_municipio_pb_licitacao_valor" in _TCE_PB_MVS_L1
