"""Integração offline. P1B_TEST_SOCKET deve apontar para o PG16 descartável de docs/cache.md."""

import asyncio
import json
import os
from contextlib import nullcontext
from datetime import date
from decimal import Decimal
from uuid import uuid4

import psycopg2
import pytest
from starlette.requests import Request

from web import cache_perfil_datado as lote, db, warm_cache as warm
from web.routes import cidade


HOJE = date(2026, 11, 26)
MUN = "Município Sintético"
OUTRO = "Outro Município"


@pytest.fixture
def banco(monkeypatch):
    socket = os.environ.get("P1B_TEST_SOCKET")
    if not socket:
        pytest.skip("requer P1B_TEST_SOCKET exclusivo")
    assert os.path.isabs(socket) and "," not in socket
    conn = psycopg2.connect(host=socket, hostaddr="", port=54160, dbname="p1b_test",
                            user="p1b_teste", connect_timeout=2)
    esquema = "teste_" + uuid4().hex
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('listen_addresses'), current_setting('unix_socket_directories')")
            assert cur.fetchone() == ("", socket)
            assert conn.server_version // 10000 == 16
            cur.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
            cur.execute(f"CREATE SCHEMA {esquema}")
            cur.execute(f"SET search_path = {esquema}, public")
            cur.execute(warm.SCHEMA_DDL)
            cur.execute("""
                CREATE TABLE mv_municipio_pb_risco(municipio text);
                CREATE TABLE tce_pb_receita(municipio text, ano int, mes_ano varchar(10),
                                            tipo_atualizacao_receita text, valor numeric(15,2));
                CREATE TABLE tce_pb_servidor(municipio text, ano_mes text, valor_vantagem numeric);
                CREATE TABLE tce_pb_despesa(municipio text, data_empenho date, mes text,
                    valor_empenhado numeric, valor_pago numeric, cnpj_basico text,
                    numero_licitacao text, modalidade_licitacao text, codigo_elemento_despesa text);
                INSERT INTO mv_municipio_pb_risco VALUES (%s), (%s), (NULL);
                INSERT INTO tce_pb_receita
                SELECT unaccent(%s), 2026, mes, 'Lançamento de Receita', valor FROM (VALUES
                    ('102025',800), ('112025',2), ('122025',3), ('012025',1),
                    ('012026',10), ('022026',90), ('032026',0), ('112026',7), ('122026',500),
                    ('132025',999), ('002026',999), ('012026x',999), (NULL,999)
                ) c(mes, valor);
                INSERT INTO tce_pb_receita VALUES
                    (%s,2026,'012026','Dedução do Fundeb',-3),
                    (%s,2026,'012026','Lançamento de Receita',999);
                INSERT INTO tce_pb_servidor VALUES (%s,'202601',5), (%s,'202603',1);
                INSERT INTO tce_pb_despesa(municipio,data_empenho,valor_empenhado,valor_pago)
                    VALUES (%s,'2026-01-30',100,80);
            """, (MUN, OUTRO, MUN, MUN, OUTRO, MUN, MUN, MUN))
        monkeypatch.setattr(cidade, "_today_gmt3", lambda: HOJE)
        monkeypatch.setattr(warm, "_today_gmt3", lambda: HOJE)
        monkeypatch.setattr(db, "get_conn", lambda: nullcontext(conn))
        monkeypatch.setattr(cidade, "get_pb_medias", lambda: {})
        yield conn
    finally:
        conn.rollback()
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"DROP SCHEMA IF EXISTS {esquema} CASCADE")
        conn.close()


def _payload(inicio=None, fim=None, mun=MUN):
    return cidade.MunicipioPayload(municipio=mun, data_inicio=inicio, data_fim=fim)


def _json(resposta):
    resposta = asyncio.run(resposta)
    assert resposta.status_code == 200
    return json.loads(resposta.body)


@pytest.mark.parametrize("inicio,fim,centavos,pct,empenhos", [
    ("2026-01-01", "2026-01-31", 1000, 50, 1),
    ("2026-01-15", "2026-01-15", 1000, 50, 0),  # despesa diária, receita e folha mensais
    ("2026-01-31", "2026-02-01", 10000, 5, 0),
    ("2025-12-31", "2026-01-01", 1300, 38.5, 0),
    ("2025-01-01", "2025-01-31", 100, None, 0),
    ("2025-11-27", "2026-11-26", 11200, 5.4, 1),  # 13 competências
    ("2026-01-01", "2026-11-26", 10700, 5.6, 1),
    ("2026-01-01", "2026-12-31", 60700, 1, 1),
    ("2026-03-01", "2026-03-31", 0, None, 0),
    ("2026-04-01", "2026-04-30", None, None, 0),
])
def test_perfil_pela_rota(banco, inicio, fim, centavos, pct, empenhos):
    resposta = _json(cidade.get_perfil(_payload(inicio, fim)))
    p = resposta["perfil"]
    receita = p["receita_arrecadada"]
    assert (Decimal(str(receita)) * 100 if receita is not None else None) == centavos
    assert (p["pct_folha_receita"], p["qtd_empenhos"]) == (pct, empenhos)
    assert (p["competencia_receita_inicio"], p["competencia_receita_fim"]) == (inicio[:7], fim[:7])
    assert "sem rateio por dia" in resposta["narrative"]["auditor"]


