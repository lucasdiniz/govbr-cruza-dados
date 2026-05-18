"""LoaderSpec — declaração de uma fonte ETL incremental.

Conforme plan v7. Imutável (frozen dataclass). Validation em __post_init__ via
ConfigError raise (não assert — python -O strip-safe).

Princípio: spec é dado, não código. Lógica de execução fica em loader.py.
"""

from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional


class ConfigError(ValueError):
    """LoaderSpec inválido."""


class CursorStrategy(enum.Enum):
    """Como o orchestrator itera arquivos do bucket."""
    YEAR_WINDOW = "YEAR_WINDOW"     # 1 file por year (TCE-PB pattern)
    MONTH_WINDOW = "MONTH_WINDOW"    # 1 file por (year, month) (Dados-PB pattern)
    SNAPSHOT = "SNAPSHOT"            # 1 file só, sem cursor (small lookup tables)


class DedupeStrategy(enum.Enum):
    """Política de UPSERT no target."""
    UPSERT_DO_NOTHING = "UPSERT_DO_NOTHING"  # Default: PK conflict = skip (requires UNIQUE INDEX on NK)
    UPSERT_DO_UPDATE = "UPSERT_DO_UPDATE"    # Freshness predicate determine update
    APPEND = "APPEND"                        # No ON CONFLICT — bucket_token idempotency only.
                                              # Use quando source não tem NK confiável.
                                              # CAVEAT: source republish = duplicação total do bucket
                                              # se sha256 mudar mas conteúdo for "mesmas rows + algumas novas".
                                              # Adequado para TCE-PB despesa (sem NK natural).


# Allowlist de funções e operadores em derived_columns SQL expressions (D9)
ALLOWED_DERIVED_FN = frozenset({
    "COALESCE", "NULLIF", "LOWER", "UPPER", "TRIM", "BTRIM", "LTRIM", "RTRIM",
    "REGEXP_REPLACE", "SUBSTRING", "SUBSTR", "LEFT", "RIGHT", "REPLACE",
    "LENGTH", "CONCAT", "TO_DATE", "TO_TIMESTAMP", "TO_CHAR", "DATE_TRUNC",
})
ALLOWED_DERIVED_OPS = frozenset({"+", "-", "*", "/", "||"})
FORBIDDEN_DERIVED_KEYWORDS = frozenset({
    "SELECT", "FROM", "WHERE", "JOIN", "UNION", "INSERT", "UPDATE", "DELETE",
    "DROP", "TRUNCATE", "ALTER", "CREATE", "GRANT", "REVOKE",
    "NEXTVAL", "CURRENT_SETTING", "PG_SLEEP", "PG_READ_FILE",
    "OVER", "PARTITION", "WITH",
})


def _validate_derived_expr(col: str, expr: str) -> None:
    """AST-lite validation: rejeita keywords proibidas e ; em derived expr."""
    if not expr or not isinstance(expr, str):
        raise ConfigError(f"derived_columns[{col}]: empty expression")
    if len(expr) > 200:
        raise ConfigError(f"derived_columns[{col}]: expression > 200 chars")
    if ";" in expr:
        raise ConfigError(f"derived_columns[{col}]: ';' forbidden")
    upper = expr.upper()
    for kw in FORBIDDEN_DERIVED_KEYWORDS:
        # Bound-word match para evitar falso positivo (e.g., 'CASE' contém 'AS')
        import re
        if re.search(r"\b" + re.escape(kw) + r"\b", upper):
            raise ConfigError(
                f"derived_columns[{col}]: keyword '{kw}' forbidden"
            )


