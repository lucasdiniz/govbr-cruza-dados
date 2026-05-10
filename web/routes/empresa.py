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
    EMPRESA_EMPENHOS_RECENTES_BY_MUN,
    EMPRESA_ESTABELECIMENTO_BY_CNPJ_COMPLETO,
    EMPRESA_LENIENCIA_BY_BASICO,
    EMPRESA_LENIENCIA_EFEITOS_BY_ID,
    EMPRESA_MATRIZ_BY_BASICO,
    EMPRESA_MUNICIPIOS_PAGANTES_BY_BASICO,
    EMPRESA_PAGAMENTOS_MENSAIS_BY_MUN,
    EMPRESA_PAGAMENTOS_MENSAIS_GLOBAL_BY_BASICO,
    EMPRESA_PAGAMENTOS_SANCAO_OUTROS,
    EMPRESA_PGFN_BY_BASICO,
    EMPRESA_SANCOES_CEIS_BY_BASICO,
    EMPRESA_SANCOES_CNEP_BY_BASICO,
    EMPRESA_SOCIOS_BY_BASICO,
    EMPRESA_STATS_BY_MUN,
    EMPRESA_TOP_ELEMENTOS_BY_MUN,
    EMPRESA_TOP_ELEMENTOS_GLOBAL_BY_BASICO,
)
from web.utils.slug import SlugLookupError, municipio_slug, slug_to_municipio

router = APIRouter()
_log = logging.getLogger("transparencia.empresa")

_CNPJ_RE = re.compile(r"^\d{14}$")

# Chave canonica usada em web_cache. Warmer e rota DEVEM usar exatamente
# esta string. Mudancas exigem invalidar o cache existente.
CACHE_QUERY_ID = "EMPRESA_PERFIL"

# Cache para a variante /empresa/<cnpj>/<municipio_slug>. Storage:
#   query_id = "EMPRESA_PERFIL_MUN"
#   municipio = f"{cnpj_completo}:{municipio_slug}"
CACHE_QUERY_ID_MUN = "EMPRESA_PERFIL_MUN"


# Mapeamento RFB do campo `porte` (codigo numerico de 2 digitos) para
# o label oficial. "00" significa nao informado e nao deve ser exibido.
_PORTE_LABELS = {
    "00": None,
    "01": "ME (Microempresa)",
    "03": "EPP (Empresa de Pequeno Porte)",
    "05": "Demais",
}


def compute_empresa_porte_label(porte_raw: Any) -> str | None:
    """Converte codigo de porte RFB para label legivel ou None."""
    if porte_raw is None:
        return None
    s = str(porte_raw).strip().zfill(2)
    return _PORTE_LABELS.get(s)


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


def _fetch_pagamentos_municipio(cur, cnpj_basico: str, municipio: str,
                                with_sancao_outros: bool = False) -> dict[str, Any]:
    """Roda as queries _BY_MUN para um (cnpj_basico, municipio) e retorna
    dict com chaves: stats, monthly, top_elementos, empenhos e
    opcionalmente pagamentos_sancao_outros.

    Reusada por:
      - compute_empresa_perfil_dict (uma vez por municipio pagante)
      - compute_empresa_municipio_perfil_dict (uma unica vez)
    """
    params = {"cnpj_basico": cnpj_basico, "municipio": municipio}

    cur.execute(EMPRESA_STATS_BY_MUN, params)
    st_cols = [d[0] for d in cur.description]
    st_row = cur.fetchone()
    stats = _convert_row(_row_to_dict(st_cols, st_row)) if st_row else {}

    cur.execute(EMPRESA_PAGAMENTOS_MENSAIS_BY_MUN, params)
    m_cols = [d[0] for d in cur.description]
    monthly = [_convert_row(_row_to_dict(m_cols, r)) for r in cur.fetchall()]

    cur.execute(EMPRESA_TOP_ELEMENTOS_BY_MUN, params)
    te_cols = [d[0] for d in cur.description]
    top_elementos = [_convert_row(_row_to_dict(te_cols, r)) for r in cur.fetchall()]

    cur.execute(EMPRESA_EMPENHOS_RECENTES_BY_MUN, params)
    e_cols = [d[0] for d in cur.description]
    empenhos = [_convert_row(_row_to_dict(e_cols, r)) for r in cur.fetchall()]

    out = {
        "municipio": municipio,
        "municipio_slug": municipio_slug(municipio),
        "stats": stats,
        "monthly": monthly,
        "top_elementos": top_elementos,
        "empenhos": empenhos,
    }
    if with_sancao_outros:
        cur.execute(
            EMPRESA_PAGAMENTOS_SANCAO_OUTROS,
            {"cnpj_basico": cnpj_basico, "municipio_atual": municipio},
        )
        so_cols = [d[0] for d in cur.description]
        out["pagamentos_sancao_outros"] = [
            _convert_row(_row_to_dict(so_cols, r)) for r in cur.fetchall()
        ]
    return out


