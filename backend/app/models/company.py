"""Tenant-scoped company / unity / customer / person ORM models.

These complement the existing authentication tables (``users``) without changing
them: ``users`` keeps credentials & login; ``people`` holds the extra cadastral/
contact data; ``companies`` groups the organisations of a tenant; ``unities``
are the branches/business units of a company; ``customers`` are the tenant's
clients (optionally linked to a company and a person).

Every table is tenant-scoped through ``tenant_id`` (uuid FK to ``tenants``) so
the same isolation guarantees used everywhere else apply here too.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin


class TenantEntityMixin:
    """Mixin for every entity that belongs to a tenant (carries ``tenant_id``).

    The ``Tenant`` root itself does NOT use this mixin — it is the aggregate root
    and therefore has no ``TenantId`` column of its own.
    """

    @property
    def tenant_key(self) -> uuid.UUID:
        return self.tenant_id  # type: ignore[attr-defined]

    def belongs_to(self, tenant_id: uuid.UUID | None) -> bool:
        return tenant_id is None or self.tenant_id == tenant_id  # type: ignore[attr-defined]


class Person(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A natural person (pessoa física) belonging to a tenant.

    This is the ``Person`` aggregate root of the identity model: cadastral data
    (``Name``, ``Cpf``, ``CellPhone``, ``Address``, ``Responsibility``) living
    separately from the pure login credentials in ``users``. The link is a 1:1
    from ``User`` to ``Person`` via ``User.person_id`` (nullable here so a
    person may exist before/without a login account).
    """

    __tablename__ = "people"
    __table_args__ = (
        Index("ix_people_tenant", "tenant_id"),
        Index("ix_people_name", "name"),
        UniqueConstraint("tenant_id", "cpf", name="uq_people_tenant_cpf"),
    )

    # Optional tenant link: Person is an aggregate root; a person may also serve
    # as the profile of a master admin (no tenant required).
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE")
    )
    # 1:1 link to a login account (a person may exist without a user).
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", name="fk_people_user", ondelete="SET NULL"),
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    cpf: Mapped[str | None] = mapped_column(String(14))
    email: Mapped[str | None] = mapped_column(String(255))
    cell_phone: Mapped[str | None] = mapped_column(String(32))
    # Structured address (kept simple/optional).
    address_line: Mapped[str | None] = mapped_column(String(255))
    address_number: Mapped[str | None] = mapped_column(String(32))
    address_complement: Mapped[str | None] = mapped_column(String(128))
    district: Mapped[str | None] = mapped_column(String(128))
    city: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str | None] = mapped_column(String(2))
    zip_code: Mapped[str | None] = mapped_column(String(16))
    responsibility: Mapped[str | None] = mapped_column(String(128))
    job_title: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship()  # noqa: F821
    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])  # noqa: F821



class Company(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantEntityMixin, Base):
    """A legal entity (empresa) belonging to a tenant (aggregate root).

    ``external_id`` is an optional ERP/legacy correlation key, unique per tenant.
    ``file_document`` stores the reference to the company's constitutive document
    (path/URL) — never the binary itself.
    """

    __tablename__ = "companies"
    __table_args__ = (
        Index("ix_companies_tenant", "tenant_id"),
        Index("ix_companies_company_name", "company_name"),
        UniqueConstraint("tenant_id", "external_id", name="uq_companies_tenant_external"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(64))
    file_document: Mapped[str | None] = mapped_column(Text)
    social_reason: Mapped[str | None] = mapped_column(String(255))
    cnpj: Mapped[str | None] = mapped_column(String(18))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship(back_populates="companies")  # noqa: F821
    customers: Mapped[list["Customer"]] = relationship(back_populates="company")
    unities: Mapped[list["Unity"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class Unity(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantEntityMixin, Base):
    """A branch / business unit (filial ou unidade) of a ``Company``.

    ``company_id`` points to ``Company``; ``matriz_type`` distinguishes the head
    office (``MATRIZ``) from branches (``FILIAL``).
    """

    __tablename__ = "unities"
    __table_args__ = (
        Index("ix_unities_tenant", "tenant_id"),
        Index("ix_unities_company", "company_id"),
        UniqueConstraint("tenant_id", "cnpj", name="uq_unities_tenant_cnpj"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    social_reason: Mapped[str | None] = mapped_column(String(255))
    cnpj: Mapped[str | None] = mapped_column(String(18))
    # ``MATRIZ`` (head office) or ``FILIAL`` (branch).
    matriz_type: Mapped[str] = mapped_column(String(16), default="FILIAL", nullable=False)
    cnes: Mapped[str | None] = mapped_column(String(32))
    sanitary_license: Mapped[str | None] = mapped_column(String(64))
    opening_hours: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    address_line: Mapped[str | None] = mapped_column(String(255))
    address_number: Mapped[str | None] = mapped_column(String(32))
    address_complement: Mapped[str | None] = mapped_column(String(128))
    district: Mapped[str | None] = mapped_column(String(128))
    city: Mapped[str | None] = mapped_column(String(128))
    state: Mapped[str | None] = mapped_column(String(2))
    zip_code: Mapped[str | None] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship()  # noqa: F821
    company: Mapped["Company"] = relationship(back_populates="unities")


class Customer(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, TenantEntityMixin, Base):
    """A tenant's client, optionally attached to a ``Company``/``Unity``/``Person``."""

    __tablename__ = "customers"
    __table_args__ = (
        Index("ix_customers_tenant", "tenant_id"),
        Index("ix_customers_company", "company_id"),
        UniqueConstraint("tenant_id", "code", name="uq_customers_tenant_code"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL")
    )
    unity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("unities.id", ondelete="SET NULL")
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL")
    )
    code: Mapped[str | None] = mapped_column(String(64))  # internal tenant code
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    document: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship()  # noqa: F821
    company: Mapped["Company | None"] = relationship(back_populates="customers")
    unity: Mapped["Unity | None"] = relationship()
    person: Mapped["Person | None"] = relationship()
