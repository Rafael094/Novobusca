"""F5 — notifications, external portals, BI reports and integrations tests.

Covers the F5 gate: notification isolation and opt-in e-mail, portal grant
lifecycle + public token submission (rejects revoked/unknown), BI metric
whitelisting and real-query results, integration outbox discipline (stays
PENDING), TypeScript type generation, and permission gates.
"""

from __future__ import annotations

from tests.conftest import assign_role, auth_header, login, make_tenant, make_user

NOTIFICATIONS = "/api/nit/notifications"
PORTAL = "/api/nit/portal"
BI = "/api/nit/bi"
INTEGRATIONS = "/api/nit/integrations"
DEV_TS = "/api/nit/dev/ts-types"


def _nit_tenant(db):
    from app.seed_nit import seed_tenant_workflow

    tenant = make_tenant(db, name="ICT F5", module_codes=["NIT"])
    seed_tenant_workflow(db, tenant.id)
    db.commit()
    return tenant


def _user(db, tenant_id, role_code, email):
    user = make_user(db, email=email, tenant_id=tenant_id)
    assign_role(db, user.id, role_code)
    return user


def _headers(client, db, tenant_id, role="NIT_MANAGER", email="f5@nit.br"):
    _user(db, tenant_id, role, email)
    return auth_header(login(client, email)["access_token"])


def _notify(db, tenant_id, user_id, title):
    from app.services.notifications import notify_user

    notify_user(
        db,
        tenant_id=tenant_id,
        user_id=user_id,
        title=title,
        kind="GENERIC",
    )
    db.commit()