def _fetch_cadastral_block(cur, cnpj_completo: str, cnpj_basico: str,
                           cnpj_ordem: str) -> dict[str, Any]:
    """Roda as queries cadastrais (estabelecimento, matriz, socios,
    sancoes, pgfn, leniencia, municipios_pagantes, top_elementos
    global, monthly_global) e retorna dict.

    Compartilhado entre as duas funcoes compute_*. Levanta
    EmpresaNotFoundError se nao houver cadastro RFB.
    """
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
    socios = [_convert_row(_row_to_dict(soc_cols, r)) for r in cur.fetchall()]

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
    pgfn = [_convert_row(_row_to_dict(pg_cols, r)) for r in cur.fetchall()]

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
        _convert_row(_row_to_dict(mp_cols, r)) for r in cur.fetchall()
    ]
    # anota slug em cada item para os templates linkarem direto
    for mp in municipios_pagantes:
        mp["slug"] = municipio_slug(mp.get("municipio") or "")

    cur.execute(EMPRESA_TOP_ELEMENTOS_GLOBAL_BY_BASICO, (cnpj_basico,))
    te_cols = [d[0] for d in cur.description]
    top_elementos = [
        _convert_row(_row_to_dict(te_cols, r)) for r in cur.fetchall()
    ]

    cur.execute(EMPRESA_PAGAMENTOS_MENSAIS_GLOBAL_BY_BASICO, (cnpj_basico,))
    m_cols = [d[0] for d in cur.description]
    monthly_global = [
        _convert_row(_row_to_dict(m_cols, r)) for r in cur.fetchall()
    ]

    return {
        "estabelecimento": estabelecimento,
        "matriz": matriz,
        "socios": socios,
        "sancoes": sancoes,
        "pgfn": pgfn,
        "acordos_leniencia": acordos,
        "municipios_pagantes": municipios_pagantes,
        "top_elementos": top_elementos,
        "monthly_global": monthly_global,
    }


def _build_meta_description(razao_social: str, cnpj_fmt: str,
                            total_pb: float, sancoes: list,
                            total_divida_pgfn: float,
                            municipio_scope: str | None = None) -> str:
    """Gera meta description curta e factual. Se municipio_scope dado,
    foca no escopo daquele municipio."""
    if municipio_scope:
        parts = [
            f"Pagamentos publicos de {razao_social} (CNPJ {cnpj_fmt}) "
            f"em {municipio_scope}/PB."
        ]
    else:
        parts = [f"Perfil de {razao_social} (CNPJ {cnpj_fmt}) no TransparenciaPB."]
    if total_pb > 0:
        parts.append(f"Recebido em PB: R$ {total_pb:,.0f}".replace(",", "."))
    if sancoes:
        parts.append(f"Sancoes: {len(sancoes)}.")
    if total_divida_pgfn > 0:
        parts.append(
            f"Divida PGFN: R$ {total_divida_pgfn:,.0f}".replace(",", ".")
        )
    return " ".join(parts)[:300]


