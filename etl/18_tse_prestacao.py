"""Carrega prestacao de contas eleitorais (receitas e despesas de campanha).

Fonte: dadosabertos.tse.jus.br
Zips: prestacao_contas_candidatos_YYYY.zip
CSVs: receitas_candidatos_YYYY_UF.csv, despesas_pagas_candidatos_YYYY_UF.csv
Delimitador: ;  Encoding: Latin-1  Quote: "
"""

import csv
import io
import zipfile
from pathlib import Path

from tqdm import tqdm

from etl.config import DATA_DIR, SQL_DIR
from etl.db import get_conn, table_count

TSE_DIR = DATA_DIR / "tse"


def _copy_batch(conn, copy_sql, buf):
    """Flush buffer via COPY."""
    if buf.tell() > 0:
        buf.seek(0)
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, buf)
        conn.commit()


def _clean_val(val):
    """Limpa valor para TSV."""
    if val is None or val == "" or val == "#NULO" or val == "#NE" or val == "-1" or val == "-4":
        return "\\N"
    val = val.replace("\\", "\\\\").replace("\t", " ").replace("\n", " ").replace("\r", "")
    return val


def _parse_money(val):
    """Converte '15000,00' -> '15000.00'."""
    if val is None or val == "" or val == "#NULO" or val == "#NE":
        return "\\N"
    return val.replace(".", "").replace(",", ".")


def _parse_date(val):
    """Converte DD/MM/YYYY -> YYYY-MM-DD."""
    if val is None or val == "" or val == "#NULO" or val == "#NE":
        return "\\N"
    parts = val.strip().split("/")
    if len(parts) == 3 and len(parts[2]) == 4:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return "\\N"


