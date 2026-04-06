"""Fase 0: Download de todos os dados brutos das fontes oficiais.

Baixa dados do Portal da Transparencia (CGU), PNCP e Receita Federal.
Dados sao salvos em DATA_DIR (configurado no .env).

Uso:
  python -m etl.00_download              # Baixa tudo
  python -m etl.00_download --only cpgf   # Baixa so CPGF
  python -m etl.00_download --only viagens --anos 2020,2021
"""

import os
import csv
import shutil
import sys
import zipfile
from datetime import date, timedelta
from pathlib import Path
from urllib.request import Request, urlopen, urlretrieve
from urllib.error import URLError, HTTPError

from tqdm import tqdm

from etl.config import DATA_DIR
from etl.utils import EMENDAS_SIGNATURES, header_matches_signature, normalize_header_label

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
       "AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/131.0.0.0 Safari/537.36")
_TIMEOUT = 300  # 5 min per file
_TOR_AVAILABLE = None  # lazy-checked on first 403


# ── URLs e padroes de download ──────────────────────────────────

TRANSPARENCIA_BASE = "https://portaldatransparencia.gov.br/download-de-dados"
RFB_BASE = "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida"

CURRENT_YEAR = date.today().year
DEFAULT_ANOS = range(2020, CURRENT_YEAR + 1)


def _read_csv_header(filepath: Path, encoding: str = "latin1") -> list[str]:
    with open(filepath, "r", encoding=encoding, errors="replace", newline="") as f:
        reader = csv.reader(f, delimiter=";", quotechar='"')
        return [normalize_header_label(col) for col in (next(reader, []) or [])]


def _detect_emendas_role(filepath: Path) -> str | None:
    try:
        header = set(_read_csv_header(filepath))
    except OSError:
        return None

    for role, signature in EMENDAS_SIGNATURES.items():
        if header_matches_signature(header, signature):
            return role
    return None


def _check_tor():
    """Verifica se torsocks esta disponivel (lazy check, executado 1 vez)."""
    global _TOR_AVAILABLE
    if _TOR_AVAILABLE is None:
        import subprocess
        try:
            r = subprocess.run(["torsocks", "--version"],
                               capture_output=True, timeout=5)
            _TOR_AVAILABLE = r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _TOR_AVAILABLE = False
        if _TOR_AVAILABLE:
            # Verifica se o servico Tor esta rodando
            try:
                r = subprocess.run(["systemctl", "is-active", "tor"],
                                   capture_output=True, timeout=5)
                _TOR_AVAILABLE = r.stdout.strip() == b"active"
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass  # Pode nao ter systemctl (macOS etc), assume OK
        print(f"    [tor] {'disponivel' if _TOR_AVAILABLE else 'indisponivel'}")
    return _TOR_AVAILABLE


def _download_via_tor(url, dest_path, timeout=600):
    """Download via Tor SOCKS proxy (fallback para 403 de IPs datacenter)."""
    import subprocess
    print(f"    [tor] tentando via Tor: {dest_path.name}...")
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            ["torsocks", "wget", "-q", "--timeout=120",
             "--user-agent", _UA,
             "-O", str(dest_path), url],
            timeout=timeout, capture_output=True
        )
        if result.returncode == 0 and dest_path.exists() and dest_path.stat().st_size > 1000:
            size_mb = dest_path.stat().st_size / 1e6
            print(f"    [tor-ok] {dest_path.name} ({size_mb:.1f}MB)")
            return True
        else:
            print(f"    [tor-erro] {dest_path.name}: exit={result.returncode}")
            if dest_path.exists():
                dest_path.unlink()
            return False
    except subprocess.TimeoutExpired:
        print(f"    [tor-timeout] {dest_path.name}")
        if dest_path.exists():
            dest_path.unlink()
        return False


