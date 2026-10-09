"""Advanced RBAC ORM models: Module → Resource → Policies (section 3).

Three independent grant paths lead to a ``Resource`` + ``AccessPolicy``:

1. ``UserPolicy``  — direct User → Resource grant, optionally scoped to a
   ``Company``/``Unity``.
2. ``GroupPolicy`` — a ``Group`` aggregates policies; users join the group via
   ``UserGroup`` (optionally scoped to a Company/Unity).
3. ``RolePolicy``  — binds a ``Role`` (a set of resources) to a User/Tenant with
   an optional Company/Unity scope. Resources coming from a Role are strictly
   ``ALLOWED`` (a role never denies).

The UI menu is also attached to the required resources:
``Menu`` → ``MenuItem`` → ``MenuItemResource`` → ``Resource``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

# Policy decision values (mirrors the spec's Allowed/Denied).
POLICY_ALLOWED = "ALLOWED"
POLICY_DENIED = "DENIED"


class Resource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Atomic authorization target belonging to a ``Module`` (1-N).

    ``code`` follows the ``"modulo:acao"`` convention (e.g. ``marcas:user``).
    ``control_company_unity`` lets a single resource be scoped by Company/Unity
    independently of the parent module.
    """

    __tablename__ = "resources"
    __table_args__ = (
        UniqueConstraint("code", name="uq_resources_code"),
        Index("ix_resources_module", "module_id"),
    )

    module_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_native: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    control_company_unity: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    module: Mapped["Module"] = relationship(back_populates="resources")  # noqa: F821
    role_policies: Mapped[list["RolePolicy"]] = relationship(
        back_populates="resource", cascade="all, delete-orphan"
    )


class RolePolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Role → Resource grant, optionally scoped to Company/Unity.

    Resources coming from a Role are strictly ``ALLOWED`` — the ``decision``
    column exists for consistency with the other policy tables and is always
    ``ALLOWED`` here.
    """

    __tablename__ = "role_policies"
    __table_args__ = (
        UniqueConstraint(
            "role_id",
            "resource_id",
            "user_id",
            "company_id",
            "unity_id",
            name="uq_role_policies_scope",
        ),
        Index("ix_role_policies_role", "role_id"),
        Index("ix_role_policies_user", "user_id"),
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    # Optional user binding: the role policy applies to this user specifically.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    unity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("unities.id", ondelete="CASCADE")
    )
    decision: Mapped[str] = mapped_column(
        String(16), default=POLICY_ALLOWED, nullable=False
    )

    role: Mapped["Role"] = relationship(back_populates="role_policies")  # noqa: F821
    resource: Mapped["Resource"] = relationship(back_populates="role_policies")


class UserPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Direct User → Resource grant/deny with optional Company/Unity scope."""

    __tablename__ = "user_policies"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "resource_id",
            "company_id",
            "unity_id",
            name="uq_user_policies_scope",
        ),
        Index("ix_user_policies_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    unity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("unities.id", ondelete="CASCADE")
    )
    # ``ALLOWED`` or ``DENIED``.
    decision: Mapped[str] = mapped_column(
        String(16), default=POLICY_ALLOWED, nullable=False
    )

    resource: Mapped["Resource"] = relationship()


