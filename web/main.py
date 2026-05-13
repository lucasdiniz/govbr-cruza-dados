"""FastAPI app — govbr-cruza-dados frontend."""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web import db
from web.routes.cidade import router as cidade_router
from web.routes.empresa import router as empresa_router
from web.routes.mapa import router as mapa_router
from web.routes.og_image import router as og_router
from web.routes.contato import build_router as build_contato_router
from web.routes.seo import router as seo_router

_dir = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_pool()
    yield
    db.close_pool()


app = FastAPI(title="govbr-cruza-dados", lifespan=lifespan)

# ─────────────────────────────────────────────────────────────────────────
# API defense middleware: bloqueia POSTs em /api/* que nao tenham Origin
# ou Referer batendo com hosts permitidos. Filtra scripts (curl, requests,
# scrapy) que nao setam Origin por default. NAO eh seguranca contra
# atacante motivado (Origin eh trivial de forjar), mas elimina ~90% do
# noise de bots/automation casual sem prejudicar UX de browser legitimo.
# ─────────────────────────────────────────────────────────────────────────

_ALLOWED_API_HOSTS = {
    "transparenciapb.org",
    "www.transparenciapb.org",
    "localhost",
    "127.0.0.1",
}


def _host_from_url(value: str) -> str:
    """Extrai 'host' (netloc sem porta) de uma URL ou retorna ''."""
    if not value:
        return ""
    from urllib.parse import urlparse
    try:
        parsed = urlparse(value)
        netloc = (parsed.netloc or "").lower()
        if ":" in netloc:
            netloc = netloc.split(":", 1)[0]
        return netloc
    except Exception:
        return ""


@app.middleware("http")
async def head_as_get(request: Request, call_next):
    """Crawlers (Googlebot, Bing, GSC) usam HEAD pra validar sitemap e
    URLs rapido sem baixar body. FastAPI/Starlette por padrao soh aceita
    GET em @router.get() — HEAD retorna 405. Esse middleware muta o
    method pra GET internamente, deixa a rota processar normal, e descarta
    o body antes de retornar — RFC 7231 §4.3.2: HEAD deve retornar mesmos
    headers que GET sem body.

    Sem isso, GSC reportava 'Couldn't fetch' em /sitemap-cidades.xml e
    /sitemap-empresas-N.xml.
    """
    if request.method == "HEAD":
        request.scope["method"] = "GET"
        response = await call_next(request)
        # Consome o body iterator pra evitar leak/hang, descarta bytes.
        body_iter = getattr(response, "body_iterator", None)
        if body_iter is not None:
            try:
                async for _ in body_iter:
                    pass
            except Exception:
                pass
        from starlette.responses import Response as _Response
        # Preserva content-type, content-length, cache-control etc.
        return _Response(
            content=b"",
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
    return await call_next(request)


@app.middleware("http")
async def api_origin_guard(request: Request, call_next):
    """Rejeita POST /api/* se Origin nao bate com hosts permitidos.

    GETs ficam livres (autocomplete, heatmap, export usam GET) — sao
    cacheaveis e idempotentes. POSTs sao os que causam carga de DB.
    """
    if request.method == "POST" and request.url.path.startswith("/api/"):
        origin_host = _host_from_url(request.headers.get("origin", ""))
        # Fallback: alguns clients (e GitHub link previews) nao setam Origin
        # mas setam Referer. Aceita qualquer um.
        referer_host = _host_from_url(request.headers.get("referer", ""))
        request_host = origin_host or referer_host
        if not request_host or request_host not in _ALLOWED_API_HOSTS:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                {"error": "Forbidden: Origin/Referer não permitido"},
                status_code=403,
            )
    return await call_next(request)


app.mount("/static", StaticFiles(directory=_dir / "static"), name="static")

templates = Jinja2Templates(directory=_dir / "templates")


def _format_short_number(value: Any) -> str:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return "-"
    abs_number = abs(number)
    if abs_number >= 1_000_000_000:
        return f"{number / 1_000_000_000:.1f} bi"
    if abs_number >= 1_000_000:
        return f"{number / 1_000_000:.1f} mi"
    if abs_number >= 1_000:
        return f"{number / 1_000:.1f} mil"
    return f"{number:,.0f}".replace(",", ".")


def _format_short_brl(value: Any) -> str:
    return f"R$ {_format_short_number(value)}"


