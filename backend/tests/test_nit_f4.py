"""F4 — R&D projects, startups, incubation and institutional indicators tests.

Covers the F4 gate: project/participant isolation, project↔asset↔startup links,
document access, indicator calculation, period/unity filters and relation integrity.
"""

from __future__ import annotations

from decimal import Decimal

from tests.conftest import assign_role, auth_header, login, make_tenant, make_user

PROJECTS = "/api/nit/projects"
STARTUPS = "/api/nit/startups"
INDICATORS = "/api/nit/indicators"
FORMICT = "/api/nit/formict"
ASSETS = "/api/nit/assets"


def _nit_tenant(db):
    from app.seed_nit import seed_tenant_workflow

    tenant = make_tenant(db, name="ICT F4", module_codes=["NIT"])
    seed_tenant_workflow(db, tenant.id)
    db.commit()
    return tenant


def _user(db, tenant_id, role_code, email):
    user = make_user(db, email=email, tenant_id=tenant_id)
    assign_role(db, user.id, role_code)
    return user


def _headers(client, db, tenant_id, role="NIT_MANAGER", email="f4@nit.br"):
    _user(db, tenant_id, role, email)
    return auth_header(login(client, email)["access_token"])


def _make_project(client, headers, title="Projeto P&D", **extra):
    resp = client.post(PROJECTS, json={"title": title, **extra}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_asset(client, headers, title="Ativo F4"):
    resp = client.post(ASSETS, json={"title": title}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- Projects ----------------------------------------------------------------
def test_project_crud_and_isolation(db, client, seeded_full):
    ta = _nit_tenant(db)
    tb = _nit_tenant(db)
    ha = _headers(client, db, ta.id, email="pa@f4.br")
    hb = _headers(client, db, tb.id, email="pb@f4.br")

    project = _make_project(client, ha)
    assert project["code"].startswith("PRJ-")

    assert client.get(PROJECTS, headers=hb).json()["total"] == 0
    assert client.get(f"{PROJECTS}/{project['id']}", headers=hb).status_code == 403


def test_project_members_and_integrity(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id)
    project = _make_project(client, headers)

    m = client.post(
        f"{PROJECTS}/{project['id']}/members",
        json={"name": "Pesquisador A", "role": "COORDINATOR"},
        headers=headers,
    )
    assert m.status_code == 201, m.text

    f = client.post(
        f"{PROJECTS}/{project['id']}/funders",
        json={"name": "FAPESP", "amount": "50000.00"},
        headers=headers,
    )
    assert f.status_code == 201
    assert Decimal(f.json()["amount"]) == Decimal("50000.00")

    milestone = client.post(
        f"{PROJECTS}/{project['id']}/milestones",
        json={"title": "Protótipo", "status": "PENDING"},
        headers=headers,
    ).json()
    done = client.patch(
        f"{PROJECTS}/milestones/{milestone['id']}",
        json={"title": "Protótipo", "status": "DONE"},
        headers=headers,
    )
    assert done.status_code == 200
    assert done.json()["status"] == "DONE"
    assert done.json()["completed_at"] is not None

    detail = client.get(f"{PROJECTS}/{project['id']}", headers=headers).json()
    assert len(detail["members"]) == 1
    assert len(detail["funders"]) == 1
    assert len(detail["milestones"]) == 1


def test_project_asset_link_integrity(db, client, seeded_full):
    ta = _nit_tenant(db)
    tb = _nit_tenant(db)
    ha = _headers(client, db, ta.id, email="la@f4.br")
    hb = _headers(client, db, tb.id, email="lb@f4.br")

    project = _make_project(client, ha)
    own_asset = _make_asset(client, ha)
    foreign_asset = _make_asset(client, hb)

    ok = client.post(
        f"{PROJECTS}/{project['id']}/assets",
        json={"asset_id": own_asset["id"], "relation": "RESULT"},
        headers=ha,
    )
    assert ok.status_code == 201, ok.text

    bad = client.post(
        f"{PROJECTS}/{project['id']}/assets",
        json={"asset_id": foreign_asset["id"], "relation": "ORIGIN"},
        headers=ha,
    )
    assert bad.status_code in (403, 422)

    dup = client.post(
        f"{PROJECTS}/{project['id']}/assets",
        json={"asset_id": own_asset["id"]},
        headers=ha,
    )
    assert dup.status_code == 409


# --- Startups and incubation -------------------------------------------------
def test_startup_creation_and_link(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id)
    project = _make_project(client, headers)
    asset = _make_asset(client, headers)

    startup = client.post(
        STARTUPS,
        json={
            "name": "Spin-off X",
            "project_id": project["id"],
            "asset_id": asset["id"],
        },
        headers=headers,
    )
    assert startup.status_code == 201, startup.text
    assert startup.json()["code"].startswith("STP-")
    # A startup linked to an asset is NOT thereby its owner (no ownership field).
    assert "owner" not in startup.json()

    member = client.post(
        f"{STARTUPS}/{startup.json()['id']}/members",
        json={"name": "Fundadora", "is_founder": True},
        headers=headers,
    )
    assert member.status_code == 201

    tb = _nit_tenant(db)
    hb = _headers(client, db, tb.id, email="xb@f4.br")
    foreign_project = _make_project(client, hb)
    bad = client.post(
        STARTUPS,
        json={"name": "Y", "project_id": foreign_project["id"]},
        headers=headers,
    )
    assert bad.status_code in (403, 422)


def test_incubation_program_flow(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id)
    startup = client.post(STARTUPS, json={"name": "Incubada"}, headers=headers).json()

    program = client.post(
        f"{STARTUPS}/programs/list",
        json={"name": "Programa 2026", "criteria": "TRL >= 3"},
        headers=headers,
    )
    assert program.status_code == 201, program.text

    part = client.post(
        f"{STARTUPS}/programs/list/{program.json()['id']}/participations",
        json={"startup_id": startup["id"]},
        headers=headers,
    )
    assert part.status_code == 201, part.text
    pid = part.json()["id"]

    assert (
        client.get(f"{STARTUPS}/{startup['id']}", headers=headers).json()["status"]
        == "INCUBATED"
    )

    stage = client.post(
        f"{STARTUPS}/participations/{pid}/stages",
        json={"title": "Mentoria 1", "status": "COMPLETED"},
        headers=headers,
    )
    assert stage.status_code == 201, stage.text
    assert stage.json()["completed_at"] is not None

    detail = client.get(f"{STARTUPS}/participations/{pid}", headers=headers).json()
    assert len(detail["stages"]) == 1

    dup = client.post(
        f"{STARTUPS}/programs/list/{program.json()['id']}/participations",
        json={"startup_id": startup["id"]},
        headers=headers,
    )
    assert dup.status_code == 409


def test_startup_isolation(db, client, seeded_full):
    ta = _nit_tenant(db)
    tb = _nit_tenant(db)
    ha = _headers(client, db, ta.id, email="sa@f4.br")
    hb = _headers(client, db, tb.id, email="sb@f4.br")
    startup = client.post(STARTUPS, json={"name": "Só A"}, headers=ha).json()

    assert client.get(STARTUPS, headers=hb).json()["total"] == 0
    assert client.get(f"{STARTUPS}/{startup['id']}", headers=hb).status_code == 403


# --- Indicators & FORMICT ----------------------------------------------------
def test_indicators_reflect_real_rows(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id)

    base = client.get(INDICATORS, headers=headers).json()
    assert base["projects_total"] == 0 and base["startups_total"] == 0

    _make_project(client, headers, status="ACTIVE")
    _make_project(client, headers, status="PLANNED")
    client.post(STARTUPS, json={"name": "S1"}, headers=headers)
    startup2 = client.post(STARTUPS, json={"name": "S2"}, headers=headers).json()
    program = client.post(
        f"{STARTUPS}/programs/list", json={"name": "P"}, headers=headers
    ).json()
    client.post(
        f"{STARTUPS}/programs/list/{program['id']}/participations",
        json={"startup_id": startup2["id"]},
        headers=headers,
    )

    data = client.get(INDICATORS, headers=headers).json()
    assert data["projects_total"] == 2
    assert data["projects_active"] == 1
    assert data["startups_total"] == 2
    assert data["startups_incubated"] == 1
    assert data["period_from"] is not None and data["period_to"] is not None


def test_formict_report_is_support_only(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _headers(client, db, tenant.id)

    report = client.get(FORMICT, headers=headers)
    assert report.status_code == 200, report.text
    body = report.json()
    # The disclaimer explicitly states this is NOT the official submission.
    assert "NÃO é o formulário oficial" in body["disclaimer"]
    assert Decimal(body["total_registered"]) == Decimal("0")
    assert Decimal(body["total_received"]) == Decimal("0")

    export = client.get(f"{FORMICT}/export", headers=headers)
    assert export.status_code == 200
    assert "FORMICT" in export.text


def test_indicators_require_permission(db, client, seeded_full):
    tenant = _nit_tenant(db)
    _user(db, tenant.id, "NIT_RESEARCHER", "ir@f4.br")
    headers = auth_header(login(client, "ir@f4.br")["access_token"])
    assert client.get(INDICATORS, headers=headers).status_code == 403
    assert client.get(FORMICT, headers=headers).status_code == 403


def test_project_requires_permission(db, client, seeded_full):
    tenant = _nit_tenant(db)
    _user(db, tenant.id, "NIT_RESEARCHER", "pr@f4.br")
    headers = auth_header(login(client, "pr@f4.br")["access_token"])
    assert client.get(PROJECTS, headers=headers).status_code == 403



