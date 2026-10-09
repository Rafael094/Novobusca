"""Role & permission administration.

Roles can be tenant-scoped (tenant_id set) or system roles (tenant_id NULL,
grantable to any tenant's users). Permission catalog is global.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models import Module, Permission, Role, RolePermission
from app.rbac import AccessContext
from app.schemas.auth import PermissionOut, RoleCreate, RoleOut, RoleUpdate

router = APIRouter()


def _module_id_by_code(db: Session, code: str | None) -> uuid.UUID | None:
    if code is None:
        return None
    module = db.execute(select(Module).where(Module.code == code)).scalar_one_or_none()
    return module.id if module else None


def _role_out(db: Session, role: Role) -> RoleOut:
    codes = list(
        db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        ).scalars()
    )
    return RoleOut(
        id=role.id,
        name=role.name,
        code=role.code,
        module_code=role.module.code if role.module else None,
        description=role.description,
        is_system=role.is_system,
        active=role.active,
        permissions=sorted(codes),
    )


def _set_permissions(db: Session, role_id: uuid.UUID, codes: list[str]) -> None:
    perms = (
        {
            p.code: p
            for p in db.execute(
                select(Permission).where(Permission.code.in_(codes))
            ).scalars()
        }
        if codes
        else {}
    )
    existing = {
        rp.permission_id: rp
        for rp in db.execute(
            select(RolePermission).where(RolePermission.role_id == role_id)
        ).scalars()
    }
    wanted_ids = {p.id for p in perms.values()}
    for perm in perms.values():
        if perm.id not in existing:
            db.add(RolePermission(role_id=role_id, permission_id=perm.id))
    for pid, rp in existing.items():
        if pid not in wanted_ids:
            db.delete(rp)


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("ROLE_VIEW")),
) -> list[RoleOut]:
    stmt = select(Role).order_by(Role.name)
    if not ctx.user.is_master_admin:
        stmt = stmt.where(
            (Role.tenant_id == ctx.user.tenant_id) | (Role.tenant_id.is_(None))
        )
    roles = db.execute(stmt).scalars().all()
    return [_role_out(db, r) for r in roles]


@router.post("/roles", response_model=RoleOut, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("ROLE_CREATE")),
    meta: dict = Depends(client_meta),
) -> RoleOut:
    tenant_id = None if ctx.user.is_master_admin else ctx.user.tenant_id
    exists = db.execute(
        select(Role).where(Role.tenant_id == tenant_id, Role.code == payload.code)
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="Já existe um papel com este código")
    role = Role(
        tenant_id=tenant_id,
        module_id=_module_id_by_code(db, payload.module_code),
        name=payload.name,
        code=payload.code,
        description=payload.description,
        is_system=False,
        active=True,
    )
    db.add(role)
    db.flush()
    _set_permissions(db, role.id, payload.permission_codes)
    db.commit()
    db.refresh(role)
    record_audit(
        db,
        action="ROLE_CREATE",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        resource="role",
        resource_id=str(role.id),
        meta={"code": role.code, "permissions": payload.permission_codes},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _role_out(db, role)


@router.get("/roles/{role_id}", response_model=RoleOut)
def get_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("ROLE_VIEW")),
) -> RoleOut:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Papel não encontrado")
    if not ctx.user.is_master_admin and role.tenant_id not in (None, ctx.user.tenant_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    return _role_out(db, role)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("ROLE_EDIT")),
    meta: dict = Depends(client_meta),
) -> RoleOut:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Papel não encontrado")
    if role.is_system and not ctx.user.is_master_admin:
        raise HTTPException(status_code=403, detail="Não é permitido editar papel de sistema")
    if not ctx.user.is_master_admin and role.tenant_id != ctx.user.tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    if payload.name is not None:
        role.name = payload.name
    if payload.description is not None:
        role.description = payload.description
    if payload.active is not None:
        role.active = payload.active
    if payload.permission_codes is not None:
        _set_permissions(db, role.id, payload.permission_codes)
    db.commit()
    db.refresh(role)
    record_audit(
        db,
        action="ROLE_UPDATE",
        tenant_id=role.tenant_id,
        user_id=ctx.user.id,
        resource="role",
        resource_id=str(role.id),
        meta=payload.model_dump(exclude_none=True),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _role_out(db, role)


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("ROLE_DELETE")),
    meta: dict = Depends(client_meta),
) -> dict:
    role = db.get(Role, role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Papel não encontrado")
    if role.is_system:
        raise HTTPException(status_code=400, detail="Não é possível excluir papel de sistema")
    if not ctx.user.is_master_admin and role.tenant_id != ctx.user.tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    db.delete(role)
    db.commit()
    record_audit(
        db,
        action="ROLE_DELETE",
        tenant_id=role.tenant_id,
        user_id=ctx.user.id,
        resource="role",
        resource_id=str(role_id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Papel removido."}


@router.get("/permissions", response_model=list[PermissionOut])
def list_permissions(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("PERMISSION_VIEW")),
) -> list[PermissionOut]:
    perms = db.execute(select(Permission).order_by(Permission.code)).scalars().all()
    result = []
    for p in perms:
        out = PermissionOut.model_validate(p)
        out.module_code = p.module.code if p.module else None
        result.append(out)
    return result
