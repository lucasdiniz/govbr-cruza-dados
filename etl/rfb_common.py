"""Parsing compartilhado dos CSVs RFB (CNPJ).

Usado pela carga classica (etl/03_rfb.py) e pelo sync mensal
(etl/rfb_sync.py). Manter as expressoes de conversao num lugar so evita que
as duas cargas divirjam (ex: sync gravando capital_social diferente do que a
carga full gravaria e todo mes "atualizando" milhoes de linhas a toa).

Arquivos RFB: sem header, delimitador ;, encoding Latin-1, decimais com
virgula. Cada CSV vai para uma staging UNLOGGED com colunas c0..cN TEXT
(staging_copy) e as expressoes abaixo convertem c0..cN para as colunas
tipadas da tabela final.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path


def staging_copy(conn, staging_table: str, n_cols: int, filepath: Path):
    """
    Cria staging table UNLOGGED com N colunas TEXT.
    Usa Python csv reader para parsear corretamente campos com ; dentro de aspas,
    e normaliza para exatamente n_cols campos. Envia como TSV via COPY.
    """
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


def _date(c: str) -> str:
    return (
        f"CASE WHEN TRIM({c}) ~ '^\\d{{8}}$' AND TRIM({c}) != '00000000'\n"
        f"         THEN safe_to_date(TRIM({c}), 'YYYYMMDD') ELSE NULL END"
    )


def _smallint(c: str) -> str:
    return f"CASE WHEN TRIM({c}) ~ '^\\d+$' THEN CAST(TRIM({c}) AS SMALLINT) ELSE NULL END"


def _text(c: str) -> str:
    return f"NULLIF(TRIM({c}), '')"


@dataclass(frozen=True)
class RfbTable:
    """Descricao de uma tabela RFB carregada a partir de CSVs."""
    table: str
    file_prefix: str          # "Empresas" -> Empresas0..9 ; "Simples" -> Simples
    n_files: int
    n_cols: int
    columns: tuple[str, ...]  # colunas de dados (ordem do INSERT)
    exprs: tuple[str, ...]    # expressoes SQL sobre c0..cN, mesma ordem de columns
    key: tuple[str, ...]      # chave natural (PK) — vazia para socio

    def select_sql(self, staging: str) -> str:
        """SELECT tipado a partir da staging raw (inclui o filtro de linhas validas)."""
        body = ",\n    ".join(f"{e} AS {c}" for e, c in zip(self.exprs, self.columns))
        return (
            f"SELECT\n    {body}\nFROM {staging}\n"
            "WHERE LENGTH(TRIM(c0)) = 8 AND TRIM(c0) ~ '^\\d+$'"
        )

    def file_names(self) -> list[str]:
        if self.n_files == 1:
            return [self.file_prefix]
        return [f"{self.file_prefix}{i}" for i in range(self.n_files)]


EMPRESA = RfbTable(
    table="empresa",
    file_prefix="Empresas",
    n_files=10,
    n_cols=7,
    columns=("cnpj_basico", "razao_social", "natureza_juridica",
             "qualif_responsavel", "capital_social", "porte", "ente_federativo"),
    exprs=(
        "LPAD(TRIM(c0), 8, '0')",
        "TRIM(c1)",
        _text("c2"),
        _text("c3"),
        # Filtra linhas corrompidas: c4 (capital_social) deve parecer um
        # numero decimal BR e c5 (porte) numerico de 1-2 digitos
        "CASE WHEN TRIM(c4) ~ '^[\\d.,]+$' AND TRIM(c4) != ''\n"
        "         THEN CAST(REPLACE(TRIM(c4), ',', '.') AS DECIMAL(15,2))\n"
        "         ELSE NULL END",
        "CASE WHEN TRIM(c5) ~ '^\\d{1,2}$' THEN CAST(TRIM(c5) AS SMALLINT) ELSE NULL END",
        _text("c6"),
    ),
    key=("cnpj_basico",),
)

ESTABELECIMENTO = RfbTable(
    table="estabelecimento",
    file_prefix="Estabelecimentos",
    n_files=10,
    n_cols=30,
    columns=(
        "cnpj_basico", "cnpj_ordem", "cnpj_dv", "matriz_filial",
        "nome_fantasia", "situacao_cadastral", "dt_situacao", "motivo_situacao",
        "nome_cidade_exterior", "pais", "dt_inicio_atividade",
        "cnae_principal", "cnae_secundaria",
        "tipo_logradouro", "logradouro", "numero", "complemento", "bairro",
        "cep", "uf", "municipio",
        "ddd1", "telefone1", "ddd2", "telefone2", "ddd_fax", "fax",
        "email", "situacao_especial", "dt_situacao_especial",
    ),
    exprs=(
        "LPAD(TRIM(c0), 8, '0')",
        "LPAD(TRIM(c1), 4, '0')",
        "LPAD(TRIM(c2), 2, '0')",
        _smallint("c3"),
        _text("c4"),
        _smallint("c5"),
        _date("c6"),
        _text("c7"),
        _text("c8"),
        _text("c9"),
        _date("c10"),
        *(_text(f"c{i}") for i in range(11, 29)),
        _date("c29"),
    ),
    key=("cnpj_basico", "cnpj_ordem", "cnpj_dv"),
)

SOCIO = RfbTable(
    table="socio",
    file_prefix="Socios",
    n_files=10,
    n_cols=11,
    columns=(
        "cnpj_basico", "tipo_socio", "nome", "cpf_cnpj_socio",
        "qualificacao", "dt_entrada", "pais",
        "cpf_representante", "nome_representante", "qualif_representante",
        "faixa_etaria",
    ),
    exprs=(
        "LPAD(TRIM(c0), 8, '0')",
        _smallint("c1"),
        _text("c2"),
        _text("c3"),
        _text("c4"),
        _date("c5"),
        _text("c6"),
        _text("c7"),
        _text("c8"),
        _text("c9"),
        _smallint("c10"),
    ),
    key=(),
)

SIMPLES = RfbTable(
    table="simples",
    file_prefix="Simples",
    n_files=1,
    n_cols=7,
    columns=(
        "cnpj_basico", "opcao_simples", "dt_opcao_simples", "dt_exclusao_simples",
        "opcao_mei", "dt_opcao_mei", "dt_exclusao_mei",
    ),
    exprs=(
        "LPAD(TRIM(c0), 8, '0')",
        _text("c1"),
        _date("c2"),
        _date("c3"),
        _text("c4"),
        _date("c5"),
        _date("c6"),
    ),
    key=("cnpj_basico",),
)

RFB_TABLES: dict[str, RfbTable] = {
    t.table: t for t in (EMPRESA, ESTABELECIMENTO, SIMPLES, SOCIO)
}

# Identidade de um vinculo de socio: quem (nome + doc mascarado + tipo) entrou
# em qual empresa, quando e com qual qualificacao. Mudanca de qualificacao
# (socio -> socio-administrador) vira historico de proposito. Atributos que
# mudam sem o vinculo terminar (faixa_etaria, representante, pais) ficam FORA
# da identidade e sao atualizados in-place — senao toda virada de faixa etaria
# viraria uma "saida" falsa em socio_historico.
SOCIO_IDENTITY = ("cnpj_basico", "tipo_socio", "nome", "cpf_cnpj_socio", "qualificacao", "dt_entrada")
SOCIO_ATTRS = tuple(c for c in SOCIO.columns if c not in SOCIO_IDENTITY)


def socio_identity_sql(alias: str) -> str:
    """md5 da identidade do vinculo; NULL-safe via ROW(...)::text."""
    cols = ", ".join(f"{alias}.{c}" for c in SOCIO_IDENTITY)
    return f"md5(ROW({cols})::text)"
