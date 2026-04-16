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

app.include_router(cidade_router)
app.include_router(mapa_router)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html")
