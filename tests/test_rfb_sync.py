"""Testes do sync mensal RFB (etl/rfb_sync.py).

Unitarios rodam sempre. Os de integracao precisam de um Postgres DESCARTAVEL:

    TEST_RFB_DSN="host=/tmp port=54329 dbname=rfb_sync_test user=postgres" pytest tests/test_rfb_sync.py

O fixture RECRIA as tabelas RFB (sql/02_schema_rfb.sql faz DROP TABLE), por
isso recusa qualquer banco cujo nome nao contenha "test".
"""
from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path

import psycopg2
import pytest

from etl import rfb_sync
from etl.refresh_post_incremental import SOURCE_REFRESH_FNS, relink_cnpj_basico_after_rfb
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
    for prefix, rows in {**data, **DOMAIN}.items():
        spec = next((s for s in RFB_TABLES.values() if s.file_prefix == prefix), None)
        names = spec.file_names() if spec else [prefix]
        for i, name in enumerate(names):
            chunk = rows if i == 0 else []  # tudo no arquivo 0; demais vazios
            zpath = d / f"{name}.zip"
            with zipfile.ZipFile(zpath, "w") as z:
                body = "".join(r + "\n" for r in chunk).encode("latin-1")
                z.writestr(f"K3241.K03200Y{i}.D60912.{prefix.upper()}CSV", body)
            out[f"{name}.zip"] = zpath
    return out


@pytest.fixture
def db():
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
        cur.execute("DROP TABLE IF EXISTS rfb_sync_log, socio_historico, rfb_sync_estab_delta, tce_pb_despesa")
        cur.execute("CREATE TABLE tce_pb_despesa (cpf_cnpj VARCHAR(14), cnpj_basico CHAR(8))")
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
    opts = rfb_sync.SyncOptions(month=month, work_dir=tmp_path / "work", min_free_gb=0, refresh=False, **kw)
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
    assert _rows(db, "SELECT cnpj_completo, mudanca FROM rfb_sync_estab_delta ORDER BY 1") == [
        ("33333333000193", "removido"), ("44444444000194", "inserido"),
    ]
    assert _rows(db, "SELECT descricao FROM dom_qualificacao WHERE codigo = '05'") == [("Administrador",)]
    status = _rows(db, "SELECT rfb_mes, status FROM rfb_sync_log ORDER BY id")
    assert status == [("2026-08", "success"), ("2026-09", "success")]
    assert _rows(db, "SELECT COUNT(*) FROM pg_tables WHERE tablename LIKE '\\_rfb\\_sync\\_%'")[0][0] == 0

    # Relink direcionado: credor novo ganha cnpj_basico, removido perde
    relink_cnpj_basico_after_rfb(db)
    assert _rows(db, "SELECT cpf_cnpj, cnpj_basico FROM tce_pb_despesa ORDER BY 1") == [
        ("33333333000193", None), ("44444444000194", "44444444"),
    ]

    # Idempotencia / protecoes de ordem
    assert _sync("2026-09", tmp_path) == 0
    assert "RFB_SYNC_RESULT=skipped" in capsys.readouterr().out
    assert _sync("2026-08", tmp_path) == 2  # regrediria a base


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
