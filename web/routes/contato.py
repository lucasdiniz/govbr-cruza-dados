"""Router /contato e /api/contato."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from web import contato as contato_svc

_log = logging.getLogger("transparencia.contato.routes")


def _client_ip(request: Request) -> str | None:
    """Extrai IP do remetente.

    Em prod com nginx, X-Real-IP é setado direto pelo nginx
    (proxy_set_header X-Real-IP $remote_addr) — confiável.
    X-Forwarded-For é appended pelo nginx mas pode conter valores spoofed
    do cliente — não confiamos.

    Valida que o resultado é um IP RFC válido (psycopg2 INET coluna
    rejeita strings malformadas; sem isso, falha com 500).
    """
    raw = request.headers.get("x-real-ip", "").strip()
    if not raw and request.client:
        raw = request.client.host or ""
    if not raw:
        return None
    try:
        import ipaddress
        ipaddress.ip_address(raw)
        return raw
    except (ValueError, TypeError):
        return None


def build_router(templates: Jinja2Templates) -> APIRouter:
    """Recebe templates do main.py pra renderizar /contato."""
    router = APIRouter()

    @router.get("/contato", response_class=HTMLResponse)
    async def contato_page(request: Request):
        return templates.TemplateResponse(request, "contato.html", {})

    @router.post("/api/contato")
    async def post_contato(request: Request, background: BackgroundTasks):
        try:
            payload_raw: Any = await request.json()
        except Exception:
            return JSONResponse({"ok": False, "error": "JSON inválido"}, status_code=400)

        try:
            payload = contato_svc.validate_payload(payload_raw)
        except contato_svc.ContatoValidationError as e:
            return JSONResponse({"ok": False, "error": str(e)}, status_code=422)

        ip = _client_ip(request)
        ua = request.headers.get("user-agent", "")[:500] or None

        # Throttle app-level (defesa em profundidade ao rate limit nginx).
        # Quando throttled, salva com honeypot_triggered=True (audit) e
        # responde sucesso fake — não revela ao abuser que foi bloqueado.
        throttled, reason = contato_svc.is_throttled(ip=ip, email=payload["email"])
        if throttled:
            _log.warning("Contato throttled (ip=%s email=%s reason=%s)", ip, payload["email"], reason)
            try:
                contato_svc.save_contato_message(
                    payload={**payload, "honeypot_triggered": True},
                    ip_remetente=ip,
                    user_agent=ua,
                )
            except Exception:
                _log.exception("Falha ao salvar mensagem throttled")
            return JSONResponse({"ok": True})

        try:
            message_id = contato_svc.save_contato_message(
                payload=payload, ip_remetente=ip, user_agent=ua
            )
        except Exception as exc:
            _log.exception("Falha ao salvar contato_messages: %s", exc)
            return JSONResponse(
                {"ok": False, "error": "Erro interno ao salvar mensagem. Tente mais tarde."},
                status_code=500,
            )

        # Honeypot triggered: salva (audit) mas responde sucesso fake e NÃO envia.
        if payload["honeypot_triggered"]:
            _log.info("Honeypot triggered (id=%s) — fake-success", message_id)
            return JSONResponse({"ok": True})

        # Envio em background pra nao bloquear a resposta.
        background.add_task(
            contato_svc.send_via_resend,
            message_id=message_id,
            payload=payload,
            ip=ip,
        )
        return JSONResponse({"ok": True})

    return router