def _clean_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    replacements = {
        "\ufffd": "",
        "SERVIOS": "SERVICOS",
        "CESSO": "CESSAO",
        "ESTGIO": "ESTAGIO",
        "SADE": "SAUDE",
    }
    cleaned = value
    for source, target in replacements.items():
        cleaned = cleaned.replace(source, target)
    return cleaned


def _format_date_br(value: Any) -> str:
    """Formata data ISO YYYY-MM-DD pra DD/MM/AAAA (formato BR).

    Aceita:
    - string ISO 'YYYY-MM-DD' ou 'YYYY-MM-DDTHH:MM:SS'
    - date/datetime objects
    - None / vazio -> '-'
    Robusto: se nao parse-avel, retorna o valor original (defesa).
    """
    if value is None or value == "":
        return "-"
    s = str(value)
    # Aceita ISO completa ou date-only. Pega so os 10 primeiros chars
    # (YYYY-MM-DD).
    iso = s[:10]
    if len(iso) != 10 or iso[4] != "-" or iso[7] != "-":
        return s  # nao parece ISO, devolve original
    try:
        yyyy, mm, dd = iso.split("-")
        return f"{dd}/{mm}/{yyyy}"
    except (ValueError, IndexError):
        return s


templates.env.filters["short_number"] = _format_short_number
templates.env.filters["short_brl"] = _format_short_brl
templates.env.filters["clean_text"] = _clean_text
templates.env.filters["date_br"] = _format_date_br


