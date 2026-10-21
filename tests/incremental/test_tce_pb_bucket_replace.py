"""Replace por bucket TCE-PB (ADR-0015, sql/46) — integração com Postgres real.

Roda contra um banco DESCARTÁVEL (recria as tabelas tce_pb_*):

    TEST_TCE_PB_DSN="host=/tmp port=5433 dbname=govbr_test user=govbr" \\
        pytest tests/incremental/test_tce_pb_bucket_replace.py

Sem TEST_TCE_PB_DSN os testes de integração são pulados; os testes de
spec/runner rodam sempre.
"""

from __future__ import annotations

import dataclasses
import os
import re
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from etl.incremental.replace import (
    DRY_RUN_ENV, ReplaceDryRun, ReplaceGuardError, apply_bucket_replace,
)
from etl.incremental.runner import _replace_problems
from etl.incremental.spec import BucketReplace, ConfigError, DedupeStrategy
from etl.incremental.specs import tce_pb_despesa, tce_pb_receita
from etl.incremental.staging import build_upsert_sql

ROOT = Path(__file__).resolve().parents[2]
TEST_DSN = os.environ.get("TEST_TCE_PB_DSN")

DESPESA = tce_pb_despesa.SPEC
RECEITA = tce_pb_receita.SPEC


# ─── Spec / runner (sem banco) ────────────────────────────────────────────────

def test_specs_tce_pb_anuais_usam_replace():
    assert DESPESA.bucket_replace is not None
    assert RECEITA.bucket_replace is not None
    assert tce_pb_despesa.SPEC.nk_synthetic_md5


def test_bucket_replace_exige_md5_e_do_nothing():
    with pytest.raises(ConfigError, match="nk_synthetic_md5"):
        dataclasses.replace(DESPESA, nk_synthetic_md5=False)
    with pytest.raises(ConfigError, match="UPSERT_DO_NOTHING"):
        dataclasses.replace(DESPESA, dedupe_strategy=DedupeStrategy.APPEND)
    with pytest.raises(ConfigError, match="1 file"):
        dataclasses.replace(DESPESA, file_pattern=lambda b: ["a.csv", "b.csv"])


def test_bucket_replace_limites_validos():
    with pytest.raises(ConfigError):
        BucketReplace(max_orphan_pct=150)
    with pytest.raises(ConfigError):
        BucketReplace(min_orphan_abs=-1)


def test_spec_hash_de_specs_sem_replace_nao_muda():
    sem = dataclasses.replace(DESPESA, bucket_replace=None)
    assert sem.spec_hash != DESPESA.spec_hash
    # Sem replace o canonical nao ganha a chave nova (hash historico preservado).
    import hashlib, json
    canonical = {
        k: v for k, v in json.loads(json.dumps({
            "source": sem.source, "table": sem.table, "target_schema": sem.target_schema,
            "natural_key": list(sem.natural_key), "cursor_strategy": sem.cursor_strategy.value,
            "dedupe_strategy": sem.dedupe_strategy.value, "columns": list(sem.columns),
            "column_types": dict(sem.column_types), "csv_delimiter": sem.csv_delimiter,
            "watermark_col": sem.watermark_col, "watermark_type": sem.watermark_type,
            "encoding": sem.encoding, "encoding_fallback": sem.encoding_fallback,
            "decimal_format": sem.decimal_format, "date_format": sem.date_format,
            "default_null_sentinels": list(sem.default_null_sentinels),
            "column_overrides": dict(sem.column_overrides),
            "derived_columns": dict(sem.derived_columns), "is_zip_source": sem.is_zip_source,
            "bootstrap_tolerance_pct": sem.bootstrap_tolerance_pct,
            "csv_header_rewrites": dict(sem.csv_header_rewrites),
        })).items()
    }
    expected = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    assert sem.spec_hash == expected