@dataclass(frozen=True)
class LoaderSpec:
    """Declaração imutável de como carregar uma fonte (source, table) incremental.

    Veja plan v7 § "LoaderSpec — campos POC" para semântica.
    """

    source: str                                # 'tce_pb' | 'dados_pb' | etc
    table: str                                 # nome do target table (sem schema)
    natural_key: list[str]                     # colunas da NK
    cursor_strategy: CursorStrategy
    dedupe_strategy: DedupeStrategy
    columns: list[str]                         # ordem das colunas no CSV
    column_types: dict[str, str]               # PG type per coluna (TEXT/BIGINT/DATE/...)
    csv_delimiter: str                         # SEM default — explicit (R6 fix)
    target_schema: str = "public"
    watermark_col: Optional[str] = None        # None para SNAPSHOT
    watermark_type: Literal["timestamp", "integer", "string"] = "string"
    encoding: str = "utf-8-sig"                # strip BOM transparente
    encoding_fallback: Optional[str] = None    # 'latin-1' para TCE-PB
    csv_quotechar: str = '"'
    decimal_format: Literal["br", "point"] = "point"  # 'br' = vírgula como decimal
    date_format: Literal["iso", "br"] = "iso"  # 'iso' = YYYY-MM-DD, 'br' = DD/MM/YYYY
    default_null_sentinels: tuple[str, ...] = ("", "00/00/0000", "0000-00-00", "NULL")
    column_overrides: dict[str, dict] = field(default_factory=dict)
    derived_columns: dict[str, str] = field(default_factory=dict)
    # Rename mapping CSV col → target DB col. Aplicado APENAS no INSERT INTO target.
    # Staging tables usam nomes do CSV (columns).
    column_renames: dict[str, str] = field(default_factory=dict)
    # Cols (no NK target) que devem ser tratadas como NULL=='' via COALESCE/NULLIF
    # no UNIQUE INDEX e no ON CONFLICT. Resolve mismatch entre legacy (que pode
    # ter inserido '') e incremental (que converte '' para NULL via sentinel).
    # Use TARGET col names (after column_renames). Apenas cols que estao na NK.
    nk_coalesce_cols: tuple[str, ...] = field(default_factory=tuple)
    # Synthetic NK via _nk_md5 column (BEFORE INSERT trigger calculates).
    # Quando True, build_upsert_sql emits ON CONFLICT (_nk_md5). Use para tabelas
    # com dups exatos no legacy data onde NK simples não funciona.
    # Requires _nk_md5 column + UNIQUE INDEX + trigger (sql/35_pb_extras_synthetic_nk.sql).
    nk_synthetic_md5: bool = False
    # Schema versioning per-bucket: callable que dado bucket_id retorna
    # (columns, column_renames) override. Se None, usa columns/column_renames default.
    # Permite suporte a schema drift histórico (e.g., TCE-PB 2018-2019 usa cols
    # diferentes vs 2020+).
    columns_per_bucket: Optional[Callable[[str], Optional[tuple[list[str], dict[str, str]]]]] = None
    is_zip_source: bool = False
    bootstrap_tolerance_pct: float = 0.0
    max_field_size: int = 1_048_576            # 1MB per field
    refetch_recent_buckets: int = 1            # N tail buckets sempre re-baixados
    # CSV header rewrites: mapeia nomes raw do CSV (potencialmente com acentos
    # e/ou espacos — e.g. "MES COMPETENCIA") para os nomes que aparecem em
    # spec.columns (e.g. "MES_COMPETENCIA"). Aplicado ANTES do header match em
    # validate_csv_header (parser.py). Default `{}` — sem efeito para specs
    # existentes. Necessario para fontes como Portal da Transparencia que
    # publicam headers nao-SQL-safe. Ver etl/incremental/specs/bolsa_familia.py
    # e ADR-0010.
    csv_header_rewrites: dict[str, str] = field(default_factory=dict)
    # Bucket file pattern: callable que dado bucket_id (str) retorna lista de
    # nomes de arquivo esperados (sem path).
    file_pattern: Optional[Callable[[str], list[str]]] = None
    # Bucket id derivation: callable que dado um filename retorna bucket_id (str).
    bucket_from_filename: Optional[Callable[[str], str]] = None
    # URL builder: callable que dado bucket_id retorna lista de
    # (url, filename) tuples para download. None = source não tem download
    # incremental (orchestrator usa só arquivos já em disco).
    url_for_bucket: Optional[Callable[[str], list[tuple[str, str]]]] = None
    # Buckets a enumerar quando rodando incremental: callable que retorna
    # lista de bucket_ids candidatos (e.g. range(2018, 2027) para year window).
    # Default: deriva do disco se url_for_bucket=None.
    enumerate_buckets: Optional[Callable[[], list[str]]] = None

    def __post_init__(self) -> None:
        # Basic types
        if not self.source or not isinstance(self.source, str):
            raise ConfigError("source must be non-empty str")
        if not self.table:
            raise ConfigError("table must be non-empty str")
        if not self.natural_key:
            raise ConfigError("natural_key must have at least 1 column")
        if not self.columns:
            raise ConfigError("columns must have at least 1 entry")
        if not self.csv_delimiter or len(self.csv_delimiter) != 1:
            raise ConfigError("csv_delimiter must be single char (no default)")

        # NK columns must be in columns or derived_columns
        cols_set = set(self.columns) | set(self.derived_columns.keys())
        for nk in self.natural_key:
            if nk not in cols_set:
                raise ConfigError(
                    f"natural_key column {nk!r} not in columns or derived_columns"
                )

        # column_types must cover columns
        for c in self.columns:
            if c not in self.column_types:
                raise ConfigError(f"column_types missing for {c!r}")

        # Watermark validations
        if self.dedupe_strategy == DedupeStrategy.UPSERT_DO_UPDATE:
            if self.watermark_col is None:
                raise ConfigError(
                    "UPSERT_DO_UPDATE requires watermark_col (freshness predicate)"
                )
        if self.cursor_strategy != CursorStrategy.SNAPSHOT and self.watermark_col is None:
            raise ConfigError(
                f"cursor_strategy={self.cursor_strategy.value} requires watermark_col"
            )

        if self.watermark_col is not None:
            if (self.watermark_col not in self.columns
                    and self.watermark_col not in self.derived_columns):
                raise ConfigError(
                    f"watermark_col {self.watermark_col!r} not in columns/derived"
                )
            if self.watermark_type not in ("timestamp", "integer", "string"):
                raise ConfigError(
                    f"watermark_type must be timestamp|integer|string, got {self.watermark_type!r}"
                )

        # Tolerance bounds
        if not (0.0 <= self.bootstrap_tolerance_pct <= 50.0):
            raise ConfigError(
                "bootstrap_tolerance_pct must be in [0.0, 50.0]"
            )

        # Validate csv_header_rewrites: valores devem estar em columns
        if self.csv_header_rewrites:
            cols_set_post = set(self.columns)
            for raw, renamed in self.csv_header_rewrites.items():
                if not raw or not renamed:
                    raise ConfigError(
                        "csv_header_rewrites: empty key/value not allowed"
                    )
                if renamed not in cols_set_post:
                    raise ConfigError(
                        f"csv_header_rewrites: target {renamed!r} not in columns"
                    )

        # Validate derived_columns expressions (D9 AST-lite)
        # NOTA: skip validation se expr contém placeholders {bucket_id} —
        # serão resolvidos em runtime, não armazenados no SQL final puro.
        for col, expr in self.derived_columns.items():
            if "{" not in expr:
                _validate_derived_expr(col, expr)

        # Cursor needs file_pattern + bucket_from_filename in non-SNAPSHOT
        if self.cursor_strategy != CursorStrategy.SNAPSHOT:
            if self.file_pattern is None:
                raise ConfigError(
                    f"cursor_strategy={self.cursor_strategy.value} requires file_pattern"
                )
            if self.bucket_from_filename is None:
                raise ConfigError(
                    f"cursor_strategy={self.cursor_strategy.value} requires bucket_from_filename"
                )

    @property
    def spec_hash(self) -> str:
        """SHA-256 do JSON canônico de campos primitivos. Estável cross-run."""
        canonical = {
            "source": self.source,
            "table": self.table,
            "target_schema": self.target_schema,
            "natural_key": list(self.natural_key),
            "cursor_strategy": self.cursor_strategy.value,
            "dedupe_strategy": self.dedupe_strategy.value,
            "columns": list(self.columns),
            "column_types": dict(self.column_types),
            "csv_delimiter": self.csv_delimiter,
            "watermark_col": self.watermark_col,
            "watermark_type": self.watermark_type,
            "encoding": self.encoding,
            "encoding_fallback": self.encoding_fallback,
            "decimal_format": self.decimal_format,
            "date_format": self.date_format,
            "default_null_sentinels": list(self.default_null_sentinels),
            "column_overrides": dict(self.column_overrides),
            "derived_columns": dict(self.derived_columns),
            "is_zip_source": self.is_zip_source,
            "bootstrap_tolerance_pct": self.bootstrap_tolerance_pct,
            "csv_header_rewrites": dict(self.csv_header_rewrites),
        }
        return hashlib.sha256(
            json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
