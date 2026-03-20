"""Fase 3: Carrega dados da Receita Federal (Empresas, Estabelecimentos, Sócios, Simples).

Arquivos sem header, delimitador ;, encoding Latin-1, decimais com vírgula.
Usa COPY via staging table UNLOGGED para máxima performance.
"""

import io
import glob
from pathlib import Path

from tqdm import tqdm

from etl.config import DATA_DIR, RFB_ENCODING
from etl.db import get_conn, table_count


def _staging_copy(conn, staging_table: str, n_cols: int, filepath: Path):
    """
    Cria staging table UNLOGGED com N colunas TEXT.
    Usa Python csv reader para parsear corretamente campos com ; dentro de aspas,
    e normaliza para exatamente n_cols campos. Envia como TSV via COPY.
    """
    import csv
    import io

    col_defs = ", ".join(f"c{i} TEXT" for i in range(n_cols))
    cols = ", ".join(f"c{i}" for i in range(n_cols))

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging_table}")
        cur.execute(f"CREATE UNLOGGED TABLE {staging_table} ({col_defs})")
    conn.commit()

    # Usa TAB como delimitador interno (nao aparece nos dados)
    copy_sql = f"""COPY {staging_table} ({cols}) FROM STDIN
        WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N')"""

    buf = io.BytesIO()
    flush_every = 100000  # flush a cada 100k linhas
    count = 0

    def _clean_lines(filepath):
        """Generator que le Latin-1, remove NUL bytes."""
        with open(filepath, "r", encoding="latin-1", errors="replace") as f:
            for line in f:
                yield line.replace("\x00", "")

    reader = csv.reader(_clean_lines(filepath), delimiter=";", quotechar='"')
    for row in reader:
        # Normaliza para exatamente n_cols campos
        if len(row) > n_cols:
            row = row[:n_cols]
        elif len(row) < n_cols:
            row = row + [""] * (n_cols - len(row))

        # Escape para formato TEXT do PostgreSQL
        escaped = []
        for val in row:
            if val == "" or val is None:
                escaped.append("\\N")
            else:
                val = val.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "")
                escaped.append(val)

        buf.write(("\t".join(escaped) + "\n").encode("utf-8"))
        count += 1

        if count % flush_every == 0:
            buf.seek(0)
            with conn.cursor() as cur:
                cur.copy_expert(copy_sql, buf)
            conn.commit()
            buf = io.BytesIO()

    # Flush restante
    if buf.tell() > 0:
        buf.seek(0)
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, buf)
        conn.commit()


def _get_files(pattern: str) -> list[Path]:
    """Retorna arquivos ordenados pelo nome."""
    files = sorted(DATA_DIR.glob(pattern))
    return files


def load_empresas(conn):
    """Carrega Empresas0..9.csv -> tabela empresa."""
    files = _get_files("Empresas*.csv")
    if not files:
        print("    AVISO: Nenhum arquivo Empresas*.csv encontrado.")
        return

    staging = "_stg_empresa"

    for filepath in tqdm(files, desc="    Empresas"):
        _staging_copy(conn, staging, 7, filepath)

        with conn.cursor() as cur:
            # Filtra linhas corrompidas: c5 (porte) deve ser numerico 1-2 digitos
            # e c4 (capital_social) deve parecer um numero decimal BR
            cur.execute(f"""
                INSERT INTO empresa (cnpj_basico, razao_social, natureza_juridica,
                                     qualif_responsavel, capital_social, porte, ente_federativo)
                SELECT
                    LPAD(TRIM(c0), 8, '0'),
                    TRIM(c1),
                    NULLIF(TRIM(c2), ''),
                    NULLIF(TRIM(c3), ''),
                    CASE WHEN TRIM(c4) ~ '^[\d.,]+$' AND TRIM(c4) != ''
                         THEN CAST(REPLACE(TRIM(c4), ',', '.') AS DECIMAL(15,2))
                         ELSE NULL
                    END,
                    CASE WHEN TRIM(c5) ~ '^\d{{1,2}}$'
                         THEN CAST(TRIM(c5) AS SMALLINT)
                         ELSE NULL
                    END,
                    NULLIF(TRIM(c6), '')
                FROM {staging}
                WHERE LENGTH(TRIM(c0)) = 8 AND TRIM(c0) ~ '^\d+$'
                ON CONFLICT (cnpj_basico) DO NOTHING
            """)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()

    print(f"    empresa: {table_count(conn, 'empresa')} registros")


