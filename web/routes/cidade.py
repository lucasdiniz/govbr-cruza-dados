"""Rotas do modo cidade."""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, Body, Query, Request
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
    AUTOCOMPLETE_MUNICIPIO_FALLBACK,
    PERFIL_MUNICIPIO,
    PERFIL_MUNICIPIO_LIVE,
    PERFIL_MUNICIPIO_PNCP,
    TOP_FORNECEDORES,
    TOP_FORNECEDORES_BASIC,
    TOP_FORNECEDORES_BASIC_DATED,
    TOP_FORNECEDORES_DATED,
    TOP_FORNECEDORES_FALLBACK,
    TOP_FORNECEDORES_FALLBACK_DATED,
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
    data_inicio: str | None = None
    data_fim: str | None = None


def _row_to_dict(cols, row):
    return dict(zip(cols, row))


def _row_to_json_dict(cols, row):
    """Like _row_to_dict but converts Decimal/date for JSON serialization."""
    d = {}
    for c, v in zip(cols, row):
        if hasattr(v, 'as_tuple'):  # Decimal
            d[c] = float(v)
        elif hasattr(v, 'isoformat'):  # date/datetime
            d[c] = v.isoformat()
        else:
            d[c] = v
    return d


def _normalize_municipio(value: str) -> str:
    return " ".join(value.strip().split())


def _has_date_filter(payload: MunicipioPayload) -> bool:
    return bool(payload.data_inicio or payload.data_fim)


def _get_periodo(payload: MunicipioPayload) -> str:
    """'ANO' se datas batem com ano atual, '' se sem filtro, 'CUSTOM' se custom."""
    if not _has_date_filter(payload):
        return ""
    today = date.today()
    yr = str(today.year)
    if payload.data_inicio == f"{yr}-01-01" and (payload.data_fim or "").startswith(yr):
        return "ANO"
    return "CUSTOM"


def _date_params(payload: MunicipioPayload) -> dict:
    params = {"municipio": _normalize_municipio(payload.municipio)}
    if payload.data_inicio:
        params["data_inicio"] = payload.data_inicio
        params["ano_inicio"] = int(payload.data_inicio[:4])
        params["ano_mes_inicio"] = payload.data_inicio[:7]
    if payload.data_fim:
        params["data_fim"] = payload.data_fim
        params["ano_fim"] = int(payload.data_fim[:4])
        params["ano_mes_fim"] = payload.data_fim[:7]
    return params


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
                return ["cnpj_basico", "nome_credor", "razao_social", "cnpj_completo", "total_pago", "qtd_empenhos", "flag_ceis", "flag_pgfn", "flag_inativa", "desc_situacao"], []


def _load_top_fornecedores_pncp(municipio: str, uf: str):
    try:
        return cached_query(
            f"fornpncp:{uf}:{municipio}",
            TOP_FORNECEDORES_PNCP,
            {"municipio": municipio, "uf": uf},
            timeout_sec=TIMEOUT_QUERY_LIGHT,
        )
    except QueryCanceled:
        return ["cnpj_basico", "nome_credor", "razao_social", "cnpj_completo", "total_contratado", "qtd_contratos", "flag_ceis", "flag_pgfn", "flag_inativa", "desc_situacao"], []


def _load_top_fornecedores_dated(params: dict):
    """Carrega top fornecedores com filtro de data (live, sem cache in-memory)."""
    empty = ["cnpj_basico", "nome_credor", "razao_social", "cnpj_completo", "total_pago", "qtd_empenhos", "flag_ceis", "flag_pgfn", "flag_inativa", "desc_situacao"], []
    for sql in [TOP_FORNECEDORES_DATED, TOP_FORNECEDORES_FALLBACK_DATED, TOP_FORNECEDORES_BASIC_DATED]:
        try:
            return execute_query(sql, params, timeout_sec=TIMEOUT_QUERY_LIGHT)
        except (UndefinedTable, QueryCanceled):
            continue
    return empty


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

    today = date.today()
    date_ctx = {
        "default_data_inicio": f"{today.year}-01-01",
        "default_data_fim": today.isoformat(),
    }

    return templates.TemplateResponse(
        request,
        "results/cidade.html",
        {
            "municipio": municipio,
            "uf": uf,
            "perfil": perfil,
            **date_ctx,
            "fornecedores": [],
            "servidores": [],
            "report_sections": _build_report_sections() if is_pb else [],
        },
    )


