"""Testes do sync mensal RFB (etl/rfb_sync.py).

Unitarios rodam sempre. Os de integracao precisam de um Postgres DESCARTAVEL:

    TEST_RFB_DSN="host=$PWD/.ensaio/socket dbname=rfb_sync_test" pytest tests/test_rfb_sync.py

O fixture RECRIA as tabelas RFB (sql/02_schema_rfb.sql faz DROP TABLE), por
isso recusa qualquer banco cujo nome nao contenha "test".
"""
from __future__ import annotations

import os
import shutil
import zipfile
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock
from urllib.error import HTTPError

import psycopg2
import pytest

from etl import refresh_post_incremental as refresh
from etl import rfb_sync, verificar_publicacao_rfb
from etl.refresh_post_incremental import SOURCE_REFRESH_FNS
from etl.rfb_common import RFB_TABLES, SOCIO, SOCIO_ATTRS, SOCIO_IDENTITY

ROOT = Path(__file__).resolve().parent.parent
TEST_DSN = os.environ.get("TEST_RFB_DSN")


# ──────────────────────────────────────────────────────────────────────────
# Unitarios
# ──────────────────────────────────────────────────────────────────────────

def test_resolve_month_valida_formato():
    assert rfb_sync.resolve_month("2026-09") == "2026-09"
    for bad in ("2026-13", "2026-9", "26-09", "2026-09;rm -rf /", ""):
        with pytest.raises(ValueError):
            rfb_sync.resolve_month(bad)


def test_lotes_cobrem_todos_os_prefixos_sem_buraco():
    bounds = rfb_sync._batch_bounds()
    assert len(bounds) == 100
    assert bounds[0] == ("00", "01")
    assert bounds[-1] == ("99", None)
    for (lo, hi), (nxt_lo, _) in zip(bounds, bounds[1:]):
        assert hi == nxt_lo


def test_expressoes_alinhadas_com_colunas():
    for spec in RFB_TABLES.values():
        assert len(spec.columns) == len(spec.exprs), spec.table
        assert len(spec.file_names()) == spec.n_files


def test_publicacao_esperada_tem_37_zips():
    zips = rfb_sync.expected_zips(rfb_sync.SYNC_ORDER)
    assert len(zips) == 37
    assert "Estabelecimentos9.zip" in zips and "Simples.zip" in zips and "Cnaes.zip" in zips


@pytest.mark.parametrize("tipo,tamanho,data,valido", [
    ("application/zip", "123", "Mon, 16 Nov 2026 10:00:00 GMT", True),
    ("application/octet-stream; charset=binary", "123", "Mon, 16 Nov 2026 10:00:00 GMT", True),
    ("text/html", "245", "Mon, 16 Nov 2026 10:00:00 GMT", False),
    ("application/zip", "0", "Mon, 16 Nov 2026 10:00:00 GMT", False),
    ("application/zip", "123", "", False),
    ("application/zip", "123", "ontem", False),
])
def test_head_valida_resposta_inteira(monkeypatch, tipo, tamanho, data, valido):
    resposta = Mock(status=200, headers={"Content-Type": tipo, "Content-Length": tamanho, "Last-Modified": data})
    cliente = Mock()
    cliente.open.side_effect = lambda *a, **kw: nullcontext(resposta)
    monkeypatch.setattr(rfb_sync, "build_opener", lambda *_: cliente)
    monkeypatch.setattr(rfb_sync.time, "sleep", lambda _: None)
    if valido:
        assert rfb_sync.head_file("2026-11", "Cnaes.zip") == (123, datetime(2026, 11, 16, 10, tzinfo=timezone.utc))
    else:
        with pytest.raises(RuntimeError, match="2026-11/Cnaes.zip"):
            rfb_sync.head_file("2026-11", "Cnaes.zip")


@pytest.mark.parametrize("erro,ausente", [(404, True), (410, True), (403, False), (302, False), (503, False)])
def test_head_distingue_ausencia_de_falha(monkeypatch, erro, ausente):
    cliente = Mock()
    cliente.open.side_effect = HTTPError("https://exemplo.gov.br", erro, "erro", {}, None)
    monkeypatch.setattr(rfb_sync, "build_opener", lambda *_: cliente)
    monkeypatch.setattr(rfb_sync.time, "sleep", lambda _: None)
    if ausente:
        assert rfb_sync.head_file("2026-11", "Cnaes.zip") is None
    else:
        with pytest.raises(RuntimeError, match="HEAD"):
            rfb_sync.head_file("2026-11", "Cnaes.zip")


@pytest.mark.parametrize("estado,esperado", [("estavel", "2026-11"), ("recente", ""), ("ausente", "")])
def test_agendador_considera_tambem_o_ultimo_zip(monkeypatch, estado, esperado):
    agora = datetime(2026, 11, 26, tzinfo=timezone.utc)

    def sonda(mes, nome):
        if nome == "Motivos.zip":
            if estado == "ausente":
                return None
            if estado == "recente":
                return 100, agora - timedelta(hours=23)
        return 100, agora - timedelta(hours=24)

    monkeypatch.setattr(verificar_publicacao_rfb, "head_file", sonda)
    assert verificar_publicacao_rfb.mes_estavel(["2026-11"], agora) == esperado