def load_estabelecimentos(conn):
    """Carrega Estabelecimentos0..9.csv → tabela estabelecimento."""
    files = _get_files("Estabelecimentos*.csv")
    if not files:
        print("    AVISO: Nenhum arquivo Estabelecimentos*.csv encontrado.")
        return

    staging = "_stg_estab"

    for filepath in tqdm(files, desc="    Estabelecimentos"):
        _staging_copy(conn, staging, 30, filepath)

        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO estabelecimento (
                    cnpj_basico, cnpj_ordem, cnpj_dv, matriz_filial,
                    nome_fantasia, situacao_cadastral, dt_situacao, motivo_situacao,
                    nome_cidade_exterior, pais, dt_inicio_atividade,
                    cnae_principal, cnae_secundaria,
                    tipo_logradouro, logradouro, numero, complemento, bairro,
                    cep, uf, municipio,
                    ddd1, telefone1, ddd2, telefone2, ddd_fax, fax,
                    email, situacao_especial, dt_situacao_especial
                )
                SELECT
                    LPAD(TRIM(c0), 8, '0'),
                    LPAD(TRIM(c1), 4, '0'),
                    LPAD(TRIM(c2), 2, '0'),
                    CASE WHEN TRIM(c3) ~ '^\d+$' THEN CAST(TRIM(c3) AS SMALLINT) ELSE NULL END,
                    NULLIF(TRIM(c4), ''),
                    CASE WHEN TRIM(c5) ~ '^\d+$' THEN CAST(TRIM(c5) AS SMALLINT) ELSE NULL END,
                    CASE WHEN TRIM(c6) ~ '^\d{{8}}$' AND TRIM(c6) != '00000000'
                         THEN safe_to_date(TRIM(c6), 'YYYYMMDD') ELSE NULL END,
                    NULLIF(TRIM(c7), ''),
                    NULLIF(TRIM(c8), ''),
                    NULLIF(TRIM(c9), ''),
                    CASE WHEN TRIM(c10) ~ '^\d{{8}}$' AND TRIM(c10) != '00000000'
                         THEN safe_to_date(TRIM(c10), 'YYYYMMDD') ELSE NULL END,
                    NULLIF(TRIM(c11), ''),
                    NULLIF(TRIM(c12), ''),
                    NULLIF(TRIM(c13), ''),
                    NULLIF(TRIM(c14), ''),
                    NULLIF(TRIM(c15), ''),
                    NULLIF(TRIM(c16), ''),
                    NULLIF(TRIM(c17), ''),
                    NULLIF(TRIM(c18), ''),
                    NULLIF(TRIM(c19), ''),
                    NULLIF(TRIM(c20), ''),
                    NULLIF(TRIM(c21), ''),
                    NULLIF(TRIM(c22), ''),
                    NULLIF(TRIM(c23), ''),
                    NULLIF(TRIM(c24), ''),
                    NULLIF(TRIM(c25), ''),
                    NULLIF(TRIM(c26), ''),
                    NULLIF(TRIM(c27), ''),
                    NULLIF(TRIM(c28), ''),
                    CASE WHEN TRIM(c29) ~ '^\d{{8}}$' AND TRIM(c29) != '00000000'
                         THEN safe_to_date(TRIM(c29), 'YYYYMMDD') ELSE NULL END
                FROM {staging}
                WHERE LENGTH(TRIM(c0)) = 8 AND TRIM(c0) ~ '^\d+$'
                ON CONFLICT (cnpj_basico, cnpj_ordem, cnpj_dv) DO NOTHING
            """)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()

    print(f"    estabelecimento: {table_count(conn, 'estabelecimento')} registros")


def load_socios(conn):
    """Carrega Socios0..9.csv → tabela socio."""
    files = _get_files("Socios*.csv")
    if not files:
        print("    AVISO: Nenhum arquivo Socios*.csv encontrado.")
        return

    staging = "_stg_socio"

    for filepath in tqdm(files, desc="    Sócios"):
        _staging_copy(conn, staging, 11, filepath)

        with conn.cursor() as cur:
            cur.execute(f"""
                INSERT INTO socio (
                    cnpj_basico, tipo_socio, nome, cpf_cnpj_socio,
                    qualificacao, dt_entrada, pais,
                    cpf_representante, nome_representante, qualif_representante,
                    faixa_etaria
                )
                SELECT
                    LPAD(TRIM(c0), 8, '0'),
                    CASE WHEN TRIM(c1) ~ '^\d+$' THEN CAST(TRIM(c1) AS SMALLINT) ELSE NULL END,
                    NULLIF(TRIM(c2), ''),
                    NULLIF(TRIM(c3), ''),
                    NULLIF(TRIM(c4), ''),
                    CASE WHEN TRIM(c5) ~ '^\d{{8}}$' AND TRIM(c5) != '00000000'
                         THEN safe_to_date(TRIM(c5), 'YYYYMMDD') ELSE NULL END,
                    NULLIF(TRIM(c6), ''),
                    NULLIF(TRIM(c7), ''),
                    NULLIF(TRIM(c8), ''),
                    NULLIF(TRIM(c9), ''),
                    CASE WHEN TRIM(c10) ~ '^\d+$' THEN CAST(TRIM(c10) AS SMALLINT) ELSE NULL END
                FROM {staging}
                WHERE LENGTH(TRIM(c0)) = 8 AND TRIM(c0) ~ '^\d+$'
            """)
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()

    print(f"    socio: {table_count(conn, 'socio')} registros")


def load_simples(conn):
    """Carrega Simples.csv → tabela simples."""
    filepath = DATA_DIR / "Simples.csv"
    if not filepath.exists():
        print("    AVISO: Simples.csv não encontrado.")
        return

    staging = "_stg_simples"
    print("    Carregando Simples.csv (pode demorar ~2min)...")
    _staging_copy(conn, staging, 7, filepath)

    with conn.cursor() as cur:
        cur.execute(f"""
            INSERT INTO simples (
                cnpj_basico, opcao_simples, dt_opcao_simples, dt_exclusao_simples,
                opcao_mei, dt_opcao_mei, dt_exclusao_mei
            )
            SELECT
                LPAD(TRIM(c0), 8, '0'),
                NULLIF(TRIM(c1), ''),
                CASE WHEN TRIM(c2) ~ '^\d{{8}}$' AND TRIM(c2) != '00000000'
                     THEN safe_to_date(TRIM(c2), 'YYYYMMDD') ELSE NULL END,
                CASE WHEN TRIM(c3) ~ '^\d{{8}}$' AND TRIM(c3) != '00000000'
                     THEN safe_to_date(TRIM(c3), 'YYYYMMDD') ELSE NULL END,
                NULLIF(TRIM(c4), ''),
                CASE WHEN TRIM(c5) ~ '^\d{{8}}$' AND TRIM(c5) != '00000000'
                     THEN safe_to_date(TRIM(c5), 'YYYYMMDD') ELSE NULL END,
                CASE WHEN TRIM(c6) ~ '^\d{{8}}$' AND TRIM(c6) != '00000000'
                     THEN safe_to_date(TRIM(c6), 'YYYYMMDD') ELSE NULL END
            FROM {staging}
            WHERE LENGTH(TRIM(c0)) = 8 AND TRIM(c0) ~ '^\d+$'
            ON CONFLICT (cnpj_basico) DO NOTHING
        """)
    conn.commit()

    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {staging}")
    conn.commit()

    print(f"    simples: {table_count(conn, 'simples')} registros")


def run():
    conn = get_conn()
    try:
        # Pula tabelas que ja tem dados significativos (retomada)
        # Thresholds para skip: so pula se ja tem volume proximo do esperado
        skip_thresholds = {'empresa': 60_000_000, 'estabelecimento': 55_000_000, 'socio': 25_000_000}
        for tbl, loader in [('empresa', load_empresas), ('estabelecimento', load_estabelecimentos),
                             ('socio', load_socios)]:
            cnt = table_count(conn, tbl)
            if cnt >= skip_thresholds.get(tbl, 0):
                print(f"    {tbl}: {cnt} registros (ja carregada, pulando)")
            else:
                loader(conn)
        load_simples(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
