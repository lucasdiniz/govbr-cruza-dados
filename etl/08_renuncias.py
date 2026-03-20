"""Fase 5.3: Carrega dados de renuncias fiscais (multiplos anos).

Fontes:
  - 20XX_RenunciasFiscais.csv
  - 20XX_EmpresasHabilitadas.csv
  - 20XX_EmpresasImunesOuIsentas.csv
  - 20XX_RenunciasFiscaisPorBeneficiario.csv
"""

import csv
import io

from tqdm import tqdm

from etl.config import DATA_DIR
from etl.db import get_conn, table_count


def _staging_load(conn, staging, n_cols, filepath):
    """Carrega CSV com header via Python csv reader (trata ; dentro de campos)."""
    col_defs = ", ".join(f"c{i} TEXT" for i in range(n_cols))
    cols = ", ".join(f"c{i}" for i in range(n_cols))

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
        cur.execute(f"CREATE UNLOGGED TABLE {staging} ({col_defs})")
    conn.commit()

    copy_sql = f"""COPY {staging} ({cols}) FROM STDIN
        WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N')"""

    buf = io.BytesIO()
    count = 0

    def clean_lines(fp):
        with open(fp, "r", encoding="latin-1", errors="replace") as f:
            for line in f:
                yield line.replace("\x00", "")

    reader = csv.reader(clean_lines(filepath), delimiter=";", quotechar='"')
    header = next(reader, None)  # Skip header

    for row in reader:
        if len(row) > n_cols:
            row = row[:n_cols]
        elif len(row) < n_cols:
            row = row + [""] * (n_cols - len(row))

        escaped = []
        for val in row:
            if val == "" or val is None:
                escaped.append("\\N")
            else:
                val = val.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "")
                escaped.append(val)

        buf.write(("\t".join(escaped) + "\n").encode("utf-8"))
        count += 1

        if count % 100000 == 0:
            buf.seek(0)
            with conn.cursor() as cur:
                cur.copy_expert(copy_sql, buf)
            conn.commit()
            buf = io.BytesIO()

    if buf.tell() > 0:
        buf.seek(0)
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, buf)
        conn.commit()


def _load_renuncias_fiscais(conn, filepath):
    staging = "_stg_renuncia"
    _staging_load(conn, staging, 15, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO renuncia_fiscal (
                ano_calendario, cnpj, razao_social, nome_fantasia,
                cnae_codigo, cnae_descricao, municipio, uf,
                tipo_renuncia, beneficio_fiscal, fundamento_legal,
                descricao, tributo, forma_tributacao, valor_renuncia
            )
            SELECT
                CASE WHEN TRIM(c0) ~ '^\d+$' THEN CAST(TRIM(c0) AS SMALLINT) ELSE NULL END,
                TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5), TRIM(c6), TRIM(c7),
                TRIM(c8), TRIM(c9), TRIM(c10), TRIM(c11), TRIM(c12), TRIM(c13),
                CASE WHEN TRIM(c14) ~ '^[\\d.,-]+$' AND TRIM(c14) != ''
                     THEN CAST(REPLACE(REPLACE(TRIM(c14), '.', ''), ',', '.') AS NUMERIC)
                     ELSE NULL END
            FROM {staging}
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()


def _load_habilitadas(conn, filepath):
    staging = "_stg_hab"
    _staging_load(conn, staging, 12, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO empresa_habilitada (
                cnpj, razao_social, nome_fantasia, cnae_codigo, cnae_descricao,
                municipio, uf, beneficio_fiscal, base_legal, descricao,
                dt_inicio, dt_fim
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4),
                TRIM(c5), TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9),
                CASE WHEN TRIM(c10) ~ '^\d{{2}}/\d{{2}}/\d{{4}}$'
                     THEN safe_to_date(TRIM(c10), 'DD/MM/YYYY') ELSE NULL END,
                CASE WHEN TRIM(c11) ~ '^\d{{2}}/\d{{2}}/\d{{4}}$'
                     THEN safe_to_date(TRIM(c11), 'DD/MM/YYYY') ELSE NULL END
            FROM {staging}
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()


def _load_imunes(conn, filepath):
    staging = "_stg_imune"
    _staging_load(conn, staging, 10, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO empresa_imune (
                ano_calendario, cnpj, razao_social, nome_fantasia,
                cnae_codigo, cnae_descricao, municipio, uf,
                tipo_entidade, beneficio_fiscal
            )
            SELECT
                CASE WHEN TRIM(c0) ~ '^\d+$' THEN CAST(TRIM(c0) AS SMALLINT) ELSE NULL END,
                TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5),
                TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9)
            FROM {staging}
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()


def _load_beneficiarios(conn, filepath):
    staging = "_stg_renbenef"
    _staging_load(conn, staging, 9, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO renuncia_beneficiario (
                ano_calendario, cnpj, razao_social, nome_fantasia,
                cnae_codigo, cnae_descricao, municipio, uf, valor_renuncia
            )
            SELECT
                CASE WHEN TRIM(c0) ~ '^\d+$' THEN CAST(TRIM(c0) AS SMALLINT) ELSE NULL END,
                TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5),
                TRIM(c6), TRIM(c7),
                CASE WHEN TRIM(c8) ~ '^[\\d.,-]+$' AND TRIM(c8) != ''
                     THEN CAST(REPLACE(REPLACE(TRIM(c8), '.', ''), ',', '.') AS NUMERIC)
                     ELSE NULL END
            FROM {staging}
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()


def run():
    conn = get_conn()
    try:
        files = sorted(DATA_DIR.glob("*_RenunciasFiscais.csv"))
        for f in tqdm(files, desc="    Renuncias Fiscais"):
            _load_renuncias_fiscais(conn, f)
        print(f"    renuncia_fiscal: {table_count(conn, 'renuncia_fiscal')} registros")

        files = sorted(DATA_DIR.glob("*_EmpresasHabilitadas.csv"))
        for f in tqdm(files, desc="    Empresas Habilitadas"):
            _load_habilitadas(conn, f)
        print(f"    empresa_habilitada: {table_count(conn, 'empresa_habilitada')} registros")

        files = sorted(DATA_DIR.glob("*_EmpresasImunesOuIsentas.csv"))
        for f in tqdm(files, desc="    Empresas Imunes"):
            _load_imunes(conn, f)
        print(f"    empresa_imune: {table_count(conn, 'empresa_imune')} registros")

        files = sorted(DATA_DIR.glob("*_RenunciasFiscaisPorBeneficiario.csv"))
        for f in tqdm(files, desc="    Renuncias Beneficiario"):
            _load_beneficiarios(conn, f)
        print(f"    renuncia_beneficiario: {table_count(conn, 'renuncia_beneficiario')} registros")

    finally:
        conn.close()


if __name__ == "__main__":
    run()
