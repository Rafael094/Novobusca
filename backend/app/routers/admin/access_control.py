"""Access-control administration: resources, groups and the three policy paths.

Endpoints (all under ``/api/admin``):

* ``GET/POST /resources``, ``PATCH /resources/{id}`` — resource catalog;
* ``GET/POST /groups``, ``PATCH/DELETE /groups/{id}`` — group aggregation;
* ``GET/POST/DELETE /user-policies``     — direct User → Resource grants;
* ``GET/POST/DELETE /group-policies``    — Group → Resource grants;
* ``GET/POST/DELETE /role-policies``     — Role → Resource grants;
* ``GET/POST/DELETE /user-groups``       — user ↔ group membership;
* ``GET /users/{id}/effective-access``   — resolved effective access diagnostics.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models import (
    Group,
    GroupPolicy,
    Module,
    Resource,
    Role,
    RolePolicy,
    User,
    UserGroup,
    UserPolicy,
)
from app.rbac import AccessContext, build_access_context
from app.schemas.rbac import (
    EffectiveAccessOut,
    GroupCreate,
    GroupOut,
    GroupPolicyCreate,
    GroupPolicyOut,
    GroupUpdate,
    ResourceCreate,
    ResourceOut,
    ResourceUpdate,
    RolePolicyCreate,
    RolePolicyOut,
    UserGroupCreate,
    UserGroupOut,
    UserPolicyCreate,
    UserPolicyOut,
)

router = APIRouter()


# --- Resources --------------------------------------------------------------
def _resource_out(resource: Resource) -> ResourceOut:
    out = ResourceOut.model_validate(resource)
    out.module_code = resource.module.code if resource.module else None
    return out


@router.get("/resources", response_model=list[ResourceOut])
def list_resources(
    module_code: str | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("RESOURCE_VIEW")),
) -> list[ResourceOut]:
    stmt = select(Resource).order_by(Resource.code)
    if module_code:
        stmt = stmt.join(Module, Module.id == Resource.module_id).where(
            Module.code == module_code
        )
    return [_resource_out(r) for r in db.execute(stmt).scalars().all()]


@router.post(
    "/resources", response_model=ResourceOut, status_code=status.HTTP_201_CREATED
)
def create_resource(
    payload: ResourceCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("RESOURCE_MANAGE")),
    meta: dict = Depends(client_meta),
) -> ResourceOut:
    if db.execute(
        select(Resource).where(Resource.code == payload.code)
    ).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Já existe um recurso com este código")
    module_id = None
    if payload.module_code:
        module = db.execute(
            select(Module).where(Module.code == payload.module_code)
        ).scalar_one_or_none()
        if module is None:
            raise HTTPException(status_code=404, detail="Módulo não encontrado")
        module_id = module.id
    if module_id is None:
        raise HTTPException(status_code=400, detail="module_code é obrigatório")
    data = payload.model_dump(exclude={"module_code"})
    resource = Resource(module_id=module_id, **data)
    db.add(resource)
    db.commit()
    db.refresh(resource)
    record_audit(
        db,
        action="RESOURCE_CREATE",
        user_id=ctx.user.id,
        resource="resource",
        resource_id=str(resource.id),
        meta={"code": resource.code},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _resource_out(resource)


@router.patch("/resources/{resource_id}", response_model=ResourceOut)
def update_resource(
    resource_id: uuid.UUID,
    payload: ResourceUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("RESOURCE_MANAGE")),
    meta: dict = Depends(client_meta),
) -> ResourceOut:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    if resource.is_native and payload.active is False:
        raise HTTPException(
            status_code=400, detail="Recursos nativos não podem ser desativados"
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(resource, field, value)
    db.commit()
    db.refresh(resource)
    record_audit(
        db,
        action="RESOURCE_UPDATE",
        user_id=ctx.user.id,
        resource="resource",
        resource_id=str(resource.id),
        meta=payload.model_dump(exclude_none=True),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return _resource_out(resource)


# --- Groups -----------------------------------------------------------------
@router.get("/groups", response_model=list[GroupOut])
def list_groups(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("GROUP_VIEW")),
) -> list[GroupOut]:
    stmt = select(Group).where(Group.deleted_at.is_(None)).order_by(Group.name)
    if not ctx.user.is_master_admin:
        stmt = stmt.where(Group.tenant_id == ctx.user.tenant_id)
    return [GroupOut.model_validate(g) for g in db.execute(stmt).scalars().all()]


@router.post("/groups", response_model=GroupOut, status_code=status.HTTP_201_CREATED)
def create_group(
    payload: GroupCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("GROUP_MANAGE")),
    meta: dict = Depends(client_meta),
) -> GroupOut:
    if ctx.user.tenant_id is None:
        raise HTTPException(status_code=400, detail="Usuário sem tenant")
    if db.execute(
        select(Group).where(
            Group.tenant_id == ctx.user.tenant_id, Group.code == payload.code
        )
    ).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Já existe um grupo com este código")
    group = Group(tenant_id=ctx.user.tenant_id, **payload.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    record_audit(
        db,
        action="GROUP_CREATE",
        tenant_id=group.tenant_id,
        user_id=ctx.user.id,
        resource="group",
        resource_id=str(group.id),
        meta={"code": group.code},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return GroupOut.model_validate(group)


def _assert_group(ctx: AccessContext, group: Group) -> None:
    if not ctx.user.is_master_admin and group.tenant_id != ctx.user.tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado")


@router.patch("/groups/{group_id}", response_model=GroupOut)
def update_group(
    group_id: uuid.UUID,
    payload: GroupUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("GROUP_MANAGE")),
    meta: dict = Depends(client_meta),
) -> GroupOut:
    group = db.get(Group, group_id)
    if group is None or group.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    _assert_group(ctx, group)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(group, field, value)
    db.commit()
    db.refresh(group)
    record_audit(
        db,
        action="GROUP_UPDATE",
        tenant_id=group.tenant_id,
        user_id=ctx.user.id,
        resource="group",
        resource_id=str(group.id),
        meta=payload.model_dump(exclude_none=True),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return GroupOut.model_validate(group)


@router.delete("/groups/{group_id}")
def delete_group(
    group_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("GROUP_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    group = db.get(Group, group_id)
    if group is None or group.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    _assert_group(ctx, group)
    from datetime import datetime, timezone

    group.active = False
    group.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(
        db,
        action="GROUP_SOFT_DELETE",
        tenant_id=group.tenant_id,
        user_id=ctx.user.id,
        resource="group",
        resource_id=str(group.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Grupo desativado (soft delete)."}


# --- Policy helpers ---------------------------------------------------------
def _assert_user_scope(ctx: AccessContext, user: User) -> None:
    if not ctx.user.is_master_admin and user.tenant_id != ctx.user.tenant_id:
        raise HTTPException(status_code=403, detail="Acesso negado: usuário de outro tenant")


def _resource_or_404(db: Session, resource_id: uuid.UUID) -> Resource:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status_code=404, detail="Recurso não encontrado")
    return resource


def _validate_scope(db: Session, company_id, unity_id) -> None:
    """Ensure a scope points at an existing company/unity (when provided)."""
    from app.models import Company, Unity

    if company_id is not None and db.get(Company, company_id) is None:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    if unity_id is not None:
        unity = db.get(Unity, unity_id)
        if unity is None:
            raise HTTPException(status_code=404, detail="Unidade não encontrada")
        if company_id is not None and unity.company_id != company_id:
            raise HTTPException(
                status_code=400, detail="Unidade não pertence à empresa informada"
            )


# --- Path 1: UserPolicy -----------------------------------------------------
@router.get("/user-policies", response_model=list[UserPolicyOut])
def list_user_policies(
    user_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("USER_POLICY_MANAGE")),
) -> list[UserPolicyOut]:
    stmt = select(UserPolicy).order_by(UserPolicy.created_at.desc())
    if user_id is not None:
        stmt = stmt.where(UserPolicy.user_id == user_id)
    elif not ctx.user.is_master_admin:
        # Restrict to users of the caller's tenant.
        stmt = stmt.join(User, User.id == UserPolicy.user_id).where(
            User.tenant_id == ctx.user.tenant_id
        )
    result = []
    for policy in db.execute(stmt).scalars().all():
        out = UserPolicyOut.model_validate(policy)
        out.resource_code = policy.resource.code if policy.resource else None
        result.append(out)
    return result


@router.post(
    "/user-policies", response_model=UserPolicyOut, status_code=status.HTTP_201_CREATED
)
def create_user_policy(
    payload: UserPolicyCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("USER_POLICY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> UserPolicyOut:
    user = db.get(User, payload.user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    _assert_user_scope(ctx, user)
    _resource_or_404(db, payload.resource_id)
    _validate_scope(db, payload.company_id, payload.unity_id)
    existing = db.execute(
        select(UserPolicy).where(
            UserPolicy.user_id == payload.user_id,
            UserPolicy.resource_id == payload.resource_id,
            UserPolicy.company_id == payload.company_id,
            UserPolicy.unity_id == payload.unity_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.decision = payload.decision
        policy = existing
    else:
        policy = UserPolicy(
            user_id=payload.user_id,
            resource_id=payload.resource_id,
            tenant_id=user.tenant_id,
            company_id=payload.company_id,
            unity_id=payload.unity_id,
            decision=payload.decision,
        )
        db.add(policy)
    db.commit()
    db.refresh(policy)
    record_audit(
        db,
        action="USER_POLICY_SET",
        tenant_id=user.tenant_id,
        user_id=ctx.user.id,
        resource="user_policy",
        resource_id=str(policy.id),
        meta={
            "target_user": str(payload.user_id),
            "resource_id": str(payload.resource_id),
            "decision": payload.decision,
        },
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    out = UserPolicyOut.model_validate(policy)
    out.resource_code = policy.resource.code if policy.resource else None
    return out


@router.delete("/user-policies/{policy_id}")
def delete_user_policy(
    policy_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("USER_POLICY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    policy = db.get(UserPolicy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Política não encontrada")
    user = db.get(User, policy.user_id)
    if user is not None:
        _assert_user_scope(ctx, user)
    db.delete(policy)
    db.commit()
    record_audit(
        db,
        action="USER_POLICY_DELETE",
        user_id=ctx.user.id,
        resource="user_policy",
        resource_id=str(policy_id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Política de usuário removida."}


# --- Path 2: GroupPolicy ----------------------------------------------------
@router.get("/group-policies", response_model=list[GroupPolicyOut])
def list_group_policies(
    group_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("GROUP_POLICY_MANAGE")),
) -> list[GroupPolicyOut]:
    stmt = select(GroupPolicy).order_by(GroupPolicy.created_at.desc())
    if group_id is not None:
        stmt = stmt.where(GroupPolicy.group_id == group_id)
    elif not ctx.user.is_master_admin:
        stmt = stmt.join(Group, Group.id == GroupPolicy.group_id).where(
            Group.tenant_id == ctx.user.tenant_id
        )
    result = []
    for policy in db.execute(stmt).scalars().all():
        out = GroupPolicyOut.model_validate(policy)
        out.resource_code = policy.resource.code if policy.resource else None
        result.append(out)
    return result


@router.post(
    "/group-policies", response_model=GroupPolicyOut, status_code=status.HTTP_201_CREATED
)
def create_group_policy(
    payload: GroupPolicyCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("GROUP_POLICY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> GroupPolicyOut:
    group = db.get(Group, payload.group_id)
    if group is None or group.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    _assert_group(ctx, group)
    _resource_or_404(db, payload.resource_id)
    _validate_scope(db, payload.company_id, payload.unity_id)
    existing = db.execute(
        select(GroupPolicy).where(
            GroupPolicy.group_id == payload.group_id,
            GroupPolicy.resource_id == payload.resource_id,
            GroupPolicy.company_id == payload.company_id,
            GroupPolicy.unity_id == payload.unity_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.decision = payload.decision
        policy = existing
    else:
        policy = GroupPolicy(
            group_id=payload.group_id,
            resource_id=payload.resource_id,
            company_id=payload.company_id,
            unity_id=payload.unity_id,
            decision=payload.decision,
        )
        db.add(policy)
    db.commit()
    db.refresh(policy)
    record_audit(
        db,
        action="GROUP_POLICY_SET",
        tenant_id=group.tenant_id,
        user_id=ctx.user.id,
        resource="group_policy",
        resource_id=str(policy.id),
        meta={
            "group_id": str(payload.group_id),
            "resource_id": str(payload.resource_id),
            "decision": payload.decision,
        },
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    out = GroupPolicyOut.model_validate(policy)
    out.resource_code = policy.resource.code if policy.resource else None
    return out


@router.delete("/group-policies/{policy_id}")
def delete_group_policy(
    policy_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("GROUP_POLICY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    policy = db.get(GroupPolicy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Política não encontrada")
    group = db.get(Group, policy.group_id)
    if group is not None:
        _assert_group(ctx, group)
    db.delete(policy)
    db.commit()
    record_audit(
        db,
        action="GROUP_POLICY_DELETE",
        user_id=ctx.user.id,
        resource="group_policy",
        resource_id=str(policy_id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Política de grupo removida."}


# --- Path 3: RolePolicy -----------------------------------------------------
@router.get("/role-policies", response_model=list[RolePolicyOut])
def list_role_policies(
    role_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("ROLE_POLICY_MANAGE")),
) -> list[RolePolicyOut]:
    stmt = select(RolePolicy).order_by(RolePolicy.created_at.desc())
    if role_id is not None:
        stmt = stmt.where(RolePolicy.role_id == role_id)
    result = []
    for policy in db.execute(stmt).scalars().all():
        out = RolePolicyOut.model_validate(policy)
        out.resource_code = policy.resource.code if policy.resource else None
        result.append(out)
    return result


@router.post(
    "/role-policies", response_model=RolePolicyOut, status_code=status.HTTP_201_CREATED
)
def create_role_policy(
    payload: RolePolicyCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("ROLE_POLICY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> RolePolicyOut:
    role = db.get(Role, payload.role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Papel não encontrado")
    if not ctx.user.is_master_admin and role.tenant_id not in (None, ctx.user.tenant_id):
        raise HTTPException(status_code=403, detail="Acesso negado")
    _resource_or_404(db, payload.resource_id)
    _validate_scope(db, payload.company_id, payload.unity_id)
    existing = db.execute(
        select(RolePolicy).where(
            RolePolicy.role_id == payload.role_id,
            RolePolicy.resource_id == payload.resource_id,
            RolePolicy.user_id == payload.user_id,
            RolePolicy.company_id == payload.company_id,
            RolePolicy.unity_id == payload.unity_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        policy = existing
    else:
        policy = RolePolicy(
            role_id=payload.role_id,
            resource_id=payload.resource_id,
            user_id=payload.user_id,
            tenant_id=role.tenant_id,
            company_id=payload.company_id,
            unity_id=payload.unity_id,
            # A role never denies: resources coming from a role are ALLOWED.
            decision="ALLOWED",
        )
        db.add(policy)
    db.commit()
    db.refresh(policy)
    record_audit(
        db,
        action="ROLE_POLICY_SET",
        tenant_id=role.tenant_id,
        user_id=ctx.user.id,
        resource="role_policy",
        resource_id=str(policy.id),
        meta={
            "role_id": str(payload.role_id),
            "resource_id": str(payload.resource_id),
        },
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    out = RolePolicyOut.model_validate(policy)
    out.resource_code = policy.resource.code if policy.resource else None
    return out


@router.delete("/role-policies/{policy_id}")
def delete_role_policy(
    policy_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("ROLE_POLICY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    policy = db.get(RolePolicy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Política não encontrada")
    db.delete(policy)
    db.commit()
    record_audit(
        db,
        action="ROLE_POLICY_DELETE",
        user_id=ctx.user.id,
        resource="role_policy",
        resource_id=str(policy_id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Política de papel removida."}


# --- User ↔ Group membership ------------------------------------------------
@router.get("/user-groups", response_model=list[UserGroupOut])
def list_user_groups(
    user_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("GROUP_VIEW")),
) -> list[UserGroupOut]:
    stmt = select(UserGroup).order_by(UserGroup.created_at.desc())
    if user_id is not None:
        stmt = stmt.where(UserGroup.user_id == user_id)
    elif not ctx.user.is_master_admin:
        stmt = stmt.join(Group, Group.id == UserGroup.group_id).where(
            Group.tenant_id == ctx.user.tenant_id
        )
    return [
        UserGroupOut.model_validate(ug) for ug in db.execute(stmt).scalars().all()
    ]


@router.post(
    "/user-groups", response_model=UserGroupOut, status_code=status.HTTP_201_CREATED
)
def create_user_group(
    payload: UserGroupCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("GROUP_MANAGE")),
    meta: dict = Depends(client_meta),
) -> UserGroupOut:
    user = db.get(User, payload.user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    _assert_user_scope(ctx, user)
    group = db.get(Group, payload.group_id)
    if group is None or group.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")
    _assert_group(ctx, group)
    _validate_scope(db, payload.company_id, payload.unity_id)
    existing = db.execute(
        select(UserGroup).where(
            UserGroup.user_id == payload.user_id,
            UserGroup.group_id == payload.group_id,
            UserGroup.company_id == payload.company_id,
            UserGroup.unity_id == payload.unity_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        link = existing
    else:
        link = UserGroup(
            user_id=payload.user_id,
            group_id=payload.group_id,
            company_id=payload.company_id,
            unity_id=payload.unity_id,
        )
        db.add(link)
    db.commit()
    db.refresh(link)
    record_audit(
        db,
        action="USER_GROUP_ADD",
        tenant_id=group.tenant_id,
        user_id=ctx.user.id,
        resource="user_group",
        resource_id=str(link.id),
        meta={"target_user": str(payload.user_id), "group_id": str(payload.group_id)},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return UserGroupOut.model_validate(link)


@router.delete("/user-groups/{link_id}")
def delete_user_group(
    link_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("GROUP_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    link = db.get(UserGroup, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Vínculo não encontrado")
    group = db.get(Group, link.group_id)
    if group is not None:
        _assert_group(ctx, group)
    db.delete(link)
    db.commit()
    record_audit(
        db,
        action="USER_GROUP_REMOVE",
        user_id=ctx.user.id,
        resource="user_group",
        resource_id=str(link_id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Usuário removido do grupo."}


# --- Effective access diagnostics -------------------------------------------
@router.get("/users/{user_id}/effective-access", response_model=EffectiveAccessOut)
def effective_access(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("USER_VIEW")),
) -> EffectiveAccessOut:
    """Resolve the *effective* access of a user (all three policy paths)."""
    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    _assert_user_scope(ctx, user)
    resolved = build_access_context(db, user)
    scoped = {
        code: {
            "company_id": [str(c) for c in scopes.get("company_id", set())],
            "unity_id": [str(u) for u in scopes.get("unity_id", set())],
        }
        for code, scopes in resolved.scoped_resources.items()
    }
    return EffectiveAccessOut(
        user_id=user.id,
        roles=resolved.roles,
        modules=resolved.modules,
        permissions=sorted(resolved.permissions),
        resources=sorted(resolved.resources),
        scoped_resources=scoped,
        companies=sorted(resolved.companies, key=str),
        unities=sorted(resolved.unities, key=str),
    )