def test_identidade_socio_ignora_faixa_etaria_e_representante():
    assert "faixa_etaria" not in SOCIO_IDENTITY
    assert "cpf_representante" not in SOCIO_IDENTITY
    assert "qualificacao" in SOCIO_IDENTITY
    assert set(SOCIO_IDENTITY) | set(SOCIO_ATTRS) == set(SOCIO.columns)


@pytest.mark.parametrize("plan,ok", [
    ({"live_antes": 0, "staging": 10, "a_remover": 0}, True),           # carga inicial
    ({"live_antes": 1000, "staging": 1005, "a_remover": 5}, True),
    ({"live_antes": 1000, "staging": 0, "a_remover": 1000}, False),      # snapshot vazio
    ({"live_antes": 1000, "staging": 500, "a_remover": 0}, False),       # encolheu
    ({"live_antes": 1000, "staging": 1000, "a_remover": 50}, False),     # remocao em massa
    ({"live_antes": 70_000_000, "staging": 70_085_591, "a_remover": 0, "incompletas": 2}, True),  # 2026-09 real
    ({"live_antes": 70_000_000, "staging": 70_000_000, "a_remover": 0, "incompletas": 7_001}, False),
    ({"live_antes": 1000, "staging": 1000, "a_remover": 0, "incompletas": 1001}, False),
])
def test_guards(plan, ok):
    spec = RFB_TABLES["empresa"]
    if ok:
        rfb_sync.check_guards(spec, plan, max_delete_pct=1.0, max_shrink_pct=1.0)
    else:
        with pytest.raises(rfb_sync.GuardError):
            rfb_sync.check_guards(spec, plan, max_delete_pct=1.0, max_shrink_pct=1.0)


def test_override_de_limite():
    assert rfb_sync._parse_pct_overrides(["socio=15", "empresa=2.5"]) == {"socio": 15.0, "empresa": 2.5}
    with pytest.raises(ValueError):
        rfb_sync._parse_pct_overrides(["tabela_x=1"])


def test_refresh_registrado_para_rfb():
    assert "rfb" in SOURCE_REFRESH_FNS


# ──────────────────────────────────────────────────────────────────────────
# Integracao (Postgres descartavel)
# ──────────────────────────────────────────────────────────────────────────

def _q(*fields) -> str:
    return ";".join(f'"{f}"' for f in fields)


def _empresa(cb, nome, nat="2062", cap="1000,00"):
    return _q(cb, nome, nat, "49", cap, "01", "")


def _estab(cb, ordem, dv, situacao="02", nome="FANTASIA"):
    f = [cb, ordem, dv, "1", nome, situacao, "20200101", "00", "", "", "20200101",
         "4711302", "", "RUA", "DAS FLORES", "10", "", "CENTRO", "58000000", "PB", "2051",
         "83", "99999999", "", "", "", "", "", "", ""]
    return _q(*f)


def _socio(cb, nome, doc, qualif="49", entrada="20200101", faixa="4"):
    return _q(cb, "2", nome, doc, qualif, entrada, "", "***000000**", "", "00", faixa)


def _simples(cb, opcao="S"):
    return _q(cb, opcao, "20200101", "00000000", "N", "00000000", "00000000")


MONTH_A = {
    "Empresas": [_empresa("11111111", "ALFA LTDA"), _empresa("22222222", "BETA LTDA"),
                 _empresa("33333333", "GAMA LTDA")],
    "Estabelecimentos": [_estab("11111111", "0001", "91"), _estab("22222222", "0001", "92"),
                         _estab("33333333", "0001", "93")],
    "Socios": [_socio("11111111", "JOAO", "***111111**"), _socio("11111111", "MARIA", "***222222**"),
               _socio("22222222", "PEDRO", "***333333**")],
    "Simples": [_simples("11111111")],
}

MONTH_B = {
    "Empresas": [_empresa("11111111", "ALFA COMERCIO LTDA"), _empresa("22222222", "BETA LTDA"),
                 _empresa("44444444", "DELTA ME")],
    "Estabelecimentos": [_estab("11111111", "0001", "91"), _estab("22222222", "0001", "92", situacao="08"),
                         _estab("44444444", "0001", "94")],
    "Socios": [_socio("11111111", "JOAO", "***111111**", faixa="5"),
               _socio("22222222", "PEDRO", "***333333**", qualif="05"),
               _socio("44444444", "ANA", "***444444**")],
    "Simples": [_simples("11111111", opcao="N"), _simples("44444444")],
}

DOMAIN = {
    "Cnaes": [_q("4711302", "Comercio varejista")],
    "Municipios": [_q("2051", "JOAO PESSOA")],
    "Naturezas": [_q("2062", "Sociedade Empresaria Limitada")],
    "Paises": [_q("105", "BRASIL")],
    "Qualificacoes": [_q("49", "Socio-Administrador"), _q("05", "Administrador")],
    "Motivos": [_q("00", "SEM MOTIVO")],
}


