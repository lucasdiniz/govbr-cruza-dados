"""Carrega dados de Servidores Federais (SIAPE).

Fonte: 202402_Cadastro.csv e 202402_Remuneracao.csv
"""

import csv
import io

from tqdm import tqdm

from etl.config import DATA_DIR
from etl.db import get_conn, table_count


SIAPE_DIR = DATA_DIR / "siape"


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


def load_cadastro(conn):
    """Carrega *_Cadastro.csv -> siape_cadastro (pega o mais recente)."""
    files = sorted(SIAPE_DIR.glob("*_Cadastro.csv"))
    if not files:
        print("    AVISO: Nenhum arquivo *_Cadastro.csv encontrado.")
        return
    filepath = files[-1]  # Mais recente
    print(f"    Usando: {filepath.name}")
    if not filepath.exists():
        return

    staging = "_stg_siape_cad"
    print("    Carregando Cadastro SIAPE...")
    _staging_load(conn, staging, 43, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO siape_cadastro (
                id_servidor_portal, nome, cpf, matricula,
                descricao_cargo, classe_cargo, referencia_cargo, padrao_cargo, nivel_cargo,
                sigla_funcao, nivel_funcao, funcao, codigo_atividade, atividade, opcao_parcial,
                cod_uorg_lotacao, uorg_lotacao, cod_org_lotacao, org_lotacao,
                cod_orgsup_lotacao, orgsup_lotacao,
                cod_uorg_exercicio, uorg_exercicio, cod_org_exercicio, org_exercicio,
                cod_orgsup_exercicio, orgsup_exercicio,
                cod_tipo_vinculo, tipo_vinculo, situacao_vinculo,
                dt_inicio_afastamento, dt_termino_afastamento,
                regime_juridico, jornada_trabalho,
                dt_ingresso_cargofuncao, dt_nomeacao_cargofuncao, dt_ingresso_orgao,
                documento_ingresso, dt_diploma_ingresso,
                diploma_ingresso_cargofuncao, diploma_ingresso_orgao,
                diploma_ingresso_servpublico, uf_exercicio
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3),
                TRIM(c4), TRIM(c5), TRIM(c6), TRIM(c7), TRIM(c8),
                TRIM(c9), TRIM(c10), TRIM(c11), TRIM(c12), TRIM(c13), TRIM(c14),
                TRIM(c15), TRIM(c16), TRIM(c17), TRIM(c18),
                TRIM(c19), TRIM(c20),
                TRIM(c21), TRIM(c22), TRIM(c23), TRIM(c24),
                TRIM(c25), TRIM(c26),
                TRIM(c27), TRIM(c28), TRIM(c29),
                safe_to_date(TRIM(c30), 'DD/MM/YYYY'),
                safe_to_date(TRIM(c31), 'DD/MM/YYYY'),
                TRIM(c32), TRIM(c33),
                safe_to_date(TRIM(c34), 'DD/MM/YYYY'),
                safe_to_date(TRIM(c35), 'DD/MM/YYYY'),
                safe_to_date(TRIM(c36), 'DD/MM/YYYY'),
                TRIM(c37), TRIM(c38),
                TRIM(c39), TRIM(c40), TRIM(c41), TRIM(c42)
            FROM {staging}
            ON CONFLICT (id_servidor_portal) DO NOTHING
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()

    print(f"    siape_cadastro: {table_count(conn, 'siape_cadastro')} registros")


def load_remuneracao(conn):
    """Carrega *_Remuneracao.csv -> siape_remuneracao (pega o mais recente)."""
    files = sorted(SIAPE_DIR.glob("*_Remuneracao.csv"))
    if not files:
        print("    AVISO: Nenhum arquivo *_Remuneracao.csv encontrado.")
        return
    filepath = files[-1]
    print(f"    Usando: {filepath.name}")

    staging = "_stg_siape_rem"
    print("    Carregando Remuneracao SIAPE...")
    # 39 colunas, mas ignoramos as colunas em U$ (pares)
    _staging_load(conn, staging, 39, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO siape_remuneracao (
                ano, mes, id_servidor_portal, cpf, nome,
                remuneracao_basica_bruta, abate_teto, gratificacao_natalina,
                abate_teto_natalina, ferias, outras_remuneracoes,
                irrf, pss_rpgs, demais_deducoes, pensao_militar,
                fundo_saude, taxa_imovel_funcional,
                remuneracao_apos_deducoes,
                verbas_indenizatorias_civil, verbas_indenizatorias_militar,
                verbas_desligamento, total_verbas_indenizatorias
            )
            SELECT
                CASE WHEN TRIM(c0) ~ '^\\d+$' THEN CAST(TRIM(c0) AS SMALLINT) ELSE NULL END,
                CASE WHEN TRIM(c1) ~ '^\\d+$' THEN CAST(TRIM(c1) AS SMALLINT) ELSE NULL END,
                TRIM(c2), TRIM(c3), TRIM(c4),
                -- Pega so colunas R$ (indices pares a partir de c5), ignora U$ (impares)
                CASE WHEN TRIM(c5) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c5),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c7) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c7),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c9) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c9),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c11) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c11),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c13) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c13),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c15) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c15),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c17) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c17),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c19) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c19),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c21) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c21),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c23) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c23),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c25) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c25),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c27) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c27),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c29) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c29),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c31) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c31),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c33) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c33),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c35) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c35),'.',''),',','.') AS NUMERIC) ELSE NULL END,
                CASE WHEN TRIM(c37) ~ '^-?[\\d.,]+$' THEN CAST(REPLACE(REPLACE(TRIM(c37),'.',''),',','.') AS NUMERIC) ELSE NULL END
            FROM {staging}
            WHERE TRIM(c2) IS NOT NULL AND TRIM(c2) != ''
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()

    print(f"    siape_remuneracao: {table_count(conn, 'siape_remuneracao')} registros")


def run():
    conn = get_conn()
    try:
        # Criar tabelas
        from etl.config import SQL_DIR
        sql = (SQL_DIR / "06_schema_siape.sql").read_text(encoding="utf-8")
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()

        load_cadastro(conn)
        load_remuneracao(conn)

        # Indices
        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS idx_siape_cad_cpf ON siape_cadastro(cpf);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_siape_cad_nome ON siape_cadastro USING gin(nome gin_trgm_ops);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_siape_cad_org ON siape_cadastro(cod_org_exercicio);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_siape_cad_uf ON siape_cadastro(uf_exercicio);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_siape_rem_servidor ON siape_remuneracao(id_servidor_portal);")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_siape_rem_cpf ON siape_remuneracao(cpf);")
        conn.commit()
        print("    Indices SIAPE criados.")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
