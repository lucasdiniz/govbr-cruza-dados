"""Carrega dados do portal dados.pb.gov.br (pagamento, empenho, contratos, saude, convenios).

Fonte: https://dados.pb.gov.br/app/
API: https://dados.pb.gov.br:443/getcsv?nome={dataset}&exercicio={ano}&mes={mes}
Formato: CSV com ; separador, valores decimais com ponto, datas ISO (YYYY-MM-DD)
CPF formatado (000.123.456-78), CNPJ formatado (12.345.678/0001-90)

Uso:
  python -m etl.20_dados_pb                           # Carrega tudo
  python -m etl.20_dados_pb --only pagamento          # So pagamento
  python -m etl.20_dados_pb --anos 2024,2025          # So esses anos
  python -m etl.20_dados_pb --no-schema               # Pula DROP/CREATE
"""

import csv
import io
import sys
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

from etl.config import DATA_DIR
from etl.db import get_conn, table_count


PB_BASE = "https://dados.pb.gov.br:443/getcsv"
ANOS = range(2018, 2027)
MESES = range(1, 13)

PB_DIR = DATA_DIR / "dados_pb"


def _clean_cpfcnpj(val):
    """Remove formatacao de CPF/CNPJ: 000.123.456-78 -> 00012345678."""
    if not val or not val.strip():
        return None
    val = val.strip().strip('"')
    if not val:
        return None
    # Remove pontos, tracos, barras
    cleaned = val.replace(".", "").replace("-", "").replace("/", "").replace(" ", "")
    if not cleaned:
        return None
    return cleaned


def _clean_val(val):
    """Limpa campo texto para COPY."""
    if val == "" or val is None:
        return "\\N"
    val = val.strip().strip('"').strip()
    if val == "":
        return "\\N"
    val = val.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "")
    return val


def _download_csv(nome, exercicio, mes=None, mes_inicio=None, mes_fim=None):
    """Baixa CSV da API e retorna linhas (generator)."""
    params = f"nome={nome}&exercicio={exercicio}"
    if mes is not None:
        params += f"&mes={mes}"
    if mes_inicio is not None:
        params += f"&mes_inicio={mes_inicio}"
    if mes_fim is not None:
        params += f"&mes_fim={mes_fim}"

    url = f"{PB_BASE}?{params}"
    try:
        resp = urlopen(url, timeout=120)
        data = resp.read().decode("utf-8", errors="replace")
        if not data.strip():
            return None
        return data
    except (URLError, HTTPError):
        return None


