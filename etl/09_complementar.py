"""Fase 4.7 + 5.2: Carrega BNDES e ComprasNet.

Fontes:
  - bndes.csv (delimitador ;, quoted, com header) — download automatizado
  - comprasnet.csv (delimitador ,, com header) — data/static/comprasnet.csv.gz no repo
Holdings removido: redundante com socio WHERE tipo_socio=1 (PJ socio de PJ)
"""

import csv
import gzip
import shutil
from pathlib import Path

from etl.config import DATA_DIR
from etl.db import copy_csv_streaming, get_conn, table_count

# comprasnet.csv.gz no repo (data/static/)
STATIC_DIR = Path(__file__).resolve().parent.parent / "data" / "static"


def _copy_escape(val):
    if val is None:
        return "\\N"
    val = str(val).strip()
    if val == "":
        return "\\N"
    return val.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "")


def _iter_csv_as_tsv(filepath: Path, expected_cols: int, encoding: str = "latin1", delimiter: str = ";"):
    """Lê CSV com parser tolerante e emite linhas TSV para COPY.

    Campos com número inesperado de colunas são pulados para evitar abortar o ETL.
    """
    skipped = 0

    with open(filepath, "r", encoding=encoding, errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=delimiter, quotechar='"')
        next(reader, None)  # header
        for row in reader:
            if not row or all(not c.strip() for c in row):
                continue
            if len(row) != expected_cols:
                skipped += 1
                continue
            yield "\t".join(_copy_escape(v) for v in row) + "\n"

    if skipped:
        print(f"      AVISO: {filepath.name}: {skipped} linha(s) malformada(s) puladas")


def load_bndes(conn):
    """Carrega BNDES CSVs → bndes_contrato.

    Aceita formato antigo (bndes.csv) ou novo (2 CSVs separados).
    """
    bndes_dir = DATA_DIR / "bndes"
    # Formato novo: 2 CSVs no subdir bndes/
    new_files = list(bndes_dir.glob("operacoes-financiamento-*.csv")) if bndes_dir.exists() else []
    # Formato antigo: bndes.csv na raiz
    old_file = DATA_DIR / "bndes.csv"

    files = new_files if new_files else ([old_file] if old_file.exists() else [])
    if not files:
        print("    AVISO: BNDES CSVs não encontrados.")
        return

    staging = "_stg_bndes"

    # Detectar número de colunas do primeiro arquivo (formato muda entre anos)
    first_file = sorted(files)[0]
    with open(first_file, "r", encoding="latin1") as f:
        header_line = f.readline()
    ncols = len(header_line.split(";"))
    print(f"    BNDES: detectado {ncols} colunas no CSV")

    cols = ", ".join(f"c{i} TEXT" for i in range(ncols))
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"CREATE UNLOGGED TABLE {staging} ({cols})")
    conn.commit()

    for filepath in sorted(files):
        print(f"    Carregando {filepath.name}...")
        copy_csv_streaming(
            conn,
            staging,
            [f"c{i}" for i in range(ncols)],
            _iter_csv_as_tsv(filepath, ncols, encoding="latin1", delimiter=";"),
        )

    # Mapeamento coluna CSV → coluna destino + transformação
    # O CSV do BNDES muda de formato entre anos (30-34 colunas)
    col_map = [
        ("cliente", "TRIM(c0)"),
        ("cnpj", "TRIM(c1)"),
        ("descricao_projeto", "TRIM(c2)"),
        ("uf", "TRIM(c3)"),
        ("municipio", "TRIM(c4)"),
        ("municipio_codigo", "TRIM(c5)"),
        ("numero_contrato", "TRIM(c6)"),
        ("dt_contratacao", "safe_to_date(TRIM(c7), 'YYYY-MM-DD')"),
        ("valor_contratado", "CASE WHEN TRIM(c8) = '' THEN NULL ELSE CAST(REPLACE(REPLACE(TRIM(c8), '.', ''), ',', '.') AS NUMERIC) END"),
        ("valor_desembolsado", "CASE WHEN TRIM(c9) = '' THEN NULL ELSE CAST(REPLACE(REPLACE(TRIM(c9), '.', ''), ',', '.') AS NUMERIC) END"),
        ("fonte_recurso", "TRIM(c10)"),
        ("custo_financeiro", "TRIM(c11)"),
        ("juros", "TRIM(c12)"),
        ("prazo_carencia_meses", r"CASE WHEN TRIM(c13) ~ '^\d+$' THEN CAST(TRIM(c13) AS INT) ELSE NULL END"),
        ("prazo_amortizacao_meses", r"CASE WHEN TRIM(c14) ~ '^\d+$' THEN CAST(TRIM(c14) AS INT) ELSE NULL END"),
        ("modalidade_apoio", "TRIM(c15)"),
        ("forma_apoio", "TRIM(c16)"),
        ("produto", "TRIM(c17)"),
        ("instrumento_financeiro", "TRIM(c18)"),
        ("inovacao", "TRIM(c19)"),
        ("area_operacional", "TRIM(c20)"),
        ("setor_cnae", "TRIM(c21)"),
        ("subsetor_cnae", "TRIM(c22)"),
        ("subsetor_cnae_codigo", "TRIM(c23)"),
        ("setor_bndes", "TRIM(c24)"),
        ("subsetor_bndes", "TRIM(c25)"),
        ("porte_cliente", "TRIM(c26)"),
        ("natureza_cliente", "TRIM(c27)"),
        ("instituicao_credenciada", "TRIM(c28)"),
        ("cnpj_instituicao", "TRIM(c29)"),
        ("tipo_garantia", "TRIM(c30)"),
        ("tipo_excepcionalidade", "TRIM(c31)"),
        ("situacao_contrato", "TRIM(c32)"),
    ]

    # Usar apenas colunas que existem no staging (c0..c{ncols-1})
    usable = col_map[:ncols]
    dest_cols = ", ".join(d for d, _ in usable)
    src_exprs = ", ".join(e for _, e in usable)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO bndes_contrato ({dest_cols})
            SELECT {src_exprs}
            FROM {staging}
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()

    print(f"    bndes_contrato: {table_count(conn, 'bndes_contrato')} registros")


