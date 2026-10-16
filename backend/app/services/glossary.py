"""Glossário do assistente — traduz jargão técnico para linguagem do usuário.

O assistente deve falar como um manual do usuário final, não como a documentação
técnica. Este módulo converte termos internos (códigos de permissão, códigos de
papel, segmentos de rota dinâmicos) para rótulos legíveis em português, de modo
que a resposta seja útil a qualquer pessoa — mesmo sem conhecer o código.

Exemplos:

* ``NIT_DOCUMENT_UPLOAD`` → *"Enviar documentos"*
* ``NIT_TT_OPERATOR`` → *"NIT - Transferência de Tecnologia"*
* ``/nit/comunicacoes/[id]`` → *"/nit/comunicacoes"* (a parte ``[id]`` some)

A tradução é um **reforço**: mesmo que a IA eventualmente escape algum código, o
texto final é normalizado antes de sair do servidor. Sem dependências externas.
"""

from __future__ import annotations

import re

from app import constants


def _permission_map() -> dict[str, str]:
    """Código de permissão → descrição legível (ex.: ``Enviar documentos``)."""
    return {code: desc for _module, code, desc in constants.PERMISSIONS}


def _role_map() -> dict[str, str]:
    """Código de papel → nome legível (ex.: ``NIT - Transferência de Tecnologia``)."""
    return {role["code"]: role["name"] for role in constants.ROLES}


_PERMISSION_MAP = _permission_map()
_ROLE_MAP = _role_map()

# Rótulos alternativos para códigos que não estão em ROLES mas aparecem na
# documentação (papéis mestres / legados). Mantidos explícitos de propósito.
_EXTRA_ROLE_LABELS: dict[str, str] = {
    "MASTER_ADMIN": "Administrador Master",
    "SUPER_ADMIN": "Super Administrador",
    "TENANT_ADMIN": "Administrador do Tenant",
}

# Códigos técnicos no formato CONSTANT_CASE (ex.: ``NIT_DOCUMENT_VIEW``).
_CONSTANT_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")

# Segmentos de rota dinâmicos: ``[id]``, ``[slug]`` → escondidos do usuário.
_DYNAMIC_SEGMENT_RE = re.compile(r"/\[[^\]]+\]")

# Rótulos que não agregam para o usuário final e podem ser removidos.
_TECHNICAL_LABELS = (
    "`POST /api", "`GET /api", "`PUT /api", "`PATCH /api", "`DELETE /api",
)


def translate_term(code: str) -> str:
    """Traduz um único código técnico para rótulo legível (ou devolve o original)."""
    if code in _PERMISSION_MAP:
        return _PERMISSION_MAP[code]
    if code in _ROLE_MAP:
        return _ROLE_MAP[code]
    if code in _EXTRA_ROLE_LABELS:
        return _EXTRA_ROLE_LABELS[code]
    return code


def humanize_routes(text: str) -> str:
    """Remove segmentos dinâmicos de rotas (``/x/[id]`` → ``/x``)."""
    return _DYNAMIC_SEGMENT_RE.sub("", text)


def humanize(text: str) -> str:
    """Converte jargão técnico em linguagem de usuário.

    Aplica (nesta ordem):

    1. remove segmentos dinâmicos de rota (``[id]``);
    2. substitui códigos de permissão/papel conhecidos pelo rótulo legível.

    Códigos desconhecidos são preservados para não mascarar informação.
    """
    if not text:
        return text
    text = humanize_routes(text)

    def _repl(match: re.Match[str]) -> str:
        code = match.group(0)
        label = translate_term(code)
        return label if label != code else code

    return _CONSTANT_RE.sub(_repl, text)


__all__ = ["humanize", "humanize_routes", "translate_term"]
