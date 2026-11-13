#!/usr/bin/env python3
"""Gera deploy/nginx-datacenter-cidrs.conf a partir da base publica iptoasn.

Lista os prefixos IPv4 anunciados pelos ASNs de nuvem em ASNS_BLOQUEADOS
no formato do bloco `geo` do nginx (`<cidr> 1;`). O arquivo gerado e
incluido por deploy/nginx-bloqueio-bots.conf.

Criterio para entrar na lista: ASN de data center (nao de provedor
residencial/movel) cujo trafego observado no access.log eh de navegadores
automatizados — pagina + assets + beacon Umami com milhares de IPs
diferentes, nenhum usuario real. Ver docs/ops.md "Runbook: bloqueio de bots".

Uso (rodar localmente e commitar o resultado; a VM nao baixa nada):
    python deploy/gerar_bloqueio_datacenter.py

Fonte: https://iptoasn.com (licenca PDDL, atualizada de hora em hora).
"""
from __future__ import annotations

import gzip
import io
import ipaddress
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FONTE = "https://iptoasn.com/data/ip2asn-v4.tsv.gz"
SAIDA = Path(__file__).with_name("nginx-datacenter-cidrs.conf")

ASNS_BLOQUEADOS: dict[int, str] = {
    132203: "Tencent Cloud (CN)",
    45090: "Tencent Cloud (CN)",
    136907: "Huawei Cloud (HK)",
    55990: "Huawei Cloud (CN)",
    45102: "Alibaba Cloud",
    37963: "Alibaba Cloud (CN)",
}

# Rede minima esperada; abaixo disso a fonte provavelmente veio truncada.
MIN_PREFIXOS = 100


def baixar() -> bytes:
    req = urllib.request.Request(FONTE, headers={"User-Agent": "transparenciapb-blocklist"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def main() -> int:
    redes: dict[int, list[ipaddress.IPv4Network]] = {a: [] for a in ASNS_BLOQUEADOS}
    with gzip.open(io.BytesIO(baixar()), "rt") as fh:
        for linha in fh:
            inicio, fim, asn, *_ = linha.rstrip("\n").split("\t")
            asn_i = int(asn)
            if asn_i not in redes:
                continue
            redes[asn_i].extend(
                ipaddress.summarize_address_range(
                    ipaddress.IPv4Address(inicio), ipaddress.IPv4Address(fim)
                )
            )

    colapsadas = {a: list(ipaddress.collapse_addresses(v)) for a, v in redes.items()}
    total = sum(len(v) for v in colapsadas.values())
    if total < MIN_PREFIXOS:
        print(f"ERRO: so {total} prefixos encontrados — fonte truncada?", file=sys.stderr)
        return 1

    agora = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out = [
        "# GERADO por deploy/gerar_bloqueio_datacenter.py — NAO editar a mao.",
        f"# Fonte: {FONTE} ({agora})",
        "# Incluido dentro do bloco `geo $tpb_datacenter` de nginx-bloqueio-bots.conf.",
    ]
    for asn, nome in ASNS_BLOQUEADOS.items():
        out.append(f"\n# AS{asn} {nome}: {len(colapsadas[asn])} prefixos")
        out.extend(f"{rede} 1;" for rede in colapsadas[asn])
    SAIDA.write_text("\n".join(out) + "\n")
    print(f"{SAIDA.name}: {total} faixas de {len(ASNS_BLOQUEADOS)} ASNs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