def _resolve_razao_social(estabelecimento: dict, agregados: dict,
                          cnpj_basico: str) -> str:
    return (
        estabelecimento.get("razao_social")
        or agregados.get("razao_social")
        or estabelecimento.get("nome_fantasia")
        or f"Empresa {cnpj_basico}"
    )


def compute_empresa_perfil_dict(
    cnpj_completo: str,
    timeout_sec: int = TIMEOUT_PROFILE,
) -> dict[str, Any]:
    """Executa todas as queries e monta o dict completo do perfil global.

    Args:
        cnpj_completo: 14 digitos numericos puros.
        timeout_sec: statement_timeout em segundos. Default TIMEOUT_PROFILE
            (3s) — adequado pra empresas tipicas. Warmer passa
            TIMEOUT_PROFILE_WARM (120s) pra cobrir mega-empresas
            governamentais (BB, Caixa, INSS) que tem milhoes de empenhos
            e estouram timeouts curtos em GROUP BY.

    Returns: dict pronto pra TemplateResponse. Inclui:
        - cadastrais (estabelecimento, matriz, socios, sancoes, pgfn,
          leniencia)
        - agregados/KPIs
        - municipios_pagantes (com slug pre-computado — lista clicavel
          pra /empresa/<cnpj>/<slug>)
        - top_elementos GLOBAL
        - monthly_global (chart 12 meses GLOBAL)
        Detalhes POR municipio (50 empenhos, monthly local, top elementos,
        stats, sancao_outros) NAO sao cacheados aqui — vivem em
        EMPRESA_PERFIL_MUN:<cnpj>:<slug> populado por
        _warm_one_empresa_municipio. Pagina global so mostra preview;
        detalhes carregam via /empresa/<cnpj>/<slug>.
    Raises: EmpresaNotFoundError se empresa nao em mv_empresa_pb ou
            cadastro RFB ausente.
    """
    if not _CNPJ_RE.fullmatch(cnpj_completo):
        raise EmpresaNotFoundError(f"CNPJ invalido: {cnpj_completo}")

    cnpj_basico = cnpj_completo[:8]
    cnpj_ordem = cnpj_completo[8:12]

    # 1. Agregados PB (mv_empresa_pb) — chave: cnpj_basico.
    agg_cols, agg_rows = execute_query(
        EMPRESA_AGREGADOS_PB_BY_BASICO,
        (cnpj_basico,),
        timeout_sec=timeout_sec,
    )
    if not agg_rows:
        raise EmpresaNotFoundError(f"sem dados PB: {cnpj_completo}")
    agregados = _convert_row(_row_to_dict(agg_cols, agg_rows[0]))

    # 2. Cadastro RFB + demais detalhes — uma transaction com todos
    # os SELECTs. statement_timeout setado e resetado em try/finally pra
    # nao vazar configuracao pro pool.
    with get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{timeout_sec * 1000}'")
            try:
                cadastral = _fetch_cadastral_block(
                    cur, cnpj_completo, cnpj_basico, cnpj_ordem
                )

                # NOTA: dados detalhados POR MUNICIPIO (50 empenhos, monthly,
                # top elementos, stats, sancao_outros) NAO sao cacheados aqui.
                # Eles vivem em cache separado (EMPRESA_PERFIL_MUN:<cnpj>:<slug>)
                # populado por _warm_one_empresa_municipio. Pagina global so
                # mostra preview + lista clicavel; detalhes carregam via
                # /empresa/<cnpj>/<slug>. Versao anterior do PR #62 cacheava
                # tudo aqui inline (dict municipios_data) — dead code que
                # inflava blobs ate 15MB pra mega-empresas governamentais
                # (BB, Caixa, INSS) sem nenhum template lendo.
            finally:
                try:
                    cur.execute("RESET statement_timeout")
                except Exception:
                    _log.warning(
                        "RESET statement_timeout falhou (conexao "
                        "provavelmente sera descartada pelo pool)"
                    )

    estabelecimento = cadastral["estabelecimento"]
    razao_social = _resolve_razao_social(estabelecimento, agregados, cnpj_basico)
    cnpj_fmt = _format_cnpj(cnpj_completo)
    total_pb_geral = float(agregados.get("total_pb_geral") or 0)
    qtd_municipios = len(cadastral["municipios_pagantes"])
    qtd_empenhos_pb = int(agregados.get("qtd_tce_empenhos") or 0) + int(
        agregados.get("qtd_pb_empenhos") or 0
    )
    total_divida_pgfn = float(agregados.get("total_divida_pgfn") or 0)

    porte_label = compute_empresa_porte_label(estabelecimento.get("porte"))

    meta_description = _build_meta_description(
        razao_social, cnpj_fmt, total_pb_geral,
        cadastral["sancoes"], total_divida_pgfn,
    )

    return {
        "cnpj": cnpj_completo,
        "cnpj_basico": cnpj_basico,
        "cnpj_ordem": cnpj_ordem,
        "cnpj_fmt": cnpj_fmt,
        "razao_social": razao_social,
        "porte_label": porte_label,
        "estabelecimento": estabelecimento,
        "matriz": cadastral["matriz"],
        "socios": cadastral["socios"],
        "sancoes": cadastral["sancoes"],
        "pgfn": cadastral["pgfn"],
        "acordos_leniencia": cadastral["acordos_leniencia"],
        "agregados": agregados,
        "municipios_pagantes": cadastral["municipios_pagantes"],
        "top_elementos": cadastral["top_elementos"],
        "monthly_global": cadastral["monthly_global"],
        "kpi_total_pb": total_pb_geral,
        "kpi_qtd_municipios": qtd_municipios,
        "kpi_qtd_empenhos": qtd_empenhos_pb,
        "kpi_total_divida_pgfn": total_divida_pgfn,
        "meta_description": meta_description,
        "scope": "global",
    }


