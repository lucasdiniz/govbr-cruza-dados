"""Submete URLs do sitemap ao IndexNow (Bing/Yandex/Yahoo/Seznam/Naver).

IndexNow eh um protocolo aberto pra notificacao de mudancas de URL. Bing
costuma indexar em horas (vs. semanas pelo crawler). NAO substitui o
Google Search Console (Google ainda nao adotou IndexNow).

Uso:
    python -m web.indexnow_submit [--limit N] [--dry-run]

Requer:
    INDEXNOW_KEY        - chave 8-128 chars (gerar com secrets.token_urlsafe).
    SITE_URL            - origem completa (default: https://transparenciapb.org).

Como gerar a chave:
    python -c "import secrets; print(secrets.token_urlsafe(32))"

Apos setar INDEXNOW_KEY no .env, a rota /<key>.txt comeca a servir o
arquivo de verificacao automaticamente. Confirme que esta acessivel:
    curl https://transparenciapb.org/<sua-key>.txt

Esse script reusa a logica do sitemap (web.routes.seo._build_sitemap_xml)
pra extrair URLs e submete em batch ao endpoint do IndexNow.

Recomendamos rodar:
    1. Apos cada deploy de codigo (via deploy.yml ou systemd post-start)
    2. Apos cada refresh de dados (warm cache concluido)
"""
from __future__ import annotations

import argparse
import html
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

# Carrega .env explicitamente: bash `source .env` no deploy.yml define vars
# de shell mas NAO exporta pra subprocesso, entao `os.environ` ficaria vazio.
# Outras entradas (etl.config) ja fazem isso; replicamos aqui pra script
# standalone funcionar igual local e em CI.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("indexnow")


INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow"
# IndexNow aceita ate 10.000 URLs por POST. Mantemos 500 por seguranca
# (evita timeout em caso de erro do endpoint).
BATCH_SIZE = 500


def _extract_urls_from_sitemap(xml_text: str) -> list[str]:
    """Parse simples (regex) das tags <loc>. Evita dependencia de XML
    parser externo; sitemap eh pequeno e bem formado.

    IMPORTANTE: o conteudo eh entity-encoded (xml.sax.saxutils.escape em
    seo.py:_build_sitemap_xml). Hoje URLs sao /cidade/<slug> e nao tem
    `&`/`<`/`>`, mas se algum dia voltarmos a indexar URLs com query
    string, html.unescape garante que `&amp;` vire `&` antes de submeter
    pro IndexNow (que rejeitaria a URL malformada silenciosamente).
    """
    return [html.unescape(loc) for loc in re.findall(r"<loc>([^<]+)</loc>", xml_text)]