def load_receitas(conn, year):
    """Carrega receitas_candidatos_YYYY_*.csv -> tse_receita_candidato."""
    prestacao_dir = TSE_DIR / f"prestacao_{year}"
    zip_path = TSE_DIR / f"prestacao_contas_candidatos_{year}.zip"

    if not prestacao_dir.exists() and zip_path.exists():
        print(f"    Extraindo {zip_path.name}...")
        prestacao_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as z:
            for name in z.namelist():
                if "receitas_candidatos_" in name or "despesas_pagas_candidatos_" in name:
                    z.extract(name, prestacao_dir)

    # Pegar arquivos por UF (ignorar o _BRASIL que e agregado)
    files = sorted(prestacao_dir.glob(f"receitas_candidatos_{year}_*.csv"))
    files = [f for f in files if "_BRASIL" not in f.name]
    if not files:
        print(f"    AVISO: Nenhum arquivo de receitas {year}.")
        return

    # Campos: c2=AA_ELEICAO, c12=SG_UF, c11=SQ_PRESTADOR,
    # c15=NR_CNPJ_PRESTADOR, c16=CD_CARGO, c17=DS_CARGO,
    # c18=SQ_CANDIDATO, c19=NR_CANDIDATO, c20=NM_CANDIDATO, c21=NR_CPF_CANDIDATO,
    # c23=NR_PARTIDO, c24=SG_PARTIDO, c25=NM_PARTIDO,
    # c27=DS_FONTE_RECEITA, c29=DS_ORIGEM_RECEITA, c31=DS_NATUREZA_RECEITA,
    # c33=DS_ESPECIE_RECEITA, c34=CD_CNAE_DOADOR, c35=DS_CNAE_DOADOR,
    # c36=NR_CPF_CNPJ_DOADOR, c37=NM_DOADOR, c38=NM_DOADOR_RFB,
    # c41=SG_UF_DOADOR, c43=NM_MUNICIPIO_DOADOR, c44=SQ_CANDIDATO_DOADOR,
    # c49=SG_PARTIDO_DOADOR, c50=NM_PARTIDO_DOADOR, c51=NR_RECIBO_DOACAO,
    # c52=NR_DOCUMENTO_DOACAO, c53=SQ_RECEITA, c54=DT_RECEITA,
    # c55=DS_RECEITA, c56=VR_RECEITA, c57=DS_NATUREZA_RECURSO_ESTIMAVEL,
    # c58=DS_GENERO, c59=DS_COR_RACA

    n_cols = 60  # total columns in receitas CSV
    staging = "_stg_tse_rec"
    col_defs = ", ".join(f"c{i} TEXT" for i in range(n_cols))
    cols = ", ".join(f"c{i}" for i in range(n_cols))
    copy_sql = f"""COPY {staging} ({cols}) FROM STDIN
        WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N')"""

    for filepath in tqdm(files, desc=f"    Receitas {year}"):
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
            cur.execute(f"CREATE UNLOGGED TABLE {staging} ({col_defs})")
        conn.commit()

        buf = io.BytesIO()
        count = 0

        with open(filepath, "r", encoding="latin-1", errors="replace") as f:
            reader = csv.reader(f, delimiter=";", quotechar='"')
            next(reader, None)  # skip header
            for row in reader:
                if len(row) > n_cols:
                    row = row[:n_cols]
                elif len(row) < n_cols:
                    row = row + [""] * (n_cols - len(row))
                line = "\t".join(_clean_val(v) for v in row) + "\n"
                buf.write(line.encode("utf-8"))
                count += 1
                if count % 100000 == 0:
                    _copy_batch(conn, copy_sql, buf)
                    buf = io.BytesIO()

        _copy_batch(conn, copy_sql, buf)

        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO tse_receita_candidato (
                    ano_eleicao, sg_uf, sq_prestador_contas, nr_cnpj_prestador,
                    cd_cargo, ds_cargo, sq_candidato, nr_candidato,
                    nm_candidato, nr_cpf_candidato, nr_partido, sg_partido, nm_partido,
                    ds_fonte_receita, ds_origem_receita, ds_natureza_receita,
                    ds_especie_receita, cd_cnae_doador, ds_cnae_doador,
                    cpf_cnpj_doador, nm_doador, nm_doador_rfb,
                    sg_uf_doador, nm_municipio_doador, sq_candidato_doador,
                    sg_partido_doador, nr_recibo_doacao, sq_receita,
                    dt_receita, ds_receita, vr_receita,
                    ds_genero, ds_cor_raca
                )
                SELECT
                    CASE WHEN TRIM(c2) ~ '^\d+$' THEN TRIM(c2)::SMALLINT ELSE NULL END,
                    NULLIF(TRIM(c12), ''),
                    NULLIF(TRIM(c11), ''),
                    NULLIF(TRIM(c15), ''),
                    NULLIF(TRIM(c16), ''),
                    NULLIF(TRIM(c17), ''),
                    NULLIF(TRIM(c18), ''),
                    NULLIF(TRIM(c19), ''),
                    NULLIF(TRIM(c20), ''),
                    NULLIF(TRIM(c21), ''),
                    NULLIF(TRIM(c23), ''),
                    NULLIF(TRIM(c24), ''),
                    NULLIF(TRIM(c25), ''),
                    NULLIF(TRIM(c27), ''),
                    NULLIF(TRIM(c29), ''),
                    NULLIF(TRIM(c31), ''),
                    NULLIF(TRIM(c33), ''),
                    NULLIF(TRIM(c34), ''),
                    NULLIF(TRIM(c35), ''),
                    NULLIF(TRIM(c36), ''),
                    NULLIF(TRIM(c37), ''),
                    NULLIF(TRIM(c38), ''),
                    NULLIF(TRIM(c41), ''),
                    NULLIF(TRIM(c43), ''),
                    NULLIF(TRIM(c44), ''),
                    NULLIF(TRIM(c49), ''),
                    NULLIF(TRIM(c51), ''),
                    NULLIF(TRIM(c53), ''),
                    CASE WHEN TRIM(c54) ~ '^\d{{2}}/\d{{2}}/\d{{4}}$'
                         THEN safe_to_date(TRIM(c54), 'DD/MM/YYYY') ELSE NULL END,
                    NULLIF(TRIM(c55), ''),
                    CASE WHEN TRIM(c56) ~ '^[\d.,]+$' AND TRIM(c56) != ''
                         THEN CAST(REPLACE(REPLACE(TRIM(c56),'.',''),',','.') AS NUMERIC)
                         ELSE NULL END,
                    NULLIF(TRIM(c58), ''),
                    NULLIF(TRIM(c59), '')
                FROM {staging}
                WHERE TRIM(c2) ~ '^\d+$'
            """)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()


def load_despesas(conn, year):
    """Carrega despesas_pagas_candidatos_YYYY_*.csv -> tse_despesa_candidato."""
    prestacao_dir = TSE_DIR / f"prestacao_{year}"
    files = sorted(prestacao_dir.glob(f"despesas_pagas_candidatos_{year}_*.csv"))
    files = [f for f in files if "_BRASIL" not in f.name]
    if not files:
        print(f"    AVISO: Nenhum arquivo de despesas {year}.")
        return

    # c2=AA_ELEICAO, c12=SG_UF, c11=SQ_PRESTADOR, c13=DS_TIPO_DOCUMENTO,
    # c14=NR_DOCUMENTO, c16=DS_FONTE_DESPESA, c18=DS_ORIGEM_DESPESA,
    # c20=DS_NATUREZA_DESPESA, c22=DS_ESPECIE_RECURSO,
    # c23=SQ_DESPESA, c24=SQ_PARCELAMENTO, c25=DT_PAGTO,
    # c26=DS_DESPESA, c27=VR_PAGTO

    n_cols = 28
    staging = "_stg_tse_desp"
    col_defs = ", ".join(f"c{i} TEXT" for i in range(n_cols))
    cols = ", ".join(f"c{i}" for i in range(n_cols))
    copy_sql = f"""COPY {staging} ({cols}) FROM STDIN
        WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N')"""

    for filepath in tqdm(files, desc=f"    Despesas {year}"):
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
            cur.execute(f"CREATE UNLOGGED TABLE {staging} ({col_defs})")
        conn.commit()

        buf = io.BytesIO()
        count = 0

        with open(filepath, "r", encoding="latin-1", errors="replace") as f:
            reader = csv.reader(f, delimiter=";", quotechar='"')
            next(reader, None)
            for row in reader:
                if len(row) > n_cols:
                    row = row[:n_cols]
                elif len(row) < n_cols:
                    row = row + [""] * (n_cols - len(row))
                line = "\t".join(_clean_val(v) for v in row) + "\n"
                buf.write(line.encode("utf-8"))
                count += 1
                if count % 100000 == 0:
                    _copy_batch(conn, copy_sql, buf)
                    buf = io.BytesIO()

        _copy_batch(conn, copy_sql, buf)

        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO tse_despesa_candidato (
                    ano_eleicao, sg_uf, sq_prestador_contas,
                    ds_tipo_documento, nr_documento,
                    ds_fonte_despesa, ds_origem_despesa,
                    ds_natureza_despesa, ds_especie_recurso,
                    sq_despesa, sq_parcelamento, dt_pagto_despesa,
                    ds_despesa, vr_pagto_despesa
                )
                SELECT
                    CASE WHEN TRIM(c2) ~ '^\d+$' THEN TRIM(c2)::SMALLINT ELSE NULL END,
                    NULLIF(TRIM(c12), ''),
                    NULLIF(TRIM(c11), ''),
                    NULLIF(TRIM(c13), ''),
                    NULLIF(TRIM(c14), ''),
                    NULLIF(TRIM(c16), ''),
                    NULLIF(TRIM(c18), ''),
                    NULLIF(TRIM(c20), ''),
                    NULLIF(TRIM(c22), ''),
                    NULLIF(TRIM(c23), ''),
                    NULLIF(TRIM(c24), ''),
                    CASE WHEN TRIM(c25) ~ '^\d{{2}}/\d{{2}}/\d{{4}}$'
                         THEN safe_to_date(TRIM(c25), 'DD/MM/YYYY') ELSE NULL END,
                    NULLIF(TRIM(c26), ''),
                    CASE WHEN TRIM(c27) ~ '^[\d.,]+$' AND TRIM(c27) != ''
                         THEN CAST(REPLACE(REPLACE(TRIM(c27),'.',''),',','.') AS NUMERIC)
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
        sql = (SQL_DIR / "18_schema_tse_prestacao.sql").read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

        for year in [2022, 2024]:
            load_receitas(conn, year)
            load_despesas(conn, year)

        print(f"    tse_receita_candidato: {table_count(conn, 'tse_receita_candidato')} registros")
        print(f"    tse_despesa_candidato: {table_count(conn, 'tse_despesa_candidato')} registros")

        print("    Criando indices...")
        with conn.cursor() as cur:
            # Receitas
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_rec_cpf_cand ON tse_receita_candidato(nr_cpf_candidato);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_rec_cpf_doador ON tse_receita_candidato(cpf_cnpj_doador);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_rec_sq ON tse_receita_candidato(sq_candidato, ano_eleicao);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_rec_partido ON tse_receita_candidato(sg_partido);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_rec_valor ON tse_receita_candidato(vr_receita);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_rec_doador_nome ON tse_receita_candidato USING gin(nm_doador gin_trgm_ops);")
            # Despesas
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_desp_sq ON tse_despesa_candidato(sq_prestador_contas);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_tse_desp_valor ON tse_despesa_candidato(vr_pagto_despesa);")
        conn.commit()
        print("    Indices TSE prestacao criados.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
