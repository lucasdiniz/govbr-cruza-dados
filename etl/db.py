"""Helpers de conexão e carga no PostgreSQL."""

from __future__ import annotations

import io
from pathlib import Path

import psycopg2
import psycopg2.extras

from etl.config import DSN, SQL_DIR


def get_conn():
    """Retorna uma conexão nova ao banco."""
    conn = psycopg2.connect(DSN)
    conn.autocommit = False
    return conn


def execute_sql_file(conn, filename: str):
    """Executa um arquivo .sql inteiro."""
    path = SQL_DIR / filename
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def copy_from_stream(conn, table: str, columns: list[str], stream,
                     delimiter: str = "\t", null_str: str = ""):
    """
    Usa COPY FROM STDIN para carga rápida.
    `stream` deve ser um file-like object (StringIO ou gerador wrappado).
    """
    cols = ", ".join(columns)
    sql = f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT csv, DELIMITER E'{delimiter}', NULL '{null_str}', QUOTE E'\\b')"
    with conn.cursor() as cur:
        cur.copy_expert(sql, stream)
    conn.commit()


def copy_csv_streaming(conn, table: str, columns: list[str],
                       line_generator, delimiter: str = "\t"):
    """
    Carga via COPY usando um generator de linhas TSV/CSV.
    Converte o generator em um file-like para copy_expert.
    """
    buffer = io.StringIO()
    count = 0
    batch_lines = 50000  # flush a cada 50k linhas

    cols = ", ".join(columns)
    copy_sql = f"COPY {table} ({cols}) FROM STDIN WITH (FORMAT text, DELIMITER E'{delimiter}', NULL '\\N')"

    with conn.cursor() as cur:
        for line in line_generator:
            buffer.write(line)
            if not line.endswith("\n"):
                buffer.write("\n")
            count += 1

            if count % batch_lines == 0:
                buffer.seek(0)
                cur.copy_expert(copy_sql, buffer)
                conn.commit()
                buffer = io.StringIO()

        # Flush restante
        if buffer.tell() > 0:
            buffer.seek(0)
            cur.copy_expert(copy_sql, buffer)
            conn.commit()

    return count


def batch_insert(conn, table: str, columns: list[str], rows: list[tuple]):
    """INSERT em batch usando execute_values (rápido para lotes menores)."""
    if not rows:
        return
    cols = ", ".join(columns)
    template = "(" + ", ".join(["%s"] * len(columns)) + ")"
    sql = f"INSERT INTO {table} ({cols}) VALUES %s ON CONFLICT DO NOTHING"
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, rows, template=template, page_size=1000)
    conn.commit()


def truncate_table(conn, table: str):
    """Trunca uma tabela (RESTART IDENTITY CASCADE)."""
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE")
    conn.commit()


def table_count(conn, table: str) -> int:
    """Retorna COUNT(*) de uma tabela."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]
