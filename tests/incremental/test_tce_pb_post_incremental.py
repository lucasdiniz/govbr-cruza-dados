"""Regressoes do hook pos-incremental TCE-PB."""

import pytest

from etl.refresh_post_incremental import (
    _TCE_PB_NORMALIZATION_UPDATES,
    _rebuild_servidor_tmp_after_tce_pb,
    normalize_tce_pb_incremental,
)


class _Cursor:
    def __init__(self, executed, functions):
        self.executed = executed
        self.functions = functions
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql):
        self.executed.append(sql)

    def fetchone(self):
        return self.functions


class _Connection:
    autocommit = False

    def __init__(self, functions=(True, True)):
        self.executed = []
        self.commits = 0
        self.functions = functions

    def cursor(self):
        return _Cursor(self.executed, self.functions)

    def commit(self):
        self.commits += 1


def test_normalize_tce_pb_incremental_executes_all_updates():
    conn = _Connection()

    counts = normalize_tce_pb_incremental(conn)

    assert len(conn.executed) == len(_TCE_PB_NORMALIZATION_UPDATES) + 1
    assert conn.commits == len(_TCE_PB_NORMALIZATION_UPDATES)
    assert all(count == 1 for count in counts.values())


def test_servidor_normalization_restores_mv_join_columns():
    servidor_sql = _TCE_PB_NORMALIZATION_UPDATES[0][1]

    assert "cpf_digitos_6" in servidor_sql
    assert "REGEXP_REPLACE(cpf_cnpj" in servidor_sql
    assert "nome_upper" in servidor_sql
    assert "UPPER(TRIM(nome_servidor))" in servidor_sql


def test_normalization_fails_before_updates_without_document_functions():
    conn = _Connection(functions=(False, True))

    with pytest.raises(RuntimeError, match="is_valid_cpf"):
        normalize_tce_pb_incremental(conn)

    assert len(conn.executed) == 1
    assert conn.commits == 0


def test_despesa_normalization_preserves_cpf_cnpj_guard():
    cnpj_sql = _TCE_PB_NORMALIZATION_UPDATES[1][1]
    cpf_sql = _TCE_PB_NORMALIZATION_UPDATES[2][1]

    assert "EXISTS" in cnpj_sql
    assert "estabelecimento" in cnpj_sql
    assert "is_valid_cnpj(d.cpf_cnpj::TEXT)" in cpf_sql
    assert "is_valid_cpf(SUBSTRING(d.cpf_cnpj FROM 4 FOR 11)::TEXT)" in cpf_sql


def test_tmp_rebuild_preserves_backing_table_oids(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        "etl.refresh_post_incremental._read_sql_file",
        lambda name: (
            "TRUNCATE TABLE _tmp_socio_empresas"
            if name == "43_tmp_servidor_post_incremental.sql"
            else "SELECT 1"
        ),
    )
    monkeypatch.setattr(
        "etl.refresh_post_incremental._run_sql",
        lambda conn, label, sql: captured.update(label=label, sql=sql),
    )

    _rebuild_servidor_tmp_after_tce_pb(object())

    assert "TRUNCATE TABLE _tmp_socio_empresas" in captured["sql"]
    assert "TRUNCATE TABLE _tmp_bf" in captured["sql"]
    assert "DROP TABLE _tmp_" not in captured["sql"]