def _write_month(base: Path, month: str, data: dict) -> dict[str, Path]:
    """ZIPs no formato RFB (1 membro, nome interno 'estranho', Latin-1)."""
    d = base / f"src-{month}"
    d.mkdir(parents=True)
    out = {}
    for prefix, rows in {**DOMAIN, **data}.items():
        spec = next((s for s in RFB_TABLES.values() if s.file_prefix == prefix), None)
        names = spec.file_names() if spec else [prefix]
        for i, name in enumerate(names):
            chunk = rows if i == 0 else []  # tudo no arquivo 0; demais vazios
            if prefix == "Socios":
                chunk = rows[i::len(names)]  # exercita inclusive colisões entre ZIPs
            zpath = d / f"{name}.zip"
            with zipfile.ZipFile(zpath, "w") as z:
                body = "".join(r + "\n" for r in chunk).encode("latin-1")
                z.writestr(f"K3241.K03200Y{i}.D60912.{prefix.upper()}CSV", body)
            out[f"{name}.zip"] = zpath
    return out


@pytest.fixture
def db(monkeypatch):
    if not TEST_DSN:
        pytest.skip("TEST_RFB_DSN nao definido")
    conn = psycopg2.connect(TEST_DSN)
    if "test" not in conn.get_dsn_parameters().get("dbname", ""):
        conn.close()
        pytest.fail("TEST_RFB_DSN precisa apontar para um banco descartavel com 'test' no nome")
    conn.autocommit = True
    with conn.cursor() as cur:
        for f in ("00_extensions.sql", "01_schema_dominio.sql", "02_schema_rfb.sql"):
            cur.execute((ROOT / "sql" / f).read_text(encoding="utf-8"))
        cur.execute("DROP TABLE IF EXISTS rfb_sync_log, socio_historico, rfb_sync_estab_delta, tce_pb_despesa, web_cache")
        cur.execute("CREATE TABLE tce_pb_despesa (cpf_cnpj VARCHAR(14), cnpj_basico CHAR(8))")
        cur.execute("CREATE TABLE web_cache (query_id TEXT, municipio TEXT, PRIMARY KEY (query_id, municipio))")
        # Grafo reduzido de MVs reais. A fixture não carrega as bases nacionais.
        cur.execute("CREATE MATERIALIZED VIEW teste_rfb_l1 AS SELECT count(*) AS n FROM socio")
        cur.execute("CREATE MATERIALIZED VIEW teste_rfb_l2 AS SELECT n FROM teste_rfb_l1")
        cur.execute("CREATE MATERIALIZED VIEW mv_empresa_municipio_pagantes AS SELECT n FROM teste_rfb_l2")
    monkeypatch.setattr(refresh, "_TCE_PB_MVS_L1", ("teste_rfb_l1",))
    monkeypatch.setattr(refresh, "_TCE_PB_MVS_L2", ("teste_rfb_l2",))
    monkeypatch.setattr(refresh, "_rebuild_servidor_tmp_after_tce_pb", lambda conn: None)
    yield conn
    conn.close()


@pytest.fixture
def fake_webdav(tmp_path, monkeypatch):
    sources: dict[str, dict[str, Path]] = {}

    def publish(month, data):
        sources[month] = _write_month(tmp_path, month, data)

    monkeypatch.setattr(rfb_sync, "list_months", lambda: sorted(sources))
    monkeypatch.setattr(rfb_sync, "list_files",
                        lambda m: {n: p.stat().st_size for n, p in sources[m].items()})

    def fake_download(month, name, expected_size, dest_dir, retries=3):
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / name
        shutil.copy(sources[month][name], dest)
        assert dest.stat().st_size == expected_size
        return dest

    monkeypatch.setattr(rfb_sync, "download_zip", fake_download)
    return publish


def _sync(month, tmp_path, **kw):
    opts = rfb_sync.SyncOptions(month=month, work_dir=tmp_path / "work", min_free_gb=0, **kw)
    return rfb_sync.run_sync(TEST_DSN, opts)


