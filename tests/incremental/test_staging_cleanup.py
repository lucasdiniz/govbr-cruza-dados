"""Regressões de limpeza de staging incremental."""

from pathlib import Path

from etl.incremental.staging import PG_IDENT_MAX, drop_staging, staging_name


class _Cursor:
    def __init__(self, failures):
        self.failures = failures

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql):
        if any(name in sql for name in self.failures):
            raise RuntimeError("drop failed")


class _Connection:
    def __init__(self, failures=()):
        self.failures = failures

    def cursor(self):
        return _Cursor(self.failures)


def test_drop_staging_returns_only_failed_tables():
    failed = drop_staging(
        _Connection(failures=("typed",)),
        "etl_staging._stg_run_raw",
        "etl_staging._stg_run_typed",
    )

    assert failed == ["etl_staging._stg_run_typed"]


def test_janitor_regex_accepts_bucket_names():
    sql = Path("sql/44_fix_cleanup_orphan_staging.sql").read_text(encoding="utf-8")

    assert "[a-zA-Z0-9_]{1,8}" in sql
    assert "status = 'running'" in sql
    assert "IF EXISTS" in sql
    assert "^_stg_([a-f0-9]{8})_" in sql
    assert "^_stg_.+_([a-f0-9]{8})_" in sql


def test_staging_name_fallback_preserves_run_prefix():
    run_id = "12345678-1234-1234-1234-123456789abc"

    name = staging_name(
        "fonte_com_nome_muito_longo",
        "tabela_com_nome_ainda_mais_longo",
        run_id,
        1234567890,
        "typed",
        bucket_id="2026-05",
    )

    assert "_stg_12345678_2026_05_1234567890_typed" in name
    assert len(name.split(".", 1)[1]) <= PG_IDENT_MAX
