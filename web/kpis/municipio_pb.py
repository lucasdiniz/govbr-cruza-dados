"""Definicao modular dos 8 KPIs de risco do municipio (Paraiba).

Este modulo eh a fonte de verdade declarativa para o "score unificado de
atencao" mostrado tanto no mapa coropletico (mv_municipio_pb_mapa.risco_score)
quanto na narrativa da pagina /search/cidade ("Nota de atencao: 73/100").

A computacao real dos 8 valores brutos por municipio mora em SQL na MV
mv_municipio_pb_kpi_score (sql/12_views.sql), porque precisa varrer todos
os 223 municipios. Este modulo:

  - Documenta cada KPI (id, label, peso, threshold de saturacao);
  - Expressa a normalizacao valor_bruto -> pontos (0..weight) que SQL e Python
    devem implementar identicamente;
  - Expoe uma funcao agregadora que recebe um dict {kpi_id: valor_bruto} e
    devolve o score unificado 0..100 + a contribuicao de cada KPI.

Para adicionar/ajustar um KPI: editar o registry KPI_MUNICIPIO_PB,
ajustar a SQL na MV correspondente, e bumpar a versao da MV.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


# -----------------------------------------------------------------------------
# Curva de normalizacao
# -----------------------------------------------------------------------------

def _concave(value: float, saturate_at: float, exponent: float = 0.6) -> float:
    """Normaliza valor 0..saturate_at para 0..1 com curva concava.

    Usada para contagens de eventos graves (1 caso ja eh sinal forte). Ex:
    com saturate=5 e exponent=0.6, value=1 retorna 0.41, value=2 retorna 0.62,
    value=5 retorna 1.0. O primeiro caso ja vale ~40% do peso.
    """
    if saturate_at <= 0 or value <= 0:
        return 0.0
    ratio = min(1.0, value / saturate_at)
    return ratio ** exponent


def _linear(value: float, saturate_at: float) -> float:
    """Normaliza valor 0..saturate_at para 0..1 linearmente. Para percentuais."""
    if saturate_at <= 0 or value <= 0:
        return 0.0
    return min(1.0, value / saturate_at)


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class KPIMunicipioDef:
    """Definicao de um KPI investigativo do municipio.

    - id: identificador unico (mesmo id usado em web/kpis/cidade.py).
    - mv_column: nome da coluna na mv_municipio_pb_kpi_score que carrega
      o valor bruto deste KPI.
    - label_citizen / label_auditor: rotulos curtos para narrativa.
    - weight: peso 0..100 na soma do score unificado. Soma dos pesos = 100.
    - saturate_at: valor bruto a partir do qual o KPI contribui com 100% do peso.
    - normalize: funcao (valor_bruto, saturate_at) -> ratio 0..1.
      Use _concave para contagens (1 caso ja eh forte) e _linear para percentuais.
    """

    id: str
    mv_column: str
    label_citizen: str
    label_auditor: str
    weight: int
    saturate_at: float
    normalize: Callable[[float, float], float]

    def points(self, raw_value: float | None) -> float:
        """Pontuacao 0..weight para este KPI dado o valor bruto."""
        v = float(raw_value or 0.0)
        return self.weight * self.normalize(v, self.saturate_at)


# Pesos somam 100. Ordem aqui = ordem usada nos breakdowns/explicacoes.
KPI_MUNICIPIO_PB: list[KPIMunicipioDef] = [
    KPIMunicipioDef(
        id="kpi-sancao-municipio",
        mv_column="qtd_sancao_municipio",
        label_citizen="Empresas sancionadas que atingem o municipio",
        label_auditor="Sancionadas com abrangencia no municipio",
        weight=15,
        saturate_at=3.0,
        normalize=_concave,
    ),
    KPIMunicipioDef(
        id="kpi-ceaf",
        mv_column="qtd_ceaf_expulsos",
        label_citizen="Servidores ja expulsos da Adm. Federal",
        label_auditor="Servidores em CEAF (expulsoes federais)",
        weight=15,
        saturate_at=5.0,
        normalize=_concave,
    ),
    KPIMunicipioDef(
        id="kpi-socio-recebendo",
        mv_column="qtd_socio_recebendo",
        label_citizen="Servidores donos de empresas que recebem aqui",
        label_auditor="Servidores socios de fornecedores municipais",
        weight=14,
        saturate_at=5.0,
        normalize=_concave,
    ),
    KPIMunicipioDef(
        id="kpi-pago-socios",
        mv_column="pct_pago_socios",
        label_citizen="% do gasto que vai para empresas dos servidores",
        label_auditor="% pago a empresas de servidores",
        weight=13,
        saturate_at=5.0,  # 5% do total_pago ja eh sinal grave
        normalize=_linear,
    ),
    KPIMunicipioDef(
        id="kpi-concentracao",
        mv_column="pct_top5",
        label_citizen="% do dinheiro nas 5 maiores fornecedoras",
        label_auditor="Concentracao top-5",
        weight=15,
        saturate_at=70.0,
        normalize=_linear,
    ),
    KPIMunicipioDef(
        id="kpi-inativas",
        mv_column="qtd_inativas_recebendo",
        label_citizen="Empresas inativas/baixadas recebendo dinheiro",
        label_auditor="Fornecedores com situacao cadastral irregular",
        weight=10,
        saturate_at=5.0,
        normalize=_concave,
    ),
    KPIMunicipioDef(
        id="kpi-bolsa-familia",
        mv_column="qtd_bf_alto_salario",
        label_citizen="Servidores no BF com salario alto",
        label_auditor="Servidores BF com salario > R$5k",
        weight=10,
        saturate_at=5.0,
        normalize=_concave,
    ),
    KPIMunicipioDef(
        id="kpi-sancao-qualquer",
        mv_column="qtd_sancao_qualquer",
        label_citizen="Empresas com sancao ativa fornecendo",
        label_auditor="Fornecedores em CEIS/CNEP (qualquer abrangencia)",
        weight=8,
        saturate_at=10.0,
        normalize=_concave,
    ),
]


assert sum(k.weight for k in KPI_MUNICIPIO_PB) == 100, (
    "Pesos dos KPIs de municipio devem somar 100"
)


# -----------------------------------------------------------------------------
# Agregador (referencia em Python; SQL faz o mesmo na MV)
# -----------------------------------------------------------------------------

def compute_score_unificado(raw: dict) -> dict:
    """Calcula o score unificado 0..100 a partir dos 8 valores brutos.

    `raw` deve ter as chaves listadas em KPIMunicipioDef.mv_column.
    Retorna {'score': int 0..100, 'breakdown': [{'id', 'label', 'pts', 'weight', 'value'}...]}.

    Usado em testes e para gerar tooltips/breakdowns na UI. A SQL da MV
    implementa a mesma formula direto em SQL para os 223 municipios.
    """
    breakdown = []
    total = 0.0
    for k in KPI_MUNICIPIO_PB:
        v = raw.get(k.mv_column)
        pts = k.points(v)
        total += pts
        breakdown.append({
            "id": k.id,
            "label": k.label_auditor,
            "pts": round(pts, 2),
            "weight": k.weight,
            "value": v,
        })
    return {"score": round(total), "breakdown": breakdown}


# -----------------------------------------------------------------------------
# Geracao do SQL CASE expression (mantem SQL e Python alinhados)
# -----------------------------------------------------------------------------

def sql_score_expression() -> str:
    """Retorna a expressao SQL que computa o score unificado 0..100.

    Usa as colunas brutas da mv_municipio_pb_kpi_score. Mantem-se em sincronia
    com compute_score_unificado() acima. Para curva concava (counts) usamos
    `LEAST(1, value/saturate)^0.6`; para linear (percentuais) `LEAST(1, value/saturate)`.

    NOTA: o componente `kpi-pago-socios` consome a coluna `pct_pago_socios`
    (ja arredondada a 2 casas na MV) — exatamente o mesmo valor que o Python
    recebe via PERFIL_MUNICIPIO. Isso evita o drift que apareceria se o SQL
    usasse a razao bruta total_pago_socios/total_pago_municipio.
    """
    parts = []
    for k in KPI_MUNICIPIO_PB:
        col = k.mv_column
        sat = k.saturate_at
        w = k.weight
        if k.normalize is _concave:
            ratio = f"POWER(LEAST(1.0, COALESCE({col}::numeric, 0) / {sat}::numeric), 0.6)"
        else:
            ratio = f"LEAST(1.0, COALESCE({col}::numeric, 0) / {sat}::numeric)"
        parts.append(f"{w} * {ratio}")
    inner = "\n      + ".join(parts)
    return f"GREATEST(0, LEAST(100, ROUND({inner})))::SMALLINT"


__all__ = [
    "KPIMunicipioDef",
    "KPI_MUNICIPIO_PB",
    "compute_score_unificado",
    "sql_score_expression",
]