def test_plano_uma_leitura_de_cada_agregado(banco):
    params = cidade._date_params(_payload("2026-01-01", "2026-01-31"))
    with banco.cursor() as cur:
        cur.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + warm.PERFIL_MUNICIPIO_LIVE, params)
        plano = cur.fetchone()[0][0]["Plan"]

    def percorrer(no):
        yield no
        for filho in no.get("Plans", []):
            yield from percorrer(filho)

    for tabela in ("tce_pb_receita", "tce_pb_servidor"):
        assert [n["Actual Loops"] for n in percorrer(plano) if n.get("Relation Name") == tabela] == [1]


def _popular_cache(conn):
    with conn.cursor() as cur:
        for mun in (MUN, OUTRO):
            perfil = {"municipio": mun, "receita_arrecadada": 900, "total_folha": 810,
                      "pct_folha_receita": 90, "risco_score": 33, "qtd_empenhos": 2,
                      "qtd_fornecedores": 1, "total_pago": 70, "pct_sem_licitacao": 0}
            warm._upsert(cur, "PERFIL", mun, list(perfil), [list(perfil.values())])
            for periodo in ("ANO", "12M"):
                for dep in ("TOP_FORNECEDORES", "TOP_SERVIDORES"):
                    warm._upsert(cur, f"{periodo}:{dep}", mun, ["total_pago"], [])
                if mun == MUN:  # no outro município as quatro chaves estavam ausentes
                    warm._upsert(cur, f"{periodo}:PERFIL", mun, list(perfil), [list(perfil.values())])
                    warm._upsert(cur, f"{periodo}:KPI_SUMMARY", mun, ["payload"], [[{"score_canonical": 33}]])
        warm._upsert(cur, "Q01__pending", MUN, [], [])
        warm._upsert(cur, "ANO:PERFIL__pending", MUN, [], [])  # sombra genérica não integra o lote
        warm._upsert(cur, "Q01xxpending", MUN, [], [])  # _ não é wildcard


@pytest.fixture
def sombras(banco, monkeypatch):
    """Preparar com adaptadores sequenciais em fixture: sem worker, ciclo ou DSN do warm."""
    _popular_cache(banco)
    monkeypatch.setattr(warm, "REWARM_KEYS", {"ANO:PERFIL", "12M:PERFIL"})

    def perfil(qid, sql, municipios, params, timeout, verbose):
        for mun in municipios:
            cols, rows = db.execute_query(sql, dict(params, municipio=mun))
            with banco.cursor() as cur:
                warm._upsert(cur, warm._effective_qid(qid), mun, cols, rows)
        return len(municipios), 0

    def kpi(municipios, periodo, verbose):
        ok = sum(warm._compute_and_cache_kpi_summary(banco, m, periodo, False) for m in municipios)
        return ok, len(municipios) - ok

    monkeypatch.setattr(warm, "_warm_query_across_munis", perfil)
    monkeypatch.setattr(warm, "_warm_kpi_summary_across_munis", kpi)
    return banco


def _leituras():
    p = _payload("2026-01-01", HOJE.isoformat())
    req = Request({"type": "http", "method": "GET", "path": "/cidade/teste", "query_string": b"",
                   "scheme": "http", "server": ("fixture.invalid", 80), "headers": []})
    html = asyncio.run(cidade._render_cidade(req, MUN))
    assert html.status_code == 200
    return (_json(cidade.get_perfil(p))["perfil"], _json(cidade.get_kpis(MUN, p)),
            _json(cidade.batch_cache(MUN, "ANO")), html.body.decode())


