"""MANDATORY tenant-isolation tests.

These tests prove that:
  * A tenant admin can only see/manage users of their own tenant.
  * Cross-tenant access is rejected (403) even when IDs are supplied explicitly.
  * The tenant is derived from the token, never trusted from the request.
  * The master admin can operate across tenants.
"""

from __future__ import annotations

from app.models import User
from tests.conftest import (
    assign_role,
    auth_header,
    login,
    make_tenant,
    make_user,
)


def _setup_two_tenants(db, seeded):
    tenant_a = make_tenant(db, name="Tenant A", module_codes=["ADMIN", "MARCAS"])
    tenant_b = make_tenant(db, name="Tenant B", module_codes=["ADMIN", "MARCAS"])

    admin_a = make_user(db, email="admin.a@example.com", tenant_id=tenant_a.id)
    admin_b = make_user(db, email="admin.b@example.com", tenant_id=tenant_b.id)
    assign_role(db, admin_a.id, "TENANT_ADMIN")
    assign_role(db, admin_b.id, "TENANT_ADMIN")

    user_a = make_user(db, email="user.a@example.com", tenant_id=tenant_a.id)
    user_b = make_user(db, email="user.b@example.com", tenant_id=tenant_b.id)
    return tenant_a, tenant_b, admin_a, admin_b, user_a, user_b


def test_list_users_only_returns_own_tenant(db, seeded, client):
    _setup_two_tenants(db, seeded)
    token_a = login(client, "admin.a@example.com")["access_token"]
    resp = client.get("/api/admin/users", headers=auth_header(token_a))
    assert resp.status_code == 200, resp.text
    emails = {u["email"] for u in resp.json()}

    assert "admin.a@example.com" in emails
    assert "user.a@example.com" in emails
    # Tenant B users must never appear for Tenant A admin.
    assert "admin.b@example.com" not in emails
    assert "user.b@example.com" not in emails


def test_list_users_ignores_cross_tenant_filter(db, seeded, client):
    """A tenant admin passing ?tenant_id=<other> must NOT see other tenant data."""
    tenant_a, tenant_b, *_ = _setup_two_tenants(db, seeded)
    token_a = login(client, "admin.a@example.com")["access_token"]

    resp = client.get(
        f"/api/admin/users?tenant_id={tenant_b.id}", headers=auth_header(token_a)
    )
    assert resp.status_code == 200, resp.text
    emails = {u["email"] for u in resp.json()}
    assert "user.b@example.com" not in emails
    assert emails.issubset({"admin.a@example.com", "user.a@example.com"})


def test_get_other_tenant_user_is_forbidden(db, seeded, client):
    _t_a, _t_b, _admin_a, _admin_b, user_a, user_b = _setup_two_tenants(db, seeded)
    token_a = login(client, "admin.a@example.com")["access_token"]

    resp = client.get(f"/api/admin/users/{user_b.id}", headers=auth_header(token_a))
    assert resp.status_code == 403, resp.text

    # Own tenant user works.
    ok = client.get(f"/api/admin/users/{user_a.id}", headers=auth_header(token_a))
    assert ok.status_code == 200, ok.text


def test_update_other_tenant_user_is_forbidden(db, seeded, client):
    _t_a, _t_b, _admin_a, _admin_b, _user_a, user_b = _setup_two_tenants(db, seeded)
    token_a = login(client, "admin.a@example.com")["access_token"]

    resp = client.patch(
        f"/api/admin/users/{user_b.id}",
        headers=auth_header(token_a),
        json={"name": "Hacked"},
    )
    assert resp.status_code == 403, resp.text

    db.expire_all()
    refreshed = db.get(User, user_b.id)
    assert refreshed.name != "Hacked"


def test_create_user_in_other_tenant_is_forbidden(db, seeded, client):
    _t_a, tenant_b, *_ = _setup_two_tenants(db, seeded)
    token_a = login(client, "admin.a@example.com")["access_token"]

    resp = client.post(
        "/api/admin/users",
        headers=auth_header(token_a),
        json={
            "access_code": "intruder@example.com",
            "email": "intruder@example.com",
            "password": "Password123!",
            "tenant_id": str(tenant_b.id),
        },
    )
    assert resp.status_code == 403, resp.text