# ----------- Metadata de colunas para tabelas de achados (Fase 1/cidadao) -----------
# Cada entrada define:
#   - citizen: label leigo (ou None para esconder)
#   - auditor: label tecnico (fallback: col|replace|title)
#   - auditor_only: True => coluna some em modo cidadao
# Colunas nao listadas caem no fallback (label unica = default Jinja).
COLUMN_META: dict[str, dict[str, Any]] = {
    # IDs e documentos crus — auditor-only
    "cnpj_basico":          {"auditor": "CNPJ Basico",         "auditor_only": True},
    "cnpj_completo":        {"auditor": "CNPJ Completo",       "auditor_only": True},
    "cpf_cnpj":             {"auditor": "CPF/CNPJ",            "auditor_only": True},
    "cpf_cnpj_sancionado":  {"auditor": "CPF/CNPJ Sancionado", "auditor_only": True},
    "cpfcnpj_contratado":   {"auditor": "CPF/CNPJ Contratado", "auditor_only": True},
    "cpf_cnpj_proponente":  {"auditor": "CPF/CNPJ Proponente", "auditor_only": True},
    "cpf_digitos_6":        {"auditor": "CPF (6 digitos)",     "auditor_only": True},
    "cpf_digitos":          {"auditor": "CPF Digitos",         "auditor_only": True},
    "nome_upper":           {"auditor": "Nome Upper",          "auditor_only": True},
    "numero_empenho":       {"auditor": "Numero Empenho",      "auditor_only": True},
    "numero_licitacao":     {"auditor": "Numero Licitacao",    "auditor_only": True},
    "numero_contrato":      {"auditor": "Numero Contrato",     "auditor_only": True},
    "ano_mes":              {"auditor": "Ano-Mes",             "auditor_only": True},
    "cnpjs_socio":          {"auditor": "CNPJs Socio",         "auditor_only": True},
    "cnpjs_vinculo":        {"auditor": "CNPJs Vinculo",       "auditor_only": True},
    "risco_score":          {"auditor": "Risco Score",         "auditor_only": True},

    # Nomes / entidades
    "razao_social":         {"citizen": "Empresa",             "auditor": "Razao Social"},
    "nome_credor":          {"citizen": "Empresa",             "auditor": "Nome Credor"},
    "nome_sancionado":      {"citizen": "Empresa punida",      "auditor": "Nome Sancionado"},
    "nome_servidor":        {"citizen": "Servidor",            "auditor": "Nome Servidor"},
    "nome_proponente":      {"citizen": "Empresa participante", "auditor": "Nome Proponente"},
    "nome_contratado":      {"citizen": "Empresa contratada",  "auditor": "Nome Contratado"},
    "socio_nome":           {"citizen": "Socio",               "auditor": "Socio Nome"},
    "doador":               {"citizen": "Doador de campanha",  "auditor": "Doador"},
    "candidato":            {"citizen": "Candidato",           "auditor": "Candidato"},
    "orgao":                {"citizen": "Orgao",               "auditor": "Orgao"},
    "orgao_sancionador":    {"citizen": "Quem aplicou a punicao", "auditor": "Orgao Sancionador"},
    "municipio":            {"citizen": "Municipio",           "auditor": "Municipio"},

    # Valores monetarios
    "valor_empenhado":      {"citizen": "Reservado",           "auditor": "Valor Empenhado"},
    "valor_pago":           {"citizen": "Pago",                "auditor": "Valor Pago"},
    "valor_contratado":     {"citizen": "Contratado",          "auditor": "Valor Contratado"},
    "valor_sancao":         {"citizen": "Valor da punicao",    "auditor": "Valor Sancao"},
    "valor_divida":         {"citizen": "Divida",              "auditor": "Valor Divida"},
    "valor_doacao":         {"citizen": "Doacao",              "auditor": "Valor Doacao"},
    "total_pago":           {"citizen": "Recebido",            "auditor": "Total Pago"},
    "total_empenhado":      {"citizen": "Total reservado",     "auditor": "Total Empenhado"},
    "total_contratado":     {"citizen": "Total contratado",    "auditor": "Total Contratado"},
    "capital_social":       {"citizen": "Capital social",      "auditor": "Capital Social"},
    "maior_salario":        {"citizen": "Maior salario",       "auditor": "Maior Salario"},
    "salario":              {"citizen": "Salario",             "auditor": "Salario"},

    # Contadores e percentuais
    "qtd_empenhos":         {"citizen": "Qtd pagamentos",      "auditor": "Qtd Empenhos", "auditor_only": True},
    "qtd_contratos":        {"citizen": "Qtd contratos",       "auditor": "Qtd Contratos"},
    "qtd_empresas_socio":   {"citizen": "Empresas onde e socio", "auditor": "Qtd Empresas Socio"},
    "pct_sem_licitacao":    {"citizen": "% sem concorrencia",  "auditor": "Pct Sem Licitacao"},
    "pct_dezembro":         {"citizen": "% em dezembro",       "auditor": "Pct Dezembro"},
    "pct_proponente_unico": {"citizen": "% com um so proponente", "auditor": "Pct Proponente Unico"},

    # Classificacoes / descritores
    "modalidade":           {"citizen": "Tipo de licitacao",   "auditor": "Modalidade"},
    "modalidade_licitacao": {"citizen": "Tipo de licitacao",   "auditor": "Modalidade Licitacao"},
    "elemento_despesa":     {"citizen": "Tipo de gasto",       "auditor": "Elemento Despesa"},
    "funcao":               {"citizen": "Area do gasto",       "auditor": "Funcao"},
    "subfuncao":            {"citizen": "Sub-area",            "auditor": "Subfuncao"},
    "categoria_sancao":     {"citizen": "Tipo de punicao",     "auditor": "Categoria Sancao"},
    "abrangencia":          {"citizen": "Alcance da punicao",  "auditor": "Abrangencia"},
    "situacao_cadastral":   {"citizen": "Cadastro",            "auditor": "Situacao Cadastral"},
    "desc_situacao":        {"citizen": "Cadastro",            "auditor": "Desc Situacao"},
    "cargo":                {"citizen": "Cargo",               "auditor": "Cargo"},

    # Datas
    "data_empenho":         {"citizen": "Data",                "auditor": "Data Empenho"},
    "data":                 {"citizen": "Data",                "auditor": "Data"},
    "dt_inicio_sancao":     {"citizen": "Inicio da punicao",   "auditor": "Dt Inicio Sancao"},
    "dt_final_sancao":      {"citizen": "Fim da punicao",      "auditor": "Dt Final Sancao"},
    "data_abertura":        {"citizen": "Abertura",            "auditor": "Data Abertura"},
    "ano":                  {"citizen": "Ano",                 "auditor": "Ano"},
    "mes":                  {"citizen": "Mes",                 "auditor": "Mes"},

    # Flags (booleanos) — exibem Sim/Nao
    "flag_ceis":            {"citizen": "Impedida (CEIS)",     "auditor": "Flag CEIS",           "auditor_only": True},
    "flag_cnep":            {"citizen": "Punida (CNEP)",       "auditor": "Flag CNEP",           "auditor_only": True},
    "flag_pgfn":            {"citizen": "Deve impostos",       "auditor": "Flag PGFN",           "auditor_only": True},
    "flag_inativa":         {"citizen": "Empresa inativa",     "auditor": "Flag Inativa",        "auditor_only": True},
    "flag_inativa_irregular": {"citizen": "Recebeu apos baixa", "auditor": "Recebeu Pos-Inativa", "auditor_only": True},
    "flag_inidoneidade":    {"citizen": "Proibida contratar",  "auditor": "Flag Inidoneidade",   "auditor_only": True},
    "flag_acordo_leniencia": {"citizen": "Acordo leniencia",   "auditor": "Flag Acordo Leniencia", "auditor_only": True},
}


