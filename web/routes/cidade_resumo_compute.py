"""Pipeline de computacao do resumo mensal /cidade/<slug>/<yyyy>-<mm>.

Chamado APENAS pelo warmer (web/warm_cache.py). Nao chamar da rota
(cache-only invariant).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from web.config import TIMEOUT_PROFILE
from web.db import get_conn
from web.queries.cidade_resumo import (
    RESUMO_AGGS_MES,
    RESUMO_COMPARATIVO,
    RESUMO_MODALIDADES,
    RESUMO_TOP_ELEMENTOS,
    RESUMO_TOP_EMPENHOS,
    RESUMO_TOP_FORNECEDORES,
    RESUMO_TOP_LICITACOES,
)
from web.utils.slug import format_yyyymm, municipio_slug, numero_slug

_log = logging.getLogger("transparencia.cidade_resumo")


class CidadeResumoEmpty(Exception):
    """Mes sem empenhos pagos > 0 para esse municipio."""


_MESES_PT = [
    "", "janeiro", "fevereiro", "marco", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _row_to_dict(cols, row):
    return dict(zip(cols, row))


def _convert(value):
    if hasattr(value, "as_tuple"):
        return float(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _convert_row(d: dict) -> dict:
    return {k: _convert(v) for k, v in d.items()}


def _prev_month(yyyy: int, mm: int) -> tuple[int, int]:
    if mm == 1:
        return yyyy - 1, 12
    return yyyy, mm - 1


def _build_meta_description(
    municipio: str, yyyy: int, mm: int,
    aggs: dict, top_forn: list,
) -> str:
    """Meta description rica + factual."""
    mes_nome = _MESES_PT[mm].capitalize()
    parts = [
        f"Gastos publicos de {municipio}/PB em {mes_nome} de {yyyy}."
    ]
    total_pago = float(aggs.get("total_pago") or 0)
    qtd_emp = int(aggs.get("qtd_empenhos") or 0)
    if total_pago > 0:
        parts.append(f"Total pago: R$ {total_pago:,.0f}".replace(",", "."))
    if qtd_emp > 0:
        parts.append(f"{qtd_emp} empenhos.")
    if top_forn:
        top1 = top_forn[0]
        parts.append(f"Maior fornecedor: {top1.get('razao_social', '')}.")
    return " ".join(parts)[:300]


def compute_cidade_resumo_dict(
    municipio: str,
    yyyy: int,
    mm: int,
    timeout_sec: int = TIMEOUT_PROFILE,
) -> dict[str, Any]:
    """Executa as queries do resumo mensal e monta dict pro template/cache.

    Raises:
        CidadeResumoEmpty: se nao ha empenhos pagos > 0 no mes. Caller
            decide entre nao-cachear ou cachear com flag noindex.
    """
    if not municipio:
        raise CidadeResumoEmpty(f"municipio vazio para {yyyy}-{mm}")
    if not (1 <= mm <= 12):
        raise CidadeResumoEmpty(f"mes invalido: {mm}")
    if not (2018 <= yyyy <= 2099):
        raise CidadeResumoEmpty(f"ano invalido: {yyyy}")

    params = {"municipio": municipio, "ano": yyyy, "mes": mm}

    # Comparativos
    prev_yr_y, prev_yr_m = yyyy - 1, mm
    prev_mes_y, prev_mes_m = _prev_month(yyyy, mm)
    comp_params = {
        "municipio": municipio,
        "ano_prev_mes": prev_mes_y, "mes_prev_mes": prev_mes_m,
        "ano_prev_yr": prev_yr_y, "mes_prev_yr": prev_yr_m,
    }

    with get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{timeout_sec * 1000}'")
            try:
                # 1. KPIs hero
                cur.execute(RESUMO_AGGS_MES, params)
                a_cols = [d[0] for d in cur.description]
                a_row = cur.fetchone()
                aggs = _convert_row(_row_to_dict(a_cols, a_row)) if a_row else {}

                qtd_emp = int(aggs.get("qtd_empenhos") or 0)
                if qtd_emp == 0:
                    raise CidadeResumoEmpty(
                        f"sem empenhos: {municipio} em {yyyy}-{mm:02d}"
                    )

                # 2. Top fornecedores
                cur.execute(RESUMO_TOP_FORNECEDORES, params)
                tf_cols = [d[0] for d in cur.description]
                top_fornecedores = [
                    _convert_row(_row_to_dict(tf_cols, r)) for r in cur.fetchall()
                ]

                # 3. Top elementos
                cur.execute(RESUMO_TOP_ELEMENTOS, params)
                te_cols = [d[0] for d in cur.description]
                top_elementos = [
                    _convert_row(_row_to_dict(te_cols, r)) for r in cur.fetchall()
                ]

                # 4. Modalidades
                cur.execute(RESUMO_MODALIDADES, params)
                mo_cols = [d[0] for d in cur.description]
                modalidades = [
                    _convert_row(_row_to_dict(mo_cols, r)) for r in cur.fetchall()
                ]

                # 5. Top empenhos (PJ-only)
                cur.execute(RESUMO_TOP_EMPENHOS, params)
                em_cols = [d[0] for d in cur.description]
                top_empenhos = [
                    _convert_row(_row_to_dict(em_cols, r)) for r in cur.fetchall()
                ]

                # 6. Top licitacoes
                cur.execute(RESUMO_TOP_LICITACOES, params)
                tl_cols = [d[0] for d in cur.description]
                top_licitacoes = [
                    _convert_row(_row_to_dict(tl_cols, r)) for r in cur.fetchall()
                ]
                # Adicionar slugs canonicos pra link
                for lic in top_licitacoes:
                    mod = lic.get("modalidade") or ""
                    num = lic.get("numero_licitacao") or ""
                    ug = lic.get("descricao_ug") or ""
                    lic["mod_num_slug"] = f"{numero_slug(mod) or 'lic'}-{numero_slug(num) or '0'}"
                    lic["ug_slug"] = numero_slug(ug) or "prefeitura"

                # 7. Comparativo
                cur.execute(RESUMO_COMPARATIVO, comp_params)
                cp_cols = [d[0] for d in cur.description]
                cp_row = cur.fetchone()
                comparativo = _convert_row(_row_to_dict(cp_cols, cp_row)) if cp_row else {}
            finally:
                try:
                    cur.execute("RESET statement_timeout")
                except Exception:
                    _log.warning("RESET statement_timeout falhou")

    mun_slug_canonical = municipio_slug(municipio)
    yyyymm = format_yyyymm(yyyy, mm)

    # Deltas %
    total_atual = float(aggs.get("total_pago") or 0)
    total_mes_ant = float(comparativo.get("total_mes_anterior") or 0)
    total_ano_ant = float(comparativo.get("total_mesmo_mes_ano_anterior") or 0)
    delta_mes_ant_pct = None
    if total_mes_ant > 0:
        delta_mes_ant_pct = ((total_atual - total_mes_ant) / total_mes_ant) * 100.0
    delta_ano_ant_pct = None
    if total_ano_ant > 0:
        delta_ano_ant_pct = ((total_atual - total_ano_ant) / total_ano_ant) * 100.0

    meta_description = _build_meta_description(
        municipio, yyyy, mm, aggs, top_fornecedores
    )

    return {
        # Identificacao
        "municipio": municipio,
        "municipio_slug": mun_slug_canonical,
        "ano": yyyy,
        "mes": mm,
        "yyyymm": yyyymm,
        "mes_nome": _MESES_PT[mm],
        "mes_nome_cap": _MESES_PT[mm].capitalize(),
        "ano_anterior": prev_yr_y,
        "mes_anterior_y": prev_mes_y,
        "mes_anterior_m": prev_mes_m,
        "mes_anterior_yyyymm": format_yyyymm(prev_mes_y, prev_mes_m),
        # KPIs agregados
        "aggs": aggs,
        "comparativo": comparativo,
        "delta_mes_ant_pct": delta_mes_ant_pct,
        "delta_ano_ant_pct": delta_ano_ant_pct,
        # Listas
        "top_fornecedores": top_fornecedores,
        "top_elementos": top_elementos,
        "modalidades": modalidades,
        "top_empenhos": top_empenhos,
        "top_licitacoes": top_licitacoes,
        # SEO
        "meta_description": meta_description,
        "scope": "cidade_resumo",
    }
