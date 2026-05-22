"""Proxy/visualizacao de PDFs do DOE-TCE-PB (ADR-0014).

O publicacao.tce.pb.gov.br serve os PDFs com:
- Content-Disposition: attachment (forca download)
- X-Frame-Options: SAMEORIGIN (bloqueia iframe externo)

Para permitir embed no nosso site sem reproduzir a politica restritiva
da fonte, este endpoint:

1. Valida que o hash esta whitelistado em tce_pb_decisao (anti-open-proxy).
2. Cacheia localmente em /var/cache/cruza-web/tce-pb/<2-prefix>/<hash>.pdf
   (PDFs sao imutaveis por hash — TCE-PB usa o hash como ID estavel).
3. Reescreve Content-Disposition para inline (default) ou attachment
   (com ?download=1).
4. Streamada via FileResponse com Cache-Control de 30 dias.

Seguranca:
- HASH_RE garante apenas [a-f0-9]{32} (impede traversal).
- Rate limit via nginx (zone separada).
- Log de acesso com hash prefix + IP truncado (LGPD).
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import Optional
from urllib.request import Request as _UrlRequest, urlopen

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse

from web.db import get_conn
from web.queries.empresa import TCE_PB_DECISAO_BY_HASH

router = APIRouter()
_log = logging.getLogger("transparencia.tce_pb")

_HASH_RE = re.compile(r"^[a-f0-9]{32}$")
_TCE_BASE_URL = "https://publicacao.tce.pb.gov.br"
_CACHE_DIR = Path(os.environ.get(
    "TCE_PB_CACHE_DIR", "/var/cache/cruza-web/tce-pb"
))
_TIMEOUT_SECS = 60.0
_USER_AGENT = "transparenciapb-proxy/1.0 (+https://transparenciapb.org)"


def _hash_whitelisted(h: str) -> bool:
    """True se o hash esta em tce_pb_decisao (anti-open-proxy)."""
    try:
        with get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(TCE_PB_DECISAO_BY_HASH, (h,))
                return cur.fetchone() is not None
    except Exception:
        _log.exception("falha ao consultar tce_pb_decisao")
        return False


def _cache_path(h: str) -> Path:
    return _CACHE_DIR / h[:2] / f"{h}.pdf"


async def _fetch_and_cache(h: str) -> Optional[Path]:
    """Baixa o PDF do TCE-PB e grava no cache local. None em falha."""
    path = _cache_path(h)
    if path.exists() and path.stat().st_size > 1000:
        return path

    def _fetch_sync() -> Optional[bytes]:
        req = _UrlRequest(
            f"{_TCE_BASE_URL}/{h}",
            headers={"User-Agent": _USER_AGENT},
        )
        try:
            with urlopen(req, timeout=_TIMEOUT_SECS) as r:
                if r.status != 200:
                    _log.warning("TCE-PB %s retornou %s", h[:8], r.status)
                    return None
                return r.read()
        except Exception:
            _log.exception("falha ao baixar PDF TCE-PB %s", h[:8])
            return None

    data = await asyncio.to_thread(_fetch_sync)
    if data is None or len(data) < 1000:
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".pdf.tmp")
        tmp.write_bytes(data)
        tmp.replace(path)
        return path
    except Exception:
        _log.exception("falha ao gravar cache PDF TCE-PB %s", h[:8])
        return None


@router.get("/api/tce-pb/decisao/{h}.pdf")
async def decisao_pdf(
    request: Request,
    h: str,
    download: int = Query(0, ge=0, le=1),
):
    """Serve o PDF da decisao via proxy.

    GET /api/tce-pb/decisao/<hash>.pdf         -> inline (iframe-friendly)
    GET /api/tce-pb/decisao/<hash>.pdf?download=1 -> attachment
    """
    if not _HASH_RE.fullmatch(h):
        raise HTTPException(status_code=400, detail="hash invalido")

    if not _hash_whitelisted(h):
        raise HTTPException(status_code=404, detail="decisao nao encontrada")

    path = await _fetch_and_cache(h)
    if path is None:
        raise HTTPException(status_code=502, detail="upstream TCE-PB indisponivel")

    disp = "attachment" if download else "inline"
    filename = f"tce-pb-{h}.pdf"
    headers = {
        "Content-Disposition": f'{disp}; filename="{filename}"',
        # Hash imutavel -> cacheavel por 30 dias.
        "Cache-Control": "public, max-age=2592000, immutable",
        "X-Content-Type-Options": "nosniff",
        # Permite embed na nossa propria origem.
        "X-Frame-Options": "SAMEORIGIN",
    }
    return FileResponse(
        path=str(path),
        media_type="application/pdf",
        headers=headers,
    )
