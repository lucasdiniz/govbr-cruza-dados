"""Rota do mapa coropletico PB."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from web.db import cached_query
from web.config import CACHE_TTL

router = APIRouter()

MAPA_SQL = """
SELECT municipio, risco_score, pct_sem_licitacao, pct_irregulares,
       pct_top5, total_pago
FROM mv_municipio_pb_mapa
WHERE municipio IS NOT NULL
"""

# TCE-PB usa nomes antigos; GeoJSON IBGE usa nomes oficiais atuais.
# Mapa aplicado no endpoint para que o frontend case pelo nome atual.
MUNICIPIO_ALIASES = {
    "Joca Claudino": "Santarém",
    "São Vicente do Seridó": "Seridó",
    "Tacima": "Campo de Santana",
}


@router.get("/mapa")
async def mapa_pb(request: Request):
    from web.main import templates
    return templates.TemplateResponse(request, "mapa.html")


@router.get("/mapa/")
async def mapa_pb_trailing(request: Request):
    from web.main import templates
    return templates.TemplateResponse(request, "mapa.html")


@router.get("/api/mapa/pb")
async def api_mapa_pb():
    cols, rows = cached_query(
        "mapa:pb",
        MAPA_SQL,
        timeout_sec=10,
        ttl=CACHE_TTL,
    )
    data = {}
    for r in rows:
        d = dict(zip(cols, r))
        key = MUNICIPIO_ALIASES.get(d["municipio"], d["municipio"])
        data[key] = {
            "risco": int(d["risco_score"]) if d["risco_score"] is not None else None,
            "pct_sem_licitacao": float(d["pct_sem_licitacao"]) if d["pct_sem_licitacao"] is not None else None,
            "pct_irregulares": float(d["pct_irregulares"]) if d["pct_irregulares"] is not None else None,
            "pct_top5": float(d["pct_top5"]) if d["pct_top5"] is not None else None,
            "total_pago": float(d["total_pago"]) if d["total_pago"] is not None else 0.0,
        }
    return JSONResponse(data)
