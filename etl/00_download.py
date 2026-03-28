"""Fase 0: Download de todos os dados brutos das fontes oficiais.

Baixa dados do Portal da Transparencia (CGU), PNCP e Receita Federal.
Dados sao salvos em DATA_DIR (configurado no .env).

Uso:
  python -m etl.00_download              # Baixa tudo
  python -m etl.00_download --only cpgf   # Baixa so CPGF
  python -m etl.00_download --only viagens --anos 2020,2021
"""

import os
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen, urlretrieve
from urllib.error import URLError, HTTPError

from tqdm import tqdm

from etl.config import DATA_DIR

_UA = "Mozilla/5.0 (compatible; govbr-etl/1.0)"
_TIMEOUT = 300  # 5 min per file


# ── URLs e padroes de download ──────────────────────────────────

TRANSPARENCIA_BASE = "https://portaldatransparencia.gov.br/download-de-dados"
RFB_BASE = "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida"

CURRENT_YEAR = date.today().year
DEFAULT_ANOS = range(2020, CURRENT_YEAR + 1)


def _download(url, dest_path, timeout=_TIMEOUT):
    """Baixa arquivo com User-Agent e timeout. Pula se ja existe."""
    if dest_path.exists() and dest_path.stat().st_size > 1000:
        print(f"    [pula] {dest_path.name} (ja existe)")
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"    [baixando] {dest_path.name}...")

    try:
        req = Request(url, headers={"User-Agent": _UA})
        with urlopen(req, timeout=timeout) as resp:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(resp, f)
        size_mb = dest_path.stat().st_size / 1e6
        print(f"    [ok] {dest_path.name} ({size_mb:.1f}MB)")
        return True
    except (URLError, HTTPError) as e:
        print(f"    [erro] {dest_path.name}: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def _unzip(zip_path, dest_dir=None):
    """Extrai zip. Destino padrao = mesmo diretorio do zip.
    Deleta arquivo corrompido para permitir re-download.
    """
    if dest_dir is None:
        dest_dir = zip_path.parent
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(dest_dir)
    except zipfile.BadZipFile:
        print(f"    [erro] {zip_path.name} nao e um zip valido, deletando para re-download")
        zip_path.unlink(missing_ok=True)


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


def _download_rfb_webdav(url, dest_path, timeout=1800):
    """Download via Nextcloud WebDAV (Basic Auth com token, sem senha).

    Forca IPv4 pois arquivos.receitafederal.gov.br nao suporta IPv6.
    """
    if dest_path.exists() and dest_path.stat().st_size > 1000:
        print(f"    [pula] {dest_path.name} (ja existe)")
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"    [baixando] {dest_path.name}...")

    import base64
    import socket
    # Forcar IPv4 (RFB nao suporta IPv6, urllib tenta IPv6 primeiro e dá timeout)
    _orig_getaddrinfo = socket.getaddrinfo
    socket.getaddrinfo = lambda *a, **kw: [
        r for r in _orig_getaddrinfo(*a, **kw) if r[0] == socket.AF_INET
    ]
    try:
        auth = base64.b64encode(b"YggdBLfdninEJX9:").decode()
        req = Request(url, headers={
            "User-Agent": _UA,
            "Authorization": f"Basic {auth}",
        })
        with urlopen(req, timeout=timeout) as resp:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(resp, f)
        size_mb = dest_path.stat().st_size / 1e6
        print(f"    [ok] {dest_path.name} ({size_mb:.1f}MB)")
        return True
    except (URLError, HTTPError) as e:
        print(f"    [erro] {dest_path.name}: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False
    finally:
        socket.getaddrinfo = _orig_getaddrinfo


def download_rfb():
    """Dados CNPJ da Receita Federal (~7GB/mes, atualizado mensalmente).

    Fonte: Nextcloud share em arquivos.receitafederal.gov.br
    Acesso via WebDAV com token publico.
    """
    dest = DATA_DIR / "rfb"
    dest.mkdir(parents=True, exist_ok=True)

    RFB_WEBDAV = "https://arquivos.receitafederal.gov.br/public.php/webdav"
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
        test_url = f"{RFB_WEBDAV}/{mes}/Cnaes.zip"
        test_path = dest / "Cnaes.zip"
        if _download_rfb_webdav(test_url, test_path, timeout=60):
            rfb_month = mes
            _unzip(test_path, dest)
            print(f"    Usando dados de {mes}")
            break
        print(f"    {mes} nao disponivel, tentando anterior...")

    if not rfb_month:
        print("    ERRO: nenhum mes disponivel encontrado")
        return

    for cat, n_files in categorias.items():
        for i in range(n_files):
            fname = f"{cat}{i}.zip" if n_files > 1 else f"{cat}.zip"
            url = f"{RFB_WEBDAV}/{rfb_month}/{fname}"
            zip_path = dest / fname
            if _download_rfb_webdav(url, zip_path):
                _unzip(zip_path, dest)


def download_pncp(anos=None):
    """PNCP - contratacoes e contratos via API Consulta.

    Contratacoes: por data × modalidade (13 modalidades), max 500/pagina.
    Contratos: por data, max 500/pagina.
    Salva JSONs compativeis com etl/04_pncp.py loader.
    """
    import json
    import time

    if anos is None:
        anos = range(2021, CURRENT_YEAR + 1)  # PNCP existe desde 2021

    PNCP_API = "https://pncp.gov.br/api/consulta/v1"
    MODALIDADES = list(range(1, 14))  # 1-13
    PAGE_SIZE_CONTRATACOES = 50   # API max for contratacoes
    PAGE_SIZE_CONTRATOS = 500     # API max for contratos
    today = date.today()

    dest_contratacoes = DATA_DIR / "pncp"
    dest_contratacoes.mkdir(parents=True, exist_ok=True)
    dest_contratos = DATA_DIR / "pncp_contratos"
    dest_contratos.mkdir(parents=True, exist_ok=True)

    # Checkpoint: ultimo dia completo baixado
    ckpt_file = DATA_DIR / "pncp" / "_checkpoint.json"
    ckpt = {}
    if ckpt_file.exists():
        try:
            ckpt = json.loads(ckpt_file.read_text())
        except Exception:
            pass
    last_contratacao = ckpt.get("last_contratacao_date", "")
    last_contrato = ckpt.get("last_contrato_date", "")

    def _api_get(url, retries=5):
        """GET com retry e backoff exponencial."""
        for attempt in range(retries):
            try:
                req = Request(url, headers={"User-Agent": _UA})
                with urlopen(req, timeout=120) as resp:
                    raw = resp.read()
                    if not raw or not raw.strip():
                        raise ValueError("Empty response body")
                    return json.loads(raw)
            except Exception as e:
                wait = min(2 ** (attempt + 1), 30)  # 2, 4, 8, 16, 30s
                if attempt < retries - 1:
                    time.sleep(wait)
                else:
                    print(f"    [erro] {e}")
                    return None

    def _week_ranges(anos):
        """Gera intervalos semanais (seg-dom) para os anos solicitados."""
        from datetime import timedelta
        for ano in anos:
            d = date(ano, 1, 1)
            # Alinhar ao inicio da semana (segunda)
            d -= timedelta(days=d.weekday())
            end = min(date(ano, 12, 31), today)
            while d <= end:
                week_end = min(d + timedelta(days=6), end)
                yield d, week_end
                d += timedelta(days=7)

    def _fetch_all_pages(base_url, page_size, max_pages=2000):
        """Pagina por todos os resultados de uma URL base."""
        all_items = []
        page = 1
        while page <= max_pages:
            url = f"{base_url}&pagina={page}&tamanhoPagina={page_size}"
            resp = _api_get(url)
            if not resp:
                break
            items = resp.get("data", [])
            if not items:
                break
            all_items.extend(items)
            total_pages = resp.get("totalPaginas", 1)
            if page >= total_pages:
                break
            page += 1
            time.sleep(0.05)
        return all_items

    # ── Contratacoes (por semana × modalidade) ──
    print("  PNCP contratacoes:")
    total_contratacoes = 0
    for week_start, week_end in _week_ranges(anos):
        ds = week_start.strftime("%Y%m%d")
        de = week_end.strftime("%Y%m%d")
        if de <= last_contratacao:
            continue

        out_path = dest_contratacoes / f"contratacoes_{ds}_{de}.json"
        if out_path.exists() and out_path.stat().st_size > 10:
            continue

        week_records = []
        for mod in MODALIDADES:
            base_url = (f"{PNCP_API}/contratacoes/publicacao"
                        f"?dataInicial={ds}&dataFinal={de}"
                        f"&codigoModalidadeContratacao={mod}")
            items = _fetch_all_pages(base_url, PAGE_SIZE_CONTRATACOES)
            week_records.extend(items)

        if week_records:
            out_path.write_text(json.dumps(week_records, ensure_ascii=False), encoding="utf-8")
            total_contratacoes += len(week_records)
            print(f"    {ds}-{de}: {len(week_records)} contratacoes")

        # Update checkpoint
        ckpt["last_contratacao_date"] = de
        ckpt_file.write_text(json.dumps(ckpt))

    print(f"    Total contratacoes baixadas: {total_contratacoes}")

    # ── Contratos (por semana) ──
    print("  PNCP contratos:")
    total_contratos = 0
    for week_start, week_end in _week_ranges(anos):
        ds = week_start.strftime("%Y%m%d")
        de = week_end.strftime("%Y%m%d")
        if de <= last_contrato:
            continue

        out_path = dest_contratos / f"contratos_{ds}_{de}.json"
        if out_path.exists() and out_path.stat().st_size > 10:
            continue

        week_records = _fetch_all_pages(
            f"{PNCP_API}/contratos?dataInicial={ds}&dataFinal={de}",
            PAGE_SIZE_CONTRATOS,
        )

        if week_records:
            out_path.write_text(json.dumps(week_records, ensure_ascii=False), encoding="utf-8")
            total_contratos += len(week_records)
            print(f"    {ds}-{de}: {len(week_records)} contratos")

        # Update checkpoint
        ckpt["last_contrato_date"] = de
        ckpt_file.write_text(json.dumps(ckpt))

    print(f"    Total contratos baixados: {total_contratos}")
    print("    Itens/resultados: usar 'python -m etl.download_pncp' (API por contratacao)")


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

    PB_BASE = "https://dados.pb.gov.br:443/getcsv"
    today = date.today()
    current_ym = today.year * 100 + today.month

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
                if ano * 100 + mes > current_ym:
                    break
                fname = f"{file_prefix}_{ano}_{mes:02d}.csv"
                fpath = dest / fname
                if fpath.exists() and fpath.stat().st_size > 100:
                    continue
                url = f"{PB_BASE}?nome={api_nome}&exercicio={ano}&mes={mes}"
                try:
                    req = Request(url, headers={"User-Agent": _UA})
                    resp = urlopen(req, timeout=120)
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
            req = Request(url, headers={"User-Agent": _UA})
            resp = urlopen(req, timeout=120)
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
            req = Request(url, headers={"User-Agent": _UA})
            resp = urlopen(req, timeout=120)
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
        if anos and source in ("cpgf", "viagens", "tce_pb", "dados_pb", "emendas", "renuncias", "pncp"):
            fn(anos=anos)
        elif source == "siape" and anos:
            fn(meses=[f"{a}01" for a in anos])
        else:
            fn()

    print("\nDownloads concluidos.")


if __name__ == "__main__":
    run()
