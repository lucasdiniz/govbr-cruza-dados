"""FastAPI app — govbr-cruza-dados frontend."""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from web import db
from web.routes.cidade import router as cidade_router
from web.routes.mapa import router as mapa_router

_dir = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_pool()
    yield
    db.close_pool()


app = FastAPI(title="govbr-cruza-dados", lifespan=lifespan)

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


templates.env.filters["short_number"] = _format_short_number
templates.env.filters["short_brl"] = _format_short_brl
templates.env.filters["clean_text"] = _clean_text


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


app.include_router(cidade_router)
app.include_router(mapa_router)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")
