"""Authentication, authorization and tenancy ORM models.

Hierarchy: Tenant -> User -> (UserRole) -> Role -> (RoleModule) -> Module
                                       -> (RolePermission) -> Permission
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

# The 1:1 ``users.person_id`` ↔ ``people.user_id`` pair forms an FK cycle. To let
# SQLAlchemy/Alembic sort the tables for DROP/CREATE deterministically, the
# ``users.person_id`` constraint is *named* and declared outside the inline DDL
# (see ``User.__table_args__`` → ``ForeignKeyConstraint``).
_FK_USERS_PERSON = "fk_users_person"
_FK_PEOPLE_USER = "fk_people_user"


class Tenant(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Aggregate root of the domain model (grupo empresarial).

    The Tenant is the ROOT: it has NO ``tenant_id`` column of its own. Every
    other entity (Company, Unity, User, roles, etc.) descends from it via a
    ``tenant_id`` FK — the ``TenantEntity`` pattern implemented in
    ``app.models.company.TenantEntityMixin``.

    ``mcp_api_key`` is the API key used by the MCP integration layer to act on
    behalf of this tenant.
    """

    __tablename__ = "tenants"

    # ``social_reason`` = Razão Social (legal name); ``company_name`` = Nome
    # Fantasia (trade name). ``cnpj`` is the group's CNPJ.
    social_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255))
    cnpj: Mapped[str | None] = mapped_column(String(18))
    mcp_api_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    users: Mapped[list["User"]] = relationship(back_populates="tenant")
    modules: Mapped[list["TenantModule"]] = relationship(back_populates="tenant")
    companies: Mapped[list["Company"]] = relationship(  # noqa: F821
        back_populates="tenant"
    )


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Pure access credentials.

    The user holds ONLY authentication data (``access_code``/login, BCrypt
    password + salt, type, MFA, refresh tokens). All cadastral data lives in the
    related ``Person`` (1:1 via ``person_id``). Tenancy is handled by the
    ``UserTenant`` association (N-N) — ``tenant_id`` is kept as the user's
    *default/active* tenant for backwards compatibility and token issuance.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("access_code", name="uq_users_access_code"),
        # Named + use_alter: breaks the users↔people FK cycle so table sorting
        # (DROP/CREATE) is deterministic for Alembic and the test schema reset.
        ForeignKeyConstraint(
            ["person_id"],
            ["people.id"],
            name=_FK_USERS_PERSON,
            ondelete="SET NULL",
            use_alter=True,
        ),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT")
    )
    # 1:1 link to the person's cadastral data (name, cpf, phone, address...).
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), unique=True
    )
    # Login identifier (``AccessCode``). ``email`` mirrors it for the terse
    # email-based login flow used by the UI.
    access_code: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    # Per-user salt (the BCrypt/Argon2 hash already embeds one; this column
    # preserves the explicit ``Salt`` field of the domain spec).
    salt: Mapped[str | None] = mapped_column(String(64))
    # ``INTERNAL`` | ``EXTERNAL`` | ``MASTER`` …
    type: Mapped[str] = mapped_column(String(32), default="INTERNAL", nullable=False)
    mfa: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Last issued opaque refresh token hash (in addition to the refresh_tokens
    # table, which keeps the full rotation history).
    refresh_token: Mapped[str | None] = mapped_column(String(128))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_master_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant | None"] = relationship(back_populates="users")
    person: Mapped["Person | None"] = relationship(  # noqa: F821
        foreign_keys=[person_id]
    )
    user_roles: Mapped[list["UserRole"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    user_tenants: Mapped[list["UserTenant"]] = relationship(  # noqa: F821
        cascade="all, delete-orphan"
    )
    user_groups: Mapped[list["UserGroup"]] = relationship(  # noqa: F821
        cascade="all, delete-orphan"
    )

    @property
    def role_ids(self) -> list[uuid.UUID]:
        return [ur.role_id for ur in self.user_roles]

    @property
    def name(self) -> str:
        """Display name — sourced from the related ``Person`` when available."""
        person = self.person
        if person is not None and person.name:
            return person.name
        return (self.email or self.access_code or "").split("@")[0]


class Module(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "modules"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Whether the module controls scope by Company/Unity (see spec section 3).
    control_company_unity: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    resources: Mapped[list["Resource"]] = relationship(  # noqa: F821
        cascade="all, delete-orphan"
    )


class TenantModule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tenant_modules"
    __table_args__ = (
        UniqueConstraint("tenant_id", "module_id", name="uq_tenant_modules"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    enabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    tenant: Mapped["Tenant"] = relationship(back_populates="modules")
    module: Mapped["Module"] = relationship()


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_roles_tenant_code"),
    )

    # A role may be tenant-scoped (tenant_id set) or a system role (NULL) that can
    # be granted to any tenant's users.
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    module_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("modules.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    module: Mapped["Module | None"] = relationship()
    role_permissions: Mapped[list["RolePermission"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    role_modules: Mapped[list["RoleModule"]] = relationship(
        back_populates="role", cascade="all, delete-orphan"
    )
    role_policies: Mapped[list["RolePolicy"]] = relationship(  # noqa: F821
        cascade="all, delete-orphan"
    )


class Permission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    module_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("modules.id", ondelete="SET NULL")
    )
    description: Mapped[str | None] = mapped_column(Text)

    module: Mapped["Module | None"] = relationship()


class RoleModule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Explicit role -> module association (a role belongs to a module)."""

    __tablename__ = "role_modules"
    __table_args__ = (UniqueConstraint("role_id", "module_id", name="uq_role_modules"),)

    role_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    module_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )

    role: Mapped["Role"] = relationship(back_populates="role_modules")
    module: Mapped["Module"] = relationship()


class RolePermission(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permissions"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        nullable=False,
    )

    role: Mapped["Role"] = relationship(back_populates="role_permissions")
    permission: Mapped["Permission"] = relationship()


class UserRole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_roles"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="user_roles")
    role: Mapped["Role"] = relationship()


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_tenant_created", "tenant_id", "created_at"),
        Index("ix_audit_logs_action", "action"),
    )

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource: Mapped[str | None] = mapped_column(String(128))
    resource_id: Mapped[str | None] = mapped_column(String(128))
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RefreshToken(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_user", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # SHA256 hash of the raw refresh token (never store the raw value).
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(Text)
