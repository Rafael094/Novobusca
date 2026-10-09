"""Tenant-scoped CRM endpoints: companies, customers and people.

Tenant isolation is enforced here (never trusted from the client): the tenant is
always derived from the authenticated user's access context. A master admin
operates across tenants and may filter by ``tenant_id``; every other user is
constrained to their own tenant.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models import Company, Customer, Person, Unity
from app.rbac import AccessContext
from app.schemas.company import (
    CompanyCreate,
    CompanyOut,
    CompanyUpdate,
    CustomerCreate,
    CustomerOut,
    CustomerUpdate,
    PaginatedCompanies,
    PaginatedCustomers,
    PaginatedPeople,
    PaginatedUnities,
    PersonCreate,
    PersonOut,
    PersonUpdate,
    UnityCreate,
    UnityOut,
    UnityUpdate,
)

router = APIRouter(prefix="/clientes", tags=["clientes"])


# --- Helpers ----------------------------------------------------------------
def _scoped_tenant(ctx: AccessContext, requested: uuid.UUID | None) -> uuid.UUID | None:
    """Return the tenant to filter by (None => all, master admin only)."""
    if ctx.user.is_master_admin:
        return requested
    if requested is not None and requested != ctx.user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é permitido acessar dados de outro tenant",
        )
    return ctx.user.tenant_id


def _assert_tenant(ctx: AccessContext, tenant_id: uuid.UUID) -> None:
    if ctx.user.is_master_admin:
        return
    if tenant_id != ctx.user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: registro de outro tenant",
        )


def _write_tenant(ctx: AccessContext, requested: uuid.UUID | None) -> uuid.UUID:
    """Tenant to assign on create; must be the caller's tenant when not master."""
    if ctx.user.is_master_admin:
        tenant = requested or ctx.user.tenant_id
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tenant_id é obrigatório para o Master Admin",
            )
        return tenant
    if requested is not None and requested != ctx.user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é permitido criar registros em outro tenant",
        )
    if ctx.user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário sem tenant"
        )
    return ctx.user.tenant_id


def _paginate(page: int, page_size: int, total: int) -> dict:
    return {"page": page, "page_size": page_size, "total": int(total)}


