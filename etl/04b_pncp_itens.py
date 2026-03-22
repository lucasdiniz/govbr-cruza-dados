"""Fase 4b: Carrega itens PNCP (JSON → PostgreSQL).

Le os JSONs baixados por download_pncp.py e insere na tabela pncp_item.

Uso:
  python -m etl.04b_pncp_itens
"""

import json
from pathlib import Path

from tqdm import tqdm

from etl.config import DATA_DIR, BATCH_SIZE
from etl.db import get_conn, batch_insert, table_count
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


def load_itens(conn):
    """Carrega pncp_itens/*.json → pncp_item."""
    if not ITENS_DIR.exists():
        print("    AVISO: diretorio pncp_itens/ nao encontrado.")
        return

    files = sorted(ITENS_DIR.glob("*.json"))
    # Excluir checkpoint
    files = [f for f in files if f.name != "_checkpoint.txt"]

    batch = []
    total = 0
    erros = 0

    for filepath in tqdm(files, desc="    PNCP itens"):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                items = json.load(f)
        except (json.JSONDecodeError, OSError):
            erros += 1
            continue

        if not isinstance(items, list):
            continue

        for item in items:
            nc = item.get("_numero_controle_pncp", "")
            if not nc:
                continue

            row = (
                nc,
                item.get("numeroItem"),
                safe_strip(str(item.get("descricao", "") or "")),
                safe_strip(str(item.get("materialOuServico", "") or "")),
                _to_decimal(item.get("valorUnitarioEstimado")),
                _to_decimal(item.get("valorTotal")),
                _to_decimal(item.get("quantidade")),
                safe_strip(str(item.get("unidadeMedida", "") or "")),
                item.get("orcamentoSigiloso"),
                safe_strip(str(item.get("criterioJulgamentoNome", "") or "")),
                safe_strip(str(item.get("situacaoCompraItemNome", "") or "")),
                item.get("temResultado"),
                safe_strip(str(item.get("ncmNbsCodigo", "") or "")) or None,
                safe_strip(str(item.get("ncmNbsDescricao", "") or "")) or None,
                safe_strip(str(item.get("catalogo", "") or "")) or None,
                safe_strip(str(item.get("catalogoCodigoItem", "") or "")) or None,
                _parse_ts(item.get("dataInclusao")),
                _parse_ts(item.get("dataAtualizacao")),
                item.get("_cnpj_orgao", ""),
                item.get("_ano_compra"),
                item.get("_sequencial_compra"),
            )

            batch.append(row)

            if len(batch) >= BATCH_SIZE:
                batch_insert(conn, "pncp_item", COLUMNS, batch)
                total += len(batch)
                batch = []

    if batch:
        batch_insert(conn, "pncp_item", COLUMNS, batch)
        total += len(batch)

    print(f"    pncp_item: {table_count(conn, 'pncp_item')} registros ({erros} arquivos com erro)")


def run():
    conn = get_conn()
    try:
        load_itens(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