def _submit_batch(host: str, key: str, urls: list[str], dry_run: bool) -> bool:
    payload = {
        "host": host,
        "key": key,
        "keyLocation": f"https://{host}/{key}.txt",
        "urlList": urls,
    }
    body = json.dumps(payload).encode("utf-8")
    if dry_run:
        log.info("[dry-run] POST %s (%d URLs)", INDEXNOW_ENDPOINT, len(urls))
        return True
    req = urllib.request.Request(
        INDEXNOW_ENDPOINT,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "TransparenciaPB-IndexNow/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = resp.status
            log.info("IndexNow response: HTTP %d (%d URLs)", status, len(urls))
            return 200 <= status < 300
    except urllib.error.HTTPError as e:
        log.error("IndexNow HTTPError %d: %s", e.code, e.read().decode("utf-8", "replace")[:500])
        return False
    except urllib.error.URLError as e:
        log.error("IndexNow URLError: %s", e.reason)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Maximo de URLs a submeter (default: todas do sitemap)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Apenas mostra URLs que seriam submetidas, sem chamar IndexNow",
    )
    args = parser.parse_args()

    key = os.environ.get("INDEXNOW_KEY", "").strip()
    if not key:
        log.error("INDEXNOW_KEY nao setada no .env. Aborte.")
        return 2

    site_url = os.environ.get("SITE_URL", "https://transparenciapb.org").strip().rstrip("/")
    parsed = urlparse(site_url)
    if not parsed.netloc:
        log.error("SITE_URL invalida: %s", site_url)
        return 2
    host = parsed.netloc

    # Gera sitemap localmente — agora usa sitemap-INDEX pattern (ver
    # web/routes/seo.py refactor pra suportar 100K+ URLs sem hit no
    # limite de 50K do protocolo sitemap.org). Iteramos sub-sitemaps:
    #   1. /sitemap-cidades.xml  (static + cidades, ~228 URLs)
    #   2. /sitemap-empresas-{n}.xml  (N shards de ate 49K cada, so se
    #                                  SITEMAP_INCLUDE_EMPRESAS=1)
    # Junta URLs de todos os sub-sitemaps e submete em batches de 500.
    #
    # NAO chamamos _build_sitemap_index — esse retorna apenas links pros
    # sub-sitemaps, nao URLs finais. IndexNow espera URLs de paginas reais.
    from web import db as web_db
    from web.routes.seo import (
        EMPRESA_SHARD_SIZE,
        _build_cidades_sitemap,
        _build_empresas_municipios_shard_sitemap,
        _build_empresas_shard_sitemap,
        _empresas_municipios_qualificadas_count,
        _empresas_qualificadas_count,
    )
    import math as _math

    pool_inited = False
    urls: list[str] = []
    flag_empresas = os.environ.get("SITEMAP_INCLUDE_EMPRESAS", "0") == "1"
    try:
        try:
            web_db.init_pool()
            pool_inited = True
        except Exception:
            log.exception(
                "Falha ao inicializar pool DB; sitemap vai usar so URLs estaticas"
            )

        # Sub-sitemap das cidades (sempre presente)
        try:
            cidades_xml = _build_cidades_sitemap(site_url)
            cidades_urls = _extract_urls_from_sitemap(cidades_xml)
            urls.extend(cidades_urls)
            log.info("sitemap-cidades: %d URLs", len(cidades_urls))
        except Exception:
            log.exception("Falha ao gerar sitemap-cidades")

        # Sub-sitemaps de empresas (so quando flag=1 — drop-in systemd
        # passou pelo subprocess via export SITEMAP_INCLUDE_EMPRESAS=1).
        if flag_empresas:
            try:
                total = _empresas_qualificadas_count()
                num_shards = _math.ceil(total / EMPRESA_SHARD_SIZE) if total > 0 else 0
                log.info(
                    "empresas qualificadas=%d, shards=%d (size=%d)",
                    total, num_shards, EMPRESA_SHARD_SIZE,
                )
                for n in range(1, num_shards + 1):
                    try:
                        shard_xml = _build_empresas_shard_sitemap(site_url, n)
                        shard_urls = _extract_urls_from_sitemap(shard_xml)
                        urls.extend(shard_urls)
                        log.info("sitemap-empresas-%d: %d URLs", n, len(shard_urls))
                    except Exception:
                        log.exception("Falha ao gerar sitemap-empresas shard %d", n)
            except Exception:
                log.exception("Falha ao contar empresas pro sitemap")

            # Pares (empresa, municipio) — variantes /empresa/<cnpj>/<slug>.
            try:
                total_em = _empresas_municipios_qualificadas_count()
                num_shards_em = (
                    _math.ceil(total_em / EMPRESA_SHARD_SIZE) if total_em > 0 else 0
                )
                log.info(
                    "empresas-municipios qualificados=%d, shards=%d (size=%d)",
                    total_em, num_shards_em, EMPRESA_SHARD_SIZE,
                )
                for n in range(1, num_shards_em + 1):
                    try:
                        shard_xml = _build_empresas_municipios_shard_sitemap(
                            site_url, n
                        )
                        shard_urls = _extract_urls_from_sitemap(shard_xml)
                        urls.extend(shard_urls)
                        log.info(
                            "sitemap-empresas-municipios-%d: %d URLs",
                            n, len(shard_urls),
                        )
                    except Exception:
                        log.exception(
                            "Falha ao gerar sitemap-empresas-municipios shard %d", n
                        )
            except Exception:
                log.exception(
                    "Falha ao contar empresas-municipios pro sitemap"
                )
        else:
            log.info(
                "SITEMAP_INCLUDE_EMPRESAS != '1' — submetendo so cidades+estaticas"
            )
    finally:
        if pool_inited:
            try:
                web_db.close_pool()
            except Exception:
                log.exception("Falha ao fechar pool DB (ignorado)")

    if args.limit:
        urls = urls[: args.limit]

    if not urls:
        log.warning("Nenhuma URL extraida do sitemap. Aborte.")
        return 1

    log.info("Submetendo %d URL(s) ao IndexNow (host=%s)", len(urls), host)
    ok = True
    # Sleep entre batches: IndexNow nao publica rate limits oficiais, mas
    # apos onda de empresas (~5K-50K URLs) podemos bater limite implicito
    # do Bing. 0.5s entre batches da margem de seguranca sem alongar muito
    # o submit (50 batches = 25s adicional). Apenas em modo real, nao dry-run.
    batch_indices = list(range(0, len(urls), BATCH_SIZE))
    for idx, i in enumerate(batch_indices):
        batch = urls[i : i + BATCH_SIZE]
        ok = _submit_batch(host, key, batch, args.dry_run) and ok
        if not args.dry_run and idx < len(batch_indices) - 1:
            time.sleep(0.5)

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