def column_label(col: str, mode: str = "auditor") -> str:
    """Retorna label para uma coluna (fallback: col.replace('_',' ').title())."""
    meta = COLUMN_META.get(col, {})
    if mode == "citizen" and meta.get("citizen"):
        return meta["citizen"]
    if meta.get("auditor"):
        return meta["auditor"]
    return col.replace("_", " ").title()


def column_is_auditor_only(col: str) -> bool:
    return bool(COLUMN_META.get(col, {}).get("auditor_only"))


templates.env.globals["COLUMN_META"] = COLUMN_META
templates.env.globals["column_label"] = column_label
templates.env.globals["column_is_auditor_only"] = column_is_auditor_only

# Data de refresh dos dados (Fase 8 - badge de credibilidade).
# Lida de env DATA_REFRESH_DATE (formato YYYY-MM-DD); se ausente, usa mes/ano atuais.
_data_refresh = os.environ.get("DATA_REFRESH_DATE", "").strip()
if not _data_refresh:
    from datetime import datetime as _dt_now, timedelta as _td, timezone as _tz
    _data_refresh = _dt_now.now(_tz(_td(hours=-3))).strftime("%Y-%m-%d")
# Formato amigavel pt-BR (DD/MM/YYYY). Entrada pode ser YYYY-MM-DD ou ja formatada.
try:
    from datetime import datetime as _dt
    _data_refresh_br = _dt.strptime(_data_refresh, "%Y-%m-%d").strftime("%d/%m/%Y")
except Exception:
    _data_refresh_br = _data_refresh
templates.env.globals["DATA_REFRESH_DATE"] = _data_refresh_br
templates.env.globals["DATA_REFRESH_DATE_ISO"] = _data_refresh

# SEO: verification meta tags (Search Console / Bing Webmaster Tools).
# Codigos vem do dashboard de cada provedor; basta colar a string token.
# Setar GOOGLE_SITE_VERIFICATION / BING_SITE_VERIFICATION no ENV_FILE
# secret do GitHub Actions (e .env local pra dev). Ver SEO ops checklist.
templates.env.globals["GOOGLE_SITE_VERIFICATION"] = os.environ.get(
    "GOOGLE_SITE_VERIFICATION", ""
).strip()
templates.env.globals["BING_SITE_VERIFICATION"] = os.environ.get(
    "BING_SITE_VERIFICATION", ""
).strip()

# Umami analytics (self-hosted em /_traffic/analytics/, ver
# deploy/setup-umami.sh + deploy/cruza-umami.service).
# O snippet so eh emitido em base.html quando AMBAS as vars estao setadas,
# entao o app continua funcionando sem analytics enquanto o painel nao for
# provisionado / nao tiver website cadastrado.
#
#   UMAMI_SCRIPT_URL    URL (relativa ou absoluta) do tracker JS, ex:
#                       /_traffic/analytics/script.js
#   UMAMI_WEBSITE_ID    UUID do "Website" cadastrado no painel Umami
#                       (login admin -> Settings -> Websites -> Add).
#
# Manter a URL como env var (em vez de hardcoded) permite desligar o
# tracker via .env sem mudanca de codigo.
templates.env.globals["UMAMI_SCRIPT_URL"] = os.environ.get(
    "UMAMI_SCRIPT_URL", ""
).strip()
templates.env.globals["UMAMI_WEBSITE_ID"] = os.environ.get(
    "UMAMI_WEBSITE_ID", ""
).strip()

