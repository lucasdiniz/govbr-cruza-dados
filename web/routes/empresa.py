"""Rota publica /empresa/{cnpj} — perfil SEO de empresa.

ARQUITETURA pos-incidente do PR #57:
- Rota e CACHE-ONLY: le de web_cache (chave EMPRESA_PERFIL:<cnpj>) e renderiza.
- Cache miss = 410 Gone (NAO faz live query — protege DB do thundering herd
  que derrubou o site quando IndexNow notificou Bing sobre 45K URLs
  simultaneamente). Cache-miss-only e seguro porque empresas so entram no
  sitemap depois de warmed (gating em deploy.yml com coverage >= 80%), e
  cleanup_orphan_empresa_cache (ADR-0009) garante que entries stale para
  CNPJs nao mais qualificados sao removidas. Miss aqui significa URL nao
  representa empresa qualificada na PB — 410 e semanticamente correto e
  acelera de-index da URL no Google (Google trata 410 como permanente e
  para de retentar em dias, vs 404 que insiste re-crawlando por semanas).
  Status revisado de 404 para 410 na revisao 2026-05-18 do ADR-0009 apos
  observar Googlebot persistindo em ~6.7k retries/dia em URLs orfas.
- DB error (pool exhaustion, statement_timeout, conn drop) = 503 com
  Retry-After. Distincao de cache miss vs DB error eh crucial: 410 em
  DB error transiente marcaria URLs legitimas como permanentemente
  removidas. read_web_cache retorna sentinel CACHE_ERROR para erros
  e None para row genuinamente ausente. (Revisao 2026-05-19 do ADR-0009
  apos review paralelo Opus 4.7-high + GPT-5.5 do PR #181.)
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
from web.db import CACHE_ERROR, execute_query, get_conn, read_web_cache
from web.queries.empresa import (
    EMPRESA_AGREGADOS_PB_BY_BASICO,
    EMPRESA_EMPENHOS_COUNT_BY_MUN,
    EMPRESA_EMPENHOS_COUNT_GLOBAL,
    EMPRESA_EMPENHOS_PAGINATED_BY_MUN,
    EMPRESA_EMPENHOS_PAGINATED_GLOBAL,
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
    EMPRESA_TCE_PB_DOE_BY_BASICO,
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

    # `qtd_empenhos` em stats ja eh o count total (foi computado pela
    # mesma query EMPRESA_STATS_BY_MUN acima). Usado pelo footer de
    # paginacao no frontend ("X paginas de Y empenhos") sem 1 query extra.
    empenhos_total = int(stats.get("qtd_empenhos") or 0) if stats else 0

    out = {
        "municipio": municipio,
        "municipio_slug": municipio_slug(municipio),
        "stats": stats,
        "monthly": monthly,
        "top_elementos": top_elementos,
        "empenhos": empenhos,
        "empenhos_total": empenhos_total,
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

    # Top 50 empenhos GLOBAIS (sem filtro de municipio) + count total.
    # Alimenta a primeira pagina da tabela paginada em /empresa/<cnpj>.
    # Pages 2+ ou filtros sao live via /api/empresa/empenhos. Cache key
    # global eh EMPRESA_PERFIL:<cnpj> — entries pre-deploy nao tem esses
    # campos, frontend lida com fallback (lazy fetch live ao mount).
    cur.execute(
        EMPRESA_EMPENHOS_PAGINATED_GLOBAL,
        {
            "cnpj_basico": cnpj_basico,
            "data_inicio": None, "data_fim": None,
            "q": None, "q_pat": None,
            "limit": 50, "offset": 0,
        },
    )
    eg_cols = [d[0] for d in cur.description]
    empenhos_global = [
        _convert_row(_row_to_dict(eg_cols, r)) for r in cur.fetchall()
    ]
    cur.execute(
        EMPRESA_EMPENHOS_COUNT_GLOBAL,
        {
            "cnpj_basico": cnpj_basico,
            "data_inicio": None, "data_fim": None,
            "q": None, "q_pat": None,
        },
    )
    cnt_row = cur.fetchone()
    empenhos_total_global = int(cnt_row[0]) if cnt_row else 0

    # TCE-PB DOE (ADR-0014): mv_empresa_tce_pb retorna 0 ou 1 row.
    # Empresas sem citacao recebem tce_pb=None (template oculta secao).
    tce_pb_doe = None
    try:
        cur.execute(EMPRESA_TCE_PB_DOE_BY_BASICO, (cnpj_basico,))
        tce_row = cur.fetchone()
        if tce_row:
            tce_cols = [d[0] for d in cur.description]
            tce_pb_doe = _convert_row(_row_to_dict(tce_cols, tce_row))
    except Exception:
        # MV pode nao existir ainda (deploy de schema antes do MV swap).
        # Falha silenciosa preserva backward compat.
        _log.warning("mv_empresa_tce_pb indisponivel para %s", cnpj_basico,
                     exc_info=True)

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
        "empenhos_global": empenhos_global,
        "empenhos_total_global": empenhos_total_global,
        "tce_pb_doe": tce_pb_doe,
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
        # Empenhos globais (top 50 + count) — pagina 1 da tabela
        # paginada em /empresa/<cnpj>. Adicionado no PR de paginacao;
        # entries pre-PR nao tem esses campos, frontend faz fallback live.
        "empenhos_global": cadastral.get("empenhos_global", []),
        "empenhos_total_global": cadastral.get("empenhos_total_global", 0),
        "tce_pb_doe": cadastral.get("tce_pb_doe"),
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
        "tce_pb_doe": cadastral.get("tce_pb_doe"),
        "municipios_pagantes": cadastral["municipios_pagantes"],
        # Pagamentos restritos ao municipio:
        "municipio": municipio,
        "municipio_slug": slug,
        "stats_municipio": stats,
        "monthly": pag["monthly"],
        "top_elementos": pag["top_elementos"],
        "empenhos": pag["empenhos"],
        # Total empenhos no municipio (count) — usado pra paginacao.
        # Adicionado no PR de paginacao; entries pre-PR cacheadas usam
        # fallback len(empenhos) no frontend (ate primeiro fetch live
        # popular total real).
        "empenhos_total": pag.get("empenhos_total") or qtd_no_mun,
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
    """Renderiza /empresa/<14-digits>. Le de web_cache.

    Resultado por cenario:
    - Cache hit -> 200 OK
    - Cache miss (row ausente) -> 410 Gone (URL permanentemente removida)
    - DB error -> 503 Retry-After (transiente, qualifying empresa pode
      estar com cache temporariamente inacessivel)

    NUNCA executa as 8 queries inline. O incidente do PR #57 mostrou que
    sob trafego de crawler agressivo (Bing + 45K URLs do IndexNow), o pool
    de DB exauria em segundos e levava o site inteiro junto. Cache-only +
    sitemap-after-warm garante que crawler so encontra URLs com cache
    quente.

    Cache miss retorna 410 (era 404 ate revisao 2026-05-18 do ADR-0009)
    porque Googlebot insistia ~6.7k re-crawls/dia em URLs orfas
    interpretando 404 como "talvez volte". 410 = "removido permanentemente",
    de-index em dias vs semanas.

    DB error retorna 503 (revisao 2026-05-19) — antes era tratado como
    cache miss permanente (410), marcando URLs legitimas como removidas
    durante pool exhaustion / restart / failover. Distincao usa sentinel
    CACHE_ERROR do read_web_cache.
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
    # cairiam em 404 mesmo apos warmer rodar (caught by GPT-5.5 review #58).
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
    if cached is CACHE_ERROR:
        # DB error transiente (pool exhausted, statement_timeout, conn drop).
        # Retornar 503 sinaliza ao crawler "tenta de novo" sem disparar
        # de-indexacao (diferente de 410, que Google trata como permanente).
        # Antes desta verificacao, `read_web_cache` retornava None em DB
        # errors (bare except: pass) e a rota tratava como cache miss
        # permanente -> 410, marcando URLs de empresas qualificadas como
        # removidas durante incidentes transientes do DB. (HIGH bug
        # convergente Opus 4.7-high + GPT-5.5 review PR #181.)
        _log.warning("DB error reading cache for /empresa/%s — returning 503", canonical)
        return Response(
            status_code=503,
            headers={"Retry-After": "60"},
            content="Servico temporariamente indisponivel.",
            media_type="text/plain; charset=utf-8",
        )
    if cached is not None:
        cols, rows = cached
        if rows and rows[0]:
            data = rows[0][0]
            if isinstance(data, dict) and data:
                return templates.TemplateResponse(
                    request, "results/empresa.html", data
                )

    # Cache miss. Pos-warm cycle + cleanup_orphan_empresa_cache (ADR-0009),
    # a tabela web_cache contem apenas CNPJs qualificados em mv_empresa_pb.
    # Miss aqui significa:
    #   (a) CNPJ inexistente (URL inventada ou digitada errada);
    #   (b) CNPJ orfao (foi removido do cache pelo cleanup pos-MV refresh
    #       que retirou empresas-fantasma contaminadas por CPF padded);
    #   (c) edge case raro: empresa nova entre warms (so visivel via
    #       sitemap apos proximo warm).
    # Em (a) e (b), 410 Gone e o codigo HTTP correto: a URL nao representa
    # (e nunca mais representara) um recurso valido no dominio PB. Em (c),
    # 410 pode causar de-index transiente de uma URL recem-criada, mas
    # como crawlers descobrem essas URLs via sitemap (que so lista apos
    # warm), o caso e improvavel e o efeito reverte no proximo crawl da
    # URL ja warmed.
    # Por que 410 e nao 404: observado em prod (18/May/2026) Googlebot
    # persistindo ~6.7k retries/dia em URLs orfas — 404 sinaliza
    # "talvez volte". 410 sinaliza "removido permanentemente" e Google
    # para de retentar em dias (vs semanas com 404).
    _log.info("cache miss /empresa/%s — returning 410 Gone (URL not in qualifying set)", canonical)
    return templates.TemplateResponse(
        request,
        "errors/404.html",
        {"path": str(request.url.path)},
        status_code=410,
    )


