"""RBAC resolution: compute a user's effective roles, modules, resources and
permissions.

Effective permissions are the union of permissions from all roles the user has.
A role's permissions are only effective if the role's module (if any) is enabled
for the user's tenant AND the role itself is active.

Effective *resources* come from the three grant paths of section 3:

1. ``UserPolicy``   — direct User → Resource (ALLOWED adds, DENIED removes);
2. ``GroupPolicy``  — via the user's ``UserGroup`` memberships;
3. ``RolePolicy``   — via the user's roles (strictly ALLOWED).

An explicit ``DENIED`` decision (UserPolicy/GroupPolicy) always wins over an
allow for the same resource.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Group,
    GroupPolicy,
    Module,
    Permission,
    Resource,
    Role,
    RolePermission,
    RolePolicy,
    TenantModule,
    User,
    UserGroup,
    UserPolicy,
    UserRole,
)


class AccessContext:
    """Computed access context for an authenticated user."""

    def __init__(
        self,
        *,
        user: User,
        tenant_id: uuid.UUID | None,
        roles: list[str],
        modules: list[str],
        permissions: set[str],
        resources: set[str] | None = None,
        scoped_resources: dict[str, dict[str, set]] | None = None,
        companies: set | None = None,
        unities: set | None = None,
    ) -> None:
        self.user = user
        self.tenant_id = tenant_id
        self.roles = roles
        self.modules = modules
        self.permissions = permissions
        self.resources = resources or set()
        # ``scoped_resources[resource_code] = {"company_id": {...}, "unity_id": {...}}``
        # for resources granted with an explicit Company/Unity scope.
        self.scoped_resources = scoped_resources or {}
        self.companies = companies or set()
        self.unities = unities or set()

    def has_permission(self, code: str) -> bool:
        return code in self.permissions

    def has_module(self, module_code: str) -> bool:
        return module_code in self.modules

    def has_resource(self, code: str) -> bool:
        return code in self.resources or "*" in self.resources


def tenant_enabled_modules(db: Session, tenant_id: uuid.UUID) -> list[str]:
    rows = db.execute(
        select(Module.code)
        .join(TenantModule, TenantModule.module_id == Module.id)
        .where(
            TenantModule.tenant_id == tenant_id,
            TenantModule.active.is_(True),
            Module.active.is_(True),
        )
    ).scalars()
    return list(rows)


def _collect_policies(
    db: Session,
    *,
    user_id: uuid.UUID,
    role_ids: list[uuid.UUID],
) -> tuple[set[str], dict[str, dict[str, set]], set, set]:
    """Resolve resource grants from the three paths.

    Returns ``(resources, scoped_resources, companies, unities)``.
    """
    rows = db.execute(select(Resource)).scalars().all()
    code_by_id: dict[uuid.UUID, str] = {r.id: r.code for r in rows}
    control_by_code: dict[str, bool] = {r.code: r.control_company_unity for r in rows}

    allowed: set[str] = set()
    denied: set[str] = set()
    scoped: dict[str, dict[str, set]] = {}
    companies: set = set()
    unities: set = set()

    def _note_scope(code: str, company_id, unity_id) -> None:
        if company_id is None and unity_id is None:
            return
        bucket = scoped.setdefault(code, {"company_id": set(), "unity_id": set()})
        if company_id is not None:
            bucket["company_id"].add(company_id)
            companies.add(company_id)
        if unity_id is not None:
            bucket["unity_id"].add(unity_id)
            unities.add(unity_id)

    # Path 1 — UserPolicy (direct user → resource, ALLOWED/DENIED).
    for policy in db.execute(
        select(UserPolicy).where(UserPolicy.user_id == user_id)
    ).scalars():
        code = code_by_id.get(policy.resource_id)
        if code is None:
            continue
        if policy.decision == "DENIED":
            denied.add(code)
        else:
            allowed.add(code)
            _note_scope(code, policy.company_id, policy.unity_id)

    # Path 2 — GroupPolicy via the user's group memberships.
    group_ids = {
        ug.group_id
        for ug in db.execute(
            select(UserGroup).where(UserGroup.user_id == user_id)
        ).scalars()
    }
    active_groups: set = set()
    if group_ids:
        active_groups = {
            g.id
            for g in db.execute(
                select(Group).where(Group.id.in_(group_ids), Group.active.is_(True))
            ).scalars()
        }
    if active_groups:
        for policy in db.execute(
            select(GroupPolicy).where(GroupPolicy.group_id.in_(active_groups))
        ).scalars():
            code = code_by_id.get(policy.resource_id)
            if code is None:
                continue
            if policy.decision == "DENIED":
                denied.add(code)
            else:
                allowed.add(code)
                _note_scope(code, policy.company_id, policy.unity_id)

    # Path 3 — RolePolicy via the user's roles (strictly ALLOWED).
    if role_ids:
        for policy in db.execute(
            select(RolePolicy).where(
                RolePolicy.role_id.in_(role_ids),
                (RolePolicy.user_id.is_(None)) | (RolePolicy.user_id == user_id),
            )
        ).scalars():
            code = code_by_id.get(policy.resource_id)
            if code is None:
                continue
            allowed.add(code)
            _note_scope(code, policy.company_id, policy.unity_id)

    resources = allowed - denied
    # Keep only scopes for granted resources that actually control the scope.
    scoped = {
        code: scopes
        for code, scopes in scoped.items()
        if code in resources and control_by_code.get(code, False)
    }
    return resources, scoped, companies, unities


def build_access_context(db: Session, user: User) -> AccessContext:
    """Resolve roles, modules, resources and permissions for a user."""
    # Master admin: full access within the administrative scope, no tenant needed.
    if user.is_master_admin:
        all_modules = list(
            db.execute(select(Module.code).where(Module.active.is_(True))).scalars()
        )
        all_perms = set(db.execute(select(Permission.code)).scalars())
        all_resources = set(db.execute(select(Resource.code)).scalars())
        return AccessContext(
            user=user,
            tenant_id=user.tenant_id,
            roles=["MASTER_ADMIN"],
            modules=all_modules,
            permissions=all_perms,
            resources=all_resources,
        )

    # Modules enabled for the tenant.
    enabled_modules = set()
    if user.tenant_id is not None:
        enabled_modules = set(tenant_enabled_modules(db, user.tenant_id))

    role_rows = db.execute(
        select(Role)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id, Role.active.is_(True))
    ).scalars().all()

    roles: list[str] = []
    permissions: set[str] = set()
    active_role_ids: list[uuid.UUID] = []

    for role in role_rows:
        # If the role is bound to a module, that module must be enabled for tenant.
        if role.module_id is not None:
            module_code = db.execute(
                select(Module.code).where(Module.id == role.module_id)
            ).scalar_one_or_none()
            if module_code is None or module_code not in enabled_modules:
                continue
        roles.append(role.code)
        active_role_ids.append(role.id)
        perm_codes = db.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        ).scalars()
        permissions.update(perm_codes)

    resources, scoped, companies, unities = _collect_policies(
        db, user_id=user.id, role_ids=active_role_ids
    )

    return AccessContext(
        user=user,
        tenant_id=user.tenant_id,
        roles=sorted(roles),
        modules=sorted(enabled_modules),
        permissions=permissions,
        resources=resources,
        scoped_resources=scoped,
        companies=companies,
        unities=unities,
    )
