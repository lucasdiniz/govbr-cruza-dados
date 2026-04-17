"""Rotas do modo cidade."""

from __future__ import annotations

import csv
import io
import time
from datetime import date

from fastapi import APIRouter, Body, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from psycopg2.errors import QueryCanceled, UndefinedTable, UndefinedColumn

from web.config import (
    LIMIT_AUTOCOMPLETE,
    TIMEOUT_AUTOCOMPLETE,
    TIMEOUT_COUNT,
    TIMEOUT_PROFILE,
    TIMEOUT_QUERY_LIGHT,
    TIMEOUT_QUERY_MEDIUM,
    TIMEOUT_QUERY_HEAVY,
)
from web.db import cached_query, execute_query, read_web_cache
from web.queries.cidade import (
    AUTOCOMPLETE_MUNICIPIO,
    HEATMAP_MENSAL,
    HEATMAP_MES_RESUMO,
    HEATMAP_MES_FORNECEDORES,
    HEATMAP_MES_ELEMENTOS,
    HEATMAP_MES_FUNCOES,
    HEATMAP_MES_MODALIDADES,
    HEATMAP_MES_EMPENHOS,
    PB_MEDIAS,
    PERFIL_MUNICIPIO,
    PERFIL_MUNICIPIO_LIVE,
    TOP_FORNECEDORES,
    TOP_FORNECEDORES_DATED,
    TOP_SERVIDORES_RISCO,
    TOP_SERVIDORES_RISCO_DATED,
)
from web.queries.registry import CIDADE_QUERIES, get_categories

router = APIRouter()

