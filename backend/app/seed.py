"""Idempotent database seed.

Creates/refreshes:
  * Modules (from app.constants.MODULES)
  * Permissions (from app.constants.PERMISSIONS)
  * System roles and their permission grants (from app.constants.ROLES)
  * The Master Admin user (from environment: MASTER_ADMIN_*)

No fake INPI data is ever inserted here — PI data comes exclusively from the
official datasets via the ingestion pipeline.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import MODULES, PERMISSIONS, RESOURCES, ROLES
from app.db import SessionLocal
from app.models import (
    Module,
    Permission,
    Person,
    Resource,
    Role,
    RolePermission,
    RolePolicy,
    Tenant,
    TenantModule,
    User,
    UserRole,
    UserTenant,
)
from app.security import hash_password


def seed_modules(db: Session) -> dict[str, Module]:
    by_code: dict[str, Module] = {}
    for order, spec in enumerate(MODULES):
        module = db.execute(
            select(Module).where(Module.code == spec["code"])
        ).scalar_one_or_none()
        if module is None:
            module = Module(
                code=spec["code"],
                name=spec["name"],
                description=spec.get("description"),
                control_company_unity=bool(spec.get("control_company_unity", False)),
                sort_order=order,
                active=True,
            )
            db.add(module)
            db.flush()
        else:
            module.name = spec["name"]
            module.description = spec.get("description")
            module.control_company_unity = bool(
                spec.get("control_company_unity", False)
            )
            module.sort_order = order
        by_code[spec["code"]] = module
    db.flush()
    return by_code


def seed_permissions(db: Session, modules: dict[str, Module]) -> dict[str, Permission]:
    by_code: dict[str, Permission] = {}
    for module_code, code, name in PERMISSIONS:
        perm = db.execute(
            select(Permission).where(Permission.code == code)
        ).scalar_one_or_none()
        module = modules.get(module_code)
        if perm is None:
            perm = Permission(
                code=code,
                name=name,
                module_id=module.id if module else None,
            )
            db.add(perm)
            db.flush()
        else:
            perm.name = name
            perm.module_id = module.id if module else None
        by_code[code] = perm
    db.flush()
    return by_code


def seed_resources(db: Session, modules: dict[str, Module]) -> dict[str, Resource]:
    """Upsert the Resource catalog (module → resource) from constants."""
    by_code: dict[str, Resource] = {}
    for spec in RESOURCES:
        resource = db.execute(
            select(Resource).where(Resource.code == spec["code"])
        ).scalar_one_or_none()
        module = modules.get(spec.get("module", ""))
        if resource is None:
            resource = Resource(
                code=spec["code"],
                name=spec["name"],
                description=spec.get("description"),
                module_id=module.id if module else None,
                is_native=bool(spec.get("is_native", True)),
                control_company_unity=bool(spec.get("control_company_unity", False)),
                active=True,
            )
            db.add(resource)
            db.flush()
        else:
            resource.name = spec["name"]
            resource.description = spec.get("description")
            resource.module_id = module.id if module else None
            resource.control_company_unity = bool(
                spec.get("control_company_unity", False)
            )
        by_code[spec["code"]] = resource
    db.flush()
    return by_code


def seed_roles(
    db: Session, modules: dict[str, Module], perms: dict[str, Permission]
) -> None:
    resources = {
        r.code: r for r in db.execute(select(Resource)).scalars()
    }
    for spec in ROLES:
        role = db.execute(
            select(Role).where(Role.tenant_id.is_(None), Role.code == spec["code"])
        ).scalar_one_or_none()
        module = modules.get(spec.get("module", ""))
        if role is None:
            role = Role(
                tenant_id=None,
                module_id=module.id if module else None,
                name=spec["name"],
                code=spec["code"],
                description=spec.get("description"),
                is_system=True,
                active=True,
            )
            db.add(role)
            db.flush()
        else:
            role.name = spec["name"]
            role.module_id = module.id if module else None
            role.is_system = True
        _grant(db, role, spec["permissions"], perms)
        _grant_resources(db, role, spec.get("resources", []), resources)
    db.flush()


def _grant_resources(
    db: Session, role: Role, codes: list[str], resources: dict[str, Resource]
) -> None:
    """Attach the role's resources (RolePolicy, always ALLOWED)."""
    if not codes:
        return
    existing = {
        rp.resource_id
        for rp in db.execute(
            select(RolePolicy).where(
                RolePolicy.role_id == role.id,
                RolePolicy.user_id.is_(None),
                RolePolicy.company_id.is_(None),
                RolePolicy.unity_id.is_(None),
            )
        ).scalars()
    }
    for code in codes:
        resource = resources.get(code)
        if resource is None or resource.id in existing:
            continue
        db.add(RolePolicy(role_id=role.id, resource_id=resource.id, decision="ALLOWED"))
    db.flush()


def _grant(
    db: Session, role: Role, codes: list[str], perms: dict[str, Permission]
) -> None:
    existing = {
        rp.permission_id
        for rp in db.execute(
            select(RolePermission).where(RolePermission.role_id == role.id)
        ).scalars()
    }
    for code in codes:
        perm = perms.get(code)
        if perm is None:
            continue
        if perm.id not in existing:
            db.add(RolePermission(role_id=role.id, permission_id=perm.id))


