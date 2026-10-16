"""User administration endpoints.

Any authenticated admin can manage tenants/users they have permission for.
A non-master tenant admin is constrained to their own tenant (tenant isolation
is enforced here, not just in the UI).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models import Person, Role, User, UserRole, UserTenant
from app.rbac import AccessContext
from app.schemas.auth import PasswordReset, RoleOut, UserCreate, UserOut, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/users")


def _to_out(db: Session, user: User) -> UserOut:
    roles: list[RoleOut] = []
    for ur in db.execute(
        select(Role).join(UserRole, UserRole.role_id == Role.id).where(
            UserRole.user_id == user.id
        )
    ).scalars():
        out = RoleOut.model_validate(ur)
        out.permissions = []
        roles.append(out)
    res = UserOut.model_validate(user)
    if user.tenant is not None:
        res.tenant_name = user.tenant.social_reason
    res.roles = roles
    return res


def _resolve_tenant(
    ctx: AccessContext, requested: uuid.UUID | None
) -> uuid.UUID | None:
    """Enforce that a non-master admin stays within their own tenant."""
    if ctx.user.is_master_admin:
        return requested
    if requested is not None and requested != ctx.user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é permitido gerenciar usuários de outro tenant",
        )
    return ctx.user.tenant_id


def _assert_same_tenant(ctx: AccessContext, user: User) -> None:
    if ctx.user.is_master_admin:
        return
    if user.tenant_id != ctx.user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: usuário de outro tenant",
        )


def _set_roles(
    db: Session,
    user_id: uuid.UUID,
    role_ids: list[uuid.UUID],
    *,
    tenant_id: uuid.UUID | None,
    actor: User | None = None,
) -> None:
    """Replace a user's roles, validating tenant ownership.

    A role may be granted only when it is a *system* role (``tenant_id IS NULL``)
    or when it belongs to the target user's tenant. This prevents a tenant
    administrator from escalating privileges by attaching a role that belongs to
    another tenant. Master admins bypass the tenant check (platform scope).
    """
    if not role_ids:
        existing = {
            ur.role_id: ur
            for ur in db.execute(
                select(UserRole).where(UserRole.user_id == user_id)
            ).scalars()
        }
        for ur in existing.values():
            db.delete(ur)
        return

    roles = {
        r.id: r
        for r in db.execute(select(Role).where(Role.id.in_(role_ids))).scalars()
    }
    missing = [str(rid) for rid in role_ids if rid not in roles]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Papel não encontrado: {', '.join(missing)}",
        )

    am_master = bool(actor is not None and actor.is_master_admin)
    for role in roles.values():
        if am_master:
            continue
        if role.tenant_id is not None and role.tenant_id != tenant_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Não é permitido atribuir papel de outro tenant "
                    f"({role.code})"
                ),
            )

    existing = {
        ur.role_id: ur
        for ur in db.execute(
            select(UserRole).where(UserRole.user_id == user_id)
        ).scalars()
    }
    for rid in role_ids:
        if rid not in existing:
            db.add(UserRole(user_id=user_id, role_id=rid))
    for rid, ur in existing.items():
        if rid not in role_ids:
            db.delete(ur)


@router.get("", response_model=list[UserOut])
def list_users(
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("USER_VIEW")),
) -> list[UserOut]:
    stmt = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    if ctx.user.is_master_admin:
        if tenant_id is not None:
            stmt = stmt.where(User.tenant_id == tenant_id)
    else:
        stmt = stmt.where(User.tenant_id == ctx.user.tenant_id)
    users = db.execute(stmt).scalars().all()
    return [_to_out(db, u) for u in users]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("USER_CREATE")),
    meta: dict = Depends(client_meta),
) -> UserOut:
    tenant_id = _resolve_tenant(ctx, payload.tenant_id)
    email = payload.email.lower()
    access_code = (payload.access_code or email).lower()
    exists = db.execute(
        select(User).where(
            User.email == email,
            User.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="Email já cadastrado")

    # Resolve / create the 1:1 Person profile holding the cadastral data.
    person: Person | None = None
    if payload.person_id is not None:
        person = db.get(Person, payload.person_id)
        if person is None:
            raise HTTPException(status_code=404, detail="Pessoa não encontrada")
    else:
        person = Person(
            tenant_id=tenant_id,
            name=payload.name or access_code.split("@")[0],
            email=email,
            active=True,
        )
        db.add(person)
        db.flush()

    user = User(
        tenant_id=tenant_id,
        person_id=person.id,
        access_code=access_code,
        email=email,
        password_hash=hash_password(payload.password),
        type=payload.type,
        mfa=payload.mfa,
        active=payload.active,
        is_master_admin=False,
    )
    db.add(user)
    db.flush()
    # N-N tenant memberships (payload.tenant_ids + the primary tenant).
    membership_ids = {tenant_id} | set(payload.tenant_ids)
    for tid in membership_ids:
        if tid is None:
            continue
        if db.execute(
            select(UserTenant).where(
                UserTenant.user_id == user.id, UserTenant.tenant_id == tid
            )
        ).scalar_one_or_none() is None:
            db.add(
                UserTenant(
                    user_id=user.id, tenant_id=tid, is_default=(tid == tenant_id)
                )
            )
    _set_roles(db, user.id, payload.role_ids, tenant_id=tenant_id, actor=ctx.user)
    db.commit()
    db.refresh(user)
    record_audit(
        db,
        action="USER_CREATE",
        tenant_id=tenant_id,
        user_id=ctx.user.id,
        resource="user",
        resource_id=str(user.id),
        meta={"email": email},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _to_out(db, user)


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("USER_VIEW")),
) -> UserOut:
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    _assert_same_tenant(ctx, user)
    return _to_out(db, user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("USER_EDIT")),
    meta: dict = Depends(client_meta),
) -> UserOut:
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    _assert_same_tenant(ctx, user)
    if payload.access_code is not None:
        user.access_code = payload.access_code.lower()
    if payload.email is not None:
        user.email = payload.email.lower()
    if payload.active is not None:
        user.active = payload.active
    if payload.type is not None:
        user.type = payload.type
    if payload.mfa is not None:
        user.mfa = payload.mfa
    if payload.person_id is not None:
        user.person_id = payload.person_id
    if payload.role_ids is not None:
        _set_roles(
            db,
            user.id,
            payload.role_ids,
            tenant_id=user.tenant_id,
            actor=ctx.user,
        )
    db.commit()
    db.refresh(user)
    record_audit(
        db,
        action="USER_UPDATE",
        tenant_id=user.tenant_id,
        user_id=ctx.user.id,
        resource="user",
        resource_id=str(user.id),
        meta=payload.model_dump(exclude_none=True, mode="json"),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _to_out(db, user)


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: uuid.UUID,
    payload: PasswordReset,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("USER_EDIT")),
    meta: dict = Depends(client_meta),
) -> dict:
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    _assert_same_tenant(ctx, user)
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    record_audit(
        db,
        action="USER_PASSWORD_RESET",
        tenant_id=user.tenant_id,
        user_id=ctx.user.id,
        resource="user",
        resource_id=str(user.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Senha redefinida com sucesso."}


@router.delete("/{user_id}")
def deactivate_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("USER_DELETE")),
    meta: dict = Depends(client_meta),
) -> dict:
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    _assert_same_tenant(ctx, user)
    if user.is_master_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível desativar o Master Admin",
        )
    user.active = False
    user.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(
        db,
        action="USER_SOFT_DELETE",
        tenant_id=user.tenant_id,
        user_id=ctx.user.id,
        resource="user",
        resource_id=str(user.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Usuário desativado (soft delete)."}
