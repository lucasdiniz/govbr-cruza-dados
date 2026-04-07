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
PNCP_CONSULTA_BASE = "https://pncp.gov.br/api/consulta/v1"
PNCP_ITEM_BASE = "https://pncp.gov.br/api/pncp/v1"
BNDES_BASE = "https://dadosabertos.bndes.gov.br/dataset/10e21ad1-568e-45e5-a8af-43f2c05ef1a2/resource"


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



def _json_get(url, *, params=None, headers=None, ok_status=(200,), timeout=30):
    merged_headers = {"User-Agent": UA, "Accept": "application/json"}
    if headers:
        merged_headers.update(headers)

    try:
        resp = requests.get(
            url,
            params=params,
            headers=merged_headers,
            timeout=timeout,
            allow_redirects=True,
        )
    except Exception as e:
        return ProbeResult(url, False, f"{type(e).__name__}: {e}"), None

    ctype = resp.headers.get("content-type", "?")
    if resp.status_code not in ok_status:
        body = resp.text[:160].replace("\n", " ")
        return ProbeResult(url, False, f"http={resp.status_code} ctype={ctype} body={body}"), None

    try:
        data = resp.json() if resp.content else None
    except ValueError:
        return ProbeResult(url, False, f"http={resp.status_code} ctype={ctype} invalid-json"), None

    return ProbeResult(url, True, f"http={resp.status_code} ctype={ctype}"), data



def _recent_months(limit):
    today = date.today().replace(day=1)
    for offset in range(limit):
        year = today.year
        month = today.month - offset
        while month <= 0:
            month += 12
            year -= 1
        yield f"{year}{month:02d}"



def _recent_week_ranges(limit):
    end = date.today()
    for offset in range(limit):
        week_end = end - timedelta(days=offset * 7)
        week_start = week_end - timedelta(days=6)
        yield week_start.strftime("%Y%m%d"), week_end.strftime("%Y%m%d")



def _probe_recent_path(name_prefix, url_builder, values, **kwargs):
    last = None
    for value in values:
        result = _probe_stream(f"{name_prefix} {value}", url_builder(value), **kwargs)
        if result.ok:
            return result
        last = result
    return last or ProbeResult(name_prefix, False, "nenhuma tentativa executada")



def _probe_pgfn_file(filename):
    today = date.today()
    quarter = (today.month - 1) // 3 + 1
    last = None
    for delta in range(4):
        q = quarter - delta
        y = today.year
        while q <= 0:
            q += 4
            y -= 1
        tri = f"{y}_trimestre_{q:02d}"
        url = f"{PGFN_BASE}/{tri}/{filename}"
        result = _probe_stream(f"PGFN {filename} {tri}", url)
        if result.ok:
            return result
        last = result
    return last or ProbeResult(f"PGFN {filename}", False, "nenhum trimestre recente respondeu com sucesso")



def _probe_rfb():
    today = date.today()
    tried = []
    last = None
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
        last = result
    return last or ProbeResult("RFB", False, f"nenhum mes recente respondeu com sucesso: {', '.join(tried)}")



def _fetch_pncp_sample():
    last_detail = "nenhuma janela com contratacoes retornou dados"
    for data_inicial, data_final in _recent_week_ranges(16):
        result, payload = _json_get(
            f"{PNCP_CONSULTA_BASE}/contratacoes/publicacao",
            params={
                "dataInicial": data_inicial,
                "dataFinal": data_final,
                "codigoModalidadeContratacao": 1,
                "pagina": 1,
                "tamanhoPagina": 10,
            },
            ok_status=(200, 204),
        )
        if not result.ok:
            last_detail = result.detail
            continue
        data = payload.get("data", []) if isinstance(payload, dict) else []
        if not data:
            last_detail = f"janela {data_inicial}-{data_final} sem contratacoes"
            continue
        for item in data:
            orgao = item.get("orgaoEntidade") or {}
            cnpj = str(orgao.get("cnpj") or "").strip()
            ano = item.get("anoCompra")
            seq = item.get("sequencialCompra")
            if cnpj and ano is not None and seq is not None:
                return (cnpj, ano, seq), f"janela {data_inicial}-{data_final}"
        last_detail = f"janela {data_inicial}-{data_final} sem cnpj/ano/seq validos"
    return None, last_detail



def _probe_pncp_itens():
    sample, detail = _fetch_pncp_sample()
    if not sample:
        return ProbeResult("PNCP itens", False, detail)
    cnpj, ano, seq = sample
    return _probe_stream(
        "PNCP itens",
        f"{PNCP_ITEM_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/itens",
        headers={"Accept": "application/json"},
        ok_status=(200,),
    )