def load_holdings(conn):
    """Carrega holding.csv → holding_vinculo."""
    filepath = DATA_DIR / "holding.csv"
    if not filepath.exists():
        print("    AVISO: holding.csv não encontrado.")
        return

    staging = "_stg_holding"
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"""CREATE UNLOGGED TABLE {staging} (
            c0 TEXT, c1 TEXT, c2 TEXT, c3 TEXT, c4 TEXT, c5 TEXT
        )""")
    conn.commit()

    # holding.csv usa VÍRGULA como delimitador
    copy_sql = f"""COPY {staging} FROM STDIN
        WITH (FORMAT csv, DELIMITER ',', HEADER true, NULL '', ENCODING 'UTF8')"""
    with open(filepath, "rb") as f:
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, f)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO holding_vinculo (
                holding_cnpj, holding_razao_social,
                cnpj_subsidiaria, razao_social_subsidiaria,
                codigo_qualificacao, qualificacao
            )
            SELECT TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5)
            FROM {staging}
            WHERE TRIM(c0) != '' AND TRIM(c2) != ''
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()

    print(f"    holding_vinculo: {table_count(conn, 'holding_vinculo')} registros")


def load_comprasnet(conn):
    """Carrega comprasnet.csv → comprasnet_contrato."""
    filepath = DATA_DIR / "comprasnet.csv"
    if not filepath.exists():
        # Tentar descomprimir do repo
        gz_path = STATIC_DIR / "comprasnet.csv.gz"
        if gz_path.exists():
            print("    Descomprimindo comprasnet.csv.gz...")
            with gzip.open(gz_path, "rb") as f_in:
                with open(filepath, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            print("    AVISO: comprasnet.csv não encontrado.")
            return

    staging = "_stg_comprasnet"
    cols = ", ".join(f"c{i} TEXT" for i in range(38))
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"CREATE UNLOGGED TABLE {staging} ({cols})")
    conn.commit()

    # comprasnet.csv usa VÍRGULA como delimitador
    copy_sql = f"""COPY {staging} FROM STDIN
        WITH (FORMAT csv, DELIMITER ',', HEADER true, NULL '', ENCODING 'UTF8')"""
    with open(filepath, "rb") as f:
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, f)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO comprasnet_contrato (
                id_comprasnet, receita_despesa, numero, orgao_codigo, orgao_nome,
                unidade_codigo, esfera, poder, sisg, gestao,
                unidade_nome_resumido, unidade_nome, unidade_origem_codigo, unidade_origem_nome,
                fornecedor_tipo, fornecedor_cnpj_cpf, fornecedor_nome,
                codigo_tipo, tipo, categoria, processo, objeto,
                fundamento_legal, informacao_complementar,
                codigo_modalidade, modalidade, unidade_compra, licitacao_numero,
                dt_assinatura, dt_publicacao, vigencia_inicio, vigencia_fim,
                valor_inicial, valor_global, num_parcelas, valor_parcela,
                valor_acumulado, situacao
            )
            SELECT
                CASE WHEN TRIM(c0) ~ '^\\d+$' THEN CAST(TRIM(c0) AS INT) ELSE NULL END,
                TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5),
                TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9),
                TRIM(c10), TRIM(c11), TRIM(c12), TRIM(c13),
                TRIM(c14), TRIM(c15), TRIM(c16), TRIM(c17), TRIM(c18),
                TRIM(c19), TRIM(c20), TRIM(c21), TRIM(c22), TRIM(c23),
                TRIM(c24), TRIM(c25), TRIM(c26), TRIM(c27),
                safe_to_date(TRIM(c28), 'YYYY-MM-DD'),
                safe_to_date(TRIM(c29), 'YYYY-MM-DD'),
                safe_to_date(TRIM(c30), 'YYYY-MM-DD'),
                safe_to_date(TRIM(c31), 'YYYY-MM-DD'),
                CASE WHEN TRIM(c32) = '' THEN NULL ELSE CAST(TRIM(c32) AS NUMERIC) END,
                CASE WHEN TRIM(c33) = '' THEN NULL ELSE CAST(TRIM(c33) AS NUMERIC) END,
                CASE WHEN TRIM(c34) ~ '^\\d+$' THEN CAST(TRIM(c34) AS INT) ELSE NULL END,
                CASE WHEN TRIM(c35) = '' THEN NULL ELSE CAST(TRIM(c35) AS NUMERIC) END,
                CASE WHEN TRIM(c36) = '' THEN NULL ELSE CAST(TRIM(c36) AS NUMERIC) END,
                TRIM(c37)
            FROM {staging}
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()

    print(f"    comprasnet_contrato: {table_count(conn, 'comprasnet_contrato')} registros")


def run():
    conn = get_conn()
    try:
        load_bndes(conn)
        # Holdings removido: redundante com socio WHERE tipo_socio=1 (PJ socio de PJ)
        load_comprasnet(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
