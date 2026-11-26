"""Integração offline. P1B_TEST_SOCKET deve apontar para o PG16 descartável de docs/cache.md."""

import asyncio
import json
import os
import sys
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
def test_perfil_pela_rota(sombras, inicio, fim, centavos, pct, empenhos):
    lote.publicar(sombras, "promover", lote.preparar(sombras))
    resposta = _json(cidade.get_perfil(_payload(inicio, fim)))
    p = resposta["perfil"]
    receita = p["receita_arrecadada"]
    assert (Decimal(str(receita)) * 100 if receita is not None else None) == centavos
    observado = p["pct_folha_receita"]
    assert (float(observado) if observado is not None else None, p["qtd_empenhos"]) == (pct, empenhos)
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
    """Workers, filtro/skip e commits reais, isolados no schema do socket da fixture."""
    _popular_cache(banco)
    monkeypatch.setattr(warm, "REWARM_KEYS", {"ANO:PERFIL", "12M:PERFIL"})
    with banco.cursor() as cur:
        cur.execute("SELECT current_schema()")
        esquema = cur.fetchone()[0]
    monkeypatch.setattr(warm, "DSN", banco.dsn + f" options='-c search_path={esquema},public'")
    monkeypatch.setattr(warm, "PARALLEL_WORKERS", 2)
    # Projeções TOP sintéticas (sem as MVs de pessoa/empresa), usando o
    # período da consulta; no ano da foto não há fornecedores nem servidores de risco.
    for nome in ("TOP_FORNECEDORES_DATED", "TOP_SERVIDORES_RISCO_DATED"):
        monkeypatch.setattr(warm, nome, "SELECT 12 AS total_pago WHERE %(ano_fim)s = 2027")
    return banco


def _html():
    req = Request({"type": "http", "method": "GET", "path": "/cidade/teste", "query_string": b"",
                   "scheme": "http", "server": ("fixture.invalid", 80), "headers": []})
    return asyncio.run(cidade._render_cidade(req, MUN))


def _indisponivel():
    p = _payload("2026-01-01", HOJE.isoformat())
    assert _html().status_code == 503
    for resposta in (cidade.get_perfil(p), cidade.get_kpis(MUN, p)):
        assert asyncio.run(resposta).status_code == 503
    assert not ({"PERFIL", "KPI_SUMMARY"} & _json(cidade.batch_cache(MUN, "ANO")).keys())
    assert _json(cidade.get_perfil(_payload()))["perfil"]["pct_folha_receita"] == 90


def _leituras():
    p = _payload("2026-01-01", HOJE.isoformat())
    html = _html()
    assert html.status_code == 200
    return (_json(cidade.get_perfil(p))["perfil"], _json(cidade.get_kpis(MUN, p)),
            _json(cidade.batch_cache(MUN, "ANO")), html.body.decode())


def test_publicacao_reversao_e_leitores(sombras):
    conn = sombras
    with conn.cursor() as cur:
        cur.execute("SELECT * FROM web_cache ORDER BY 1,2")
        preimagem = cur.fetchall()
    _indisponivel()
    sha = lote.preparar(conn)
    _indisponivel()
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
    _indisponivel()
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
    _indisponivel()
    with sombras.cursor() as cur:
        cur.execute("SELECT to_regclass('web_cache_perfil_reversao')")
        assert cur.fetchone() == (None,)


def test_erro_em_municipio_nao_libera_manifesto(sombras, monkeypatch):
    monkeypatch.setattr(warm, "_warm_kpi_summary_across_munis", lambda *_: (1, 1))
    with pytest.raises(ValueError, match="KPI_SUMMARY incompleto"):
        lote.preparar(sombras)
    with pytest.raises(ValueError, match="Sombras"):
        lote.preparar(sombras)  # não retomar sombras de uma tentativa anterior
    _indisponivel()


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
    _indisponivel()


