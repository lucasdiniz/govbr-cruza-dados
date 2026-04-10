"""Fase 4b: Carrega itens PNCP (JSON → PostgreSQL).

Le os JSONs baixados por etl.00_download e insere na tabela pncp_item.
Usa COPY + thread pool para maximizar throughput em HDD.

Uso:
  python -m etl.04b_pncp_itens
"""

import io
import json
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from importlib import import_module

from tqdm import tqdm

from etl.config import DATA_DIR, SQL_DIR
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

# Log file for errors
LOG_FILE = DATA_DIR / "pncp_itens_etl.log"


def _log(msg):
    """Append a timestamped message to the log file and print it."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(f"    {line}")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


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


def _to_int(val):
    """Convert to int safely. Returns None on failure."""
    if val is None:
        return None
    try:
        return int(val)
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
            _escape_copy(_to_int(item.get("_ano_compra"))),
            _escape_copy(_to_int(item.get("_sequencial_compra"))),
        ]
        lines.append("\t".join(vals) + "\n")

    return lines


def _flush_buffer(conn, buffer, batch_num):
    """Flush a buffer to the DB via COPY. Returns (success, rows, error_msg)."""
    buffer.seek(0)
    # Count lines before sending
    content = buffer.getvalue()
    row_count = content.count("\n")
    buffer.seek(0)

    try:
        with conn.cursor() as cur:
            cur.copy_expert(COPY_SQL, buffer)
        conn.commit()
        return True, row_count, None
    except Exception as e:
        # Roll back the failed transaction so connection stays usable
        conn.rollback()
        error_msg = str(e).strip()
        _log(f"ERRO batch #{batch_num}: {error_msg}")

        # Try to find the offending line by inserting line-by-line
        _log(f"  Tentando identificar linhas problematicas no batch #{batch_num}...")
        buffer.seek(0)
        recovered = 0
        failed_lines = 0
        for i, line in enumerate(buffer):
            single = io.StringIO(line)
            try:
                with conn.cursor() as cur:
                    cur.copy_expert(COPY_SQL, single)
                conn.commit()
                recovered += 1
            except Exception as line_err:
                conn.rollback()
                failed_lines += 1
                if failed_lines <= 5:  # Log first 5 bad lines
                    # Show truncated line content for debugging
                    preview = line.strip()[:200]
                    _log(f"  Linha {i} falhou: {str(line_err).strip()[:100]}")
                    _log(f"    Conteudo: {preview}")

        _log(f"  Batch #{batch_num}: {recovered} recuperadas, {failed_lines} descartadas")
        return False, recovered, error_msg


def _ensure_itens_downloaded():
    import_module("etl.00_download").ensure_pncp_itens_downloaded(log=_log)


def load_itens(conn):
    """Carrega pncp_itens/*.json → pncp_item usando COPY + thread pool."""
    _ensure_itens_downloaded()

    if not ITENS_DIR.exists():
        print("    AVISO: diretorio pncp_itens/ nao encontrado.")
        return

    # Create table (DROP + CREATE) for clean start
    _log("Criando tabela pncp_item...")
    sql = (SQL_DIR / "03b_schema_pncp_itens.sql").read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()

    # Use os.scandir for speed (no sorting 3M entries)
    _log("Escaneando diretorio de JSONs...")
    itens_dir = str(ITENS_DIR)
    filepaths = [
        os.path.join(itens_dir, e.name)
        for e in os.scandir(itens_dir)
        if e.name.endswith(".json") and e.is_file()
    ]
    _log(f"{len(filepaths)} arquivos JSON encontrados")

    total = 0
    erros_arquivo = 0
    erros_batch = 0
    buffer = io.StringIO()
    buffer_count = 0
    batch_num = 0
    flush_every = 50000  # flush to DB every 50k files

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = {executor.submit(_read_file, fp): fp for fp in filepaths}

        for future in tqdm(as_completed(futures), total=len(futures), desc="    PNCP itens"):
            result = future.result()
            if result is None:
                erros_arquivo += 1
                continue

            for line in result:
                buffer.write(line)

            buffer_count += 1

            if buffer_count >= flush_every:
                batch_num += 1
                success, rows, _ = _flush_buffer(conn, buffer, batch_num)
                total += rows
                if not success:
                    erros_batch += 1
                buffer = io.StringIO()
                buffer_count = 0

    # Flush remaining
    if buffer.tell() > 0:
        batch_num += 1
        success, rows, _ = _flush_buffer(conn, buffer, batch_num)
        total += rows
        if not success:
            erros_batch += 1

    final_count = table_count(conn, 'pncp_item')
    _log(f"CONCLUIDO: {final_count} registros na tabela")
    _log(f"  Arquivos lidos: {len(filepaths) - erros_arquivo} OK, {erros_arquivo} com erro")
    _log(f"  Batches: {batch_num} total, {erros_batch} com erro parcial")
    print(f"    pncp_item: {final_count} registros ({erros_arquivo} arquivos com erro, {erros_batch} batches com erro)")


def _create_indexes(conn):
    """Cria indices para queries de superfaturamento."""
    # Disable parallel workers to reduce temp disk usage on large tables
    with conn.cursor() as cur:
        cur.execute("SET max_parallel_maintenance_workers = 0;")
    conn.commit()

    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_pncp_item_cnpj_orgao ON pncp_item(cnpj_orgao);",
        "CREATE INDEX IF NOT EXISTS idx_pncp_item_controle ON pncp_item(numero_controle_pncp);",
        "CREATE INDEX IF NOT EXISTS idx_pncp_item_ncm ON pncp_item(ncm_nbs_codigo) WHERE ncm_nbs_codigo IS NOT NULL;",
        "CREATE INDEX IF NOT EXISTS idx_pncp_item_descricao_trgm ON pncp_item USING gin (descricao gin_trgm_ops);",
        "CREATE INDEX IF NOT EXISTS idx_pncp_item_valor ON pncp_item(valor_unitario_estimado);",
        "CREATE INDEX IF NOT EXISTS idx_pncp_item_material ON pncp_item(material_ou_servico);",
        "CREATE INDEX IF NOT EXISTS idx_pncp_item_situacao ON pncp_item(situacao_item_nome);",
    ]
    for idx_sql in indexes:
        with conn.cursor() as cur:
            cur.execute(idx_sql)
        conn.commit()


def run():
    _log("="*60)
    _log("INICIO etl.04b_pncp_itens")
    conn = get_conn()
    try:
        load_itens(conn)
        _log("Criando indices...")
        _create_indexes(conn)
        _log("Indices criados.")
    except Exception:
        _log(f"ERRO FATAL: {traceback.format_exc()}")
        raise
    finally:
        conn.close()
        _log("FIM etl.04b_pncp_itens")
        _log("="*60)


if __name__ == "__main__":
    run()
