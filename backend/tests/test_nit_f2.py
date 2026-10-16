"""F2 — committees, TRL and advanced portfolio tests.

Covers the F2 gate: committee authorization, conflict of interest, quorum and
voting, integrity of history, deadline alerts, data isolation and regression.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import assign_role, auth_header, login, make_tenant, make_user

COMMITTEES = "/api/nit/committees"
TRL = "/api/nit/trl"
PORTFOLIO = "/api/nit/portfolio"
ASSETS = "/api/nit/assets"


def _nit_tenant(db):
    from app.seed_nit import seed_tenant_workflow

    tenant = make_tenant(db, name="ICT F2", module_codes=["NIT"])
    seed_tenant_workflow(db, tenant.id)
    db.commit()
    return tenant


def _user(db, tenant_id, role_code, email):
    user = make_user(db, email=email, tenant_id=tenant_id)
    assign_role(db, user.id, role_code)
    return user


def _manager_headers(client, db, tenant_id, email="mgr@f2.br"):
    _user(db, tenant_id, "NIT_MANAGER", email)
    return auth_header(login(client, email)["access_token"])


def _make_committee(client, headers, quorum=2):
    resp = client.post(
        COMMITTEES,
        json={"name": "Comitê de Inovação", "quorum": quorum},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _add_member(client, headers, committee_id, name):
    resp = client.post(
        f"{COMMITTEES}/{committee_id}/members",
        json={"name": name, "kind": "VOTING"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- Committees: CRUD, isolation --------------------------------------------
def test_committee_crud_and_isolation(db, client, seeded_full):
    ta = _nit_tenant(db)
    tb = _nit_tenant(db)
    ha = _manager_headers(client, db, ta.id)
    hb = _manager_headers(client, db, tb.id, email="mgrb@f2.br")

    committee = _make_committee(client, ha)
    assert committee["code"].startswith("COM-")

    # The other tenant cannot see it or fetch it by id.
    assert client.get(COMMITTEES, headers=hb).json() == []
    assert client.get(f"{COMMITTEES}/{committee['id']}", headers=hb).status_code == 403


def test_committee_requires_permission(db, client, seeded_full):
    tenant = _nit_tenant(db)
    _user(db, tenant.id, "NIT_RESEARCHER", "res@f2.br")
    headers = auth_header(login(client, "res@f2.br")["access_token"])
    # A researcher lacks NIT_COMMITTEE_VIEW.
    assert client.get(COMMITTEES, headers=headers).status_code == 403


# --- Voting, quorum, conflict of interest -----------------------------------
def _setup_meeting_with_item(client, headers, db, quorum=2, members=("A", "B")):
    committee = _make_committee(client, headers, quorum=quorum)
    member_ids = [_add_member(client, headers, committee["id"], n)["id"] for n in members]
    meeting = client.post(
        f"{COMMITTEES}/{committee['id']}/meetings",
        json={
            "title": "Reunião ordinária",
            "scheduled_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    ).json()
    item = client.post(
        f"{COMMITTEES}/meetings/{meeting['id']}/items",
        json={"title": "Deliberação 1"},
        headers=headers,
    ).json()
    return committee, member_ids, item


def test_vote_quorum_blocks_premature_decision(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _manager_headers(client, db, tenant.id)
    committee, member_ids, item = _setup_meeting_with_item(client, headers, db, quorum=2)

    # Only one vote cast -> quorum of 2 not reached -> decision rejected.
    v = client.post(
        f"{COMMITTEES}/items/{item['id']}/votes",
        json={"member_id": member_ids[0], "vote": "APPROVE"},
        headers=headers,
    )
    assert v.status_code == 201, v.text

    d = client.post(
        f"{COMMITTEES}/items/{item['id']}/decision",
        json={"outcome": "APPROVED"},
        headers=headers,
    )
    assert d.status_code == 409  # quorum insuficiente


def test_vote_quorum_met_allows_approval(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _manager_headers(client, db, tenant.id)
    committee, member_ids, item = _setup_meeting_with_item(client, headers, db, quorum=2)

    for mid in member_ids:
        r = client.post(
            f"{COMMITTEES}/items/{item['id']}/votes",
            json={"member_id": mid, "vote": "APPROVE"},
            headers=headers,
        )
        assert r.status_code == 201, r.text

    tally = client.get(f"{COMMITTEES}/items/{item['id']}/votes", headers=headers).json()
    assert tally["valid"] == 2 and tally["can_approve"] is True

    d = client.post(
        f"{COMMITTEES}/items/{item['id']}/decision",
        json={"outcome": "APPROVED", "justification": "Aprovado pelo comitê"},
        headers=headers,
    )
    assert d.status_code == 200, d.text
    assert d.json()["outcome"] == "APPROVED"
    assert d.json()["approvals"] == 2


def test_conflict_of_interest_impedes_vote(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _manager_headers(client, db, tenant.id)
    committee, member_ids, item = _setup_meeting_with_item(client, headers, db, quorum=2)

    # Member A declares a conflict -> recorded as IMPEDED.
    r = client.post(
        f"{COMMITTEES}/items/{item['id']}/votes",
        json={"member_id": member_ids[0], "vote": "APPROVE", "conflict_of_interest": True},
        headers=headers,
    )
    assert r.status_code == 201 and r.json()["vote"] == "IMPEDED"

    tally = client.get(f"{COMMITTEES}/items/{item['id']}/votes", headers=headers).json()
    assert tally["impeded"] == 1 and tally["valid"] == 0


def test_duplicate_vote_rejected(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _manager_headers(client, db, tenant.id)
    committee, member_ids, item = _setup_meeting_with_item(client, headers, db, quorum=1)

    first = client.post(
        f"{COMMITTEES}/items/{item['id']}/votes",
        json={"member_id": member_ids[0], "vote": "APPROVE"},
        headers=headers,
    )
    assert first.status_code == 201
    second = client.post(
        f"{COMMITTEES}/items/{item['id']}/votes",
        json={"member_id": member_ids[0], "vote": "REJECT"},
        headers=headers,
    )
    assert second.status_code == 409


def test_decision_requires_permission(db, client, seeded_full):
    tenant = _nit_tenant(db)
    mgr = _manager_headers(client, db, tenant.id)
    # Committee member can vote but not decide.
    member_user = _user(db, tenant.id, "NIT_COMMITTEE_MEMBER", "member@f2.br")
    mheaders = auth_header(login(client, "member@f2.br")["access_token"])
    committee, member_ids, item = _setup_meeting_with_item(client, mgr, db, quorum=1)

    v = client.post(
        f"{COMMITTEES}/items/{item['id']}/votes",
        json={"member_id": member_ids[0], "vote": "APPROVE"},
        headers=mheaders,
    )
    assert v.status_code == 201, v.text
    d = client.post(
        f"{COMMITTEES}/items/{item['id']}/decision",
        json={"outcome": "APPROVED"},
        headers=mheaders,
    )
    assert d.status_code == 403
    _ = member_user


# --- TRL ---------------------------------------------------------------------
def _create_asset(client, headers, title="Ativo F2", **extra):
    resp = client.post(ASSETS, json={"title": title, **extra}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_trl_requires_target_and_records_history(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _manager_headers(client, db, tenant.id)
    asset = _create_asset(client, headers)

    # Neither/both targets -> 422.
    assert client.post(TRL, json={"level": 3, "rationale": "x"}, headers=headers).status_code == 422

    r1 = client.post(
        TRL,
        json={"asset_id": asset["id"], "level": 3, "rationale": "Prova de conceito"},
        headers=headers,
    )
    assert r1.status_code == 201, r1.text
    assert r1.json()["previous_level"] is None

    r2 = client.post(
        TRL,
        json={"asset_id": asset["id"], "level": 5, "rationale": "Protótipo validado"},
        headers=headers,
    )
    assert r2.status_code == 201
    assert r2.json()["previous_level"] == 3

    history = client.get(
        f"{TRL}/history?asset_id={asset['id']}", headers=headers
    ).json()
    assert len(history) == 2
    assert history[0]["level"] == 5  # newest first


def test_trl_isolation_across_tenants(db, client, seeded_full):
    ta = _nit_tenant(db)
    tb = _nit_tenant(db)
    ha = _manager_headers(client, db, ta.id)
    hb = _manager_headers(client, db, tb.id, email="mgrtb@f2.br")
    asset = _create_asset(client, ha)

    # B cannot record TRL against A's asset.
    r = client.post(
        TRL,
        json={"asset_id": asset["id"], "level": 4, "rationale": "tentativa"},
        headers=hb,
    )
    assert r.status_code == 403


def test_trl_requires_permission(db, client, seeded_full):
    tenant = _nit_tenant(db)
    _manager_headers(client, db, tenant.id)
    _user(db, tenant.id, "NIT_RESEARCHER", "tr@f2.br")
    headers = auth_header(login(client, "tr@f2.br")["access_token"])
    assert client.get(f"{TRL}/history", headers=headers).status_code == 403


# --- Portfolio & alerts ------------------------------------------------------
def test_portfolio_view_and_real_alerts(db, client, seeded_full):
    tenant = _nit_tenant(db)
    headers = _manager_headers(client, db, tenant.id)

    soon = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
    far = (datetime.now(timezone.utc) + timedelta(days=800)).isoformat()
    past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()

    _create_asset(client, headers, "Ativo A", asset_type="PATENT", expires_at=soon)
    _create_asset(client, headers, "Ativo B", asset_type="SOFTWARE", expires_at=far)
    _create_asset(client, headers, "Ativo C", asset_type="PATENT", expires_at=past)

    view = client.get(PORTFOLIO, headers=headers).json()
    assert view["total"] == 3
    assert view["by_type"].get("PATENT") == 2
    assert view["expiring_soon"] == 1
    assert view["expired"] == 1

    alerts = client.get(f"{PORTFOLIO}/alerts?days=90", headers=headers).json()
    # Only the soon/past assets (with a real expires_at within the window).
    assert len(alerts) == 2
    assert alerts[0]["severity"] == "expired"  # sorted by days_to_expiry asc


def test_portfolio_no_invented_deadlines(db, client, seeded_full):
    """An asset without ``expires_at`` never appears in the alerts."""
    tenant = _nit_tenant(db)
    headers = _manager_headers(client, db, tenant.id)
    _create_asset(client, headers, "Ativo sem vigência")

    view = client.get(PORTFOLIO, headers=headers).json()
    assert view["items"][0]["days_to_expiry"] is None
    assert view["expiring_soon"] == 0 and view["expired"] == 0
    assert client.get(f"{PORTFOLIO}/alerts", headers=headers).json() == []


def test_portfolio_isolation(db, client, seeded_full):
    ta = _nit_tenant(db)
    tb = _nit_tenant(db)
    ha = _manager_headers(client, db, ta.id)
    hb = _manager_headers(client, db, tb.id, email="mgrtb2@f2.br")
    _create_asset(client, ha, "Somente A")

    assert client.get(PORTFOLIO, headers=hb).json()["total"] == 0


