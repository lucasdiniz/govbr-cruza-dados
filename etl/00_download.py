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
from datetime import date
from pathlib import Path
from urllib.request import urlretrieve
from urllib.error import URLError, HTTPError

from tqdm import tqdm

from etl.config import DATA_DIR


# ── URLs e padroes de download ──────────────────────────────────

TRANSPARENCIA_BASE = "https://portaldatransparencia.gov.br/download-de-dados"
RFB_BASE = "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida"

CURRENT_YEAR = date.today().year
DEFAULT_ANOS = range(2020, CURRENT_YEAR + 1)


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
        anos = DEFAULT_ANOS
    dest = DATA_DIR / "cpgf"
    dest.mkdir(parents=True, exist_ok=True)

    current_ym = int(f"{date.today().year}{date.today().month:02d}")
    print("  CPGF:")
    for ano in anos:
        for mes in range(1, 13):
            ym = f"{ano}{mes:02d}"
            if int(ym) > current_ym:
                break
            url = f"{TRANSPARENCIA_BASE}/cpgf/{ym}"
            zip_path = dest / f"{ym}_CPGF.zip"
            if _download(url, zip_path):
                _unzip(zip_path, dest)


def download_viagens(anos=None):
    """Viagens a servico (anual)."""
    if anos is None:
        anos = DEFAULT_ANOS
    dest = DATA_DIR / "viagens"
    dest.mkdir(parents=True, exist_ok=True)

    print("  Viagens:")
    for ano in anos:
        url = f"{TRANSPARENCIA_BASE}/viagens/{ano}"
        zip_path = dest / f"viagens_{ano}.zip"
        if _download(url, zip_path):
            _unzip(zip_path, dest)


def download_siape(meses=None):
    """Servidores federais SIAPE (mensal). Tenta mes atual e 2 anteriores."""
    if meses is None:
        today = date.today()
        meses = []
        for offset in range(3):  # tenta mes atual, -1, -2
            m = today.month - offset
            y = today.year
            if m <= 0:
                m += 12
                y -= 1
            meses.append(f"{y}{m:02d}")
    dest = DATA_DIR / "siape"
    dest.mkdir(parents=True, exist_ok=True)

    print("  SIAPE:")
    for ym in meses:
        url = f"{TRANSPARENCIA_BASE}/servidores/{ym}_Servidores_SIAPE"
        zip_path = dest / f"{ym}_Servidores_SIAPE.zip"
        if _download(url, zip_path):
            _unzip(zip_path, dest)


def download_sancoes():
    """CEIS, CNEP, CEAF, Acordos de Leniencia (snapshot diario).
    Tenta data de hoje e ate 7 dias anteriores (publicacao pode atrasar).
    """
    from datetime import timedelta
    dest = DATA_DIR / "sancoes"
    dest.mkdir(parents=True, exist_ok=True)

    print("  Sancoes:")
    for dataset in ["ceis", "cnep", "ceaf", "acordos-leniencia"]:
        name = dataset.replace("-", "_").upper()
        downloaded = False
        for offset in range(8):  # hoje ate 7 dias atras
            dt = (date.today() - timedelta(days=offset)).strftime("%Y%m%d")
            zip_path = dest / f"{dt}_{name}.zip"
            url = f"{TRANSPARENCIA_BASE}/{dataset}/{dt}"
            if _download(url, zip_path):
                _unzip(zip_path, dest)
                downloaded = True
                break
        if not downloaded:
            print(f"    [aviso] {name}: nenhuma data disponivel nos ultimos 7 dias")


def download_emendas(anos=None):
    """Emendas parlamentares - Portal da Transparencia (anual)."""
    if anos is None:
        anos = DEFAULT_ANOS
    dest = DATA_DIR / "emendas"
    dest.mkdir(parents=True, exist_ok=True)

    print("  Emendas:")
    for ano in anos:
        url = f"{TRANSPARENCIA_BASE}/emendas-parlamentares/{ano}"
        zip_path = dest / f"{ano}_EmendaParlamentar.zip"
        if _download(url, zip_path):
            _unzip(zip_path, dest)