class Group(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Tenant-scoped group of users (agregador de políticas)."""

    __tablename__ = "groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_groups_tenant_code"),
        Index("ix_groups_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship()  # noqa: F821
    group_policies: Mapped[list["GroupPolicy"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    user_groups: Mapped[list["UserGroup"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class GroupPolicy(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Group → Resource grant/deny with optional Company/Unity scope."""

    __tablename__ = "group_policies"
    __table_args__ = (
        UniqueConstraint(
            "group_id",
            "resource_id",
            "company_id",
            "unity_id",
            name="uq_group_policies_scope",
        ),
        Index("ix_group_policies_group", "group_id"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    unity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("unities.id", ondelete="CASCADE")
    )
    decision: Mapped[str] = mapped_column(
        String(16), default=POLICY_ALLOWED, nullable=False
    )

    group: Mapped["Group"] = relationship(back_populates="group_policies")
    resource: Mapped["Resource"] = relationship()


class UserGroup(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """User ↔ Group membership, optionally scoped to Company/Unity."""

    __tablename__ = "user_groups"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "group_id", "company_id", "unity_id", name="uq_user_groups_scope"
        ),
        Index("ix_user_groups_user", "user_id"),
        Index("ix_user_groups_group", "group_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    group_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    unity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("unities.id", ondelete="CASCADE")
    )

    group: Mapped["Group"] = relationship(back_populates="user_groups")


# --- UI Menu -----------------------------------------------------------------


class Menu(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A named UI menu (e.g. the main sidebar)."""

    __tablename__ = "menus"
    __table_args__ = (UniqueConstraint("code", name="uq_menus_code"),)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    items: Mapped[list["MenuItem"]] = relationship(
        back_populates="menu", cascade="all, delete-orphan"
    )


class MenuItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A menu entry (``Menu`` 1-N), optionally nested under a parent item."""

    __tablename__ = "menu_items"
    __table_args__ = (Index("ix_menu_items_menu", "menu_id"),)

    menu_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("menus.id", ondelete="CASCADE"), nullable=False
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("menu_items.id", ondelete="CASCADE")
    )
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    route: Mapped[str | None] = mapped_column(String(255))
    icon: Mapped[str | None] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    menu: Mapped["Menu"] = relationship(back_populates="items")
    item_resources: Mapped[list["MenuItemResource"]] = relationship(
        back_populates="menu_item", cascade="all, delete-orphan"
    )


class MenuItemResource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """``MenuItem`` → ``Resource`` requirement: which resource a menu entry needs."""

    __tablename__ = "menu_item_resources"
    __table_args__ = (
        UniqueConstraint("menu_item_id", "resource_id", name="uq_menu_item_resources"),
    )

    menu_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("menu_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    resource_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False
    )

    menu_item: Mapped["MenuItem"] = relationship(back_populates="item_resources")
    resource: Mapped["Resource"] = relationship()


# --- Identity: User ↔ Tenant / Company / Unity -------------------------------


class UserTenant(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """N-N association linking a ``User`` to the tenants they may access."""

    __tablename__ = "user_tenants"
    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="uq_user_tenants"),
        Index("ix_user_tenants_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class UserCompanyUnity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Effective lotação: ``User`` × ``Company`` × ``Unity``."""

    __tablename__ = "user_company_unity"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "company_id", "unity_id", name="uq_user_company_unity"
        ),
        Index("ix_user_company_unity_user", "user_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    unity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("unities.id", ondelete="CASCADE")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class GutRange(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Abstract Gut range (faixa GUT) — tenant-scoped reference table."""

    __tablename__ = "gut_ranges"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_gut_ranges_tenant_code"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    start_value: Mapped[int | None] = mapped_column(Integer)
    end_value: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Department(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Tenant-scoped organisational department (Departamento)."""

    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_departments_tenant_code"),
        Index("ix_departments_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# --- Selective monitoring (section 4) ---------------------------------------


class MarcaMonitoramento(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Selective monitoring of a single marca.

    Monitoring is NEVER global/automatic: a row exists only while the user keeps
    that specific marca under watch (see ``routers/marcas.py``).
    """

    __tablename__ = "marcas_monitoramento"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "codigo_interno", name="uq_marcas_monitoramento_tenant_codigo"
        ),
        Index("ix_marcas_monitoramento_tenant", "tenant_id"),
        Index("ix_marcas_monitoramento_codigo", "codigo_interno"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Logical reference to ``marcas.codigo_interno`` (the INPI process code).
    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    monitored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PatenteMonitoramento(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Selective monitoring of a single patente (mirror of the marca table)."""

    __tablename__ = "patentes_monitoramento"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "codigo_interno", name="uq_patentes_monitoramento_tenant_codigo"
        ),
        Index("ix_patentes_monitoramento_tenant", "tenant_id"),
        Index("ix_patentes_monitoramento_codigo", "codigo_interno"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    monitored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


