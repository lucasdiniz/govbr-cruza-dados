"""Fase 11 - OG image dinamica para paginas de cidade."""

from __future__ import annotations

import hashlib
import io
import os
import time
import unicodedata
from pathlib import Path

from fastapi import APIRouter, Response
from fastapi.responses import FileResponse

from web.db import cached_query
from web.config import CACHE_TTL

try:
    from PIL import Image, ImageDraw, ImageFont  # type: ignore

    _PIL_OK = True
except Exception:  # pragma: no cover
    _PIL_OK = False

router = APIRouter()

_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "og_cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_TTL = 24 * 3600


def _norm_slug(name: str) -> str:
    n = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return "".join(c.lower() if c.isalnum() else "-" for c in n).strip("-")


def _font(size: int):
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _fetch_perfil(municipio: str) -> dict | None:
    sql = """
        SELECT municipio, risco_score, total_pago, pct_sem_licitacao
        FROM mv_municipio_pb_risco
        WHERE unaccent(lower(municipio)) = unaccent(lower(%(mun)s))
        LIMIT 1
    """
    try:
        cols, rows = cached_query(
            f"og:perfil:{municipio.lower()}",
            sql,
            params={"mun": municipio},
            timeout_sec=5,
            ttl=CACHE_TTL,
        )
    except Exception:
        return None
    if not rows:
        return None
    return dict(zip(cols, rows[0]))


def _fmt_brl(value) -> str:
    try:
        v = float(value or 0)
    except Exception:
        return "R$ 0"
    if abs(v) >= 1_000_000_000:
        return f"R$ {v / 1_000_000_000:.1f} bi".replace(".", ",")
    if abs(v) >= 1_000_000:
        return f"R$ {v / 1_000_000:.0f} mi"
    if abs(v) >= 1_000:
        return f"R$ {v / 1_000:.0f} mil"
    return f"R$ {v:.0f}"


def _render_png(municipio: str, perfil: dict | None) -> bytes:
    W, H = 1200, 630
    bg = (6, 10, 20)
    accent = (96, 165, 250)
    text_main = (243, 244, 246)
    text_muted = (156, 163, 175)

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # Gradiente simples no canto superior
    for y in range(140):
        a = int(35 * (1 - y / 140))
        draw.rectangle([(0, y), (W, y + 1)], fill=(6, 10, 20 + a))

    # Barra lateral colorida por severidade
    risco = int(perfil.get("risco_score") or 0) if perfil else 0
    if risco >= 75:
        bar = (220, 38, 38)
    elif risco >= 55:
        bar = (249, 115, 22)
    elif risco >= 35:
        bar = (234, 179, 8)
    else:
        bar = (34, 197, 94)
    draw.rectangle([(0, 0), (14, H)], fill=bar)

    # Logo/marca topo
    f_brand = _font(28)
    draw.text((48, 44), "TransparenciaPB", font=f_brand, fill=accent)

    # Titulo municipio
    f_title = _font(84)
    title = municipio
    draw.text((48, 150), title, font=f_title, fill=text_main)

    # Linha horizontal
    draw.line([(48, 270), (W - 48, 270)], fill=(75, 85, 99), width=2)

    # Metricas
    total_pago = _fmt_brl(perfil.get("total_pago") if perfil else 0)
    pct_sem = float(perfil.get("pct_sem_licitacao") or 0) if perfil else 0

    f_label = _font(26)
    f_value = _font(56)

    draw.text((48, 310), "Nota de atencao", font=f_label, fill=text_muted)
    draw.text((48, 344), f"{risco}/100", font=f_value, fill=bar)

    draw.text((440, 310), "Ja pago a fornecedores", font=f_label, fill=text_muted)
    draw.text((440, 344), total_pago, font=f_value, fill=text_main)

    draw.text((48, 460), "Compras sem licitacao", font=f_label, fill=text_muted)
    draw.text((48, 494), f"{pct_sem:.0f}%", font=f_value, fill=text_main)

    # Footer
    f_foot = _font(22)
    draw.text(
        (48, H - 56),
        "Dados abertos cruzados - transparencia-pb.com.br",
        font=f_foot,
        fill=text_muted,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


@router.get("/og/cidade/{slug}.png")
async def og_cidade(slug: str):
    if not _PIL_OK:
        return Response(status_code=501, content="Pillow nao instalado")
    safe_slug = _norm_slug(slug)
    if not safe_slug:
        return Response(status_code=400)

    cache_path = _CACHE_DIR / f"{safe_slug}.png"
    if cache_path.exists() and (time.time() - cache_path.stat().st_mtime) < _TTL:
        return FileResponse(cache_path, media_type="image/png")

    # Resolve slug -> nome de municipio (normalizado)
    # Busca em mv_municipio_pb_risco por slug aproximado
    sql = """
        SELECT municipio FROM mv_municipio_pb_risco
        WHERE lower(unaccent(replace(municipio, ' ', '-'))) = %(slug)s
        LIMIT 1
    """
    municipio = slug.replace("-", " ").title()
    try:
        cols, rows = cached_query(
            f"og:slug:{safe_slug}",
            sql,
            params={"slug": safe_slug},
            timeout_sec=5,
            ttl=CACHE_TTL,
        )
        if rows:
            municipio = rows[0][0]
    except Exception:
        pass

    perfil = _fetch_perfil(municipio)
    png = _render_png(municipio, perfil)

    try:
        cache_path.write_bytes(png)
    except Exception:
        pass
    return Response(content=png, media_type="image/png")
