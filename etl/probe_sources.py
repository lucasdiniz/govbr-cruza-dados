"""Probes de conectividade/contrato para fontes remotas do ETL.

Uso:
  python -m etl.probe_sources
  python -m etl.probe_sources --strict
"""

import argparse
import base64
import socket
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

import requests


UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")
TRANSPARENCIA_BASE = "https://portaldatransparencia.gov.br/download-de-dados"
TSE_BASE = "https://cdn.tse.jus.br/estatistica/sead/odsele"
TCE_BASE = "https://download.tce.pb.gov.br/dados-abertos/dados-consolidados"
DADOS_PB_BASE = "https://dados.pb.gov.br/getcsv"
PGFN_BASE = "https://dadosabertos.pgfn.gov.br"
RFB_WEBDAV = "https://arquivos.receitafederal.gov.br/public.php/webdav"
RFB_AUTH = base64.b64encode(b"YggdBLfdninEJX9:").decode()


@dataclass
class ProbeResult:
    name: str
    ok: bool
    detail: str


@contextmanager
def _ipv4_only(enabled: bool):
    if not enabled:
        yield
        return
    orig = socket.getaddrinfo
    socket.getaddrinfo = lambda *a, **kw: [r for r in orig(*a, **kw) if r[0] == socket.AF_INET]
    try:
        yield
    finally:
        socket.getaddrinfo = orig


def _probe_stream(name, url, *, params=None, headers=None, ok_status=(200,), timeout=30, ipv4_only=False):
    merged_headers = {"User-Agent": UA}
    if headers:
        merged_headers.update(headers)

    try:
        with _ipv4_only(ipv4_only):
            with requests.get(
                url,
                params=params,
                headers=merged_headers,
                timeout=timeout,
                stream=True,
                allow_redirects=True,
            ) as resp:
                status = resp.status_code
                ctype = resp.headers.get("content-type", "?")
                if status not in ok_status:
                    body = resp.text[:160].replace("\n", " ")
                    return ProbeResult(name, False, f"http={status} ctype={ctype} body={body}")

                chunk = b""
                if status != 204:
                    chunk = next(resp.iter_content(chunk_size=256), b"")
                return ProbeResult(name, True, f"http={status} ctype={ctype} bytes={len(chunk)}")
    except Exception as e:
        return ProbeResult(name, False, f"{type(e).__name__}: {e}")


def _probe_pgfn():
    today = date.today()
    quarter = (today.month - 1) // 3 + 1
    for delta in range(4):
        q = quarter - delta
        y = today.year
        while q <= 0:
            q += 4
            y -= 1
        tri = f"{y}_trimestre_{q:02d}"
        url = f"{PGFN_BASE}/{tri}/Dados_abertos_Nao_Previdenciario.zip"
        result = _probe_stream(f"PGFN {tri}", url)
        if result.ok:
            return result
    return ProbeResult("PGFN", False, "nenhum trimestre recente respondeu com sucesso")


def _probe_sancoes():
    for offset in range(8):
        dt = (date.today() - timedelta(days=offset)).strftime("%Y%m%d")
        url = f"{TRANSPARENCIA_BASE}/ceis/{dt}"
        result = _probe_stream(f"Sancoes CEIS {dt}", url)
        if result.ok:
            return result
    return ProbeResult("Sancoes CEIS", False, "nenhuma data dos ultimos 7 dias respondeu com sucesso")


def _probe_siape():
    today = date.today()
    for offset in range(3):
        month = today.month - offset
        year = today.year
        if month <= 0:
            month += 12
            year -= 1
        ym = f"{year}{month:02d}"
        url = f"{TRANSPARENCIA_BASE}/servidores/{ym}_Servidores_SIAPE"
        result = _probe_stream(f"SIAPE {ym}", url)
        if result.ok:
            return result
    return ProbeResult("SIAPE", False, "nenhum dos 3 meses recentes respondeu com sucesso")


def _probe_rfb():
    today = date.today()
    tried = []
    for delta in range(4):
        d = today.replace(day=1) - timedelta(days=delta * 28)
        mes = f"{d.year}-{d.month:02d}"
        tried.append(mes)
        url = f"{RFB_WEBDAV}/{mes}/Cnaes.zip"
        result = _probe_stream(
            f"RFB {mes}",
            url,
            headers={"Authorization": f"Basic {RFB_AUTH}"},
            timeout=60,
            ipv4_only=True,
        )
        if result.ok:
            return result
    return ProbeResult("RFB", False, f"nenhum mes recente respondeu com sucesso: {', '.join(tried)}")


def iter_probes() -> Iterable[ProbeResult]:
    yield _probe_stream("Portal CPGF", f"{TRANSPARENCIA_BASE}/cpgf/202301")
    yield _probe_stream("Portal Viagens", f"{TRANSPARENCIA_BASE}/viagens/2024")
    yield _probe_stream("Portal Emendas", f"{TRANSPARENCIA_BASE}/emendas-parlamentares/2024")
    yield _probe_stream("Portal Renuncias", f"{TRANSPARENCIA_BASE}/renuncias/2024")
    yield _probe_stream("Portal Bolsa Familia", f"{TRANSPARENCIA_BASE}/novo-bolsa-familia/202402")
    yield _probe_siape()
    yield _probe_sancoes()
    yield _probe_rfb()
    yield _probe_pgfn()
    yield _probe_stream(
        "PNCP contratos",
        "https://pncp.gov.br/api/consulta/v1/contratos",
        params={"dataInicial": "20240101", "dataFinal": "20240107", "pagina": 1, "tamanhoPagina": 10},
        ok_status=(200,),
    )
    yield _probe_stream(
        "PNCP contratacoes",
        "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao",
        params={
            "dataInicial": "20240101",
            "dataFinal": "20240107",
            "codigoModalidadeContratacao": 1,
            "pagina": 1,
            "tamanhoPagina": 10,
        },
        ok_status=(200, 204),
    )
    yield _probe_stream(
        "TCE-PB despesas",
        f"{TCE_BASE}/despesas/despesas-2024.zip",
    )
    yield _probe_stream(
        "Dados PB empenho",
        DADOS_PB_BASE,
        params={"nome": "empenho_original", "exercicio": "2025", "mes": "01"},
    )
    yield _probe_stream(
        "BNDES operacoes",
        "https://dadosabertos.bndes.gov.br/dataset/10e21ad1-568e-45e5-a8af-43f2c05ef1a2/resource/6f56b78c-510f-44b6-8274-78a5b7e931f4/download/operacoes-financiamento-operacoes-nao-automaticas.csv",
    )
    yield _probe_stream(
        "TSE candidatos 2024",
        f"{TSE_BASE}/consulta_cand/consulta_cand_2024.zip",
    )
    yield _probe_stream(
        "TSE prestacao 2024",
        f"{TSE_BASE}/prestacao_contas/prestacao_de_contas_eleitorais_candidatos_2024.zip",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="retorna exit code 1 se algum probe falhar")
    args = parser.parse_args()

    print("=== Testing download sources ===")
    results = list(iter_probes())
    failed = 0
    for result in results:
        prefix = "OK" if result.ok else "FAIL"
        print(f"  {prefix}: {result.name} - {result.detail}")
        if not result.ok:
            failed += 1
    print(f"=== Done: {len(results) - failed}/{len(results)} probes OK ===")

    if failed and args.strict:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
