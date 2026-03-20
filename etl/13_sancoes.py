"""Carrega dados de Sancoes (CEIS, CNEP, CEAF, Acordos de Leniencia).

Fonte: portaldatransparencia.gov.br/download-de-dados/
"""

import csv
import io

from etl.config import DATA_DIR
from etl.db import get_conn, table_count


SANCOES_DIR = DATA_DIR / "sancoes"


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
    next(reader, None)  # Skip header

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

    if buf.tell() > 0:
        buf.seek(0)
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, buf)
        conn.commit()


def load_ceis(conn):
    filepath = sorted(SANCOES_DIR.glob("*_CEIS.csv"))
    if not filepath:
        print("    AVISO: CEIS.csv nao encontrado.")
        return
    filepath = filepath[0]

    staging = "_stg_ceis"
    _staging_load(conn, staging, 24, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO ceis_sancao (
                cadastro, codigo_sancao, tipo_pessoa, cpf_cnpj_sancionado,
                nome_sancionado, nome_informado_orgao, razao_social_rfb, nome_fantasia_rfb,
                numero_processo, categoria_sancao,
                dt_inicio_sancao, dt_final_sancao, dt_publicacao,
                publicacao, detalhamento_publicacao, dt_transito_julgado,
                abrangencia_sancao, orgao_sancionador, uf_orgao_sancionador,
                esfera_orgao_sancionador, fundamentacao_legal,
                dt_origem_informacao, origem_informacoes, observacoes
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3),
                TRIM(c4), TRIM(c5), TRIM(c6), TRIM(c7),
                TRIM(c8), TRIM(c9),
                safe_to_date(c10, 'DD/MM/YYYY'), safe_to_date(c11, 'DD/MM/YYYY'),
                safe_to_date(c12, 'DD/MM/YYYY'),
                TRIM(c13), TRIM(c14), safe_to_date(c15, 'DD/MM/YYYY'),
                TRIM(c16), TRIM(c17), TRIM(c18), TRIM(c19), TRIM(c20),
                safe_to_date(c21, 'DD/MM/YYYY'), TRIM(c22), TRIM(c23)
            FROM {staging}
        """)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()
    print(f"    ceis_sancao: {table_count(conn, 'ceis_sancao')} registros")


def load_cnep(conn):
    filepath = sorted(SANCOES_DIR.glob("*_CNEP.csv"))
    if not filepath:
        print("    AVISO: CNEP.csv nao encontrado.")
        return
    filepath = filepath[0]

    staging = "_stg_cnep"
    _staging_load(conn, staging, 25, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO cnep_sancao (
                cadastro, codigo_sancao, tipo_pessoa, cpf_cnpj_sancionado,
                nome_sancionado, nome_informado_orgao, razao_social_rfb, nome_fantasia_rfb,
                numero_processo, categoria_sancao, valor_multa,
                dt_inicio_sancao, dt_final_sancao, dt_publicacao,
                publicacao, detalhamento_publicacao, dt_transito_julgado,
                abrangencia_sancao, orgao_sancionador, uf_orgao_sancionador,
                esfera_orgao_sancionador, fundamentacao_legal,
                dt_origem_informacao, origem_informacoes, observacoes
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3),
                TRIM(c4), TRIM(c5), TRIM(c6), TRIM(c7),
                TRIM(c8), TRIM(c9),
                CASE WHEN TRIM(c10) ~ '^[\\d.,-]+$' AND TRIM(c10) != ''
                     THEN CAST(REPLACE(REPLACE(TRIM(c10),'.',''),',','.') AS NUMERIC)
                     ELSE NULL END,
                safe_to_date(c11, 'DD/MM/YYYY'), safe_to_date(c12, 'DD/MM/YYYY'),
                safe_to_date(c13, 'DD/MM/YYYY'),
                TRIM(c14), TRIM(c15), safe_to_date(c16, 'DD/MM/YYYY'),
                TRIM(c17), TRIM(c18), TRIM(c19), TRIM(c20), TRIM(c21),
                safe_to_date(c22, 'DD/MM/YYYY'), TRIM(c23), TRIM(c24)
            FROM {staging}
        """)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()
    print(f"    cnep_sancao: {table_count(conn, 'cnep_sancao')} registros")