@router.get("/api/autocomplete/municipio")
async def autocomplete_municipio(q: str = Query(..., min_length=2)):
    try:
        _, rows = cached_query(
            f"ac:mun:{q.casefold()[:20]}",
            AUTOCOMPLETE_MUNICIPIO,
            {"q": _normalize_municipio(q), "limit": LIMIT_AUTOCOMPLETE},
            timeout_sec=TIMEOUT_AUTOCOMPLETE,
            ttl=3600,
        )
    except (UndefinedTable, Exception):
        # Fallback: PNCP-only autocomplete when MV is unavailable
        try:
            _, rows = cached_query(
                f"ac:mun:fb:{q.casefold()[:20]}",
                AUTOCOMPLETE_MUNICIPIO_FALLBACK,
                {"q": _normalize_municipio(q), "limit": LIMIT_AUTOCOMPLETE},
                timeout_sec=TIMEOUT_AUTOCOMPLETE,
                ttl=300,
            )
        except Exception:
            return JSONResponse([])
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
    periodo = _get_periodo(payload)

    # Try pre-computed cache first (ALL or ANO)
    if periodo != "CUSTOM":
        cached = read_web_cache(query_def.id, municipio, periodo=periodo)
        if cached:
            cols, rows = cached
            return _render_result_table(request, query_def.title, cols, rows)

    # Live query (CUSTOM range or cache miss)
    if _has_date_filter(payload) and query_def.sql_full_dated:
        sql = query_def.sql_full_dated
        params = _date_params(payload)
    else:
        sql = query_def.sql_full
        params = {"municipio": municipio}

    try:
        cols, rows = execute_query(sql, params, timeout_sec=query_def.timeout_sec)
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
    periodo = _get_periodo(payload)

    if _has_date_filter(payload) and _is_pb(uf):
        # Date-filtered: try cache ANO then live
        if periodo != "CUSTOM":
            cached = read_web_cache("TOP_FORNECEDORES", municipio, periodo=periodo)
            if cached:
                cols, rows = cached
            else:
                cols, rows = _load_top_fornecedores_dated(_date_params(payload))
        else:
            cols, rows = _load_top_fornecedores_dated(_date_params(payload))
    else:
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
async def batch_cache(municipio_path: str, periodo: str = ""):
    """Retorna todos os dados do cache de uma vez para o municipio.

    periodo: '' para all-time, 'ANO' para ano atual.
    Busca todos os rows e filtra por prefixo, com fallback.
    """
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
                prefix = f"{periodo}:" if periodo else ""
                for row in cur.fetchall():
                    qid, cols, rows_data, count = row
                    entry = {
                        "columns": cols if isinstance(cols, list) else [],
                        "rows": rows_data if isinstance(rows_data, list) else [],
                        "row_count": count or 0,
                    }
                    if periodo and qid.startswith(prefix):
                        # Prefixed entry: strip prefix for the response key
                        base_qid = qid[len(prefix):]
                        result[base_qid] = entry
                    elif not periodo and ":" not in qid:
                        # Unprefixed entry for all-time
                        result[qid] = entry
                    elif ":" in qid:
                        # Prefixed but not matching: skip
                        pass
                    else:
                        # Fallback: only for queries without dated variants (TOP_SERVIDORES)
                        if periodo and qid == "TOP_SERVIDORES" and qid not in result:
                            result[qid] = entry
    except Exception:
        pass
    return JSONResponse(result)


@router.post("/api/perfil")
async def get_perfil(payload: MunicipioPayload):
    """Retorna perfil do municipio como JSON, com filtro temporal opcional."""
    municipio = _normalize_municipio(payload.municipio)
    periodo = _get_periodo(payload)

    if periodo != "CUSTOM":
        cached = read_web_cache("PERFIL", municipio, periodo=periodo)
        if cached:
            cols, rows = cached
            if rows:
                return JSONResponse(_row_to_json_dict(cols, rows[0]))

    if _has_date_filter(payload):
        try:
            cols, rows = execute_query(PERFIL_MUNICIPIO_LIVE, _date_params(payload), timeout_sec=15)
        except QueryCanceled:
            return JSONResponse({})
    else:
        try:
            cols, rows = cached_query(
                f"perfil:{municipio.casefold()}",
                PERFIL_MUNICIPIO,
                {"municipio": municipio},
                timeout_sec=TIMEOUT_PROFILE,
            )
        except (QueryCanceled, Exception):
            return JSONResponse({})

    if rows:
        return JSONResponse(_row_to_json_dict(cols, rows[0]))
    return JSONResponse({})


@router.post("/api/cache/invalidate")
async def invalidate_web_cache(payload: dict = Body(...)):
    """Invalida entradas do web_cache por query_id(s)."""
    query_ids = payload.get("query_ids", [])
    if not query_ids:
        return JSONResponse({"deleted": 0})
    try:
        from web.db import get_conn
        with get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                ph = ",".join(["%s"] * len(query_ids))
                cur.execute(f"DELETE FROM web_cache WHERE query_id IN ({ph})", query_ids)
                deleted = cur.rowcount
        return JSONResponse({"deleted": deleted})
    except Exception:
        return JSONResponse({"error": "falha ao invalidar"}, status_code=500)


