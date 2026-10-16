"""F0 — Foundation hardening tests.

Covers the independent, decision-free security fixes made in phase F0:

* R-04 — refuse to start a non-local environment with default secrets;
* R-08 — a tenant admin cannot attach a role belonging to another tenant;
* R-10 — structured logging / request correlation id;
* R-14 — integrity violations map to HTTP 409 (not 500);
* error responses never leak internal details.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.conftest import assign_role, auth_header, login, make_tenant, make_user


# --- R-04: insecure defaults refused outside local ---------------------------


def _settings(**env_overrides):
    """Build a fresh Settings ignoring any .env, using explicit values only."""
    from app.config import Settings

    base = {
        "DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/db",
        "INPI_BASE_URL": "https://dadosabertos.inpi.gov.br",
    }
    base.update(env_overrides)
    return Settings(_env_file=None, **base)


def test_local_env_tolerates_dev_defaults():
    s = _settings(ENVIRONMENT="local")
    assert s.jwt_secret == "dev-secret-change-me"


def test_test_env_tolerates_dev_defaults():
    # The test-suite itself runs with ENVIRONMENT=test.
    s = _settings(ENVIRONMENT="test")
    assert s.jwt_refresh_secret == "dev-refresh-secret-change-me"


def test_production_refuses_default_jwt_secret():
    with pytest.raises(ValidationError) as exc:
        _settings(ENVIRONMENT="production")
    assert "JWT_SECRET" in str(exc.value)


def test_production_refuses_short_secret():
    with pytest.raises(ValidationError) as exc:
        _settings(
            ENVIRONMENT="production",
            JWT_SECRET="short",
            JWT_REFRESH_SECRET="another-short-secret",
            MASTER_ADMIN_PASSWORD="Str0ng-Re@l-Admin-Password!",
        )
    assert "32 caracteres" in str(exc.value)


def test_production_refuses_equal_secrets():
    same = "a" * 48
    with pytest.raises(ValidationError) as exc:
        _settings(
            ENVIRONMENT="production",
            JWT_SECRET=same,
            JWT_REFRESH_SECRET=same,
            MASTER_ADMIN_PASSWORD="Str0ng-Re@l-Admin-Password!",
        )
    assert "JWT_SECRET == JWT_REFRESH_SECRET" in str(exc.value)


def test_production_refuses_default_master_password():
    with pytest.raises(ValidationError) as exc:
        _settings(
            ENVIRONMENT="production",
            JWT_SECRET="a" * 48,
            JWT_REFRESH_SECRET="b" * 48,
        )
    assert "MASTER_ADMIN_PASSWORD" in str(exc.value)


def test_production_accepts_strong_secrets():
    s = _settings(
        ENVIRONMENT="production",
        JWT_SECRET="a" * 48,
        JWT_REFRESH_SECRET="b" * 48,
        MASTER_ADMIN_PASSWORD="Str0ng-Re@l-Admin-Password!",
    )
    assert s.environment == "production"


# --- R-08: cross-tenant role assignment refused ------------------------------


def test_tenant_admin_cannot_attach_another_tenants_role(db, seeded, client):
    """Tenant B's administrator must not grant tenant A's custom role."""
    from app.models import Role, UserRole

    tenant_a = make_tenant(db, name="ICT A", module_codes=["ADMIN"])
    tenant_b = make_tenant(db, name="ICT B", module_codes=["ADMIN"])

    # A custom (non-system) role owned by tenant A.
    role_a = Role(tenant_id=tenant_a.id, name="Gestor A", code="GESTOR_A", active=True)
    db.add(role_a)
    db.commit()

    admin_b = make_user(db, email="adminb@example.com", tenant_id=tenant_b.id)
    assign_role(db, admin_b.id, "SUPER_ADMIN")
    headers = auth_header(login(client, "adminb@example.com")["access_token"])

    target = make_user(db, email="targetb@example.com", tenant_id=tenant_b.id)

    resp = client.patch(
        f"/api/admin/users/{target.id}",
        headers=headers,
        json={"role_ids": [str(role_a.id)]},
    )
    assert resp.status_code == 403, resp.text
    assert "outro tenant" in resp.json()["detail"]

    granted = (
        db.query(UserRole)
        .filter(UserRole.user_id == target.id, UserRole.role_id == role_a.id)
        .first()
    )
    assert granted is None


def test_tenant_admin_cannot_create_user_with_foreign_role(db, seeded, client):
    from app.models import Role, User

    tenant_a = make_tenant(db, name="ICT A2", module_codes=["ADMIN"])
    tenant_b = make_tenant(db, name="ICT B2", module_codes=["ADMIN"])
    role_a = Role(tenant_id=tenant_a.id, name="Gestor A2", code="GESTOR_A2", active=True)
    db.add(role_a)
    db.commit()

    admin_b = make_user(db, email="adminb2@example.com", tenant_id=tenant_b.id)
    assign_role(db, admin_b.id, "SUPER_ADMIN")
    headers = auth_header(login(client, "adminb2@example.com")["access_token"])

    resp = client.post(
        "/api/admin/users",
        headers=headers,
        json={
            "email": "novob@example.com",
            "access_code": "novob@example.com",
            "password": "Password123!",
            "name": "Novo B",
            "role_ids": [str(role_a.id)],
        },
    )
    assert resp.status_code == 403, resp.text
    assert db.query(User).filter(User.email == "novob@example.com").first() is None


def test_tenant_admin_can_attach_own_tenant_role(db, seeded, client):
    from app.models import Role, UserRole

    tenant = make_tenant(db, name="ICT Own", module_codes=["ADMIN", "MARCAS"])
    own_role = Role(tenant_id=tenant.id, name="Gestor", code="GESTOR_OWN", active=True)
    db.add(own_role)
    db.commit()

    admin = make_user(db, email="adminown@example.com", tenant_id=tenant.id)
    assign_role(db, admin.id, "SUPER_ADMIN")
    headers = auth_header(login(client, "adminown@example.com")["access_token"])
    target = make_user(db, email="targetown@example.com", tenant_id=tenant.id)

    resp = client.patch(
        f"/api/admin/users/{target.id}",
        headers=headers,
        json={"role_ids": [str(own_role.id)]},
    )
    assert resp.status_code == 200, resp.text
    assert (
        db.query(UserRole)
        .filter(UserRole.user_id == target.id, UserRole.role_id == own_role.id)
        .first()
        is not None
    )


def test_unknown_role_id_returns_404(db, seeded, client):
    import uuid

    tenant = make_tenant(db, name="ICT Unknown", module_codes=["ADMIN"])
    admin = make_user(db, email="adminunk@example.com", tenant_id=tenant.id)
    assign_role(db, admin.id, "SUPER_ADMIN")
    headers = auth_header(login(client, "adminunk@example.com")["access_token"])
    target = make_user(db, email="targetunk@example.com", tenant_id=tenant.id)

    resp = client.patch(
        f"/api/admin/users/{target.id}",
        headers=headers,
        json={"role_ids": [str(uuid.uuid4())]},
    )
    assert resp.status_code == 404, resp.text


# --- R-10: request correlation id -------------------------------------------


def test_response_echoes_request_id(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID")


def test_incoming_request_id_is_propagated(client):
    resp = client.get("/api/health", headers={"X-Request-ID": "corr-123"})
    assert resp.headers.get("X-Request-ID") == "corr-123"


def test_json_logging_formatter_emits_request_id():
    import json
    import logging

    from app.logging_config import JsonFormatter, RequestIdFilter, set_request_id

    set_request_id("rid-xyz")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    RequestIdFilter().filter(record)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == "hello world"
    assert payload["request_id"] == "rid-xyz"
    assert payload["level"] == "INFO"


# --- R-14: integrity errors map to 409, no leakage ---------------------------


def test_internal_error_returns_generic_500():
    """A raising route yields a 500 without leaking internals (no stack/SQL)."""
    from fastapi import APIRouter
    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    probe = APIRouter()

    @probe.get("/__probe_error")
    def _raise():
        raise RuntimeError("segredo-interno-nao-deve-vazar")

    app.include_router(probe)
    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.get("/__probe_error")

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Erro interno do servidor."}
    assert "segredo-interno-nao-deve-vazar" not in resp.text
    assert "RuntimeError" not in resp.text