def load_ceaf(conn):
    filepath = sorted(SANCOES_DIR.glob("*_Expulsoes.csv"))
    if not filepath:
        print("    AVISO: Expulsoes.csv nao encontrado.")
        return
    filepath = filepath[0]

    staging = "_stg_ceaf"
    _staging_load(conn, staging, 25, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO ceaf_expulsao (
                cadastro, codigo_sancao, tipo_pessoa, cpf_cnpj_sancionado,
                nome_sancionado, categoria_sancao, numero_documento, numero_processo,
                dt_inicio_sancao, dt_final_sancao, dt_publicacao,
                publicacao, detalhamento_publicacao, dt_transito_julgado,
                abrangencia_sancao, cargo_efetivo, funcao_confianca,
                orgao_lotacao, orgao_sancionador, uf_orgao_sancionador,
                esfera_orgao_sancionador, fundamentacao_legal,
                dt_origem_informacao, origem_informacoes, observacoes
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3),
                TRIM(c4), TRIM(c5), TRIM(c6), TRIM(c7),
                safe_to_date(c8, 'DD/MM/YYYY'), safe_to_date(c9, 'DD/MM/YYYY'),
                safe_to_date(c10, 'DD/MM/YYYY'),
                TRIM(c11), TRIM(c12), safe_to_date(c13, 'DD/MM/YYYY'),
                TRIM(c14), TRIM(c15), TRIM(c16), TRIM(c17),
                TRIM(c18), TRIM(c19), TRIM(c20), TRIM(c21),
                safe_to_date(c22, 'DD/MM/YYYY'), TRIM(c23), TRIM(c24)
            FROM {staging}
        """)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()
    print(f"    ceaf_expulsao: {table_count(conn, 'ceaf_expulsao')} registros")


def load_acordos(conn):
    filepath = sorted(SANCOES_DIR.glob("*_Acordos.csv"))
    if not filepath:
        print("    AVISO: Acordos.csv nao encontrado.")
        return
    filepath = filepath[0]

    staging = "_stg_acordos"
    _staging_load(conn, staging, 11, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO acordo_leniencia (
                id_acordo, cnpj_sancionado, razao_social_rfb, nome_fantasia_rfb,
                dt_inicio_acordo, dt_fim_acordo, situacao_acordo,
                dt_informacao, numero_processo, termos_acordo, orgao_sancionador
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3),
                safe_to_date(c4, 'DD/MM/YYYY'), safe_to_date(c5, 'DD/MM/YYYY'),
                TRIM(c6), safe_to_date(c7, 'DD/MM/YYYY'),
                TRIM(c8), TRIM(c9), TRIM(c10)
            FROM {staging}
        """)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()
    print(f"    acordo_leniencia: {table_count(conn, 'acordo_leniencia')} registros")

    # Efeitos
    filepath = sorted(SANCOES_DIR.glob("*_Efeitos.csv"))
    if not filepath:
        return
    filepath = filepath[0]

    staging = "_stg_efeitos"
    _staging_load(conn, staging, 3, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO acordo_efeito (id_acordo, efeito, complemento)
            SELECT TRIM(c0), TRIM(c1), TRIM(c2) FROM {staging}
        """)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()
    print(f"    acordo_efeito: {table_count(conn, 'acordo_efeito')} registros")


def run():
    conn = get_conn()
    try:
        from etl.config import SQL_DIR
        sql = (SQL_DIR / "13_schema_sancoes.sql").read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

        load_ceis(conn)
        load_cnep(conn)
        load_ceaf(conn)
        load_acordos(conn)

        # Indices
        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_ceis_cpf_cnpj ON ceis_sancao(cpf_cnpj_sancionado);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_ceis_vigencia ON ceis_sancao(dt_inicio_sancao, dt_final_sancao);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_cnep_cpf_cnpj ON cnep_sancao(cpf_cnpj_sancionado);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_ceaf_cpf_cnpj ON ceaf_expulsao(cpf_cnpj_sancionado);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_acordo_cnpj ON acordo_leniencia(cnpj_sancionado);")
        conn.commit()
        print("    Indices sancoes criados.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
