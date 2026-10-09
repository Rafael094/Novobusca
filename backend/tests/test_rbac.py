"""RBAC resolution tests: roles, modules and permission unions."""

from __future__ import annotations

from tests.conftest import assign_role, auth_header, login, make_tenant, make_user


def test_master_admin_has_all_permissions(db, seeded, client):
    from app.constants import ALL_PERMISSION_CODES

    tokens = login(client, "master@intelliinpi.com.br", "ChangeMe_MasterAdmin_123!")
    me = client.get("/api/auth/me", headers=auth_header(tokens["access_token"])).json()
    assert set(ALL_PERMISSION_CODES).issubset(set(me["permissions"]))


def test_role_grants_expected_permissions(db, seeded, client):
    tenant = make_tenant(db, name="Marcas Tenant", module_codes=["MARCAS"])
    user = make_user(db, email="viewer@example.com", tenant_id=tenant.id)
    assign_role(db, user.id, "MARCAS_VIEW")

    token = login(client, "viewer@example.com")["access_token"]
    me = client.get("/api/auth/me", headers=auth_header(token)).json()
    assert "MARCAS_VIEW" in me["permissions"]
    assert "MARCAS_SEARCH" in me["permissions"]
    # Export is not part of the viewer role.
    assert "MARCAS_EXPORT" not in me["permissions"]


def test_union_of_multiple_roles(db, seeded, client):
    tenant = make_tenant(db, name="Multi", module_codes=["MARCAS", "PATENTES"])
    user = make_user(db, email="multi@example.com", tenant_id=tenant.id)
    assign_role(db, user.id, "MARCAS_VIEW")
    assign_role(db, user.id, "PATENTES_VIEW")

    token = login(client, "multi@example.com")["access_token"]
    me = client.get("/api/auth/me", headers=auth_header(token)).json()
    assert {"MARCAS_VIEW", "PATENTES_VIEW"}.issubset(set(me["permissions"]))


def test_role_with_disabled_module_grants_nothing(db, seeded, client):
    # Tenant does NOT have the MARCAS module enabled.
    tenant = make_tenant(db, name="No Marcas", module_codes=["ADMIN"])
    user = make_user(db, email="noMarcas@example.com", tenant_id=tenant.id)
    assign_role(db, user.id, "MARCAS_VIEW")

    token = login(client, "noMarcas@example.com")["access_token"]
    me = client.get("/api/auth/me", headers=auth_header(token)).json()
    assert "MARCAS_VIEW" not in me["permissions"]


def test_admin_can_list_roles_and_modules(db, seeded, client):
    tenant = make_tenant(db, name="Admin T", module_codes=["ADMIN"])
    admin = make_user(db, email="tadmin@example.com", tenant_id=tenant.id)
    assign_role(db, admin.id, "TENANT_ADMIN")
    token = login(client, "tadmin@example.com")["access_token"]

    roles = client.get("/api/admin/roles", headers=auth_header(token))
    assert roles.status_code == 200, roles.text
    assert any(r["code"] == "TENANT_ADMIN" for r in roles.json())

    modules = client.get("/api/admin/modules", headers=auth_header(token))
    assert modules.status_code == 200, modules.text
    assert len(modules.json()) >= 9