def test_folha_duas_grafias_sem_mes_invalido(sombras):
    with sombras.cursor() as cur:
        cur.execute("DELETE FROM tce_pb_servidor")
        cur.execute("""
            INSERT INTO tce_pb_servidor SELECT %s, mes, v FROM (VALUES
              ('2026-01',2), ('202601',3), ('2026--01',900), ('2026-00',900),
              ('202513',900), ('2026-1',900), ('202601x',900)) c(mes,v);
            UPDATE tce_pb_receita SET valor=100 WHERE mes_ano='012026';
        """, (MUN,))
    lote.publicar(sombras, "promover", lote.preparar(sombras))
    for inicio in ("2026-01-01", "2025-12-01"):
        perfil = _json(cidade.get_perfil(_payload(inicio, "2026-01-31")))["perfil"]
        assert perfil["total_folha"] == 5
    assert _json(cidade.get_perfil(_payload("2026-01-01", "2026-01-31")))["perfil"]["pct_folha_receita"] == 5


def test_pre_aprovacao_cron_reset_miss_e_custom(sombras, monkeypatch):
    sha = lote.preparar(sombras)
    monkeypatch.setattr(warm, "REWARM_KEYS", set())  # warm genérico/cron, inclusive miss
    with sombras.cursor() as cur:
        cur.execute("DELETE FROM web_cache WHERE query_id LIKE '%__pending'")  # reset genérico existente
    # TOP_* reais já presentes; roda os filtros reais de skip e a fase completa
    # sem queries de relatório. OUTRO não tinha nenhuma das quatro live.
    for p, params in warm._parametros_datados(HOJE).items():
        _, falhas = warm._warm_phase(p, [MUN, OUTRO], [], params, False)
        assert not falhas
    with sombras.cursor() as cur:
        cur.execute("SELECT count(*) FROM web_cache WHERE municipio=%s AND query_id=ANY(%s)", (OUTRO, lote.CHAVES))
        assert cur.fetchone() == (0,)
        cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + cidade.PERFIL_MUNICIPIO_PUBLICADO,
                    cidade._date_params(_payload("2026-01-15", "2026-02-01")))
        plano = cur.fetchone()[0][0]["Plan"]
        def leituras(no):
            yield no
            for filho in no.get("Plans", []):
                yield from leituras(filho)
        assert all(n["Actual Loops"] == 0 for n in leituras(plano)
                   if n.get("Relation Name", "").startswith("tce_pb_"))
    for p in (_payload("2026-01-15", "2026-02-01"), _payload("2026-01-01", HOJE.isoformat(), OUTRO)):
        assert asyncio.run(cidade.get_perfil(p)).status_code == 503
        assert asyncio.run(cidade.get_kpis(p.municipio, p)).status_code == 503
    lote.publicar(sombras, "promover", sha)
    assert _json(cidade.get_perfil(_payload("2026-01-15", "2026-02-01")))["perfil"]["total_folha"] == 5


