"""Tests for the AI analysis endpoints (DeepSeek integration).

The DeepSeek client itself is not called over the network here: we assert the
status endpoint, the explicit 503 degradation when no API key is configured,
and — by monkeypatching the deepseek service — the full report assembly.
"""

from __future__ import annotations

import json

from app.models import Marca
from app.services import deepseek
from tests.conftest import assign_role, auth_header, login, make_tenant, make_user


def _token(client, db, seeded, *, email: str, tenant_id):
    user = make_user(db, email=email, tenant_id=tenant_id)
    assign_role(db, user.id, "SUPER_ADMIN")
    return auth_header(login(client, email)["access_token"])


def test_analysis_status_reports_configuration(client, db, seeded):
    tenant = make_tenant(db, name="AI Status", module_codes=["ADMIN", "MARCAS"])
    headers = _token(client, db, seeded, email="ai@example.com", tenant_id=tenant.id)

    resp = client.get("/api/analises/status", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "configured" in body
    assert "model" in body


def test_analysis_returns_503_when_not_configured(client, db, seeded, monkeypatch):
    monkeypatch.setattr(deepseek, "is_configured", lambda: False)
    tenant = make_tenant(db, name="AI Off", module_codes=["ADMIN", "MARCAS"])
    headers = _token(client, db, seeded, email="off@example.com", tenant_id=tenant.id)

    resp = client.post(
        "/api/analises",
        headers=headers,
        json={"brand_name": "ZZZTESTE", "nice_classes": ["35"]},
    )
    assert resp.status_code == 503


def test_analysis_report_includes_patents(client, db, seeded, monkeypatch):
    """Regression: patents are retrieved without crashing (title lives on
    ``patentes_conteudo``, not on the bibliographic ``patente`` row).

    Before the fix, ``_retrieve_patentes`` read ``Patente.titulo`` (no such
    attribute) -> AttributeError -> HTTP 500 whenever ``include_patentes`` was
    on, which the browser surfaced as "Failed to fetch".
    """
    from app.models import Patente, PatenteConteudo, PatenteDepositante

    tenant = make_tenant(db, name="AI Pat", module_codes=["ADMIN", "MARCAS"])
    headers = _token(client, db, seeded, email="pat@example.com", tenant_id=tenant.id)

    db.add(Patente(codigo_interno="pat-1", numero_inpi="BR1234567"))
    db.add(
        PatenteConteudo(
            codigo_interno="pat-1",
            numero_inpi="BR1234567",
            titulo="DISPOSITIVO ZETALAB DE TESTE",
            resumo="Dispositivo para laboratorio Zeta.",
        )
    )
    db.add(
        PatenteDepositante(
            codigo_interno="pat-1",
            numero_inpi="BR1234567",
            ordem="1",
            depositante="Zeta Pesquisas Ltda",
        )
    )
    db.commit()

    monkeypatch.setattr(deepseek, "is_configured", lambda: True)
    monkeypatch.setattr(
        deepseek,
        "chat",
        lambda *a, **k: deepseek.DeepSeekResult(
            content=json.dumps(
                {
                    "overall_risk": "baixo",
                    "score": 10,
                    "summary": "Sem conflitos relevantes.",
                    "conflicts": [],
                    "recommendations": [],
                }
            ),
            model="deepseek-chat",
        ),
    )

    resp = client.post(
        "/api/analises",
        headers=headers,
        json={
            "brand_name": "Zetalab",
            "nice_classes": [],
            "options": {"include_patentes": True, "strict_nice": False},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["related_patents"]) >= 1
    patents = {p["titulo"]: p for p in body["related_patents"]}
    entry = patents["DISPOSITIVO ZETALAB DE TESTE"]
    assert entry["numero_inpi"] == "BR1234567"
    assert entry["depositante"] == "Zeta Pesquisas Ltda"


def test_analysis_report_with_stubbed_model(client, db, seeded, monkeypatch):
    tenant = make_tenant(db, name="AI On", module_codes=["ADMIN", "MARCAS"])
    headers = _token(client, db, seeded, email="on@example.com", tenant_id=tenant.id)

    # Seed a marca that shares a token with the requested brand.
    db.add(
        Marca(
            codigo_interno="ai-1",
            numero_inpi="999999999",
            elemento_nominativo="Zeta Labs",
            codigo_situacao="IPAS023",
            descricao_situacao="Registro de marca em vigor",
        )
    )
    db.commit()

    fake = {
        "overall_risk": "alto",
        "score": 68,
        "summary": "Conflito relevante encontrado.",
        "conflicts": [
            {
                "title": "Zeta Labs",
                "score": 70,
                "level": "alto",
                "description": "Nome semelhante na mesma classe.",
                "fonte": "INPI",
            }
        ],
        "recommendations": ["Avaliar variação nominal.", "Considerar oposição."],
    }

    monkeypatch.setattr(deepseek, "is_configured", lambda: True)
    monkeypatch.setattr(
        deepseek,
        "chat",
        lambda *a, **k: deepseek.DeepSeekResult(
            content=json.dumps(fake), model="deepseek-chat"
        ),
    )

    resp = client.post(
        "/api/analises",
        headers=headers,
        json={
            "brand_name": "Zeta Labs",
            "nice_classes": ["35"],
            "holder": "Zeta Ltda",
            "options": {"include_patentes": False, "strict_nice": False},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["overall_risk"] == "alto"
    assert body["score"] == 68
    assert body["ai_available"] is True
    assert len(body["similar_brands"]) >= 1
    assert body["recommendations"]