def _rows(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def test_sync_completo_mes_a_mes(db, fake_webdav, tmp_path, capsys):
    fake_webdav("2026-08", MONTH_A)
    fake_webdav("2026-09", MONTH_B)

    # Carga inicial via sync (tabelas vazias -> guards nao se aplicam)
    assert _sync("2026-08", tmp_path) == 0
    assert _rows(db, "SELECT COUNT(*) FROM empresa")[0][0] == 3
    assert _rows(db, "SELECT COUNT(*) FROM socio")[0][0] == 3
    joao_id = _rows(db, "SELECT id FROM socio WHERE nome = 'JOAO'")[0][0]
    db.cursor().execute(
        "INSERT INTO tce_pb_despesa VALUES ('44444444000194', NULL), ('33333333000193', '33333333')"
    )
    db.cursor().execute(
        "INSERT INTO web_cache VALUES ('EMPRESA_PERFIL', '33333333000193'), "
        "('EMPRESA_PERFIL_MUN', '33333333000193:joao-pessoa'), ('EMPRESA_PERFIL', '11111111000191'), "
        "('PERFIL', 'Joao Pessoa')"
    )

    # Mes seguinte. Limites folgados: fixture minusculo (2 de 3 socios saem = 67%).
    assert _sync("2026-09", tmp_path, max_delete_pct={t: 100 for t in RFB_TABLES}) == 0
    assert "RFB_SYNC_RESULT=synced" in capsys.readouterr().out

    assert _rows(db, "SELECT cnpj_basico, razao_social FROM empresa ORDER BY 1") == [
        ("11111111", "ALFA COMERCIO LTDA"), ("22222222", "BETA LTDA"), ("44444444", "DELTA ME"),
    ]
    assert _rows(db, "SELECT cnpj_completo, situacao_cadastral FROM estabelecimento ORDER BY 1") == [
        ("11111111000191", 2), ("22222222000192", 8), ("44444444000194", 2),
    ]
    assert _rows(db, "SELECT cnpj_basico, opcao_simples FROM simples ORDER BY 1") == [
        ("11111111", "N"), ("44444444", "S"),
    ]
    # JOAO: so faixa etaria mudou -> mesmo id, atualizado in-place
    assert _rows(db, "SELECT id, faixa_etaria FROM socio WHERE nome = 'JOAO'") == [(joao_id, 5)]
    # MARIA saiu; PEDRO mudou de qualificacao -> vinculo antigo no historico
    assert _rows(db, "SELECT nome, qualificacao, rfb_mes_removido FROM socio_historico ORDER BY 1") == [
        ("MARIA", "49", "2026-09"), ("PEDRO", "49", "2026-09"),
    ]
    assert _rows(db, "SELECT nome, qualificacao, cpf_cnpj_norm FROM socio ORDER BY 1") == [
        ("ANA", "49", "444444"), ("JOAO", "49", "111111"), ("PEDRO", "05", "333333"),
    ]
    assert _rows(db, "SELECT descricao FROM dom_qualificacao WHERE codigo = '05'") == [("Administrador",)]
    status = _rows(db, "SELECT rfb_mes, status FROM rfb_sync_log ORDER BY id")
    assert status == [("2026-08", "success"), ("2026-09", "success")]
    assert _rows(db, "SELECT COUNT(*) FROM pg_tables WHERE tablename LIKE '\\_rfb\\_sync\\_%'")[0][0] == 0

    # Relink direcionado: credor novo ganha cnpj_basico, removido perde
    assert _rows(db, "SELECT cpf_cnpj, cnpj_basico FROM tce_pb_despesa ORDER BY 1") == [
        ("33333333000193", None), ("44444444000194", "44444444"),
    ]
    # Paginas do estabelecimento removido saem do cache; resto intocado.
    assert _rows(db, "SELECT n FROM mv_empresa_municipio_pagantes") == [(3,)]
    assert _rows(db, "SELECT query_id, municipio FROM web_cache ORDER BY 1, 2") == [
        ("EMPRESA_PERFIL", "11111111000191"), ("PERFIL", "Joao Pessoa"),
    ]
    # Delta consumido so depois do relink
    assert _rows(db, "SELECT COUNT(*) FROM rfb_sync_estab_delta")[0][0] == 0

    # Idempotencia / protecoes de ordem
    assert _sync("2026-09", tmp_path) == 0
    assert "RFB_SYNC_RESULT=skipped" in capsys.readouterr().out
    assert _sync("2026-08", tmp_path) == 2  # regrediria a base
    assert _sync("2026-08", tmp_path, force=True) == 2


def test_resync_forcado_eh_noop(db, fake_webdav, tmp_path):
    fake_webdav("2026-09", MONTH_B)
    assert _sync("2026-09", tmp_path) == 0
    before = _rows(db, "SELECT id, cnpj_basico, nome, qualificacao, faixa_etaria FROM socio ORDER BY id")
    assert _sync("2026-09", tmp_path, force=True) == 0
    stats = _rows(db, "SELECT stats FROM rfb_sync_log ORDER BY id DESC LIMIT 1")[0][0]
    for t in ("empresa", "estabelecimento", "simples"):
        assert (stats[t]["removidas"], stats[t]["atualizadas"], stats[t]["inseridas"]) == (0, 0, 0), t
    assert (stats["socio"]["movidas_historico"], stats["socio"]["inseridas"]) == (0, 0)
    assert _rows(db, "SELECT id, cnpj_basico, nome, qualificacao, faixa_etaria FROM socio ORDER BY id") == before


def test_guard_de_remocao_em_massa_nao_toca_live(db, fake_webdav, tmp_path):
    fake_webdav("2026-08", MONTH_A)
    truncated = {k: v[:1] for k, v in MONTH_A.items()}  # "download truncado"
    fake_webdav("2026-09", truncated)
    assert _sync("2026-08", tmp_path) == 0
    snapshot = _rows(db, "SELECT * FROM empresa ORDER BY 1")

    assert _sync("2026-09", tmp_path) == 2
    assert _rows(db, "SELECT * FROM empresa ORDER BY 1") == snapshot
    assert _rows(db, "SELECT status FROM rfb_sync_log ORDER BY id DESC LIMIT 1") == [("aborted",)]


def test_lock_impede_sync_concorrente(db, fake_webdav, tmp_path):
    fake_webdav("2026-09", MONTH_B)
    other = psycopg2.connect(TEST_DSN)
    try:
        with other.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (rfb_sync.ADVISORY_LOCK_KEY,))
        assert _sync("2026-09", tmp_path) == 1
    finally:
        other.close()
    assert _rows(db, "SELECT COUNT(*) FROM empresa")[0][0] == 0