@pytest.mark.parametrize("nova_data", [date(2026, 11, 27), date(2027, 1, 1)])
def test_intervalo_real_nos_quatro_leitores(sombras, monkeypatch, nova_data):
    sha = lote.preparar(sombras)
    lote.publicar(sombras, "promover", sha)
    monkeypatch.setattr(cidade, "_today_gmt3", lambda: nova_data)
    monkeypatch.setattr(warm, "_today_gmt3", lambda: nova_data)
    html = _html().body.decode()
    assert "2026-01-01 a 2026-11-26" in html and " (ate hoje)" not in html
    assert 'label="Ano atual" selected' not in html
    for periodo, inicio in (("ANO", nova_data.replace(month=1, day=1).isoformat()),
                            ("12M", cidade._last_12m_bounds(nova_data)[0])):
        p = _payload(inicio, nova_data.isoformat())
        batch = _json(cidade.batch_cache(MUN, periodo))
        assert not ({"PERFIL", "KPI_SUMMARY"} & batch.keys())
        assert "TOP_FORNECEDORES" in batch  # contrato das outras chaves não mudou
        atual = _json(cidade.get_perfil(p))["perfil"]
        assert (atual["periodo_inicio"], atual["periodo_fim"]) == (inicio, nova_data.isoformat())
        # A fixture não tem as tabelas dos TOP_* live: falha explícita, não
        # resumo antigo rotulado como atual nem KPIs zeros sintetizados.
        assert asyncio.run(cidade.get_kpis(MUN, p)).status_code == 503
    anterior = _payload("2026-01-01", HOJE.isoformat())
    assert _json(cidade.get_kpis(MUN, anterior))["periodo_fim"] == HOJE.isoformat()
    # Com os TOPs disponíveis, a mesma API calcula o intervalo atual em vez
    # de reutilizar o resumo cacheado com o rótulo novo.
    monkeypatch.setattr(cidade, "TOP_FORNECEDORES_DATED", warm.TOP_FORNECEDORES_DATED)
    monkeypatch.setattr(cidade, "TOP_SERVIDORES_RISCO_DATED", warm.TOP_SERVIDORES_RISCO_DATED)
    atual = _json(cidade.get_kpis(MUN, _payload(f"{nova_data.year}-01-01", nova_data.isoformat())))
    assert (atual["periodo_inicio"], atual["periodo_fim"]) == (f"{nova_data.year}-01-01", nova_data.isoformat())
    lote.publicar(sombras, "reverter", sha)  # inversa independente do relógio
    _indisponivel()


@pytest.mark.parametrize("qid", ["ANO:TOP_FORNECEDORES", "12M:TOP_SERVIDORES", "PERFIL"])
def test_dependencia_reescrita_bloqueia_inversa(sombras, qid):
    sha = lote.preparar(sombras)
    lote.publicar(sombras, "promover", sha)
    with sombras.cursor() as cur:
        cur.execute("UPDATE web_cache SET updated_at=now() WHERE query_id=%s AND municipio=%s", (qid, OUTRO))
    with pytest.raises(ValueError, match="Dependências"):
        lote.publicar(sombras, "reverter", sha)
    assert Decimal(_leituras()[0]["receita_arrecadada"]) == 107


def test_kpi_de_top_antigo_nao_recebe_data_do_perfil(sombras):
    with sombras.cursor() as cur:
        warm._upsert(cur, "12M:TOP_FORNECEDORES", MUN, ["total_pago"], [[99]])
    with pytest.raises(ValueError, match="12M:KPI_SUMMARY incompleto"):
        lote.preparar(sombras)
    _indisponivel()


def test_cli_com_lock_e_conexoes_proprias(sombras, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["cache_perfil_datado", "preparar"])
    with sombras.cursor() as cur:
        cur.execute("SELECT pg_advisory_lock(hashtextextended('perfil-datado-pb', 0))")
        with pytest.raises(RuntimeError, match="em execução"):
            lote.main()
        cur.execute("SELECT pg_advisory_unlock(hashtextextended('perfil-datado-pb', 0))")
    lote.main()
    sha = capsys.readouterr().out.split("SHA-256: ")[-1].strip()
    assert len(bytes.fromhex(sha)) == 32
    for operacao in ("promover", "reverter"):
        monkeypatch.setattr(sys, "argv", ["cache_perfil_datado", operacao, sha])
        lote.main()
        if operacao == "promover":
            assert _leituras()[0]["periodo_inicio"] == "2026-01-01"
    _indisponivel()


@pytest.mark.parametrize("inicio,fim", [("20260101", "2026-11-26"), ("2026-01-01", "20261126"),
                                        ("2025-W48-4", "2026-11-26")])
def test_grafia_nao_canonica_nao_vira_custom(inicio, fim):
    p = _payload(inicio, fim)
    assert asyncio.run(cidade.get_perfil(p)).status_code == 400
    assert asyncio.run(cidade.get_kpis(MUN, p)).status_code == 400
