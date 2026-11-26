"""Rejeições, commits e saída do entrypoint. Integração só em PG descartável local."""
import hashlib
import os
import sys
import uuid

import psycopg2
import pytest

from etl.incremental import db, orchestrator, runner
from etl.incremental.spec import CursorStrategy, DedupeStrategy, LoaderSpec


def test_zip_com_membro_errado_nao_reaproveita_csv_antigo(tmp_path, monkeypatch):
    import io
    import zipfile
    from etl.incremental import download
    resposta = io.BytesIO()
    with zipfile.ZipFile(resposta, "w") as arq:
        arq.writestr("outro.csv", "coluna\nnovo\n")
    resposta.headers = {"Content-Length": str(resposta.tell())}
    resposta.status = 200
    resposta.seek(0)
    monkeypatch.setattr(download, "urlopen", lambda *_, **kw: resposta)
    destino = tmp_path / "fonte.zip"
    destino.write_bytes(b"anterior")
    (tmp_path / "pedido.csv").write_text("anterior")
    res = download.conditional_download(govbr_conn=None, run_id=uuid.uuid4(), source="teste",
        table="teste", bucket_id="2026", url="https://example.invalid/fonte.zip", dest_path=destino,
        force_refetch=True, membros_esperados=("pedido.csv",))
    assert res.status == "failed"
    assert destino.read_bytes() == b"anterior"
    assert (tmp_path / "pedido.csv").read_text() == "anterior"


@pytest.fixture
def recorte(tmp_path):
    dsn = os.getenv("TEST_INTEGRIDADE_DSN")
    if not dsn:
        pytest.skip("requer TEST_INTEGRIDADE_DSN com migrations 22–29 e 33")
    conn = psycopg2.connect(dsn)
    if not conn.info.dbname.endswith("_test") or not conn.info.host.startswith("/"):
        conn.close()
        pytest.fail("fixture exige socket Unix e banco descartável *_test")
    conn.autocommit = True
    tabela = "teste_fase_" + uuid.uuid4().hex[:12]
    with conn.cursor() as c:
        c.execute(f"CREATE TABLE {tabela} (chave text PRIMARY KEY, competencia text, valor numeric)")
        c.execute(f"GRANT SELECT, INSERT, UPDATE ON {tabela} TO etl_incremental")
    spec = LoaderSpec(
        source="teste", table=tabela, columns=["chave", "competencia", "valor"],
        column_types={"chave":"TEXT", "competencia":"TEXT", "valor":"NUMERIC"},
        natural_key=["chave"], watermark_col="competencia",
        cursor_strategy=CursorStrategy.YEAR_WINDOW, dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
        csv_delimiter=";", decimal_format="br",
        file_pattern=lambda ano:[f"{ano}.csv"], bucket_from_filename=lambda n:n[:4],
    )
    def executar(*anos):
        return orchestrator.run_incremental_for_source(
            spec, data_dir=tmp_path, govbr_dsn=dsn,
            dsn=psycopg2.extensions.make_dsn(dsn, user="etl_incremental"), only_buckets=list(anos),
        )
    def ler(sql, params=()):
        with conn.cursor() as c:
            c.execute(sql, params)
            return c.fetchall()
    def arquivo(ano, dados):
        p = tmp_path / f"{ano}.csv"
        p.write_text("chave;competencia;valor\n" + dados, encoding="utf-8")
        return hashlib.sha256(p.read_bytes()).hexdigest()
    try:
        yield tabela, executar, ler, arquivo
    finally:
        with conn.cursor() as c:
            c.execute(f"DROP TABLE {tabela}")
        conn.close()