def compute_empresa_municipio_perfil_dict(
    cnpj_completo: str,
    municipio: str,
    timeout_sec: int = TIMEOUT_PROFILE,
    cadastral_cache: dict[str, Any] | None = None,
    agregados_cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Computa o perfil de uma empresa SCOPED a um municipio especifico.

    Reaproveita o cadastral block (estabelecimento, matriz, socios,
    sancoes, pgfn, leniencia) e substitui as listagens globais de
    pagamentos por dados focados no municipio recebido.

    Args:
        cnpj_completo: 14 digitos numericos puros.
        municipio: nome canonico do municipio (NAO slug). Caller deve
            ter resolvido via slug_to_municipio.
        timeout_sec: idem compute_empresa_perfil_dict.
        cadastral_cache: dict ja com cadastrais resolvidos (estabelecimento,
            matriz, socios, sancoes, pgfn, acordos_leniencia,
            municipios_pagantes). Se passado, EVITA refazer 5-7 queries
            cadastrais. Otimizacao critica pro warmer: BB com 200 munis
            faria 200x as mesmas queries — pre-fetch global e reuso aqui
            corta isso. Se None, fetcha do DB normalmente.
        agregados_cache: row de mv_empresa_pb. Se passado, evita 1 query.

    Raises: EmpresaNotFoundError se empresa nao em mv_empresa_pb,
            sem cadastro RFB, ou sem pagamentos no municipio dado.
    """
    if not _CNPJ_RE.fullmatch(cnpj_completo):
        raise EmpresaNotFoundError(f"CNPJ invalido: {cnpj_completo}")
    if not municipio:
        raise EmpresaNotFoundError("municipio vazio")

    cnpj_basico = cnpj_completo[:8]
    cnpj_ordem = cnpj_completo[8:12]

    if agregados_cache is not None:
        agregados = agregados_cache
    else:
        agg_cols, agg_rows = execute_query(
            EMPRESA_AGREGADOS_PB_BY_BASICO,
            (cnpj_basico,),
            timeout_sec=timeout_sec,
        )
        if not agg_rows:
            raise EmpresaNotFoundError(f"sem dados PB: {cnpj_completo}")
        agregados = _convert_row(_row_to_dict(agg_cols, agg_rows[0]))

    with get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{timeout_sec * 1000}'")
            try:
                if cadastral_cache is not None:
                    cadastral = cadastral_cache
                else:
                    cadastral = _fetch_cadastral_block(
                        cur, cnpj_completo, cnpj_basico, cnpj_ordem
                    )
                pag = _fetch_pagamentos_municipio(
                    cur, cnpj_basico, municipio,
                    with_sancao_outros=bool(cadastral["sancoes"]),
                )
            finally:
                try:
                    cur.execute("RESET statement_timeout")
                except Exception:
                    _log.warning("RESET statement_timeout falhou")

    stats = pag.get("stats") or {}
    qtd_no_mun = int(stats.get("qtd_empenhos") or 0)
    if qtd_no_mun == 0:
        raise EmpresaNotFoundError(
            f"sem pagamentos: {cnpj_completo} em {municipio}"
        )

    estabelecimento = cadastral["estabelecimento"]
    razao_social = _resolve_razao_social(estabelecimento, agregados, cnpj_basico)
    cnpj_fmt = _format_cnpj(cnpj_completo)
    total_pago_mun = float(stats.get("total_pago") or 0)
    total_emp_mun = float(stats.get("total_empenhado") or 0)
    qtd_sem_lic = int(stats.get("qtd_sem_licitacao") or 0)
    pct_sem_lic = (qtd_sem_lic * 100.0 / qtd_no_mun) if qtd_no_mun > 0 else 0.0

    porte_label = compute_empresa_porte_label(estabelecimento.get("porte"))
    total_divida_pgfn = float(agregados.get("total_divida_pgfn") or 0)

    meta_description = _build_meta_description(
        razao_social, cnpj_fmt, total_pago_mun,
        cadastral["sancoes"], total_divida_pgfn,
        municipio_scope=municipio,
    )

    slug = municipio_slug(municipio)

    return {
        "cnpj": cnpj_completo,
        "cnpj_basico": cnpj_basico,
        "cnpj_ordem": cnpj_ordem,
        "cnpj_fmt": cnpj_fmt,
        "razao_social": razao_social,
        "porte_label": porte_label,
        "estabelecimento": estabelecimento,
        "matriz": cadastral["matriz"],
        "socios": cadastral["socios"],
        "sancoes": cadastral["sancoes"],
        "pgfn": cadastral["pgfn"],
        "acordos_leniencia": cadastral["acordos_leniencia"],
        "agregados": agregados,
        "municipios_pagantes": cadastral["municipios_pagantes"],
        # Pagamentos restritos ao municipio:
        "municipio": municipio,
        "municipio_slug": slug,
        "stats_municipio": stats,
        "monthly": pag["monthly"],
        "top_elementos": pag["top_elementos"],
        "empenhos": pag["empenhos"],
        "pagamentos_sancao_outros": pag.get("pagamentos_sancao_outros") or [],
        # KPIs focados no municipio:
        "kpi_total_pago_mun": total_pago_mun,
        "kpi_total_empenhado_mun": total_emp_mun,
        "kpi_qtd_empenhos_mun": qtd_no_mun,
        "kpi_qtd_sem_licitacao_mun": qtd_sem_lic,
        "kpi_pct_sem_licitacao_mun": pct_sem_lic,
        "kpi_total_divida_pgfn": total_divida_pgfn,
        "meta_description": meta_description,
        "scope": "municipio",
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


# slug_to_municipio() ja normaliza acentos/case e tolera hifens duplos.
# Nao precisamos validar regex aqui: lookup falha (None) eh suficiente
# pra rejeitar slug invalido com 404. (Ver fix P2 GPT-5.5 PR #62.)


@router.get("/empresa/{cnpj}/{municipio_slug_in}")
async def empresa_perfil_municipio(
    request: Request, cnpj: str, municipio_slug_in: str
):
    """Renderiza /empresa/<14-digits>/<municipio-slug>. Cache-only (mesmo
    invariant da rota global): cache miss = 503 com Retry-After 1h.

    Validacoes em ordem:
    1. CNPJ canonico (14 digitos numericos puros, sem mascara).
    2. Filial (ordem != 0001) -> redireciona pra matriz preservando o slug.
    3. Slug municipio resolve via slug_to_municipio. None = 404.
    4. Slug nao canonico -> 301 pro slug canonico.
    5. Lookup web_cache(EMPRESA_PERFIL_MUN, "<cnpj>:<slug>"). Hit -> render.
       Miss -> 503.
    """
    from web.main import templates

    canonical_cnpj = _normalize_cnpj_input(cnpj)
    if not canonical_cnpj:
        return templates.TemplateResponse(
            request,
            "errors/404.html",
            {"path": str(request.url.path)},
            status_code=404,
        )
    if cnpj != canonical_cnpj:
        return RedirectResponse(
            url=f"/empresa/{canonical_cnpj}/{municipio_slug_in}",
            status_code=301,
        )

    cnpj_ordem = canonical_cnpj[8:12]
    if cnpj_ordem != "0001":
        try:
            matriz_dv = _calculate_cnpj_dv(canonical_cnpj[:8], "0001")
            matriz = canonical_cnpj[:8] + "0001" + matriz_dv
            return RedirectResponse(
                url=f"/empresa/{matriz}/{municipio_slug_in}",
                status_code=301,
            )
        except ValueError:
            return templates.TemplateResponse(
                request,
                "errors/404.html",
                {"path": str(request.url.path)},
                status_code=404,
            )

    # Resolve slug -> nome canonico do municipio.
    # IMPORTANTE: slug_to_municipio() ja normaliza (case, acentos), entao
    # variantes como Joao-Pessoa, JOAO-PESSOA, joao--pessoa resolvem.
    # Tentamos resolver ANTES de validar regex estrito — se nao bater
    # case canonico, devolvemos 301. Sem isso, slugs validos mas
    # nao-canonicos virariam 404 silenciosos. (P2 GPT-5.5 PR #62.)
    if not municipio_slug_in:
        return templates.TemplateResponse(
            request,
            "errors/404.html",
            {"path": str(request.url.path)},
            status_code=404,
        )
    try:
        municipio_nome = slug_to_municipio(municipio_slug_in)
    except SlugLookupError:
        # Cold start sem cache + DB indisponivel -> 503 (caller deve
        # retentar). Evita 404 falso enquanto o cache nao carregou.
        return Response(
            status_code=503,
            headers={"Retry-After": "60"},
            content="Cache de slugs indisponivel. Tente novamente.",
            media_type="text/plain; charset=utf-8",
        )
    if not municipio_nome:
        # Slug nao bate com nenhum municipio conhecido — agora sim 404
        # (depois de tentar resolver via lookup que tolera variantes).
        return templates.TemplateResponse(
            request,
            "errors/404.html",
            {"path": str(request.url.path)},
            status_code=404,
        )

    # Slug nao canonico (ex: case diferente, hifens duplos) -> 301 pro canonico
    canonical_slug = municipio_slug(municipio_nome)
    if canonical_slug and canonical_slug != municipio_slug_in:
        return RedirectResponse(
            url=f"/empresa/{canonical_cnpj}/{canonical_slug}",
            status_code=301,
        )

    cache_key = f"{canonical_cnpj}:{canonical_slug}"
    cached = read_web_cache(CACHE_QUERY_ID_MUN, cache_key)
    if cached is not None:
        _cols, rows = cached
        if rows and rows[0]:
            data = rows[0][0]
            if isinstance(data, dict) and data:
                return templates.TemplateResponse(
                    request, "results/empresa_municipio.html", data
                )

    _log.info(
        "cache miss /empresa/%s/%s — returning 503",
        canonical_cnpj, canonical_slug,
    )
    return Response(
        status_code=503,
        headers={"Retry-After": "3600"},
        content=(
            "Perfil em construcao — este recorte (empresa × municipio) "
            "ainda nao foi pre-processado. Tente novamente mais tarde."
        ),
        media_type="text/plain; charset=utf-8",
    )
