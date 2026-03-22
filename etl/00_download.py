"""Fase 0: Download de todos os dados brutos das fontes oficiais.

Baixa dados do Portal da Transparencia (CGU), PNCP e Receita Federal.
Dados sao salvos em DATA_DIR (configurado no .env).

Uso:
  python -m etl.00_download              # Baixa tudo
  python -m etl.00_download --only cpgf   # Baixa so CPGF
  python -m etl.00_download --only viagens --anos 2020,2021
"""

import os
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve
from urllib.error import URLError, HTTPError

from tqdm import tqdm

from etl.config import DATA_DIR


# ── URLs e padroes de download ──────────────────────────────────

TRANSPARENCIA_BASE = "https://portaldatransparencia.gov.br/download-de-dados"
RFB_BASE = "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida"


def _download(url, dest_path):
    """Baixa arquivo com barra de progresso. Pula se ja existe."""
    if dest_path.exists() and dest_path.stat().st_size > 1000:
        print(f"    [pula] {dest_path.name} (ja existe)")
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"    [baixando] {dest_path.name}...")

    try:
        urlretrieve(url, dest_path)
        size_mb = dest_path.stat().st_size / 1e6
        print(f"    [ok] {dest_path.name} ({size_mb:.1f}MB)")
        return True
    except (URLError, HTTPError) as e:
        print(f"    [erro] {dest_path.name}: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def _unzip(zip_path, dest_dir=None):
    """Extrai zip. Destino padrao = mesmo diretorio do zip."""
    if dest_dir is None:
        dest_dir = zip_path.parent
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(dest_dir)
    except zipfile.BadZipFile:
        print(f"    [erro] {zip_path.name} nao e um zip valido")


# ── Downloads por fonte ─────────────────────────────────────────

def download_cpgf(anos=None):
    """Cartao de Pagamento do Governo Federal (mensal)."""
    if anos is None:
        anos = range(2020, 2027)
    dest = DATA_DIR / "cpgf"
    dest.mkdir(parents=True, exist_ok=True)

    print("  CPGF:")
    for ano in anos:
        for mes in range(1, 13):
            ym = f"{ano}{mes:02d}"
            url = f"{TRANSPARENCIA_BASE}/cpgf/{ym}"
            zip_path = dest / f"{ym}_CPGF.zip"
            if _download(url, zip_path):
                _unzip(zip_path, dest)


def download_viagens(anos=None):
    """Viagens a servico (anual)."""
    if anos is None:
        anos = range(2020, 2027)
    dest = DATA_DIR / "viagens"
    dest.mkdir(parents=True, exist_ok=True)

    print("  Viagens:")
    for ano in anos:
        url = f"{TRANSPARENCIA_BASE}/viagens/{ano}"
        zip_path = dest / f"viagens_{ano}.zip"
        if _download(url, zip_path):
            _unzip(zip_path, dest)


def download_siape(meses=None):
    """Servidores federais SIAPE (mensal)."""
    if meses is None:
        meses = ["202602"]  # Mais recente por padrao
    dest = DATA_DIR / "siape"
    dest.mkdir(parents=True, exist_ok=True)

    print("  SIAPE:")
    for ym in meses:
        url = f"{TRANSPARENCIA_BASE}/servidores/{ym}_Servidores_SIAPE"
        zip_path = dest / f"{ym}_Servidores_SIAPE.zip"
        if _download(url, zip_path):
            _unzip(zip_path, dest)


def download_sancoes():
    """CEIS, CNEP, CEAF, Acordos de Leniencia (snapshot diario)."""
    dest = DATA_DIR / "sancoes"
    dest.mkdir(parents=True, exist_ok=True)

    # Usar data de hoje
    from datetime import date
    dt = date.today().strftime("%Y%m%d")

    print("  Sancoes:")
    for dataset in ["ceis", "cnep", "ceaf", "acordos-leniencia"]:
        url = f"{TRANSPARENCIA_BASE}/{dataset}/{dt}"
        name = dataset.replace("-", "_").upper()
        zip_path = dest / f"{dt}_{name}.zip"
        if _download(url, zip_path):
            _unzip(zip_path, dest)


def download_emendas():
    """Emendas parlamentares - Tesouro (snapshot)."""
    dest = DATA_DIR
    # Emendas do Tesouro nao tem URL padrao de download do portal.
    # Os dados originais vieram de outra fonte (br-acc).
    print("  Emendas: dados originais do br-acc (sem download automatizado)")


def download_pgfn():
    """Divida Ativa da Uniao - PGFN."""
    # PGFN tem download proprio fora do Portal da Transparencia
    # https://www.gov.br/pgfn/pt-br/assuntos/divida-ativa-da-uniao/transparencia-fiscal-1
    print("  PGFN: dados originais do br-acc (download manual via gov.br/pgfn)")


def download_rfb():
    """Dados CNPJ da Receita Federal."""
    # RFB tem download proprio: https://dados.gov.br/dados/conjuntos-dados/cadastro-nacional-da-pessoa-juridica---cnpj
    # Arquivos sao muito grandes (~30GB) e mudam trimestralmente
    print("  RFB/CNPJ: dados originais do br-acc (download manual via dados.gov.br)")


def download_pncp():
    """PNCP - licitacoes e contratos."""
    # Contratacoes e contratos: dados originais do br-acc (JSON pre-baixado)
    print("  PNCP contratacoes/contratos: dados originais do br-acc")
    # Itens e resultados: baixar via API (requer contratacoes ja carregadas no banco)
    print("  PNCP itens/resultados: usar 'python -m etl.download_pncp'")


def download_renuncias():
    """Renuncias fiscais (anual)."""
    dest = DATA_DIR
    # Renuncias ja vieram do br-acc como 20XX_RenunciasFiscais.csv
    print("  Renuncias: dados originais do br-acc (sem download automatizado)")


def download_tce_pb(anos=None):
    """TCE-PB - Dados consolidados (despesas, servidores, licitacoes, receitas)."""
    if anos is None:
        anos = range(2018, 2027)
    dest = DATA_DIR / "tce_pb"
    dest.mkdir(parents=True, exist_ok=True)

    TCE_BASE = "https://download.tce.pb.gov.br/dados-abertos/dados-consolidados"
    categorias = ["despesas", "servidores", "licitacoes", "receitas"]

    print("  TCE-PB:")
    for cat in categorias:
        for ano in anos:
            url = f"{TCE_BASE}/{cat}/{cat}-{ano}.zip"
            zip_path = dest / f"{cat}-{ano}.zip"
            if _download(url, zip_path):
                _unzip(zip_path, dest)


def download_complementar():
    """BNDES, Holdings, ComprasNet."""
    print("  BNDES: dados originais do br-acc (download manual via dadosabertos.bndes.gov.br)")
    print("  Holdings: dados originais do br-acc")
    print("  ComprasNet: dados originais do br-acc")


# ── Orquestrador ────────────────────────────────────────────────

DOWNLOADERS = {
    "cpgf": download_cpgf,
    "viagens": download_viagens,
    "siape": download_siape,
    "sancoes": download_sancoes,
    "emendas": download_emendas,
    "pgfn": download_pgfn,
    "rfb": download_rfb,
    "pncp": download_pncp,
    "renuncias": download_renuncias,
    "tce_pb": download_tce_pb,
    "complementar": download_complementar,
}


def run():
    print("=" * 60)
    print("Download de dados brutos")
    print(f"Destino: {DATA_DIR}")
    print("=" * 60)

    # Parse args
    only = None
    anos = None
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--only" and i + 1 < len(args):
            only = args[i + 1].split(",")
            i += 2
        elif args[i] == "--anos" and i + 1 < len(args):
            anos = [int(a) for a in args[i + 1].split(",")]
            i += 2
        else:
            i += 1

    sources = only if only else DOWNLOADERS.keys()

    for source in sources:
        if source not in DOWNLOADERS:
            print(f"  AVISO: fonte '{source}' desconhecida, pulando.")
            continue

        fn = DOWNLOADERS[source]
        # Passar anos se a funcao aceita
        if anos and source in ("cpgf", "viagens", "tce_pb"):
            fn(anos=anos)
        elif source == "siape" and anos:
            fn(meses=[f"{a}01" for a in anos])
        else:
            fn()

    print("\nDownloads concluidos.")


if __name__ == "__main__":
    run()