def _download(url, dest_path, timeout=_TIMEOUT):
    """Baixa arquivo com User-Agent e timeout. Pula se ja existe.
    Se receber 403 (IP bloqueado), tenta via Tor automaticamente.
    """
    if dest_path.exists() and dest_path.stat().st_size > 1000:
        print(f"    [pula] {dest_path.name} (ja existe)")
        return True

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"    [baixando] {dest_path.name}...")

    try:
        req = Request(url, headers={
            "User-Agent": _UA,
            "Accept": "text/html,application/xhtml+xml,*/*",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        })
        with urlopen(req, timeout=timeout) as resp:
            with open(dest_path, "wb") as f:
                shutil.copyfileobj(resp, f)
        size_mb = dest_path.stat().st_size / 1e6
        print(f"    [ok] {dest_path.name} ({size_mb:.1f}MB)")
        return True
    except HTTPError as e:
        if e.code == 403 and _check_tor():
            # IP provavelmente bloqueado (datacenter), tentar via Tor
            if dest_path.exists():
                dest_path.unlink()
            return _download_via_tor(url, dest_path)
        print(f"    [erro] {dest_path.name}: {e}")
        if dest_path.exists():
            dest_path.unlink()
        return False
    except URLError as e:
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
    """Emendas parlamentares + TransfereGov - Portal da Transparencia."""
    if anos is None:
        anos = DEFAULT_ANOS
    dest = DATA_DIR / "emendas"
    dest.mkdir(parents=True, exist_ok=True)

    print("  Emendas:")
    # Portal mudou: todos os anos redirecionam para o mesmo ZIP consolidado.
    # Tentar URL direta do CDN CGU primeiro, depois fallback por ano.
    cgu_url = "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/emendas-parlamentares/EmendasParlamentares.zip"
    zip_path = dest / "EmendasParlamentares.zip"
    downloaded = _download(cgu_url, zip_path)
    if downloaded:
        _unzip(zip_path, dest)
    else:
        # Fallback: tentar via portal (redireciona para o mesmo CDN)
        for ano in anos:
            url = f"{TRANSPARENCIA_BASE}/emendas-parlamentares/{ano}"
            zip_path_ano = dest / f"{ano}_EmendaParlamentar.zip"
            if _download(url, zip_path_ano):
                _unzip(zip_path_ano, dest)
                break  # todas as URLs redirecionam para o mesmo arquivo

    # TransfereGov (convenios e favorecidos) - mensal
    print("  TransfereGov:")
    today = date.today()
    for delta in range(6):  # tentar ultimos 6 meses
        d = today.replace(day=1)
        for _ in range(delta):
            d = (d - timedelta(days=1)).replace(day=1)
        ym = f"{d.year}{d.month:02d}"
        url = f"{TRANSPARENCIA_BASE}/transferencias/{ym}"
        zip_path = dest / f"{ym}_Transferencias.zip"
        if _download(url, zip_path):
            _unzip(zip_path, dest)
            print(f"    Usando transferencias de {ym}")
            break
        if zip_path.exists() and zip_path.stat().st_size < 100:
            zip_path.unlink(missing_ok=True)
        print(f"    {ym} nao disponivel...")

    role_targets = {
        "tesouro": dest / "emendas_tesouro.csv",
        "convenios": dest / "transferegov_convenios.csv",
        "favorecidos": dest / "transferegov_favorecidos.csv",
    }
    for csv_path in sorted(dest.glob("*.csv")):
        role = _detect_emendas_role(csv_path)
        target = role_targets.get(role)
        if not target or csv_path == target:
            continue
        shutil.copy2(csv_path, target)
        print(f"    [renomeia] {csv_path.name} -> {target.name}")


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

    # Renomear arquivos extraidos (RFB mudou formato dos nomes dentro dos ZIPs)
    # Formato novo: K3241.K03200Y0.D60314.EMPRECSV → Empresas0.csv
    _rfb_rename_map = {
        "EMPRECSV": "Empresas",
        "ESTABELE": "Estabelecimentos",
        "SOCIOCSV": "Socios",
    }
    for f in dest.iterdir():
        if f.suffix == ".zip" or f.name.endswith(".csv"):
            continue
        name = f.name
        # Arquivos numerados (Y0-Y9)
        for suffix, prefix in _rfb_rename_map.items():
            if name.endswith(suffix):
                # Extrair indice do Y0-Y9
                idx = name.split("Y")[-1].split(".")[0] if "Y" in name else "0"
                new_name = f"{prefix}{idx}.csv"
                new_path = dest / new_name
                if not new_path.exists():
                    f.rename(new_path)
                    print(f"    [renomeia] {name} → {new_name}")
                break
        # Dominio: F.K03200$Z.D60314.CNAECSV → Cnaes.csv etc.
        _rfb_domain_map = {
            "CNAECSV": "Cnaes.csv",
            "MOTICSV": "Motivos.csv",
            "MUNICCSV": "Municipios.csv",
            "NATJUCSV": "Naturezas.csv",
            "PAISCSV": "Paises.csv",
            "QUALSCSV": "Qualificacoes.csv",
        }
        for suffix, target in _rfb_domain_map.items():
            if name.endswith(suffix):
                new_path = dest / target
                if not new_path.exists():
                    f.rename(new_path)
                    print(f"    [renomeia] {name} → {target}")
                break
        # Simples: F.K03200$W.SIMPLES.CSV.D60314 → Simples.csv
        if "SIMPLES" in name:
            new_path = dest / "Simples.csv"
            if not new_path.exists():
                f.rename(new_path)
                print(f"    [renomeia] {name} → Simples.csv")


