"""Smoke tests para a spec bolsa_familia + sql/41 contracts.

Cobertura:
- SPEC valida (__post_init__ passa).
- build_upsert_sql usa UPPERCASE em derived (CR1 regression).
- ON CONFLICT usa _nk_md5 (nk_synthetic_md5=True).
- DedupeStrategy = UPSERT_DO_NOTHING (decisao do user — nao corrigir).
- csv_header_rewrites cobre todos os headers raw esperados.
- bucket_from_filename aceita ambos CSV interno e ZIP.
- file_pattern + url_for_bucket geram nomes consistentes.
- enumerate_buckets comeca em 2023-03 (Novo BF substituiu Auxilio Brasil).
"""
from __future__ import annotations

from datetime import date

import pytest

from etl.incremental.spec import (
    CursorStrategy,
    DedupeStrategy,
)
from etl.incremental.specs.bolsa_familia import (
    SPEC,
    COLUMNS,
    CSV_HEADER_REWRITES,
    _bucket_from_filename,
    _file_pattern,
    _url_for_bucket,
    _enumerate_buckets,
)
from etl.incremental.staging import build_upsert_sql


# ─── SPEC validation ──────────────────────────────────────────────────────


def test_spec_basic_attrs():
    assert SPEC.source == "bolsa_familia"
    assert SPEC.table == "bolsa_familia"
    assert SPEC.cursor_strategy == CursorStrategy.MONTH_WINDOW
    assert SPEC.dedupe_strategy == DedupeStrategy.UPSERT_DO_NOTHING
    assert SPEC.is_zip_source is True
    assert SPEC.refetch_recent_buckets == 1
    assert SPEC.encoding == "latin-1"
    assert SPEC.decimal_format == "br"


def test_spec_uses_synthetic_md5_nk():
    """Decisao chave: NK natural nao cobre todos casos (CPF vazio + parcelas
    retroativas). Synthetic md5 cobre 100%."""
    assert SPEC.nk_synthetic_md5 is True


def test_spec_columns_uppercase_sql_safe():
    """spec.columns deve usar UPPERCASE sem espaco/acento (SQL-safe).
    Headers raw do CSV vem via csv_header_rewrites."""
    for col in COLUMNS:
        assert col == col.upper(), f"col {col!r} deveria ser UPPERCASE"
        assert " " not in col, f"col {col!r} tem espaco"
        # Sem acentos: ASCII apenas
        assert col.isascii(), f"col {col!r} tem caractere nao-ASCII"


def test_spec_natural_key_declarative():
    """NK declarativa = trio semantico de parcela. ON CONFLICT usa _nk_md5
    (porque nk_synthetic_md5=True), mas NK lista documenta intencao."""
    assert "MES_COMPETENCIA" in SPEC.natural_key
    assert "MES_REFERENCIA" in SPEC.natural_key
    assert "CPF_FAVORECIDO" in SPEC.natural_key
    assert "NIS_FAVORECIDO" in SPEC.natural_key


# ─── build_upsert_sql contracts (mitigations CR1, F1) ─────────────────────


def test_build_upsert_sql_uses_uppercase_csv_in_derived():
    """CR1 regression: derived_columns SELECT usa raw staging col names
    (UPPERCASE), nao o target lowercase. Erro classico: 'cpf_favorecido'
    em vez de 'CPF_FAVORECIDO' faz REGEXP_REPLACE apontar para coluna
    inexistente no staging."""
    sql = build_upsert_sql(SPEC, stg_typed="_stg_test", bucket_id="2026-04")
    assert "REGEXP_REPLACE(CPF_FAVORECIDO" in sql
    assert "REGEXP_REPLACE(cpf_favorecido" not in sql


def test_build_upsert_sql_on_conflict_uses_nk_md5():
    """nk_synthetic_md5=True -> ON CONFLICT (_nk_md5)."""
    sql = build_upsert_sql(SPEC, stg_typed="_stg_test", bucket_id="2026-04")
    assert "ON CONFLICT (_nk_md5)" in sql


def test_build_upsert_sql_uses_do_nothing():
    """F1 dispensado: DedupeStrategy = UPSERT_DO_NOTHING. Incremental
    acumula novos meses, nao corrige existentes."""
    sql = build_upsert_sql(SPEC, stg_typed="_stg_test", bucket_id="2026-04")
    assert "DO NOTHING" in sql
    assert "DO UPDATE" not in sql