@router.post("/api/servidor/detalhes")
async def get_servidor_detalhes(payload: dict = Body(...)):
    """Retorna detalhes enriquecidos de um servidor: empresas, BF, vinculo, sancoes, empenhos."""
    cpf6 = payload.get("cpf6", "")
    nome = payload.get("nome", "")
    cnpjs = (payload.get("cnpjs") or [])[:100]
    municipio = payload.get("municipio", "")
    if not cpf6 or not nome:
        return JSONResponse({})
    try:
        from web.db import get_conn
        result = {}
        with get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                # Empresas vinculadas
                if cnpjs:
                    ph = ",".join(["%s"] * len(cnpjs))
                    cur.execute(f"""
                        SELECT e.cnpj_basico, e.razao_social, e.capital_social,
                               est.cnpj_completo, est.situacao_cadastral,
                               est.cnae_principal, est.uf,
                               COALESCE(dm.descricao, est.municipio) AS municipio,
                               COALESCE(dq.descricao, s.qualificacao) AS qualificacao_socio,
                               s.dt_entrada AS dt_entrada_sociedade
                        FROM empresa e
                        LEFT JOIN estabelecimento est ON est.cnpj_basico = e.cnpj_basico
                            AND est.cnpj_ordem = '0001'
                        LEFT JOIN dom_municipio dm ON dm.codigo = est.municipio
                        LEFT JOIN socio s ON s.cnpj_basico = e.cnpj_basico
                            AND s.cpf_cnpj_norm = %s
                            AND UPPER(TRIM(s.nome)) = %s
                        LEFT JOIN dom_qualificacao dq ON dq.codigo = s.qualificacao
                        WHERE e.cnpj_basico IN ({ph})
                    """, [cpf6, nome] + cnpjs)
                    cols = [d[0] for d in cur.description]
                    rows = cur.fetchall()
                    empresas = []
                    for row in rows:
                        r = _row_to_dict(cols, row)
                        for k, v in r.items():
                            if hasattr(v, 'as_tuple'):
                                r[k] = float(v)
                            elif hasattr(v, 'isoformat'):
                                r[k] = v.isoformat()
                        empresas.append(r)
                    result["empresas"] = empresas

                # Bolsa Família
                cur.execute("""
                    SELECT mes_competencia, valor_parcela, nm_municipio
                    FROM bolsa_familia
                    WHERE cpf_digitos = %s
                      AND UPPER(TRIM(nm_favorecido)) = %s
                    ORDER BY mes_competencia DESC
                    LIMIT 5
                """, (cpf6, nome))
                bf_cols = [d[0] for d in cur.description]
                bf_rows = cur.fetchall()
                if bf_rows:
                    bf_list = []
                    for row in bf_rows:
                        r = _row_to_dict(bf_cols, row)
                        for k, v in r.items():
                            if hasattr(v, 'as_tuple'):
                                r[k] = float(v)
                        bf_list.append(r)
                    result["bolsa_familia"] = bf_list

                # Vínculo como servidor
                cur.execute("""
                    SELECT municipio, descricao_cargo, data_admissao,
                           MIN(ano_mes) AS primeiro_registro,
                           MAX(ano_mes) AS ultimo_registro,
                           MAX(valor_vantagem) AS maior_salario
                    FROM tce_pb_servidor
                    WHERE cpf_digitos_6 = %s AND nome_upper = %s
                    GROUP BY municipio, descricao_cargo, data_admissao
                    ORDER BY MAX(ano_mes) DESC
                """, (cpf6, nome))
                srv_cols = [d[0] for d in cur.description]
                srv_rows = cur.fetchall()
                if srv_rows:
                    vinculos = []
                    for row in srv_rows:
                        r = _row_to_dict(srv_cols, row)
                        for k, v in r.items():
                            if hasattr(v, 'as_tuple'):
                                r[k] = float(v)
                            elif hasattr(v, 'isoformat'):
                                r[k] = v.isoformat()
                        vinculos.append(r)
                    result["vinculos"] = vinculos

                # Sancoes CEIS/CNEP das empresas vinculadas
                if cnpjs:
                    ph = ",".join(["%s"] * len(cnpjs))
                    cur.execute(f"""
                        SELECT LEFT(cpf_cnpj_sancionado, 8) AS cnpj_basico,
                               'CEIS' AS fonte,
                               nome_sancionado, categoria_sancao, orgao_sancionador,
                               esfera_orgao_sancionador,
                               dt_inicio_sancao, dt_final_sancao
                        FROM ceis_sancao
                        WHERE LEFT(cpf_cnpj_sancionado, 8) IN ({ph})
                        UNION ALL
                        SELECT LEFT(cpf_cnpj_sancionado, 8) AS cnpj_basico,
                               'CNEP' AS fonte,
                               nome_sancionado, categoria_sancao, orgao_sancionador,
                               esfera_orgao_sancionador,
                               dt_inicio_sancao, dt_final_sancao
                        FROM cnep_sancao
                        WHERE LEFT(cpf_cnpj_sancionado, 8) IN ({ph})
                    """, cnpjs + cnpjs)
                    san_cols = [d[0] for d in cur.description]
                    san_rows = cur.fetchall()
                    sancoes_map = {}
                    for row in san_rows:
                        r = _row_to_dict(san_cols, row)
                        for k, v in r.items():
                            if hasattr(v, 'isoformat'):
                                r[k] = v.isoformat()
                        cb = r["cnpj_basico"]
                        sancoes_map.setdefault(cb, []).append(r)
                    if sancoes_map:
                        result["empresa_sancoes"] = sancoes_map

                # PGFN dividas das empresas vinculadas
                if cnpjs:
                    ph = ",".join(["%s"] * len(cnpjs))
                    cur.execute(f"""
                        SELECT LEFT(cpf_cnpj_norm, 8) AS cnpj_basico,
                               tipo_devedor, valor_consolidado, situacao_inscricao
                        FROM pgfn_divida
                        WHERE LENGTH(cpf_cnpj_norm) = 14
                          AND LEFT(cpf_cnpj_norm, 8) IN ({ph})
                    """, cnpjs)
                    pgfn_cols = [d[0] for d in cur.description]
                    pgfn_rows = cur.fetchall()
                    pgfn_map = {}
                    for row in pgfn_rows:
                        r = _row_to_dict(pgfn_cols, row)
                        for k, v in r.items():
                            if hasattr(v, 'as_tuple'):
                                r[k] = float(v)
                        cb = r["cnpj_basico"]
                        pgfn_map.setdefault(cb, []).append(r)
                    if pgfn_map:
                        result["empresa_pgfn"] = pgfn_map

                # Empenhos recebidos pelas empresas no municipio
                if cnpjs and municipio:
                    ph = ",".join(["%s"] * len(cnpjs))
                    cur.execute(f"""
                        SELECT cnpj_basico,
                               SUM(valor_pago) AS total_pago,
                               SUM(valor_empenhado) AS total_empenhado,
                               COUNT(*) AS qtd_empenhos,
                               MIN(data_empenho) AS primeiro_empenho,
                               MAX(data_empenho) AS ultimo_empenho
                        FROM tce_pb_despesa
                        WHERE cnpj_basico IN ({ph})
                          AND municipio = %s
                          AND valor_pago > 0
                        GROUP BY cnpj_basico
                    """, cnpjs + [municipio])
                    emp_cols = [d[0] for d in cur.description]
                    emp_rows = cur.fetchall()
                    empenhos_map = {}
                    for row in emp_rows:
                        r = _row_to_dict(emp_cols, row)
                        for k, v in r.items():
                            if hasattr(v, 'as_tuple'):
                                r[k] = float(v)
                            elif hasattr(v, 'isoformat'):
                                r[k] = v.isoformat()
                        empenhos_map[r["cnpj_basico"]] = r
                    if empenhos_map:
                        result["empresa_empenhos"] = empenhos_map

                # CEAF - Expulsoes da Administracao Federal
                cur.execute("""
                    SELECT categoria_sancao, cargo_efetivo, funcao_confianca,
                           orgao_lotacao, orgao_sancionador, dt_inicio_sancao,
                           dt_final_sancao, dt_transito_julgado, fundamentacao_legal,
                           numero_processo
                    FROM ceaf_expulsao
                    WHERE cpf_cnpj_norm = %s
                      AND UPPER(unaccent(nome_sancionado)) = %s
                    ORDER BY dt_inicio_sancao DESC
                """, (cpf6, nome))
                ceaf_cols = [d[0] for d in cur.description]
                ceaf_rows = cur.fetchall()
                if ceaf_rows:
                    ceaf_list = []
                    for row in ceaf_rows:
                        r = _row_to_dict(ceaf_cols, row)
                        for k, v in r.items():
                            if hasattr(v, 'isoformat'):
                                r[k] = v.isoformat()
                        ceaf_list.append(r)
                    result["ceaf"] = ceaf_list

                # Acordos de Leniencia das empresas vinculadas
                if cnpjs:
                    ph = ",".join(["%s"] * len(cnpjs))
                    cur.execute(f"""
                        SELECT LEFT(al.cnpj_norm, 8) AS cnpj_basico,
                               al.situacao_acordo
                        FROM acordo_leniencia al
                        WHERE LEFT(al.cnpj_norm, 8) IN ({ph})
                    """, cnpjs)
                    ac_cols = [d[0] for d in cur.description]
                    ac_rows = cur.fetchall()
                    if ac_rows:
                        acordos_map = {}
                        for row in ac_rows:
                            r = _row_to_dict(ac_cols, row)
                            cb = r["cnpj_basico"]
                            acordos_map.setdefault(cb, []).append(r)
                        result["empresa_acordos"] = acordos_map

                # Empenhos das empresas vinculadas durante o vinculo do servidor
                if cnpjs and municipio:
                    ph = ",".join(["%s"] * len(cnpjs))
                    cur.execute(f"""
                        WITH vinculo AS (
                            SELECT MIN(data_admissao) AS dt_admissao,
                                   TO_DATE(MIN(ano_mes), 'YYYYMM') AS primeiro_dt,
                                   TO_DATE(MAX(ano_mes), 'YYYYMM') + INTERVAL '1 month' - INTERVAL '1 day' AS ultimo_dt
                            FROM tce_pb_servidor
                            WHERE cpf_digitos_6 = %s AND nome_upper = %s AND municipio = %s
                        )
                        SELECT d.cnpj_basico, d.data_empenho, d.elemento_despesa,
                               d.valor_empenhado, d.valor_pago,
                               d.modalidade_licitacao, d.numero_licitacao, d.id
                        FROM tce_pb_despesa d, vinculo v
                        WHERE d.cnpj_basico IN ({ph})
                          AND d.municipio = %s
                          AND d.valor_pago > 0
                          AND d.data_empenho >= COALESCE(v.dt_admissao, v.primeiro_dt)
                          AND d.data_empenho <= v.ultimo_dt
                        ORDER BY d.data_empenho DESC
                        LIMIT 100
                    """, [cpf6, nome, municipio] + cnpjs + [municipio])
                    ev_cols = [d[0] for d in cur.description]
                    ev_rows = cur.fetchall()
                    if ev_rows:
                        emp_vinc = []
                        for row in ev_rows:
                            r = _row_to_dict(ev_cols, row)
                            for k, v in r.items():
                                if hasattr(v, 'as_tuple'):
                                    r[k] = float(v)
                                elif hasattr(v, 'isoformat'):
                                    r[k] = v.isoformat()
                            emp_vinc.append(r)
                        result["empenhos_durante_vinculo"] = emp_vinc

        return JSONResponse(result, headers={"Cache-Control": "public, max-age=3600"})
    except Exception:
        import logging; logging.exception("servidor detalhes failed")
        return JSONResponse({})


