"""Testes do assistente (chat) sobre a documentação do sistema.

O cliente DeepSeek não é chamado pela rede: usamos ``monkeypatch`` para forçar o
modo não configurado e para injetar uma resposta simulada do modelo.
"""

from __future__ import annotations

from app.services import deepseek
from tests.conftest import assign_role, auth_header, login, make_tenant, make_user


def _token(client, db, *, email: str, tenant_id):
    user = make_user(db, email=email, tenant_id=tenant_id)
    assign_role(db, user.id, "SUPER_ADMIN")
    return auth_header(login(client, email)["access_token"])


def _tenant(db, name: str):
    return make_tenant(db, name=name, module_codes=["ADMIN", "MARCAS"])


def test_chat_status_reports_base_and_configuration(client, db, seeded):
    tenant = _tenant(db, "Chat Status")
    headers = _token(client, db, email="chatstatus@example.com", tenant_id=tenant.id)

    resp = client.get("/api/chat/status", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "configured" in body
    assert body["documents"] >= 10
    assert body["sections"] >= 40
    assert "model" in body


def test_chat_requires_authentication(client, seeded):
    resp = client.post("/api/chat", json={"message": "onde vejo meus clientes?"})
    assert resp.status_code == 401


def test_chat_degrades_without_ai_key(client, db, seeded, monkeypatch):
    monkeypatch.setattr(deepseek, "is_configured", lambda: False)
    tenant = _tenant(db, "Chat Sem IA")
    headers = _token(client, db, email="chatnoai@example.com", tenant_id=tenant.id)

    resp = client.post(
        "/api/chat",
        headers=headers,
        json={"message": "onde vejo meus clientes?"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ai_available"] is False
    # Mesmo sem IA, devolve trechos de documentação recuperados.
    assert "/clientes" in body["answer"]
    assert body["sources"]


def test_chat_degradation_hides_technical_jargon(client, db, seeded, monkeypatch):
    """Sem IA, a resposta não deve vazar jargão de desenvolvedor."""
    monkeypatch.setattr(deepseek, "is_configured", lambda: False)
    tenant = _tenant(db, "Chat Jargao")
    headers = _token(client, db, email="chatsemjargao@example.com", tenant_id=tenant.id)

    resp = client.post(
        "/api/chat",
        headers=headers,
        json={"message": "como insiro documentos do NIT?"},
    )
    assert resp.status_code == 200, resp.text
    answer = resp.json()["answer"]
    # Não deve expor a variável de ambiente nem códigos internos.
    assert "DEEPSEEK_API_KEY" not in answer
    assert "NIT_DOCUMENT_UPLOAD" not in answer
    assert "NIT_DOCUMENT_VIEW" not in answer
    # Não deve expor segmentos dinâmicos de rota.
    assert "[id]" not in answer


def test_chat_answers_with_stubbed_model(client, db, seeded, monkeypatch):
    monkeypatch.setattr(deepseek, "is_configured", lambda: True)
    monkeypatch.setattr(
        deepseek,
        "chat",
        lambda messages, **kwargs: deepseek.DeepSeekResult(
            content="Vá em CRM / Clientes → Clientes e empresas (/clientes).",
            model="deepseek-stub",
        ),
    )
    tenant = _tenant(db, "Chat Com IA")
    headers = _token(client, db, email="chatyesai@example.com", tenant_id=tenant.id)

    resp = client.post(
        "/api/chat",
        headers=headers,
        json={
            "message": "onde vejo meus clientes?",
            "history": [
                {"role": "user", "content": "oi"},
                {"role": "assistant", "content": "olá!"},
            ],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ai_available"] is True
    assert "/clientes" in body["answer"]
    assert body["model"] == "deepseek-stub"