# slug_to_municipio() ja normaliza acentos/case e tolera hifens duplos.
# Nao precisamos validar regex aqui: lookup falha (None) eh suficiente
# pra rejeitar slug invalido com 404. (Ver fix P2 GPT-5.5 PR #62.)


@router.get("/empresa/{cnpj}/{municipio_slug_in}")
async def empresa_perfil_municipio(
    request: Request, cnpj: str, municipio_slug_in: str
):
    """Renderiza /empresa/<14-digits>/<municipio-slug>. Cache-only (mesmo
    invariant da rota global).

    Resultado por cenario:
    - Cache hit -> 200 OK
    - Cache miss (row ausente) -> 410 Gone
    - DB error -> 503 Retry-After
    - Slug invalido -> 404 (ANTES do lookup de cache)

    Validacoes em ordem:
    1. CNPJ canonico (14 digitos numericos puros, sem mascara).
    2. Filial (ordem != 0001) -> redireciona pra matriz preservando o slug.
    3. Slug municipio resolve via slug_to_municipio. None = 404.
    4. Slug nao canonico -> 301 pro slug canonico.
    5. Lookup web_cache(EMPRESA_PERFIL_MUN, "<cnpj>:<slug>"). Hit -> render.
       DB error -> 503. Miss -> 410.
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
    if cached is CACHE_ERROR:
        # DB error transiente — 503 em vez de 410 (ver docstring de
        # empresa_perfil acima e ADR-0009 revisao 2026-05-19).
        _log.warning(
            "DB error reading cache for /empresa/%s/%s — returning 503",
            canonical_cnpj, canonical_slug,
        )
        return Response(
            status_code=503,
            headers={"Retry-After": "60"},
            content="Servico temporariamente indisponivel.",
            media_type="text/plain; charset=utf-8",
        )
    if cached is not None:
        _cols, rows = cached
        if rows and rows[0]:
            data = rows[0][0]
            if isinstance(data, dict) and data:
                return templates.TemplateResponse(
                    request, "results/empresa_municipio.html", data
                )

    _log.info(
        "cache miss /empresa/%s/%s — returning 410 Gone (URL not in qualifying set)",
        canonical_cnpj, canonical_slug,
    )
    return templates.TemplateResponse(
        request,
        "errors/404.html",
        {"path": str(request.url.path)},
        status_code=410,
    )


# ─────────────────────────────────────────────────────────────────────────
# /api/empresa/empenhos — paginate + filtra empenhos. Live (5s timeout).
# Page 1 sem filtros eh servido pelo warmer cache (campo `empenhos` em
# EMPRESA_PERFIL/EMPRESA_PERFIL_MUN); frontend so chama este endpoint pra
# pages 2+ ou qualquer filtro. Sem cache server-side proprio: usuario que
# pagina/filtra geralmente vai ver dados unicos, baixa hit rate.
# ─────────────────────────────────────────────────────────────────────────


from fastapi import Body
from fastapi.responses import JSONResponse
from psycopg2.errors import QueryCanceled

# Limites do endpoint. Ver plan.md "Performance: limites e safeguards".
_PAGE_SIZE = 50
_API_TIMEOUT_SEC = 5
_Q_MIN_CHARS = 2
_Q_MAX_CHARS = 100


def _parse_iso_date_or_none(s: Any) -> str | None:
    """Aceita 'YYYY-MM-DD' valido OU retorna None.

    Validacao em 2 passos:
    1. Regex de shape (defensivo contra strings absurdas).
    2. `date.fromisoformat` pra rejeitar datas calendarial-mente
       impossiveis (ex: '2026-02-31') que passariam pelo regex mas
       quebrariam o cast `::date` em PG (-> 500).
    """
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return None
    try:
        from datetime import date as _date
        _date.fromisoformat(s)
    except ValueError:
        return None
    return s


def _parse_search_query_or_none(q: Any) -> tuple[str | None, str | None]:
    """Normaliza query de busca textual. Retorna (q_clean, q_pat) onde
    q_pat eh o pattern para ILIKE (com wildcards %). Min 2 chars, max
    100. Strings menores/vazias retornam (None, None) — query SQL
    simplifica via `%(q)s IS NULL OR ...`.
    """
    if q is None:
        return (None, None)
    s = str(q).strip()
    if len(s) < _Q_MIN_CHARS:
        return (None, None)
    if len(s) > _Q_MAX_CHARS:
        s = s[:_Q_MAX_CHARS]
    # Escape % e _ pra que o usuario nao injete wildcards (pode tornar
    # busca extremamente lenta sem retornar erros).
    escaped = s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pat = f"%{escaped}%"
    return (s, pat)


def _empenho_row_to_dict(row, cols):
    """Converte row do PG (Decimal/date) pra dict JSON-serializavel."""
    d = _row_to_dict(cols, row)
    return _convert_row(d)


@router.post("/api/empresa/empenhos")
async def get_empresa_empenhos(payload: dict = Body(...)):
    """Lista paginada de empenhos de uma empresa.

    Body:
        cnpj: 14 digitos (canonico). Obrigatorio.
        municipio: nome canonico do municipio (NAO slug). Opcional —
            None/vazio = visao global (todos os municipios).
        q: busca textual (min 2 chars). Opcional.
        data_inicio, data_fim: 'YYYY-MM-DD'. Opcional.
        page: 1-indexed. Default 1.

    Returns:
        {empenhos: [...], total: int, page: int, total_pages: int,
         page_size: int, scope: 'global'|'municipio'}

    Errors:
        400 cnpj invalido
        504 query timeout (mega-empresa + filtros pesados)
    """
    # Validacao
    cnpj_raw = "".join(ch for ch in str(payload.get("cnpj", "")) if ch.isdigit())
    if not _CNPJ_RE.fullmatch(cnpj_raw):
        return JSONResponse(
            {"error": "cnpj invalido (esperado 14 digitos)"}, status_code=400
        )
    cnpj_basico = cnpj_raw[:8]

    municipio = (payload.get("municipio") or "").strip() or None
    data_inicio = _parse_iso_date_or_none(payload.get("data_inicio"))
    data_fim = _parse_iso_date_or_none(payload.get("data_fim"))
    q_clean, q_pat = _parse_search_query_or_none(payload.get("q"))

    try:
        page = int(payload.get("page") or 1)
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1
    offset = (page - 1) * _PAGE_SIZE

    params = {
        "cnpj_basico": cnpj_basico,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "q": q_clean,
        "q_pat": q_pat,
        "limit": _PAGE_SIZE,
        "offset": offset,
    }
    if municipio:
        params["municipio"] = municipio
        list_sql = EMPRESA_EMPENHOS_PAGINATED_BY_MUN
        count_sql = EMPRESA_EMPENHOS_COUNT_BY_MUN
        scope = "municipio"
    else:
        list_sql = EMPRESA_EMPENHOS_PAGINATED_GLOBAL
        count_sql = EMPRESA_EMPENHOS_COUNT_GLOBAL
        scope = "global"

    try:
        with get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = '{_API_TIMEOUT_SEC * 1000}'")
                try:
                    cur.execute(list_sql, params)
                    cols = [d[0] for d in cur.description]
                    empenhos = [_empenho_row_to_dict(r, cols) for r in cur.fetchall()]

                    # Count com mesmos params (sem limit/offset)
                    count_params = {k: v for k, v in params.items()
                                    if k not in ("limit", "offset")}
                    cur.execute(count_sql, count_params)
                    cnt_row = cur.fetchone()
                    total = int(cnt_row[0]) if cnt_row else 0
                finally:
                    try:
                        cur.execute("RESET statement_timeout")
                    except Exception:
                        _log.warning("RESET statement_timeout falhou")
    except QueryCanceled:
        # Timeout — geralmente mega-empresa (BB/Caixa/INSS) com OFFSET
        # alto sem filtros. Frontend mostra mensagem amigavel.
        return JSONResponse(
            {
                "error": "timeout",
                "message": (
                    "A busca demorou muito. Use filtros (data ou texto) "
                    "para refinar."
                ),
            },
            status_code=504,
        )
    except Exception as exc:
        _log.exception("get_empresa_empenhos: %s", exc)
        return JSONResponse(
            {"error": "internal", "message": "Erro ao buscar empenhos."},
            status_code=500,
        )

    total_pages = (total + _PAGE_SIZE - 1) // _PAGE_SIZE if total > 0 else 0
    return {
        "empenhos": empenhos,
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "page_size": _PAGE_SIZE,
        "scope": scope,
    }