def _probe_pncp_resultados():
    sample, detail = _fetch_pncp_sample()
    if not sample:
        return ProbeResult("PNCP resultados", False, detail)

    cnpj, ano, seq = sample
    result, payload = _json_get(
        f"{PNCP_ITEM_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/itens",
        ok_status=(200,),
    )
    if not result.ok:
        return ProbeResult("PNCP resultados", False, result.detail)

    itens = payload if isinstance(payload, list) else []
    for item in itens:
        num_item = item.get("numeroItem")
        if not num_item or not item.get("temResultado"):
            continue
        return _probe_stream(
            "PNCP resultados",
            f"{PNCP_ITEM_BASE}/orgaos/{cnpj}/compras/{ano}/{seq}/itens/{num_item}/resultados",
            headers={"Accept": "application/json"},
            ok_status=(200,),
        )

    return ProbeResult("PNCP resultados", False, "nenhum item recente com resultados disponiveis")



def iter_probes() -> Iterable[ProbeResult]:
    yield _probe_stream("Portal CPGF", f"{TRANSPARENCIA_BASE}/cpgf/202301")
    yield _probe_stream("Portal Viagens", f"{TRANSPARENCIA_BASE}/viagens/2024")
    yield _probe_recent_path(
        "Portal SIAPE",
        lambda ym: f"{TRANSPARENCIA_BASE}/servidores/{ym}_Servidores_SIAPE",
        _recent_months(3),
    )
    for dataset in ("ceis", "cnep", "ceaf", "acordos-leniencia"):
        yield _probe_recent_path(
            f"Portal Sancoes {dataset}",
            lambda dt, dataset=dataset: f"{TRANSPARENCIA_BASE}/{dataset}/{dt}",
            ((date.today() - timedelta(days=offset)).strftime("%Y%m%d") for offset in range(8)),
        )
    yield _probe_stream(
        "Portal Emendas CDN",
        "https://dadosabertos-download.cgu.gov.br/PortalDaTransparencia/saida/emendas-parlamentares/EmendasParlamentares.zip",
    )
    yield _probe_recent_path(
        "Portal Transferencias",
        lambda ym: f"{TRANSPARENCIA_BASE}/transferencias/{ym}",
        _recent_months(6),
    )
    for filename in (
        "Dados_abertos_Nao_Previdenciario.zip",
        "Dados_abertos_Previdenciario.zip",
        "Dados_abertos_FGTS.zip",
    ):
        yield _probe_pgfn_file(filename)
    yield _probe_rfb()
    yield _probe_stream(
        "PNCP contratos",
        f"{PNCP_CONSULTA_BASE}/contratos",
        params={"dataInicial": "20240101", "dataFinal": "20240107", "pagina": 1, "tamanhoPagina": 10},
        ok_status=(200,),
    )
    yield _probe_stream(
        "PNCP contratacoes",
        f"{PNCP_CONSULTA_BASE}/contratacoes/publicacao",
        params={
            "dataInicial": "20240101",
            "dataFinal": "20240107",
            "codigoModalidadeContratacao": 1,
            "pagina": 1,
            "tamanhoPagina": 10,
        },
        ok_status=(200, 204),
    )
    yield _probe_pncp_itens()
    yield _probe_pncp_resultados()
    yield _probe_stream("Portal Renuncias", f"{TRANSPARENCIA_BASE}/renuncias/2024")
    yield _probe_stream("Portal Bolsa Familia", f"{TRANSPARENCIA_BASE}/novo-bolsa-familia/202402")
    for category in ("despesas", "servidores", "licitacoes", "receitas"):
        yield _probe_stream(
            f"TCE-PB {category}",
            f"{TCE_BASE}/{category}/{category}-2024.zip",
        )
    yield _probe_stream(
        "Dados PB pagamento",
        DADOS_PB_BASE,
        params={"nome": "pagamento", "exercicio": "2025", "mes": "01"},
    )
    yield _probe_stream(
        "Dados PB empenho",
        DADOS_PB_BASE,
        params={"nome": "empenho_original", "exercicio": "2025", "mes": "01"},
    )
    yield _probe_stream(
        "Dados PB contratos",
        DADOS_PB_BASE,
        params={"nome": "contratos", "exercicio": "2024"},
    )
    yield _probe_stream(
        "Dados PB convenios",
        DADOS_PB_BASE,
        params={"nome": "convenios", "exercicio": "2024", "mes_inicio": "1", "mes_fim": "12"},
    )
    yield _probe_stream(
        "BNDES nao automaticas",
        f"{BNDES_BASE}/6f56b78c-510f-44b6-8274-78a5b7e931f4/download/operacoes-financiamento-operacoes-nao-automaticas.csv",
    )
    yield _probe_stream(
        "BNDES automaticas",
        f"{BNDES_BASE}/612faa0b-b6be-4b2c-9317-da5dc2c0b901/download/operacoes-financiamento-operacoes-indiretas-automaticas.csv",
    )
    yield _probe_stream(
        "TSE candidatos 2024",
        f"{TSE_BASE}/consulta_cand/consulta_cand_2024.zip",
    )
    yield _probe_stream(
        "TSE bens 2024",
        f"{TSE_BASE}/bem_candidato/bem_candidato_2024.zip",
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
