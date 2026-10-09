"""API tests for the tenant-scoped CRM (clientes) endpoints.

Covers: permission guards, tenant isolation, CRUD happy paths, soft delete and
pagination. Runs against the real FastAPI app via TestClient.
"""

from __future__ import annotations

from tests.conftest import assign_role, auth_header, login, make_tenant, make_user


def _admin_token(client, db, seeded, *, email: str, tenant_id):
    user = make_user(db, email=email, tenant_id=tenant_id)
    assign_role(db, user.id, "SUPER_ADMIN")
    return auth_header(login(client, email)["access_token"])


def test_companies_require_permission(client, db, seeded):
    # Only CLIENTES enabled -> a plain user without a matching role sees 403.
    tenant = make_tenant(db, name="NoPerm", module_codes=["CLIENTES"])
    make_user(db, email="noperm@example.com", tenant_id=tenant.id)
    token = auth_header(login(client, "noperm@example.com")["access_token"])

    resp = client.get("/api/clientes/companies", headers=token)
    assert resp.status_code == 403


def test_company_crud_and_tenant_scope(client, db, seeded):
    tenant = make_tenant(db, name="CRUD Tenant", module_codes=["ADMIN", "CLIENTES"])
    headers = _admin_token(
        client, db, seeded, email="crud@example.com", tenant_id=tenant.id
    )

    # Create
    resp = client.post(
        "/api/clientes/companies",
        headers=headers,
        json={"company_name": "X LTDA", "external_id": "ERP-X"},
    )
    assert resp.status_code == 201, resp.text
    company_id = resp.json()["id"]
    assert resp.json()["tenant_id"] == str(tenant.id)

    # Duplicate external_id -> 409
    dup = client.post(
        "/api/clientes/companies",
        headers=headers,
        json={"company_name": "Outra", "external_id": "ERP-X"},
    )
    assert dup.status_code == 409

    # List
    listed = client.get("/api/clientes/companies", headers=headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["pagination"]["total"] == 1
    assert body["items"][0]["company_name"] == "X LTDA"

    # Update
    upd = client.patch(
        f"/api/clientes/companies/{company_id}",
        headers=headers,
        json={"social_reason": "X Indústria LTDA"},
    )
    assert upd.status_code == 200
    assert upd.json()["social_reason"] == "X Indústria LTDA"

    # Soft delete
    dele = client.delete(f"/api/clientes/companies/{company_id}", headers=headers)
    assert dele.status_code == 200
    after = client.get("/api/clientes/companies", headers=headers).json()
    assert after["pagination"]["total"] == 0


def test_unity_crud_and_company_link(client, db, seeded):
    """A Unity is created under a Company and exposed with company_name."""
    tenant = make_tenant(db, name="Unity API", module_codes=["ADMIN", "CLIENTES"])
    headers = _admin_token(
        client, db, seeded, email="unity@example.com", tenant_id=tenant.id
    )
    company = client.post(
        "/api/clientes/companies",
        headers=headers,
        json={"company_name": "Rede Filial"},
    ).json()

    created = client.post(
        "/api/clientes/unities",
        headers=headers,
        json={
            "company_id": company["id"],
            "name": "Loja Centro",
            "matriz_type": "FILIAL",
            "cnes": "9876543",
            "opening_hours": "09:00-18:00",
        },
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["company_id"] == company["id"]
    assert body["company_name"] == "Rede Filial"
    assert body["matriz_type"] == "FILIAL"

    listed = client.get(
        f"/api/clientes/unities?company_id={company['id']}", headers=headers
    ).json()
    assert listed["pagination"]["total"] == 1
    assert listed["items"][0]["name"] == "Loja Centro"


def test_customer_linking_via_api(client, db, seeded):
    tenant = make_tenant(db, name="Link Tenant", module_codes=["ADMIN", "CLIENTES"])
    headers = _admin_token(
        client, db, seeded, email="link@example.com", tenant_id=tenant.id
    )

    company = client.post(
        "/api/clientes/companies",
        headers=headers,
        json={"company_name": "Fornecedora S/A"},
    ).json()

    cust = client.post(
        "/api/clientes/customers",
        headers=headers,
        json={"name": "Cliente Final", "company_id": company["id"]},
    )
    assert cust.status_code == 201, cust.text
    assert cust.json()["company_name"] == "Fornecedora S/A"


def test_customers_cannot_cross_tenant(client, db, seeded):
    tenant_a = make_tenant(db, name="IsoA", module_codes=["ADMIN", "CLIENTES"])
    tenant_b = make_tenant(db, name="IsoB", module_codes=["ADMIN", "CLIENTES"])

    headers_a = _admin_token(
        client, db, seeded, email="a@example.com", tenant_id=tenant_a.id
    )
    headers_b = _admin_token(
        client, db, seeded, email="b@example.com", tenant_id=tenant_b.id
    )

    client.post(
        "/api/clientes/companies",
        headers=headers_a,
        json={"company_name": "Só do A"},
    )

    # Tenant B must never see tenant A's companies.
    listed_b = client.get("/api/clientes/companies", headers=headers_b).json()
    assert listed_b["pagination"]["total"] == 0


def test_people_crud(client, db, seeded):
    tenant = make_tenant(db, name="People API", module_codes=["ADMIN", "CLIENTES"])
    headers = _admin_token(
        client, db, seeded, email="people@example.com", tenant_id=tenant.id
    )

    created = client.post(
        "/api/clientes/people",
        headers=headers,
        json={"name": "Maria Silva", "email": "maria@example.com"},
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]

    listed = client.get("/api/clientes/people?q=Maria", headers=headers).json()
    assert listed["pagination"]["total"] == 1
    assert listed["items"][0]["name"] == "Maria Silva"

    assert (
        client.delete(f"/api/clientes/people/{pid}", headers=headers).status_code == 200
    )
