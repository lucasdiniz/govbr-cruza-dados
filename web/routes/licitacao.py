"""Rota publica /licitacao/<mun-slug>/<ano>/<ug-slug>/<modalidade-num-slug>
— perfil SEO de licitacao publica TCE-PB.

ARQUITETURA cache-only (mirror de /empresa, mesma motivacao do PR #57):
- Rota le de web_cache (chave LICITACAO_PERFIL:<canonical-path>) e renderiza.
- Cache miss = 503 com Retry-After (NAO faz live query — sob trafego de
  crawler agressivo, pool exauria). Cache-miss-only e seguro porque
  licitacoes so entram no sitemap depois de warmed.
- A funcao `compute_licitacao_dict` executa as queries e monta o dict.
  Eh chamada APENAS pelo warmer (web/warm_cache.py), nunca inline.

URL canonica: 5 segmentos garantem unicidade absoluta:
  /licitacao/<mun-slug>/<ano>/<ug-slug>/<modalidade-num-slug>

  Onde:
    - mun-slug: municipio_slug(nome canonico do municipio)
    - ano: 4 digitos (2018-2099)
    - ug-slug: slug do descricao_ug ("secretaria-municipal-de-saude")
    - modalidade-num-slug: f"{numero_slug(modalidade)}-{numero_slug(numero)}"

Cache key idem: "{mun_slug}:{ano}:{ug_slug}:{modalidade_num_slug}".

LGPD: filtragem PJ-only via REGEXP no warm SQL. Layer 2 no template:
proponente sem JOIN em estabelecimento e omitido.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

from web.config import TIMEOUT_PROFILE, TIMEOUT_PROFILE_WARM
from web.db import execute_query, get_conn, read_web_cache
from web.queries.licitacao import (
    LICITACAO_DETAIL,
    LICITACAO_EMPENHOS_VINCULADOS,
    LICITACAO_OUTRAS_MESMA_MODALIDADE,
    LICITACAO_OUTRAS_MESMO_ORGAO,
    LICITACAO_PROPONENTES,
)
from web.utils.pii_scrub import scrub_pii
from web.utils.slug import (
    SlugLookupError,
    all_municipios_slugged,
    municipio_slug,
    numero_slug,
    slug_to_municipio,
)

router = APIRouter()
_log = logging.getLogger("transparencia.licitacao")

# Chave canonica usada em web_cache. Warmer e rota DEVEM usar exatamente
# esta string. Mudancas exigem invalidar o cache existente.
CACHE_QUERY_ID = "LICITACAO_PERFIL"


# ─────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────


_ANO_RE = re.compile(r"^(20[1-9][0-9])$")  # 2010-2099


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


def _build_cache_key(mun_slug: str, ano: int, ug_slug: str, mod_num_slug: str) -> str:
    """Constroi a cache key canonica. Mesma string usada pelo warmer."""
    return f"{mun_slug}:{ano}:{ug_slug}:{mod_num_slug}"


def _build_mod_num_slug(modalidade: str, numero_licitacao: str) -> str:
    """Junta modalidade-slug + numero-slug no formato canonico."""
    mod = numero_slug(modalidade) or "lic"
    num = numero_slug(numero_licitacao) or "0"
    return f"{mod}-{num}"


# ─────────────────────────────────────────────────────────────────────────
# Compute pipeline (chamado APENAS pelo warmer)
# ─────────────────────────────────────────────────────────────────────────


class LicitacaoNotFoundError(Exception):
    """Licitacao nao existe na 5-tupla canonica OU nao tem proponente PJ qualificado."""


def _build_meta_description(detail: dict, proponentes: list, empenhos: list) -> str:
    """Meta description rica + factual."""
    mun = detail.get("municipio", "")
    modalidade = detail.get("modalidade", "")
    num = detail.get("numero_licitacao", "")
    ano = detail.get("ano_licitacao", "")
    objeto = (detail.get("objeto_licitacao") or "").strip()
    if len(objeto) > 100:
        objeto = objeto[:97].rstrip() + "..."
    parts = [f"Licitacao {modalidade} {num}/{ano} em {mun}/PB."]
    if objeto:
        parts.append(f"Objeto: {objeto}")
    if proponentes:
        parts.append(f"{len(proponentes)} proponente(s).")
    total_pago = sum(float(e.get("valor_pago") or 0) for e in empenhos)
    if total_pago > 0:
        parts.append(f"R$ {total_pago:,.0f} pagos".replace(",", "."))
    return " ".join(parts)[:300]


def compute_licitacao_dict(
    municipio: str,
    ano: int,
    codigo_ug: str,
    modalidade: str,
    numero_licitacao: str,
    timeout_sec: int = TIMEOUT_PROFILE,
) -> dict[str, Any]:
    """Executa queries e monta dict pra template + cache.

    Args:
        municipio: nome canonico do municipio (NAO slug).
        ano: ano_licitacao SMALLINT.
        codigo_ug: codigo_ug VARCHAR exato.
        modalidade: modalidade TEXT exato.
        numero_licitacao: numero_licitacao VARCHAR exato.
        timeout_sec: statement_timeout. Default TIMEOUT_PROFILE (3s) pro
            route inline (nao chamado); warmer usa TIMEOUT_PROFILE_WARM (600s).

    Raises:
        LicitacaoNotFoundError: se nao casa nenhuma row OR sem proponente PJ.
    """
    params = {
        "municipio": municipio,
        "ano": ano,
        "codigo_ug": codigo_ug,
        "modalidade": modalidade,
        "numero_licitacao": numero_licitacao,
    }

    with get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = '{timeout_sec * 1000}'")
            try:
                # 1. Metadata
                cur.execute(LICITACAO_DETAIL, params)
                det_cols = [d[0] for d in cur.description]
                det_row = cur.fetchone()
                if not det_row:
                    raise LicitacaoNotFoundError(
                        f"Licitacao nao encontrada: {municipio}/{ano}/{codigo_ug}/{modalidade}/{numero_licitacao}"
                    )
                detail = _convert_row(_row_to_dict(det_cols, det_row))
                # Scrub PII de texto livre antes de cachear (P1 GPT 5.5).
                # objeto_licitacao eh TEXT digitado por servidor TCE — pode
                # conter CPF/RG/email/tel embedded mesmo quando a licitacao
                # eh PJ. Aplicado AQUI pra cache ficar limpo.
                if detail.get("objeto_licitacao"):
                    detail["objeto_licitacao"] = scrub_pii(detail["objeto_licitacao"])

                # 2. Proponentes (apenas PJ via inline regex + JOIN estabelecimento)
                cur.execute(LICITACAO_PROPONENTES, params)
                prop_cols = [d[0] for d in cur.description]
                proponentes = [
                    _convert_row(_row_to_dict(prop_cols, r)) for r in cur.fetchall()
                ]

                if not proponentes:
                    # Sem proponente PJ qualificado — nao deve estar no sitemap
                    raise LicitacaoNotFoundError(
                        f"Licitacao sem proponente PJ qualificado: {numero_licitacao}/{ano}"
                    )

                # 3. Empenhos vinculados (top 50, PJ only)
                cur.execute(LICITACAO_EMPENHOS_VINCULADOS, params)
                emp_cols = [d[0] for d in cur.description]
                empenhos = [
                    _convert_row(_row_to_dict(emp_cols, r)) for r in cur.fetchall()
                ]

                # 4. Outras licitacoes do mesmo orgao (sidebar)
                cur.execute(LICITACAO_OUTRAS_MESMO_ORGAO, params)
                or_cols = [d[0] for d in cur.description]
                outras_orgao = [
                    _convert_row(_row_to_dict(or_cols, r)) for r in cur.fetchall()
                ]
                for o in outras_orgao:
                    o["mod_num_slug"] = _build_mod_num_slug(
                        o.get("modalidade") or "", o.get("numero_licitacao") or ""
                    )
                    # ug_slug per row (P2 Opus PR #108) — antes herdava
                    # ug_slug da pagina pai, gerando 503 quando descricao_ug
                    # textual variava entre rows do mesmo codigo_ug.
                    o["ug_slug"] = numero_slug(o.get("descricao_ug") or "") or "prefeitura"
                    # Scrub objeto_licitacao (texto livre).
                    if o.get("objeto_licitacao"):
                        o["objeto_licitacao"] = scrub_pii(o["objeto_licitacao"])

                # 5. Outras licitacoes da mesma modalidade no municipio
                cur.execute(LICITACAO_OUTRAS_MESMA_MODALIDADE, params)
                om_cols = [d[0] for d in cur.description]
                outras_modalidade = [
                    _convert_row(_row_to_dict(om_cols, r)) for r in cur.fetchall()
                ]
                for o in outras_modalidade:
                    o["mod_num_slug"] = _build_mod_num_slug(
                        o.get("modalidade") or "", o.get("numero_licitacao") or ""
                    )
                    o["ug_slug"] = numero_slug(o.get("descricao_ug") or "") or "prefeitura"
                    if o.get("objeto_licitacao"):
                        o["objeto_licitacao"] = scrub_pii(o["objeto_licitacao"])
            finally:
                try:
                    cur.execute("RESET statement_timeout")
                except Exception:
                    _log.warning("RESET statement_timeout falhou")

    # Total contratado (do vencedor): proponente com maior valor_ofertado.
    vencedor = proponentes[0] if proponentes else None
    valor_contratado = float(vencedor.get("valor_ofertado") or 0) if vencedor else 0.0
    valor_pago_total = sum(float(e.get("valor_pago") or 0) for e in empenhos)
    valor_empenhado_total = sum(float(e.get("valor_empenhado") or 0) for e in empenhos)

    mun_slug = municipio_slug(municipio)
    ug_slug_canonical = numero_slug(detail.get("descricao_ug") or "") or "prefeitura"
    mod_num_slug = _build_mod_num_slug(modalidade, numero_licitacao)

    meta_description = _build_meta_description(detail, proponentes, empenhos)

    return {
        # Identificacao canonica
        "municipio": municipio,
        "municipio_slug": mun_slug,
        "ano": ano,
        "codigo_ug": codigo_ug,
        "ug_slug": ug_slug_canonical,
        "modalidade": modalidade,
        "numero_licitacao": numero_licitacao,
        "mod_num_slug": mod_num_slug,
        # Dados principais
        "detail": detail,
        "proponentes": proponentes,
        "empenhos": empenhos,
        "outras_orgao": outras_orgao,
        "outras_modalidade": outras_modalidade,
        # KPIs derivados
        "vencedor": vencedor,
        "valor_contratado": valor_contratado,
        "valor_pago_total": valor_pago_total,
        "valor_empenhado_total": valor_empenhado_total,
        # SEO
        "meta_description": meta_description,
        "scope": "licitacao",
    }


# ─────────────────────────────────────────────────────────────────────────
# Rota — cache-only
# ─────────────────────────────────────────────────────────────────────────


@router.get("/licitacao/{mun_slug}/{ano}/{ug_slug}/{mod_num_slug}")
async def licitacao_perfil(
    request: Request,
    mun_slug: str,
    ano: str,
    ug_slug: str,
    mod_num_slug: str,
):
    """Renderiza pagina de licitacao. Cache-only. Miss = 503."""
    from web.main import templates

    # Validacao ano
    if not _ANO_RE.fullmatch(ano):
        return templates.TemplateResponse(
            request,
            "errors/404.html",
            {"path": str(request.url.path)},
            status_code=404,
        )

    # Resolve mun_slug → nome canonico
    try:
        municipio_nome = slug_to_municipio(mun_slug)
    except SlugLookupError:
        return Response(
            status_code=503,
            headers={"Retry-After": "60"},
            content="Cache de slugs indisponivel. Tente novamente.",
            media_type="text/plain; charset=utf-8",
        )
    if not municipio_nome:
        return templates.TemplateResponse(
            request,
            "errors/404.html",
            {"path": str(request.url.path)},
            status_code=404,
        )

    # Slug nao canonico → 301
    canonical_mun_slug = municipio_slug(municipio_nome)
    if canonical_mun_slug and canonical_mun_slug != mun_slug:
        return RedirectResponse(
            url=f"/licitacao/{canonical_mun_slug}/{ano}/{ug_slug}/{mod_num_slug}",
            status_code=301,
        )

    # Validacao basica de slug segments (rejeita injection cedo)
    if not re.fullmatch(r"[a-z0-9-]+", ug_slug):
        return templates.TemplateResponse(
            request,
            "errors/404.html",
            {"path": str(request.url.path)},
            status_code=404,
        )
    if not re.fullmatch(r"[a-z0-9-]+", mod_num_slug):
        return templates.TemplateResponse(
            request,
            "errors/404.html",
            {"path": str(request.url.path)},
            status_code=404,
        )

    # Lookup no web_cache
    cache_key = _build_cache_key(canonical_mun_slug, int(ano), ug_slug, mod_num_slug)
    cached = read_web_cache(CACHE_QUERY_ID, cache_key)
    if cached is not None:
        cols, rows = cached
        if rows and rows[0]:
            data = rows[0][0]
            if isinstance(data, dict) and data:
                return templates.TemplateResponse(
                    request, "results/licitacao.html", data
                )

    # Cache miss
    _log.info("cache miss /licitacao/%s — returning 503", cache_key)
    return Response(
        status_code=503,
        headers={"Retry-After": "3600"},
        content=(
            "Licitacao em construcao — esta pagina ainda nao foi pre-processada. "
            "Tente novamente mais tarde."
        ),
        media_type="text/plain; charset=utf-8",
    )