def test_build_upsert_sql_target_uses_lowercase_renames():
    """INSERT INTO target usa col names lowercase (column_renames)."""
    sql = build_upsert_sql(SPEC, stg_typed="_stg_test", bucket_id="2026-04")
    assert "INSERT INTO public.bolsa_familia" in sql
    # cols renomeadas em INSERT INTO (..., cpf_favorecido, ...)
    assert "cpf_favorecido" in sql
    assert "mes_competencia" in sql


# ─── csv_header_rewrites ──────────────────────────────────────────────────


def test_csv_header_rewrites_covers_all_columns():
    """Todo header raw mapeia para uma col de spec.columns. Sem cols
    extras (caso contrario, validator do __post_init__ falharia)."""
    rewrite_targets = set(CSV_HEADER_REWRITES.values())
    columns_set = set(COLUMNS)
    assert rewrite_targets == columns_set


def test_csv_header_rewrites_has_9_entries():
    """Portal Transparencia publica 9 cols. Smoke contra refator acidental."""
    assert len(CSV_HEADER_REWRITES) == 9


def test_csv_header_rewrites_includes_accented_keys():
    """Empirico: validado em 202510, 202512, 202602. Acentos preservam
    com encoding latin-1."""
    assert "MÊS COMPETÊNCIA" in CSV_HEADER_REWRITES
    assert "CÓDIGO MUNICÍPIO SIAFI" in CSV_HEADER_REWRITES
    assert "NOME MUNICÍPIO" in CSV_HEADER_REWRITES


# ─── Bucket helpers ───────────────────────────────────────────────────────


def test_bucket_from_filename_csv():
    """Framework chama com CSV apos extracao do ZIP."""
    assert _bucket_from_filename("202604_NovoBolsaFamilia.csv") == "2026-04"
    assert _bucket_from_filename("202301_NovoBolsaFamilia.csv") == "2023-01"


def test_bucket_from_filename_zip():
    """Aceita ZIP tambem (download.py pode chamar antes da extracao)."""
    assert _bucket_from_filename("novo_bf_202604.zip") == "2026-04"


def test_bucket_from_filename_unknown_returns_none():
    """Arquivos fora do padrao retornam None — framework skip."""
    assert _bucket_from_filename("garbage.txt") is None
    assert _bucket_from_filename("202604_NovoBolsaFamilia.txt") is None


def test_file_pattern_returns_csv_name():
    """file_pattern aponta para o CSV interno do ZIP (apos extracao)."""
    assert _file_pattern("2026-04") == ["202604_NovoBolsaFamilia.csv"]


def test_url_for_bucket_format():
    """URL = base + YYYYMM (sem hifen); destino = novo_bf_YYYYMM.zip."""
    urls = _url_for_bucket("2026-04")
    assert len(urls) == 1
    url, filename = urls[0]
    assert url.endswith("/202604")
    assert filename == "novo_bf_202604.zip"
    assert "portaldatransparencia" in url


# ─── enumerate_buckets ────────────────────────────────────────────────────


def test_enumerate_buckets_starts_at_2023_03():
    """Novo Bolsa Familia substituiu Auxilio Brasil em marco/2023."""
    buckets = _enumerate_buckets()
    assert buckets[0] == "2023-03"


def test_enumerate_buckets_continues_to_today():
    """Ultimo bucket = mes atual."""
    buckets = _enumerate_buckets()
    today = date.today()
    expected_last = f"{today.year}-{today.month:02d}"
    assert buckets[-1] == expected_last


def test_enumerate_buckets_monotonic():
    """Buckets em ordem cronologica."""
    buckets = _enumerate_buckets()
    for prev, curr in zip(buckets, buckets[1:]):
        assert prev < curr, f"{prev} >= {curr} quebra ordem"


# ─── spec_hash stability ──────────────────────────────────────────────────


def test_spec_hash_includes_csv_header_rewrites():
    """Mudar csv_header_rewrites altera spec_hash (forca re-bootstrap)."""
    import dataclasses as dc
    h1 = SPEC.spec_hash
    spec_mod = dc.replace(SPEC, csv_header_rewrites={"X": "MES_COMPETENCIA"})
    h2 = spec_mod.spec_hash
    assert h1 != h2
