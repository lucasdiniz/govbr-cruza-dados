"""Phase 1b smoke tests — validate framework core."""

from __future__ import annotations

import pytest
from etl.incremental.spec import (
    LoaderSpec, CursorStrategy, DedupeStrategy, ConfigError,
)
from etl.incremental.staging import build_upsert_sql, staging_name


# ─── LoaderSpec validation ────────────────────────────────────────────────────

def test_loader_spec_basic_validation():
    """Spec válida cria sem erro."""
    spec = LoaderSpec(
        source="test",
        table="test_table",
        natural_key=["a", "b"],
        cursor_strategy=CursorStrategy.SNAPSHOT,
        dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
        columns=["a", "b", "c"],
        column_types={"a": "TEXT", "b": "TEXT", "c": "TEXT"},
        csv_delimiter=";",
        file_pattern=lambda bid: ["test.csv"],
        bucket_from_filename=lambda n: "snapshot",
    )
    assert spec.source == "test"


def test_loader_spec_rejects_csv_delimiter_default():
    """csv_delimiter sem default obrigatório."""
    with pytest.raises(TypeError):
        LoaderSpec(
            source="test", table="t", natural_key=["a"],
            cursor_strategy=CursorStrategy.SNAPSHOT,
            dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
            columns=["a"], column_types={"a": "TEXT"},
        )


def test_loader_spec_rejects_nk_not_in_columns():
    with pytest.raises(ConfigError, match="natural_key"):
        LoaderSpec(
            source="test", table="t", natural_key=["missing_col"],
            cursor_strategy=CursorStrategy.SNAPSHOT,
            dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
            columns=["a"], column_types={"a": "TEXT"},
            csv_delimiter=";",
            file_pattern=lambda b: ["x"],
            bucket_from_filename=lambda n: "snapshot",
        )


def test_loader_spec_upsert_do_update_requires_watermark():
    with pytest.raises(ConfigError, match="UPSERT_DO_UPDATE"):
        LoaderSpec(
            source="test", table="t", natural_key=["a"],
            cursor_strategy=CursorStrategy.SNAPSHOT,
            dedupe_strategy=DedupeStrategy.UPSERT_DO_UPDATE,
            columns=["a"], column_types={"a": "TEXT"},
            csv_delimiter=";",
            file_pattern=lambda b: ["x"],
            bucket_from_filename=lambda n: "snapshot",
        )


def test_loader_spec_rejects_dynamic_sql_in_derived():
    with pytest.raises(ConfigError, match="forbidden"):
        LoaderSpec(
            source="test", table="t", natural_key=["a"],
            cursor_strategy=CursorStrategy.SNAPSHOT,
            dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
            columns=["a"], column_types={"a": "TEXT"},
            csv_delimiter=";",
            derived_columns={"x": "SELECT * FROM users"},
            file_pattern=lambda b: ["x"],
            bucket_from_filename=lambda n: "snapshot",
        )


def test_loader_spec_hash_stable():
    """spec_hash é determinístico para mesma config."""
    def _make():
        return LoaderSpec(
            source="test", table="t", natural_key=["a"],
            cursor_strategy=CursorStrategy.SNAPSHOT,
            dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
            columns=["a", "b"], column_types={"a": "TEXT", "b": "TEXT"},
            csv_delimiter=";",
            file_pattern=lambda b: ["x"],
            bucket_from_filename=lambda n: "snapshot",
        )
    s1 = _make()
    s2 = _make()
    assert s1.spec_hash == s2.spec_hash


# ─── staging_name truncate ────────────────────────────────────────────────────

import uuid

def test_staging_name_basic():
    name = staging_name("tce", "despesa", uuid.uuid4(), 1, "raw")
    assert name.startswith("etl_staging._stg_tce_despesa_")
    assert name.endswith("_raw")


def test_staging_name_truncate_under_63_bytes():
    """Nome com source/table longos deve truncar."""
    long_source = "very_long_source_name"
    long_table = "very_long_table_name_here_too"
    name = staging_name(long_source, long_table, uuid.uuid4(), 1, "final")
    # Strip schema prefix
    table_only = name.split(".", 1)[1]
    assert len(table_only) <= 63


# ─── build_upsert_sql with COALESCE ───────────────────────────────────────────

def test_build_upsert_sql_uses_coalesce_for_nk_coalesce_cols():
    spec = LoaderSpec(
        source="test", table="t",
        natural_key=["nk1", "nk2"],
        cursor_strategy=CursorStrategy.SNAPSHOT,
        dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
        columns=["nk1", "nk2", "data"],
        column_types={"nk1": "TEXT", "nk2": "TEXT", "data": "TEXT"},
        nk_coalesce_cols=("nk2",),
        csv_delimiter=";",
        file_pattern=lambda b: ["x"],
        bucket_from_filename=lambda n: "snapshot",
    )
    sql = build_upsert_sql(spec, "etl_staging.test_typed")
    # PG normalizes varchar→text in expression indexes; use (col)::text to match
    assert "ON CONFLICT (nk1, COALESCE(NULLIF((nk2)::text, ''::text), '__NULL__'::text))" in sql


def test_build_upsert_sql_applies_renames():
    spec = LoaderSpec(
        source="test", table="t",
        natural_key=["CSV_NAME"],
        cursor_strategy=CursorStrategy.SNAPSHOT,
        dedupe_strategy=DedupeStrategy.UPSERT_DO_NOTHING,
        columns=["CSV_NAME", "OTHER"],
        column_types={"CSV_NAME": "TEXT", "OTHER": "TEXT"},
        column_renames={"CSV_NAME": "target_name"},
        csv_delimiter=";",
        file_pattern=lambda b: ["x"],
        bucket_from_filename=lambda n: "snapshot",
    )
    sql = build_upsert_sql(spec, "etl_staging.test_typed")
    assert "INSERT INTO public.t (target_name, OTHER)" in sql
    assert "ON CONFLICT (target_name)" in sql


# ─── conn wrappers ────────────────────────────────────────────────────────────

class _FakeConn:
    def __init__(self, autocommit):
        self.autocommit = autocommit


def test_main_tx_conn_rejects_autocommit():
    from etl.incremental.conn import MainTxConn, WiringError
    with pytest.raises(WiringError):
        MainTxConn(_FakeConn(autocommit=True))


def test_autocommit_dlq_conn_rejects_non_autocommit():
    from etl.incremental.conn import AutocommitDlqConn, WiringError
    with pytest.raises(WiringError):
        AutocommitDlqConn(_FakeConn(autocommit=False))


def test_main_tx_conn_accepts_autocommit_off():
    from etl.incremental.conn import MainTxConn
    c = MainTxConn(_FakeConn(autocommit=False))
    assert c is not None


# ─── csv parsing helpers ──────────────────────────────────────────────────────

def test_clean_for_tab_empty_to_pg_null():
    from etl.incremental.parser import _clean_for_tab
    assert _clean_for_tab("") == "\\N"
    assert _clean_for_tab(None) == "\\N"
    assert _clean_for_tab("value") == "value"


def test_br_decimal_sql_handles_thousands_sep():
    from etl.incremental.parser import br_decimal_to_sql_expr
    expr = br_decimal_to_sql_expr("col_x")
    assert "replace" in expr.lower()
    assert "::numeric" in expr


def test_br_date_sql_handles_iso_and_br():
    from etl.incremental.parser import br_date_to_sql_expr
    expr = br_date_to_sql_expr("col_x")
    assert "DD/MM/YYYY" in expr
    assert "::date" in expr