def test_runner_trata_bucket_replace_falho_como_erro():
    falho = SimpleNamespace(
        bucket_id="2026", all_success=False,
        files=[(Path("x.csv"), SimpleNamespace(error="GUARDA_REPLACE G3: ..."))],
    )
    ok = SimpleNamespace(bucket_id="2025", all_success=True, files=[])
    summary = {"status": "partial", "buckets": [ok, falho]}
    problems = _replace_problems("tce_pb.tce_pb_despesa", DESPESA, summary)
    assert problems == ["tce_pb.tce_pb_despesa bucket 2026: GUARDA_REPLACE G3: ..."]
    # Spec sem replace: bucket falho segue a regra antiga (partial nao falha).
    assert _replace_problems("x.y", dataclasses.replace(DESPESA, bucket_replace=None), summary) == []
    # Download falho (sem arquivo processado) tambem e erro.
    sem_arquivo = SimpleNamespace(bucket_id="2024", all_success=False, files=[])
    assert _replace_problems("k", DESPESA, {"status": "partial", "buckets": [sem_arquivo]}) == [
        "k bucket 2024: download falhou / arquivo ausente"
    ]
    # "Sucesso" sem replace executado (ex.: caminho futuro que pule o replace).
    sem_replace = SimpleNamespace(
        bucket_id="2023", all_success=True,
        files=[(Path("d.csv"), SimpleNamespace(error=None, replace_stats=None))],
    )
    assert _replace_problems("k", DESPESA, {"status": "success", "buckets": [sem_replace]}) == [
        "k bucket 2023: sucesso com replace nao executado (d.csv)"
    ]


# ─── Integração ───────────────────────────────────────────────────────────────

def _row_hash_fn_sql() -> str:
    """Só a etl_admin.row_hash_md5 de sql/35a (o resto do arquivo mexe em pb_*)."""
    text = (ROOT / "sql/35a_pb_extras_synthetic_nk_columns.sql").read_text()
    m = re.search(
        r"CREATE OR REPLACE FUNCTION etl_admin\.row_hash_md5.*?\$func\$.*?\$func\$[^;]*;", text, re.S
    )
    assert m, "row_hash_md5 nao encontrada em sql/35a"
    return m.group(0)


@pytest.fixture(scope="module")
def db():
    if not TEST_DSN:
        pytest.skip("TEST_TCE_PB_DSN nao definido")
    import psycopg2

    conn = psycopg2.connect(TEST_DSN)
    if "test" not in conn.get_dsn_parameters().get("dbname", ""):
        conn.close()
        pytest.fail("TEST_TCE_PB_DSN precisa apontar para um banco descartavel com 'test' no nome")
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("CREATE SCHEMA IF NOT EXISTS etl_admin")
        cur.execute(_row_hash_fn_sql())
        cur.execute("DROP TABLE IF EXISTS tce_pb_despesa_removido, tce_pb_receita_removido")
        cur.execute((ROOT / "sql/19_schema_tce_pb.sql").read_text())
        cur.execute((ROOT / "sql/42_tce_pb_synthetic_nk.sql").read_text())
        for t in ("despesa", "servidor", "licitacao", "receita"):
            cur.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS ix_tce_pb_{t}_nk_md5 ON tce_pb_{t} (_nk_md5)"
            )
        cur.execute((ROOT / "sql/46_tce_pb_bucket_replace.sql").read_text())
    conn.autocommit = False
    yield conn
    conn.close()


@pytest.fixture
def clean(db):
    with db.cursor() as cur:
        cur.execute(
            "TRUNCATE tce_pb_despesa, tce_pb_receita, "
            "tce_pb_despesa_removido, tce_pb_receita_removido"
        )
    db.commit()
    yield db
    db.rollback()


_TYPED = {"NUMERIC": "NUMERIC", "DATE": "DATE", "SMALLINT": "SMALLINT"}


def _stage(conn, spec, rows: list[dict], name: str = "public._t_stg") -> str:
    """Cria uma staging 'typed' igual à do loader (nomes/tipos do CSV)."""
    cols = list(spec.columns)
    defs = ", ".join(f"{c} {_TYPED.get(spec.column_types[c], 'TEXT')}" for c in cols)
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {name}")
        cur.execute(f"CREATE TABLE {name} ({defs})")
        for r in rows:
            cur.execute(
                f"INSERT INTO {name} ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                [r.get(c) for c in cols],
            )
    return name


def _load(conn, spec, rows, bucket, run_id=None):
    """Upsert + replace na mesma transação, como o loader. Commit no fim."""
    stg = _stage(conn, spec, rows)
    with conn.cursor() as cur:
        cur.execute(build_upsert_sql(spec, stg, bucket_id=bucket))
        inserted = cur.fetchone()[0]
    stats = apply_bucket_replace(conn, spec, stg, bucket_id=bucket, run_id=run_id or uuid.uuid4())
    conn.commit()
    return inserted, stats