def _save_csv(data, filepath):
    """Salva CSV em disco para cache."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(data)


def _load_csv(filepath):
    """Carrega CSV de disco se existir."""
    if filepath.exists() and filepath.stat().st_size > 100:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    return None


def _staging_load_from_data(conn, staging, csv_data, n_cols, delimiter=";"):
    """Carrega CSV data em tabela staging via COPY."""
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

    reader = csv.reader(io.StringIO(csv_data), delimiter=delimiter, quotechar='"')
    next(reader, None)  # skip header

    for row in reader:
        if not row or all(not c.strip() for c in row):
            continue
        if len(row) > n_cols:
            row = row[:n_cols]
        elif len(row) < n_cols:
            row = row + [""] * (n_cols - len(row))

        escaped = [_clean_val(val) for val in row]
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


def load_pagamento(conn, anos):
    """Carrega pagamento (autorizacoes de pagamento estaduais) -> pb_pagamento."""
    total = 0
    for ano in anos:
        for mes in MESES:
            cache = PB_DIR / f"pagamento_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                data = _download_csv("pagamento", ano, mes=mes)
                if data is None:
                    continue
                _save_csv(data, cache)

            staging = "_stg_pb_pagamento"
            n = _staging_load_from_data(conn, staging, data, 12)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            sql = """
                INSERT INTO pb_pagamento (
                    exercicio, codigo_unidade_gestora, numero_empenho,
                    numero_autorizacao_pagamento, tipo_despesa, data_pagamento,
                    valor_pagamento, codigo_tipo_documento, descricao_tipo_documento,
                    nome_credor, cpfcnpj_credor, tipo_credor
                )
                SELECT
                    CASE WHEN TRIM(c0) ~ '^\\d{{4}}$' THEN CAST(TRIM(c0) AS SMALLINT) ELSE NULL END,
                    TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4),
                    CASE WHEN TRIM(c5) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c5) AS DATE) ELSE NULL END,
                    CASE WHEN TRIM(c6) ~ '^-?[\\d.]+$' THEN CAST(TRIM(c6) AS DECIMAL(15,2)) ELSE NULL END,
                    TRIM(c7), TRIM(c8), TRIM(c9),
                    REPLACE(REPLACE(REPLACE(REPLACE(TRIM(c10), '.', ''), '-', ''), '/', ''), ' ', ''),
                    TRIM(c11)
                FROM {staging}
            """.format(staging=staging)
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            total += n

        print(f"    pagamento-{ano}: {total:,} linhas acumuladas", flush=True)
    return total


def load_empenho(conn, anos):
    """Carrega empenho_original -> pb_empenho."""
    total = 0
    for ano in anos:
        ano_count = 0
        for mes in MESES:
            cache = PB_DIR / f"empenho_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                data = _download_csv("empenho_original", ano, mes=mes)
                if data is None:
                    continue
                _save_csv(data, cache)

            staging = "_stg_pb_empenho"
            n = _staging_load_from_data(conn, staging, data, 41)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            # CPF/CNPJ cleanup inline — remove formatacao na coluna c19
            # Dates: c4 (empenho), c16 (saida diarias), c17 (chegada diarias)
            sql = """
                INSERT INTO pb_empenho (
                    exercicio, codigo_unidade_gestora, numero_empenho,
                    numero_empenho_origem, data_empenho, historico_empenho,
                    codigo_situacao_empenho, codigo_tipo_empenho, descricao_tipo_empenho,
                    nome_situacao_empenho, valor_empenho, codigo_modalidade_licitacao,
                    codigo_motivo_dispensa_licitacao, codigo_tipo_credito, nome_tipo_credito,
                    destino_diarias, data_saida_diarias, data_chegada_diarias,
                    nome_credor, cpfcnpj_credor, tipo_credor,
                    codigo_municipio, nome_municipio, numero_processo_pagamento,
                    numero_contrato, codigo_unidade_orcamentaria, codigo_funcao,
                    codigo_subfuncao, codigo_programa, codigo_acao,
                    codigo_fonte_recurso, codigo_natureza_despesa,
                    codigo_categoria_economica_despesa, codigo_grupo_natureza_despesa,
                    codigo_modalidade_aplicacao_despesa, codigo_elemento_despesa,
                    codigo_item_despesa, codigo_finalidade_fixacao, nome_finalidade_fixacao,
                    codigo_licitacao, orcamento_democratico
                )
                SELECT
                    CASE WHEN TRIM(c0) ~ '^\\d{{4}}$' THEN CAST(TRIM(c0) AS SMALLINT) ELSE NULL END,
                    TRIM(c1), TRIM(c2), TRIM(c3),
                    CASE WHEN TRIM(c4) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c4) AS DATE) ELSE NULL END,
                    TRIM(c5), TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9),
                    CASE WHEN TRIM(c10) ~ '^-?[\\d.]+$' THEN CAST(TRIM(c10) AS DECIMAL(15,2)) ELSE NULL END,
                    TRIM(c11), TRIM(c12), TRIM(c13), TRIM(c14),
                    TRIM(c15),
                    CASE WHEN TRIM(c16) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c16) AS DATE) ELSE NULL END,
                    CASE WHEN TRIM(c17) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c17) AS DATE) ELSE NULL END,
                    TRIM(c18),
                    REPLACE(REPLACE(REPLACE(REPLACE(TRIM(c19), '.', ''), '-', ''), '/', ''), ' ', ''),
                    TRIM(c20),
                    TRIM(c21), TRIM(c22), TRIM(c23),
                    TRIM(c24), TRIM(c25), TRIM(c26),
                    TRIM(c27), TRIM(c28), TRIM(c29),
                    TRIM(c30), TRIM(c31),
                    TRIM(c32), TRIM(c33),
                    TRIM(c34), TRIM(c35),
                    TRIM(c36), TRIM(c37), TRIM(c38),
                    TRIM(c39), TRIM(c40)
                FROM {staging}
            """.format(staging=staging)
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            ano_count += n

        total += ano_count
        print(f"    empenho-{ano}: {ano_count:,} linhas", flush=True)
    return total


def load_contratos(conn, anos):
    """Carrega contratos estaduais -> pb_contrato."""
    total = 0
    for ano in anos:
        cache = PB_DIR / f"contratos_{ano}.csv"
        data = _load_csv(cache)
        if data is None:
            data = _download_csv("contratos", ano)
            if data is None:
                print(f"    contratos-{ano}: sem dados")
                continue
            _save_csv(data, cache)

        staging = "_stg_pb_contrato"
        n = _staging_load_from_data(conn, staging, data, 20)
        if n == 0:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            continue

        sql = """
            INSERT INTO pb_contrato (
                codigo_contrato, numero_registro_cge, numero_contrato,
                nome_contratante, numero_processo_licitatorio,
                objeto_contrato, complemento_objeto_contrato,
                nome_contratado, cpfcnpj_contratado,
                data_celebracao_contrato, data_publicacao,
                data_inicio_vigencia, data_termino_vigencia,
                valor_original, nome_municipio, outros_municipios,
                nome_gestor_contrato, numero_portaria,
                data_publicacao_portaria, url_contrato
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4),
                TRIM(c5), TRIM(c6), TRIM(c7),
                REPLACE(REPLACE(REPLACE(REPLACE(TRIM(c8), '.', ''), '-', ''), '/', ''), ' ', ''),
                CASE WHEN TRIM(c9) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c9) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c10) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c10) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c11) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c11) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c12) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c12) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c13) ~ '^-?[\\d.]+$' THEN CAST(TRIM(c13) AS DECIMAL(15,2)) ELSE NULL END,
                TRIM(c14), TRIM(c15), TRIM(c16), TRIM(c17),
                CASE WHEN TRIM(c18) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c18) AS DATE) ELSE NULL END,
                TRIM(c19)
            FROM {staging}
        """.format(staging=staging)
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()
        total += n
        print(f"    contratos-{ano}: {n:,} linhas")
    return total


def load_saude(conn, anos):
    """Carrega pagamentos gestao pactuada saude -> pb_saude."""
    total = 0
    for ano in anos:
        for mes in MESES:
            cache = PB_DIR / f"saude_{ano}_{mes:02d}.csv"
            data = _load_csv(cache)
            if data is None:
                data = _download_csv("pagamentos_gestao_pactuada_saude", ano, mes=mes)
                if data is None:
                    continue
                _save_csv(data, cache)

            staging = "_stg_pb_saude"
            n = _staging_load_from_data(conn, staging, data, 15)
            if n == 0:
                with conn.cursor() as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {staging}")
                conn.commit()
                continue

            sql = """
                INSERT INTO pb_saude (
                    codigo_envio, competencia, codigo_organizacao_social,
                    nome_organizacao_social, codigo_lancamento, data_lancamento,
                    numero_documento, tipo_documento, numero_processo,
                    codigo_categoria_despesa, nome_categoria_despesa,
                    cpfcnpj_credor, nome_credor, valor_lancamento,
                    observacao_lancamento
                )
                SELECT
                    TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4),
                    CASE WHEN TRIM(c5) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c5) AS DATE) ELSE NULL END,
                    TRIM(c6), TRIM(c7), TRIM(c8), TRIM(c9), TRIM(c10),
                    REPLACE(REPLACE(REPLACE(REPLACE(TRIM(c11), '.', ''), '-', ''), '/', ''), ' ', ''),
                    TRIM(c12),
                    CASE WHEN TRIM(c13) ~ '^-?[\\d.]+$' THEN CAST(TRIM(c13) AS DECIMAL(15,2)) ELSE NULL END,
                    TRIM(c14)
                FROM {staging}
            """.format(staging=staging)
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            total += n

        print(f"    saude-{ano}: {total:,} acumuladas", flush=True)
    return total


def load_convenios(conn, anos):
    """Carrega convenios estado-municipios -> pb_convenio."""
    total = 0
    for ano in anos:
        cache = PB_DIR / f"convenios_{ano}.csv"
        data = _load_csv(cache)
        if data is None:
            data = _download_csv("convenios", ano, mes_inicio=1, mes_fim=12)
            if data is None:
                print(f"    convenios-{ano}: sem dados")
                continue
            _save_csv(data, cache)

        staging = "_stg_pb_convenio"
        n = _staging_load_from_data(conn, staging, data, 16)
        if n == 0:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {staging}")
            conn.commit()
            continue

        sql = """
            INSERT INTO pb_convenio (
                codigo_convenio, numero_registro_cge, numero_convenio,
                nome_concedente, nome_convenente, cnpj_convenente,
                nome_municipio, objetivo_convenio, complemento_objeto_convenio,
                data_celebracao_convenio, data_publicacao,
                valor_concedente, valor_contrapartida,
                data_inicio_vigencia, data_termino_vigencia, url_convenio
            )
            SELECT
                TRIM(c0), TRIM(c1), TRIM(c2), TRIM(c3), TRIM(c4),
                REPLACE(REPLACE(REPLACE(REPLACE(TRIM(c5), '.', ''), '-', ''), '/', ''), ' ', ''),
                TRIM(c6), TRIM(c7), TRIM(c8),
                CASE WHEN TRIM(c9) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c9) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c10) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c10) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c11) ~ '^-?[\\d.]+$' THEN CAST(TRIM(c11) AS DECIMAL(15,2)) ELSE NULL END,
                CASE WHEN TRIM(c12) ~ '^-?[\\d.]+$' THEN CAST(TRIM(c12) AS DECIMAL(15,2)) ELSE NULL END,
                CASE WHEN TRIM(c13) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c13) AS DATE) ELSE NULL END,
                CASE WHEN TRIM(c14) ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}$' THEN CAST(TRIM(c14) AS DATE) ELSE NULL END,
                TRIM(c15)
            FROM {staging}
        """.format(staging=staging)
        with conn.cursor() as cur:
            cur.execute(sql)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()
        total += n
        print(f"    convenios-{ano}: {n:,} linhas")
    return total


def create_indices(conn):
    """Cria indices para as tabelas dados.pb.gov.br."""
    print("    Criando indices...")
    indices = [
        # Pagamento
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_cpfcnpj ON pb_pagamento(cpfcnpj_credor)",
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_exercicio ON pb_pagamento(exercicio)",
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_data ON pb_pagamento(data_pagamento)",
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_ug ON pb_pagamento(codigo_unidade_gestora)",
        "CREATE INDEX IF NOT EXISTS idx_pb_pag_valor ON pb_pagamento(valor_pagamento)",
        # Empenho
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_cpfcnpj ON pb_empenho(cpfcnpj_credor)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_exercicio ON pb_empenho(exercicio)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_data ON pb_empenho(data_empenho)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_modalidade ON pb_empenho(codigo_modalidade_licitacao)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_ug ON pb_empenho(codigo_unidade_gestora)",
        "CREATE INDEX IF NOT EXISTS idx_pb_emp_valor ON pb_empenho(valor_empenho)",
        # Contrato
        "CREATE INDEX IF NOT EXISTS idx_pb_ctr_cpfcnpj ON pb_contrato(cpfcnpj_contratado)",
        "CREATE INDEX IF NOT EXISTS idx_pb_ctr_valor ON pb_contrato(valor_original)",
        # Saude
        "CREATE INDEX IF NOT EXISTS idx_pb_saude_cpfcnpj ON pb_saude(cpfcnpj_credor)",
        "CREATE INDEX IF NOT EXISTS idx_pb_saude_valor ON pb_saude(valor_lancamento)",
        # Convenio
        "CREATE INDEX IF NOT EXISTS idx_pb_conv_cnpj ON pb_convenio(cnpj_convenente)",
        "CREATE INDEX IF NOT EXISTS idx_pb_conv_valor ON pb_convenio(valor_concedente)",
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
            sql = (SQL_DIR / "20_schema_dados_pb.sql").read_text(encoding="utf-8")
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()
            print("    Schema dados.pb.gov.br criado.")
        else:
            print("    Schema skip (--no-schema).")

        loaders = {
            "pagamento": load_pagamento,
            "empenho": load_empenho,
            "contratos": load_contratos,
            "saude": load_saude,
            "convenios": load_convenios,
        }

        targets = only if only else loaders.keys()
        for target in targets:
            if target in loaders:
                print(f"\n  [{target}]")
                loaders[target](conn, anos)

        # Contagens
        print()
        for t in ["pb_pagamento", "pb_empenho", "pb_contrato", "pb_saude", "pb_convenio"]:
            print(f"    {t}: {table_count(conn, t):,} registros")

        # Indices
        create_indices(conn)

    finally:
        conn.close()


if __name__ == "__main__":
    run()
