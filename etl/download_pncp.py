"""Compat: wrapper legado para o downloader PNCP centralizado em etl.00_download.

Uso:
  python -m etl.download_pncp                    # Baixa itens
  python -m etl.download_pncp --workers 20        # Paralelismo (default: 10)
"""

from importlib import import_module

_download = import_module("etl.00_download")

DEFAULT_WORKERS = _download.DEFAULT_PNCP_ITEM_WORKERS
REQUEST_TIMEOUT = _download.PNCP_ITEM_REQUEST_TIMEOUT
ITENS_DIR = _download.ITENS_DIR
_api_get = _download._pncp_api_get
_load_checkpoint = _download._load_checkpoint
_save_checkpoint = _download._save_checkpoint
_get_contratacoes = _download._get_contratacoes
_download_itens_one = _download._download_itens_one
download_itens = _download.download_itens
run = _download.run_pncp_download


if __name__ == "__main__":
    run()