# --- Companies --------------------------------------------------------------
@router.get("/companies", response_model=PaginatedCompanies)
def list_companies(
    q: str | None = None,
    active: bool | None = None,
    tenant_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("COMPANY_VIEW")),
) -> PaginatedCompanies:
    scope = _scoped_tenant(ctx, tenant_id)
    conditions = [Company.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(Company.tenant_id == scope)
    if q:
        like = f"%{q}%"
        conditions.append(
            or_(
                Company.company_name.ilike(like),
                Company.social_reason.ilike(like),
                Company.external_id.ilike(like),
                Company.cnpj.ilike(like),
            )
        )
    if active is not None:
        conditions.append(Company.active.is_(active))

    total = db.execute(select(func.count(Company.id)).where(*conditions)).scalar_one()
    rows = (
        db.execute(
            select(Company)
            .where(*conditions)
            .order_by(Company.company_name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    ids = [c.id for c in rows]
    counts: dict[uuid.UUID, int] = {}
    unity_counts: dict[uuid.UUID, int] = {}
    if ids:
        for cid, cnt in db.execute(
            select(Customer.company_id, func.count(Customer.id))
            .where(Customer.company_id.in_(ids), Customer.deleted_at.is_(None))
            .group_by(Customer.company_id)
        ):
            counts[cid] = int(cnt)
        for cid, cnt in db.execute(
            select(Unity.company_id, func.count(Unity.id))
            .where(Unity.company_id.in_(ids), Unity.deleted_at.is_(None))
            .group_by(Unity.company_id)
        ):
            unity_counts[cid] = int(cnt)

    items = []
    for c in rows:
        out = CompanyOut.model_validate(c)
        out.customer_count = counts.get(c.id, 0)
        out.unity_count = unity_counts.get(c.id, 0)
        items.append(out)
    return PaginatedCompanies(pagination=_paginate(page, page_size, total), items=items)


@router.post(
    "/companies", response_model=CompanyOut, status_code=status.HTTP_201_CREATED
)
def create_company(
    payload: CompanyCreate,
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("COMPANY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> CompanyOut:
    tenant = _write_tenant(ctx, tenant_id)
    data = payload.model_dump()
    active = data.pop("active", True)
    if data.get("external_id"):
        exists = db.execute(
            select(Company).where(
                Company.tenant_id == tenant,
                Company.external_id == data["external_id"],
            )
        ).scalar_one_or_none()
        if exists is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Já existe uma empresa com este ExternalId neste tenant",
            )
    company = Company(tenant_id=tenant, active=active, **data)
    db.add(company)
    db.commit()
    db.refresh(company)
    record_audit(
        db,
        action="COMPANY_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="company",
        resource_id=str(company.id),
        meta={"company_name": company.company_name},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return CompanyOut.model_validate(company)


@router.get("/companies/{company_id}", response_model=CompanyOut)
def get_company(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("COMPANY_VIEW")),
) -> CompanyOut:
    company = db.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    _assert_tenant(ctx, company.tenant_id)
    out = CompanyOut.model_validate(company)
    out.customer_count = int(
        db.execute(
            select(func.count(Customer.id)).where(
                Customer.company_id == company.id, Customer.deleted_at.is_(None)
            )
        ).scalar_one()
    )
    return out


@router.patch("/companies/{company_id}", response_model=CompanyOut)
def update_company(
    company_id: uuid.UUID,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("COMPANY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> CompanyOut:
    company = db.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    _assert_tenant(ctx, company.tenant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(company, field, value)
    db.commit()
    db.refresh(company)
    record_audit(
        db,
        action="COMPANY_UPDATE",
        tenant_id=company.tenant_id,
        user_id=ctx.user.id,
        resource="company",
        resource_id=str(company.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return CompanyOut.model_validate(company)


@router.delete("/companies/{company_id}")
def delete_company(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("COMPANY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    company = db.get(Company, company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    _assert_tenant(ctx, company.tenant_id)
    company.active = False
    company.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(
        db,
        action="COMPANY_SOFT_DELETE",
        tenant_id=company.tenant_id,
        user_id=ctx.user.id,
        resource="company",
        resource_id=str(company.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Empresa desativada (soft delete)."}


# --- Unities (filiais / unidades) --------------------------------------------
@router.get("/unities", response_model=PaginatedUnities)
def list_unities(
    q: str | None = None,
    company_id: uuid.UUID | None = None,
    active: bool | None = None,
    tenant_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("UNITY_VIEW")),
) -> PaginatedUnities:
    scope = _scoped_tenant(ctx, tenant_id)
    conditions = [Unity.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(Unity.tenant_id == scope)
    if company_id is not None:
        conditions.append(Unity.company_id == company_id)
    if q:
        like = f"%{q}%"
        conditions.append(
            or_(
                Unity.name.ilike(like),
                Unity.social_reason.ilike(like),
                Unity.cnpj.ilike(like),
            )
        )
    if active is not None:
        conditions.append(Unity.active.is_(active))

    total = db.execute(select(func.count(Unity.id)).where(*conditions)).scalar_one()
    rows = (
        db.execute(
            select(Unity)
            .where(*conditions)
            .order_by(Unity.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    items = []
    for u in rows:
        out = UnityOut.model_validate(u)
        out.company_name = u.company.company_name if u.company else None
        items.append(out)
    return PaginatedUnities(
        pagination=_paginate(page, page_size, total), items=items
    )


@router.post("/unities", response_model=UnityOut, status_code=status.HTTP_201_CREATED)
def create_unity(
    payload: UnityCreate,
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("UNITY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> UnityOut:
    tenant = _write_tenant(ctx, tenant_id)
    company = db.get(Company, payload.company_id)
    if company is None or company.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    _assert_tenant(ctx, company.tenant_id)
    data = payload.model_dump()
    data.pop("company_id", None)
    active = data.pop("active", True)
    unity = Unity(tenant_id=tenant, company_id=payload.company_id, active=active, **data)
    db.add(unity)
    db.commit()
    db.refresh(unity)
    record_audit(
        db,
        action="UNITY_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="unity",
        resource_id=str(unity.id),
        meta={"name": unity.name, "company_id": str(payload.company_id)},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    out = UnityOut.model_validate(unity)
    out.company_name = company.company_name
    return out


@router.get("/unities/{unity_id}", response_model=UnityOut)
def get_unity(
    unity_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("UNITY_VIEW")),
) -> UnityOut:
    unity = db.get(Unity, unity_id)
    if unity is None or unity.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")
    _assert_tenant(ctx, unity.tenant_id)
    out = UnityOut.model_validate(unity)
    out.company_name = unity.company.company_name if unity.company else None
    return out


@router.patch("/unities/{unity_id}", response_model=UnityOut)
def update_unity(
    unity_id: uuid.UUID,
    payload: UnityUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("UNITY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> UnityOut:
    unity = db.get(Unity, unity_id)
    if unity is None or unity.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")
    _assert_tenant(ctx, unity.tenant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(unity, field, value)
    db.commit()
    db.refresh(unity)
    record_audit(
        db,
        action="UNITY_UPDATE",
        tenant_id=unity.tenant_id,
        user_id=ctx.user.id,
        resource="unity",
        resource_id=str(unity.id),
        meta=payload.model_dump(exclude_none=True),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    out = UnityOut.model_validate(unity)
    out.company_name = unity.company.company_name if unity.company else None
    return out


@router.delete("/unities/{unity_id}")
def delete_unity(
    unity_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("UNITY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    unity = db.get(Unity, unity_id)
    if unity is None or unity.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Unidade não encontrada")
    _assert_tenant(ctx, unity.tenant_id)
    unity.active = False
    unity.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(
        db,
        action="UNITY_SOFT_DELETE",
        tenant_id=unity.tenant_id,
        user_id=ctx.user.id,
        resource="unity",
        resource_id=str(unity.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Unidade desativada (soft delete)."}



# --- Customers --------------------------------------------------------------
def _customer_out(db: Session, customer: Customer) -> CustomerOut:
    out = CustomerOut.model_validate(customer)
    out.company_name = customer.company.company_name if customer.company else None
    out.unity_name = customer.unity.name if customer.unity else None
    out.person_name = customer.person.name if customer.person else None
    return out


@router.get("/customers", response_model=PaginatedCustomers)
def list_customers(
    q: str | None = None,
    active: bool | None = None,
    company_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CUSTOMER_VIEW")),
) -> PaginatedCustomers:
    scope = _scoped_tenant(ctx, tenant_id)
    conditions = [Customer.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(Customer.tenant_id == scope)
    if q:
        like = f"%{q}%"
        conditions.append(
            or_(
                Customer.name.ilike(like),
                Customer.document.ilike(like),
                Customer.code.ilike(like),
            )
        )
    if active is not None:
        conditions.append(Customer.active.is_(active))
    if company_id is not None:
        conditions.append(Customer.company_id == company_id)

    total = db.execute(select(func.count(Customer.id)).where(*conditions)).scalar_one()
    rows = (
        db.execute(
            select(Customer)
            .where(*conditions)
            .order_by(Customer.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedCustomers(
        pagination=_paginate(page, page_size, total),
        items=[_customer_out(db, c) for c in rows],
    )


@router.post(
    "/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED
)
def create_customer(
    payload: CustomerCreate,
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CUSTOMER_MANAGE")),
    meta: dict = Depends(client_meta),
) -> CustomerOut:
    tenant = _write_tenant(ctx, tenant_id)
    data = payload.model_dump()
    active = data.pop("active", True)
    if data.get("company_id"):
        company = db.get(Company, data["company_id"])
        if company is None or company.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Empresa não encontrada")
        _assert_tenant(ctx, company.tenant_id)
    if data.get("person_id"):
        person = db.get(Person, data["person_id"])
        if person is None or person.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Pessoa não encontrada")
        _assert_tenant(ctx, person.tenant_id)
    customer = Customer(tenant_id=tenant, active=active, **data)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    record_audit(
        db,
        action="CUSTOMER_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="customer",
        resource_id=str(customer.id),
        meta={"name": customer.name},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _customer_out(db, customer)


@router.get("/customers/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CUSTOMER_VIEW")),
) -> CustomerOut:
    customer = db.get(Customer, customer_id)
    if customer is None or customer.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    _assert_tenant(ctx, customer.tenant_id)
    return _customer_out(db, customer)


@router.patch("/customers/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: uuid.UUID,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CUSTOMER_MANAGE")),
    meta: dict = Depends(client_meta),
) -> CustomerOut:
    customer = db.get(Customer, customer_id)
    if customer is None or customer.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    _assert_tenant(ctx, customer.tenant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(customer, field, value)
    db.commit()
    db.refresh(customer)
    record_audit(
        db,
        action="CUSTOMER_UPDATE",
        tenant_id=customer.tenant_id,
        user_id=ctx.user.id,
        resource="customer",
        resource_id=str(customer.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _customer_out(db, customer)


@router.delete("/customers/{customer_id}")
def delete_customer(
    customer_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CUSTOMER_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    customer = db.get(Customer, customer_id)
    if customer is None or customer.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    _assert_tenant(ctx, customer.tenant_id)
    customer.active = False
    customer.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(
        db,
        action="CUSTOMER_SOFT_DELETE",
        tenant_id=customer.tenant_id,
        user_id=ctx.user.id,
        resource="customer",
        resource_id=str(customer.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Cliente desativado (soft delete)."}

# --- People -----------------------------------------------------------------
@router.get("/people", response_model=PaginatedPeople)
def list_people(
    q: str | None = None,
    active: bool | None = None,
    tenant_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("PERSON_VIEW")),
) -> PaginatedPeople:
    scope = _scoped_tenant(ctx, tenant_id)
    conditions = [Person.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(Person.tenant_id == scope)
    if q:
        like = f"%{q}%"
        conditions.append(or_(Person.name.ilike(like), Person.cpf.ilike(like)))
    if active is not None:
        conditions.append(Person.active.is_(active))

    total = db.execute(select(func.count(Person.id)).where(*conditions)).scalar_one()
    rows = (
        db.execute(
            select(Person)
            .where(*conditions)
            .order_by(Person.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedPeople(
        pagination=_paginate(page, page_size, total),
        items=[PersonOut.model_validate(p) for p in rows],
    )


@router.post(
    "/people", response_model=PersonOut, status_code=status.HTTP_201_CREATED
)
def create_person(
    payload: PersonCreate,
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("PERSON_MANAGE")),
    meta: dict = Depends(client_meta),
) -> PersonOut:
    tenant = _write_tenant(ctx, tenant_id)
    data = payload.model_dump()
    active = data.pop("active", True)
    person = Person(tenant_id=tenant, active=active, **data)
    db.add(person)
    db.commit()
    db.refresh(person)
    record_audit(
        db,
        action="PERSON_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="person",
        resource_id=str(person.id),
        meta={"name": person.name},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return PersonOut.model_validate(person)


@router.get("/people/{person_id}", response_model=PersonOut)
def get_person(
    person_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("PERSON_VIEW")),
) -> PersonOut:
    person = db.get(Person, person_id)
    if person is None or person.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada")
    _assert_tenant(ctx, person.tenant_id)
    return PersonOut.model_validate(person)


@router.patch("/people/{person_id}", response_model=PersonOut)
def update_person(
    person_id: uuid.UUID,
    payload: PersonUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("PERSON_MANAGE")),
    meta: dict = Depends(client_meta),
) -> PersonOut:
    person = db.get(Person, person_id)
    if person is None or person.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada")
    _assert_tenant(ctx, person.tenant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(person, field, value)
    db.commit()
    db.refresh(person)
    record_audit(
        db,
        action="PERSON_UPDATE",
        tenant_id=person.tenant_id,
        user_id=ctx.user.id,
        resource="person",
        resource_id=str(person.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return PersonOut.model_validate(person)


@router.delete("/people/{person_id}")
def delete_person(
    person_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("PERSON_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    person = db.get(Person, person_id)
    if person is None or person.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Pessoa não encontrada")
    _assert_tenant(ctx, person.tenant_id)
    person.active = False
    person.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(
        db,
        action="PERSON_SOFT_DELETE",
        tenant_id=person.tenant_id,
        user_id=ctx.user.id,
        resource="person",
        resource_id=str(person.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Pessoa desativada (soft delete)."}
