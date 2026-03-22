"""Download de itens e resultados (propostas) do PNCP via API REST.

Itera sobre todas as contratacoes no banco e baixa:
  1. Itens de cada contratacao (descricao, qtd, valor unitario, unidade)
  2. Resultados/propostas de cada item (fornecedor vencedor, valor homologado)

Salva JSONs incrementalmente em DATA_DIR/pncp_itens/ e DATA_DIR/pncp_resultados/.
Usa checkpoint para retomar de onde parou.

Uso:
  python -m etl.download_pncp                    # Baixa itens + resultados
  python -m etl.download_pncp --only itens        # So itens
  python -m etl.download_pncp --only resultados   # So resultados
  python -m etl.download_pncp --workers 20        # Paralelismo (default: 10)
"""

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from etl.config import DATA_DIR
from etl.db import get_conn

# ── Config ────────────────────────────────────────────────────────

PNCP_API_BASE = "https://pncp.gov.br/api/pncp/v1"
DEFAULT_WORKERS = 10
REQUEST_TIMEOUT = 30  # seconds

ITENS_DIR = DATA_DIR / "pncp_itens"
RESULTADOS_DIR = DATA_DIR / "pncp_resultados"


# ── Helpers ───────────────────────────────────────────────────────

def _api_get(url):
    """GET request com retry simples."""
    for attempt in range(3):
        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (URLError, HTTPError, TimeoutError, json.JSONDecodeError) as e:
            if attempt == 2:
                return None
            time.sleep(1 * (attempt + 1))
    return None


def _load_checkpoint(path):
    """Carrega set de contratacoes ja processadas."""
    if path.exists():
        return set(path.read_text(encoding="utf-8").splitlines())
    return set()


def _save_checkpoint(path, processed_id):
    """Adiciona um ID ao checkpoint."""
    with open(path, "a", encoding="utf-8") as f:
        f.write(processed_id + "\n")


def _get_contratacoes():
    """Busca todas as contratacoes do banco (cnpj, ano, sequencial, numero_controle)."""
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT cnpj_orgao, ano_compra, sequencial_compra, numero_controle_pncp
                FROM pncp_contratacao
                WHERE cnpj_orgao IS NOT NULL
                  AND ano_compra IS NOT NULL
                  AND sequencial_compra IS NOT NULL
                ORDER BY ano_compra DESC, sequencial_compra DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()


# ── Download de itens ─────────────────────────────────────────────

def _download_itens_one(cnpj, ano, seq, numero_controle):
    """Baixa itens de uma contratacao. Retorna (numero_controle, n_itens) ou None."""
    # Arquivo de saida: pncp_itens/{cnpj}_{ano}_{seq}.json
    out_file = ITENS_DIR / f"{cnpj}_{ano}_{seq}.json"
    if out_file.exists():
        return (numero_controle, -1)  # ja existe

    url = f"{PNCP_API_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
    data = _api_get(url)

    if data is None:
        return None

    # Enriquecer cada item com referencia a contratacao
    if isinstance(data, list):
        for item in data:
            item["_numero_controle_pncp"] = numero_controle
            item["_cnpj_orgao"] = cnpj
            item["_ano_compra"] = ano
            item["_sequencial_compra"] = seq

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    n = len(data) if isinstance(data, list) else 0
    return (numero_controle, n)


def download_itens(contratacoes, workers=DEFAULT_WORKERS):
    """Baixa itens de todas as contratacoes com paralelismo."""
    ITENS_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_path = ITENS_DIR / "_checkpoint.txt"
    done = _load_checkpoint(checkpoint_path)

    pending = [(c, a, s, nc) for c, a, s, nc in contratacoes if nc not in done]
    print(f"  Itens PNCP: {len(pending)} pendentes ({len(done)} ja baixados)")

    if not pending:
        return

    total_itens = 0
    erros = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_download_itens_one, c, a, s, nc): nc
            for c, a, s, nc in pending
        }

        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if result is None:
                erros += 1
            else:
                nc, n = result
                if n >= 0:
                    total_itens += max(n, 0)
                _save_checkpoint(checkpoint_path, nc)

            if i % 1000 == 0:
                elapsed = time.time() - t0
                rate = i / elapsed
                eta = (len(pending) - i) / rate if rate > 0 else 0
                print(f"    {i}/{len(pending)} ({rate:.0f}/s, "
                      f"~{eta/60:.0f}min restante, "
                      f"{total_itens} itens, {erros} erros)")

    elapsed = time.time() - t0
    print(f"  Itens concluido: {total_itens} itens de {len(pending)} "
          f"contratacoes em {elapsed/60:.1f}min ({erros} erros)")


