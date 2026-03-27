"""Fase 4b: Carrega itens PNCP (JSON → PostgreSQL).

Le os JSONs baixados por download_pncp.py e insere na tabela pncp_item.
Usa COPY + thread pool para maximizar throughput em HDD.

Uso:
  python -m etl.04b_pncp_itens
"""

import io
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from tqdm import tqdm

from etl.config import DATA_DIR
from etl.db import get_conn, table_count
from etl.utils import safe_strip


ITENS_DIR = DATA_DIR / "pncp_itens"

COLUMNS = [
    "numero_controle_pncp", "numero_item", "descricao",
    "material_ou_servico", "valor_unitario_estimado", "valor_total",
    "quantidade", "unidade_medida", "orcamento_sigiloso",
    "criterio_julgamento_nome", "situacao_item_nome", "tem_resultado",
    "ncm_nbs_codigo", "ncm_nbs_descricao",
    "catalogo", "catalogo_codigo_item",
    "dt_inclusao", "dt_atualizacao",
    "cnpj_orgao", "ano_compra", "sequencial_compra",
]

COPY_SQL = f"COPY pncp_item ({', '.join(COLUMNS)}) FROM STDIN WITH (FORMAT text, DELIMITER E'\\t', NULL '\\N')"


def _parse_ts(val):
    """Parse ISO timestamp ou None."""
    if not val:
        return None
    return str(val)[:19]


def _to_decimal(val):
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _extract_catalogo(val):
    """Extract catalogo name from dict or string."""
    if val is None:
        return None
    if isinstance(val, dict):
        return safe_strip(str(val.get("nome", "") or "")) or None
    return safe_strip(str(val)) or None


def _escape_copy(val):
    """Escape value for COPY TEXT format."""
    if val is None:
        return "\\N"
    s = str(val)
    return s.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def _read_file(filepath):
    """Read and parse a single JSON file. Returns list of TSV lines."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            items = json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None

    if not isinstance(items, list):
        return None

    lines = []
    for item in items:
        nc = item.get("_numero_controle_pncp", "")
        if not nc:
            continue

        vals = [
            _escape_copy(nc),
            _escape_copy(item.get("numeroItem")),
            _escape_copy(safe_strip(str(item.get("descricao", "") or ""))),
            _escape_copy(safe_strip(str(item.get("materialOuServico", "") or ""))),
            _escape_copy(_to_decimal(item.get("valorUnitarioEstimado"))),
            _escape_copy(_to_decimal(item.get("valorTotal"))),
            _escape_copy(_to_decimal(item.get("quantidade"))),
            _escape_copy(safe_strip(str(item.get("unidadeMedida", "") or ""))),
            _escape_copy(item.get("orcamentoSigiloso")),
            _escape_copy(safe_strip(str(item.get("criterioJulgamentoNome", "") or ""))),
            _escape_copy(safe_strip(str(item.get("situacaoCompraItemNome", "") or ""))),
            _escape_copy(item.get("temResultado")),
            _escape_copy(safe_strip(str(item.get("ncmNbsCodigo", "") or "")) or None),
            _escape_copy(safe_strip(str(item.get("ncmNbsDescricao", "") or "")) or None),
            _escape_copy(_extract_catalogo(item.get("catalogo"))),
            _escape_copy(safe_strip(str(item.get("catalogoCodigoItem", "") or "")) or None),
            _escape_copy(_parse_ts(item.get("dataInclusao"))),
            _escape_copy(_parse_ts(item.get("dataAtualizacao"))),
            _escape_copy(item.get("_cnpj_orgao", "")),
            _escape_copy(item.get("_ano_compra")),
            _escape_copy(item.get("_sequencial_compra")),
        ]
        lines.append("\t".join(vals) + "\n")

    return lines


def load_itens(conn):
    """Carrega pncp_itens/*.json → pncp_item usando COPY + thread pool."""
    if not ITENS_DIR.exists():
        print("    AVISO: diretorio pncp_itens/ nao encontrado.")
        return

    # Use os.scandir for speed (no sorting 3M entries)
    itens_dir = str(ITENS_DIR)
    filepaths = [
        os.path.join(itens_dir, e.name)
        for e in os.scandir(itens_dir)
        if e.name.endswith(".json") and e.is_file()
    ]
    print(f"    {len(filepaths)} arquivos JSON encontrados")

    total = 0
    erros = 0
    buffer = io.StringIO()
    buffer_count = 0
    flush_every = 50000  # flush to DB every 50k files

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_read_file, fp): fp for fp in filepaths}

        for future in tqdm(as_completed(futures), total=len(futures), desc="    PNCP itens"):
            result = future.result()
            if result is None:
                erros += 1
                continue

            for line in result:
                buffer.write(line)
                total += 1

            buffer_count += 1

            if buffer_count >= flush_every:
                buffer.seek(0)
                with conn.cursor() as cur:
                    cur.copy_expert(COPY_SQL, buffer)
                conn.commit()
                buffer = io.StringIO()
                buffer_count = 0

    # Flush remaining
    if buffer.tell() > 0:
        buffer.seek(0)
        with conn.cursor() as cur:
            cur.copy_expert(COPY_SQL, buffer)
        conn.commit()

    print(f"    pncp_item: {table_count(conn, 'pncp_item')} registros ({erros} arquivos com erro)")


def run():
    conn = get_conn()
    try:
        load_itens(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
