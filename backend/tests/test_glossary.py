"""Testes do glossário do assistente (tradução de jargão técnico).

Garante que a resposta entregue ao usuário final não vaze códigos internos de
permissão/papel nem segmentos de rota dinâmicos (``[id]``).
"""

from __future__ import annotations

from app.services import glossary


def test_translate_known_permission():
    assert glossary.translate_term("NIT_DOCUMENT_UPLOAD") == "Enviar documentos"
    assert glossary.translate_term("NIT_DOCUMENT_VIEW") == (
        "Visualizar/baixar documentos autorizados"
    )


def test_translate_known_role():
    # Papéis em ROLES usam o nome legível definido em constants.py.
    assert glossary.translate_term("NIT_TT_OPERATOR") == (
        "NIT - Transferência de Tecnologia"
    )
    assert glossary.translate_term("SUPER_ADMIN") == "Super Administrador"


def test_translate_unknown_code_is_preserved():
    assert glossary.translate_term("ALGUMA_COISA_DESCONHECIDA") == (
        "ALGUMA_COISA_DESCONHECIDA"
    )


def test_humanize_routes_drops_dynamic_segments():
    text = "Acesse /nit/comunicacoes/[id] e envie o arquivo."
    assert glossary.humanize_routes(text) == (
        "Acesse /nit/comunicacoes e envie o arquivo."
    )


def test_humanize_replaces_permission_and_role_codes():
    text = (
        "Quem pode enviar: papéis com NIT_DOCUMENT_UPLOAD "
        "(SUPER_ADMIN, NIT_TT_OPERATOR)."
    )
    result = glossary.humanize(text)
    assert "NIT_DOCUMENT_UPLOAD" not in result
    assert "Enviar documentos" in result
    assert "NIT_TT_OPERATOR" not in result


def test_humanize_normalizes_multiple_terms():
    text = "Vá em /nit/documentos; requer NIT_DOCUMENT_VIEW."
    result = glossary.humanize(text)
    assert "[id]" not in result
    assert "NIT_DOCUMENT_VIEW" not in result