def test_publicacao_reversao_e_leitores(sombras):
    conn = sombras
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM web_cache ORDER BY 1,2")
        preimagem = cur.fetchall()
    antes = _leituras()
    assert "Folha/receita: 90%" in antes[3]
    sha = lote.preparar(conn)
    assert _leituras() == antes
    for periodo in ("", "ANO", "12M"):
        assert not any("__pending" in k for k in _json(cidade.batch_cache(MUN, periodo)))
    assert "Q01xxpending" in _json(cidade.batch_cache(MUN))
    lote.publicar(conn, "promover", sha)
    p, kpis, batch, html = _leituras()
    assert Decimal(p["receita_arrecadada"]) == 107
    assert kpis["kpis"] and kpis["score_canonical"] == 33
    assert kpis == json.loads(batch["KPI_SUMMARY"]["rows"][0][0])
    assert "Folha/receita: 5,6%" in html
    assert _json(cidade.get_perfil(_payload()))["perfil"]["pct_folha_receita"] == 90
    p12 = _json(cidade.get_perfil(_payload("2025-11-27", HOJE.isoformat())))["perfil"]
    assert Decimal(p12["receita_arrecadada"]) == 112
    lote.publicar(conn, "reverter", sha)
    assert _leituras() == antes
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM web_cache ORDER BY 1,2")
        assert cur.fetchall() == preimagem


def test_overlay_receita_zero_nao_herda_percentual(sombras):
    with sombras.cursor() as cur:
        cur.execute("UPDATE tce_pb_receita SET valor=0")
    lote.publicar(sombras, "promover", lote.preparar(sombras))
    p, _, _, html = _leituras()
    assert Decimal(p["receita_arrecadada"]) == 0 and p["pct_folha_receita"] is None
    assert "Folha/receita: indisponível" in html and "Folha/receita: 90%" not in html


@pytest.mark.parametrize("falha", ["ausente", "sobra", "mudou", "dependencia", "cadastro"])
def test_prevalidacao_bloqueia_todo_o_lote(sombras, falha):
    sha = lote.preparar(sombras)
    with sombras.cursor() as cur:
        if falha == "ausente":
            cur.execute("DELETE FROM web_cache WHERE query_id=%s AND municipio=%s",
                        (warm._effective_qid("12M:KPI_SUMMARY"), OUTRO))
        elif falha == "sobra":
            warm._upsert(cur, warm._effective_qid("ANO:PERFIL"), "Não cadastrado", [], [[]])
        elif falha == "cadastro":
            cur.execute("DELETE FROM mv_municipio_pb_risco WHERE municipio=%s", (OUTRO,))
        else:
            qid = warm._effective_qid("ANO:PERFIL") if falha == "mudou" else "12M:TOP_SERVIDORES"
            cur.execute("UPDATE web_cache SET updated_at=now() WHERE query_id=%s AND municipio=%s", (qid, OUTRO))
    with pytest.raises(ValueError):
        lote.publicar(sombras, "promover", sha)
    assert _leituras()[0]["pct_folha_receita"] == 90
    with sombras.cursor() as cur:
        cur.execute("SELECT to_regclass('web_cache_perfil_reversao')")
        assert cur.fetchone() == (None,)


def test_erro_em_municipio_nao_libera_manifesto(sombras, monkeypatch):
    monkeypatch.setattr(warm, "_warm_kpi_summary_across_munis", lambda *_: (1, 1))
    with pytest.raises(ValueError, match="KPI_SUMMARY incompleto"):
        lote.preparar(sombras)
    with pytest.raises(ValueError, match="Sombras"):
        lote.preparar(sombras)  # não retomar sombras de uma tentativa anterior
    assert _leituras()[0]["pct_folha_receita"] == 90


def test_reversao_nao_apaga_escrita_posterior(sombras):
    sha = lote.preparar(sombras)
    lote.publicar(sombras, "promover", sha)
    with sombras.cursor() as cur:
        cur.execute("UPDATE web_cache SET updated_at=now() WHERE query_id='12M:PERFIL' AND municipio=%s", (OUTRO,))
    with pytest.raises(ValueError, match="live alterado"):
        lote.publicar(sombras, "reverter", sha)
    assert Decimal(_leituras()[0]["receita_arrecadada"]) == 107


def test_falha_durante_swap_desfaz_ate_a_inversa(sombras):
    sha = lote.preparar(sombras)
    with sombras.cursor() as cur:
        cur.execute("""
            CREATE FUNCTION pular_par() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN RETURN NULL; END $$;
            CREATE TRIGGER pular_uma_promocao BEFORE UPDATE ON web_cache FOR EACH ROW
                WHEN (NEW.query_id = '12M:KPI_SUMMARY' AND NEW.municipio = 'Outro Município')
                EXECUTE FUNCTION pular_par();
        """)
    with pytest.raises(ValueError, match="live alterado"):
        lote.publicar(sombras, "promover", sha)
    with sombras.cursor() as cur:
        cur.execute("SELECT count(*), to_regclass('web_cache_perfil_reversao') FROM web_cache WHERE query_id=ANY(%s)",
                    (lote.SOMBRAS,))
        assert cur.fetchone() == (8, None)
    assert _leituras()[0]["pct_folha_receita"] == 90