# JS load order. Each entry is a path relative to /static/js/, emitted as
# an individual <script> tag in base.html. Order matters because the scripts
# are plain (non-module) and rely on cross-file globals — files are loaded
# in the same order they appeared in the original app.js.
#
# This is intentionally hard-coded here (versioned with code) rather than
# read from a manifest file at startup, because:
#   * .gitignore excludes *.txt at the repo root, so an external manifest
#     would silently disappear from a fresh clone.
#   * Adding/removing a script is a code change and deserves a code review.
#   * No file I/O at startup; less fragility.
#
# When adding a new component, append it here in the position that respects
# any cross-file references (most files don't have hard ordering needs).
JS_FILES: list[str] = [
    # umami-track: wrapper safe pra window.umami.track. Precisa carregar
    # ANTES de qualquer componente que dispare trackEvent() — primeiro item.
    "lib/umami-track.js",
    # scroll-deep: depende do trackEvent helper acima.
    "lib/scroll-deep.js",
    # page-engagement: tempo na pagina + scroll max no pagehide.
    # Depende do trackEvent helper. Init em pages/main.js.
    "lib/page-engagement.js",
    # dialog-engagement: pareia dialog-aberto com dialog-fechado.
    # Listener self-attaching via lib/umami-track.js -> document
    # 'tpb:tracked' CustomEvent. Init em pages/main.js.
    "lib/dialog-engagement.js",
    # redes-sociais-popup: CTA once-per-user pra seguir IG+X +
    # tracking delegado de clicks em [data-rede-social]. Init em
    # pages/main.js. Inclui deep-link pro app no mobile.
    "components/redes-sociais-popup.js",
    "components/search-tabs.js",
    "components/mode-toggle.js",
    # md3-ready helper. Must load early so any later script can register
    # readiness callbacks for <md-*> elements (full bundle is in the deferred
    # ES module web/static/js/md3/imports.js).
    "lib/md3-ready.js",
    "lib/dual-label.js",
    "lib/slug.js",
    "lib/column-meta.js",
    "components/term-tooltip.js",
    "lib/expand-context.js",
    "components/narrative-anchors.js",
    "components/anchor-auto-expand.js",
    "components/explainers.js",
    "components/mobile-descriptions.js",
    "components/credibility-dialog.js",
    "components/font-toggle.js",
    "components/overflow-menu.js",
    "components/tour.js",
    "components/denuncia-dialog.js",
    "components/snackbar.js",
    "components/back-to-top.js",
    "components/topnav-elevation.js",
    "components/share.js",
    "components/autocomplete.js",
    "pages/cidade-bootstrap.js",
    "components/finding-card.js",
    "components/result-table.js",
    "lib/format.js",
    "components/top-fornecedores.js",
    "lib/cnpj-format.js",
    "components/date-filter.js",
    "components/date-filter-ui.js",
    "components/hero-stats.js",
    "components/kpi-strip.js",
    "components/concentracao-card.js",
    "pages/cidade-refresh-kpis.js",
    "components/heatmap.js",
    "pages/cidade-refresh-perfil.js",
    "components/dialog-nav.js",
    "components/dialog-history-swipe.js",
    "components/dialog-url-state.js",
    "lib/skeleton.js",
    "components/dialog-links.js",
    "components/dialog-table-sort.js",
    "components/dialog-decorate.js",
    "lib/api.js",
    "components/empenho-table.js",
    "components/empresa-card.js",
    "components/servidor-dialog.js",
    "components/fornecedor-dialog.js",
    "components/heatmap-dialog.js",
    "components/empenho-dialog.js",
    "components/licitacao-dialog.js",
    "components/top-servidores.js",
    "pages/cidade-async-panels.js",
    "components/report-sections.js",
    "lib/run-limited.js",
    "components/data-table.js",
    "components/clickable-rows.js",
    "components/empenhos-controller.js",
    "pages/main.js",
]
templates.env.globals["JS_FILES"] = JS_FILES
templates.env.globals["ASSET_VERSION"] = "110"


# ─────────────────────────────────────────────────────────────────────────
# Asset manifest (build pipeline em scripts/build-assets.mjs).
#
# Em prod, web/static/dist/manifest.json mapeia nomes lógicos
# ("core.js", "mapa.js", "index.css") -> filenames com hash content-based
# ("core.<hash>.min.js"). Templates usam {{ asset_url('core.js') }}.
#
# Modo dev (sem build): asset_url() devolve URL raw para o arquivo original
# (não minificado), com cache buster ?v=ASSET_VERSION. Permite rodar
# `uvicorn` localmente sem rodar `npm run build` antes.
#
# Em prod, exportar ASSETS_STRICT=1 (deploy.yml seta isso) para FALHAR LOUD
# se o manifest sumir ou ficar inconsistente — evita servir URLs raw quando
# o usuário esperaria as hashed (debugging hard).
# ─────────────────────────────────────────────────────────────────────────

_ASSET_MANIFEST_PATH = _dir / "static" / "dist" / "manifest.json"
_ASSETS_STRICT = os.environ.get("ASSETS_STRICT", "").strip() in ("1", "true", "True", "yes")