def test_create_user_without_tenant_defaults_to_own_tenant(db, seeded, client):
    tenant_a, _tenant_b, *_ = _setup_two_tenants(db, seeded)
    token_a = login(client, "admin.a@example.com")["access_token"]

    resp = client.post(
        "/api/admin/users",
        headers=auth_header(token_a),
        json={
            "access_code": "new.a@example.com",
            "email": "new.a@example.com",
            "name": "New A",
            "password": "Password123!",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["tenant_id"] == str(tenant_a.id)


def test_deactivate_other_tenant_user_is_forbidden(db, seeded, client):
    _t_a, _t_b, _admin_a, _admin_b, _user_a, user_b = _setup_two_tenants(db, seeded)
    token_a = login(client, "admin.a@example.com")["access_token"]

    resp = client.delete(f"/api/admin/users/{user_b.id}", headers=auth_header(token_a))
    assert resp.status_code == 403, resp.text


def test_master_admin_can_see_all_tenants(db, seeded, client):
    _t_a, tenant_b, *_ = _setup_two_tenants(db, seeded)
    token_master = login(
        client,
        "master@intelliinpi.com.br",
        "ChangeMe_MasterAdmin_123!",
    )["access_token"]

    resp = client.get("/api/admin/users", headers=auth_header(token_master))
    assert resp.status_code == 200, resp.text
    emails = {u["email"] for u in resp.json()}
    assert {"admin.a@example.com", "user.b@example.com"}.issubset(emails)

    filtered = client.get(
        f"/api/admin/users?tenant_id={tenant_b.id}", headers=auth_header(token_master)
    )
    assert filtered.status_code == 200
    f_emails = {u["email"] for u in filtered.json()}
    assert "user.b@example.com" in f_emails
    assert "user.a@example.com" not in f_emails


def test_master_admin_can_manage_other_tenant_user(db, seeded, client):
    user_b = _setup_two_tenants(db, seeded)[5]
    token_master = login(
        client, "master@intelliinpi.com.br", "ChangeMe_MasterAdmin_123!"
    )["access_token"]

    resp = client.get(
        f"/api/admin/users/{user_b.id}", headers=auth_header(token_master)
    )
    assert resp.status_code == 200, resp.text


def test_tenant_derived_from_token_not_request_body(db, seeded, client):
    """A tampered tenant_id inside the request body must be rejected."""
    _t_a, tenant_b, *_ = _setup_two_tenants(db, seeded)
    token_a = login(client, "admin.a@example.com")["access_token"]

    resp = client.post(
        "/api/admin/users",
        headers=auth_header(token_a),
        json={
            "access_code": "smuggled@example.com",
            "email": "smuggled@example.com",
            "password": "Password123!",
            "tenant_id": str(tenant_b.id),
        },
    )
    assert resp.status_code == 403, resp.text


def test_modules_scoped_to_tenant(db, seeded, client):
    """A role bound to a module only grants permissions if the module is enabled."""
    tenant_a = make_tenant(db, name="Only Marcas", module_codes=["MARCAS"])
    analista = make_user(db, email="analista@example.com", tenant_id=tenant_a.id)
    assign_role(db, analista.id, "MARCAS_VIEW")

    token = login(client, "analista@example.com")["access_token"]
    me = client.get("/api/auth/me", headers=auth_header(token))
    assert me.status_code == 200, me.text
    body = me.json()
    assert "MARCAS_VIEW" in body["permissions"]
    assert "USER_VIEW" not in body["permissions"]
    assert not any(p.startswith("TENANT_") for p in body["permissions"])


def test_user_without_role_has_no_permissions(db, seeded, client):
    tenant_a = make_tenant(db, name="Empty", module_codes=["MARCAS"])
    make_user(db, email="nobody@example.com", tenant_id=tenant_a.id)

    token = login(client, "nobody@example.com")["access_token"]
    resp = client.get("/api/admin/users", headers=auth_header(token))
    assert resp.status_code == 403, resp.text

    me = client.get("/api/auth/me", headers=auth_header(token))
    assert me.status_code == 200
    assert me.json()["permissions"] == []

