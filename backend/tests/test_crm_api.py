"""API tests for the commercial CRM endpoints (``/api/crm``).

Covers, against the real FastAPI app + database:

* permission guards and tenant isolation (list / get / update / delete /
  conversion must never leak across tenants);
* the opportunity funnel lifecycle and its business rules (WON needs a
  customer, LOST needs a reason, illegal transitions are rejected);
* the proposal lifecycle including ``sent_at`` / ``replied_at`` / ``decision_at``
  side effects;
* conversion of a won lead into a client without duplicating the customer;
* the commercial dashboard aggregates and ``/api/dashboard/business``.
"""

from __future__ import annotations

from tests.conftest import assign_role, auth_header, login, make_tenant, make_user


def _admin_token(client, db, *, email: str, tenant_id):
    user = make_user(db, email=email, tenant_id=tenant_id)
    assign_role(db, user.id, "SUPER_ADMIN")
    return auth_header(login(client, email)["access_token"])


def _tenant(db, name: str):
    return make_tenant(db, name=name, module_codes=["ADMIN", "CLIENTES"])


def _new_opportunity(client, headers, **overrides) -> dict:
    payload = {"title": "Registro de marca para rede de franquias"}
    payload.update(overrides)
    resp = client.post("/api/crm/opportunities", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _new_proposal(client, headers, **overrides) -> dict:
    payload = {"title": "Proposta de registro de marca"}
    payload.update(overrides)
    resp = client.post("/api/crm/proposals", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- Permissions & isolation -------------------------------------------------
def test_crm_requires_permission(client, db, seeded):
    tenant = _tenant(db, "CRM NoPerm")
    make_user(db, email="noperm-crm@example.com", tenant_id=tenant.id)
    token = auth_header(login(client, "noperm-crm@example.com")["access_token"])

    assert client.get("/api/crm/opportunities", headers=token).status_code == 403
    assert client.get("/api/crm/proposals", headers=token).status_code == 403
    assert client.get("/api/crm/dashboard", headers=token).status_code == 403
    assert client.get("/api/dashboard/business", headers=token).status_code == 403


def test_opportunity_isolation_between_tenants(client, db, seeded):
    tenant_a = _tenant(db, "CRM Iso A")
    tenant_b = _tenant(db, "CRM Iso B")
    headers_a = _admin_token(client, db, email="crm-a@example.com", tenant_id=tenant_a.id)
    headers_b = _admin_token(client, db, email="crm-b@example.com", tenant_id=tenant_b.id)

    created = _new_opportunity(client, headers_a, title="Só do tenant A")
    opp_id = created["id"]

    # Listing is scoped.
    listed_b = client.get("/api/crm/opportunities", headers=headers_b).json()
    assert listed_b["pagination"]["total"] == 0

    # Reading by id returns 404 (indistinguishable from "does not exist").
    assert (
        client.get(f"/api/crm/opportunities/{opp_id}", headers=headers_b).status_code
        == 404
    )
    # Updating / deleting / converting across tenants is impossible.
    assert (
        client.patch(
            f"/api/crm/opportunities/{opp_id}",
            headers=headers_b,
            json={"title": "hack"},
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/crm/opportunities/{opp_id}", headers=headers_b).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/crm/opportunities/{opp_id}/convert", headers=headers_b, json={}
        ).status_code
        == 404
    )

    # A cross-tenant customer reference is rejected on create.
    customer_a = client.post(
        "/api/clientes/customers", headers=headers_a, json={"name": "Cliente A"}
    ).json()
    rejected = client.post(
        "/api/crm/opportunities",
        headers=headers_b,
        json={"title": "Link cruzado", "customer_id": customer_a["id"]},
    )
    assert rejected.status_code == 422


def test_proposals_and_activities_are_tenant_scoped(client, db, seeded):
    tenant_a = _tenant(db, "CRM Iso P A")
    tenant_b = _tenant(db, "CRM Iso P B")
    headers_a = _admin_token(client, db, email="crm-pa@example.com", tenant_id=tenant_a.id)
    headers_b = _admin_token(client, db, email="crm-pb@example.com", tenant_id=tenant_b.id)

    proposal = _new_proposal(client, headers_a, title="Proposta A")
    assert client.get("/api/crm/proposals", headers=headers_b).json()["pagination"]["total"] == 0
    assert (
        client.get(f"/api/crm/proposals/{proposal['id']}", headers=headers_b).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/crm/proposals/{proposal['id']}/status",
            headers=headers_b,
            json={"status": "SENT"},
        ).status_code
        == 404
    )

    activity = client.post(
        "/api/crm/activities",
        headers=headers_a,
        json={
            "kind": "CALL",
            "subject_type": "PROPOSAL",
            "subject_id": proposal["id"],
            "title": "Ligação de follow-up",
        },
    )
    assert activity.status_code == 201, activity.text
    assert (
        client.get("/api/crm/activities", headers=headers_b).json()["pagination"]["total"]
        == 0
    )
    assert (
        client.patch(
            f"/api/crm/activities/{activity.json()['id']}",
            headers=headers_b,
            json={"outcome": "DONE"},
        ).status_code
        == 404
    )

    # An activity pointing at another tenant's subject is rejected.
    cross = client.post(
        "/api/crm/activities",
        headers=headers_b,
        json={
            "kind": "CALL",
            "subject_type": "PROPOSAL",
            "subject_id": proposal["id"],
            "title": "Cruzada",
        },
    )
    assert cross.status_code == 422


# --- Funnel lifecycle --------------------------------------------------------
def test_opportunity_code_is_sequential_per_tenant(client, db, seeded):
    tenant = _tenant(db, "CRM Codes")
    headers = _admin_token(client, db, email="codes@example.com", tenant_id=tenant.id)

    first = _new_opportunity(client, headers)
    second = _new_opportunity(client, headers)
    assert first["code"] == "OPP-000001"
    assert second["code"] == "OPP-000002"


def test_opportunity_stage_transitions_and_rules(client, db, seeded):
    tenant = _tenant(db, "CRM Rules")
    headers = _admin_token(client, db, email="rules@example.com", tenant_id=tenant.id)
    opportunity = _new_opportunity(client, headers)
    opp_id = opportunity["id"]
    assert opportunity["stage"] == "NEW"

    # Happy path along the funnel.
    for stage in ("QUALIFICATION", "PROPOSAL", "SENT", "NEGOTIATION"):
        resp = client.post(
            f"/api/crm/opportunities/{opp_id}/stage",
            headers=headers,
            json={"stage": stage},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["stage"] == stage

    # LOST without a reason is rejected (422).
    assert (
        client.post(
            f"/api/crm/opportunities/{opp_id}/stage",
            headers=headers,
            json={"stage": "LOST"},
        ).status_code
        == 422
    )

    # WON without a customer is refused (409) — conversion must be used.
    assert (
        client.post(
            f"/api/crm/opportunities/{opp_id}/stage",
            headers=headers,
            json={"stage": "WON"},
        ).status_code
        == 409
    )

    # An illegal jump (NEW -> SENT is fine, but WON -> NEW is not) is 409.
    won = client.post(
        f"/api/crm/opportunities/{opp_id}/convert", headers=headers, json={}
    )
    assert won.status_code == 200, won.text
    illegal = client.post(
        f"/api/crm/opportunities/{opp_id}/stage",
        headers=headers,
        json={"stage": "NEW"},
    )
    assert illegal.status_code == 409


def test_lost_records_reason(client, db, seeded):
    tenant = _tenant(db, "CRM Lost")
    headers = _admin_token(client, db, email="lost@example.com", tenant_id=tenant.id)
    opportunity = _new_opportunity(client, headers)

    lost = client.post(
        f"/api/crm/opportunities/{opportunity['id']}/stage",
        headers=headers,
        json={"stage": "LOST", "lost_reason": "Sem orçamento no período"},
    )
    assert lost.status_code == 200
    assert lost.json()["stage"] == "LOST"
    assert lost.json()["lost_reason"] == "Sem orçamento no período"


# --- Proposals lifecycle -----------------------------------------------------
def test_proposal_lifecycle_records_dates(client, db, seeded):
    tenant = _tenant(db, "CRM Proposal")
    headers = _admin_token(client, db, email="prop@example.com", tenant_id=tenant.id)
    opportunity = _new_opportunity(client, headers, estimated_value="1500.00")

    proposal = _new_proposal(
        client,
        headers,
        title="Proposta de PI",
        opportunity_id=opportunity["id"],
        total_value="1500.00",
        valid_until="2026-12-31",
    )
    assert proposal["status"] == "DRAFT"
    assert proposal["sent_at"] is None
    pid = proposal["id"]

    # DRAFT -> PENDING_SEND is allowed, but the illegal jump to APPROVED is not.
    illegal = client.post(
        f"/api/crm/proposals/{pid}/status", headers=headers, json={"status": "APPROVED"}
    )
    assert illegal.status_code == 409

    # DRAFT -> SENT stamps ``sent_at``.
    sent = client.post(
        f"/api/crm/proposals/{pid}/status", headers=headers, json={"status": "SENT"}
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["sent_at"] is not None

    # Registering the reply stamps ``replied_at``.
    reply = client.post(
        f"/api/crm/proposals/{pid}/status",
        headers=headers,
        json={"status": "AWAITING_REPLY", "mark_reply": True},
    )
    assert reply.status_code == 200, reply.text
    assert reply.json()["replied_at"] is not None

    # Approval stamps ``decision_at`` and keeps the notes.
    approved = client.post(
        f"/api/crm/proposals/{pid}/status",
        headers=headers,
        json={"status": "APPROVED", "decision_notes": "Contrato em elaboração"},
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "APPROVED"
    assert body["decision_at"] is not None
    assert body["decision_notes"] == "Contrato em elaboração"


def test_proposal_codes_are_sequential(client, db, seeded):
    tenant = _tenant(db, "CRM Prop Codes")
    headers = _admin_token(client, db, email="pcodes@example.com", tenant_id=tenant.id)
    assert _new_proposal(client, headers)["code"] == "PRO-000001"
    assert _new_proposal(client, headers)["code"] == "PRO-000002"


def test_proposal_is_not_a_registered_trademark(client, db, seeded):
    """Approving a proposal must not create a marca/patente anywhere."""
    tenant = _tenant(db, "CRM NoMarca")
    headers = _admin_token(client, db, email="nomarca@example.com", tenant_id=tenant.id)
    proposal = _new_proposal(client, headers)
    client.post(
        f"/api/crm/proposals/{proposal['id']}/status",
        headers=headers,
        json={"status": "SENT"},
    )
    client.post(
        f"/api/crm/proposals/{proposal['id']}/status",
        headers=headers,
        json={"status": "APPROVED"},
    )
    # The tenant's monitored PI assets remain untouched by the CRM approval.
    mon = client.get("/api/marcas/monitoramento", headers=headers).json()
    assert mon["pagination"]["total"] == 0


# --- Conversion --------------------------------------------------------------
def test_conversion_reuses_customer_without_duplicating(client, db, seeded):
    tenant = _tenant(db, "CRM Dedup")
    headers = _admin_token(client, db, email="dedup@example.com", tenant_id=tenant.id)

    existing = client.post(
        "/api/clientes/customers",
        headers=headers,
        json={"name": "Cliente Existente", "document": "12345678000199"},
    ).json()

    first = _new_opportunity(client, headers, title="Opp A")
    r1 = client.post(
        f"/api/crm/opportunities/{first['id']}/convert",
        headers=headers,
        json={"name": "Cliente Existente", "document": "12345678000199"},
    )
    assert r1.status_code == 200, r1.text

    # Same person, differently formatted document -> must NOT create a second row.
    second = _new_opportunity(client, headers, title="Opp B")
    r2 = client.post(
        f"/api/crm/opportunities/{second['id']}/convert",
        headers=headers,
        json={"name": "Cliente Existente", "document": "12.345.678/0001-99"},
    )
    assert r2.status_code == 200, r2.text

    customers = client.get("/api/clientes/customers", headers=headers).json()
    assert customers["pagination"]["total"] == 1
    assert customers["items"][0]["id"] == existing["id"]


def test_conversion_links_existing_customer_and_backfills_proposals(client, db, seeded):
    tenant = _tenant(db, "CRM Convert Link")
    headers = _admin_token(client, db, email="convlink@example.com", tenant_id=tenant.id)

    customer = client.post(
        "/api/clientes/customers", headers=headers, json={"name": "Cliente Alvo"}
    ).json()
    opportunity = _new_opportunity(client, headers, title="Opp vinculada")
    proposal = _new_proposal(
        client, headers, title="Proposta vinculada", opportunity_id=opportunity["id"]
    )
    assert proposal["customer_name"] is None

    converted = client.post(
        f"/api/crm/opportunities/{opportunity['id']}/convert",
        headers=headers,
        json={"customer_id": customer["id"]},
    )
    assert converted.status_code == 200, converted.text
    assert converted.json()["stage"] == "WON"
    assert converted.json()["customer_name"] == "Cliente Alvo"

    # The proposal keeps its history and now points at the customer.
    refreshed = client.get(f"/api/crm/proposals/{proposal['id']}", headers=headers).json()
    assert refreshed["customer_name"] == "Cliente Alvo"


# --- Dashboard ---------------------------------------------------------------
def test_business_dashboard_counts_are_tenant_scoped(client, db, seeded):
    tenant_a = _tenant(db, "Dash A")
    tenant_b = _tenant(db, "Dash B")
    headers_a = _admin_token(client, db, email="dash-a@example.com", tenant_id=tenant_a.id)
    headers_b = _admin_token(client, db, email="dash-b@example.com", tenant_id=tenant_b.id)

    # Tenant A has real activity; tenant B has none.
    client.post("/api/clientes/customers", headers=headers_a, json={"name": "Cliente A1"})
    client.post("/api/clientes/customers", headers=headers_a, json={"name": "Cliente A2"})
    opp = _new_opportunity(client, headers_a, estimated_value="2500.00")
    proposal = _new_proposal(
        client, headers_a, title="Proposta A", opportunity_id=opp["id"], valid_until="2020-01-01"
    )
    client.post(
        f"/api/crm/proposals/{proposal['id']}/status", headers=headers_a, json={"status": "SENT"}
    )

    dash_a = client.get("/api/dashboard/business", headers=headers_a).json()
    counters = dash_a["counters"]
    assert dash_a["scope"] == "tenant"
    assert counters["total_customers"] == 2
    assert counters["active_customers"] == 2
    assert counters["open_opportunities"] == 1
    assert counters["proposals_to_send"] == 0
    assert counters["proposals_awaiting_reply"] == 1
    assert counters["proposals_overdue"] == 1  # valid_until in the past + still open
    assert counters["conversion_rate"] is None  # nothing decided yet -> no fabrication

    # The funnel always exposes every stage, in order.
    assert [f["stage"] for f in dash_a["funnel"]] == [
        "NEW",
        "QUALIFICATION",
        "PROPOSAL",
        "SENT",
        "NEGOTIATION",
        "WON",
        "LOST",
    ]
    assert dash_a["funnel"][0]["count"] == 1
    assert dash_a["funnel"][0]["value"] == "2500.00"

    # The evolution series has one bucket per month of the requested window.
    evolution = dash_a["evolution"]
    assert len(evolution) == 12
    assert sum(p["new_customers"] for p in evolution) == 2
    assert sum(p["proposals_sent"] for p in evolution) == 1

    # There is a pending proposal listed, with a reason and the customer's data.
    assert len(dash_a["pending_proposals"]) >= 1
    first = dash_a["pending_proposals"][0]
    assert first["reason"] == "OVERDUE"
    assert first["status"] == "SENT"

    # Tenant B sees an empty, honest dashboard.
    dash_b = client.get("/api/dashboard/business", headers=headers_b).json()
    assert dash_b["counters"]["total_customers"] == 0
    assert dash_b["counters"]["open_opportunities"] == 0
    assert dash_b["pending_proposals"] == []
    assert all(p["new_customers"] == 0 for p in dash_b["evolution"])


def test_business_dashboard_recent_activity_is_real(client, db, seeded):
    tenant = _tenant(db, "Dash Activity")
    headers = _admin_token(client, db, email="dash-act@example.com", tenant_id=tenant.id)

    client.post("/api/clientes/customers", headers=headers, json={"name": "Cliente Novo"})
    _new_opportunity(client, headers, title="Oportunidade Nova")
    _new_proposal(client, headers, title="Proposta Nova")

    dash = client.get("/api/dashboard/business", headers=headers).json()
    kinds = {item["kind"] for item in dash["recent_activity"]}
    assert "customer" in kinds
    assert "opportunity" in kinds
    assert "proposal" in kinds
    # Events are ordered newest first.
    timestamps = [item["at"] for item in dash["recent_activity"]]
    assert timestamps == sorted(timestamps, reverse=True)


def test_business_dashboard_period_is_configurable(client, db, seeded):
    tenant = _tenant(db, "Dash Period")
    headers = _admin_token(client, db, email="dash-period@example.com", tenant_id=tenant.id)

    dash24 = client.get("/api/dashboard/business?months=24", headers=headers).json()
    assert dash24["period"]["months"] == 24
    assert len(dash24["evolution"]) == 24

    # Out-of-range periods are rejected by the query validation.
    assert (
        client.get("/api/dashboard/business?months=99", headers=headers).status_code == 422
    )