SECTION_META = {
    "Conflito de Interesses": {
        "slug": "conflitos",
        "title": "Possiveis conflitos de interesse",
        "title_lay": "Gente que tem dois lados da mesa",
        "description": "Situacoes em que servidores, empresas contratadas e pagamentos publicos podem estar relacionados de forma inadequada.",
        "description_lay": "Quando a pessoa que decide o gasto e a pessoa que recebe acabam sendo a mesma — ou tem alguma liga&ccedil;&atilde;o que deveria impedir a contrata&ccedil;&atilde;o.",
    },
    "Licitacao e Concorrencia": {
        "slug": "licitacoes",
        "title": "Sinais em compras e licitacoes",
        "title_lay": "Como a prefeitura compra — sinais de alerta",
        "description": "Padroes que podem indicar baixa concorrencia, direcionamento ou concentracao anormal de contratos.",
        "description_lay": "A lei manda licitar para o governo gastar menos. Aqui mostramos compras sem disputa, uma s&oacute; empresa ganhando tudo, ou contratos fatiados para escapar da regra.",
    },
    "Fornecedores Irregulares": {
        "slug": "fornecedores-irregulares",
        "title": "Fornecedores com sinais de irregularidade",
        "title_lay": "Empresas que n&atilde;o deveriam estar recebendo",
        "description": "Empresas com sancoes, dividas ou situacao cadastral irregular que aparecem recebendo recursos do municipio.",
        "description_lay": "Empresas punidas por fraude, devendo impostos federais, ou com situa&ccedil;&atilde;o irregular na Receita — e mesmo assim a prefeitura contratou e pagou.",
    },
    "Orcamento e Financeiro": {
        "slug": "orcamento",
        "title": "Execucao orcamentaria e financeira",
        "title_lay": "Como o dinheiro da prefeitura est&aacute; saindo",
        "description": "Desvios entre o que foi empenhado, contratado e efetivamente pago, alem de concentracoes atipicas de despesas.",
        "description_lay": "Quando o que foi prometido e o que foi pago n&atilde;o batem, ou quando um m&ecirc;s concentra muito mais gasto do que os outros.",
    },
    "Politico-Eleitoral": {
        "slug": "politico-eleitoral",
        "title": "Relacoes politico-eleitorais",
        "title_lay": "Pol&iacute;tica e dinheiro p&uacute;blico se misturando",
        "description": "Cruzes entre doacoes de campanha, beneficios sociais e pagamentos publicos que merecem verificacao.",
        "description_lay": "Doadores de campanha que depois viraram fornecedores, pagamentos em per&iacute;odo eleitoral ou outros cruzamentos entre pol&iacute;tica e contratos.",
    },
    "Cruzamento Estado x Municipio": {
        "slug": "estado-municipio",
        "title": "Relacoes entre estado e municipio",
        "title_lay": "Liga&ccedil;&otilde;es entre governo do estado e prefeitura",
        "description": "Achados que conectam contratos estaduais e despesas municipais com os mesmos atores ou periodos.",
        "description_lay": "Mesmas empresas ou pessoas aparecendo em contratos do Estado e do munic&iacute;pio ao mesmo tempo.",
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
    """Compat: aceita formato 'Municipio - UF' mas retorna sempre ('nome', 'PB')."""
    raw = _normalize_municipio(raw)
    if " - " in raw and len(raw.split(" - ")[-1]) == 2:
        parts = raw.rsplit(" - ", 1)
        return parts[0].strip(), "PB"
    return raw, "PB"


def _load_top_fornecedores(municipio: str, uf: str = ""):
    try:
        return cached_query(
            f"forn:{municipio}",
            TOP_FORNECEDORES,
            {"municipio": municipio},
            timeout_sec=TIMEOUT_QUERY_MEDIUM,
        )
    except QueryCanceled:
        return ["cnpj_basico", "nome_credor", "razao_social", "cnpj_completo", "total_pago", "qtd_empenhos", "flag_ceis", "flag_pgfn", "flag_inativa", "abrangencia_sancao_info", "desc_situacao"], []


def _load_top_fornecedores_dated(params: dict):
    """Carrega top fornecedores com filtro de data (live, sem cache in-memory)."""
    empty = ["cnpj_basico", "nome_credor", "razao_social", "cnpj_completo", "total_pago", "qtd_empenhos", "flag_ceis", "flag_pgfn", "flag_inativa", "abrangencia_sancao_info", "desc_situacao"], []
    try:
        return execute_query(TOP_FORNECEDORES_DATED, params, timeout_sec=TIMEOUT_QUERY_MEDIUM)
    except (UndefinedTable, UndefinedColumn, QueryCanceled):
        return empty


def _load_top_servidores(municipio: str, params: dict | None = None):
    query = TOP_SERVIDORES_RISCO_DATED if params and "ano_mes_inicio" in params else TOP_SERVIDORES_RISCO
    qparams = params if params else {"municipio": municipio}
    try:
        return cached_query(
            f"serv:{municipio.casefold()}",
            query,
            qparams,
            timeout_sec=TIMEOUT_QUERY_HEAVY,
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


# --- Medias PB (cache em memoria, TTL 6h) -------------------------------
_PB_MEDIAS_CACHE: dict = {"value": None, "expires_at": 0.0}
_PB_MEDIAS_TTL_SECONDS = 6 * 60 * 60


def get_pb_medias() -> dict:
    """Agregados dos 223 municipios da PB. Cached em memoria por 6h."""
    now = time.time()
    if _PB_MEDIAS_CACHE["value"] and now < _PB_MEDIAS_CACHE["expires_at"]:
        return _PB_MEDIAS_CACHE["value"]
    try:
        cols, rows = execute_query(PB_MEDIAS, {}, timeout_sec=TIMEOUT_PROFILE)
        medias = _row_to_dict(cols, rows[0]) if rows else {}
    except Exception:
        medias = {}
    _PB_MEDIAS_CACHE["value"] = medias
    _PB_MEDIAS_CACHE["expires_at"] = now + _PB_MEDIAS_TTL_SECONDS
    return medias


def _fmt_brl_narrative(value) -> str:
    """Formata valor em R$ para narrativa: 'R$ 187 mi', 'R$ 3,2 mi', 'R$ 450 mil'."""
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        return "R$ 0"
    if n >= 1_000_000_000:
        return f"R$ {n / 1_000_000_000:.1f} bi".replace(".", ",")
    if n >= 1_000_000:
        val = n / 1_000_000
        if val >= 10:
            return f"R$ {val:.0f} mi"
        return f"R$ {val:.1f} mi".replace(".", ",")
    if n >= 1_000:
        return f"R$ {n / 1_000:.0f} mil"
    return f"R$ {n:,.0f}".replace(",", ".")


def _fmt_pct(value, decimals: int = 1) -> str:
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        return "0%"
    if decimals == 0 or n >= 10:
        return f"{n:.0f}%"
    return f"{n:.1f}%".replace(".", ",")


def _compare_vs_mediana(valor, mediana, higher_is_worse: bool = True) -> str:
    """Retorna texto curto: 'acima da m&eacute;dia PB', 'pr&oacute;ximo da m&eacute;dia', 'abaixo da m&eacute;dia'."""
    try:
        v = float(valor or 0)
        m = float(mediana or 0)
    except (TypeError, ValueError):
        return ""
    if m <= 0:
        return ""
    delta = (v - m) / m
    if abs(delta) < 0.10:
        return "pr&oacute;ximo da m&eacute;dia da Para&iacute;ba"
    if delta > 0:
        return "acima da m&eacute;dia da Para&iacute;ba" if higher_is_worse else "acima da m&eacute;dia da Para&iacute;ba"
    return "abaixo da m&eacute;dia da Para&iacute;ba" if higher_is_worse else "abaixo da m&eacute;dia da Para&iacute;ba"


def build_narrative(perfil: dict, medias: dict | None = None) -> dict:
    """Monta narrativa humana a partir do perfil + agregados PB.

    Retorna dict com chaves `citizen` (HTML para modo cidadao) e `auditor`
    (HTML para modo auditor) — ambas prontas para |safe no template.
    """
    medias = medias or {}
    municipio = (perfil.get("municipio") or "Este munic&iacute;pio").title()
    total_empenhado = perfil.get("total_empenhado") or 0
    total_pago = perfil.get("total_pago") or 0
    qtd_fornecedores = int(perfil.get("qtd_fornecedores") or 0)
    pct_sem_licitacao = perfil.get("pct_sem_licitacao") or 0
    risco_score = perfil.get("risco_score")
    pct_folha = perfil.get("pct_folha_receita") or 0

    pct_pago = 0.0
    try:
        if float(total_empenhado or 0) > 0:
            pct_pago = 100.0 * float(total_pago) / float(total_empenhado)
    except (TypeError, ValueError):
        pct_pago = 0.0

    mediana_risco = medias.get("mediana_risco")
    mediana_pct_sem_licitacao = medias.get("mediana_pct_sem_licitacao")

    # ----- Cidadao -----
    qtd_forn_fmt = f"{qtd_fornecedores:,}".replace(",", ".")
    frag_citizen = [f"A prefeitura de <strong>{municipio}</strong> j&aacute; pagou "
                    f"<a href=\"#fornecedores\"><strong>{_fmt_brl_narrative(total_pago)}</strong></a> "
                    f"a <a href=\"#fornecedores\"><strong>{qtd_forn_fmt}</strong> empresas</a>."]

    if pct_sem_licitacao:
        cmp_sl = _compare_vs_mediana(pct_sem_licitacao, mediana_pct_sem_licitacao, higher_is_worse=True)
        sl_txt = (
            f" Desse dinheiro, <a href=\"#licitacoes\"><strong>{_fmt_pct(pct_sem_licitacao)}</strong> "
            f"saiu em compras sem concorr&ecirc;ncia</a>"
        )
        if cmp_sl and mediana_pct_sem_licitacao:
            sl_txt += f" — {cmp_sl} (mediana: {_fmt_pct(mediana_pct_sem_licitacao)})"
        sl_txt += "."
        frag_citizen.append(sl_txt)

    if risco_score is not None:
        cmp_nota = _compare_vs_mediana(risco_score, mediana_risco, higher_is_worse=True)
        nota_txt = (
            f" A <a href=\"#relatorio\"><strong>nota de aten&ccedil;&atilde;o</strong></a> desta cidade "
            f"&eacute; <strong>{float(risco_score):.0f}/100</strong>"
        )
        if cmp_nota and mediana_risco is not None:
            nota_txt += f" — {cmp_nota} (mediana PB: {float(mediana_risco):.0f})"
        nota_txt += "."
        frag_citizen.append(nota_txt)

    citizen_html = "".join(frag_citizen)

    # ----- Auditor -----
    frag_auditor = [
        f"<strong>{municipio}</strong>: "
        f"{_fmt_brl_narrative(total_empenhado)} empenhado / "
        f"<a href=\"#fornecedores\">{_fmt_brl_narrative(total_pago)} pago</a> "
        f"({_fmt_pct(pct_pago, decimals=1)})."
    ]
    if pct_sem_licitacao:
        frag_auditor.append(
            f" <a href=\"#licitacoes\">Dispensa/inexigibilidade: {_fmt_pct(pct_sem_licitacao)}</a>"
            + (f" (p50 PB: {_fmt_pct(mediana_pct_sem_licitacao)})" if mediana_pct_sem_licitacao else "")
            + "."
        )
    if pct_folha:
        frag_auditor.append(f" Folha/receita: {_fmt_pct(pct_folha)}.")
    if risco_score is not None:
        frag_auditor.append(
            f" <a href=\"#relatorio\">Risco composto: {float(risco_score):.0f}/100</a>"
            + (f" (p50 PB: {float(mediana_risco):.0f})" if mediana_risco is not None else "")
            + "."
        )
    auditor_html = "".join(frag_auditor)

    return {"citizen": citizen_html, "auditor": auditor_html}


# ── Destaques (Fase 3) ──────────────────────────────────────────
# Achados traduzidos em uma frase, renderizados acima das seções técnicas
# em modo cidadão. Cada entrada descreve como agregar uma query cacheada
# em um card com ícone + número + frase + link "Ver detalhes".
#
# Campos:
#   - query_id: id da query no registry (usa web_cache)
#   - icon: emoji
#   - severity: "red" | "orange" | "yellow" (cor da borda/ícone)
#   - template: frase (suporta {brl}, {qtd}, {plural})
#   - section_slug: âncora de scroll (slug da SECTION_META)
#   - value_col: coluna a somar para {brl} (vazio = não mostra valor)
#   - count_col: coluna a contar distinct para {qtd}; None = conta linhas
#   - min_value: limiar mínimo do total somado para mostrar o card
#   - min_count: limiar mínimo da contagem para mostrar o card
DESTAQUES_SPEC = [
    {
        "query_id": "Q65",
        "icon": "&#128681;",  # 🚩
        "severity": "red",
        "template": "<strong>{brl}</strong> pagos a <strong>{qtd}</strong> empresa{plural} punida{plural} por fraude",
        "section_slug": "fornecedores-irregulares",
        "value_col": "total_pago",
        "count_col": "cpf_cnpj_sancionado",
        "min_value": 10_000,
        "min_count": 1,
    },
    {
        "query_id": "Q67",
        "icon": "&#128181;",  # 💵
        "severity": "orange",
        "template": "<strong>{brl}</strong> pagos a <strong>{qtd}</strong> empresa{plural} devendo impostos federais",
        "section_slug": "fornecedores-irregulares",
        "value_col": "total_pago",
        "count_col": "cnpj_basico",
        "min_value": 50_000,
        "min_count": 1,
    },
    {
        "query_id": "Q70",
        "icon": "&#9888;&#65039;",  # ⚠️
        "severity": "orange",
        "template": "<strong>{brl}</strong> pagos a <strong>{qtd}</strong> empresa{plural} com cadastro irregular na Receita",
        "section_slug": "fornecedores-irregulares",
        "value_col": "total_pago",
        "count_col": "cpf_cnpj",
        "min_value": 50_000,
        "min_count": 1,
    },
    {
        "query_id": "Q77",
        "icon": "&#129513;",  # 🧩
        "severity": "yellow",
        "template": "<strong>{qtd}</strong> caso{plural} de compras fatiadas (indicio de fracionamento)",
        "section_slug": "licitacoes",
        "value_col": "",
        "count_col": None,  # conta linhas
        "min_value": 0,
        "min_count": 2,
    },
    {
        "query_id": "Q71",
        "icon": "&#127968;",  # 🏠
        "severity": "yellow",
        "template": "<strong>{qtd}</strong> empresa{plural} registrada{plural} no mesmo endere&ccedil;o receberam pagamento",
        "section_slug": "licitacoes",
        "value_col": "",
        "count_col": "cnpj_basico",
        "min_value": 0,
        "min_count": 2,
    },
    {
        "query_id": "Q61",
        "icon": "&#128202;",  # 📊
        "severity": "yellow",
        "template": "<strong>{qtd}</strong> fornecedor{plural_es} com diferen&ccedil;a atipica entre empenhado e pago",
        "section_slug": "orcamento",
        "value_col": "",
        "count_col": None,
        "min_value": 0,
        "min_count": 5,
    },
]


def _fmt_int_br(n: int) -> str:
    return f"{int(n):,}".replace(",", ".")


def _destaque_plural(n: int, form: str = "s") -> str:
    """Retorna '' para n<=1, sufixo plural caso contrário."""
    return form if n > 1 else ""


def _aggregate_destaque(spec: dict, cols: list[str], rows: list[tuple]) -> tuple[float, int]:
    """Soma value_col e conta count_col (ou linhas) a partir dos rows do cache."""
    if not rows:
        return 0.0, 0
    val_idx = cols.index(spec["value_col"]) if spec.get("value_col") and spec["value_col"] in cols else -1
    total = 0.0
    if val_idx >= 0:
        for r in rows:
            try:
                total += float(r[val_idx] or 0)
            except (TypeError, ValueError):
                pass
    count_col = spec.get("count_col")
    if count_col is None:
        qtd = len(rows)
    else:
        cnt_idx = cols.index(count_col) if count_col in cols else -1
        if cnt_idx < 0:
            qtd = len(rows)
        else:
            qtd = len({r[cnt_idx] for r in rows if r[cnt_idx] is not None})
    return total, qtd


def pick_destaques(municipio: str, max_cards: int = 5) -> list[dict]:
    """Monta lista de destaques para o modo cidadão a partir do web_cache.

    Retorna uma lista de dicts prontos para o template `partials/destaques.html`:
        {icon, severity, html, section_slug, query_id, total, qtd}
    Vazia se nenhum achado passa dos limiares (template pode mostrar zero-state).
    """
    cards: list[dict] = []
    for spec in DESTAQUES_SPEC:
        cached = read_web_cache(spec["query_id"], municipio)
        if not cached:
            continue
        cols, rows = cached
        total, qtd = _aggregate_destaque(spec, cols, rows)
        if qtd < spec.get("min_count", 1):
            continue
        if spec.get("value_col") and total < spec.get("min_value", 0):
            continue
        brl = _fmt_brl_narrative(total) if spec.get("value_col") else ""
        plural = _destaque_plural(qtd, "s")
        plural_es = _destaque_plural(qtd, "es")
        html = spec["template"].format(
            brl=brl,
            qtd=_fmt_int_br(qtd),
            plural=plural,
            plural_es=plural_es,
        )
        cards.append({
            "icon": spec["icon"],
            "severity": spec["severity"],
            "html": html,
            "section_slug": spec["section_slug"],
            "query_id": spec["query_id"],
            "total": total,
            "qtd": qtd,
            "_sort_key": (qtd * total) if spec.get("value_col") else qtd * 1000,
        })
    # Ordena por gravidade (red > orange > yellow) e depois por impacto (_sort_key)
    sev_order = {"red": 0, "orange": 1, "yellow": 2}
    cards.sort(key=lambda c: (sev_order.get(c["severity"], 9), -c["_sort_key"]))
    return cards[:max_cards]


def _build_report_sections(pb_only: bool = True):
    sections = []
    for category, queries in get_categories():
        meta = SECTION_META[category]
        sections.append(
            {
                "slug": meta["slug"],
                "title": meta["title"],
                "title_lay": meta.get("title_lay", ""),
                "description": meta["description"],
                "description_lay": meta.get("description_lay", ""),
                "queries": queries,
            }
        )
    return sections


def _servidor_severity_key(s: dict) -> tuple:
    """Sort key: red severity (0), yellow (1), rest (2), then by -maior_salario."""
    is_red = bool(
        s.get('flag_ceaf_expulso')
        or (s.get('total_pago_durante_vinculo') and s['total_pago_durante_vinculo'] > 0)
        or s.get('flag_socio_inidoneidade')
    )
    is_yellow = bool(s.get('flag_socio_sancionado') or s.get('flag_bolsa_familia'))
    severity = 0 if is_red else (1 if is_yellow else 2)
    salary = -(s.get('maior_salario') or 0)
    return (severity, salary)


def _render_result_table(request: Request, title: str, cols: list[str], rows: list[tuple]):
    from web.main import templates

    items = [_row_to_dict(cols, row) for row in rows]

    # Sort by sanction severity when abrangencia column exists: red first, yellow, rest
    if 'abrangencia' in cols:
        def _sancao_sort_key(item):
            abr = str(item.get('abrangencia', '') or '')
            cat = str(item.get('categoria_sancao', '') or '')
            if 'inidone' in cat.lower() or 'Nacional' in abr or 'Todas as Esferas' in abr:
                return 0
            if abr:
                return 1
            return 2
        items.sort(key=_sancao_sort_key)

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

    perfil = None
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

    if not perfil:
        return templates.TemplateResponse(
            request,
            "results/cidade.html",
            {
                "municipio": municipio,
                "uf": "PB",
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

    narrative = build_narrative(perfil, get_pb_medias())
    destaques = pick_destaques(municipio)

    return templates.TemplateResponse(
        request,
        "results/cidade.html",
        {
            "municipio": municipio,
            "uf": "PB",
            "perfil": perfil,
            **date_ctx,
            "fornecedores": [],
            "servidores": [],
            "report_sections": _build_report_sections(),
            "narrative": narrative,
            "destaques": destaques,
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
    except Exception:
        return JSONResponse([])
    # rows are (nome, uf, rank_val) - todos PB
    return JSONResponse([r[0] for r in rows])


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
    periodo = _get_periodo(payload)

    if _has_date_filter(payload):
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
        if cached:
            cols, rows = cached
        else:
            cols, rows = _load_top_fornecedores(municipio)
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
    has_dates = _has_date_filter(payload)
    periodo = _get_periodo(payload) if has_dates else ""
    if has_dates:
        params = _date_params(payload)
        cached = read_web_cache("TOP_SERVIDORES", municipio, periodo) if periodo != "CUSTOM" else None
        if cached:
            cols, rows = cached
        else:
            cols, rows = _load_top_servidores(municipio, params)
    else:
        cached = read_web_cache("TOP_SERVIDORES", municipio)
        if cached:
            cols, rows = cached
        else:
            cols, rows = _load_top_servidores(municipio)
    servidores = [_row_to_dict(cols, row) for row in rows]
    servidores.sort(key=_servidor_severity_key)
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


@router.get("/api/heatmap/{municipio_path}")
async def get_heatmap(municipio_path: str):
    """Retorna grade (ano, mes) -> total_empenhado para heatmap mensal."""
    municipio = _normalize_municipio(municipio_path)
    cols: list[str] = []
    rows: list[tuple] = []
    try:
        cached = read_web_cache("HEATMAP", municipio)
    except Exception:
        cached = None
    if cached:
        cols, rows = cached
    else:
        try:
            cols, rows = cached_query(
                f"heatmap:{municipio.casefold()}",
                HEATMAP_MENSAL,
                {"municipio": municipio},
                timeout_sec=TIMEOUT_QUERY_LIGHT,
            )
        except (QueryCanceled, Exception):
            return JSONResponse({"cells": []})
    cells = [_row_to_json_dict(cols, r) for r in rows]
    return JSONResponse({"cells": cells})


@router.get("/api/heatmap/{municipio_path}/{ano}/{mes}")
async def get_heatmap_mes(municipio_path: str, ano: int, mes: int):
    """Drill-down de um mes especifico: resumo, top fornecedores, top elementos."""
    municipio = _normalize_municipio(municipio_path)
    if not (1 <= mes <= 12) or not (2000 <= ano <= 2100):
        return JSONResponse({"error": "parametros invalidos"}, status_code=400)
    mes_str = f"{mes:02d}"
    params = {"municipio": municipio, "ano": ano, "mes": mes_str}
    try:
        rcols, rrows = execute_query(HEATMAP_MES_RESUMO, params, timeout_sec=TIMEOUT_QUERY_LIGHT)
        fcols, frows = execute_query(HEATMAP_MES_FORNECEDORES, params, timeout_sec=TIMEOUT_QUERY_LIGHT)
        ecols, erows = execute_query(HEATMAP_MES_ELEMENTOS, params, timeout_sec=TIMEOUT_QUERY_LIGHT)
        fucols, furows = execute_query(HEATMAP_MES_FUNCOES, params, timeout_sec=TIMEOUT_QUERY_LIGHT)
        mcols, mrows = execute_query(HEATMAP_MES_MODALIDADES, params, timeout_sec=TIMEOUT_QUERY_LIGHT)
        emcols, emrows = execute_query(HEATMAP_MES_EMPENHOS, params, timeout_sec=TIMEOUT_QUERY_LIGHT)
    except (QueryCanceled, Exception) as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return JSONResponse({
        "resumo": _row_to_json_dict(rcols, rrows[0]) if rrows else {},
        "fornecedores": [_row_to_json_dict(fcols, r) for r in frows],
        "elementos": [_row_to_json_dict(ecols, r) for r in erows],
        "funcoes": [_row_to_json_dict(fucols, r) for r in furows],
        "modalidades": [_row_to_json_dict(mcols, r) for r in mrows],
        "empenhos": [_row_to_json_dict(emcols, r) for r in emrows],
    })


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

                # Bolsa Família (apenas durante vínculo ativo)
                cur.execute("""
                    WITH vinculo AS (
                        SELECT COALESCE(TO_CHAR(MIN(data_admissao), 'YYYYMM'), MIN(ano_mes)) AS inicio,
                               MAX(ano_mes) AS fim
                        FROM tce_pb_servidor
                        WHERE cpf_digitos_6 = %s AND nome_upper = %s
                          AND ano_mes >= '2022-01'
                    )
                    SELECT bf.mes_competencia, bf.valor_parcela, bf.nm_municipio
                    FROM bolsa_familia bf, vinculo v
                    WHERE bf.cpf_digitos = %s
                      AND UPPER(TRIM(bf.nm_favorecido)) = %s
                      AND bf.mes_competencia >= v.inicio
                      AND bf.mes_competencia <= v.fim
                    ORDER BY bf.mes_competencia DESC
                    LIMIT 5
                """, (cpf6, nome, cpf6, nome))
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
                               esfera_orgao_sancionador, abrangencia_sancao,
                               dt_inicio_sancao, dt_final_sancao
                        FROM ceis_sancao
                        WHERE LEFT(cpf_cnpj_sancionado, 8) IN ({ph})
                          AND LENGTH(cpf_cnpj_sancionado) = 14
                        UNION ALL
                        SELECT LEFT(cpf_cnpj_sancionado, 8) AS cnpj_basico,
                               'CNEP' AS fonte,
                               nome_sancionado, categoria_sancao, orgao_sancionador,
                               esfera_orgao_sancionador, abrangencia_sancao,
                               dt_inicio_sancao, dt_final_sancao
                        FROM cnep_sancao
                        WHERE LEFT(cpf_cnpj_sancionado, 8) IN ({ph})
                          AND LENGTH(cpf_cnpj_sancionado) = 14
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
    nome_credor = payload.get("nome_credor", "")
    cpf_cnpj = payload.get("cpf_cnpj", "")
    if not cnpj_basico:
        return JSONResponse({})
    try:
        from web.db import get_conn
        result = {}
        with get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                # Build filters: prefer cpf_cnpj (exact entity), fallback to cnpj_basico + nome_credor
                if cpf_cnpj:
                    id_clause = "cpf_cnpj = %s AND municipio = %s"
                    id_params = [cpf_cnpj, municipio]
                else:
                    nc_clause = " AND nome_credor = %s" if nome_credor else ""
                    id_clause = f"cnpj_basico = %s AND municipio = %s{nc_clause}"
                    id_params = [cnpj_basico, municipio] + ([nome_credor] if nome_credor else [])

                # Empenhos recentes no municipio
                cur.execute(f"""
                    SELECT id, numero_empenho, data_empenho, elemento_despesa,
                           valor_empenhado, valor_pago,
                           modalidade_licitacao, numero_licitacao
                    FROM tce_pb_despesa
                    WHERE {id_clause}
                      AND valor_pago > 0
                    ORDER BY data_empenho DESC
                    LIMIT 50
                """, id_params)
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
                cur.execute(f"""
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
                    WHERE {id_clause}
                      AND valor_pago > 0
                """, id_params)
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
                cur.execute(f"""
                    SELECT TO_CHAR(data_empenho, 'YYYY-MM') AS mes,
                           SUM(valor_pago) AS total_mes
                    FROM tce_pb_despesa
                    WHERE {id_clause}
                      AND valor_pago > 0
                      AND data_empenho >= (CURRENT_DATE - INTERVAL '12 months')
                    GROUP BY TO_CHAR(data_empenho, 'YYYY-MM')
                    ORDER BY mes
                """, id_params)
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
                cur.execute(f"""
                    SELECT elemento_despesa,
                           SUM(valor_pago) AS total_elemento,
                           COUNT(*) AS qtd
                    FROM tce_pb_despesa
                    WHERE {id_clause}
                      AND valor_pago > 0
                    GROUP BY elemento_despesa
                    ORDER BY SUM(valor_pago) DESC
                    LIMIT 3
                """, id_params)
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
                           orgao_sancionador, esfera_orgao_sancionador, fundamentacao_legal,
                           abrangencia_sancao
                    FROM ceis_sancao
                    WHERE LEFT(cpf_cnpj_sancionado, 8) = %s
                      AND LENGTH(cpf_cnpj_sancionado) = 14
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
                           orgao_sancionador, esfera_orgao_sancionador, fundamentacao_legal, valor_multa,
                           abrangencia_sancao
                    FROM cnep_sancao
                    WHERE LEFT(cpf_cnpj_sancionado, 8) = %s
                      AND LENGTH(cpf_cnpj_sancionado) = 14
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
                    if cpf_cnpj:
                        outros_where = "d.cpf_cnpj = %s AND d.municipio != %s"
                        outros_params = [cpf_cnpj, municipio]
                    else:
                        outros_nc = " AND d.nome_credor = %s" if nome_credor else ""
                        outros_where = f"d.cnpj_basico = %s AND d.municipio != %s{outros_nc}"
                        outros_params = [cnpj_basico, municipio] + ([nome_credor] if nome_credor else [])
                    cur.execute(f"""
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
                            AND EXISTS (SELECT 1 FROM estabelecimento est WHERE est.cnpj_completo = d.cpf_cnpj)
                        WHERE {outros_where}
                          AND d.valor_pago > 0
                          AND d.data_empenho >= san.dt_inicio_sancao
                          AND (san.dt_final_sancao IS NULL OR d.data_empenho <= san.dt_final_sancao)
                        GROUP BY d.municipio
                        ORDER BY total_pago DESC
                    """, outros_params)
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
                if cpf_cnpj:
                    mun_where = "cpf_cnpj = %s AND valor_pago > 0"
                    mun_params = [cpf_cnpj]
                else:
                    mun_nc = " AND nome_credor = %s" if nome_credor else ""
                    mun_where = f"cnpj_basico = %s AND valor_pago > 0{mun_nc}"
                    mun_params = [cnpj_basico] + ([nome_credor] if nome_credor else [])
                cur.execute(f"""
                    SELECT municipio, SUM(valor_pago) AS total_pago
                    FROM tce_pb_despesa
                    WHERE {mun_where}
                    GROUP BY municipio
                    ORDER BY total_pago DESC
                """, mun_params)
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
                if cpf_cnpj:
                    est_where = "est.cnpj_completo = %s"
                    est_params = (cpf_cnpj,)
                else:
                    est_where = "est.cnpj_basico = %s AND est.cnpj_ordem = '0001'"
                    est_params = (cnpj_basico,)
                cur.execute(f"""
                    SELECT situacao_cadastral, dt_situacao,
                           cnpj_completo, cnae_principal, uf,
                           COALESCE(dm.descricao, est.municipio) AS municipio
                    FROM estabelecimento est
                    LEFT JOIN dom_municipio dm ON dm.codigo = est.municipio
                    WHERE {est_where}
                """, est_params)
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
    modalidade = payload.get("modalidade", "")
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
                      AND (%s = '' OR modalidade = %s)
                    LIMIT 1
                """, (numero, municipio, ano, ano, modalidade, modalidade))
                cols = [d[0] for d in cur.description]
                rows = cur.fetchall()
                if rows:
                    result["licitacao"] = _convert(_row_to_dict(cols, rows[0]))

                # Proponentes
                cur.execute("""
                    SELECT l.nome_proponente, l.cpf_cnpj_proponente,
                           SUM(l.valor_ofertado) AS valor_ofertado,
                           MAX(l.situacao_proposta) AS situacao_proposta,
                           MAX(e.razao_social) AS razao_social
                    FROM tce_pb_licitacao l
                    LEFT JOIN empresa e ON e.cnpj_basico = l.cnpj_basico_proponente
                    WHERE l.numero_licitacao = %s AND l.municipio = %s
                      AND (%s = 0 OR l.ano_licitacao = %s)
                      AND (%s = '' OR l.modalidade = %s)
                    GROUP BY l.nome_proponente, l.cpf_cnpj_proponente
                    ORDER BY SUM(l.valor_ofertado) DESC
                """, (numero, municipio, ano, ano, modalidade, modalidade))
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
