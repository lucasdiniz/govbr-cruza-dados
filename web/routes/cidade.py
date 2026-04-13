"""Rotas do modo cidade."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from psycopg2.errors import QueryCanceled, UndefinedTable

from web.config import (
    LIMIT_AUTOCOMPLETE,
    TIMEOUT_AUTOCOMPLETE,
    TIMEOUT_COUNT,
    TIMEOUT_PROFILE,
    TIMEOUT_QUERY_LIGHT,
)
from web.db import cached_query, execute_query, read_web_cache
from web.queries.cidade import (
    AUTOCOMPLETE_MUNICIPIO,
    PERFIL_MUNICIPIO,
    PERFIL_MUNICIPIO_PNCP,
    TOP_FORNECEDORES,
    TOP_FORNECEDORES_BASIC,
    TOP_FORNECEDORES_FALLBACK,
    TOP_FORNECEDORES_PNCP,
    TOP_SERVIDORES_RISCO,
)
from web.queries.registry import CIDADE_QUERIES, get_categories

router = APIRouter()

SECTION_META = {
    "Conflito de Interesses": {
        "slug": "conflitos",
        "title": "Possiveis conflitos de interesse",
        "description": "Situacoes em que servidores, empresas contratadas e pagamentos publicos podem estar relacionados de forma inadequada.",
    },
    "Licitacao e Concorrencia": {
        "slug": "licitacoes",
        "title": "Sinais em compras e licitacoes",
        "description": "Padroes que podem indicar baixa concorrencia, direcionamento ou concentracao anormal de contratos.",
    },
    "Fornecedores Irregulares": {
        "slug": "fornecedores-irregulares",
        "title": "Fornecedores com sinais de irregularidade",
        "description": "Empresas com sancoes, dividas ou situacao cadastral irregular que aparecem recebendo recursos do municipio.",
    },
    "Orcamento e Financeiro": {
        "slug": "orcamento",
        "title": "Execucao orcamentaria e financeira",
        "description": "Desvios entre o que foi empenhado, contratado e efetivamente pago, alem de concentracoes atipicas de despesas.",
    },
    "Politico-Eleitoral": {
        "slug": "politico-eleitoral",
        "title": "Relacoes politico-eleitorais",
        "description": "Cruzes entre doacoes de campanha, beneficios sociais e pagamentos publicos que merecem verificacao.",
    },
    "Cruzamento Estado x Municipio": {
        "slug": "estado-municipio",
        "title": "Relacoes entre estado e municipio",
        "description": "Achados que conectam contratos estaduais e despesas municipais com os mesmos atores ou periodos.",
    },
}


class MunicipioPayload(BaseModel):
    municipio: str
    uf: str = ""


def _row_to_dict(cols, row):
    return dict(zip(cols, row))


def _normalize_municipio(value: str) -> str:
    return " ".join(value.strip().split())


def _parse_municipio_uf(raw: str) -> tuple[str, str]:
    """Parse 'Municipio - UF' format. Returns (municipio, uf)."""
    raw = _normalize_municipio(raw)
    if " - " in raw and len(raw.split(" - ")[-1]) == 2:
        parts = raw.rsplit(" - ", 1)
        return parts[0].strip(), parts[1].strip().upper()
    return raw, ""


def _is_pb(uf: str) -> bool:
    return uf == "" or uf == "PB"


def _load_top_fornecedores(municipio: str, uf: str = ""):
    if not _is_pb(uf):
        return _load_top_fornecedores_pncp(municipio, uf)
    try:
        return cached_query(
            f"forn:{municipio}",
            TOP_FORNECEDORES,
            {"municipio": municipio},
            timeout_sec=TIMEOUT_QUERY_LIGHT,
        )
    except (UndefinedTable, QueryCanceled):
        try:
            return cached_query(
                f"fornfb:{municipio}",
                TOP_FORNECEDORES_FALLBACK,
                {"municipio": municipio},
                timeout_sec=TIMEOUT_QUERY_LIGHT,
            )
        except QueryCanceled:
            try:
                return cached_query(
                    f"fornbasic:{municipio}",
                    TOP_FORNECEDORES_BASIC,
                    {"municipio": municipio},
                    timeout_sec=TIMEOUT_PROFILE + 2,
                )
            except QueryCanceled:
                return ["cnpj_basico", "nome_credor", "total_pago", "qtd_empenhos", "flag_ceis", "flag_pgfn", "flag_inativa"], []


def _load_top_fornecedores_pncp(municipio: str, uf: str):
    try:
        return cached_query(
            f"fornpncp:{uf}:{municipio}",
            TOP_FORNECEDORES_PNCP,
            {"municipio": municipio, "uf": uf},
            timeout_sec=TIMEOUT_QUERY_LIGHT,
        )
    except QueryCanceled:
        return ["cnpj_basico", "nome_credor", "total_contratado", "qtd_contratos", "flag_ceis", "flag_pgfn", "flag_inativa"], []


def _load_top_servidores(municipio: str):
    try:
        return cached_query(
            f"serv:{municipio.casefold()}",
            TOP_SERVIDORES_RISCO,
            {"municipio": municipio},
            timeout_sec=TIMEOUT_QUERY_LIGHT,
        )
    except QueryCanceled:
        return [
            "cpf_digitos_6", "nome_upper", "nome_servidor",
            "municipios", "maior_salario", "cargo",
            "qtd_empresas_socio", "cnpjs_socio",
            "flag_conflito_interesses", "flag_multi_empresa",
            "flag_bolsa_familia", "flag_duplo_vinculo_estado",
            "flag_alto_salario_socio", "risco_score",
        ], []


def _get_query_def(query_id: str):
    query_def = CIDADE_QUERIES.get(query_id.upper())
    if query_def is None:
        raise KeyError(query_id)
    return query_def


def _build_report_sections(pb_only: bool = True):
    sections = []
    for category, queries in get_categories():
        meta = SECTION_META[category]
        sections.append(
            {
                "slug": meta["slug"],
                "title": meta["title"],
                "description": meta["description"],
                "queries": queries,
            }
        )
    return sections


def _render_result_table(request: Request, title: str, cols: list[str], rows: list[tuple]):
    from web.main import templates

    items = [_row_to_dict(cols, row) for row in rows]
    response = templates.TemplateResponse(
        request,
        "partials/result_table.html",
        {
            "title": title,
            "columns": cols,
            "rows": items,
        },
    )
    response.headers["X-Row-Count"] = str(len(items))
    return response


def _csv_response(filename: str, cols: list[str], rows: list[tuple]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(cols)
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    data = "\ufeff" + buffer.getvalue()
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(data, media_type="text/csv; charset=utf-8", headers=headers)


def _render_partial(request: Request, template_name: str, context: dict):
    from web.main import templates

    return templates.TemplateResponse(request, template_name, context)


@router.get("/search/cidade")
async def search_cidade(request: Request, q: str = Query(..., min_length=2)):
    from web.main import templates

    municipio, uf = _parse_municipio_uf(q)
    is_pb = _is_pb(uf)

    perfil = None
    if is_pb:
        try:
            cached = read_web_cache("PERFIL", municipio)
            if cached:
                cols, rows = cached
            else:
                cols, rows = cached_query(
                    f"perfil:{municipio.casefold()}",
                    PERFIL_MUNICIPIO,
                    {"municipio": municipio},
                    timeout_sec=TIMEOUT_PROFILE,
                )
            perfil = _row_to_dict(cols, rows[0]) if rows else None
        except (QueryCanceled, Exception):
            perfil = None
    else:
        # Non-PB: build profile from PNCP data
        try:
            cols, rows = cached_query(
                f"perfil_pncp:{uf}:{municipio.casefold()}",
                PERFIL_MUNICIPIO_PNCP,
                {"municipio": municipio, "uf": uf},
                timeout_sec=TIMEOUT_PROFILE,
            )
            if rows and rows[0][1]:  # qtd_contratos > 0
                perfil = _row_to_dict(cols, rows[0])
                # Add uf to perfil for template
                perfil["uf"] = uf
                perfil["is_pncp"] = True
        except (QueryCanceled, Exception):
            perfil = None

    if not perfil:
        return templates.TemplateResponse(
            request,
            "results/cidade.html",
            {
                "municipio": municipio,
                "uf": uf,
                "perfil": None,
                "fornecedores": [],
                "servidores": [],
                "report_sections": [],
            },
        )

    return templates.TemplateResponse(
        request,
        "results/cidade.html",
        {
            "municipio": municipio,
            "uf": uf,
            "perfil": perfil,
            "fornecedores": [],
            "servidores": [],
            "report_sections": _build_report_sections() if is_pb else [],
        },
    )


@router.get("/api/autocomplete/municipio")
async def autocomplete_municipio(q: str = Query(..., min_length=2)):
    _, rows = cached_query(
        f"ac:mun:{q.casefold()[:20]}",
        AUTOCOMPLETE_MUNICIPIO,
        {"q": _normalize_municipio(q), "limit": LIMIT_AUTOCOMPLETE},
        timeout_sec=TIMEOUT_AUTOCOMPLETE,
        ttl=3600,
    )
    # rows are (nome, uf, rank_val)
    results = []
    for r in rows:
        nome, uf = r[0], r[1]
        if uf == "PB":
            results.append(nome)
        else:
            results.append(f"{nome} - {uf}")
    return JSONResponse(results)


@router.post("/api/count/{query_id}")
async def count_query(query_id: str, payload: MunicipioPayload):
    try:
        query_def = _get_query_def(query_id)
    except KeyError:
        return JSONResponse({"error": "Query nao encontrada"}, status_code=404)

    municipio = _normalize_municipio(payload.municipio)
    try:
        _, rows = cached_query(
            f"count:{query_def.id}:{municipio.casefold()}",
            query_def.sql_count,
            {"municipio": municipio},
            timeout_sec=min(query_def.timeout_sec, TIMEOUT_COUNT),
            ttl=900,
        )
    except QueryCanceled:
        return JSONResponse({"error": "Tempo excedido"}, status_code=504)

    count = int(rows[0][0]) if rows else 0
    return JSONResponse({"query_id": query_def.id, "title": query_def.title, "count": count})


@router.post("/api/run/{query_id}", response_class=HTMLResponse)
async def run_query(request: Request, query_id: str, payload: MunicipioPayload):
    try:
        query_def = _get_query_def(query_id)
    except KeyError:
        return HTMLResponse("<p class='color-red text-sm'>Query nao encontrada.</p>", status_code=404)

    municipio = _normalize_municipio(payload.municipio)

    # Try pre-computed cache first
    cached = read_web_cache(query_def.id, municipio)
    if cached:
        cols, rows = cached
        return _render_result_table(request, query_def.title, cols, rows)

    try:
        cols, rows = execute_query(
            query_def.sql_full,
            {"municipio": municipio},
            timeout_sec=query_def.timeout_sec,
        )
    except QueryCanceled:
        return HTMLResponse(
            "<p class='color-red text-sm'>Tempo excedido ao executar a query.</p>",
            status_code=504,
        )

    return _render_result_table(request, query_def.title, cols, rows)


@router.post("/api/top/fornecedores", response_class=HTMLResponse)
async def top_fornecedores(request: Request, payload: MunicipioPayload):
    municipio = _normalize_municipio(payload.municipio)
    uf = payload.uf.strip().upper() if payload.uf else ""
    cached = read_web_cache("TOP_FORNECEDORES", municipio)
    if cached and _is_pb(uf):
        cols, rows = cached
    else:
        cols, rows = _load_top_fornecedores(municipio, uf)
    fornecedores = [_row_to_dict(cols, row) for row in rows]
    response = _render_partial(
        request,
        "partials/top_fornecedores.html",
        {"fornecedores": fornecedores},
    )
    response.headers["X-Row-Count"] = str(len(fornecedores))
    return response


@router.post("/api/top/servidores", response_class=HTMLResponse)
async def top_servidores(request: Request, payload: MunicipioPayload):
    municipio = _normalize_municipio(payload.municipio)
    uf = payload.uf.strip().upper() if payload.uf else ""
    if not _is_pb(uf):
        # No servidor data for non-PB municipalities
        response = _render_partial(
            request,
            "partials/top_servidores.html",
            {"servidores": []},
        )
        response.headers["X-Row-Count"] = "0"
        return response
    cached = read_web_cache("TOP_SERVIDORES", municipio)
    if cached:
        cols, rows = cached
    else:
        cols, rows = _load_top_servidores(municipio)
    servidores = [_row_to_dict(cols, row) for row in rows]
    response = _render_partial(
        request,
        "partials/top_servidores.html",
        {"servidores": servidores},
    )
    response.headers["X-Row-Count"] = str(len(servidores))
    return response


@router.post("/api/batch/{municipio_path}")
async def batch_cache(municipio_path: str):
    """Retorna todos os dados do cache de uma vez para o municipio."""
    municipio = _normalize_municipio(municipio_path)
    result = {}
    try:
        from web.db import get_conn
        with get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT query_id, columns, rows, row_count FROM web_cache WHERE municipio = %s",
                    (municipio,),
                )
                for row in cur.fetchall():
                    qid, cols, rows_data, count = row
                    result[qid] = {
                        "columns": cols if isinstance(cols, list) else [],
                        "rows": rows_data if isinstance(rows_data, list) else [],
                        "row_count": count or 0,
                    }
    except Exception:
        pass
    return JSONResponse(result)


@router.get("/api/export/{query_id}")
async def export_query_csv(query_id: str, municipio: str = Query(..., min_length=2)):
    try:
        query_def = _get_query_def(query_id)
    except KeyError:
        return Response("Query nao encontrada", status_code=404)

    normalized = _normalize_municipio(municipio)
    try:
        cols, rows = execute_query(
            query_def.sql_full,
            {"municipio": normalized},
            timeout_sec=query_def.timeout_sec,
        )
    except QueryCanceled:
        return Response("Tempo excedido ao exportar", status_code=504)

    safe_city = normalized.lower().replace(" ", "-")
    return _csv_response(f"{query_def.id.lower()}-{safe_city}.csv", cols, rows)
