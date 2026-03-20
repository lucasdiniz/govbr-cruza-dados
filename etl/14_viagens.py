"""Carrega dados de Viagens a Servico do Governo Federal.

Fonte: portaldatransparencia.gov.br/download-de-dados/viagens
"""

import csv
import io

from tqdm import tqdm

from etl.config import DATA_DIR
from etl.db import get_conn, table_count


VIAGENS_DIR = DATA_DIR / "viagens"


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


def load_viagens(conn, year):
    """Carrega YYYY_Viagem.csv -> viagem."""
    filepath = VIAGENS_DIR / f"{year}_Viagem.csv"
    if not filepath.exists():
        print(f"    AVISO: {filepath.name} nao encontrado.")
        return

    staging = "_stg_viagem"
    _staging_load(conn, staging, 20, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO viagem (
                id_processo_viagem, numero_proposta, situacao,
                viagem_urgente, justificativa_urgencia,
                cod_orgao_superior, nome_orgao_superior,
                cod_orgao_solicitante, nome_orgao_solicitante,
                cpf_viajante, nome_viajante, cargo, funcao, descricao_funcao,
                dt_inicio, dt_fim, destinos, motivo,
                valor_diarias, valor_passagens
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4),
                TRIM(c5), TRIM(c6), TRIM(c7), TRIM(c8),
                TRIM(c9), TRIM(c10), TRIM(c11), TRIM(c12), TRIM(c13),
                safe_to_date(c14, 'DD/MM/YYYY'), safe_to_date(c15, 'DD/MM/YYYY'),
                TRIM(c16), TRIM(c17),
                CASE WHEN TRIM(c18) ~ '^-?[\\d.,]+$' AND TRIM(c18) != ''
                     THEN CAST(REPLACE(REPLACE(TRIM(c18),'.',''),',','.') AS NUMERIC)
                     ELSE NULL END,
                CASE WHEN TRIM(c19) ~ '^-?[\\d.,]+$' AND TRIM(c19) != ''
                     THEN CAST(REPLACE(REPLACE(TRIM(c19),'.',''),',','.') AS NUMERIC)
                     ELSE NULL END
            FROM {staging}
        """)
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()


def load_pagamentos(conn, year):
    """Carrega YYYY_Pagamento.csv -> viagem_pagamento."""
    filepath = VIAGENS_DIR / f"{year}_Pagamento.csv"
    if not filepath.exists():
        print(f"    AVISO: {filepath.name} nao encontrado.")
        return

    staging = "_stg_viagem_pag"
    _staging_load(conn, staging, 10, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO viagem_pagamento (
                id_processo_viagem, numero_proposta,
                cod_orgao_superior, nome_orgao_superior,
                cod_orgao_pagador, nome_orgao_pagador,
                cod_unidade_gestora, nome_unidade_gestora,
                tipo_pagamento, valor
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3),
                TRIM(c4), TRIM(c5), TRIM(c6), TRIM(c7),
                TRIM(c8),
                CASE WHEN TRIM(c9) ~ '^-?[\\d.,]+$' AND TRIM(c9) != ''
                     THEN CAST(REPLACE(REPLACE(TRIM(c9),'.',''),',','.') AS NUMERIC)
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
        from etl.config import SQL_DIR
        sql = (SQL_DIR / "14_schema_viagens.sql").read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

        for year in [2023, 2024]:
            print(f"    Carregando viagens {year}...")
            load_viagens(conn, year)
            load_pagamentos(conn, year)

        print(f"    viagem: {table_count(conn, 'viagem')} registros")
        print(f"    viagem_pagamento: {table_count(conn, 'viagem_pagamento')} registros")

        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_viagem_cpf ON viagem(cpf_viajante);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_viagem_orgao ON viagem(cod_orgao_solicitante);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_viagem_dt ON viagem(dt_inicio);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_viagem_nome ON viagem USING gin(nome_viajante gin_trgm_ops);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_viagem_destino ON viagem USING gin(destinos gin_trgm_ops);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_viagem_pag_processo ON viagem_pagamento(id_processo_viagem);")
        conn.commit()
        print("    Indices viagens criados.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
