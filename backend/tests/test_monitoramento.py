"""Selective monitoring tests (section 4).

Proves that monitoring is NEVER global or automatic: a marca/patente is watched
only when the current user explicitly enables it, and the flag is per-user and
per-tenant.
"""

from __future__ import annotations

from app.models import Marca, MarcaMonitoramento
from tests.conftest import assign_role, auth_header, login, make_tenant, make_user


def _seed_marca(db, codigo: str = "900000001"):
    marca = Marca(
        codigo_interno=codigo,
        numero_inpi="900000001",
        elemento_nominativo="TESTMON",
    )
    db.add(marca)
    db.commit()
    return marca


def _analista(client, db, *, email: str, tenant_id):
    user = make_user(db, email=email, tenant_id=tenant_id)
    assign_role(db, user.id, "ANALISTA")
    return user, auth_header(login(client, email)["access_token"])


def test_search_does_not_auto_monitor(db, seeded, client):
    """Entering the marcas list must NOT flag anything as monitored."""
    tenant = make_tenant(db, name="MonTenant", module_codes=["MARCAS", "BUSCA"])
    _seed_marca(db, "900000001")
    _user, headers = _analista(client, db, email="mon1@example.com", tenant_id=tenant.id)

    body = client.get("/api/marcas/search?q=TESTMON", headers=headers).json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["monitorada"] is False
    assert body["items"][0]["monitoramento_id"] is None
    # No monitoring row was created as a side effect.
    assert db.query(MarcaMonitoramento).count() == 0


def test_toggle_monitoring_is_selective(db, seeded, client):
    tenant = make_tenant(db, name="MonTenant2", module_codes=["MARCAS", "BUSCA"])
    _seed_marca(db, "900000002")
    _seed_marca(db, "900000003")
    _user, headers = _analista(client, db, email="mon2@example.com", tenant_id=tenant.id)

    # Enable only the first marca.
    on = client.post(
        "/api/marcas/900000002/monitoramento",
        headers=headers,
        json={"active": True},
    )
    assert on.status_code == 200, on.text
    assert on.json()["active"] is True

    body = client.get("/api/marcas/search?q=TESTMON", headers=headers).json()
    by_code = {i["codigo_interno"]: i for i in body["items"]}
    assert by_code["900000002"]["monitorada"] is True
    # The other marca is untouched — monitoring is not global.
    assert by_code["900000003"]["monitorada"] is False


def test_monitoring_is_per_user(db, seeded, client):
    """One user's monitoring must not appear for another user in the tenant."""
    tenant = make_tenant(db, name="MonTenant3", module_codes=["MARCAS", "BUSCA"])
    _seed_marca(db, "900000004")
    _u1, headers1 = _analista(client, db, email="u1@example.com", tenant_id=tenant.id)
    _u2, headers2 = _analista(client, db, email="u2@example.com", tenant_id=tenant.id)

    client.post(
        "/api/marcas/900000004/monitoramento", headers=headers1, json={"active": True}
    )

    body1 = client.get("/api/marcas/search?q=TESTMON", headers=headers1).json()
    body2 = client.get("/api/marcas/search?q=TESTMON", headers=headers2).json()
    assert body1["items"][0]["monitorada"] is True
    assert body2["items"][0]["monitorada"] is False


def test_monitoring_list_and_removal(db, seeded, client):
    tenant = make_tenant(db, name="MonTenant4", module_codes=["MARCAS", "BUSCA"])
    _seed_marca(db, "900000005")
    _user, headers = _analista(client, db, email="mon4@example.com", tenant_id=tenant.id)

    client.post(
        "/api/marcas/900000005/monitoramento", headers=headers, json={"active": True}
    )
    listed = client.get("/api/marcas/monitoramento", headers=headers).json()
    assert listed["pagination"]["total"] == 1
    assert listed["items"][0]["codigo_interno"] == "900000005"

    removed = client.delete("/api/marcas/900000005/monitoramento", headers=headers)
    assert removed.status_code == 200
    assert client.get("/api/marcas/monitoramento", headers=headers).json()[
        "pagination"
    ]["total"] == 0


def test_monitoring_requires_permission(db, seeded, client):
    """A user whose role lacks MARCAS_MONITOR cannot toggle monitoring."""
    tenant = make_tenant(db, name="MonNoPerm", module_codes=["MARCAS"])
    _seed_marca(db, "900000006")
    viewer = make_user(db, email="viewer@example.com", tenant_id=tenant.id)
    assign_role(db, viewer.id, "MARCAS_VIEW")  # view only, no monitor
    headers = auth_header(login(client, "viewer@example.com")["access_token"])

    resp = client.post(
        "/api/marcas/900000006/monitoramento", headers=headers, json={"active": True}
    )
    assert resp.status_code == 403, resp.text