def test_linha_duplicada_no_snapshot_vira_um_socio(db, fake_webdav, tmp_path):
    """A RFB publica algumas linhas de socio repetidas byte a byte (7 grupos em
    ~2M no arquivo Socios1 de 2026-09). O sync guarda uma so."""
    dup = dict(MONTH_A, Socios=MONTH_A["Socios"] + [MONTH_A["Socios"][0]])
    fake_webdav("2026-08", dup)
    assert _sync("2026-08", tmp_path) == 0
    assert _rows(db, "SELECT COUNT(*) FROM socio WHERE nome = 'JOAO'")[0][0] == 1
    assert _rows(db, "SELECT stats->'socio'->'repeticoes_identicas' FROM rfb_sync_log") == [(1,)]


@pytest.mark.parametrize("parcial", [True, False], ids=["somente-estabelecimento", "sem-refresh"])
def test_pendente_nao_publica_nem_consume_delta(db, fake_webdav, tmp_path, capsys, parcial):
    fake_webdav("2026-08", MONTH_A)
    fake_webdav("2026-09", MONTH_B)
    assert _sync("2026-08", tmp_path) == 0
    capsys.readouterr()
    db.cursor().execute("INSERT INTO tce_pb_despesa VALUES ('44444444000194', NULL)")
    db.cursor().execute("INSERT INTO web_cache VALUES ('EMPRESA_PERFIL','33333333000193')")
    limites = {t: 100 for t in RFB_TABLES}
    modo = {"tables": ("estabelecimento",)} if parcial else {"refresh": False}
    assert _sync("2026-09", tmp_path, max_delete_pct=limites, **modo) == 3
    assert capsys.readouterr().out.strip() == "RFB_SYNC_RESULT=publicacao_pendente"
    assert _rows(db, "SELECT status, stats->'dados_aplicados' FROM rfb_sync_log ORDER BY id DESC LIMIT 1"
                 ) == [("publicacao_pendente", True)]
    assert rfb_sync._last_success(db) == "2026-08"
    with pytest.raises(RuntimeError, match="pendente"):
        SOURCE_REFRESH_FNS["rfb"](db)
    assert _rows(db, "SELECT cnpj_completo, mudanca FROM rfb_sync_estab_delta ORDER BY 1") == [
        ("33333333000193", "removido"), ("44444444000194", "inserido")]
    assert _rows(db, "SELECT cnpj_basico FROM tce_pb_despesa") == [(None,)]
    assert _rows(db, "SELECT count(*) FROM web_cache") == [(1,)]
    assert _sync("2026-10", tmp_path) == 2  # não atravessa a pendência
    assert _sync("2026-09", tmp_path, max_delete_pct=limites) == 0
    assert rfb_sync._last_success(db) == "2026-09"
    assert _rows(db, "SELECT cnpj_basico FROM tce_pb_despesa") == [("44444444",)]
    assert _rows(db, "SELECT count(*) FROM web_cache") == [(0,)]
    assert _rows(db, "SELECT count(*) FROM rfb_sync_estab_delta") == [(0,)]


def _estado_negocio(db):
    tabelas = (*rfb_sync.SYNC_ORDER, *rfb_sync.DOMAIN_FILES.values(),
               "socio_historico", "rfb_sync_estab_delta", "web_cache", "tce_pb_despesa")
    return {t: _rows(db, f"SELECT xmin, t.* FROM {t} t ORDER BY t") for t in tabelas}


@pytest.mark.parametrize("compensado", [False, True], ids=["103x104", "falta-compensa-sobra"])
def test_multiplicidade_live_recusada_antes_de_empresa(db, fake_webdav, tmp_path, compensado):
    socios = MONTH_A["Socios"] + [_socio("55555555", f"CONTROLE {n}", "") for n in range(100)]
    fake_webdav("2026-08", dict(MONTH_A, Socios=socios))
    fake_webdav("2026-09", dict(MONTH_B, Socios=socios))
    assert _sync("2026-08", tmp_path) == 0
    cols = ", ".join(SOCIO.columns)
    db.cursor().execute(f"INSERT INTO socio ({cols}) SELECT {cols} FROM socio WHERE nome='JOAO'")
    if compensado:
        db.cursor().execute("DELETE FROM socio WHERE nome='MARIA'")
    antes = _estado_negocio(db)
    # Nem o escopo parcial nem --force desabilitam a barreira.
    modo = {"tables": ("empresa",), "force": True} if compensado else {}
    assert _sync("2026-09", tmp_path, max_delete_pct={t: 100 for t in RFB_TABLES}, **modo) == 2
    assert _estado_negocio(db) == antes
    status, plano = _rows(db, "SELECT status, stats->'socio' FROM rfb_sync_log ORDER BY id DESC LIMIT 1")[0]
    assert status == "aborted"
    assert (plano["staging"], plano["live_antes"]) == (103, 103 if compensado else 104)
    assert (plano["identidades_multiplas_live"], plano["a_inserir"]) == (1, int(compensado))


