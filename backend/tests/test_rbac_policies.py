"""Tests for the advanced RBAC model (section 3).

Covers the three grant paths that lead to a Resource + AccessPolicy:

1. ``UserPolicy``   — direct User → Resource (ALLOWED/DENIED, optional scope);
2. ``GroupPolicy``  — via ``UserGroup`` membership;
3. ``RolePolicy``   — via the user's roles (strictly ALLOWED).

Also covers the Module → Resource catalog and the admin API that manages them.
"""

from __future__ import annotations

from app.models import (
    Group,
    GroupPolicy,
    Resource,
    UserGroup,
    UserPolicy,
)
from app.rbac import build_access_context
from tests.conftest import assign_role, auth_header, login, make_tenant, make_user


def _resource(db, code: str) -> Resource:
    return db.query(Resource).filter(Resource.code == code).one()


def test_resources_seeded_with_module_link(db, seeded):
    resources = db.query(Resource).all()
    assert len(resources) >= 20
    marcas = _resource(db, "marcas:user")
    assert marcas.module.code == "MARCAS"
    assert marcas.control_company_unity is True
    # A resource whose module does NOT control scope stays False.
    assert _resource(db, "core:user").control_company_unity is False


def test_user_policy_grants_resource_directly(db, seeded):
    tenant = make_tenant(db, name="UP", module_codes=["MARCAS"])
    user = make_user(db, email="up@example.com", tenant_id=tenant.id)
    db.add(
        UserPolicy(
            user_id=user.id,
            resource_id=_resource(db, "marcas:user").id,
            tenant_id=tenant.id,
            decision="ALLOWED",
        )
    )
    db.commit()

    ctx = build_access_context(db, user)
    assert ctx.has_resource("marcas:user")


def test_user_policy_denied_wins_over_role(db, seeded):
    """An explicit DENIED removes a resource even when a role grants it."""
    tenant = make_tenant(db, name="Deny", module_codes=["MARCAS"])
    user = make_user(db, email="deny@example.com", tenant_id=tenant.id)
    assign_role(db, user.id, "MARCAS_VIEW")  # grants marcas:user
    db.add(
        UserPolicy(
            user_id=user.id,
            resource_id=_resource(db, "marcas:user").id,
            tenant_id=tenant.id,
            decision="DENIED",
        )
    )
    db.commit()

    ctx = build_access_context(db, user)
    assert not ctx.has_resource("marcas:user")


def test_group_policy_flows_through_membership(db, seeded):
    tenant = make_tenant(db, name="Grp", module_codes=["MARCAS"])
    user = make_user(db, email="grp@example.com", tenant_id=tenant.id)
    group = Group(tenant_id=tenant.id, code="EQUIPE_MARCAS", name="Equipe Marcas")
    db.add(group)
    db.flush()
    db.add(UserGroup(user_id=user.id, group_id=group.id))
    db.add(
        GroupPolicy(
            group_id=group.id,
            resource_id=_resource(db, "marcas:monitor").id,
            decision="ALLOWED",
        )
    )
    db.commit()

    ctx = build_access_context(db, user)
    assert ctx.has_resource("marcas:monitor")


def test_inactive_group_grants_nothing(db, seeded):
    tenant = make_tenant(db, name="InactiveGrp", module_codes=["MARCAS"])
    user = make_user(db, email="ig@example.com", tenant_id=tenant.id)
    group = Group(tenant_id=tenant.id, code="OFF", name="Off", active=False)
    db.add(group)
    db.flush()
    db.add(UserGroup(user_id=user.id, group_id=group.id))
    db.add(
        GroupPolicy(
            group_id=group.id,
            resource_id=_resource(db, "marcas:monitor").id,
            decision="ALLOWED",
        )
    )
    db.commit()

    ctx = build_access_context(db, user)
    assert not ctx.has_resource("marcas:monitor")


def test_role_policy_grants_resource(db, seeded):
    tenant = make_tenant(db, name="RP", module_codes=["MARCAS"])
    user = make_user(db, email="rp@example.com", tenant_id=tenant.id)
    assign_role(db, user.id, "MARCAS_VIEW")

    ctx = build_access_context(db, user)
    # MARCAS_VIEW maps to the ``marcas:user`` resource via RolePolicy.
    assert ctx.has_resource("marcas:user")
    assert not ctx.has_resource("marcas:monitor")


