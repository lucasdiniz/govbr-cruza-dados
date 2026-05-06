"""Service layer para /contato — validação, persistência, envio via Resend.

Usado pelo router em web/routes/contato.py. Mantém a lógica desacoplada
do FastAPI pra facilitar teste e troca de provider de email.

Provider: Resend (https://resend.com). API key em RESEND_API_KEY (env).
Domínio remetente: noreply@transparenciapb.org (precisa ser verificado
no painel do Resend — criar account, adicionar domínio, configurar
DNS records SPF/DKIM, gerar API key, setar RESEND_API_KEY no .env da VM).
Sem RESEND_API_KEY a app salva as mensagens normalmente mas nao envia
emails — useful pra dev/staging.
"""
from __future__ import annotations

import html
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, TypedDict

import urllib.error
import urllib.request
import json as _json

from web import db


_log = logging.getLogger("transparencia.contato")

# ─── Configuração ──────────────────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_FROM = os.environ.get("RESEND_FROM", "noreply@transparenciapb.org")
CONTATO_DEST = os.environ.get("CONTATO_DEST", "contato@transparenciapb.org")
RESEND_API_URL = "https://api.resend.com/emails"

# ─── Validação ─────────────────────────────────────────────────────────
TITULO_MIN = 3
TITULO_MAX = 120
MENSAGEM_MIN = 20
MENSAGEM_MAX = 5000
NOME_MAX = 100
EMAIL_MAX = 254  # RFC 5321

# Regex pragmatica de email (RFC perfeita é insana). Cobre 99% dos casos.
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


class ContatoValidationError(ValueError):
    """Erro de validação de payload — message é amigavel pro user."""


class ValidatedPayload(TypedDict):
    nome: str
    email: str
    titulo: str
    mensagem: str
    honeypot_triggered: bool


def _strip_str(value: Any, max_len: int) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ContatoValidationError("Campo deve ser texto.")
    s = value.strip()
    if len(s) > max_len:
        raise ContatoValidationError(f"Campo excede limite de {max_len} caracteres.")
    return s


def _scrub_control_chars(value: str, allow_newlines: bool = False) -> str:
    """Remove control chars (\\r\\n\\t etc) que podem quebrar headers/JSON
    se passados pra API de email. Preserva newlines em mensagem (allow_newlines)."""
    if allow_newlines:
        # Permite \n. Normaliza \r\n -> \n. Strip outros controls.
        s = value.replace("\r\n", "\n").replace("\r", "\n")
        return "".join(c for c in s if c == "\n" or c == "\t" or ord(c) >= 32)
    return "".join(c for c in value if ord(c) >= 32)


def validate_payload(raw: Any) -> ValidatedPayload:
    """Valida payload JSON do POST /api/contato.

    Raises ContatoValidationError com mensagem PT-BR amigável.
    Retorna ValidatedPayload pronto pra persistência.
    """
    if not isinstance(raw, dict):
        raise ContatoValidationError("Formato de requisição inválido.")

    # Honeypot: campo "website" deve estar vazio. Se preenchido, sinalizamos
    # mas não rejeitamos — o caller decide o que fazer (responder sucesso
    # fake, sem enviar email).
    honeypot_value = raw.get("website", "")
    honeypot_triggered = bool(isinstance(honeypot_value, str) and honeypot_value.strip())

    nome = _scrub_control_chars(_strip_str(raw.get("nome", ""), NOME_MAX))
    email = _scrub_control_chars(_strip_str(raw.get("email", ""), EMAIL_MAX))
    titulo = _scrub_control_chars(_strip_str(raw.get("titulo", ""), TITULO_MAX))
    mensagem = _scrub_control_chars(
        _strip_str(raw.get("mensagem", ""), MENSAGEM_MAX),
        allow_newlines=True,
    )

    if not email:
        raise ContatoValidationError("Email é obrigatório.")
    if not _EMAIL_RE.match(email):
        raise ContatoValidationError("Email inválido.")
    if len(titulo) < TITULO_MIN:
        raise ContatoValidationError(f"Título deve ter pelo menos {TITULO_MIN} caracteres.")
    if len(mensagem) < MENSAGEM_MIN:
        raise ContatoValidationError(f"Mensagem deve ter pelo menos {MENSAGEM_MIN} caracteres.")

    return {
        "nome": nome,
        "email": email.lower(),
        "titulo": titulo,
        "mensagem": mensagem,
        "honeypot_triggered": honeypot_triggered,
    }