# ── Download de resultados ────────────────────────────────────────

def _download_resultados_one(cnpj, ano, seq, numero_controle):
    """Baixa resultados de todos os itens de uma contratacao."""
    out_file = RESULTADOS_DIR / f"{cnpj}_{ano}_{seq}.json"
    if out_file.exists():
        return (numero_controle, -1)

    # Primeiro busca itens para saber quantos sao
    itens_file = ITENS_DIR / f"{cnpj}_{ano}_{seq}.json"
    if itens_file.exists():
        with open(itens_file, "r", encoding="utf-8") as f:
            try:
                itens = json.load(f)
            except json.JSONDecodeError:
                return None
    else:
        # Busca itens da API
        url_itens = f"{PNCP_API_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/itens"
        itens = _api_get(url_itens)
        if not itens or not isinstance(itens, list):
            return (numero_controle, 0)

    all_resultados = []
    for item in itens:
        num_item = item.get("numeroItem")
        tem_resultado = item.get("temResultado", False)
        if not num_item or not tem_resultado:
            continue

        url = f"{PNCP_API_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{num_item}/resultados"
        data = _api_get(url)
        if data and isinstance(data, list):
            for r in data:
                r["_numero_controle_pncp"] = numero_controle
                r["_cnpj_orgao"] = cnpj
                r["_ano_compra"] = ano
                r["_sequencial_compra"] = seq
            all_resultados.extend(data)

    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_resultados, f, ensure_ascii=False)

    return (numero_controle, len(all_resultados))


def download_resultados(contratacoes, workers=DEFAULT_WORKERS):
    """Baixa resultados de todas as contratacoes com paralelismo."""
    RESULTADOS_DIR.mkdir(parents=True, exist_ok=True)
    checkpoint_path = RESULTADOS_DIR / "_checkpoint.txt"
    done = _load_checkpoint(checkpoint_path)

    pending = [(c, a, s, nc) for c, a, s, nc in contratacoes if nc not in done]
    print(f"  Resultados PNCP: {len(pending)} pendentes ({len(done)} ja baixados)")

    if not pending:
        return

    total_resultados = 0
    erros = 0
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_download_resultados_one, c, a, s, nc): nc
            for c, a, s, nc in pending
        }

        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if result is None:
                erros += 1
            else:
                nc, n = result
                if n >= 0:
                    total_resultados += max(n, 0)
                _save_checkpoint(checkpoint_path, nc)

            if i % 1000 == 0:
                elapsed = time.time() - t0
                rate = i / elapsed
                eta = (len(pending) - i) / rate if rate > 0 else 0
                print(f"    {i}/{len(pending)} ({rate:.0f}/s, "
                      f"~{eta/60:.0f}min restante, "
                      f"{total_resultados} resultados, {erros} erros)")

    elapsed = time.time() - t0
    print(f"  Resultados concluido: {total_resultados} resultados de {len(pending)} "
          f"contratacoes em {elapsed/60:.1f}min ({erros} erros)")


# ── Main ──────────────────────────────────────────────────────────

def run():
    print("=" * 60)
    print("Download PNCP: Itens e Resultados")
    print(f"Destino itens: {ITENS_DIR}")
    print(f"Destino resultados: {RESULTADOS_DIR}")
    print("=" * 60)

    # Parse args
    only = None
    workers = DEFAULT_WORKERS
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--only" and i + 1 < len(args):
            only = args[i + 1]
            i += 2
        elif args[i] == "--workers" and i + 1 < len(args):
            workers = int(args[i + 1])
            i += 2
        else:
            i += 1

    print(f"Workers: {workers}")
    print("Buscando contratacoes do banco...")
    contratacoes = _get_contratacoes()
    print(f"Total: {len(contratacoes)} contratacoes")

    if only is None or only == "itens":
        download_itens(contratacoes, workers=workers)

    if only is None or only == "resultados":
        download_resultados(contratacoes, workers=workers)

    print("\nDownload PNCP concluido.")


if __name__ == "__main__":
    run()