def download_pncp(anos=None):
    """PNCP - contratacoes e contratos via API Consulta.

    Contratacoes: por data × modalidade (13 modalidades), max 500/pagina.
    Contratos: por data, max 500/pagina.
    Salva JSONs compativeis com etl/04_pncp.py loader.
    """
    import json
    import time
    from etl.download_pncp import DEFAULT_WORKERS as PNCP_ITEM_WORKERS, download_itens

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

    # Session com connection pooling (reutiliza TCP+SSL, ~10x mais rapido)
    import requests as _requests
    _session = _requests.Session()
    _session.headers.update({
        "User-Agent": _UA,
        "Accept": "application/json",
    })
    _adapter = _requests.adapters.HTTPAdapter(
        pool_connections=10, pool_maxsize=20,
        max_retries=_requests.adapters.Retry(total=0),  # retry manual
    )
    _session.mount("https://", _adapter)

    def _api_get(url, retries=3):
        """GET com requests.Session (connection pooling).
        Retorna dict (sucesso), empty dict (204/sem dados), ou None (erro).
        """
        for attempt in range(retries):
            try:
                resp = _session.get(url, timeout=20)
                if resp.status_code == 204 or not resp.content:
                    return {"data": [], "totalPaginas": 0, "totalRegistros": 0}
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                wait = min(2 ** (attempt + 1), 10)  # 2, 4, 8s
                err_type = type(e).__name__
                if attempt < retries - 1:
                    print(f"    [retry {attempt+1}/{retries}] {err_type}: {e} (wait {wait}s)")
                    time.sleep(wait)
                else:
                    print(f"    [erro] {err_type}: {e}")
                    print(f"    [url ] {url}")
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
        """Pagina por todos os resultados de uma URL base.
        Returns None if the first page fails (API error), [] if no results.
        """
        all_items = []
        page = 1
        while page <= max_pages:
            url = f"{base_url}&pagina={page}&tamanhoPagina={page_size}"
            resp = _api_get(url)
            if not resp:
                if page == 1:
                    return None  # API error on first page
                break
            items = resp.get("data", [])
            if not items:
                break
            all_items.extend(items)
            total_pages = resp.get("totalPaginas", 1)
            if page >= total_pages:
                break
            page += 1
            time.sleep(0.2)
        return all_items

    def _fetch_week_contratacoes(ds, de):
        """Baixa contratacoes de todas as modalidades para uma semana.
        Returns (records_list, failed_count).
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        records = []
        failed = 0

        def _fetch_mod(mod):
            base_url = (f"{PNCP_API}/contratacoes/publicacao"
                        f"?dataInicial={ds}&dataFinal={de}"
                        f"&codigoModalidadeContratacao={mod}")
            return _fetch_all_pages(base_url, PAGE_SIZE_CONTRATACOES)

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(_fetch_mod, m): m for m in MODALIDADES}
            for fut in as_completed(futures):
                items = fut.result()
                if items is None:
                    failed += 1
                elif items:
                    records.extend(items)

        return records, failed

    def _download_one_week_contratacoes(week_start, week_end):
        """Baixa e salva contratacoes de uma semana. Thread-safe.
        Returns (ds, n_records, failed_mods).
        """
        ds = week_start.strftime("%Y%m%d")
        de = week_end.strftime("%Y%m%d")
        out_path = dest_contratacoes / f"contratacoes_{ds}_{de}.json"
        if out_path.exists() and out_path.stat().st_size > 10:
            return ds, -1, 0  # -1 = skipped

        records, failed = _fetch_week_contratacoes(ds, de)
        if failed > 0:
            return ds, 0, failed
        if records:
            out_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        return ds, len(records), 0

    def _download_one_week_contratos(week_start, week_end):
        """Baixa e salva contratos de uma semana. Thread-safe.
        Returns (ds, n_records, failed).
        """
        ds = week_start.strftime("%Y%m%d")
        de = week_end.strftime("%Y%m%d")
        out_path = dest_contratos / f"contratos_{ds}_{de}.json"
        if out_path.exists() and out_path.stat().st_size > 10:
            return ds, -1, False

        records = _fetch_all_pages(
            f"{PNCP_API}/contratos?dataInicial={ds}&dataFinal={de}",
            PAGE_SIZE_CONTRATOS,
        )
        if records is None:
            return ds, 0, True
        if records:
            out_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
        return ds, len(records), False

    def _collect_contratacoes_for_itens():
        contratacoes = {}
        for filepath in sorted(dest_contratacoes.glob("*.json")):
            if filepath.name.startswith("_"):
                continue
            try:
                raw = json.loads(filepath.read_text(encoding="utf-8"))
            except Exception:
                continue
            items = raw if isinstance(raw, list) else raw.get("data", [])
            for item in items or []:
                nc = str(item.get("numeroControlePNCP") or "").strip()
                orgao = item.get("orgaoEntidade") or {}
                cnpj = str(orgao.get("cnpj") or "").strip()
                ano = item.get("anoCompra")
                seq = item.get("sequencialCompra")
                if not (nc and cnpj and ano is not None and seq is not None):
                    continue
                contratacoes[nc] = (cnpj, int(ano), int(seq), nc)
        return list(contratacoes.values())

    PARALLEL_WEEKS = 3  # semanas processadas em paralelo

    # ── Contratacoes (paralelo por semana, 4 threads por semana para modalidades) ──
    from concurrent.futures import ThreadPoolExecutor, as_completed
    print("  PNCP contratacoes:")
    total_contratacoes = 0
    consecutive_errors = 0
    failed_contratacao_weeks = []
    MAX_CONSECUTIVE_ERRORS = 20

    weeks_to_process = []
    for week_start, week_end in _week_ranges(anos):
        de = week_end.strftime("%Y%m%d")
        if de <= last_contratacao:
            continue
        weeks_to_process.append((week_start, week_end))

    # Processar em lotes de PARALLEL_WEEKS
    for batch_start in range(0, len(weeks_to_process), PARALLEL_WEEKS):
        batch = weeks_to_process[batch_start:batch_start + PARALLEL_WEEKS]

        with ThreadPoolExecutor(max_workers=PARALLEL_WEEKS) as pool:
            futures = {
                pool.submit(_download_one_week_contratacoes, ws, we): (ws, we)
                for ws, we in batch
            }
            for fut in as_completed(futures):
                ds, n_records, failed_mods = fut.result()
                if n_records == -1:
                    consecutive_errors = 0
                    continue  # skipped
                if failed_mods > 0:
                    consecutive_errors += 1
                    failed_contratacao_weeks.append(ds)
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        break
                    print(f"    {ds}: ERRO em {failed_mods}/{len(MODALIDADES)} modalidades")
                    continue
                consecutive_errors = 0
                if n_records > 0:
                    total_contratacoes += n_records
                    print(f"    {ds}: {n_records} contratacoes")

        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            print(f"    [abort] {MAX_CONSECUTIVE_ERRORS} semanas consecutivas com erro")
            break

        # Advance checkpoint to end of batch
        last_de = max(we.strftime("%Y%m%d") for _, we in batch)
        ckpt["last_contratacao_date"] = last_de
        ckpt_file.write_text(json.dumps(ckpt))

    ckpt["failed_contratacao_weeks"] = failed_contratacao_weeks
    ckpt_file.write_text(json.dumps(ckpt, indent=2))
    print(f"    Total contratacoes baixadas: {total_contratacoes}")
    if failed_contratacao_weeks:
        print(f"    ATENCAO: {len(failed_contratacao_weeks)} semanas com falha")

    # ── Contratos (paralelo por semana) ──
    print("  PNCP contratos:")
    total_contratos = 0
    consecutive_errors = 0
    failed_contrato_weeks = []

    weeks_to_process = []
    for week_start, week_end in _week_ranges(anos):
        de = week_end.strftime("%Y%m%d")
        if de <= last_contrato:
            continue
        weeks_to_process.append((week_start, week_end))

    for batch_start in range(0, len(weeks_to_process), PARALLEL_WEEKS):
        batch = weeks_to_process[batch_start:batch_start + PARALLEL_WEEKS]

        with ThreadPoolExecutor(max_workers=PARALLEL_WEEKS) as pool:
            futures = {
                pool.submit(_download_one_week_contratos, ws, we): (ws, we)
                for ws, we in batch
            }
            for fut in as_completed(futures):
                ds, n_records, failed = fut.result()
                if n_records == -1:
                    consecutive_errors = 0
                    continue
                if failed:
                    consecutive_errors += 1
                    failed_contrato_weeks.append(ds)
                    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                        break
                    print(f"    {ds}: ERRO, sera retentado")
                    continue
                consecutive_errors = 0
                if n_records > 0:
                    total_contratos += n_records
                    print(f"    {ds}: {n_records} contratos")

        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            print(f"    [abort] {MAX_CONSECUTIVE_ERRORS} semanas consecutivas com erro")
            break

        last_de = max(we.strftime("%Y%m%d") for _, we in batch)
        ckpt["last_contrato_date"] = last_de
        ckpt_file.write_text(json.dumps(ckpt))

    ckpt["failed_contrato_weeks"] = failed_contrato_weeks
    ckpt_file.write_text(json.dumps(ckpt, indent=2))
    print(f"    Total contratos baixados: {total_contratos}")
    if failed_contrato_weeks:
        print(f"    ATENCAO: {len(failed_contrato_weeks)} semanas com falha")

    contratacoes_para_itens = _collect_contratacoes_for_itens()
    if contratacoes_para_itens:
        print("  PNCP itens:")
        download_itens(contratacoes_para_itens, workers=PNCP_ITEM_WORKERS)
    else:
        print("  PNCP itens: AVISO: nenhuma contratacao elegivel encontrada para download")


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


def download_tse(anos=None):
    """TSE - candidatos, bens declarados e prestacao de contas por ano."""
    if anos is None:
        anos = [2020, 2022, 2024]
    dest = DATA_DIR / "tse"
    dest.mkdir(parents=True, exist_ok=True)

    tse_base = "https://cdn.tse.jus.br/estatistica/sead/odsele"
    anos_suportados = {2020, 2022, 2024}

    print("  TSE:")
    for ano in sorted(set(int(a) for a in anos)):
        if ano not in anos_suportados:
            print(f"    [aviso] ano {ano} nao mapeado para download do TSE, pulando")
            continue

        arquivos = [
            (f"{tse_base}/consulta_cand/consulta_cand_{ano}.zip",
             dest / f"consulta_cand_{ano}.zip"),
            (f"{tse_base}/bem_candidato/bem_candidato_{ano}.zip",
             dest / f"bem_candidato_{ano}.zip"),
        ]
        if ano in (2022, 2024):
            arquivos.append(
                (f"{tse_base}/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_{ano}.zip",
                 dest / f"prestacao_contas_candidatos_{ano}.zip")
            )

        for url, zip_path in arquivos:
            _download(url, zip_path, timeout=1800)


def download_bolsa_familia(anos=None):
    """Novo Bolsa Familia (mensal) - Portal da Transparencia."""
    if anos is None:
        anos = range(2023, CURRENT_YEAR + 1)
    dest = DATA_DIR / "bolsa_familia"
    dest.mkdir(parents=True, exist_ok=True)

    current_ym = int(f"{date.today().year}{date.today().month:02d}")
    start_ym = 202303

    print("  Novo Bolsa Familia:")
    for ano in anos:
        for mes in range(1, 13):
            ym = int(f"{ano}{mes:02d}")
            if ym < start_ym:
                continue
            if ym > current_ym:
                break
            url = f"{TRANSPARENCIA_BASE}/novo-bolsa-familia/{ym}"
            zip_path = dest / f"novo_bf_{ym}.zip"
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
    if today.month == 1:
        current_ym = (today.year - 1) * 100 + 12
    else:
        current_ym = today.year * 100 + (today.month - 1)

    # Datasets mensais: (nome_api, prefixo_arquivo)
    monthly = [
        ("pagamento", "pagamento"),
        ("empenho_original", "empenho"),
        ("pagamentos_gestao_pactuada_saude", "saude"),
        ("pagamento_anulacao", "pagamento_anulacao"),
        ("liquidacaodespesa", "liquidacaodespesa"),
        ("liquidacaodespesadescontos", "liquidacaodespesadescontos"),
        ("empenho_anulacao", "empenho_anulacao"),
        ("empenho_suplementacao", "empenho_suplementacao"),
        ("dotacao", "dotacao"),
        ("liquidacao", "liquidacao_cge"),
        ("aditivos_contrato", "aditivos_contrato"),
        ("aditivos_convenio", "aditivos_convenio"),
        ("Diarias", "diarias"),  # Case-sensitive! D maiúsculo
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

    # Datasets anuais (sem mes): (nome_api, prefixo)
    yearly = [
        ("convenios", "convenios"),
        ("unidade_gestora_dadospb", "unidade_gestora"),
    ]
    for api_nome, file_prefix in yearly:
        for ano in anos:
            fname = f"{file_prefix}_{ano}.csv"
            fpath = dest / fname
            if fpath.exists() and fpath.stat().st_size > 100:
                continue
            url = f"{PB_BASE}?nome={api_nome}&exercicio={ano}"
            if api_nome == "convenios":
                url += "&mes_inicio=1&mes_fim=12"
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
    "tse": download_tse,
    "bolsa_familia": download_bolsa_familia,
    "tce_pb": download_tce_pb,
    "dados_pb": download_dados_pb,
    "complementar": download_complementar,
}


def _validate_downloads_legacy():
    """Valida que todos os dados criticos foram baixados.

    Retorna lista de erros (vazia = tudo OK).
    """
    errors = []

    def _check(desc, pattern_or_path, min_count=1):
        if isinstance(pattern_or_path, Path):
            if not pattern_or_path.exists() or pattern_or_path.stat().st_size < 100:
                errors.append(f"{desc}: arquivo nao encontrado ({pattern_or_path})")
        else:
            found = list(DATA_DIR.glob(pattern_or_path))
            if len(found) < min_count:
                errors.append(f"{desc}: esperado >={min_count} arquivos para '{pattern_or_path}', encontrado {len(found)}")

    # RFB (essencial — sem isso nao tem CNPJ)
    _check("RFB Empresas", "rfb/Empresas*.csv", min_count=1)
    _check("RFB Estabelecimentos", "rfb/Estabelecimentos*.csv", min_count=1)
    _check("RFB Socios", "rfb/Socios*.csv", min_count=1)
    _check("RFB Simples", "rfb/Simples.csv")
    _check("RFB Dominio", "rfb/Cnaes.csv")

    # PNCP
    _check("PNCP contratacoes", "pncp/*.json", min_count=10)
    _check("PNCP contratos", "pncp_contratos/*.json", min_count=10)
    _check("PNCP itens", "pncp_itens/*.json", min_count=1)

    # Emendas
    _check("Emendas Tesouro", "emendas/emendas_tesouro.csv")
    _check("TransfereGov convenios", "emendas/transferegov_convenios.csv")

    # CPGF
    _check("CPGF", "cpgf/*.csv", min_count=5)

    # PGFN
    _check("PGFN", "pgfn/pgfn_*.csv", min_count=1)

    # Sancoes
    for nome in ("ceis", "cnep", "ceaf", "acordos"):
        _check(f"Sancoes {nome}", f"sancoes/{nome}*.csv", min_count=1)

    # SIAPE
    _check("SIAPE Cadastro", "siape/*_Cadastro.csv", min_count=1)
    _check("SIAPE Remuneracao", "siape/*_Remuneracao.csv", min_count=1)

    # Viagens
    _check("Viagens", "viagens/*.csv", min_count=1)

    # TCE-PB
    _check("TCE-PB despesas", "tce_pb/despesas-*.csv", min_count=1)
    _check("TCE-PB servidores", "tce_pb/servidores-*.csv", min_count=1)

    # Dados PB
    _check("Dados PB pagamento", "dados_pb/pagamento-*.csv", min_count=5)
    _check("Dados PB empenho", "dados_pb/empenho-*.csv", min_count=5)

    # BNDES
    _check("BNDES", "bndes/operacoes-financiamento-*.csv", min_count=1)

    return errors


def validate_downloads():
    """Valida que todos os dados criticos foram baixados."""
    errors = []

    def _glob_ok(pattern):
        return [
            path for path in DATA_DIR.glob(pattern)
            if path.exists() and (path.is_dir() or path.stat().st_size >= 100)
        ]

    def _check(desc, pattern_or_path, min_count=1):
        if isinstance(pattern_or_path, Path):
            if not pattern_or_path.exists() or pattern_or_path.stat().st_size < 100:
                errors.append(f"{desc}: arquivo nao encontrado ({pattern_or_path})")
        else:
            found = _glob_ok(pattern_or_path)
            if len(found) < min_count:
                errors.append(f"{desc}: esperado >={min_count} arquivos para '{pattern_or_path}', encontrado {len(found)}")

    def _check_any(desc, patterns, min_count=1):
        found = []
        for pattern in patterns:
            found.extend(_glob_ok(pattern))
        if len(found) < min_count:
            joined = "' ou '".join(patterns)
            errors.append(f"{desc}: esperado >={min_count} arquivos para '{joined}', encontrado {len(found)}")

    _check("RFB Empresas", "rfb/Empresas*.csv", min_count=1)
    _check("RFB Estabelecimentos", "rfb/Estabelecimentos*.csv", min_count=1)
    _check("RFB Socios", "rfb/Socios*.csv", min_count=1)
    _check("RFB Simples", "rfb/Simples.csv")
    _check("RFB Dominio", "rfb/Cnaes.csv")

    _check("PNCP contratacoes", "pncp/*.json", min_count=10)
    _check("PNCP contratos", "pncp_contratos/*.json", min_count=10)

    _check_any("Emendas Tesouro", ["emendas/emendas_tesouro.csv", "emendas/*emendas*tesouro*.csv", "emendas_tesouro.csv", "*emendas*tesouro*.csv"])
    _check_any("TransfereGov convenios", ["emendas/transferegov_convenios.csv", "emendas/*transferegov*convenio*.csv", "transferegov_convenios.csv", "*convenio*.csv"])
    _check_any("TransfereGov favorecidos", ["emendas/transferegov_favorecidos.csv", "emendas/*transferegov*favorecid*.csv", "transferegov_favorecidos.csv", "*favorecid*.csv"])

    _check("CPGF", "cpgf/*.csv", min_count=5)
    _check_any("PGFN", ["pgfn/arquivo_lai_*.csv", "pgfn/pgfn_*.csv", "pgfn_*.csv"], min_count=1)

    _check("Sancoes CEIS", "sancoes/*_CEIS.csv", min_count=1)
    _check("Sancoes CNEP", "sancoes/*_CNEP.csv", min_count=1)
    _check("Sancoes CEAF/Expulsoes", "sancoes/*_Expulsoes.csv", min_count=1)
    _check("Sancoes Acordos", "sancoes/*_Acordos.csv", min_count=1)

    _check("SIAPE Cadastro", "siape/*_Cadastro.csv", min_count=1)
    _check("SIAPE Remuneracao", "siape/*_Remuneracao.csv", min_count=1)
    _check("Viagens", "viagens/*.csv", min_count=1)

    _check("TCE-PB despesas", "tce_pb/despesas-*.csv", min_count=1)
    _check("TCE-PB servidores", "tce_pb/servidores-*.csv", min_count=1)

    _check("Dados PB pagamento", "dados_pb/pagamento_*.csv", min_count=5)
    _check("Dados PB empenho", "dados_pb/empenho_*.csv", min_count=5)

    for ano in (2020, 2022, 2024):
        _check_any(
            f"TSE candidatos {ano}",
            [f"tse/consulta_cand_{ano}.zip", f"tse/cand_{ano}/consulta_cand_{ano}_*.csv"],
            min_count=1,
        )
        _check_any(
            f"TSE bens {ano}",
            [f"tse/bem_candidato_{ano}.zip", f"tse/bens_{ano}/bem_candidato_{ano}_*.csv"],
            min_count=1,
        )
    for ano in (2022, 2024):
        _check_any(
            f"TSE prestacao receitas {ano}",
            [f"tse/prestacao_contas_candidatos_{ano}.zip", f"tse/prestacao_{ano}/receitas_candidatos_{ano}_*.csv"],
            min_count=1,
        )
        _check_any(
            f"TSE prestacao despesas {ano}",
            [f"tse/prestacao_contas_candidatos_{ano}.zip", f"tse/prestacao_{ano}/despesas_pagas_candidatos_{ano}_*.csv"],
            min_count=1,
        )

    _check("Bolsa Familia", "bolsa_familia/*_NovoBolsaFamilia.csv", min_count=1)
    _check_any("BNDES", ["bndes/operacoes-financiamento-*.csv", "bndes.csv"], min_count=1)

    return errors


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

    download_errors = []
    for source in sources:
        if source not in DOWNLOADERS:
            print(f"  AVISO: fonte '{source}' desconhecida, pulando.")
            continue

        fn = DOWNLOADERS[source]
        try:
            if anos and source in ("cpgf", "viagens", "tce_pb", "dados_pb", "emendas", "renuncias", "pncp", "tse", "bolsa_familia"):
                fn(anos=anos)
            elif source == "siape" and anos:
                fn(meses=[f"{a}01" for a in anos])
            else:
                fn()
        except Exception as e:
            print(f"  ERRO no download de {source}: {e}")
            download_errors.append((source, str(e)))

    if download_errors:
        print(f"\n{'='*60}")
        print(f"FALHA: {len(download_errors)} fonte(s) falharam no download:")
        for src, err in download_errors:
            print(f"  - {src}: {err}")
        print(f"{'='*60}")
        raise RuntimeError(f"Download falhou para: {', '.join(s for s, _ in download_errors)}")

    # Validacao pos-download (apenas quando rodando tudo, nao com --only)
    if not only:
        print("\n  Validando downloads...")
        validation_errors = validate_downloads()
        if validation_errors:
            print(f"\n{'='*60}")
            print(f"AVISO: {len(validation_errors)} fonte(s) incompletas (ETL continuara com dados disponiveis):")
            for err in validation_errors:
                print(f"  - {err}")
            print(f"{'='*60}")
        else:
            print("  Todos os downloads validados com sucesso.")

    print("\nDownloads concluidos.")


if __name__ == "__main__":
    run()
