"""Fase 5.1: Carrega dados da PGFN (Dívida Ativa da União).

Fonte: pgfn_0..5.csv (delimitador ;, com header, encoding Latin-1, ~6.3GB total)
"""

from tqdm import tqdm

from etl.config import DATA_DIR
from etl.db import get_conn, table_count


def run():
    conn = get_conn()
    try:
        pgfn_dir = DATA_DIR / "pgfn"
        files = sorted(pgfn_dir.glob("arquivo_lai_*.csv")) if pgfn_dir.exists() else []
        if not files:
            # Fallback: busca no DATA_DIR raiz (layout antigo)
            files = sorted(DATA_DIR.glob("pgfn_*.csv"))
        if not files:
            print("    AVISO: Nenhum arquivo PGFN encontrado (pgfn/ ou pgfn_*.csv).")
            return

        staging = "_stg_pgfn"

        for filepath in tqdm(files, desc="    PGFN"):
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
                cur.execute(f"""CREATE UNLOGGED TABLE {staging} (
                    c0 TEXT, c1 TEXT, c2 TEXT, c3 TEXT, c4 TEXT,
                    c5 TEXT, c6 TEXT, c7 TEXT, c8 TEXT, c9 TEXT,
                    c10 TEXT, c11 TEXT, c12 TEXT
                )""")
            conn.commit()

            copy_sql = f"""COPY {staging} FROM STDIN
                WITH (FORMAT csv, DELIMITER ';', HEADER true, NULL '', ENCODING 'LATIN1')"""
            with open(filepath, "rb") as f:
                with conn.cursor() as cur:
                    cur.copy_expert(copy_sql, f)
            conn.commit()

            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO pgfn_divida (
                        cpf_cnpj, tipo_pessoa, tipo_devedor, nome_devedor,
                        uf_devedor, unidade_responsavel, numero_inscricao,
                        tipo_situacao_inscricao, situacao_inscricao,
                        receita_principal, dt_inscricao, indicador_ajuizado,
                        valor_consolidado
                    )
                    SELECT
                        TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4),
                        TRIM(c5), TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9),
                        CASE WHEN TRIM(c10) ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$' THEN safe_to_date(TRIM(c10), 'DD/MM/YYYY') ELSE NULL END,
                        TRIM(c11),
                        CASE WHEN TRIM(c12) = '' THEN NULL
                             ELSE CAST(REPLACE(REPLACE(TRIM(c12), '.', ''), ',', '.') AS NUMERIC)
                        END
                    FROM {staging}
                """)
            conn.commit()

            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()

        print(f"    pgfn_divida: {table_count(conn, 'pgfn_divida')} registros")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