@pytest.mark.parametrize("defeito", ["atributo-conflitante", "conversao-iguala", "ultimo-dominio-invalido"])
def test_recusa_arquivo_ambiguo_antes_do_primeiro_lote(db, fake_webdav, tmp_path, defeito):
    fake_webdav("2026-08", MONTH_A)
    if defeito == "ultimo-dominio-invalido":
        dados = dict(MONTH_B, Motivos=[])
    else:
        faixa = "6" if defeito == "atributo-conflitante" else "05"
        dados = dict(MONTH_B, Socios=MONTH_B["Socios"] + [_socio("11111111", "JOAO", "***111111**", faixa=faixa)])
    fake_webdav("2026-09", dados)
    assert _sync("2026-08", tmp_path) == 0
    antes = _estado_negocio(db)
    assert _sync("2026-09", tmp_path, max_delete_pct={t: 100 for t in RFB_TABLES}) == 2
    assert _estado_negocio(db) == antes
    assert _rows(db, "SELECT status FROM rfb_sync_log ORDER BY id DESC LIMIT 1") == [("aborted",)]


def test_pos_condicao_recusa_chave_trocada_com_mesmo_total(db, fake_webdav, tmp_path):
    fake_webdav("2026-08", MONTH_A)
    db.cursor().execute("""
        CREATE OR REPLACE FUNCTION trocar_nome_teste() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN NEW.nome := 'OUTRA IDENTIDADE'; RETURN NEW; END $$;
        CREATE TRIGGER teste BEFORE INSERT ON socio FOR EACH ROW EXECUTE FUNCTION trocar_nome_teste()
    """)
    assert _sync("2026-08", tmp_path) == 1
    assert _rows(db, "SELECT count(*) FROM socio") == [(3,)]
    assert _rows(db, "SELECT n FROM teste_rfb_l1") == [(0,)]
    assert _rows(db, "SELECT count(*) FROM rfb_sync_estab_delta") == [(3,)]
    assert _rows(db, "SELECT status FROM rfb_sync_log") == [("failed",)]


def test_falha_apos_relink_antes_de_l2_preserva_delta(db, fake_webdav, tmp_path, monkeypatch):
    fake_webdav("2026-08", MONTH_A)
    db.cursor().execute("INSERT INTO tce_pb_despesa VALUES ('11111111000191', NULL)")
    with monkeypatch.context() as m:
        m.setattr(refresh, "_TCE_PB_MVS_L2", ("teste_l2_ausente",))
        assert _sync("2026-08", tmp_path) == 1
    assert _rows(db, "SELECT cnpj_basico FROM tce_pb_despesa") == [("11111111",)]
    assert _rows(db, "SELECT count(*) FROM rfb_sync_estab_delta") == [(3,)]
    assert rfb_sync._last_success(db) is None
    assert _sync("2026-08", tmp_path) == 0
    assert _rows(db, "SELECT n FROM teste_rfb_l2") == [(3,)]
    assert _rows(db, "SELECT count(*) FROM rfb_sync_estab_delta") == [(0,)]


def test_falha_na_marca_integral_desfaz_baixa_do_delta(db, fake_webdav, tmp_path, monkeypatch):
    fake_webdav("2026-08", MONTH_A)
    original = rfb_sync._update_log

    def falha(conn, log_id, status, stats, erro=None):
        if status == "success":
            raise RuntimeError("falha injetada na confirmação final")
        original(conn, log_id, status, stats, erro)

    monkeypatch.setattr(rfb_sync, "_update_log", falha)
    assert _sync("2026-08", tmp_path) == 1
    assert rfb_sync._last_success(db) is None
    assert _rows(db, "SELECT count(*) FROM rfb_sync_estab_delta") == [(3,)]


