"""Redaction de PII em texto livre antes de cachear pra paginas indexaveis.

Usado pra `objeto_licitacao`, `historico` de empenho, e qualquer outro
campo TEXT que pode ter sido digitado por servidor com CPF/RG/email/telefone
embedded (ex: "Pagamento a Joao Silva CPF 123.456.789-01" ou "Contratacao
de servico para paciente Maria CNH 12345678").

Conservador deliberadamente: false-positives sao OK (perdemos um pouco de
texto legitimo); false-negatives expoem PII indexada. Por isso o regex
de CPF eh agressivo (qualquer 11 digitos consecutivos).

Aplicado no warm/compute ANTES de salvar na cache. Cache fica limpo.
P1 GPT 5.5 review PR #108.
"""
from __future__ import annotations

import re

# CPF: 11 digitos com ou sem mascara. Casa "123.456.789-01", "12345678901",
# "***.456.789-**". Captura tambem "CPF: 123.456.789-01" e similares.
# Inclui sequencias de 11 digitos puros (mesmo sem rotulo) — agressivo.
_CPF_RE = re.compile(
    r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"
    r"|"
    r"\*{3}\.?\d{3}\.?\d{3}-?\*{2}",
)

# RG (varia muito por estado, mas formato comum: 7-10 digitos +/- DV).
# Pegamos "RG: <numeros>" ou "RG <numeros>".
_RG_RE = re.compile(r"\bRG\s*:?\s*[\d.\-X]{7,12}\b", re.IGNORECASE)

# Email
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Telefone brasileiro: (83) 9 9999-9999, (83)99999-9999, 83 99999 9999, etc.
# Pega 10-11 digitos com separadores opcionais (parenteses, espaco, hifen).
_PHONE_RE = re.compile(
    r"\(?\d{2}\)?\s*9?\s*\d{4}[-\s]?\d{4}\b"
    r"|"
    r"\b\d{2}\s*9?\d{4}[-\s]?\d{4}\b",
)


def scrub_pii(text: str | None) -> str | None:
    """Substitui CPF/RG/email/telefone embedded em texto livre por placeholders.

    Returns None se input eh None. String vazia se input eh vazia.

    >>> scrub_pii("Pagamento a Maria CPF 123.456.789-01")
    'Pagamento a Maria [CPF removido]'
    >>> scrub_pii("Contato joao@exemplo.com tel (83) 99999-9999")
    'Contato [email removido] tel [telefone removido]'
    >>> scrub_pii("RG: 1234567-X documento de identidade")
    '[RG removido] documento de identidade'
    >>> scrub_pii(None)
    >>> scrub_pii("")
    ''
    """
    if text is None:
        return None
    if not text:
        return text
    s = str(text)
    s = _CPF_RE.sub("[CPF removido]", s)
    s = _RG_RE.sub("[RG removido]", s)
    s = _EMAIL_RE.sub("[email removido]", s)
    s = _PHONE_RE.sub("[telefone removido]", s)
    return s


def scrub_pii_dict(d: dict, keys: list[str]) -> dict:
    """Aplica scrub_pii nas chaves especificadas do dict (in-place + return).

    Caller passa explicitamente as chaves de texto livre — evita scrub
    overzealous em campos estruturados que coincidentemente tem digitos.
    """
    if not d:
        return d
    for k in keys:
        if k in d and d[k]:
            d[k] = scrub_pii(d[k])
    return d
