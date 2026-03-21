"""Fase 4.6: Carrega dados do Cartão de Pagamento do Governo Federal (CPGF).

Fonte: cpgf_0..60.csv (delimitador ;, com header, campos quoted, encoding Latin-1)
"""

from tqdm import tqdm

from etl.config import DATA_DIR
from etl.db import get_conn, table_count


def run():
    conn = get_conn()
    try:
        # Busca em DATA_DIR/cpgf_*.csv (legado) e DATA_DIR/cpgf/*.csv (novo)
        files = sorted(DATA_DIR.glob("cpgf_*.csv")) + sorted((DATA_DIR / "cpgf").glob("*.csv"))
        files = sorted(set(files))  # deduplica
        if not files:
            print("    AVISO: Nenhum arquivo CPGF encontrado.")
            return

        staging = "_stg_cpgf"

        for filepath in tqdm(files, desc="    CPGF"):
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
                cur.execute(f"""CREATE UNLOGGED TABLE {staging} (
                    c0 TEXT, c1 TEXT, c2 TEXT, c3 TEXT, c4 TEXT,
                    c5 TEXT, c6 TEXT, c7 TEXT, c8 TEXT, c9 TEXT,
                    c10 TEXT, c11 TEXT, c12 TEXT, c13 TEXT, c14 TEXT
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
                    INSERT INTO cpgf_transacao (
                        codigo_orgao_superior, nome_orgao_superior,
                        codigo_orgao, nome_orgao,
                        codigo_unidade_gestora, nome_unidade_gestora,
                        ano_extrato, mes_extrato,
                        cpf_portador, nome_portador,
                        cnpj_cpf_favorecido, nome_favorecido,
                        tipo_transacao, dt_transacao, valor_transacao
                    )
                    SELECT
                        TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4), TRIM(c5),
                        CASE WHEN TRIM(c6) ~ '^\d+$' THEN CAST(TRIM(c6) AS SMALLINT) ELSE NULL END,
                        CASE WHEN TRIM(c7) ~ '^\d+$' THEN CAST(TRIM(c7) AS SMALLINT) ELSE NULL END,
                        TRIM(c8), TRIM(c9), TRIM(c10), TRIM(c11), TRIM(c12),
                        CASE WHEN TRIM(c13) ~ '^\d{2}/\d{2}/\d{4}$' THEN safe_to_date(TRIM(c13), 'DD/MM/YYYY') ELSE NULL END,
                        CASE WHEN TRIM(c14) = '' THEN NULL
                             ELSE CAST(REPLACE(REPLACE(TRIM(c14), '.', ''), ',', '.') AS NUMERIC)
                        END
                    FROM {staging}
                """)
            conn.commit()

            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()

        print(f"    cpgf_transacao: {table_count(conn, 'cpgf_transacao')} registros")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