def _desp(n: int, *, valor_pago="100.00", fonte="Recursos nao vinculados", **kw) -> dict:
    row = {
        "municipio": "Vieirópolis", "codigo_unidade_gestora": "201221",
        "descricao_unidade_gestora": "Prefeitura", "numero_empenho": str(n),
        "data_empenho": date(2026, 7, 28), "mes": "07", "cpf_cnpj": "08320251000165",
        "nome_credor": "POSTO", "valor_empenhado": "100.00", "valor_liquidado": "100.005",
        "valor_pago": valor_pago, "descricao_fonte_recurso": fonte,
        "modalidade_licitacao": "Sem Licitação", "numero_licitacao": "000000000",
        "co": "0", "historico": "COMBUSTIVEL",
    }
    row.update(kw)
    return row


def _count(conn, sql, *args):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchone()[0]


def test_primeira_carga_nao_remove_nada(clean):
    inserted, stats = _load(clean, DESPESA, [_desp(1), _desp(2)], "2026")
    assert inserted == 2
    assert stats["removidas"] == 0
    assert stats["hashes_arquivo"] == stats["mantidas"] == 2


def test_republicacao_com_edicao_substitui_versao_antiga(clean):
    _load(clean, DESPESA, [_desp(1), _desp(2), _desp(3)], "2026")
    # TCE-PB republica: empenho 1 pago a mais, empenho 2 com descricao editada.
    run = uuid.uuid4()
    novo = [_desp(1, valor_pago="150.00"), _desp(2, fonte="Recursos não Vinculados"), _desp(3)]
    inserted, stats = _load(clean, DESPESA, novo, "2026", run)
    assert inserted == 2
    assert stats["remover_versao_substituida"] == 2
    assert stats["remover_ausente_no_arquivo"] == 0
    assert stats["removidas"] == 2
    assert _count(clean, "SELECT count(*) FROM tce_pb_despesa WHERE ano_arquivo = 2026") == 3
    assert _count(clean, "SELECT sum(valor_pago) FROM tce_pb_despesa") == 350
    # Backup: linha inteira + run + motivo.
    with clean.cursor() as cur:
        cur.execute(
            "SELECT numero_empenho, valor_pago, removido_motivo, removido_bucket "
            "FROM tce_pb_despesa_removido WHERE removido_run_id = %s ORDER BY 1",
            (str(run),),
        )
        assert cur.fetchall() == [
            ("1", 100, "versao_substituida", 2026),
            ("2", 100, "versao_substituida", 2026),
        ]


def test_rerun_identico_e_noop(clean):
    rows = [_desp(1), _desp(2)]
    _load(clean, DESPESA, rows, "2026")
    inserted, stats = _load(clean, DESPESA, rows, "2026")
    assert inserted == 0 and stats["removidas"] == 0


def test_legado_duplicado_do_etl_classico_e_removido(clean):
    """Cenário da issue #211: cópia legada (descrição antiga) + cópia nova."""
    with clean.cursor() as cur:
        cur.execute(
            """INSERT INTO tce_pb_despesa (municipio, codigo_ug, descricao_ug, numero_empenho,
                   data_empenho, mes, cpf_cnpj, nome_credor, valor_empenhado, valor_liquidado,
                   valor_pago, descricao_fonte_recurso, co, ano_arquivo)
               VALUES ('Vieirópolis','201221','Prefeitura','1','2026-07-28','07','08320251000165',
                       'POSTO',100,100.01,100,'Recursos nao vinculados (antigo)','9',2026)"""
        )
    clean.commit()
    _, stats = _load(clean, DESPESA, [_desp(1)], "2026")
    assert stats["remover_versao_substituida"] == 1
    assert _count(clean, "SELECT count(*) FROM tce_pb_despesa") == 1


def test_outros_anos_nao_sao_tocados(clean):
    _load(clean, DESPESA, [_desp(1), _desp(2)], "2025")
    _, stats = _load(clean, DESPESA, [_desp(1)], "2026")
    assert stats["linhas_bucket_antes"] == 1  # só o próprio 2026 (recém inserido)
    assert _count(clean, "SELECT count(*) FROM tce_pb_despesa WHERE ano_arquivo = 2025") == 2


