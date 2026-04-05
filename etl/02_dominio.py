"""Fase 2: Carrega tabelas de domínio (lookup tables) da Receita Federal."""

import glob

from tqdm import tqdm

from etl.config import DATA_DIR, RFB_ENCODING
from etl.db import get_conn, batch_insert, truncate_table, table_count
from etl.utils import parse_csv_line, safe_strip

# Mapeamento: (arquivo, tabela, colunas)
DOMAIN_TABLES = [
    ("Cnaes.csv", "dom_cnae", ["codigo", "descricao"]),
    ("Municipios.csv", "dom_municipio", ["codigo", "descricao"]),
    ("Naturezas.csv", "dom_natureza_juridica", ["codigo", "descricao"]),
    ("Paises.csv", "dom_pais", ["codigo", "descricao"]),
    ("Qualificacoes.csv", "dom_qualificacao", ["codigo", "descricao"]),
    ("Motivos.csv", "dom_motivo", ["codigo", "descricao"]),
]


def load_domain_table(conn, filename: str, table: str, columns: list[str]):
    """Carrega uma tabela de domínio (arquivo pequeno, cabe na RAM)."""
    filepath = DATA_DIR / "rfb" / filename
    if not filepath.exists():
        filepath = DATA_DIR / filename
    if not filepath.exists():
        print(f"    AVISO: {filename} não encontrado, pulando.")
        return

    rows = []
    with open(filepath, "r", encoding=RFB_ENCODING, errors="replace") as f:
        for line in f:
            fields = parse_csv_line(line, delimiter=";")
            if len(fields) >= 2:
                codigo = safe_strip(fields[0])
                descricao = safe_strip(fields[1])
                if codigo:
                    rows.append((codigo, descricao))

    truncate_table(conn, table)
    batch_insert(conn, table, columns, rows)
    count = table_count(conn, table)
    print(f"    {table}: {count} registros")


def run():
    conn = get_conn()
    try:
        for filename, table, columns in DOMAIN_TABLES:
            print(f"  Carregando {filename} ->{table}...")
            load_domain_table(conn, filename, table, columns)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
