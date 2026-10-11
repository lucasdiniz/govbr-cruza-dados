"""Fase 3: Carrega dados da Receita Federal (Empresas, Estabelecimentos, Sócios, Simples).

Arquivos sem header, delimitador ;, encoding Latin-1, decimais com vírgula.
Usa COPY via staging table UNLOGGED para máxima performance.

Carga inicial (full). Atualizacao mensal de uma base ja carregada eh feita
por etl/rfb_sync.py (diff in-place) — esta fase pula tabelas ja populadas.
Conversoes de coluna compartilhadas em etl/rfb_common.py.
"""

from pathlib import Path

from tqdm import tqdm

from etl.config import DATA_DIR
from etl.db import get_conn, table_count
from etl.rfb_common import EMPRESA, ESTABELECIMENTO, SIMPLES, SOCIO, RfbTable, staging_copy

# Compat: outros modulos/scripts importavam _staging_copy daqui.
_staging_copy = staging_copy


def _get_files(pattern: str) -> list[Path]:
    """Retorna arquivos ordenados pelo nome. Busca em rfb/ e raiz."""
    rfb_dir = DATA_DIR / "rfb"
    files = sorted(rfb_dir.glob(pattern)) if rfb_dir.exists() else []
    if not files:
        files = sorted(DATA_DIR.glob(pattern))
    return files


def _insert_sql(spec: RfbTable, staging: str) -> str:
    cols = ", ".join(spec.columns)
    conflict = f"\nON CONFLICT ({', '.join(spec.key)}) DO NOTHING" if spec.key else ""
    return f"INSERT INTO {spec.table} ({cols})\n{spec.select_sql(staging)}{conflict}"


def _load_files(conn, spec: RfbTable, staging: str, files: list[Path], desc: str):
    for filepath in tqdm(files, desc=desc):
        staging_copy(conn, staging, spec.n_cols, filepath)

        with conn.cursor() as cur:
            cur.execute(_insert_sql(spec, staging))
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {staging}")
        conn.commit()

    print(f"    {spec.table}: {table_count(conn, spec.table)} registros")


def load_empresas(conn):
    """Carrega Empresas0..9.csv -> tabela empresa."""
    files = _get_files("Empresas*.csv")
    if not files:
        print("    AVISO: Nenhum arquivo Empresas*.csv encontrado.")
        return
    _load_files(conn, EMPRESA, "_stg_empresa", files, "    Empresas")


def load_estabelecimentos(conn):
    """Carrega Estabelecimentos0..9.csv → tabela estabelecimento."""
    files = _get_files("Estabelecimentos*.csv")
    if not files:
        print("    AVISO: Nenhum arquivo Estabelecimentos*.csv encontrado.")
        return
    _load_files(conn, ESTABELECIMENTO, "_stg_estab", files, "    Estabelecimentos")


def load_socios(conn):
    """Carrega Socios0..9.csv → tabela socio."""
    files = _get_files("Socios*.csv")
    if not files:
        print("    AVISO: Nenhum arquivo Socios*.csv encontrado.")
        return
    _load_files(conn, SOCIO, "_stg_socio", files, "    Sócios")


def load_simples(conn):
    """Carrega Simples.csv → tabela simples."""
    filepath = DATA_DIR / "rfb" / "Simples.csv"
    if not filepath.exists():
        filepath = DATA_DIR / "Simples.csv"
    if not filepath.exists():
        print("    AVISO: Simples.csv não encontrado.")
        return

    staging = "_stg_simples"
    print("    Carregando Simples.csv (pode demorar ~2min)...")
    staging_copy(conn, staging, SIMPLES.n_cols, filepath)

    with conn.cursor() as cur:
        cur.execute(_insert_sql(SIMPLES, staging))
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
