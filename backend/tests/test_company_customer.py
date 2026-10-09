"""Company / Unity / Customer / Person model tests.

Proves the tenant-scoped CRM entities:
  * persist with all their fields and relationships;
  * enforce tenant isolation through ``tenant_id`` (the same guarantee used
    everywhere else in the platform);
  * are soft-deletable.
"""

from __future__ import annotations

from app.models import Company, Customer, Person, Unity
from tests.conftest import make_company, make_tenant, make_unity, make_user


def test_company_belongs_to_tenant(db, seeded):
    tenant = make_tenant(db, name="Empresa Tenant", module_codes=["CLIENTES"])
    company = Company(
        tenant_id=tenant.id,
        company_name="Acme",
        social_reason="Acme Indústria LTDA",
        external_id="ERP-001",
        file_document="docs/acme-contrato-social.pdf",
        cnpj="12.345.678/0001-90",
    )
    db.add(company)
    db.commit()
    db.refresh(company)

    assert company.id is not None
    assert company.tenant_id == tenant.id
    assert company.company_name == "Acme"
    assert company.social_reason == "Acme Indústria LTDA"
    assert company.external_id == "ERP-001"
    assert company.file_document == "docs/acme-contrato-social.pdf"
    assert company.active is True


def test_unity_belongs_to_company(db, seeded):
    """A ``Unity`` (branch) is linked to ``Company`` and carries its own fields."""
    tenant = make_tenant(db, name="Unity Tenant", module_codes=["CLIENTES"])
    company = make_company(db, tenant_id=tenant.id, name="Rede Center")
    unity = Unity(
        tenant_id=tenant.id,
        company_id=company.id,
        name="Center Norte",
        social_reason="Rede Center Norte LTDA",
        cnpj="22.333.444/0001-55",
        matriz_type="MATRIZ",
        cnes="1234567",
        sanitary_license="VISA-2026-001",
        opening_hours="08:00-22:00",
    )
    db.add(unity)
    db.commit()
    db.refresh(unity)

    assert unity.company_id == company.id
    assert unity.matriz_type == "MATRIZ"
    assert unity.cnes == "1234567"
    assert unity.sanitary_license == "VISA-2026-001"
    assert unity.opening_hours == "08:00-22:00"
    # Company → Unity relationship is wired both ways.
    assert unity in company.unities


def test_customer_links_company_unity_and_person(db, seeded):
    tenant = make_tenant(db, name="CRM Tenant", module_codes=["CLIENTES"])
    company = make_company(db, tenant_id=tenant.id, name="Fornecedor S/A")
    unity = make_unity(db, tenant_id=tenant.id, company_id=company.id, name="Filial Sul")
    person = Person(tenant_id=tenant.id, name="João Contato", email="joao@x.com")
    db.add(person)
    db.flush()

    customer = Customer(
        tenant_id=tenant.id,
        company_id=company.id,
        unity_id=unity.id,
        person_id=person.id,
        code="CLI-001",
        name="Cliente Final",
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)

    assert customer.company_id == company.id
    assert customer.unity_id == unity.id
    assert customer.person_id == person.id
    assert customer.company.company_name == "Fornecedor S/A"
    assert customer.unity.name == "Filial Sul"
    assert customer.person.name == "João Contato"


def test_person_carries_cadastral_data_and_links_user(db, seeded):
    """The Person holds the cadastral data; the User holds only credentials."""
    tenant = make_tenant(db, name="People Tenant", module_codes=["CLIENTES"])
    user = make_user(db, email="linked@example.com", tenant_id=tenant.id)
    person = user.person

    assert person is not None
    assert user.person_id == person.id
    # CPF / CellPhone / Address / Responsibility live on the Person.
    person.cpf = "123.456.789-00"
    person.cell_phone = "+55 11 99999-0000"
    person.address_line = "Av. Paulista"
    person.address_number = "1000"
    person.state = "SP"
    person.responsibility = "Diretor"
    db.commit()
    db.refresh(person)

    assert person.cpf == "123.456.789-00"
    assert person.cell_phone == "+55 11 99999-0000"
    assert person.responsibility == "Diretor"
    # The user has no ``name`` column of its own — it is derived from Person.
    assert user.name == "linked"


def test_entities_are_tenant_scoped(db, seeded):
    """Data from one tenant must never mix with another tenant's rows."""
    tenant_a = make_tenant(db, name="Iso A", module_codes=["CLIENTES"])
    tenant_b = make_tenant(db, name="Iso B", module_codes=["CLIENTES"])

    db.add(Company(tenant_id=tenant_a.id, company_name="A LTDA"))
    db.add(Company(tenant_id=tenant_b.id, company_name="B LTDA"))
    db.commit()

    a_companies = (
        db.query(Company).filter(Company.tenant_id == tenant_a.id).all()
    )
    b_companies = (
        db.query(Company).filter(Company.tenant_id == tenant_b.id).all()
    )
    assert [c.company_name for c in a_companies] == ["A LTDA"]
    assert [c.company_name for c in b_companies] == ["B LTDA"]


def test_company_soft_delete(db, seeded):
    tenant = make_tenant(db, name="SoftDel Tenant", module_codes=["CLIENTES"])
    company = Company(tenant_id=tenant.id, company_name="Some LTDA")
    db.add(company)
    db.commit()

    from datetime import datetime, timezone

    company.deleted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(company)
    assert company.deleted_at is not None


def test_seed_creates_default_tenant_and_links_admin(db, seeded_full):
    from app.constants import ALL_PERMISSION_CODES
    from app.models import Role, RolePermission, TenantModule, UserRole

    tenant = seeded_full["tenant"]
    master = seeded_full["master"]

    assert tenant.social_reason  # default tenant created
    assert master.tenant_id == tenant.id  # admin linked to default tenant
    assert master.is_master_admin is True  # cross-tenant reach retained

    # Every module enabled for the default tenant.
    from app.models import Module

    module_count = db.query(Module).filter(Module.active.is_(True)).count()
    enabled = (
        db.query(TenantModule).filter(TenantModule.tenant_id == tenant.id).count()
    )
    assert enabled == module_count

    # SUPER_ADMIN role holds every permission and is granted to the admin.
    role = db.query(Role).filter(Role.code == "SUPER_ADMIN").one()
    perm_codes = {
        rp.permission_id
        for rp in db.query(RolePermission).filter(RolePermission.role_id == role.id)
    }
    assert len(perm_codes) == len(ALL_PERMISSION_CODES)
    granted = (
        db.query(UserRole)
        .filter(UserRole.user_id == master.id, UserRole.role_id == role.id)
        .count()
    )
    assert granted == 1


def test_default_tenant_seed_is_idempotent(db, seeded_full):
    from app import seed
    from app.models import Tenant

    modules = seeded_full["modules"]
    seed.seed_default_tenant(db, modules)
    seed.seed_default_admin_access(
        db, seeded_full["tenant"], seeded_full["master"], seeded_full["permissions"]
    )
    db.commit()

    # Only one default tenant must exist after re-running.
    assert db.query(Tenant).count() == 1