# --- Notifications ----------------------------------------------------------
def test_notifications_are_user_scoped(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers_a = _headers(client, db, tenant.id, email="na@f5.br")
    _headers(client, db, tenant.id, email="nb@f5.br")
    user_a = make_user(db, email="na@f5.br2", tenant_id=tenant.id)
    db.commit()

    _notify(db, tenant.id, user_a.id, "Sua notificação")

    # A different user never sees another user's notifications.
    listing = client.get(NOTIFICATIONS, headers=headers_a).json()
    assert listing["total"] == 0


def test_notification_read_flow(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id, email="read@f5.br")
    token = login(client, "read@f5.br")["access_token"]
    me = client.get("/api/auth/me", headers=auth_header(token)).json()

    _notify(db, tenant.id, me["id"], "Você foi designado")
    listing = client.get(NOTIFICATIONS, headers=headers).json()
    assert listing["total"] == 1
    assert listing["unread"] == 1
    notification_id = listing["items"][0]["id"]

    read = client.post(f"{NOTIFICATIONS}/{notification_id}/read", headers=headers)
    assert read.status_code == 200
    assert read.json()["read_at"] is not None
    assert client.get(NOTIFICATIONS, headers=headers).json()["unread"] == 0


def test_notification_email_opt_in_queues_outbox(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id, email="pref@f5.br")
    token = login(client, "pref@f5.br")["access_token"]
    me = client.get("/api/auth/me", headers=auth_header(token)).json()

    pref = client.put(
        f"{NOTIFICATIONS}/preferences",
        json={"kind": "GENERIC", "in_app_enabled": True, "email_enabled": True},
        headers=headers,
    )
    assert pref.status_code == 200
    assert pref.json()["email_enabled"] is True

    from app.services.notifications import notify_user

    notify_user(
        db,
        tenant_id=tenant.id,
        user_id=me["id"],
        title="Com e-mail",
        kind="GENERIC",
        email="pref@f5.br",
    )
    db.commit()

    emails = client.get(f"{NOTIFICATIONS}/emails", headers=headers).json()
    assert len(emails) == 1
    # The outbox entry is queued, never claimed as sent without a real transport.
    assert emails[0]["status"] == "QUEUED"


def test_notification_invalid_preference_kind_rejected(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id, email="bad@f5.br")
    resp = client.put(
        f"{NOTIFICATIONS}/preferences",
        json={"kind": "NOPE", "in_app_enabled": True, "email_enabled": False},
        headers=headers,
    )
    assert resp.status_code == 422


# --- External portals -------------------------------------------------------
def _grant(client, headers, email="pesq@ext.br", kind="RESEARCHER"):
    resp = client.post(
        f"{PORTAL}/access",
        json={"portal_kind": kind, "email": email, "name": "Pesquisador Externo"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_portal_grant_lifecycle_and_public_submission(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id, email="pv@f5.br")

    grant = _grant(client, headers)
    # The token is revealed exactly once at creation.
    assert grant["access_token"]
    token = grant["access_token"]

    # Internal listing never exposes the token again.
    listing = client.get(f"{PORTAL}/access", headers=headers).json()
    assert len(listing) == 1
    assert listing[0].get("access_token") is None

    # Public submission with the correct token succeeds.
    submit = client.post(
        f"{PORTAL}/public/RESEARCHER/requests?email=pesq@ext.br&token={token}",
        json={"request_type": "INFORMATION", "subject": "Dúvida sobre PI"},
    )
    assert submit.status_code == 201, submit.text
    assert submit.json()["status"] == "NEW"

    # Wrong token is rejected.
    bad = client.post(
        f"{PORTAL}/public/RESEARCHER/requests?email=pesq@ext.br&token=wrongtoken123",
        json={"request_type": "INFORMATION", "subject": "x"},
    )
    assert bad.status_code == 401

    # Tríage by internal staff.
    request_id = submit.json()["id"]
    triage = client.post(
        f"{PORTAL}/requests/{request_id}/triage",
        json={"status": "TRIAGED", "note": "Encaminhado ao setor"},
        headers=headers,
    )
    assert triage.status_code == 200
    assert triage.json()["status"] == "TRIAGED"
    assert len(triage.json()["notes"]) == 1

    # Revoked grant is refused.
    assert client.post(f"{PORTAL}/access/{grant['id']}/revoke", headers=headers).status_code == 200
    after = client.post(
        f"{PORTAL}/public/RESEARCHER/requests?email=pesq@ext.br&token={token}",
        json={"request_type": "INFORMATION", "subject": "y"},
    )
    assert after.status_code == 401


def test_portal_access_duplicate_rejected(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id, email="dup@f5.br")
    _grant(client, headers, email="same@ext.br")
    again = client.post(
        f"{PORTAL}/access",
        json={"portal_kind": "RESEARCHER", "email": "same@ext.br", "name": "Duplicado"},
        headers=headers,
    )
    assert again.status_code == 409


def test_portal_requests_are_tenant_scoped(db, client, seeded_full):
    ta = _nit_tenant(db)
    tb = _nit_tenant(db)
    ha = _headers(client, db, ta.id, email="ra@f5.br")
    hb = _headers(client, db, tb.id, email="rb@f5.br")

    grant = _grant(client, ha)
    client.post(
        f"{PORTAL}/public/RESEARCHER/requests?email=pesq@ext.br&token={grant['access_token']}",
        json={"request_type": "INFORMATION", "subject": "Somente do tenant A"},
    )
    assert len(client.get(f"{PORTAL}/requests", headers=ha).json()) == 1
    assert len(client.get(f"{PORTAL}/requests", headers=hb).json()) == 0


# --- BI reports -------------------------------------------------------------
def test_bi_report_real_metrics_and_whitelist(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id, email="bi@f5.br")

    metrics = client.get(f"{BI}/metrics", headers=headers).json()
    assert "disclosure_total" in metrics
    assert "startups_incubated" in metrics

    # An unknown metric is rejected (only real metrics can be selected).
    bad = client.post(
        f"{BI}/reports",
        json={"name": "Ruim", "metrics": ["not_a_metric"]},
        headers=headers,
    )
    assert bad.status_code == 422

    created = client.post(
        f"{BI}/reports",
        json={"name": "Meu relatório", "metrics": ["disclosure_total", "startups_total"]},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    report_id = created.json()["id"]

    # Duplicate report name is rejected per tenant.
    dup = client.post(
        f"{BI}/reports",
        json={"name": "Meu relatório", "metrics": []},
        headers=headers,
    )
    assert dup.status_code == 409

    run = client.post(f"{BI}/reports/{report_id}/run", headers=headers)
    assert run.status_code == 200
    result = run.json()["result"]
    # Values come from real queries (tenant has no data yet => zeros).
    assert result["disclosure_total"] == 0
    assert result["startups_total"] == 0

    export = client.get(f"{BI}/reports/{report_id}/export", headers=headers)
    assert export.status_code == 200
    assert "indicador,valor" in export.text


def test_bi_reports_are_tenant_scoped(db, client, seeded_full):
    ta = _nit_tenant(db)
    tb = _nit_tenant(db)
    ha = _headers(client, db, ta.id, email="bia@f5.br")
    hb = _headers(client, db, tb.id, email="bib@f5.br")

    report = client.post(
        f"{BI}/reports",
        json={"name": "Relatório A", "metrics": ["disclosure_total"]},
        headers=ha,
    ).json()

    assert len(client.get(f"{BI}/reports", headers=hb).json()) == 0
    assert client.post(f"{BI}/reports/{report['id']}/run", headers=hb).status_code == 403


# --- Integrations -----------------------------------------------------------
def test_integration_outbox_stays_pending(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id, email="int@f5.br")

    endpoint = client.post(
        f"{INTEGRATIONS}/endpoints",
        json={"kind": "SEI", "name": "SEI Institucional", "enabled": True},
        headers=headers,
    )
    assert endpoint.status_code == 201, endpoint.text

    delivery = client.post(
        f"{INTEGRATIONS}/endpoints/{endpoint.json()['id']}/deliveries",
        json={"event": "DISCLOSURE_CREATED", "payload": {"id": "x"}},
        headers=headers,
    )
    assert delivery.status_code == 201
    # Nothing is claimed as delivered without a real transport.
    assert delivery.json()["status"] == "PENDING"
    assert delivery.json()["delivered_at"] is None


def test_integration_broadcast_only_enabled_endpoints(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id, email="bc@f5.br")

    client.post(
        f"{INTEGRATIONS}/endpoints",
        json={"kind": "SEI", "name": "Ativo", "enabled": True},
        headers=headers,
    )
    client.post(
        f"{INTEGRATIONS}/endpoints",
        json={"kind": "SIGA", "name": "Inativo", "enabled": False},
        headers=headers,
    )

    broadcast = client.post(
        f"{INTEGRATIONS}/broadcast",
        json={"event": "TEST_EVENT", "payload": {}},
        headers=headers,
    )
    assert broadcast.status_code == 200
    # Only the enabled endpoint receives a queued delivery.
    assert len(broadcast.json()) == 1


# --- Dev tooling / TS types -------------------------------------------------
def test_ts_types_generation(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id, email="dev@f5.br")
    resp = client.get(DEV_TS, headers=headers)
    assert resp.status_code == 200
    assert "export type" in resp.text


# --- Permission gates -------------------------------------------------------
def test_f5_permission_gates(db, client, seeded_full):
    tenant = _nit_tenant(db)
    # A researcher cannot manage the portal nor BI reports.
    headers = _headers(client, db, tenant.id, role="NIT_RESEARCHER", email="low@f5.br")
    assert client.get(f"{PORTAL}/access", headers=headers).status_code == 403
    assert client.get(f"{BI}/reports", headers=headers).status_code == 403
    assert client.get(DEV_TS, headers=headers).status_code == 403