# ─── Throttling app-level ──────────────────────────────────────────────
# Defesa em profundidade contra abuse — independente do rate limit do
# nginx, protege contra burst que ultrapasse a quota gratuita do Resend
# (3000/mês). Limites combinados: max 5 mensagens não-honeypot por IP em
# 1 hora, ou 5 por email_remetente em 24h.

THROTTLE_PER_IP_HOUR = 5
THROTTLE_PER_EMAIL_DAY = 5


def is_throttled(ip: str | None, email: str) -> tuple[bool, str | None]:
    """Verifica se uma nova submissão deve ser bloqueada.

    Retorna (throttled, motivo). Throttled=True significa "rejeitar" — o
    caller responde sucesso fake (mesma resposta que honeypot, evita dar
    feedback util pro abuser).
    """
    sql = """
        SELECT
            COUNT(*) FILTER (
                WHERE ip_remetente IS NOT NULL
                  AND ip_remetente = %(ip)s::inet
                  AND criada_em > NOW() - INTERVAL '1 hour'
                  AND honeypot_triggered = FALSE
            ) AS by_ip,
            COUNT(*) FILTER (
                WHERE email_remetente = %(email)s
                  AND criada_em > NOW() - INTERVAL '24 hours'
                  AND honeypot_triggered = FALSE
            ) AS by_email
        FROM contato_messages
    """
    try:
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(sql, {"ip": ip, "email": email})
                row = cur.fetchone()
        if not row:
            return False, None
        by_ip = int(row[0] or 0)
        by_email = int(row[1] or 0)
        if ip and by_ip >= THROTTLE_PER_IP_HOUR:
            return True, f"ip:{by_ip}/h"
        if by_email >= THROTTLE_PER_EMAIL_DAY:
            return True, f"email:{by_email}/d"
        return False, None
    except Exception:
        # Se o check falhar (DB problema), permite passar — o save abaixo
        # provavelmente também falhará e o caller responde 500. Não
        # bloqueia silenciosamente em caso de erro do throttle check.
        _log.exception("Falha em is_throttled — permitindo submissão")
        return False, None


# ─── Persistência ──────────────────────────────────────────────────────

