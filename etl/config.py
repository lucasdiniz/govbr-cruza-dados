"""Configuração central: caminhos, conexão DB, constantes."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Banco de Dados ──────────────────────────────────────────────
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
DB_NAME = os.getenv("POSTGRES_DB", "govbr")
DB_USER = os.getenv("POSTGRES_USER", "govbr")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "govbr_dev")

DSN = f"host={DB_HOST} port={DB_PORT} dbname={DB_NAME} user={DB_USER} password={DB_PASS}"

# ── Diretórios ──────────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", "/data/raw-data"))
SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

# ── Constantes de carga ────────────────────────────────────────
BATCH_SIZE = 5000          # Rows por batch INSERT
COPY_BUFFER_SIZE = 8192    # Bytes para COPY FROM STDIN
RFB_ENCODING = "latin-1"   # Encoding dos CSVs da Receita Federal
CSV_DELIMITER = ";"
