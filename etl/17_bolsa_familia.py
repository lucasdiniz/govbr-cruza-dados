"""Carrega dados do Novo Bolsa Familia.

Fonte: portaldatransparencia.gov.br/download-de-dados/novo-bolsa-familia
Arquivos: YYYYMM_NovoBolsaFamilia.csv (;, Latin-1, com header, valor com virgula)
~20M registros por mes.
"""

from etl.config import DATA_DIR, SQL_DIR
from etl.db import get_conn, table_count


def run():
    conn = get_conn()
    try:
        sql = (SQL_DIR / "17_schema_bolsa_familia.sql").read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

        bf_dir = DATA_DIR / "bolsa_familia"
        files = sorted(bf_dir.glob("*_NovoBolsaFamilia.csv"))
        if not files:
            print("    AVISO: Nenhum arquivo *_NovoBolsaFamilia.csv encontrado.")
            return

        staging = "_stg_bolsa_familia"

        for filepath in files:
            print(f"    Carregando {filepath.name} para staging...")

            with conn.cursor() as cur:
                cur.execute(f"TRUNCATE {staging}")
            conn.commit()

            copy_sql = f"""COPY {staging} FROM STDIN WITH (
                FORMAT csv, DELIMITER ';', HEADER true, NULL '',
                ENCODING 'LATIN1', QUOTE '"'
            )"""

            with open(filepath, "rb") as f:
                with conn.cursor() as cur:
                    cur.copy_expert(copy_sql, f)
            conn.commit()

            print(f"    Inserindo em bolsa_familia...")
            with conn.cursor() as cur:
                cur.execute(f"""
                    INSERT INTO bolsa_familia (
                        mes_competencia, mes_referencia, uf, cd_municipio_siafi,
                        nm_municipio, cpf_favorecido, nis_favorecido, nm_favorecido,
                        valor_parcela
                    )
                    SELECT
                        TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3),
                        TRIM(c4), TRIM(c5), TRIM(c6), TRIM(c7),
                        CASE WHEN TRIM(c8) ~ '^[\\d.,]+$' AND TRIM(c8) != ''
                             THEN CAST(REPLACE(REPLACE(TRIM(c8), '.', ''), ',', '.') AS NUMERIC)
                             ELSE NULL END
                    FROM {staging}
                """)
            conn.commit()
            print(f"    {filepath.name} carregado.")

        # Limpar staging
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()

        count = table_count(conn, "bolsa_familia")
        print(f"    bolsa_familia: {count} registros")

        print("    Criando indices...")
        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bf_cpf ON bolsa_familia(cpf_favorecido);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bf_nis ON bolsa_familia(nis_favorecido);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bf_nome ON bolsa_familia USING gin(nm_favorecido gin_trgm_ops);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bf_municipio ON bolsa_familia(cd_municipio_siafi);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_bf_uf ON bolsa_familia(uf);")
        conn.commit()
        print("    Indices Bolsa Familia criados.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
