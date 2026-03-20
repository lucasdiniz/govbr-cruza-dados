"""Fase 4.1-4.2: Carrega dados do PNCP (JSON → PostgreSQL).

Usa ijson para streaming incremental de JSONs grandes.
"""

import json
from pathlib import Path

import ijson
from tqdm import tqdm

from etl.config import DATA_DIR, BATCH_SIZE
from etl.db import get_conn, batch_insert, table_count
from etl.utils import parse_date_br, safe_strip


def _safe_get(obj: dict, *keys, default=None):
    """Acessa chaves aninhadas em dict com segurança."""
    current = obj
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return default
        if current is None:
            return default
    return current


def _parse_date_or_none(val):
    """Parse ISO date string ou None."""
    if not val:
        return None
    s = str(val)[:10]  # Pega só YYYY-MM-DD
    return parse_date_br(s)


def _parse_timestamp_or_none(val):
    """Parse ISO timestamp string ou None."""
    if not val:
        return None
    return str(val)[:19]  # YYYY-MM-DDTHH:MM:SS


def _to_decimal(val):
    """Converte valor numérico para string decimal ou None."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def load_contratacoes(conn):
    """Carrega pncp/*.json → pncp_contratacao."""
    pncp_dir = DATA_DIR / "pncp"
    if not pncp_dir.exists():
        print("    AVISO: diretório pncp/ não encontrado.")
        return

    files = sorted(pncp_dir.glob("*.json"))
    columns = [
        "numero_controle_pncp", "cnpj_orgao", "orgao_razao_social",
        "poder", "esfera", "uf", "municipio_nome", "municipio_ibge",
        "codigo_unidade", "nome_unidade",
        "ano_compra", "sequencial_compra", "numero_compra", "processo",
        "objeto", "modalidade_id", "modalidade_nome",
        "modo_disputa_nome", "situacao_nome", "amparo_legal", "srp",
        "valor_estimado", "valor_homologado",
        "dt_abertura_proposta", "dt_encerramento_proposta",
        "dt_publicacao_pncp", "dt_atualizacao",
    ]

    batch = []
    total = 0

    for filepath in tqdm(files, desc="    PNCP contratações"):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"      AVISO: erro ao parsear {filepath.name}, pulando.")
                continue

        # data pode ser uma lista ou um dict com chave "data"
        items = data if isinstance(data, list) else data.get("data", [])

        for item in items:
            row = (
                safe_strip(str(_safe_get(item, "numeroControlePNCP", default=""))),
                safe_strip(str(_safe_get(item, "orgaoEntidade", "cnpj", default=""))),
                safe_strip(str(_safe_get(item, "orgaoEntidade", "razaoSocial", default=""))),
                safe_strip(str(_safe_get(item, "orgaoEntidade", "poderId", default=""))),
                safe_strip(str(_safe_get(item, "orgaoEntidade", "esferaId", default=""))),
                safe_strip(str(_safe_get(item, "unidadeOrgao", "ufSigla", default=""))),
                safe_strip(str(_safe_get(item, "unidadeOrgao", "municipioNome", default=""))),
                _safe_get(item, "unidadeOrgao", "codigoIbge"),
                safe_strip(str(_safe_get(item, "unidadeOrgao", "codigoUnidade", default=""))),
                safe_strip(str(_safe_get(item, "unidadeOrgao", "nomeUnidade", default=""))),
                _safe_get(item, "anoCompra"),
                _safe_get(item, "sequencialCompra"),
                safe_strip(str(_safe_get(item, "numeroCompra", default=""))),
                safe_strip(str(_safe_get(item, "processo", default=""))),
                safe_strip(str(_safe_get(item, "objetoCompra", default=""))),
                _safe_get(item, "modalidadeId"),
                safe_strip(str(_safe_get(item, "modalidadeNome", default=""))),
                safe_strip(str(_safe_get(item, "modoDisputaNome", default=""))),
                safe_strip(str(_safe_get(item, "situacaoCompraNome", default=""))),
                safe_strip(str(_safe_get(item, "amparoLegal", "nome", default=""))),
                _safe_get(item, "srp"),
                _to_decimal(_safe_get(item, "valorTotalEstimado")),
                _to_decimal(_safe_get(item, "valorTotalHomologado")),
                _parse_timestamp_or_none(_safe_get(item, "dataAberturaProposta")),
                _parse_timestamp_or_none(_safe_get(item, "dataEncerramentoProposta")),
                _parse_date_or_none(_safe_get(item, "dataPublicacaoPncp")),
                _parse_timestamp_or_none(_safe_get(item, "dataAtualizacao")),
            )

            if row[0]:  # Tem numero_controle_pncp
                batch.append(row)

            if len(batch) >= BATCH_SIZE:
                batch_insert(conn, "pncp_contratacao", columns, batch)
                total += len(batch)
                batch = []

    if batch:
        batch_insert(conn, "pncp_contratacao", columns, batch)
        total += len(batch)

    print(f"    pncp_contratacao: {table_count(conn, 'pncp_contratacao')} registros")


def load_contratos(conn):
    """Carrega pncp_contratos/*.json → pncp_contrato."""
    contratos_dir = DATA_DIR / "pncp_contratos"
    if not contratos_dir.exists():
        print("    AVISO: diretório pncp_contratos/ não encontrado.")
        return

    files = sorted(contratos_dir.glob("*.json"))
    columns = [
        "numero_controle_pncp", "numero_controle_contratacao",
        "cnpj_orgao", "orgao_razao_social", "poder", "esfera",
        "uf", "municipio_nome", "municipio_ibge",
        "codigo_unidade", "nome_unidade",
        "tipo_contrato", "categoria_processo",
        "tipo_pessoa_fornecedor", "ni_fornecedor", "nome_fornecedor",
        "pais_fornecedor", "receita", "objeto", "processo",
        "valor_inicial", "valor_global", "valor_acumulado",
        "valor_parcela", "num_parcelas",
        "ano_contrato", "sequencial_contrato",
        "dt_assinatura", "dt_vigencia_inicio", "dt_vigencia_fim",
        "dt_publicacao_pncp", "dt_atualizacao",
    ]

    batch = []
    total = 0

    for filepath in tqdm(files, desc="    PNCP contratos"):
        with open(filepath, "r", encoding="utf-8") as f:
            try:
                raw = json.load(f)
            except json.JSONDecodeError:
                print(f"      AVISO: erro ao parsear {filepath.name}, pulando.")
                continue

        items = raw if isinstance(raw, list) else raw.get("data", [])
        if items is None:
            continue

        for item in items:
            row = (
                safe_strip(str(_safe_get(item, "numeroControlePNCP", default=""))),
                safe_strip(str(_safe_get(item, "numeroControlePncpCompra", default=""))),
                safe_strip(str(_safe_get(item, "orgaoEntidade", "cnpj", default=""))),
                safe_strip(str(_safe_get(item, "orgaoEntidade", "razaoSocial", default=""))),
                safe_strip(str(_safe_get(item, "orgaoEntidade", "poderId", default=""))),
                safe_strip(str(_safe_get(item, "orgaoEntidade", "esferaId", default=""))),
                safe_strip(str(_safe_get(item, "unidadeOrgao", "ufSigla", default=""))),
                safe_strip(str(_safe_get(item, "unidadeOrgao", "municipioNome", default=""))),
                _safe_get(item, "unidadeOrgao", "codigoIbge"),
                safe_strip(str(_safe_get(item, "unidadeOrgao", "codigoUnidade", default=""))),
                safe_strip(str(_safe_get(item, "unidadeOrgao", "nomeUnidade", default=""))),
                safe_strip(str(_safe_get(item, "tipoContrato", "nome", default=""))),
                safe_strip(str(_safe_get(item, "categoriaProcesso", "nome", default=""))),
                safe_strip(str(_safe_get(item, "tipoPessoa", default=""))),
                safe_strip(str(_safe_get(item, "niFornecedor", default=""))),
                safe_strip(str(_safe_get(item, "nomeRazaoSocialFornecedor", default=""))),
                safe_strip(str(_safe_get(item, "codigoPaisFornecedor", default=""))),
                _safe_get(item, "receita"),
                safe_strip(str(_safe_get(item, "objetoContrato", default=""))),
                safe_strip(str(_safe_get(item, "processo", default=""))),
                _to_decimal(_safe_get(item, "valorInicial")),
                _to_decimal(_safe_get(item, "valorGlobal")),
                _to_decimal(_safe_get(item, "valorAcumulado")),
                _to_decimal(_safe_get(item, "valorParcela")),
                _safe_get(item, "numeroParcelas"),
                _safe_get(item, "anoContrato"),
                _safe_get(item, "sequencialContrato"),
                _parse_date_or_none(_safe_get(item, "dataAssinatura")),
                _parse_date_or_none(_safe_get(item, "dataVigenciaInicio")),
                _parse_date_or_none(_safe_get(item, "dataVigenciaFim")),
                _parse_timestamp_or_none(_safe_get(item, "dataPublicacaoPncp")),
                _parse_timestamp_or_none(_safe_get(item, "dataAtualizacao")),
            )

            if row[0]:
                batch.append(row)

            if len(batch) >= BATCH_SIZE:
                batch_insert(conn, "pncp_contrato", columns, batch)
                total += len(batch)
                batch = []

    if batch:
        batch_insert(conn, "pncp_contrato", columns, batch)
        total += len(batch)

    print(f"    pncp_contrato: {table_count(conn, 'pncp_contrato')} registros")


def run():
    conn = get_conn()
    try:
        load_contratacoes(conn)
        load_contratos(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    run()