def test_guarda_g3_orfaos_aborta_e_nao_grava_nada(clean):
    _load(clean, DESPESA, [_desp(i) for i in range(10)], "2026")
    spec = dataclasses.replace(DESPESA, bucket_replace=BucketReplace(max_orphan_pct=0, min_orphan_abs=3))
    stg = _stage(clean, spec, [_desp(0), _desp(1), _desp(100)])  # 8 empenhos "sumiram"
    with clean.cursor() as cur:
        cur.execute(build_upsert_sql(spec, stg, bucket_id="2026"))
    with pytest.raises(ReplaceGuardError, match="G3"):
        apply_bucket_replace(clean, spec, stg, bucket_id="2026", run_id=uuid.uuid4())
    clean.rollback()
    assert _count(clean, "SELECT count(*) FROM tce_pb_despesa") == 10  # upsert desfeito
    assert _count(clean, "SELECT count(*) FROM tce_pb_despesa_removido") == 0


def test_orfaos_dentro_do_limite_sao_removidos_com_motivo(clean):
    _load(clean, DESPESA, [_desp(i) for i in range(5)], "2026")
    _, stats = _load(clean, DESPESA, [_desp(i) for i in range(4)], "2026")
    assert stats["remover_ausente_no_arquivo"] == 1
    assert _count(
        clean, "SELECT count(*) FROM tce_pb_despesa_removido WHERE removido_motivo = 'ausente_no_arquivo'"
    ) == 1


def test_guarda_g1_receita_fora_do_ano(clean):
    def rec(ano, cod):
        return {"municipio": "Vieirópolis", "codigo_unidade_gestora": "201221",
                "descricao_unidade_gestora": "Prefeitura", "mes_ano": f"01/{ano}", "ano": ano,
                "codigo_receita": cod, "descricao_receita": "IPTU",
                "tipo_atualizacao_receita": "Lançamento de Receita", "valor": "10.00"}
    _, stats = _load(clean, RECEITA, [rec(2026, "1")], "2026")
    assert stats["removidas"] == 0
    stg = _stage(clean, RECEITA, [rec(2026, "1"), rec(2025, "2")])
    with clean.cursor() as cur:
        cur.execute(build_upsert_sql(RECEITA, stg, bucket_id="2026"))
    with pytest.raises(ReplaceGuardError, match="G1"):
        apply_bucket_replace(clean, RECEITA, stg, bucket_id="2026", run_id=uuid.uuid4())
    clean.rollback()


def test_guarda_g2_paridade_e_g4_vazio_na_funcao(clean):
    _load(clean, DESPESA, [_desp(1)], "2026")
    run = str(uuid.uuid4())
    with clean.cursor() as cur:
        cur.execute("CREATE TEMP TABLE _f (h text) ON COMMIT DROP")
        cur.execute("INSERT INTO _f SELECT _nk_md5 FROM tce_pb_despesa UNION ALL SELECT md5('x')")
        with pytest.raises(Exception, match="G2"):
            cur.execute(
                "SELECT etl_admin.tce_pb_replace_bucket('tce_pb_despesa', 2026, 'pg_temp._f'::regclass, %s)",
                (run,),
            )
    clean.rollback()
    with clean.cursor() as cur:
        cur.execute("CREATE TEMP TABLE _f (h text) ON COMMIT DROP")
        with pytest.raises(Exception, match="G4"):
            cur.execute(
                "SELECT etl_admin.tce_pb_replace_bucket('tce_pb_despesa', 2026, 'pg_temp._f'::regclass, %s)",
                (run,),
            )
    clean.rollback()
    with clean.cursor() as cur:
        cur.execute("CREATE TEMP TABLE _f (h text) ON COMMIT DROP")
        with pytest.raises(Exception, match="allowlist"):
            cur.execute(
                "SELECT etl_admin.tce_pb_replace_bucket('socio', 2026, 'pg_temp._f'::regclass, %s)",
                (run,),
            )
    clean.rollback()
    assert _count(clean, "SELECT count(*) FROM tce_pb_despesa") == 1


def test_dry_run_calcula_e_nao_remove(clean, monkeypatch):
    _load(clean, DESPESA, [_desp(1), _desp(2)], "2026")
    monkeypatch.setenv(DRY_RUN_ENV, "1")
    stg = _stage(clean, DESPESA, [_desp(1, valor_pago="999.00"), _desp(2)])
    with clean.cursor() as cur:
        cur.execute(build_upsert_sql(DESPESA, stg, bucket_id="2026"))
    with pytest.raises(ReplaceDryRun, match='"remover_versao_substituida": 1'):
        apply_bucket_replace(clean, DESPESA, stg, bucket_id="2026", run_id=uuid.uuid4())
    clean.rollback()
    assert _count(clean, "SELECT count(*) FROM tce_pb_despesa") == 2


