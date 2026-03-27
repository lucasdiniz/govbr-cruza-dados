"""Carrega dados consolidados do TCE-PB (despesas, servidores, licitacoes, receitas).

Fonte: https://dados-abertos.tce.pb.gov.br/dados-consolidados
Formato: CSV com ; separador, encoding UTF-8 BOM, valores decimais com virgula

Uso:
  python -m etl.19_tce_pb                    # Carrega tudo
  python -m etl.19_tce_pb --only despesas    # So despesas
  python -m etl.19_tce_pb --anos 2024,2025   # So esses anos
"""

import csv
import io
import sys
from pathlib import Path

from tqdm import tqdm

from etl.config import DATA_DIR
from etl.db import get_conn, table_count


from datetime import date

TCE_DIR = DATA_DIR / "tce_pb"
ANOS = range(2018, date.today().year + 1)


def _parse_decimal_br(val):
    """Converte '1.234,56' ou '1234.56' para string decimal padrao."""
    if not val or not val.strip():
        return None
    val = val.strip().strip('"')
    if not val:
        return None
    # Formato brasileiro: 1.234,56
    if "," in val:
        val = val.replace(".", "").replace(",", ".")
    try:
        float(val)
        return val
    except ValueError:
        return None


def _parse_date_br(val):
    """Converte DD/MM/YYYY para YYYY-MM-DD."""
    if not val or not val.strip():
        return None
    val = val.strip()
    parts = val.split("/")
    if len(parts) == 3 and len(parts[2]) == 4:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return None