def test_company_unity_scope_is_resolved(db, seeded):
    """A UserPolicy scoped to a company surfaces in scoped_resources."""
    from tests.conftest import make_company

    tenant = make_tenant(db, name="Scoped", module_codes=["MARCAS"])
    company = make_company(db, tenant_id=tenant.id, name="Filial X")
    user = make_user(db, email="scope@example.com", tenant_id=tenant.id)
    db.add(
        UserPolicy(
            user_id=user.id,
            resource_id=_resource(db, "marcas:user").id,
            tenant_id=tenant.id,
            company_id=company.id,
            decision="ALLOWED",
        )
    )
    db.commit()

    ctx = build_access_context(db, user)
    assert ctx.has_resource("marcas:user")
    assert company.id in ctx.scoped_resources["marcas:user"]["company_id"]
    assert company.id in ctx.companies


def test_master_admin_gets_all_resources(db, seeded, client):
    token = login(client, "master@intelliinpi.com.br", "ChangeMe_MasterAdmin_123!")[
        "access_token"
    ]
    me = client.get("/api/auth/me", headers=auth_header(token)).json()
    assert "marcas:user" in me["resources"]
    assert "accesscontrol:admin" in me["resources"]


def test_admin_can_list_resources_and_create_group(db, seeded, client):
    tenant = make_tenant(db, name="ACL", module_codes=["ADMIN"])
    admin = make_user(db, email="acl@example.com", tenant_id=tenant.id)
    assign_role(db, admin.id, "SUPER_ADMIN")
    headers = auth_header(login(client, "acl@example.com")["access_token"])

    res = client.get("/api/admin/resources", headers=headers)
    assert res.status_code == 200, res.text
    codes = {r["code"] for r in res.json()}
    assert "marcas:user" in codes and "actionplan:user" in codes

    created = client.post(
        "/api/admin/groups",
        headers=headers,
        json={"code": "EQUIPE", "name": "Equipe"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["tenant_id"] == str(tenant.id)

    listed = client.get("/api/admin/groups", headers=headers).json()
    assert any(g["code"] == "EQUIPE" for g in listed)


def test_user_policy_api_end_to_end(db, seeded, client):
    tenant = make_tenant(db, name="UPApi", module_codes=["ADMIN", "MARCAS"])
    admin = make_user(db, email="upa@example.com", tenant_id=tenant.id)
    assign_role(db, admin.id, "SUPER_ADMIN")
    target = make_user(db, email="target@example.com", tenant_id=tenant.id)
    headers = auth_header(login(client, "upa@example.com")["access_token"])

    resource_id = str(_resource(db, "marcas:monitor").id)
    created = client.post(
        "/api/admin/user-policies",
        headers=headers,
        json={
            "user_id": str(target.id),
            "resource_id": resource_id,
            "decision": "ALLOWED",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["resource_code"] == "marcas:monitor"

    # Effective access diagnostics expose the granted resource.
    eff = client.get(
        f"/api/admin/users/{target.id}/effective-access", headers=headers
    )
    assert eff.status_code == 200, eff.text
    assert "marcas:monitor" in eff.json()["resources"]

    # Deleting the policy revokes it.
    pid = created.json()["id"]
    deleted = client.delete(f"/api/admin/user-policies/{pid}", headers=headers)
    assert deleted.status_code == 200
    eff2 = client.get(
        f"/api/admin/users/{target.id}/effective-access", headers=headers
    ).json()
    assert "marcas:monitor" not in eff2["resources"]


def test_menu_chain_links_items_to_resources(db, seeded):
    """Menu → MenuItem → MenuItemResource → Resource wiring."""
    from app.models import Menu, MenuItem, MenuItemResource

    menu = Menu(code="MAIN", name="Principal")
    db.add(menu)
    db.flush()
    item = MenuItem(menu_id=menu.id, label="Marcas", route="/marcas", sort_order=1)
    db.add(item)
    db.flush()
    db.add(
        MenuItemResource(
            menu_item_id=item.id, resource_id=_resource(db, "marcas:user").id
        )
    )
    db.commit()
    db.refresh(item)

    assert item.item_resources[0].resource.code == "marcas:user"