def test_migracao_preserva_auditoria_historica_e_skip_nao_encobre_pendencia(db, fake_webdav, tmp_path):
    rfb_sync.apply_schema(db)
    db.cursor().execute("""
        ALTER TABLE rfb_sync_log DROP CONSTRAINT rfb_sync_log_status_v2,
            ADD CHECK (status IN ('running','success','failed','aborted'));
        INSERT INTO rfb_sync_log (rfb_mes, status, stats) VALUES
            ('2026-08','success','{}'), ('2026-09','success','{"tabelas_parciais":["socio"]}');
    """)
    historico = _rows(db, "SELECT * FROM rfb_sync_log ORDER BY id")
    fake_webdav("2026-08", MONTH_A)
    assert _sync("2026-08", tmp_path) == 0  # sucesso legado, sem exigir novos campos
    assert _rows(db, "SELECT * FROM rfb_sync_log ORDER BY id") == historico
    assert _sync("2026-08", tmp_path, force=True, refresh=False) == 3
    assert _sync("2026-08", tmp_path) == 0  # precisa publicar, não pular
    assert _rows(db, "SELECT status FROM rfb_sync_log ORDER BY id DESC LIMIT 1") == [("success",)]
    assert _rows(db, "SELECT count(*) FROM rfb_sync_estab_delta") == [(0,)]



def test_retry_nao_mistura_republicacao_do_mesmo_tamanho(db, fake_webdav, tmp_path):
    mes = "2026-08"
    fake_webdav(mes, MONTH_A)
    assert _sync(mes, tmp_path, tables=("empresa",)) == 3
    manifesto, = _rows(db, "SELECT stats->'manifesto' FROM rfb_sync_log")[0]
    assert len(manifesto) == 37
    zip_path = tmp_path / f"src-{mes}" / "Empresas0.zip"
    with zipfile.ZipFile(zip_path) as z:
        membro, = z.infolist()
        original = z.read(membro)
    empresas = _rows(db, "SELECT cnpj_basico,razao_social FROM empresa ORDER BY 1")
    alterado = original.replace(b"ALFA", b"BETA")
    assert alterado != original
    with zipfile.ZipFile(zip_path, "w") as z:
        z.writestr(membro, alterado)
    assert zip_path.stat().st_size == manifesto["Empresas0.zip"]["zip_bytes"]
    assert _sync(mes, tmp_path, force=True) == 2
    assert _rows(db, "SELECT cnpj_basico,razao_social FROM empresa ORDER BY 1") == empresas
    assert _rows(db, "SELECT count(*) FROM estabelecimento") == [(0,)]
    assert _rows(db, "SELECT status,stats ? 'aplicacao_iniciada' FROM rfb_sync_log ORDER BY id DESC LIMIT 1") == [
        ("aborted", False)]


def test_retry_apos_falha_entre_lotes_preserva_historico_e_delta(db, fake_webdav, tmp_path, monkeypatch):
    fake_webdav("2026-08", MONTH_A)
    fake_webdav("2026-09", MONTH_B)
    assert _sync("2026-08", tmp_path) == 0
    db.cursor().execute("INSERT INTO tce_pb_despesa VALUES ('44444444000194', NULL)")
    id_controle = _rows(db, "SELECT id FROM socio WHERE nome='JOAO'")
    id_saida = _rows(db, "SELECT id FROM socio WHERE nome='MARIA'")
    limites = {t: 100 for t in RFB_TABLES}
    original = rfb_sync._exec

    def falha(conn, sql, params=None):
        if sql.startswith("WITH gone AS") and "t.cnpj_basico >= '22'" in sql:
            raise RuntimeError("falha injetada após commit do prefixo 11")
        return original(conn, sql, params)

    with monkeypatch.context() as m:
        m.setattr(rfb_sync, "_exec", falha)
        assert _sync("2026-09", tmp_path, max_delete_pct=limites) == 1
    assert _rows(db, "SELECT id FROM socio_historico WHERE nome='MARIA'") == id_saida
    assert _rows(db, "SELECT count(*) FROM rfb_sync_estab_delta") == [(2,)]
    assert _rows(db, "SELECT cnpj_basico FROM tce_pb_despesa") == [(None,)]
    assert _sync("2026-09", tmp_path, max_delete_pct=limites) == 0
    stats = _rows(db, "SELECT stats FROM rfb_sync_log WHERE status = 'success' ORDER BY id DESC LIMIT 1")[0][0]
    assert stats["estabelecimento"]["inseridas"] == 0
    assert _rows(db, "SELECT id FROM socio_historico WHERE nome='MARIA'") == id_saida
    assert _rows(db, "SELECT id FROM socio WHERE nome='JOAO'") == id_controle
    assert _rows(db, "SELECT count(*) FROM rfb_sync_estab_delta") == [(0,)]
    assert _rows(db, "SELECT cnpj_basico FROM tce_pb_despesa") == [("44444444",)]


def test_historico_aceita_id_repetido(db, fake_webdav, tmp_path):
    """socio recriado (02_schema_rfb) reinicia o SERIAL: o mesmo id original
    pode voltar ao historico sem violar chave."""
    fake_webdav("2026-08", MONTH_A)
    assert _sync("2026-08", tmp_path) == 0
    cur = db.cursor()
    cur.execute(
        "INSERT INTO socio_historico (id, cnpj_basico, nome, removido_em, rfb_mes_removido) "
        "SELECT id, cnpj_basico, nome, CURRENT_DATE, '2026-01' FROM socio"
    )
    cur.execute(
        "INSERT INTO socio_historico (id, cnpj_basico, nome, removido_em, rfb_mes_removido) "
        "SELECT id, cnpj_basico, nome, CURRENT_DATE, '2026-02' FROM socio"
    )
    assert _rows(db, "SELECT COUNT(*), COUNT(DISTINCT id) FROM socio_historico")[0] == (6, 3)