def _staging_load(conn, staging, filepath, n_cols):
    """Carrega CSV em tabela staging via COPY."""
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
        with open(fp, "r", encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                yield line.replace("\x00", "")

    reader = csv.reader(clean_lines(filepath), delimiter=";", quotechar='"')
    next(reader, None)  # skip header

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

    return count


# Macro para converter valor BR em SQL
_DECIMAL_SQL = """
    CASE WHEN TRIM({col}) ~ '^-?[\\d.,]+$' AND TRIM({col}) != ''
         THEN CAST(REPLACE(REPLACE(TRIM({col}),'.',''),',','.') AS DECIMAL(15,2))
         ELSE NULL END
"""

_DATE_SQL = """
    CASE WHEN TRIM({col}) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}'
         THEN TO_DATE(LEFT(TRIM({col}), 10), 'YYYY-MM-DD')
         WHEN TRIM({col}) ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}$'
         THEN TO_DATE(TRIM({col}), 'DD/MM/YYYY')
         ELSE NULL END
"""


def load_despesas(conn, anos):
    """Carrega despesas-YYYY.csv -> tce_pb_despesa."""
    for ano in anos:
        filepath = TCE_DIR / f"despesas-{ano}.csv"
        if not filepath.exists():
            print(f"    AVISO: {filepath.name} nao encontrado.")
            continue

        print(f"    despesas-{ano}...", end=" ", flush=True)
        staging = "_stg_tce_despesa"
        n = _staging_load(conn, staging, filepath, 40)

        sql = """
                INSERT INTO tce_pb_despesa (
                    municipio, codigo_ug, descricao_ug, numero_empenho,
                    data_empenho, mes, cpf_cnpj, nome_credor,
                    valor_empenhado, valor_liquidado, valor_pago,
                    codigo_unidade_orcamentaria, descricao_unidade_orcamentaria,
                    codigo_funcao, funcao, codigo_subfuncao, subfuncao,
                    codigo_programa, programa, codigo_acao, acao,
                    codigo_categoria_economica, categoria_economica,
                    codigo_natureza, grupo_natureza_despesa,
                    codigo_modalidade_aplicacao, modalidade_aplicacao,
                    codigo_elemento_despesa, elemento_despesa,
                    codigo_subelemento, codigo_subelemento_exibicao,
                    numero_licitacao, modalidade_licitacao, numero_obra,
                    historico, codigo_fonte_recurso, descricao_fonte_recurso,
                    ano_fonte, co, descricao_co,
                    ano_arquivo
                )
                SELECT
                    TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3),
                    {date_empenho},
                    TRIM(c5), TRIM(c6), TRIM(c7),
                    {val_empenhado}, {val_liquidado}, {val_pago},
                    TRIM(c11), TRIM(c12),
                    TRIM(c13), TRIM(c14), TRIM(c15), TRIM(c16),
                    TRIM(c17), TRIM(c18), TRIM(c19), TRIM(c20),
                    TRIM(c21), TRIM(c22),
                    TRIM(c23), TRIM(c24),
                    TRIM(c25), TRIM(c26),
                    TRIM(c27), TRIM(c28),
                    TRIM(c29), TRIM(c30),
                    TRIM(c31), TRIM(c32), TRIM(c33),
                    TRIM(c34), TRIM(c35), TRIM(c36),
                    TRIM(c37), TRIM(c38), TRIM(c39),
                    {ano}::SMALLINT
                FROM {staging}
            """.format(
                staging=staging,
                date_empenho=_DATE_SQL.format(col="c4"),
                val_empenhado=_DECIMAL_SQL.format(col="c8"),
                val_liquidado=_DECIMAL_SQL.format(col="c9"),
                val_pago=_DECIMAL_SQL.format(col="c10"),
                ano=ano,
            )
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()
        print(f"{n:,} linhas")


def load_servidores(conn, anos):
    """Carrega servidores-YYYY.csv -> tce_pb_servidor."""
    for ano in anos:
        filepath = TCE_DIR / f"servidores-{ano}.csv"
        if not filepath.exists():
            print(f"    AVISO: {filepath.name} nao encontrado.")
            continue

        print(f"    servidores-{ano}...", end=" ", flush=True)
        staging = "_stg_tce_servidor"
        n = _staging_load(conn, staging, filepath, 11)

        sql = """
                INSERT INTO tce_pb_servidor (
                    municipio, codigo_ug, descricao_ug, cpf_cnpj,
                    nome_servidor, tipo_cargo, descricao_cargo,
                    valor_vantagem, data_admissao, matricula, ano_mes
                )
                SELECT
                    TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3),
                    TRIM(c4), TRIM(c5), TRIM(c6),
                    {val_vantagem},
                    {date_admissao},
                    TRIM(c9), TRIM(c10)
                FROM {staging}
            """.format(
                staging=staging,
                val_vantagem=_DECIMAL_SQL.format(col="c7"),
                date_admissao=_DATE_SQL.format(col="c8"),
            )
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()
        print(f"{n:,} linhas")


def load_licitacoes(conn, anos):
    """Carrega licitacoes-YYYY.csv -> tce_pb_licitacao."""
    for ano in anos:
        filepath = TCE_DIR / f"licitacoes-{ano}.csv"
        if not filepath.exists():
            print(f"    AVISO: {filepath.name} nao encontrado.")
            continue

        print(f"    licitacoes-{ano}...", end=" ", flush=True)
        staging = "_stg_tce_licitacao"
        n = _staging_load(conn, staging, filepath, 13)

        sql = """
                INSERT INTO tce_pb_licitacao (
                    municipio, codigo_ug, descricao_ug,
                    numero_licitacao, numero_protocolo_tce, ano_licitacao,
                    modalidade, objeto_licitacao, data_homologacao,
                    nome_proponente, cpf_cnpj_proponente,
                    valor_ofertado, situacao_proposta
                )
                SELECT
                    TRIM(c0), TRIM(c1), TRIM(c2),
                    TRIM(c3), TRIM(c4),
                    CASE WHEN TRIM(c5) ~ '^\\d{{4}}$'
                         THEN CAST(TRIM(c5) AS SMALLINT)
                         ELSE NULL END,
                    TRIM(c6), TRIM(c7),
                    {date_homol},
                    TRIM(c9), TRIM(c10),
                    {val_ofertado},
                    TRIM(c12)
                FROM {staging}
            """.format(
                staging=staging,
                date_homol=_DATE_SQL.format(col="c8"),
                val_ofertado=_DECIMAL_SQL.format(col="c11"),
            )
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()
        print(f"{n:,} linhas")


def load_receitas(conn, anos):
    """Carrega receitas-YYYY.csv -> tce_pb_receita."""
    for ano in anos:
        filepath = TCE_DIR / f"receitas-{ano}.csv"
        if not filepath.exists():
            print(f"    AVISO: {filepath.name} nao encontrado.")
            continue

        print(f"    receitas-{ano}...", end=" ", flush=True)
        staging = "_stg_tce_receita"
        n = _staging_load(conn, staging, filepath, 13)

        sql = """
                INSERT INTO tce_pb_receita (
                    municipio, codigo_ug, descricao_ug,
                    mes_ano, ano, codigo_receita, descricao_receita,
                    tipo_atualizacao_receita, valor,
                    codigo_fonte_recurso, descricao_fonte_recurso,
                    co, descricao_co
                )
                SELECT
                    TRIM(c0), TRIM(c1), TRIM(c2),
                    TRIM(c3),
                    CASE WHEN TRIM(c4) ~ '^\\d{{4}}$'
                         THEN CAST(TRIM(c4) AS SMALLINT)
                         ELSE NULL END,
                    TRIM(c5), TRIM(c6),
                    TRIM(c7),
                    {val},
                    TRIM(c9), TRIM(c10),
                    TRIM(c11), TRIM(c12)
                FROM {staging}
            """.format(
                staging=staging,
                val=_DECIMAL_SQL.format(col="c8"),
            )
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()
        print(f"{n:,} linhas")


def create_indices(conn):
    """Cria indices para as tabelas TCE-PB."""
    print("    Criando indices...")
    indices = [
        # Despesas
        "CREATE INDEX IF NOT EXISTS idx_tce_desp_cpf_cnpj ON tce_pb_despesa(cpf_cnpj)",
        "CREATE INDEX IF NOT EXISTS idx_tce_desp_municipio ON tce_pb_despesa(municipio)",
        "CREATE INDEX IF NOT EXISTS idx_tce_desp_data ON tce_pb_despesa(data_empenho)",
        "CREATE INDEX IF NOT EXISTS idx_tce_desp_ug ON tce_pb_despesa(codigo_ug)",
        "CREATE INDEX IF NOT EXISTS idx_tce_desp_licitacao ON tce_pb_despesa(numero_licitacao)",
        "CREATE INDEX IF NOT EXISTS idx_tce_desp_valor ON tce_pb_despesa(valor_empenhado)",
        "CREATE INDEX IF NOT EXISTS idx_tce_desp_elemento ON tce_pb_despesa(codigo_elemento_despesa)",
        # Servidores
        "CREATE INDEX IF NOT EXISTS idx_tce_serv_cpf ON tce_pb_servidor(cpf_cnpj)",
        "CREATE INDEX IF NOT EXISTS idx_tce_serv_municipio ON tce_pb_servidor(municipio)",
        "CREATE INDEX IF NOT EXISTS idx_tce_serv_nome ON tce_pb_servidor USING gin(nome_servidor gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS idx_tce_serv_ug ON tce_pb_servidor(codigo_ug)",
        # Licitacoes
        "CREATE INDEX IF NOT EXISTS idx_tce_lic_cpf_cnpj ON tce_pb_licitacao(cpf_cnpj_proponente)",
        "CREATE INDEX IF NOT EXISTS idx_tce_lic_municipio ON tce_pb_licitacao(municipio)",
        "CREATE INDEX IF NOT EXISTS idx_tce_lic_numero ON tce_pb_licitacao(numero_licitacao)",
        "CREATE INDEX IF NOT EXISTS idx_tce_lic_modalidade ON tce_pb_licitacao(modalidade)",
        "CREATE INDEX IF NOT EXISTS idx_tce_lic_ano ON tce_pb_licitacao(ano_licitacao)",
        # Receitas
        "CREATE INDEX IF NOT EXISTS idx_tce_rec_municipio ON tce_pb_receita(municipio)",
        "CREATE INDEX IF NOT EXISTS idx_tce_rec_ano ON tce_pb_receita(ano)",
    ]
    with conn.cursor() as cur:
        for idx_sql in indices:
            cur.execute(idx_sql)
    conn.commit()
    print("    Indices criados.")


def run():
    # Parse args
    only = None
    anos = list(ANOS)
    skip_schema = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--only" and i + 1 < len(args):
            only = args[i + 1].split(",")
            i += 2
        elif args[i] == "--anos" and i + 1 < len(args):
            anos = [int(a) for a in args[i + 1].split(",")]
            i += 2
        elif args[i] == "--no-schema":
            skip_schema = True
            i += 1
        else:
            i += 1

    conn = get_conn()
    try:
        if not skip_schema:
            from etl.config import SQL_DIR
            sql = (SQL_DIR / "19_schema_tce_pb.sql").read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            print("    Schema TCE-PB criado.")
        else:
            print("    Schema skip (--no-schema).")

        loaders = {
            "despesas": load_despesas,
            "servidores": load_servidores,
            "licitacoes": load_licitacoes,
            "receitas": load_receitas,
        }

        targets = only if only else loaders.keys()
        for target in targets:
            if target in loaders:
                loaders[target](conn, anos)

        # Contagens
        for t in ["tce_pb_despesa", "tce_pb_servidor", "tce_pb_licitacao", "tce_pb_receita"]:
            print(f"    {t}: {table_count(conn, t):,} registros")

        # Indices
        create_indices(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    run()
