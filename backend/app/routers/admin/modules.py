"""Module administration (catalog of available platform modules)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models import Module
from app.rbac import AccessContext
from app.schemas.auth import ModuleCreate, ModuleOut, ModuleUpdate

router = APIRouter(prefix="/modules")


def _to_out(module: Module) -> ModuleOut:
    return ModuleOut.model_validate(module)


@router.get("", response_model=list[ModuleOut])
def list_modules(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("MODULE_VIEW")),
) -> list[ModuleOut]:
    modules = db.execute(select(Module).order_by(Module.sort_order, Module.code)).scalars().all()
    return [_to_out(m) for m in modules]


@router.post("", response_model=ModuleOut, status_code=status.HTTP_201_CREATED)
def create_module(
    payload: ModuleCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("MODULE_MANAGE")),
    meta: dict = Depends(client_meta),
) -> ModuleOut:
    exists = db.execute(
        select(Module).where(Module.code == payload.code)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="Já existe um módulo com este código")
    module = Module(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        control_company_unity=payload.control_company_unity,
        sort_order=payload.sort_order,
        active=payload.active,
    )
    db.add(module)
    db.commit()
    db.refresh(module)
    record_audit(
        db,
        action="MODULE_CREATE",
        user_id=ctx.user.id,
        resource="module",
        resource_id=str(module.id),
        meta={"code": module.code},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _to_out(module)


@router.patch("/{module_id}", response_model=ModuleOut)
def update_module(
    module_id: uuid.UUID,
    payload: ModuleUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("MODULE_MANAGE")),
    meta: dict = Depends(client_meta),
) -> ModuleOut:
    module = db.get(Module, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Módulo não encontrado")
    for field in ("name", "description", "control_company_unity", "sort_order", "active"):
        value = getattr(payload, field)
        if value is not None:
            setattr(module, field, value)
    db.commit()
    db.refresh(module)
    record_audit(
        db,
        action="MODULE_UPDATE",
        user_id=ctx.user.id,
        resource="module",
        resource_id=str(module.id),
        meta=payload.model_dump(exclude_none=True),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _to_out(module)


@router.delete("/{module_id}")
def delete_module(
    module_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("MODULE_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    module = db.get(Module, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Módulo não encontrado")
    # Soft disable: never delete a module that may be referenced by tenants/roles.
    module.active = False
    db.commit()
    record_audit(
        db,
        action="MODULE_DISABLE",
        user_id=ctx.user.id,
        resource="module",
        resource_id=str(module.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Módulo desativado."}
