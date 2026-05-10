"""Rota publica /empresa/{cnpj} — perfil SEO de empresa.

ARQUITETURA pos-incidente do PR #57:
- Rota e CACHE-ONLY: le de web_cache (chave EMPRESA_PERFIL:<cnpj>) e renderiza.
- Cache miss = 503 com Retry-After (NAO faz live query — protege DB do
  thundering herd que derrubou o site quando IndexNow notificou Bing sobre
  45K URLs simultaneamente). Cache-miss-only e seguro porque empresas so
  entram no sitemap depois de warmed.
- A funcao `compute_empresa_perfil_dict` executa as 8 queries e monta o
  dict completo. Eh chamada APENAS pelo warmer (web/warm_cache.py), nunca
  inline na rota.

URL: /empresa/<14-digitos>. CNPJ formatado com mascara redireciona via
404; entrada deve ser 14 digitos numericos puros (canonical).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from web.config import TIMEOUT_PROFILE
from web.db import execute_query, get_conn, read_web_cache
from web.queries.empresa import (
    EMPRESA_AGREGADOS_PB_BY_BASICO,
    EMPRESA_ESTABELECIMENTO_BY_CNPJ_COMPLETO,
    EMPRESA_LENIENCIA_BY_BASICO,
    EMPRESA_LENIENCIA_EFEITOS_BY_ID,
    EMPRESA_MATRIZ_BY_BASICO,
    EMPRESA_MUNICIPIOS_PAGANTES_BY_BASICO,
    EMPRESA_PGFN_BY_BASICO,
    EMPRESA_SANCOES_CEIS_BY_BASICO,
    EMPRESA_SANCOES_CNEP_BY_BASICO,
    EMPRESA_SOCIOS_BY_BASICO,
    EMPRESA_TOP_ELEMENTOS_GLOBAL_BY_BASICO,
)

router = APIRouter()
_log = logging.getLogger("transparencia.empresa")

_CNPJ_RE = re.compile(r"^\d{14}$")

# Chave canonica usada em web_cache. Warmer e rota DEVEM usar exatamente
# esta string. Mudancas exigem invalidar o cache existente.
CACHE_QUERY_ID = "EMPRESA_PERFIL"


def _row_to_dict(cols, row):
    return dict(zip(cols, row))


def _convert(value):
    if hasattr(value, "as_tuple"):  # Decimal
        return float(value)
    if hasattr(value, "isoformat"):  # date/datetime
        return value.isoformat()
    return value


def _convert_row(d: dict) -> dict:
    return {k: _convert(v) for k, v in d.items()}


def _format_cnpj(cnpj14: str) -> str:
    return f"{cnpj14[:2]}.{cnpj14[2:5]}.{cnpj14[5:8]}/{cnpj14[8:12]}-{cnpj14[12:14]}"


def _normalize_cnpj_input(raw: str) -> str | None:
    """Retorna 14 digitos puros (sem mascara) ou None se invalido."""
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) != 14:
        return None
    return digits


def _calculate_cnpj_dv(basico: str, ordem: str) -> str:
    """Computa os 2 digitos verificadores do CNPJ a partir de basico+ordem.

    Algoritmo padrao da Receita Federal (modulo 11):
    - DV1: soma ponderada dos primeiros 12 digitos com pesos
      [5,4,3,2,9,8,7,6,5,4,3,2], depois (sum * 10) % 11 % 10.
    - DV2: idem com 13 digitos e pesos [6,5,4,3,2,9,8,7,6,5,4,3,2].

    Pure math, sem DB hit. Usado pra redirecionar /empresa/<filial> ->
    /empresa/<matriz> sem precisar consultar estabelecimento (mantem o
    invariant cache-only da rota).
    """
    digits = basico + ordem
    if len(digits) != 12 or not digits.isdigit():
        raise ValueError(f"basico+ordem invalido: {digits!r}")
    weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum1 = sum(int(digits[i]) * weights1[i] for i in range(12))
    dv1 = (sum1 * 10) % 11 % 10
    digits2 = digits + str(dv1)
    weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    sum2 = sum(int(digits2[i]) * weights2[i] for i in range(13))
    dv2 = (sum2 * 10) % 11 % 10
    return f"{dv1}{dv2}"


# ─────────────────────────────────────────────────────────────────────────
# Pipeline de computacao: roda as 8 queries e monta o dict de template.
# Usado APENAS pelo warmer. Nao chamar da rota (custo alto, risco de pool
# exhaustion sob trafego de crawler).
# ─────────────────────────────────────────────────────────────────────────


class EmpresaNotFoundError(Exception):
    """Empresa nao tem dados PB (nao em mv_empresa_pb) ou CNPJ invalido."""


def compute_empresa_perfil_dict(cnpj_completo: str) -> dict[str, Any]:
    """Executa as 8 queries e monta o dict completo do perfil.

    Returns: dict pronto pra TemplateResponse.
    Raises: EmpresaNotFoundError se empresa nao em mv_empresa_pb ou
            cadastro RFB ausente. Outras exceptions sao do DB e propagam.
    """
    if not _CNPJ_RE.fullmatch(cnpj_completo):
        raise EmpresaNotFoundError(f"CNPJ invalido: {cnpj_completo}")

    cnpj_basico = cnpj_completo[:8]
    cnpj_ordem = cnpj_completo[8:12]

    # 1. Agregados PB (mv_empresa_pb) — chave: cnpj_basico.
    agg_cols, agg_rows = execute_query(
        EMPRESA_AGREGADOS_PB_BY_BASICO,
        (cnpj_basico,),
        timeout_sec=TIMEOUT_PROFILE,
    )
    if not agg_rows:
        raise EmpresaNotFoundError(f"sem dados PB: {cnpj_completo}")
    agregados = _convert_row(_row_to_dict(agg_cols, agg_rows[0]))

    # 2. Cadastro RFB + 3-8 demais detalhes — uma transaction com todos
    # os SELECTs. statement_timeout setado e resetado em try/finally pra
    # nao vazar configuracao pro pool.
    with get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{TIMEOUT_PROFILE * 1000}'")
            try:
                cur.execute(EMPRESA_ESTABELECIMENTO_BY_CNPJ_COMPLETO, (cnpj_completo,))
                est_cols = [d[0] for d in cur.description]
                est_rows = cur.fetchall()
                if not est_rows:
                    raise EmpresaNotFoundError(f"sem cadastro RFB: {cnpj_completo}")
                estabelecimento = _convert_row(_row_to_dict(est_cols, est_rows[0]))

                matriz = None
                if cnpj_ordem != "0001":
                    cur.execute(EMPRESA_MATRIZ_BY_BASICO, (cnpj_basico,))
                    mat_cols = [d[0] for d in cur.description]
                    mat_row = cur.fetchone()
                    if mat_row:
                        matriz = _convert_row(_row_to_dict(mat_cols, mat_row))

                cur.execute(EMPRESA_SOCIOS_BY_BASICO, (cnpj_basico,))
                soc_cols = [d[0] for d in cur.description]
                socios = [
                    _convert_row(_row_to_dict(soc_cols, r))
                    for r in cur.fetchall()
                ]

                cur.execute(EMPRESA_SANCOES_CEIS_BY_BASICO, (cnpj_basico,))
                ceis_cols = [d[0] for d in cur.description]
                sancoes: list[dict] = []
                for r in cur.fetchall():
                    item = _convert_row(_row_to_dict(ceis_cols, r))
                    item["origem"] = "CEIS"
                    sancoes.append(item)

                cur.execute(EMPRESA_SANCOES_CNEP_BY_BASICO, (cnpj_basico,))
                cnep_cols = [d[0] for d in cur.description]
                for r in cur.fetchall():
                    item = _convert_row(_row_to_dict(cnep_cols, r))
                    item["origem"] = "CNEP"
                    sancoes.append(item)

                cur.execute(EMPRESA_PGFN_BY_BASICO, (cnpj_basico,))
                pg_cols = [d[0] for d in cur.description]
                pgfn = [
                    _convert_row(_row_to_dict(pg_cols, r))
                    for r in cur.fetchall()
                ]

                cur.execute(EMPRESA_LENIENCIA_BY_BASICO, (cnpj_basico,))
                len_cols = [d[0] for d in cur.description]
                acordos = []
                for r in cur.fetchall():
                    a = _convert_row(_row_to_dict(len_cols, r))
                    cur.execute(EMPRESA_LENIENCIA_EFEITOS_BY_ID, (a["id_acordo"],))
                    ef_cols = [d[0] for d in cur.description]
                    a["efeitos"] = [
                        _row_to_dict(ef_cols, er) for er in cur.fetchall()
                    ]
                    acordos.append(a)

                cur.execute(EMPRESA_MUNICIPIOS_PAGANTES_BY_BASICO, (cnpj_basico,))
                mp_cols = [d[0] for d in cur.description]
                municipios_pagantes = [
                    _convert_row(_row_to_dict(mp_cols, r))
                    for r in cur.fetchall()
                ]

                cur.execute(EMPRESA_TOP_ELEMENTOS_GLOBAL_BY_BASICO, (cnpj_basico,))
                te_cols = [d[0] for d in cur.description]
                top_elementos = [
                    _convert_row(_row_to_dict(te_cols, r))
                    for r in cur.fetchall()
                ]
            finally:
                try:
                    cur.execute("RESET statement_timeout")
                except Exception:
                    _log.warning(
                        "RESET statement_timeout falhou (conexao "
                        "provavelmente sera descartada pelo pool)"
                    )

    razao_social = (
        estabelecimento.get("razao_social")
        or agregados.get("razao_social")
        or estabelecimento.get("nome_fantasia")
        or f"Empresa {cnpj_basico}"
    )
    cnpj_fmt = _format_cnpj(cnpj_completo)
    total_pb_geral = float(agregados.get("total_pb_geral") or 0)
    qtd_municipios = len(municipios_pagantes)
    qtd_empenhos_pb = int(agregados.get("qtd_tce_empenhos") or 0) + int(
        agregados.get("qtd_pb_empenhos") or 0
    )
    total_divida_pgfn = float(agregados.get("total_divida_pgfn") or 0)

    # Meta description (150-160 chars). Mantemos curta e factual.
    meta_parts = [
        f"Perfil de {razao_social} (CNPJ {cnpj_fmt}) no TransparenciaPB."
    ]
    if total_pb_geral > 0:
        meta_parts.append(
            f"Recebido em PB: R$ {total_pb_geral:,.0f}".replace(",", ".")
        )
    if sancoes:
        meta_parts.append(f"Sancoes: {len(sancoes)}.")
    if total_divida_pgfn > 0:
        meta_parts.append(
            f"Divida PGFN: R$ {total_divida_pgfn:,.0f}".replace(",", ".")
        )
    meta_description = " ".join(meta_parts)[:300]

    return {
        "cnpj": cnpj_completo,
        "cnpj_basico": cnpj_basico,
        "cnpj_ordem": cnpj_ordem,
        "cnpj_fmt": cnpj_fmt,
        "razao_social": razao_social,
        "estabelecimento": estabelecimento,
        "matriz": matriz,
        "socios": socios,
        "sancoes": sancoes,
        "pgfn": pgfn,
        "acordos_leniencia": acordos,
        "agregados": agregados,
        "municipios_pagantes": municipios_pagantes,
        "top_elementos": top_elementos,
        "kpi_total_pb": total_pb_geral,
        "kpi_qtd_municipios": qtd_municipios,
        "kpi_qtd_empenhos": qtd_empenhos_pb,
        "kpi_total_divida_pgfn": total_divida_pgfn,
        "meta_description": meta_description,
    }


# ─────────────────────────────────────────────────────────────────────────
# Rota — cache-only.
# ─────────────────────────────────────────────────────────────────────────


@router.get("/empresa/{cnpj}")
async def empresa_perfil(request: Request, cnpj: str):
    """Renderiza /empresa/<14-digits>. Le de web_cache. Cache miss = 503.

    NUNCA executa as 8 queries inline. O incidente do PR #57 mostrou que
    sob trafego de crawler agressivo (Bing + 45K URLs do IndexNow), o pool
    de DB exauria em segundos e levava o site inteiro junto. Cache-only +
    sitemap-after-warm garante que crawler so encontra URLs com cache
    quente.
    """
    from web.main import templates

    canonical = _normalize_cnpj_input(cnpj)
    if not canonical:
        return templates.TemplateResponse(
            request,
            "errors/404.html",
            {"path": str(request.url.path)},
            status_code=404,
        )
    if cnpj != canonical:
        return RedirectResponse(url=f"/empresa/{canonical}", status_code=301)

    # Filial → matriz: o warmer popula cache so para a matriz (cnpj_ordem='0001')
    # de cada cnpj_basico (mesma logica do sitemap). Se chegou aqui um CNPJ
    # de filial (ordem != 0001), redireciona pra matriz canonica usando DV
    # computado matematicamente (sem DB hit, mantem cache-only invariant).
    # Sem isso, links do dialog de fornecedor que usam exactDoc da filial
    # cairiam em 503 mesmo apos warmer rodar (caught by GPT-5.5 review #58).
    cnpj_ordem = canonical[8:12]
    if cnpj_ordem != "0001":
        try:
            matriz_dv = _calculate_cnpj_dv(canonical[:8], "0001")
            matriz = canonical[:8] + "0001" + matriz_dv
            return RedirectResponse(url=f"/empresa/{matriz}", status_code=301)
        except ValueError:
            return templates.TemplateResponse(
                request,
                "errors/404.html",
                {"path": str(request.url.path)},
                status_code=404,
            )

    # Lookup no web_cache. Schema: (query_id=EMPRESA_PERFIL, municipio=cnpj),
    # rows[0][0] = dict completo serializado como JSONB.
    cached = read_web_cache(CACHE_QUERY_ID, canonical)
    if cached is not None:
        cols, rows = cached
        if rows and rows[0]:
            data = rows[0][0]
            if isinstance(data, dict) and data:
                return templates.TemplateResponse(
                    request, "results/empresa.html", data
                )

    # Cache miss. Em fluxo normal (pos-warm), so deveria acontecer pra:
    # (a) CNPJ que nao ta em mv_empresa_pb (deveria ser 404), ou
    # (b) primeiras requests apos restart antes de warm completar.
    # Retornamos 503 com Retry-After 1h pra crawler back off. A AUSENCIA
    # do CNPJ no sitemap (gated) significa que crawlers nem deveriam
    # estar aqui — se chegou ate aqui, eh acesso direto/legado.
    _log.info("cache miss /empresa/%s — returning 503", canonical)
    return Response(
        status_code=503,
        headers={"Retry-After": "3600"},
        content=(
            "Perfil em construcao — esta empresa ainda nao foi pre-processada. "
            "Tente novamente mais tarde."
        ),
        media_type="text/plain; charset=utf-8",
    )