@router.post("/api/fornecedor/detalhes")
async def get_fornecedor_detalhes(payload: dict = Body(...)):
    """Retorna detalhes de um fornecedor: empenhos recentes, sancoes, situacao cadastral."""
    cnpj_basico = payload.get("cnpj_basico", "")
    municipio = payload.get("municipio", "")
    if not cnpj_basico:
        return JSONResponse({})
    try:
        from web.db import get_conn
        result = {}
        with get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                # Empenhos recentes no municipio
                cur.execute("""
                    SELECT id, numero_empenho, data_empenho, elemento_despesa,
                           valor_empenhado, valor_pago,
                           modalidade_licitacao, numero_licitacao
                    FROM tce_pb_despesa
                    WHERE cnpj_basico = %s AND municipio = %s
                      AND valor_pago > 0
                    ORDER BY data_empenho DESC
                    LIMIT 50
                """, (cnpj_basico, municipio))
                emp_cols = [d[0] for d in cur.description]
                emp_rows = cur.fetchall()
                empenhos = []
                for row in emp_rows:
                    r = _row_to_dict(emp_cols, row)
                    for k, v in r.items():
                        if hasattr(v, 'as_tuple'):
                            r[k] = float(v)
                        elif hasattr(v, 'isoformat'):
                            r[k] = v.isoformat()
                    empenhos.append(r)
                result["empenhos"] = empenhos

                # Aggregate stats (all empenhos, no LIMIT)
                cur.execute("""
                    SELECT COUNT(*) AS qtd_empenhos,
                           COALESCE(SUM(valor_empenhado), 0) AS total_empenhado,
                           COALESCE(SUM(valor_pago), 0) AS total_pago,
                           MIN(data_empenho) AS primeiro_empenho,
                           MAX(data_empenho) AS ultimo_empenho,
                           COUNT(*) FILTER (
                               WHERE numero_licitacao IS NULL
                                  OR numero_licitacao = '000000000'
                                  OR modalidade_licitacao ILIKE '%%sem licit%%'
                           ) AS qtd_sem_licitacao
                    FROM tce_pb_despesa
                    WHERE cnpj_basico = %s AND municipio = %s
                      AND valor_pago > 0
                """, (cnpj_basico, municipio))
                agg_cols = [d[0] for d in cur.description]
                agg_row = cur.fetchone()
                if agg_row:
                    stats = _row_to_dict(agg_cols, agg_row)
                    for k, v in stats.items():
                        if hasattr(v, 'as_tuple'):
                            stats[k] = float(v)
                        elif hasattr(v, 'isoformat'):
                            stats[k] = v.isoformat()
                    result["stats"] = stats

                # Monthly payments (last 12 months)
                cur.execute("""
                    SELECT TO_CHAR(data_empenho, 'YYYY-MM') AS mes,
                           SUM(valor_pago) AS total_mes
                    FROM tce_pb_despesa
                    WHERE cnpj_basico = %s AND municipio = %s
                      AND valor_pago > 0
                      AND data_empenho >= (CURRENT_DATE - INTERVAL '12 months')
                    GROUP BY TO_CHAR(data_empenho, 'YYYY-MM')
                    ORDER BY mes
                """, (cnpj_basico, municipio))
                m_cols = [d[0] for d in cur.description]
                m_rows = cur.fetchall()
                monthly = []
                for row in m_rows:
                    r = _row_to_dict(m_cols, row)
                    for k, v in r.items():
                        if hasattr(v, 'as_tuple'):
                            r[k] = float(v)
                    monthly.append(r)
                result["monthly"] = monthly

                # Top 3 elementos de despesa
                cur.execute("""
                    SELECT elemento_despesa,
                           SUM(valor_pago) AS total_elemento,
                           COUNT(*) AS qtd
                    FROM tce_pb_despesa
                    WHERE cnpj_basico = %s AND municipio = %s
                      AND valor_pago > 0
                    GROUP BY elemento_despesa
                    ORDER BY SUM(valor_pago) DESC
                    LIMIT 3
                """, (cnpj_basico, municipio))
                el_cols = [d[0] for d in cur.description]
                el_rows = cur.fetchall()
                top_elementos = []
                for row in el_rows:
                    r = _row_to_dict(el_cols, row)
                    for k, v in r.items():
                        if hasattr(v, 'as_tuple'):
                            r[k] = float(v)
                    top_elementos.append(r)
                result["top_elementos"] = top_elementos

                # Sancoes CEIS
                cur.execute("""
                    SELECT cpf_cnpj_sancionado, categoria_sancao, dt_inicio_sancao, dt_final_sancao,
                           orgao_sancionador, esfera_orgao_sancionador, fundamentacao_legal
                    FROM ceis_sancao
                    WHERE LEFT(cpf_cnpj_sancionado, 8) = %s
                    ORDER BY dt_inicio_sancao DESC
                """, (cnpj_basico,))
                san_cols = [d[0] for d in cur.description]
                san_rows = cur.fetchall()
                sancoes = []
                for row in san_rows:
                    r = _row_to_dict(san_cols, row)
                    r["origem"] = "CEIS"
                    for k, v in r.items():
                        if hasattr(v, 'isoformat'):
                            r[k] = v.isoformat()
                    sancoes.append(r)

                # Sancoes CNEP
                cur.execute("""
                    SELECT cpf_cnpj_sancionado, categoria_sancao, dt_inicio_sancao, dt_final_sancao,
                           orgao_sancionador, esfera_orgao_sancionador, fundamentacao_legal, valor_multa
                    FROM cnep_sancao
                    WHERE LEFT(cpf_cnpj_sancionado, 8) = %s
                    ORDER BY dt_inicio_sancao DESC
                """, (cnpj_basico,))
                cnep_cols = [d[0] for d in cur.description]
                cnep_rows = cur.fetchall()
                for row in cnep_rows:
                    r = _row_to_dict(cnep_cols, row)
                    r["origem"] = "CNEP"
                    for k, v in r.items():
                        if hasattr(v, 'as_tuple'):
                            r[k] = float(v)
                        elif hasattr(v, 'isoformat'):
                            r[k] = v.isoformat()
                    sancoes.append(r)

                if sancoes:
                    result["sancoes"] = sancoes

                    # Empenhos durante sancao em OUTROS municipios
                    cur.execute("""
                        SELECT d.municipio, COUNT(*) AS qtd_empenhos,
                               SUM(d.valor_pago) AS total_pago
                        FROM tce_pb_despesa d
                        JOIN (
                            SELECT LEFT(cpf_cnpj_sancionado, 8) AS cb,
                                   dt_inicio_sancao, dt_final_sancao
                            FROM ceis_sancao
                            UNION ALL
                            SELECT LEFT(cpf_cnpj_sancionado, 8),
                                   dt_inicio_sancao, dt_final_sancao
                            FROM cnep_sancao
                        ) san ON san.cb = d.cnpj_basico
                        WHERE d.cnpj_basico = %s
                          AND d.municipio != %s
                          AND d.valor_pago > 0
                          AND d.data_empenho >= san.dt_inicio_sancao
                          AND (san.dt_final_sancao IS NULL OR d.data_empenho <= san.dt_final_sancao)
                        GROUP BY d.municipio
                        ORDER BY total_pago DESC
                    """, (cnpj_basico, municipio))
                    es_cols = [d2[0] for d2 in cur.description]
                    es_rows = cur.fetchall()
                    if es_rows:
                        outros = []
                        for row in es_rows:
                            r = _row_to_dict(es_cols, row)
                            for k, v in r.items():
                                if hasattr(v, 'as_tuple'):
                                    r[k] = float(v)
                            outros.append(r)
                        result["empenhos_sancao_outros"] = outros

                # Municipios onde o fornecedor recebeu pagamentos
                cur.execute("""
                    SELECT municipio, SUM(valor_pago) AS total_pago
                    FROM tce_pb_despesa
                    WHERE cnpj_basico = %s AND valor_pago > 0
                    GROUP BY municipio
                    ORDER BY total_pago DESC
                """, (cnpj_basico,))
                mun_cols = [d2[0] for d2 in cur.description]
                mun_rows = cur.fetchall()
                if mun_rows and len(mun_rows) > 1:
                    mun_list = []
                    for row in mun_rows:
                        r = _row_to_dict(mun_cols, row)
                        for k, v in r.items():
                            if hasattr(v, 'as_tuple'):
                                r[k] = float(v)
                        mun_list.append(r)
                    result["municipios_ativos"] = mun_list

                # Situacao cadastral (inatividade)
                cur.execute("""
                    SELECT situacao_cadastral, dt_situacao,
                           cnpj_completo, cnae_principal, uf,
                           COALESCE(dm.descricao, est.municipio) AS municipio
                    FROM estabelecimento est
                    LEFT JOIN dom_municipio dm ON dm.codigo = est.municipio
                    WHERE est.cnpj_basico = %s AND est.cnpj_ordem = '0001'
                """, (cnpj_basico,))
                sit_cols = [d[0] for d in cur.description]
                sit_rows = cur.fetchall()
                if sit_rows:
                    sit = _row_to_dict(sit_cols, sit_rows[0])
                    for k, v in sit.items():
                        if hasattr(v, 'isoformat'):
                            sit[k] = v.isoformat()
                    result["estabelecimento"] = sit

                # Divida PGFN
                cur.execute("""
                    SELECT numero_inscricao, situacao_inscricao,
                           receita_principal, valor_consolidado,
                           dt_inscricao, indicador_ajuizado
                    FROM pgfn_divida
                    WHERE LEFT(cpf_cnpj_norm, 8) = %s AND LENGTH(cpf_cnpj_norm) = 14
                    ORDER BY valor_consolidado DESC
                """, (cnpj_basico,))
                pgfn_cols = [d[0] for d in cur.description]
                pgfn_rows = cur.fetchall()
                if pgfn_rows:
                    dividas = []
                    for row in pgfn_rows:
                        r = _row_to_dict(pgfn_cols, row)
                        for k, v in r.items():
                            if hasattr(v, 'as_tuple'):
                                r[k] = float(v)
                            elif hasattr(v, 'isoformat'):
                                r[k] = v.isoformat()
                        dividas.append(r)
                    result["pgfn"] = dividas

                # Acordos de Leniencia
                cur.execute("""
                    SELECT al.cnpj_sancionado, al.razao_social_rfb, al.situacao_acordo,
                           al.orgao_sancionador, al.dt_inicio_acordo, al.dt_fim_acordo,
                           al.numero_processo, al.id_acordo
                    FROM acordo_leniencia al
                    WHERE LEFT(al.cnpj_norm, 8) = %s
                    ORDER BY al.dt_inicio_acordo DESC
                """, (cnpj_basico,))
                al_cols = [d[0] for d in cur.description]
                al_rows = cur.fetchall()
                if al_rows:
                    acordos = []
                    for row in al_rows:
                        a = _row_to_dict(al_cols, row)
                        for k, v in a.items():
                            if hasattr(v, 'isoformat'):
                                a[k] = v.isoformat()
                        # Buscar efeitos do acordo
                        cur.execute("""
                            SELECT efeito, complemento FROM acordo_efeito
                            WHERE id_acordo = %s
                        """, (a["id_acordo"],))
                        ef_cols = [d[0] for d in cur.description]
                        ef_rows = cur.fetchall()
                        a["efeitos"] = [_row_to_dict(ef_cols, er) for er in ef_rows]
                        acordos.append(a)
                    result["acordos_leniencia"] = acordos

        return JSONResponse(result, headers={"Cache-Control": "public, max-age=3600"})
    except Exception:
        import logging; logging.exception("fornecedor detalhes failed")
        return JSONResponse({})