def test_backup_restaura_linhas_removidas(clean):
    """Runbook docs/ops.md: restaurar por removido_run_id."""
    _load(clean, DESPESA, [_desp(1), _desp(2)], "2026")
    run = uuid.uuid4()
    _load(clean, DESPESA, [_desp(1)], "2026", run)
    assert _count(clean, "SELECT count(*) FROM tce_pb_despesa") == 1
    with clean.cursor() as cur:
        cur.execute(
            """SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position)
                 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'tce_pb_despesa'"""
        )
        cols = cur.fetchone()[0]
        cur.execute(
            f"""INSERT INTO tce_pb_despesa ({cols})
                SELECT {cols} FROM tce_pb_despesa_removido WHERE removido_run_id = %s
                ON CONFLICT (_nk_md5) DO NOTHING""",
            (str(run),),
        )
    clean.commit()
    assert _count(clean, "SELECT count(*) FROM tce_pb_despesa") == 2


def test_arquivo_vazio_ou_so_cabecalho_falha_em_replace(tmp_path):
    """Publicacao vazia/placeholder nunca vira 'sucesso sem replace'."""
    from etl.incremental.loader import _incremental_load

    vazio = tmp_path / "despesas-2026.csv"
    vazio.write_bytes(b"")
    res = _incremental_load(DESPESA, None, vazio, file_sequence=1, bucket_id="2026")
    assert res.status == "failed" and "G4" in res.error
    html = tmp_path / "html.csv"
    html.write_bytes(b"<!DOCTYPE html><html>Arquivo Sendo Processado</html>")
    res = _incremental_load(DESPESA, None, html, file_sequence=1, bucket_id="2026")
    assert res.status == "failed" and "G4" in res.error
    # Spec acumulativa mantem o comportamento antigo (sucesso vazio).
    acumulativa = dataclasses.replace(DESPESA, bucket_replace=None)
    res = _incremental_load(acumulativa, None, vazio, file_sequence=1, bucket_id="2026")
    assert res.status == "success"


def test_linha_com_municipio_vazio_e_mantida(clean):
    """despesas-2023 tem ~7k linhas com municipio/UG vazios: em replace elas
    entram no conjunto do arquivo (nao vao para a DLQ) e nao sao removidas."""
    rows = [_desp(1, municipio=None, codigo_unidade_gestora=None), _desp(2)]
    _load(clean, DESPESA, rows, "2026")
    inserted, stats = _load(clean, DESPESA, rows, "2026")
    assert inserted == 0 and stats["removidas"] == 0
    assert _count(clean, "SELECT count(*) FROM tce_pb_despesa WHERE municipio IS NULL") == 1


def test_p_file_precisa_ser_tabela_temp_comum(clean):
    """SECURITY DEFINER: view/tabela comum como p_file executaria codigo do
    chamador com privilegios do dono — rejeitado antes de ler."""
    _load(clean, DESPESA, [_desp(1)], "2026")
    run = str(uuid.uuid4())
    with clean.cursor() as cur:
        cur.execute("CREATE TEMP VIEW _v AS SELECT _nk_md5 AS h FROM tce_pb_despesa")
        with pytest.raises(Exception, match="TEMP comum"):
            cur.execute(
                "SELECT etl_admin.tce_pb_replace_bucket('tce_pb_despesa', 2026, 'pg_temp._v'::regclass, %s)",
                (run,),
            )
    clean.rollback()
    with clean.cursor() as cur:
        cur.execute("CREATE TABLE public._f_perm AS SELECT _nk_md5 AS h FROM tce_pb_despesa")
        with pytest.raises(Exception, match="TEMP comum"):
            cur.execute(
                "SELECT etl_admin.tce_pb_replace_bucket('tce_pb_despesa', 2026, 'public._f_perm'::regclass, %s)",
                (run,),
            )
    clean.rollback()
    with clean.cursor() as cur:
        cur.execute("CREATE TEMP TABLE _f_int ON COMMIT DROP AS SELECT 1 AS h")
        with pytest.raises(Exception, match="TEMP comum"):
            cur.execute(
                "SELECT etl_admin.tce_pb_replace_bucket('tce_pb_despesa', 2026, 'pg_temp._f_int'::regclass, %s)",
                (run,),
            )
    clean.rollback()
