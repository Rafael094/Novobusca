"""Tenant administration endpoints (master admin only)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models import Module, Tenant, TenantModule, User
from app.rbac import AccessContext
from app.schemas.auth import TenantCreate, TenantOut, TenantUpdate

router = APIRouter(prefix="/tenants")


def _tenant_modules(db: Session, tenant_id: uuid.UUID) -> list[str]:
    return list(
        db.execute(
            select(Module.code)
            .join(TenantModule, TenantModule.module_id == Module.id)
            .where(TenantModule.tenant_id == tenant_id, TenantModule.active.is_(True))
        ).scalars()
    )


def _to_out(db: Session, tenant: Tenant) -> TenantOut:
    user_count = db.execute(
        select(func.count(User.id)).where(
            User.tenant_id == tenant.id, User.deleted_at.is_(None)
        )
    ).scalar_one()
    # ``Tenant.modules`` is a relationship to ``TenantModule`` ORM rows, while
    # ``TenantOut.modules`` is a ``list[str]`` of module *codes*. Populate the
    # scalar fields explicitly (never validate the relationship) and then set
    # the two computed fields below.
    out = TenantOut(
        id=tenant.id,
        social_reason=tenant.social_reason,
        company_name=tenant.company_name,
        cnpj=tenant.cnpj,
        mcp_api_key=tenant.mcp_api_key,
        email=tenant.email,
        phone=tenant.phone,
        active=tenant.active,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        deleted_at=tenant.deleted_at,
    )
    out.modules = _tenant_modules(db, tenant.id)
    out.user_count = int(user_count)
    return out


def _set_modules(db: Session, tenant_id: uuid.UUID, module_codes: list[str]) -> None:
    """Replace the tenant's module set with the given codes."""
    existing = {
        tm.module_id: tm
        for tm in db.execute(
            select(TenantModule).where(TenantModule.tenant_id == tenant_id)
        ).scalars()
    }
    wanted = (
        {
            m.id: m
            for m in db.execute(
                select(Module).where(Module.code.in_(module_codes))
            ).scalars()
        }
        if module_codes
        else {}
    )

    now = datetime.now(timezone.utc)
    for module_id in wanted:
        tm = existing.get(module_id)
        if tm is None:
            db.add(
                TenantModule(
                    tenant_id=tenant_id,
                    module_id=module_id,
                    active=True,
                    enabled_at=now,
                )
            )
        elif not tm.active:
            tm.active = True
            tm.enabled_at = now
            tm.disabled_at = None
    for module_id, tm in existing.items():
        if module_id not in wanted and tm.active:
            tm.active = False
            tm.disabled_at = now


@router.get("", response_model=list[TenantOut])
def list_tenants(
    include_deleted: bool = False,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("TENANT_VIEW")),
) -> list[TenantOut]:
    stmt = select(Tenant).order_by(Tenant.created_at.desc())
    if not include_deleted:
        stmt = stmt.where(Tenant.deleted_at.is_(None))
    tenants = db.execute(stmt).scalars().all()
    return [_to_out(db, t) for t in tenants]


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def create_tenant(
    payload: TenantCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("TENANT_CREATE")),
    meta: dict = Depends(client_meta),
) -> TenantOut:
    tenant = Tenant(
        social_reason=payload.social_reason,
        company_name=payload.company_name,
        cnpj=payload.cnpj,
        email=payload.email,
        phone=payload.phone,
        active=payload.active,
    )
    db.add(tenant)
    db.flush()
    _set_modules(db, tenant.id, payload.module_codes)
    db.commit()
    db.refresh(tenant)
    record_audit(
        db,
        action="TENANT_CREATE",
        tenant_id=tenant.id,
        user_id=ctx.user.id,
        resource="tenant",
        resource_id=str(tenant.id),
        meta={"name": tenant.name, "modules": payload.module_codes},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _to_out(db, tenant)


@router.get("/{tenant_id}", response_model=TenantOut)
def get_tenant(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("TENANT_VIEW")),
) -> TenantOut:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    return _to_out(db, tenant)


@router.patch("/{tenant_id}", response_model=TenantOut)
def update_tenant(
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("TENANT_EDIT")),
    meta: dict = Depends(client_meta),
) -> TenantOut:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    for field in ("social_reason", "company_name", "cnpj", "email", "phone", "active"):
        value = getattr(payload, field)
        if value is not None:
            setattr(tenant, field, value)
    db.commit()
    db.refresh(tenant)
    record_audit(
        db,
        action="TENANT_UPDATE",
        tenant_id=tenant.id,
        user_id=ctx.user.id,
        resource="tenant",
        resource_id=str(tenant.id),
        meta=payload.model_dump(exclude_none=True),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _to_out(db, tenant)


@router.put("/{tenant_id}/modules", response_model=TenantOut)
def set_tenant_modules(
    tenant_id: uuid.UUID,
    module_codes: list[str],
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("MODULE_MANAGE")),
    meta: dict = Depends(client_meta),
) -> TenantOut:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    _set_modules(db, tenant_id, module_codes)
    db.commit()
    record_audit(
        db,
        action="TENANT_MODULES_UPDATE",
        tenant_id=tenant.id,
        user_id=ctx.user.id,
        resource="tenant",
        resource_id=str(tenant.id),
        meta={"modules": module_codes},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _to_out(db, tenant)


@router.delete("/{tenant_id}")
def delete_tenant(
    tenant_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("TENANT_DELETE")),
    meta: dict = Depends(client_meta),
) -> dict:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant não encontrado")
    tenant.active = False
    tenant.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(
        db,
        action="TENANT_SOFT_DELETE",
        tenant_id=tenant.id,
        user_id=ctx.user.id,
        resource="tenant",
        resource_id=str(tenant.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Tenant desativado (soft delete)."}