def download_pgfn():
    """Divida Ativa da Uniao - PGFN (dados abertos, trimestral).

    URL: https://dadosabertos.pgfn.gov.br/{YYYY}_trimestre_{QQ}/
    3 arquivos por trimestre. Tenta o mais recente.
    """
    dest = DATA_DIR / "pgfn"
    dest.mkdir(parents=True, exist_ok=True)

    PGFN_BASE = "https://dadosabertos.pgfn.gov.br"
    arquivos = [
        "Dados_abertos_Nao_Previdenciario.zip",
        "Dados_abertos_Previdenciario.zip",
        "Dados_abertos_FGTS.zip",
    ]

    # Tentar trimestres recentes (atual ate 2 atras)
    today = date.today()
    trimestre_atual = (today.month - 1) // 3 + 1
    tentativas = []
    for delta in range(4):
        q = trimestre_atual - delta
        y = today.year
        while q <= 0:
            q += 4
            y -= 1
        tentativas.append(f"{y}_trimestre_{q:02d}")

    print("  PGFN:")
    pgfn_dir = None
    for tri in tentativas:
        test_url = f"{PGFN_BASE}/{tri}/{arquivos[0]}"
        test_path = dest / f"test_{tri}.zip"
        if _download(test_url, test_path):
            pgfn_dir = tri
            # Rename test file to proper name
            proper = dest / arquivos[0]
            if not proper.exists():
                test_path.rename(proper)
            _unzip(proper, dest)
            print(f"    Usando dados de {tri}")
            break
        if test_path.exists():
            test_path.unlink()
        print(f"    {tri} nao disponivel...")

    if not pgfn_dir:
        print("    ERRO: nenhum trimestre disponivel")
        return

    # Baixar os outros arquivos
    for arq in arquivos[1:]:
        url = f"{PGFN_BASE}/{pgfn_dir}/{arq}"
        zip_path = dest / arq
        if _download(url, zip_path):
            _unzip(zip_path, dest)


def download_rfb():
    """Dados CNPJ da Receita Federal (~30GB, atualizado mensalmente).

    URL: https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj/{YYYY-MM}/
    Tenta mes atual e anterior ate encontrar dados disponiveis.
    """
    dest = DATA_DIR / "rfb"
    dest.mkdir(parents=True, exist_ok=True)

    RFB_BASE = "https://dadosabertos.rfb.gov.br/CNPJ/dados_abertos_cnpj"
    categorias = {
        "Empresas": 10,
        "Estabelecimentos": 10,
        "Socios": 10,
        "Simples": 1,
        "Cnaes": 1,
        "Motivos": 1,
        "Municipios": 1,
        "Naturezas": 1,
        "Paises": 1,
        "Qualificacoes": 1,
    }

    # Tentar mes atual e os 3 anteriores
    from datetime import timedelta
    today = date.today()
    meses_tentativa = []
    for delta in range(4):
        d = today.replace(day=1) - timedelta(days=delta * 28)
        meses_tentativa.append(f"{d.year}-{d.month:02d}")

    print("  RFB/CNPJ:")
    rfb_month = None
    for mes in meses_tentativa:
        # Testar se o mes existe baixando o menor arquivo
        test_url = f"{RFB_BASE}/{mes}/Cnaes.zip"
        test_path = dest / f"Cnaes_{mes}.zip"
        if _download(test_url, test_path):
            rfb_month = mes
            print(f"    Usando dados de {mes}")
            break
        print(f"    {mes} nao disponivel, tentando anterior...")

    if not rfb_month:
        print("    ERRO: nenhum mes disponivel encontrado")
        return

    for cat, n_files in categorias.items():
        for i in range(n_files):
            fname = f"{cat}{i}.zip" if n_files > 1 else f"{cat}.zip"
            url = f"{RFB_BASE}/{rfb_month}/{fname}"
            zip_path = dest / fname
            if _download(url, zip_path):
                _unzip(zip_path, dest)


def download_pncp():
    """PNCP - licitacoes e contratos (API only, sem bulk download)."""
    print("  PNCP:")
    print("    Contratacoes/contratos: sem bulk download disponivel")
    print("    Usar 'python -m etl.download_pncp' para baixar via API REST")


def download_renuncias(anos=None):
    """Renuncias fiscais (anual) - Portal da Transparencia."""
    if anos is None:
        anos = DEFAULT_ANOS
    dest = DATA_DIR / "renuncias"
    dest.mkdir(parents=True, exist_ok=True)

    print("  Renuncias:")
    for ano in anos:
        url = f"{TRANSPARENCIA_BASE}/renuncias/{ano}"
        zip_path = dest / f"{ano}_RenunciasFiscais.zip"
        if _download(url, zip_path):
            _unzip(zip_path, dest)


def download_tce_pb(anos=None):
    """TCE-PB - Dados consolidados (despesas, servidores, licitacoes, receitas)."""
    if anos is None:
        anos = range(2018, CURRENT_YEAR + 1)
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