def test_descoberta_por_head_sem_listagem(monkeypatch):
    """PROPFIND do servidor RFB voltou vazio: meses/arquivos vem de HEAD."""
    publicados = {"2026-09": {n: 100 for n in rfb_sync.expected_zips(rfb_sync.SYNC_ORDER)},
                  "2026-10": {"Cnaes.zip": 10, "Empresas0.zip": 10}}  # mes ainda subindo
    monkeypatch.setattr(rfb_sync, "_candidate_months", lambda n=4: ["2026-10", "2026-09", "2026-08"])
    monkeypatch.setattr(rfb_sync, "head_file",
                        lambda mo, name: (publicados[mo][name], None) if name in publicados.get(mo, {}) else None)
    assert rfb_sync.list_months() == ["2026-09", "2026-10"]
    assert len(rfb_sync.list_files("2026-09")) == 37
    assert rfb_sync.resolve_month("latest") == "2026-09"  # 2026-10 incompleto


def test_empresa_sem_razao_social_nao_derruba_sync(db, fake_webdav, tmp_path):
    """2026-09 trouxe 2 empresas com razao_social vazia (natureza '0000').
    Existente: fica intocada (nem update nem delete). Nova: nao entra."""
    fake_webdav("2026-08", MONTH_A)
    vazia = _q("11111111", "", "0000", "00", "0,00", "", "")          # existente
    nova_vazia = _q("55555555", "", "0000", "00", "0,00", "", "")     # nova
    fake_webdav("2026-09", dict(MONTH_A, Empresas=[vazia, nova_vazia] + MONTH_A["Empresas"][1:]))
    assert _sync("2026-08", tmp_path) == 0
    antes = _rows(db, "SELECT * FROM empresa WHERE cnpj_basico = '11111111'")

    assert _sync("2026-09", tmp_path) == 0
    assert _rows(db, "SELECT * FROM empresa WHERE cnpj_basico = '11111111'") == antes
    assert _rows(db, "SELECT COUNT(*) FROM empresa WHERE cnpj_basico = '55555555'")[0][0] == 0
    stats = _rows(db, "SELECT stats FROM rfb_sync_log ORDER BY id DESC LIMIT 1")[0][0]
    assert stats["empresa"]["incompletas_ignoradas"] == 2
    assert stats["empresa"]["removidas"] == 0


def test_download_retoma_apos_reset(tmp_path, monkeypatch):
    """Servidor derruba a conexao no meio; a 2a tentativa continua via Range."""
    import http.server
    import threading

    payload = bytes(range(256)) * 4000  # ~1 MB
    calls = []

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            rng = self.headers.get("Range")
            calls.append(rng)
            if rng is None:  # 1a: manda metade e derruba
                self.send_response(200)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload[: len(payload) // 2])
                self.wfile.flush()
                self.connection.shutdown(2)
                return
            start = int(rng.split("=")[1].rstrip("-"))
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{len(payload)-1}/{len(payload)}")
            self.send_header("Content-Length", str(len(payload) - start))
            self.end_headers()
            self.wfile.write(payload[start:])

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(rfb_sync, "WEBDAV_BASE", f"http://127.0.0.1:{srv.server_address[1]}")
        monkeypatch.setattr(rfb_sync.time, "sleep", lambda s: None)
        out = rfb_sync.download_zip("2026-09", "X.zip", len(payload), tmp_path)
    finally:
        srv.shutdown()
    assert out.read_bytes() == payload
    assert calls[0] is None and calls[1] == f"bytes={len(payload) // 2}-"



def test_snapshot_com_muitas_razoes_vazias_aborta_sem_tocar_live(db, fake_webdav, tmp_path, monkeypatch):
    """Revisao PR #209: incompletos em massa (formato mudou) abortam ANTES do
    primeiro lote, em vez de virar 'success' com a tabela parada."""
    monkeypatch.setattr(rfb_sync, "MAX_INCOMPLETE_ROWS", 1)
    fake_webdav("2026-08", MONTH_A)
    sem_nome = [_q(cb, "", "2062", "49", "1,00", "01", "") for cb in ("11111111", "22222222", "33333333")]
    fake_webdav("2026-09", dict(MONTH_B, Empresas=sem_nome))
    assert _sync("2026-08", tmp_path) == 0
    antes = _rows(db, "SELECT * FROM empresa ORDER BY 1")
    assert _sync("2026-09", tmp_path, max_delete_pct={t: 100 for t in RFB_TABLES}) == 2
    assert _rows(db, "SELECT * FROM empresa ORDER BY 1") == antes
    assert _rows(db, "SELECT status FROM rfb_sync_log ORDER BY id DESC LIMIT 1") == [("aborted",)]