def test_arquivo_rejeitado_nao_pula_competencia_e_retry_nao_duplica(recorte):
    t, executar, ler, arquivo = recorte
    sha = arquivo("2025", "a;2025;11,00\n ;2025;7,00\n ;2025;7,00\n")
    arquivo("2026", "b;2026;9,00\n")
    for _ in range(2):
        res = executar("2025","2026")
        assert res["status"] == "failed"
        assert ler(f"SELECT count(*) FROM {t}") == [(0,)]
        assert ler("SELECT status,rows_streamed,rows_inserted,rows_rejected_null_key "
                   "FROM etl_phase_log WHERE run_id=%s", (str(res["run_id"]),)) == [("partial",3,0,2)]
        assert not ler("SELECT last_value FROM etl_watermark WHERE table_name=%s", (t,))
        assert ler("SELECT line_number FROM etl_rejected_rows WHERE table_name=%s AND "
                   "right(file_path,64)=%s ORDER BY 1", (t,sha)) == [(3,), (4,)]
    arquivo("2025", "a;2025;11,00\na;2025;11,00\n")
    for esperados in ((1,1),(0,2)):
        res = executar("2025","2026")
        assert res["status"] == "success"
        assert ler("SELECT rows_inserted,rows_skipped_dup FROM etl_phase_log WHERE run_id=%s "
                   "ORDER BY id LIMIT 1", (str(res["run_id"]),)) == [esperados]
    assert ler(f"SELECT count(*),sum(valor)*100 FROM {t}") == [(2,2000)]
    assert ler("SELECT last_value FROM etl_watermark WHERE table_name=%s", (t,)) == [("2026",)]
    assert ler("SELECT count(*) FROM etl_cache_invalidation_queue WHERE table_name=%s", (t,)) == [(2,)]


def test_falha_na_marca_reverte_fase_dados_e_pendencia(recorte, monkeypatch):
    t, executar, ler, arquivo = recorte
    arquivo("2025", "a;2025;1,00\n")
    def falhar(*args, **kwargs):
        raise ValueError("Falha sintética antes de confirmar marca")
    monkeypatch.setattr(db, "set_watermark", falhar)
    res = executar("2025")
    assert res["status"] == "failed"
    assert ler(f"SELECT count(*) FROM {t}") == [(0,)]
    assert ler("SELECT status,rows_inserted FROM etl_phase_log WHERE run_id=%s",
               (str(res["run_id"]),)) == [("failed",0)]
    assert not ler("SELECT id FROM etl_cache_invalidation_queue WHERE table_name=%s", (t,))


def test_falha_de_dlq_nao_fica_verde(recorte, monkeypatch):
    from etl.incremental import parser
    t, executar, ler, arquivo = recorte
    arquivo("2025", "a;2025;11,00\ncampos;faltantes\n")
    def dlq_indisponivel(*args):
        raise RuntimeError("DLQ indisponível")
    monkeypatch.setattr(parser, "_dlq_insert", dlq_indisponivel)
    res = executar("2025")
    assert res["status"] == "failed"
    assert ler(f"SELECT count(*) FROM {t}") == [(0,)]
    assert not ler("SELECT last_value FROM etl_watermark WHERE table_name=%s", (t,))


def test_bucket_solicitado_ausente_bloqueia_escopo(recorte):
    t, executar, ler, arquivo = recorte
    arquivo("2025", "a;2025;11,00\n")
    assert executar("2025","2026")["status"] == "failed"
    assert ler(f"SELECT count(*) FROM {t}") == [(0,)]


@pytest.mark.parametrize("estado", ["partial", "aborted", "failed"])
def test_cli_recusa_publicacao_incompleta(monkeypatch, tmp_path, estado):
    from etl.incremental.specs.bolsa_familia import SPEC
    monkeypatch.setattr(runner, "_load_all_specs", lambda: {"bf.bf":SPEC})
    monkeypatch.setattr(runner, "_auto_bootstrap_if_needed", lambda *_: [])
    monkeypatch.setattr(orchestrator, "run_incremental_for_source", lambda *a, **k: {"status":estado, "buckets":[]})
    monkeypatch.setattr(sys, "argv", ["runner","--only","bf.bf","--only-buckets","2026-10",
                                     "--dsn","ignorado","--data-dir",str(tmp_path)])
    assert runner.main() != 0
