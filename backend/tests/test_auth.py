"""Authentication tests: login, me, refresh rotation, logout, rate limiting."""

from __future__ import annotations

from tests.conftest import assign_role, auth_header, login, make_tenant, make_user

MASTER_EMAIL = "master@intelliinpi.com.br"
MASTER_PASSWORD = "ChangeMe_MasterAdmin_123!"


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "intelliinpi"


def test_login_success_returns_tokens(client, db, seeded):
    resp = client.post(
        "/api/auth/login", json={"email": MASTER_EMAIL, "password": MASTER_PASSWORD}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["expires_in"] > 0


def test_login_wrong_password_is_generic(client, db, seeded):
    resp = client.post(
        "/api/auth/login", json={"email": MASTER_EMAIL, "password": "wrong-password"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Credenciais inválidas."


def test_login_unknown_email_is_generic(client, db, seeded):
    resp = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Credenciais inválidas."


def test_inactive_user_cannot_login(client, db, seeded):
    tenant = make_tenant(db, name="T", module_codes=["MARCAS"])
    make_user(db, email="inactive@example.com", tenant_id=tenant.id, active=False)
    resp = client.post(
        "/api/auth/login",
        json={"email": "inactive@example.com", "password": "Password123!"},
    )
    # Inactive accounts get the same generic error (no account-status leak).
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Credenciais inválidas."


def test_inactive_tenant_user_cannot_login(client, db, seeded):
    tenant = make_tenant(db, name="T2", module_codes=["MARCAS"])
    tenant.active = False
    db.commit()
    make_user(db, email="intenant@example.com", tenant_id=tenant.id)
    resp = client.post(
        "/api/auth/login",
        json={"email": "intenant@example.com", "password": "Password123!"},
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Credenciais inválidas."


def test_me_requires_authentication(client, db, seeded):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_returns_master_admin_context(client, db, seeded):
    tokens = login(client, MASTER_EMAIL, MASTER_PASSWORD)
    resp = client.get("/api/auth/me", headers=auth_header(tokens["access_token"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_master_admin"] is True
    assert body["email"] == MASTER_EMAIL
    assert "MASTER_ADMIN" in body["roles"]
    assert len(body["permissions"]) > 0


def test_invalid_token_rejected(client, db, seeded):
    resp = client.get("/api/auth/me", headers=auth_header("not-a-real-token"))
    assert resp.status_code == 401


def test_refresh_rotates_token(client, db, seeded):
    tokens = login(client, MASTER_EMAIL, MASTER_PASSWORD)
    old_refresh = tokens["refresh_token"]

    resp = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert resp.status_code == 200, resp.text
    new_refresh = resp.json()["refresh_token"]
    assert new_refresh != old_refresh

    # The old refresh token must no longer be accepted (rotation).
    reuse = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401


def test_logout_revokes_refresh(client, db, seeded):
    tokens = login(client, MASTER_EMAIL, MASTER_PASSWORD)
    refresh = tokens["refresh_token"]

    logout = client.post("/api/auth/logout", json={"refresh_token": refresh})
    assert logout.status_code == 200

    reuse = client.post("/api/auth/refresh", json={"refresh_token": refresh})
    assert reuse.status_code == 401


def test_no_permission_endpoint_returns_403(client, db, seeded):
    tenant = make_tenant(db, name="NoPerm", module_codes=["MARCAS"])
    make_user(db, email="plain@example.com", tenant_id=tenant.id)
    token = login(client, "plain@example.com")["access_token"]
    resp = client.get("/api/admin/tenants", headers=auth_header(token))
    assert resp.status_code == 403
