"""Rota publica /empresa/{cnpj} — perfil SEO de empresa.

Renderiza pagina indexavel com cadastro RFB, sancoes, dividas, agregados
de pagamentos publicos PB e municipios pagantes. Reaproveita as queries
de web.queries.empresa (mesma fonte que o dialog usa em cidade.py).

URL: /empresa/<14-digitos>. CNPJ formatado com mascara redireciona via
404; entrada deve ser 14 digitos numericos puros (canonical).
"""

from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from web.config import TIMEOUT_PROFILE
from web.db import execute_query, get_conn
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


@router.get("/empresa/{cnpj}")
async def empresa_perfil(request: Request, cnpj: str):
    """Renderiza /empresa/<14-digits>. Redireciona para forma canonica
    (14 digitos puros) se a entrada veio com mascara/pontos.
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

    cnpj_basico = canonical[:8]
    cnpj_ordem = canonical[8:12]

    try:
        # 1. Agregados PB (mv_empresa_pb) — chave: cnpj_basico.
        # Se a empresa nao esta na MV, nao tem dados PB -> 404.
        try:
            agg_cols, agg_rows = execute_query(
                EMPRESA_AGREGADOS_PB_BY_BASICO,
                (cnpj_basico,),
                timeout_sec=TIMEOUT_PROFILE,
            )
        except Exception:
            # DB indisponivel: 503 transitorio (nao 404, pra evitar deindex).
            return Response(
                status_code=503,
                headers={"Retry-After": "300"},
                content="Servico temporariamente indisponivel. Tente novamente em alguns minutos.",
                media_type="text/plain; charset=utf-8",
            )

        if not agg_rows:
            return templates.TemplateResponse(
                request,
                "errors/404.html",
                {"path": str(request.url.path)},
                status_code=404,
            )

        agregados = _convert_row(_row_to_dict(agg_cols, agg_rows[0]))

        # 2. Cadastro RFB (estabelecimento + empresa) — chave: cnpj_completo.
        # Detalhes (sancoes/divida/leniencia/pagamentos) sao consultados POR
        # CNPJ_BASICO (8 digitos) pra coerencia com mv_empresa_pb que agrega
        # por basico. URL e canonicalizada com 14 digitos da matriz mas a
        # pagina representa a empresa raiz.
        with get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(f"SET statement_timeout = '{TIMEOUT_PROFILE * 1000}'")
                # try/finally: garante RESET statement_timeout em qualquer
                # caminho (404 cedo, exception, ou sucesso). Sem isso, a
                # config de sessao vaza pra proxima request que pegar a
                # mesma conexao do pool, podendo quebrar queries pesadas
                # de outros endpoints. (Caught by GPT-5.5 review do PR #57.)
                try:
                    cur.execute(EMPRESA_ESTABELECIMENTO_BY_CNPJ_COMPLETO, (canonical,))
                    est_cols = [d[0] for d in cur.description]
                    est_rows = cur.fetchall()
                    if not est_rows:
                        return templates.TemplateResponse(
                            request,
                            "errors/404.html",
                            {"path": str(request.url.path)},
                            status_code=404,
                        )
                    estabelecimento = _convert_row(_row_to_dict(est_cols, est_rows[0]))

                    # 3. Matriz (se a entidade nao for ela propria a matriz)
                    matriz = None
                    if cnpj_ordem != "0001":
                        cur.execute(EMPRESA_MATRIZ_BY_BASICO, (cnpj_basico,))
                        mat_cols = [d[0] for d in cur.description]
                        mat_row = cur.fetchone()
                        if mat_row:
                            matriz = _convert_row(_row_to_dict(mat_cols, mat_row))

                    # 4. Socios
                    cur.execute(EMPRESA_SOCIOS_BY_BASICO, (cnpj_basico,))
                    soc_cols = [d[0] for d in cur.description]
                    socios = [
                        _convert_row(_row_to_dict(soc_cols, r))
                        for r in cur.fetchall()
                    ]

                    # 5. Sancoes CEIS + CNEP (por basico, todos estabelecimentos)
                    cur.execute(EMPRESA_SANCOES_CEIS_BY_BASICO, (cnpj_basico,))
                    ceis_cols = [d[0] for d in cur.description]
                    sancoes = []
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

                    # 6. PGFN (por basico)
                    cur.execute(EMPRESA_PGFN_BY_BASICO, (cnpj_basico,))
                    pg_cols = [d[0] for d in cur.description]
                    pgfn = [
                        _convert_row(_row_to_dict(pg_cols, r))
                        for r in cur.fetchall()
                    ]

                    # 7. Acordos de Leniencia + efeitos (por basico)
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

                    # 8. Municipios pagantes (PB) + top elementos (por basico)
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
                        # se conexao ja foi marcada como aborted, RESET
                        # falha — tolerar porque putconn vai descartar a
                        # conexao corrompida em vez de devolver ao pool.
                        _log.warning(
                            "RESET statement_timeout falhou (conexao "
                            "provavelmente sera descartada pelo pool)"
                        )
    except Exception:
        _log.exception("empresa perfil failed cnpj=%s", canonical)
        return Response(
            status_code=503,
            headers={"Retry-After": "300"},
            content="Servico temporariamente indisponivel. Tente novamente em alguns minutos.",
            media_type="text/plain; charset=utf-8",
        )

    razao_social = (
        estabelecimento.get("razao_social")
        or agregados.get("razao_social")
        or estabelecimento.get("nome_fantasia")
        or f"Empresa {cnpj_basico}"
    )
    cnpj_fmt = _format_cnpj(canonical)
    total_pb_geral = float(agregados.get("total_pb_geral") or 0)
    qtd_municipios = len(municipios_pagantes)
    qtd_empenhos_pb = int(agregados.get("qtd_tce_empenhos") or 0) + int(
        agregados.get("qtd_pb_empenhos") or 0
    )
    sancoes_vigentes = sum(
        1
        for s in sancoes
        if not s.get("dt_final_sancao")
        or str(s.get("dt_final_sancao")) >= "1900-01-01"  # placeholder; UI usa data
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

    return templates.TemplateResponse(
        request,
        "results/empresa.html",
        {
            "cnpj": canonical,
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
        },
    )
