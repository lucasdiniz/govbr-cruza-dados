"""Registry de KPIs investigativos da pagina /search/cidade.

Cada KPI eh um KPIDef com:
  - metadata fixa (id, labels, anchor link, tooltip)
  - uma funcao compute(ctx) que recebe o contexto agregado e devolve
    {value, severity, value_extra?, value_suffix?, is_money?}.

O contexto eh construido uma unica vez por _build_context() a partir do
perfil do municipio + listas de fornecedores e servidores ja cacheadas
em web_cache. Adicionar um KPI novo = escrever uma funcao + uma linha em
CIDADE_KPIS abaixo.

Severidades: 'red' (sinal critico, exige verificacao), 'yellow' (atencao),
'neutral' (sem sinal ou contexto basal).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


# -----------------------------------------------------------------------------
# Constantes (parametros legais / limiares de alerta)
# -----------------------------------------------------------------------------

# Salario mensal acima do qual receber Bolsa Familia eh suspeito.
# Regra de Protecao do BF (Lei 14.601/2023, Decreto 11.699/2023): mantem
# o beneficio para familias com renda per capita ate R$706. Servidor com
# salario > R$5.000 dificilmente se enquadra mesmo com familia grande.
BF_SALARIO_SUSPEITO = 5000.0

# Limiares de concentracao de fornecedores
CONCENTRACAO_TOP1_RED = 20.0   # Top 1 ficando com >20% do dinheiro
CONCENTRACAO_TOP5_RED = 60.0   # Top 5 ficando com >60%
CONCENTRACAO_TOP5_YELLOW = 40.0


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def to_float(v: Any) -> float:
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def sev_count(n: int, red_at: int = 1, yellow_at: int = 0) -> str:
    """Severidade para metricas de contagem (>= red_at vermelho, > yellow_at amarelo)."""
    if n >= red_at:
        return "red"
    if n > yellow_at:
        return "yellow"
    return "neutral"


def sev_money(value: float, red_at: float = 0.01) -> str:
    """Severidade para metricas monetarias (qualquer valor > 0 = vermelho por default)."""
    return "red" if value >= red_at else "neutral"


# -----------------------------------------------------------------------------
# Definicao do registry
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class KPIDef:
    id: str
    label_citizen: str
    label_auditor: str
    href: str         # ancora para a section detalhada (#slug)
    tooltip: str
    compute: Callable[[dict], dict]


# -----------------------------------------------------------------------------
# Construcao do contexto
# -----------------------------------------------------------------------------

def _build_context(
    perfil: dict | None,
    fornecedores: list[dict],
    servidores: list[dict],
) -> dict:
    """Agrega todos os sinais necessarios pelos KPIs em um dict reutilizavel.

    Single source of truth: cada agregacao acontece UMA vez aqui, e depois
    cada KPI consulta o ctx.
    """
    perfil = perfil or {}
    total_pago = to_float(perfil.get("total_pago"))

    # ---- Fornecedores -------------------------------------------------------
    sancao_qualquer = 0
    sancao_municipio = 0
    inativas_recebendo = 0
    for f in fornecedores:
        info = str(f.get("abrangencia_sancao_info") or "")
        is_municipio = info.startswith("!")
        has_ceis = bool(f.get("flag_ceis"))
        has_cnep = bool(f.get("flag_cnep"))
        has_idn = bool(f.get("flag_inidoneidade"))
        has_acordo = bool(f.get("flag_acordo_leniencia"))
        if has_ceis or has_cnep or has_idn or has_acordo:
            sancao_qualquer += 1
        if is_municipio or has_idn or has_acordo:
            sancao_municipio += 1
        if f.get("flag_inativa"):
            inativas_recebendo += 1

    # ---- Concentracao top fornecedores --------------------------------------
    forn_sorted = sorted(
        fornecedores,
        key=lambda r: to_float(r.get("total_pago")),
        reverse=True,
    )
    top5 = forn_sorted[:5]
    top_concentracao = []
    for rank, f in enumerate(top5, 1):
        valor = to_float(f.get("total_pago"))
        pct = (valor / total_pago * 100.0) if total_pago > 0 else 0.0
        nome = (f.get("razao_social") or f.get("nome_credor") or "").strip()
        top_concentracao.append({
            "rank": rank,
            "nome": nome,
            "cnpj_completo": f.get("cnpj_completo"),
            "cnpj_basico": f.get("cnpj_basico"),
            "total_pago": valor,
            "pct": pct,
            "is_red": pct > CONCENTRACAO_TOP1_RED,
        })
    pct_top1 = top_concentracao[0]["pct"] if top_concentracao else 0.0
    pct_top5 = sum(x["pct"] for x in top_concentracao)

    # ---- Servidores ---------------------------------------------------------
    bf_alto_salario = 0
    bf_total = 0
    ceaf_expulsos = 0
    socio_recebendo = 0
    total_pago_socios = 0.0
    for s in servidores:
        if s.get("flag_bolsa_familia"):
            bf_total += 1
            if to_float(s.get("maior_salario")) > BF_SALARIO_SUSPEITO:
                bf_alto_salario += 1
        if s.get("flag_ceaf_expulso"):
            ceaf_expulsos += 1
        if (s.get("qtd_empresas_socio") or 0) and to_float(s.get("total_pago_empresas")) > 0:
            socio_recebendo += 1
        total_pago_socios += to_float(s.get("total_pago_durante_vinculo"))

    return {
        "perfil": perfil,
        "total_pago": total_pago,
        # fornecedores
        "sancao_qualquer": sancao_qualquer,
        "sancao_municipio": sancao_municipio,
        "inativas_recebendo": inativas_recebendo,
        "pct_top1": pct_top1,
        "pct_top5": pct_top5,
        "top_concentracao": top_concentracao,
        # servidores
        "bf_alto_salario": bf_alto_salario,
        "bf_total": bf_total,
        "ceaf_expulsos": ceaf_expulsos,
        "socio_recebendo": socio_recebendo,
        "total_pago_socios": total_pago_socios,
    }


# -----------------------------------------------------------------------------
# Funcoes compute() — uma por KPI
# -----------------------------------------------------------------------------

def _compute_concentracao(ctx: dict) -> dict:
    pct5 = ctx["pct_top5"]
    pct1 = ctx["pct_top1"]
    if pct5 > CONCENTRACAO_TOP5_RED or pct1 > CONCENTRACAO_TOP1_RED:
        sev = "red"
    elif pct5 > CONCENTRACAO_TOP5_YELLOW:
        sev = "yellow"
    else:
        sev = "neutral"
    return {
        "value": round(pct5),
        "value_suffix": "%",
        "value_extra": f"Top 1 = {pct1:.1f}%" if pct1 > 0 else None,
        "severity": sev,
    }


def _compute_sancao_municipio(ctx: dict) -> dict:
    n = ctx["sancao_municipio"]
    return {"value": n, "severity": sev_count(n, red_at=1)}


def _compute_sancao_qualquer(ctx: dict) -> dict:
    n = ctx["sancao_qualquer"]
    return {"value": n, "severity": sev_count(n, red_at=3)}


def _compute_inativas(ctx: dict) -> dict:
    n = ctx["inativas_recebendo"]
    return {"value": n, "severity": sev_count(n, red_at=1)}


def _compute_ceaf(ctx: dict) -> dict:
    n = ctx["ceaf_expulsos"]
    return {"value": n, "severity": sev_count(n, red_at=1)}


def _compute_socio_recebendo(ctx: dict) -> dict:
    n = ctx["socio_recebendo"]
    return {"value": n, "severity": sev_count(n, red_at=3)}


def _compute_pago_socios(ctx: dict) -> dict:
    v = ctx["total_pago_socios"]
    return {"value": v, "is_money": True, "severity": sev_money(v)}


def _compute_bolsa_familia(ctx: dict) -> dict:
    n = ctx["bf_alto_salario"]
    total = ctx["bf_total"]
    extra = f"de {total} no BF" if total > n else None
    return {"value": n, "value_extra": extra, "severity": sev_count(n, red_at=1)}


# -----------------------------------------------------------------------------
# REGISTRY — ordem aqui = ordem visual na hero strip
# -----------------------------------------------------------------------------

CIDADE_KPIS: list[KPIDef] = [
    KPIDef(
        id="kpi-concentracao",
        label_citizen="Quanto do dinheiro vai para as 5 maiores",
        label_auditor="Concentracao nas top 5 fornecedoras",
        href="#concentracao-fornecedores",
        tooltip=(
            "Concentracao alta sugere baixa concorrencia ou direcionamento. "
            f"Limiares de alerta: Top 1 > {CONCENTRACAO_TOP1_RED:.0f}% "
            f"ou Top 5 > {CONCENTRACAO_TOP5_RED:.0f}% do total pago."
        ),
        compute=_compute_concentracao,
    ),
    KPIDef(
        id="kpi-sancao-municipio",
        label_citizen="Empresas sancionadas que atingem este municipio",
        label_auditor="Sancionadas com abrangencia no municipio",
        href="#fornecedores-irregulares",
        tooltip=(
            "Empresas com sancao de inidoneidade (nacional, Lei 14.133 art. 156 IV) "
            "ou de abrangencia que inclui este municipio. Por lei, a prefeitura nao "
            "deveria contratar."
        ),
        compute=_compute_sancao_municipio,
    ),
    KPIDef(
        id="kpi-sancao-qualquer",
        label_citizen="Empresas com sancao ativa fornecendo a prefeitura",
        label_auditor="Fornecedores em CEIS/CNEP (qualquer abrangencia)",
        href="#fornecedores-irregulares",
        tooltip=(
            "Inclui sancoes federais, estaduais e de outros municipios. Pode nao "
            "impedir contratacao aqui, mas merece verificacao."
        ),
        compute=_compute_sancao_qualquer,
    ),
    KPIDef(
        id="kpi-inativas",
        label_citizen="Empresas inativas / baixadas recebendo dinheiro",
        label_auditor="Fornecedores com situacao cadastral irregular",
        href="#fornecedores-irregulares",
        tooltip=(
            "Empresas que nao constam como ativas na Receita Federal mas mesmo "
            "assim aparecem recebendo da prefeitura. Pode indicar fraude ou erro "
            "cadastral grave."
        ),
        compute=_compute_inativas,
    ),
    KPIDef(
        id="kpi-ceaf",
        label_citizen="Servidores ja expulsos da Adm. Federal",
        label_auditor="Servidores em CEAF (expulsoes federais)",
        href="#conflitos",
        tooltip=(
            "Pessoas com registro de demissao por improbidade ou falta grave em "
            "orgaos federais e que aparecem na folha do municipio."
        ),
        compute=_compute_ceaf,
    ),
    KPIDef(
        id="kpi-socio-recebendo",
        label_citizen="Servidores que sao donos de empresas que recebem aqui",
        label_auditor="Servidores socios de fornecedores municipais",
        href="#conflitos",
        tooltip=(
            "A Lei 8.112/90 (federal) e o art. 9 da Lei 8.666/93 vedam essa "
            "pratica. No municipio, depende do estatuto local, mas o cruzamento "
            "sempre exige verificacao."
        ),
        compute=_compute_socio_recebendo,
    ),
    KPIDef(
        id="kpi-pago-socios",
        label_citizen="Total pago a empresas dos servidores",
        label_auditor="Pago a empresas de servidores durante vinculo",
        href="#conflitos",
        tooltip=(
            "Soma dos pagamentos do municipio para empresas onde o(a) servidor(a) "
            "era socio(a) NO MESMO PERIODO em que estava na folha. Forte indicio "
            "de conflito de interesses."
        ),
        compute=_compute_pago_socios,
    ),
    KPIDef(
        id="kpi-bolsa-familia",
        label_citizen="Servidores com salario alto + Bolsa Familia",
        label_auditor=f"Servidores BF + salario > R${BF_SALARIO_SUSPEITO/1000:.0f}k",
        href="#conflitos",
        tooltip=(
            "A Regra de Protecao do BF (Lei 14.601/2023) mantem o beneficio para "
            "renda per capita ate R$706. Servidor com salario alto dificilmente "
            "se enquadra mesmo com familia grande."
        ),
        compute=_compute_bolsa_familia,
    ),
]


# -----------------------------------------------------------------------------
# Entry point
# -----------------------------------------------------------------------------

def compute_cidade_kpis(
    perfil: dict | None,
    fornecedores: list[dict],
    servidores: list[dict],
) -> dict:
    """Renderiza todos os KPIs registrados em CIDADE_KPIS para um municipio.

    Retorna dict pronto para ser passado ao template:
      - kpis: list[dict] (um por card da hero strip)
      - top_concentracao: list[dict] (linhas do card de barras horizontais)
      - pct_top1, pct_top5, concentracao_red
    """
    ctx = _build_context(perfil, fornecedores, servidores)

    rendered: list[dict] = []
    for kdef in CIDADE_KPIS:
        result = kdef.compute(ctx)
        rendered.append({
            "id": kdef.id,
            "label_citizen": kdef.label_citizen,
            "label_auditor": kdef.label_auditor,
            "href": kdef.href,
            "tooltip": kdef.tooltip,
            **result,
        })

    return {
        "kpis": rendered,
        "top_concentracao": ctx["top_concentracao"],
        "pct_top1": ctx["pct_top1"],
        "pct_top5": ctx["pct_top5"],
        "concentracao_red": (
            ctx["pct_top1"] > CONCENTRACAO_TOP1_RED
            or ctx["pct_top5"] > CONCENTRACAO_TOP5_RED
        ),
    }