def test_monitoring_list_is_route_not_shadowed_by_path_param(db, seeded, client):
    """`GET /api/patentes/monitoramento` must NOT be captured by `/{codigo}`.

    Regression guard: the literal route has to be declared before the
    ``{codigo_interno}`` path parameter, otherwise FastAPI resolves
    ``/monitoramento`` as a patente code and returns 404 "Patente não encontrada".
    """
    tenant = make_tenant(db, name="MonRoute", module_codes=["PATENTES"])
    user = make_user(db, email="route@example.com", tenant_id=tenant.id)
    assign_role(db, user.id, "PATENTES_VIEW")
    headers = auth_header(login(client, "route@example.com")["access_token"])

    resp = client.get("/api/patentes/monitoramento", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["pagination"]["total"] == 0
    assert resp.json()["items"] == []


def test_monitoring_list_only_returns_own_watch_with_display_fields(db, seeded, client):
    """The user's list shows ONLY their own watched items, enriched for display."""
    tenant = make_tenant(db, name="MonList", module_codes=["MARCAS", "BUSCA"])
    _seed_marca(db, "900000010")
    _seed_marca(db, "900000011")
    _user, headers = _analista(
        client, db, email="list@example.com", tenant_id=tenant.id
    )
    # Also a *different* user in the same tenant watches one marca.
    _other, _ = _analista(
        client, db, email="other@example.com", tenant_id=tenant.id
    )

    # Current user watches only 900000010.
    client.post(
        "/api/marcas/900000010/monitoramento", headers=headers, json={"active": True}
    )
    # The other user watches 900000011 (must not leak into our list).
    other_headers = auth_header(login(client, "other@example.com")["access_token"])
    client.post(
        "/api/marcas/900000011/monitoramento",
        headers=other_headers,
        json={"active": True},
    )

    listed = client.get("/api/marcas/monitoramento", headers=headers).json()
    assert listed["pagination"]["total"] == 1
    item = listed["items"][0]
    assert item["codigo_interno"] == "900000010"
    assert item["tipo"] == "marca"
    # Display fields are joined from the marca row.
    assert item["titulo"] == "TESTMON"
    assert item["numero_inpi"] == "900000001"

    # The other user sees only theirs.
    other_list = client.get(
        "/api/marcas/monitoramento", headers=other_headers
    ).json()
    assert other_list["pagination"]["total"] == 1
    assert other_list["items"][0]["codigo_interno"] == "900000011"


def test_patentes_monitoring_list_and_removal(db, seeded, client):
    """Patentes mirror the marcas watch list, with the title joined."""
    from app.models import Patente, PatenteConteudo

    tenant = make_tenant(db, name="MonPat", module_codes=["PATENTES", "ADMIN"])
    db.add(Patente(codigo_interno="800000001", numero_inpi="BR800000001"))
    db.add(
        PatenteConteudo(
            codigo_interno="800000001",
            numero_inpi="BR800000001",
            titulo="DISPOSITIVO DE TESTE",
        )
    )
    db.commit()
    user = make_user(db, email="patmon@example.com", tenant_id=tenant.id)
    # TENANT_ADMIN includes PATENTES_MONITOR (see constants.ROLES).
    assign_role(db, user.id, "TENANT_ADMIN")
    headers = auth_header(login(client, "patmon@example.com")["access_token"])

    on = client.post(
        "/api/patentes/800000001/monitoramento", headers=headers, json={"active": True}
    )
    assert on.status_code == 200, on.text
    assert on.json()["active"] is True

    listed = client.get("/api/patentes/monitoramento", headers=headers).json()
    assert listed["pagination"]["total"] == 1
    item = listed["items"][0]
    assert item["codigo_interno"] == "800000001"
    assert item["tipo"] == "patente"
    assert item["titulo"] == "DISPOSITIVO DE TESTE"
    assert item["numero_inpi"] == "BR800000001"

    removed = client.delete("/api/patentes/800000001/monitoramento", headers=headers)
    assert removed.status_code == 200
    assert (
        client.get("/api/patentes/monitoramento", headers=headers).json()["pagination"][
            "total"
        ]
        == 0
    )