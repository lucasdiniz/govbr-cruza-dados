"""Fase 5.1: Carrega dados da PGFN (Divida Ativa da Uniao)."""

import csv
import re
from pathlib import Path

from tqdm import tqdm

from etl.config import DATA_DIR
from etl.db import copy_csv_streaming, get_conn, table_count


EXPECTED_COLS = [
    "cpf_cnpj", "tipo_pessoa", "tipo_devedor", "nome_devedor",
    "uf_devedor", "unidade_responsavel", "numero_inscricao",
    "tipo_situacao_inscricao", "situacao_inscricao",
    "receita_principal", "dt_inscricao", "indicador_ajuizado",
    "valor_consolidado",
]

HEADER_ALIASES = {
    "cpf_cnpj": {"cpfcnpj"},
    "tipo_pessoa": {"tipopessoa"},
    "tipo_devedor": {"tipodevedor"},
    "nome_devedor": {"nomedevedor"},
    "uf_devedor": {"ufdevedor", "ufdodevedor"},
    "unidade_responsavel": {"unidaderesponsavel"},
    "numero_inscricao": {"numeroinscricao"},
    "tipo_situacao_inscricao": {"tiposituacaoinscricao"},
    "situacao_inscricao": {"situacaoinscricao"},
    "receita_principal": {"receitaprincipal"},
    "dt_inscricao": {"datainscricao", "dtinscricao"},
    "indicador_ajuizado": {"indicadorajuizado"},
    "valor_consolidado": {"valorconsolidado"},
}


def _normalize_header(value: str) -> str:
    value = value.strip().lower()
    return re.sub(r"[^a-z0-9]", "", value)


def _copy_escape(val):
    if val is None:
        return "\\N"
    val = str(val).strip()
    if val == "":
        return "\\N"
    return val.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "")


def _resolve_header_positions(header: list[str]) -> dict[str, int | None]:
    normalized = {_normalize_header(name): idx for idx, name in enumerate(header)}
    positions = {}
    for dest, aliases in HEADER_ALIASES.items():
        positions[dest] = next((normalized[a] for a in aliases if a in normalized), None)
    return positions


def _iter_pgfn_rows(filepath: Path):
    skipped = 0

    with open(filepath, "r", encoding="latin1", errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=";", quotechar='"')
        header = next(reader, None)
        if not header:
            return

        positions = _resolve_header_positions(header)
        missing = [col for col in EXPECTED_COLS if positions[col] is None]
        if missing:
            raise RuntimeError(f"{filepath.name}: colunas PGFN ausentes no header: {', '.join(missing)}")

        for row in reader:
            if not row or all(not c.strip() for c in row):
                continue
            try:
                values = [row[positions[col]] if positions[col] < len(row) else None for col in EXPECTED_COLS]
            except Exception:
                skipped += 1
                continue
            yield "\t".join(_copy_escape(v) for v in values) + "\n"

    if skipped:
        print(f"      AVISO: {filepath.name}: {skipped} linha(s) malformada(s) puladas")


def run():
    conn = get_conn()
    try:
        pgfn_dir = DATA_DIR / "pgfn"
        files = sorted(pgfn_dir.glob("arquivo_lai_*.csv")) if pgfn_dir.exists() else []
        if not files:
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

            copy_csv_streaming(
                conn,
                staging,
                [f"c{i}" for i in range(13)],
                _iter_pgfn_rows(filepath),
            )

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