def seed_master_admin(db: Session) -> User:
    """Ensure the master admin exists as a credential-only user + Person.

    ``users`` keeps only the credentials (``access_code`` == email, password
    hash); the display name lives in the linked ``people`` row (1:1).
    """
    email = settings.master_admin_email.lower()
    user = db.execute(
        select(User).where(User.email == email).order_by(User.created_at)
    ).scalars().first()
    if user is None:
        user = User(
            tenant_id=None,
            access_code=email,
            email=email,
            password_hash=hash_password(settings.master_admin_password),
            active=True,
            type="MASTER",
            is_master_admin=True,
        )
        db.add(user)
        db.flush()
    else:
        user.is_master_admin = True
        user.active = True
        user.access_code = user.access_code or email
        if not user.password_hash:
            user.password_hash = hash_password(settings.master_admin_password)

    # 1:1 Person profile holding the cadastral/display name.
    person = db.execute(
        select(Person).where(Person.user_id == user.id)
    ).scalar_one_or_none()
    if person is None:
        person = Person(
            tenant_id=None,
            user_id=user.id,
            name=settings.master_admin_name,
            email=email,
            active=True,
        )
        db.add(person)
        db.flush()
    user.person_id = person.id
    db.flush()
    return user


def seed_default_tenant(db: Session, modules: dict[str, Module]) -> Tenant:
    """Ensure a default tenant exists with every module enabled.

    Always returns a *tenant* so the master admin (and any user without a tenant)
    can be linked to it, preserving data isolation. Idempotent.
    """
    tenant = db.execute(
        select(Tenant)
        .where(Tenant.social_reason == settings.default_tenant_name)
        .order_by(Tenant.created_at)
    ).scalars().first()
    if tenant is None:
        tenant = Tenant(
            social_reason=settings.default_tenant_name,
            company_name=settings.default_tenant_name,
            active=True,
        )
        db.add(tenant)
        db.flush()
    else:
        tenant.active = True
        tenant.company_name = tenant.company_name or tenant.social_reason

    # Enable every active module for the default tenant.
    enabled = {
        tm.module_id
        for tm in db.execute(
            select(TenantModule).where(TenantModule.tenant_id == tenant.id)
        ).scalars()
    }
    for module in modules.values():
        if module.id in enabled:
            continue
        db.add(TenantModule(tenant_id=tenant.id, module_id=module.id, active=True))
    db.flush()
    return tenant


def seed_default_admin_access(
    db: Session, tenant: Tenant, user: User, perms: dict[str, Permission]
) -> None:
    """Link the admin user to the default tenant and grant full access.

    Keeps ``is_master_admin`` intact (cross-tenant reach) and adds the
    ``SUPER_ADMIN`` role (all permissions) so no privilege is ever lost. Also
    registers the ``UserTenant`` membership and the admin's company lotação.
    """
    if user.tenant_id is None:
        user.tenant_id = tenant.id

    # N-N membership (UserTenant) is the canonical multi-tenant link.
    membership = db.execute(
        select(UserTenant).where(
            UserTenant.user_id == user.id, UserTenant.tenant_id == tenant.id
        )
    ).scalar_one_or_none()
    if membership is None:
        db.add(
            UserTenant(user_id=user.id, tenant_id=tenant.id, is_default=True)
        )

    role = db.execute(
        select(Role).where(Role.tenant_id.is_(None), Role.code == "SUPER_ADMIN")
    ).scalar_one_or_none()
    if role is None:
        return
    # Ensure the role has every permission (idempotent top-up).
    existing = {
        rp.permission_id
        for rp in db.execute(
            select(RolePermission).where(RolePermission.role_id == role.id)
        ).scalars()
    }
    for perm in perms.values():
        if perm.id not in existing:
            db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    # Ensure the role maps to every resource (RolePolicy, always ALLOWED).
    existing_resources = {
        rp.resource_id
        for rp in db.execute(
            select(RolePolicy).where(RolePolicy.role_id == role.id)
        ).scalars()
    }
    for resource in db.execute(select(Resource)).scalars():
        if resource.id not in existing_resources:
            db.add(
                RolePolicy(
                    role_id=role.id, resource_id=resource.id, decision="ALLOWED"
                )
            )
    # Grant the role to the admin user if not already granted.
    linked = db.execute(
        select(UserRole).where(
            UserRole.user_id == user.id, UserRole.role_id == role.id
        )
    ).scalar_one_or_none()
    if linked is None:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    db.flush()


def run_seed() -> dict:
    db = SessionLocal()
    try:
        modules = seed_modules(db)
        perms = seed_permissions(db, modules)
        resources = seed_resources(db, modules)
        seed_roles(db, modules, perms)
        master = seed_master_admin(db)
        tenant = seed_default_tenant(db, modules)
        seed_default_admin_access(db, tenant, master, perms)
        db.commit()
        return {
            "modules": len(modules),
            "permissions": len(perms),
            "resources": len(resources),
            "roles": len(ROLES),
            "master_admin": master.email,
            "default_tenant": tenant.social_reason,
        }
    finally:
        db.close()


if __name__ == "__main__":
    result = run_seed()
    print("Seed concluído:")
    for key, value in result.items():
        print(f"  - {key}: {value}")