def save_contato_message(
    payload: ValidatedPayload,
    ip_remetente: str | None,
    user_agent: str | None,
) -> int:
    """Insere mensagem em contato_messages. Retorna ID."""
    sql = """
        INSERT INTO contato_messages
            (ip_remetente, user_agent, email_remetente, nome_remetente,
             titulo, mensagem, honeypot_triggered)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    with db.get_conn() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    ip_remetente,
                    user_agent,
                    payload["email"],
                    payload["nome"] or None,
                    payload["titulo"],
                    payload["mensagem"],
                    payload["honeypot_triggered"],
                ),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0


def _mark_email_sent(message_id: int) -> None:
    try:
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE contato_messages SET email_enviado_em = NOW(), email_erro = NULL "
                    "WHERE id = %s",
                    (message_id,),
                )
    except Exception:
        _log.exception("[contato id=%s] falha ao marcar email_enviado_em", message_id)


def _mark_email_error(message_id: int, error: str) -> None:
    try:
        with db.get_conn() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE contato_messages SET email_erro = %s WHERE id = %s",
                    (error[:1000], message_id),
                )
    except Exception:
        _log.exception("[contato id=%s] falha ao marcar email_erro=%s", message_id, error[:200])


# ─── Envio via Resend ──────────────────────────────────────────────────

def _format_email_body(payload: ValidatedPayload, ip: str | None, message_id: int) -> tuple[str, str]:
    """Retorna (text, html)."""
    nome_label = payload["nome"] or "(sem nome)"
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    text = (
        f"Nova mensagem via /contato (id={message_id})\n"
        f"\n"
        f"De: {nome_label} <{payload['email']}>\n"
        f"IP: {ip or '?'}\n"
        f"Recebida em: {when}\n"
        f"\n"
        f"Título: {payload['titulo']}\n"
        f"\n"
        f"{payload['mensagem']}\n"
        f"\n"
        f"---\n"
        f"Para responder, use Reply diretamente — Reply-To está configurado pra {payload['email']}.\n"
    )
    h = html.escape
    html_body = (
        f"<div style=\"font-family: -apple-system, sans-serif; max-width: 600px;\">"
        f"<h2 style=\"color:#1a1a1a;\">Nova mensagem via /contato <small style=\"color:#666;font-weight:normal;\">(id={message_id})</small></h2>"
        f"<p><strong>De:</strong> {h(nome_label)} &lt;{h(payload['email'])}&gt;<br>"
        f"<strong>IP:</strong> {h(ip or '?')}<br>"
        f"<strong>Recebida em:</strong> {h(when)}</p>"
        f"<h3>Título</h3>"
        f"<p style=\"background:#f5f5f5;padding:12px;border-radius:6px;\">{h(payload['titulo'])}</p>"
        f"<h3>Mensagem</h3>"
        f"<p style=\"background:#f5f5f5;padding:12px;border-radius:6px;white-space:pre-wrap;\">{h(payload['mensagem'])}</p>"
        f"<hr><p style=\"color:#666;font-size:0.85em;\">Para responder, use Reply diretamente — Reply-To está configurado pra <code>{h(payload['email'])}</code>.</p>"
        f"</div>"
    )
    return text, html_body


def send_via_resend(message_id: int, payload: ValidatedPayload, ip: str | None) -> None:
    """Envia o email via Resend API. Atualiza contato_messages com status.

    Não levanta exceção — falhas são logadas e persistidas em email_erro.
    """
    if not RESEND_API_KEY:
        msg = "RESEND_API_KEY não configurada"
        _log.error("[contato id=%s] %s", message_id, msg)
        _mark_email_error(message_id, msg)
        return

    text, html_body = _format_email_body(payload, ip, message_id)

    body = {
        "from": RESEND_FROM,
        "to": [CONTATO_DEST],
        "reply_to": payload["email"],
        "subject": f"[Contato] {payload['titulo']}",
        "html": html_body,
        "text": text,
    }
    data = _json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        RESEND_API_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "transparenciapb/contato",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            response_body = resp.read().decode("utf-8", errors="replace")
            if 200 <= status < 300:
                _log.info("[contato id=%s] email enviado via Resend (HTTP %s)", message_id, status)
                _mark_email_sent(message_id)
                return
            _log.error("[contato id=%s] Resend HTTP %s: %s", message_id, status, response_body[:500])
            _mark_email_error(message_id, f"HTTP {status}: {response_body[:500]}")
    except urllib.error.HTTPError as e:
        body_resp = e.read().decode("utf-8", errors="replace") if e.fp else ""
        _log.error("[contato id=%s] Resend HTTPError %s: %s", message_id, e.code, body_resp[:500])
        _mark_email_error(message_id, f"HTTP {e.code}: {body_resp[:500]}")
    except urllib.error.URLError as e:
        _log.error("[contato id=%s] Resend URLError: %s", message_id, e)
        _mark_email_error(message_id, f"URLError: {e}")
    except Exception as exc:
        _log.exception("[contato id=%s] Falha inesperada no Resend", message_id)
        _mark_email_error(message_id, f"Unexpected: {exc}")