@router.post("/api/empenho/detalhes")
async def get_empenho_detalhes(payload: dict = Body(...)):
    """Retorna detalhes completos de um empenho pelo ID."""
    empenho_id = payload.get("id")
    if not empenho_id:
        return JSONResponse({})
    try:
        from web.db import get_conn
        with get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT numero_empenho, data_empenho, nome_credor, cpf_cnpj,
                           valor_empenhado, valor_liquidado, valor_pago,
                           elemento_despesa, modalidade_licitacao, numero_licitacao,
                           historico, funcao, subfuncao, programa, acao,
                           descricao_ug, descricao_unidade_orcamentaria,
                           descricao_fonte_recurso, categoria_economica,
                           grupo_natureza_despesa, modalidade_aplicacao,
                           municipio
                    FROM tce_pb_despesa
                    WHERE id = %s
                """, (empenho_id,))
                cols = [d[0] for d in cur.description]
                row = cur.fetchone()
                if not row:
                    return JSONResponse({})
                r = _row_to_dict(cols, row)
                for k, v in r.items():
                    if hasattr(v, 'as_tuple'):
                        r[k] = float(v)
                    elif hasattr(v, 'isoformat'):
                        r[k] = v.isoformat()
                return JSONResponse(r, headers={"Cache-Control": "public, max-age=3600"})
    except Exception:
        import logging; logging.exception("empenho detalhes failed")
        return JSONResponse({})


@router.post("/api/licitacao/detalhes")
async def get_licitacao_detalhes(payload: dict = Body(...)):
    """Retorna detalhes de uma licitacao: metadata, proponentes e despesas vinculadas."""
    numero = payload.get("numero_licitacao", "")
    ano = payload.get("ano_licitacao", 0)
    municipio = payload.get("municipio", "")
    if not numero or not municipio:
        return JSONResponse({})

    # Despesa stores as '000282025' (9 digits), licitacao as '00028/2025'
    numero_despesa = numero  # keep original for tce_pb_despesa
    if len(numero) == 9 and numero.isdigit() and '/' not in numero:
        year_part = numero[5:]
        num_part = numero[:5]
        if 2000 <= int(year_part) <= 2099:
            numero = f"{num_part}/{year_part}"
            if not ano:
                ano = int(year_part)
    try:
        from web.db import get_conn

        def _convert(row_dict):
            for k, v in row_dict.items():
                if hasattr(v, 'as_tuple'):
                    row_dict[k] = float(v)
                elif hasattr(v, 'isoformat'):
                    row_dict[k] = v.isoformat()
            return row_dict

        result = {}
        with get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                # Metadata da licitacao
                cur.execute("""
                    SELECT DISTINCT objeto_licitacao, modalidade,
                           data_homologacao, descricao_ug
                    FROM tce_pb_licitacao
                    WHERE numero_licitacao = %s AND municipio = %s
                      AND (%s = 0 OR ano_licitacao = %s)
                    LIMIT 1
                """, (numero, municipio, ano, ano))
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                if rows:
                    result["licitacao"] = _convert(_row_to_dict(cols, rows[0]))

                # Proponentes
                cur.execute("""
                    SELECT nome_proponente, cpf_cnpj_proponente,
                           valor_ofertado, situacao_proposta,
                           e.razao_social
                    FROM tce_pb_licitacao l
                    LEFT JOIN empresa e ON e.cnpj_basico = l.cnpj_basico_proponente
                    WHERE l.numero_licitacao = %s AND l.municipio = %s
                      AND (%s = 0 OR l.ano_licitacao = %s)
                    ORDER BY l.valor_ofertado DESC
                """, (numero, municipio, ano, ano))
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                result["proponentes"] = [_convert(_row_to_dict(cols, r)) for r in rows]

                # Despesas vinculadas
                cur.execute("""
                    SELECT id, nome_credor, cpf_cnpj, data_empenho,
                           elemento_despesa, valor_empenhado, valor_pago
                    FROM tce_pb_despesa
                    WHERE numero_licitacao = %s AND municipio = %s
                      AND valor_pago > 0
                    ORDER BY data_empenho DESC
                    LIMIT 50
                """, (numero_despesa, municipio))
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                result["despesas"] = [_convert(_row_to_dict(cols, r)) for r in rows]

        return JSONResponse(result, headers={"Cache-Control": "public, max-age=3600"})
    except Exception:
        import logging; logging.exception("licitacao detalhes failed")
        return JSONResponse({})


@router.get("/api/export/{query_id}")
async def export_query_csv(
    query_id: str,
    municipio: str = Query(..., min_length=2),
    data_inicio: str | None = Query(None),
    data_fim: str | None = Query(None),
):
    try:
        query_def = _get_query_def(query_id)
    except KeyError:
        return Response("Query nao encontrada", status_code=404)

    normalized = _normalize_municipio(municipio)

    if data_inicio and data_fim and query_def.sql_full_dated:
        params = {"municipio": normalized, "data_inicio": data_inicio, "data_fim": data_fim,
                  "ano_inicio": int(data_inicio[:4]), "ano_fim": int(data_fim[:4]),
                  "ano_mes_inicio": data_inicio[:7], "ano_mes_fim": data_fim[:7]}
        sql = query_def.sql_full_dated
    else:
        params = {"municipio": normalized}
        sql = query_def.sql_full

    try:
        cols, rows = execute_query(sql, params, timeout_sec=query_def.timeout_sec)
    except QueryCanceled:
        return Response("Tempo excedido ao exportar", status_code=504)

    safe_city = normalized.lower().replace(" ", "-")
    return _csv_response(f"{query_def.id.lower()}-{safe_city}.csv", cols, rows)
