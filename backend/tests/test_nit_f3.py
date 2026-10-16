"""F3 — technology transfer, negotiations and contracts tests.

Covers the F3 gate: negotiation isolation, contract-document access, parties and
assets integrity, monetary (Decimal) calculations, deadline alerts, pipeline
transitions and administrative permissions.
"""

from __future__ import annotations

from decimal import Decimal

from tests.conftest import assign_role, auth_header, login, make_tenant, make_user

TT = "/api/nit/tt"
CONTRACTS = "/api/nit/contracts"


def _nit_tenant(db):
    from app.seed_nit import seed_tenant_workflow

    tenant = make_tenant(db, name="ICT F3", module_codes=["NIT"])
    seed_tenant_workflow(db, tenant.id)
    db.commit()
    return tenant


def _user(db, tenant_id, role_code, email):
    user = make_user(db, email=email, tenant_id=tenant_id)
    assign_role(db, user.id, role_code)
    return user


def _headers(client, db, tenant_id, role="NIT_MANAGER", email="tt@f3.br"):
    _user(db, tenant_id, role, email)
    return auth_header(login(client, email)["access_token"])


def _make_offer(client, headers, status="PUBLISHED"):
    created = client.post(
        TT + "/offers",
        json={"title": "Sensor óptico", "public_summary": "Tecnologia de sensoriamento"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    offer = created.json()
    if status == "PUBLISHED":
        upd = client.patch(
            f"{TT}/offers/{offer['id']}", json={"status": "PUBLISHED"}, headers=headers
        )
        assert upd.status_code == 200, upd.text
        offer = upd.json()
    return offer


# --- Catalog and interests ---------------------------------------------------
def test_catalog_only_shows_published(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id)
    _make_offer(client, headers, status="DRAFT")
    _make_offer(client, headers, status="PUBLISHED")

    catalog = client.get(f"{TT}/catalog", headers=headers).json()
    assert catalog["total"] == 1
    # All offers (management view) shows both.
    all_offers = client.get(f"{TT}/offers", headers=headers).json()
    assert all_offers["total"] == 2


def test_interest_only_for_published_offer(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id)
    draft = _make_offer(client, headers, status="DRAFT")

    resp = client.post(
        f"{TT}/offers/{draft['id']}/interests",
        json={"organization_name": "Empresa X"},
        headers=headers,
    )
    assert resp.status_code == 409

    published = _make_offer(client, headers, status="PUBLISHED")
    ok = client.post(
        f"{TT}/offers/{published['id']}/interests",
        json={"organization_name": "Empresa Y", "contact_email": "y@emp.br"},
        headers=headers,
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["status"] == "NEW"


def test_tt_isolation_across_tenants(db, client, seeded_full):
    ta = _nit_tenant(db)
    tb = _nit_tenant(db)
    ha = _headers(client, db, ta.id, email="a@f3.br")
    hb = _headers(client, db, tb.id, email="b@f3.br")

    offer = _make_offer(client, ha)
    assert client.get(f"{TT}/offers", headers=hb).json()["total"] == 0
    assert client.get(f"{TT}/offers/{offer['id']}", headers=hb).status_code == 403


# --- Negotiation pipeline ----------------------------------------------------
def _setup_negotiation(client, headers):
    offer = _make_offer(client, headers)
    interest = client.post(
        f"{TT}/offers/{offer['id']}/interests",
        json={"organization_name": "Empresa Z"},
        headers=headers,
    ).json()
    neg = client.post(
        f"{TT}/negotiations",
        json={"interest_id": interest["id"]},
        headers=headers,
    )
    assert neg.status_code == 201, neg.text
    return offer, interest, neg.json()


def test_pipeline_valid_and_invalid_transitions(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id)
    offer, interest, neg = _setup_negotiation(client, headers)
    assert neg["stage"] == "NEW"

    # NEW -> FIRST_CONTACT is not a declared edge (must go through QUALIFICATION).
    invalid = client.post(
        f"{TT}/negotiations/{neg['id']}/advance",
        json={"to_stage": "FIRST_CONTACT"},
        headers=headers,
    )
    assert invalid.status_code == 422

    ok = client.post(
        f"{TT}/negotiations/{neg['id']}/advance",
        json={"to_stage": "QUALIFICATION", "expected_version": 0},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["stage"] == "QUALIFICATION"
    assert len(ok.json()["history"]) == 2  # creation + advance


def test_pipeline_does_not_change_contract_status(db, client, seeded_full):
    """Advancing a negotiation to CONTRACTING never touches a contract's status."""
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id)
    offer, interest, neg = _setup_negotiation(client, headers)

    contract = client.post(
        CONTRACTS, json={"title": "Contrato inicial"}, headers=headers
    ).json()
    assert contract["status"] == "DRAFT"

    for stage in ["QUALIFICATION", "FIRST_CONTACT", "TECHNICAL_DISCUSSION", "NEGOTIATION", "APPROVAL", "CONTRACTING"]:
        r = client.post(
            f"{TT}/negotiations/{neg['id']}/advance",
            json={"to_stage": stage},
            headers=headers,
        )
        assert r.status_code == 200, f"{stage}: {r.text}"

    # The contract remained DRAFT — the pipeline never changes legal status.
    after = client.get(f"{CONTRACTS}/{contract['id']}", headers=headers).json()
    assert after["status"] == "DRAFT"


def test_negotiation_isolation(db, client, seeded_full):
    ta = _nit_tenant(db)
    tb = _nit_tenant(db)
    ha = _headers(client, db, ta.id, email="na@f3.br")
    hb = _headers(client, db, tb.id, email="nb@f3.br")
    _off, _int, neg = _setup_negotiation(client, ha)

    assert client.get(f"{TT}/negotiations/{neg['id']}", headers=hb).status_code == 403


# --- Contracts, parties, obligations and royalties ---------------------------
def test_contract_parties_and_isolation(db, client, seeded_full):
    ta = _nit_tenant(db)
    tb = _nit_tenant(db)
    ha = _headers(client, db, ta.id, email="ca@f3.br")
    hb = _headers(client, db, tb.id, email="cb@f3.br")

    contract = client.post(
        CONTRACTS,
        json={
            "title": "Licenciamento",
            "parties": [
                {"role": "LICENSOR", "name": "ICT A"},
                {"role": "LICENSEE", "name": "Empresa Y"},
            ],
        },
        headers=ha,
    )
    assert contract.status_code == 201, contract.text
    body = contract.json()
    assert body["code"].startswith("CT-")
    assert len(body["parties"]) == 2

    # The other tenant cannot read it.
    assert client.get(f"{CONTRACTS}/{body['id']}", headers=hb).status_code == 403
    assert client.get(CONTRACTS, headers=hb).json()["total"] == 0


def test_royalty_decimal_math_and_summary(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id)
    contract = client.post(
        CONTRACTS,
        json={"title": "Contrato royalties", "registered_amount": "10000.50"},
        headers=headers,
    ).json()
    assert Decimal(contract["registered_amount"]) == Decimal("10000.50")

    client.post(
        f"{CONTRACTS}/{contract['id']}/royalties",
        json={
            "period": "2026-01",
            "expected_amount": "1000.10",
            "registered_amount": "1000.10",
            "received_amount": "1000.10",
        },
        headers=headers,
    )
    client.post(
        f"{CONTRACTS}/{contract['id']}/royalties",
        json={
            "period": "2026-02",
            "expected_amount": "2000.20",
            "registered_amount": "2000.20",
            "received_amount": "500.05",
        },
        headers=headers,
    )

    summary = client.get(
        f"{CONTRACTS}/{contract['id']}/royalties/summary", headers=headers
    ).json()
    assert Decimal(summary["total_registered"]) == Decimal("3000.30")
    assert Decimal(summary["total_received"]) == Decimal("1500.15")
    # pending = registered - received, exact (no floating point drift).
    assert Decimal(summary["pending"]) == Decimal("1500.15")
    assert summary["entries"] == 2


def test_obligation_alerts_only_real_due_dates(db, client, seeded_full):
    from datetime import date, timedelta

    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id)
    contract = client.post(
        CONTRACTS, json={"title": "Contrato com obrigações"}, headers=headers
    ).json()

    soon = (date.today() + timedelta(days=10)).isoformat()
    later = (date.today() + timedelta(days=300)).isoformat()
    client.post(
        f"{CONTRACTS}/{contract['id']}/obligations",
        json={"kind": "REPORT", "description": "Relatório trimestral", "due_date": soon},
        headers=headers,
    )
    client.post(
        f"{CONTRACTS}/{contract['id']}/obligations",
        json={"kind": "PAYMENT", "description": "Pagamento anual", "due_date": later},
        headers=headers,
    )
    # An obligation with no due date never appears in alerts.
    client.post(
        f"{CONTRACTS}/{contract['id']}/obligations",
        json={"kind": "OTHER", "description": "Sem prazo"},
        headers=headers,
    )

    alerts = client.get(f"{CONTRACTS}/obligations/alerts?days=60", headers=headers).json()
    assert len(alerts) == 1
    assert alerts[0]["severity"] in ("critical", "warning")


def test_obligation_status_update(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id)
    contract = client.post(CONTRACTS, json={"title": "C"}, headers=headers).json()
    ob = client.post(
        f"{CONTRACTS}/{contract['id']}/obligations",
        json={"kind": "DELIVERY", "description": "Entrega de protótipo"},
        headers=headers,
    ).json()
    assert ob["status"] == "PENDING"

    upd = client.patch(
        f"{CONTRACTS}/obligations/{ob['id']}",
        json={"status": "DONE"},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "DONE"


def test_tt_requires_permission(db, client, seeded_full):
    tenant = _nit_tenant(db)
    _user(db, tenant.id, "NIT_RESEARCHER", "rr@f3.br")
    headers = auth_header(login(client, "rr@f3.br")["access_token"])
    # A researcher lacks NIT_OFFER_VIEW.
    assert client.get(f"{TT}/offers", headers=headers).status_code == 403
    assert client.get(CONTRACTS, headers=headers).status_code == 403