def download_dados_pb(anos=None):
    """dados.pb.gov.br - Dados estaduais PB (pagamento, empenho, contratos, saude, convenios)."""
    if anos is None:
        anos = range(2018, CURRENT_YEAR + 1)
    dest = DATA_DIR / "dados_pb"
    dest.mkdir(parents=True, exist_ok=True)

    from urllib.request import urlopen
    from urllib.error import URLError, HTTPError

    PB_BASE = "https://dados.pb.gov.br:443/getcsv"

    # Datasets mensais
    monthly = [
        ("pagamento", "pagamento"),
        ("empenho_original", "empenho"),
        ("pagamentos_gestao_pactuada_saude", "saude"),
    ]

    print("  dados.pb.gov.br:")
    for api_nome, file_prefix in monthly:
        for ano in anos:
            for mes in range(1, 13):
                fname = f"{file_prefix}_{ano}_{mes:02d}.csv"
                fpath = dest / fname
                if fpath.exists() and fpath.stat().st_size > 100:
                    continue
                url = f"{PB_BASE}?nome={api_nome}&exercicio={ano}&mes={mes}"
                try:
                    resp = urlopen(url, timeout=120)
                    data = resp.read()
                    if len(data) > 100:
                        with open(fpath, "wb") as f:
                            f.write(data)
                        print(f"    [ok] {fname} ({len(data)/1024:.0f}KB)")
                    else:
                        print(f"    [vazio] {fname}")
                except (URLError, HTTPError):
                    print(f"    [erro] {fname}")

    # Contratos (por ano, sem mes)
    for ano in anos:
        fname = f"contratos_{ano}.csv"
        fpath = dest / fname
        if fpath.exists() and fpath.stat().st_size > 100:
            continue
        url = f"{PB_BASE}?nome=contratos&exercicio={ano}"
        try:
            resp = urlopen(url, timeout=120)
            data = resp.read()
            if len(data) > 100:
                with open(fpath, "wb") as f:
                    f.write(data)
                print(f"    [ok] {fname} ({len(data)/1024:.0f}KB)")
        except (URLError, HTTPError):
            pass

    # Convenios (por ano)
    for ano in anos:
        fname = f"convenios_{ano}.csv"
        fpath = dest / fname
        if fpath.exists() and fpath.stat().st_size > 100:
            continue
        url = f"{PB_BASE}?nome=convenios&exercicio={ano}&mes_inicio=1&mes_fim=12"
        try:
            resp = urlopen(url, timeout=120)
            data = resp.read()
            if len(data) > 100:
                with open(fpath, "wb") as f:
                    f.write(data)
                print(f"    [ok] {fname} ({len(data)/1024:.0f}KB)")
        except (URLError, HTTPError):
            pass


def download_complementar():
    """BNDES, Holdings, ComprasNet."""
    dest_bndes = DATA_DIR / "bndes"
    dest_bndes.mkdir(parents=True, exist_ok=True)

    print("  BNDES:")
    # BNDES operacoes financeiras - agora dividido em 2 CSVs
    BNDES_BASE = "https://dadosabertos.bndes.gov.br/dataset/10e21ad1-568e-45e5-a8af-43f2c05ef1a2/resource"
    bndes_files = {
        "operacoes-financiamento-operacoes-nao-automaticas.csv":
            f"{BNDES_BASE}/6f56b78c-510f-44b6-8274-78a5b7e931f4/download/operacoes-financiamento-operacoes-nao-automaticas.csv",
        "operacoes-financiamento-operacoes-indiretas-automaticas.csv":
            f"{BNDES_BASE}/612faa0b-b6be-4b2c-9317-da5dc2c0b901/download/operacoes-financiamento-operacoes-indiretas-automaticas.csv",
    }
    for fname, url in bndes_files.items():
        _download(url, dest_bndes / fname)

    # Holdings: relacoes holding-subsidiaria extraidas dos socios RFB (507k rows)
    # Sem fonte publica conhecida separada — derivado do RFB socios
    print("  Holdings: derivado RFB socios (holding.csv no DATA_DIR)")

    # ComprasNet: contratos federais (104k rows) — substituido por compras.gov.br
    # Dados historicos sem endpoint bulk publico
    print("  ComprasNet: dados historicos (comprasnet.csv no DATA_DIR)")


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
    "dados_pb": download_dados_pb,
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
        if anos and source in ("cpgf", "viagens", "tce_pb", "dados_pb", "emendas", "renuncias"):
            fn(anos=anos)
        elif source == "siape" and anos:
            fn(meses=[f"{a}01" for a in anos])
        else:
            fn()

    print("\nDownloads concluidos.")


if __name__ == "__main__":
    run()
