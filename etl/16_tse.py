"""Carrega dados do TSE (candidatos e bens declarados).

Fonte: dadosabertos.tse.jus.br
Arquivos por UF dentro de zips: consulta_cand_YYYY_UF.csv, bem_candidato_YYYY_UF.csv
"""

import csv
import io
from pathlib import Path

from tqdm import tqdm

from etl.config import DATA_DIR
from etl.db import get_conn, table_count

TSE_DIR = DATA_DIR / "tse"


def _staging_load(conn, staging, n_cols, filepath):
    """Carrega CSV com header via Python csv reader."""
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
    next(reader, None)

    for row in reader:
        if len(row) > n_cols:
            row = row[:n_cols]
        elif len(row) < n_cols:
            row = row + [""] * (n_cols - len(row))

        escaped = []
        for val in row:
            if val == "" or val is None or val == "#NULO" or val == "#NE":
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


def load_candidatos(conn, year):
    """Carrega consulta_cand_YYYY_*.csv -> tse_candidato."""
    cand_dir = TSE_DIR / f"cand_{year}"
    if not cand_dir.exists():
        # Tentar extrair do zip
        zip_path = TSE_DIR / f"consulta_cand_{year}.zip"
        if zip_path.exists():
            import zipfile
            cand_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(cand_dir)

    files = sorted(cand_dir.glob(f"consulta_cand_{year}_*.csv"))
    if not files:
        print(f"    AVISO: Nenhum arquivo de candidatos {year} encontrado.")
        return

    staging = "_stg_tse_cand"
    # O CSV do TSE tem ~50 colunas, pegamos as que interessam
    for filepath in tqdm(files, desc=f"    Candidatos {year}"):
        _staging_load(conn, staging, 50, filepath)

        with conn.cursor() as cur:
            # Colunas: c2=ANO, c10=SG_UF, c12=NM_UE, c13=CD_CARGO, c14=DS_CARGO,
            # c15=SQ_CANDIDATO, c16=NR_CANDIDATO, c17=NM_CANDIDATO, c18=NM_URNA,
            # c19=NM_SOCIAL, c20=NR_CPF, c25=NR_PARTIDO, c26=SG_PARTIDO, c27=NM_PARTIDO,
            # c35=SG_UF_NASCIMENTO, c36=DT_NASCIMENTO, c38=CD_GENERO, c39=DS_GENERO,
            # c40=CD_GRAU_INSTRUCAO, c41=DS_GRAU_INSTRUCAO, c42=CD_ESTADO_CIVIL,
            # c44=CD_COR_RACA, c45=DS_COR_RACA, c46=CD_OCUPACAO, c47=DS_OCUPACAO,
            # c48=CD_SIT_TOT_TURNO, c49=DS_SIT_TOT_TURNO
            cur.execute(f"""
                INSERT INTO tse_candidato (
                    ano_eleicao, sg_uf, nm_ue, cd_cargo, ds_cargo,
                    sq_candidato, nr_candidato, nm_candidato, nm_urna_candidato,
                    nm_social_candidato, cpf,
                    nr_partido, sg_partido, nm_partido,
                    sg_uf_nascimento, dt_nascimento,
                    cd_genero, ds_genero, cd_grau_instrucao, ds_grau_instrucao,
                    cd_cor_raca, ds_cor_raca, cd_ocupacao, ds_ocupacao,
                    cd_sit_tot_turno, ds_sit_tot_turno,
                    ds_situacao_candidatura
                )
                SELECT
                    CASE WHEN TRIM(c2) ~ '^\d+$' THEN CAST(TRIM(c2) AS SMALLINT) ELSE NULL END,
                    TRIM(c10), TRIM(c12), TRIM(c13), TRIM(c14),
                    TRIM(c15), TRIM(c16), TRIM(c17), TRIM(c18),
                    TRIM(c19), TRIM(c20),
                    TRIM(c25), TRIM(c26), TRIM(c27),
                    TRIM(c35), safe_to_date(TRIM(c36), 'DD/MM/YYYY'),
                    TRIM(c38), TRIM(c39), TRIM(c40), TRIM(c41),
                    TRIM(c44), TRIM(c45), TRIM(c46), TRIM(c47),
                    TRIM(c48), TRIM(c49),
                    TRIM(c23)
                FROM {staging}
                WHERE TRIM(c2) ~ '^\d+$'
            """)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()


def load_bens(conn, year):
    """Carrega bem_candidato_YYYY_*.csv -> tse_bem_candidato."""
    bens_dir = TSE_DIR / f"bens_{year}"
    if not bens_dir.exists():
        zip_path = TSE_DIR / f"bem_candidato_{year}.zip"
        if zip_path.exists():
            import zipfile
            bens_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path) as z:
                z.extractall(bens_dir)

    files = sorted(bens_dir.glob(f"bem_candidato_{year}_*.csv"))
    if not files:
        print(f"    AVISO: Nenhum arquivo de bens {year} encontrado.")
        return

    staging = "_stg_tse_bem"
    # Colunas: c2=ANO, c8=SG_UF, c11=SQ_CANDIDATO, c12=NR_ORDEM,
    # c13=CD_TIPO_BEM, c14=DS_TIPO_BEM, c15=DS_BEM, c16=VR_BEM
    for filepath in tqdm(files, desc=f"    Bens {year}"):
        _staging_load(conn, staging, 19, filepath)

        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO tse_bem_candidato (
                    ano_eleicao, sg_uf, sq_candidato, nr_ordem_bem,
                    cd_tipo_bem, ds_tipo_bem, ds_bem, valor_bem
                )
                SELECT
                    CASE WHEN TRIM(c2) ~ '^\d+$' THEN CAST(TRIM(c2) AS SMALLINT) ELSE NULL END,
                    TRIM(c8), TRIM(c11), TRIM(c12),
                    TRIM(c13), TRIM(c14), TRIM(c15),
                    CASE WHEN TRIM(c16) ~ '^-?[\\d.,]+$' AND TRIM(c16) != ''
                         THEN CAST(REPLACE(REPLACE(TRIM(c16),'.',''),',','.') AS NUMERIC)
                         ELSE NULL END
                FROM {staging}
                WHERE TRIM(c2) ~ '^\d+$'
            """)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()


def run():
    conn = get_conn()
    try:
        from etl.config import SQL_DIR
        sql = (SQL_DIR / "16_schema_tse.sql").read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

        for year in [2020, 2022, 2024]:
            load_candidatos(conn, year)
            load_bens(conn, year)

        print(f"    tse_candidato: {table_count(conn, 'tse_candidato')} registros")
        print(f"    tse_bem_candidato: {table_count(conn, 'tse_bem_candidato')} registros")

        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_cand_cpf ON tse_candidato(cpf);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_cand_sq ON tse_candidato(sq_candidato, ano_eleicao);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_cand_partido ON tse_candidato(sg_partido);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_cand_nome ON tse_candidato USING gin(nm_candidato gin_trgm_ops);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_bem_sq ON tse_bem_candidato(sq_candidato, ano_eleicao);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_bem_valor ON tse_bem_candidato(valor_bem);")
        conn.commit()
        print("    Indices TSE criados.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