# Mapa nome lógico -> path raw (relativo a /static/) usado como fallback
# quando manifest está ausente (dev). Mantém os mesmos arquivos servidos
# antes do build pipeline.
_ASSET_RAW_FALLBACKS: dict[str, str] = {
    "core.js": None,  # core.js não tem fallback unitário — em dev, JS_FILES é renderizado um por um.
    "mapa.js": "/static/js/pages/mapa.js",
    "index.css": "/static/css/index.css",
}


def _load_asset_manifest() -> dict[str, str] | None:
    if not _ASSET_MANIFEST_PATH.exists():
        if _ASSETS_STRICT:
            raise RuntimeError(
                f"ASSETS_STRICT=1 mas manifest ausente em {_ASSET_MANIFEST_PATH}. "
                "Rode `npm run build` ou desative ASSETS_STRICT pra servir assets raw."
            )
        return None
    try:
        import json as _json
        data = _json.loads(_ASSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        if _ASSETS_STRICT:
            raise RuntimeError(f"Manifest corrupto ({_ASSET_MANIFEST_PATH}): {exc}")
        return None
    # Validacao mínima: chaves obrigatórias presentes em prod.
    if _ASSETS_STRICT:
        missing = [k for k in ("core.js", "mapa.js", "index.css") if k not in data]
        if missing:
            raise RuntimeError(
                f"Manifest em {_ASSET_MANIFEST_PATH} sem chaves obrigatórias: {missing}"
            )
        # Validação extra: arquivos referenciados existem fisicamente em dist/.
        # Sem isso, um manifest válido apontando pra arquivos faltantes
        # passaria startup e produziria 404 em runtime.
        dist_dir = _ASSET_MANIFEST_PATH.parent
        ghost = []
        for key in ("core.js", "mapa.js", "index.css"):
            filename = data.get(key)
            if not filename:
                continue
            if not (dist_dir / filename).is_file():
                ghost.append(f"{key} -> {filename}")
        if ghost:
            raise RuntimeError(
                f"Manifest aponta pra arquivos ausentes em {dist_dir}: {ghost}"
            )
    return data


_ASSET_MANIFEST: dict[str, str] | None = _load_asset_manifest()


def asset_url(logical_name: str) -> str:
    """Retorna URL do asset.
    Em prod (manifest carregado): /static/dist/<hashed-name>.
    Em dev (sem manifest): caminho raw com ?v=ASSET_VERSION.
    """
    if _ASSET_MANIFEST and logical_name in _ASSET_MANIFEST:
        return f"/static/dist/{_ASSET_MANIFEST[logical_name]}"
    fallback = _ASSET_RAW_FALLBACKS.get(logical_name)
    if fallback:
        return f"{fallback}?v={templates.env.globals['ASSET_VERSION']}"
    raise KeyError(f"asset_url: nome lógico desconhecido sem fallback: {logical_name!r}")


def has_asset_bundle(logical_name: str) -> bool:
    """True se manifest tem bundle hashed pra este nome (modo prod)."""
    return bool(_ASSET_MANIFEST and logical_name in _ASSET_MANIFEST)


templates.env.globals["asset_url"] = asset_url
templates.env.globals["has_asset_bundle"] = has_asset_bundle
templates.env.globals["ASSETS_STRICT"] = _ASSETS_STRICT


# ─────────────────────────────────────────────────────────────────────────
# SEO helpers — canonical URL e detecção de URL com state de dialog.
# ─────────────────────────────────────────────────────────────────────────

_DIALOG_QUERY_PARAMS_PREFIX = ("d_",)
_DIALOG_QUERY_PARAM_EXACT = "d"


def _request_origin(request: Request) -> str:
    """Origem efetiva (esquema + host) — respeita reverse proxy headers."""
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme or "https"
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.netloc
    return f"{proto}://{host}".rstrip("/")


def canonical_url(request: Request) -> str:
    """URL canonica: mesma URL atual mas SEM query params do dialog state.

    Strip de `d=...` e `d_*=...` evita duplicate-content em buscas quando
    usuarios compartilham deep-links (ex: ?d=fornecedor&d_cnpj=...). A URL
    canonica fica sempre apontando pra pagina sem dialog.
    """
    origin = _request_origin(request)
    path = request.url.path
    kept = []
    for key, value in request.query_params.multi_items():
        if key == _DIALOG_QUERY_PARAM_EXACT:
            continue
        if any(key.startswith(p) for p in _DIALOG_QUERY_PARAMS_PREFIX):
            continue
        kept.append((key, value))
    if not kept:
        return f"{origin}{path}"
    from urllib.parse import urlencode
    return f"{origin}{path}?{urlencode(kept)}"


def is_dialog_state_url(request: Request) -> bool:
    """True se a URL atual contem state de dialog (?d=... ou ?d_*=...).

    Usado pra emitir <meta name='robots' content='noindex,follow'> nessas
    URLs — evita que crawlers indexem versoes 'com dialog aberto' como
    paginas separadas.
    """
    qp = request.query_params
    if _DIALOG_QUERY_PARAM_EXACT in qp:
        return True
    return any(any(k.startswith(p) for p in _DIALOG_QUERY_PARAMS_PREFIX) for k in qp.keys())


templates.env.globals["canonical_url"] = canonical_url
templates.env.globals["is_dialog_state_url"] = is_dialog_state_url
templates.env.globals["request_origin"] = _request_origin

# Helper de slug pra URLs amigaveis (/cidade/<slug>). Mesma logica em
# web/utils/slug.py garante que sitemap, links em HTML e a rota /cidade/{slug}
# usem a forma canonica (acento removido, lowercase, hifens normalizados).
from web.utils.slug import municipio_slug as _municipio_slug
templates.env.globals["municipio_slug"] = _municipio_slug
templates.env.filters["municipio_slug"] = _municipio_slug


app.include_router(cidade_router)
app.include_router(empresa_router)
app.include_router(mapa_router)
app.include_router(og_router)
app.include_router(build_contato_router(templates))
app.include_router(seo_router)


# Fase 12 - erros amigaveis em vez de stack traces
from fastapi.exceptions import HTTPException as _HTTPException
from starlette.exceptions import HTTPException as _StarletteHTTPException
from fastapi.responses import HTMLResponse as _HTMLResponse
import logging as _logging
import uuid as _uuid

_err_log = _logging.getLogger("transparencia.web")


@app.exception_handler(404)
@app.exception_handler(_StarletteHTTPException)
async def _handle_http_exception(request: Request, exc):
    status_code = getattr(exc, "status_code", 500)
    if status_code == 404:
        return templates.TemplateResponse(
            request, "errors/404.html",
            {"path": str(request.url.path)},
            status_code=404,
        )
    # Outros HTTPException (405, 503, etc): devolve resposta padrao do
    # Starlette (status code + message text). NAO re-raise — isso cairia
    # no _handle_unexpected e viraria 500 estilizado, escondendo o status
    # real. Crawlers (Googlebot, Bing) usam HEAD pra validar sitemap;
    # FastAPI ate aceita HEAD em rotas GET, mas se a rota nao define HEAD
    # explicitamente algumas versoes retornam 405. Devolvendo o 405 puro,
    # o crawler interpreta como "rota existe, vou usar GET" em vez de
    # "servidor quebrado, ignora". (Bug: GSC reportava 'Couldn't fetch'
    # nos sitemaps porque 500 era retornado em vez de 405/200.)
    from starlette.responses import PlainTextResponse
    headers = getattr(exc, "headers", None) or {}
    detail = getattr(exc, "detail", "") or ""
    return PlainTextResponse(
        str(detail) if detail else "",
        status_code=status_code,
        headers=headers,
    )


@app.exception_handler(Exception)
async def _handle_unexpected(request: Request, exc: Exception):
    error_id = _uuid.uuid4().hex[:8]
    _err_log.exception("Unhandled error [%s] on %s", error_id, request.url.path)
    # Para chamadas XHR/fetch (HTMX, fetch API, JSON), devolve fragmento minimo
    # em vez da pagina HTML completa — evita injetar header duplicado em paineis async.
    accept = (request.headers.get("accept") or "").lower()
    is_xhr = (
        request.headers.get("hx-request") == "true"
        or request.headers.get("x-requested-with")
        or "application/json" in accept
        or request.url.path.startswith("/api/")
    )
    if is_xhr:
        from fastapi.responses import HTMLResponse
        return HTMLResponse(
            f'<p class="text-sm text-muted">Nao foi possivel carregar este bloco agora. (ref: {error_id})</p>',
            status_code=500,
        )
    return templates.TemplateResponse(
        request, "errors/500.html",
        {"error_id": error_id},
        status_code=500,
    )


@app.get("/")
async def index(request: Request):
    from web.routes.cidade import get_pb_medias
    try:
        municipio_total_pb = int(get_pb_medias().get("n_municipios") or 223)
    except Exception:
        municipio_total_pb = 223
    return templates.TemplateResponse(
        request,
        "index.html",
        {"municipio_total_pb": municipio_total_pb},
    )


@app.get("/sw.js")
async def service_worker():
    return FileResponse(_dir / "static" / "sw.js", media_type="application/javascript")


@app.get("/glossario")
async def glossario(request: Request):
    return templates.TemplateResponse(request, "glossario.html")


@app.get("/sobre")
async def sobre(request: Request):
    """Pagina /sobre: metodologia + fontes + limitacoes (E-E-A-T pra SEO)."""
    return templates.TemplateResponse(request, "sobre.html")


# ─────────────────────────────────────────────────────────────────────────
# Casos investigativos — relatorios em markdown renderizados como HTML
# ─────────────────────────────────────────────────────────────────────────
# Cada entrada referencia um relatorio em /relatorios/*.md. Hard-coded para
# manter controle sobre quais relatorios sao publicos no site (vs. so no
# GitHub).
CASOS: dict[str, dict[str, str]] = {
    "socorro-gadelha": {
        "file": "relatorios/relatorio_caso_socorro_gadelha_pb.md",
        "title": "Caso Socorro Gadelha — Secretaria expulsa pela CGU em cargo municipal de mesma pasta",
        "description": (
            "Maria do Socorro Gadelha Campos de Lira foi destituida pela CGU em "
            "29/12/2022 por violar a moralidade administrativa. Segue Secretaria "
            "Municipal de Habitacao Social de Joao Pessoa (gestao Cicero Lucena, PP) "
            "ha mais de 4 anos. Em 26/08/2025 a ALPB aprovou conceder a ela a "
            "Medalha Epitacio Pessoa. Caso identificado pelo cruzamento CEAF x folha "
            "no transparenciapb.org."
        ),
        "painel_url": (
            "/cidade/joao-pessoa?d=servidor&d_cpf6=256054"
            "&d_nome=MARIA+DO+SOCORRO+GADELHA+CAMPOS+DE+LIRA"
            "&d_snome=MARIA+DO+SOCORRO+GADELHA+CAMPOS+DE+LIRA"
            "&d_cnpjs=13519354&d_tab=dialog-section-3"
        ),
        "data_publicacao": "2026-05-11",
        "og_image": "/static/img/casos/socorro-foto.jpg",
        "hero_image": "/static/img/casos/socorro-foto.jpg",
        "hero_alt": (
            "Maria do Socorro Gadelha Campos de Lira, Secretária Municipal de "
            "Habitação Social de João Pessoa, em audiência pública na Câmara "
            "Municipal em 04/06/2024."
        ),
        "hero_caption": (
            "Maria do Socorro Gadelha Campos de Lira, atual Secretária "
            "Municipal de Habitação Social de João Pessoa, em audiência "
            "pública na Câmara Municipal em 04/06/2024. "
            "Foto: Câmara Municipal de João Pessoa."
        ),
    },
}

_REPO_ROOT = _dir.parent  # web/ -> repo root


def _render_markdown(md_text: str) -> str:
    """Renderiza markdown -> HTML com extensoes uteis (tabelas, attrs, toc)."""
    import markdown as _md
    return _md.markdown(
        md_text,
        extensions=[
            "tables",
            "fenced_code",
            "attr_list",
            "sane_lists",
            "smarty",
            "toc",
        ],
        output_format="html5",
    )


@app.get("/caso/{slug}")
async def caso(request: Request, slug: str):
    """Renderiza um relatorio investigativo em /relatorios/*.md como pagina web.

    URL canonica para divulgacao do caso (X/Twitter, Instagram, e-mail
    pra redacoes). Substitui o link direto pro GitHub e mantem o trafego
    no dominio proprio.
    """
    meta = CASOS.get(slug)
    if not meta:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Caso nao encontrado"}, status_code=404)

    md_path = _REPO_ROOT / meta["file"]
    if not md_path.is_file():
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "Relatorio nao localizado"}, status_code=500)

    md_text = md_path.read_text(encoding="utf-8")
    html = _render_markdown(md_text)

    # Extrai o H1 do markdown renderizado para colocar antes do hero;
    # o resto do conteudo segue depois do hero e dos CTAs.
    import re as _re
    h1_match = _re.search(r"<h1[^>]*>.*?</h1>", html, flags=_re.DOTALL)
    titulo_html = h1_match.group(0) if h1_match else ""
    corpo_html = html[h1_match.end():] if h1_match else html

    return templates.TemplateResponse(
        request,
        "caso.html",
        {
            "slug": slug,
            "meta": meta,
            "titulo_html": titulo_html,
            "conteudo_html": corpo_html,
        },
    )
