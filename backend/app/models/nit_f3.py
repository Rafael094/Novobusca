"""NIT phase F3 ORM models — technology transfer, negotiations and contracts.

Conventions (same invariants as F1/F2):

* every entity is tenant-scoped and carries the standard mixins;
* monetary values use ``Numeric(18, 2)`` (Decimal) — NEVER floating point;
* registered contract/royalty amounts and received amounts are DISTINCT columns;
* the negotiation pipeline NEVER mutates a contract's legal status;
* contractual documents reuse the confidential document module (F1).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

# --- Vocabularies -----------------------------------------------------------

OFFER_STATUS_DRAFT = "DRAFT"
OFFER_STATUS_PUBLISHED = "PUBLISHED"
OFFER_STATUS_SUSPENDED = "SUSPENDED"
OFFER_STATUS_CLOSED = "CLOSED"
OFFER_STATUSES: tuple[str, ...] = (
    OFFER_STATUS_DRAFT,
    OFFER_STATUS_PUBLISHED,
    OFFER_STATUS_SUSPENDED,
    OFFER_STATUS_CLOSED,
)

TRANSFER_MODALITIES: tuple[str, ...] = (
    "LICENSING",
    "ASSIGNMENT",
    "CO_DEVELOPMENT",
    "SERVICE",
    "OTHER",
)

INTEREST_STATUS_NEW = "NEW"
INTEREST_STATUS_QUALIFYING = "QUALIFYING"
INTEREST_STATUS_IN_NEGOTIATION = "IN_NEGOTIATION"
INTEREST_STATUS_DECLINED = "DECLINED"
INTEREST_STATUS_CONVERTED = "CONVERTED"
INTEREST_STATUSES: tuple[str, ...] = (
    INTEREST_STATUS_NEW,
    INTEREST_STATUS_QUALIFYING,
    INTEREST_STATUS_IN_NEGOTIATION,
    INTEREST_STATUS_DECLINED,
    INTEREST_STATUS_CONVERTED,
)

# Negotiation pipeline stages (configurable order; the engine validates edges).
NEG_STAGE_NEW = "NEW"
NEG_STAGE_QUALIFICATION = "QUALIFICATION"
NEG_STAGE_FIRST_CONTACT = "FIRST_CONTACT"
NEG_STAGE_TECHNICAL = "TECHNICAL_DISCUSSION"
NEG_STAGE_NEGOTIATION = "NEGOTIATION"
NEG_STAGE_APPROVAL = "APPROVAL"
NEG_STAGE_CONTRACTING = "CONTRACTING"
NEG_STAGE_CLOSED = "CLOSED"
NEG_STAGES: tuple[str, ...] = (
    NEG_STAGE_NEW,
    NEG_STAGE_QUALIFICATION,
    NEG_STAGE_FIRST_CONTACT,
    NEG_STAGE_TECHNICAL,
    NEG_STAGE_NEGOTIATION,
    NEG_STAGE_APPROVAL,
    NEG_STAGE_CONTRACTING,
    NEG_STAGE_CLOSED,
)
NEG_TERMINAL: frozenset[str] = frozenset({NEG_STAGE_CLOSED})

LICENSE_TYPES: tuple[str, ...] = ("LICENSE", "ASSIGNMENT")

CONTRACT_STATUS_DRAFT = "DRAFT"
CONTRACT_STATUS_ACTIVE = "ACTIVE"
CONTRACT_STATUS_EXPIRED = "EXPIRED"
CONTRACT_STATUS_TERMINATED = "TERMINATED"
CONTRACT_STATUSES: tuple[str, ...] = (
    CONTRACT_STATUS_DRAFT,
    CONTRACT_STATUS_ACTIVE,
    CONTRACT_STATUS_EXPIRED,
    CONTRACT_STATUS_TERMINATED,
)

OBLIGATION_STATUS_PENDING = "PENDING"
OBLIGATION_STATUS_DONE = "DONE"
OBLIGATION_STATUS_LATE = "LATE"
OBLIGATION_STATUS_WAIVED = "WAIVED"
OBLIGATION_STATUSES: tuple[str, ...] = (
    OBLIGATION_STATUS_PENDING,
    OBLIGATION_STATUS_DONE,
    OBLIGATION_STATUS_LATE,
    OBLIGATION_STATUS_WAIVED,
)
OBLIGATION_KINDS: tuple[str, ...] = (
    "DELIVERY",
    "PAYMENT",
    "REPORT",
    "TRAINING",
    "COMPLIANCE",
    "OTHER",
)

PARTY_ROLES: tuple[str, ...] = ("LICENSOR", "LICENSEE", "ASSIGNOR", "ASSIGNEE", "OTHER")


class TechnologyOffer(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A technology available for transfer (public-facing catalog item).

    Only ``PUBLISHED`` offers reach the public catalog. Internal documents and
    confidential data never appear here: the public description is an explicit,
    approved field.
    """

    __tablename__ = "technology_offers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_technology_offers_tenant_code"),
        Index("ix_technology_offers_tenant", "tenant_id"),
        Index("ix_technology_offers_status", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ip_assets.id", ondelete="SET NULL")
    )
    unity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("unities.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    public_summary: Mapped[str | None] = mapped_column(Text)
    technology_area: Mapped[str | None] = mapped_column(String(128))
    maturity: Mapped[str | None] = mapped_column(String(64))
    modality: Mapped[str] = mapped_column(String(32), default="LICENSING", nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    conditions: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default=OFFER_STATUS_DRAFT, nullable=False)
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    asset: Mapped["IPAsset | None"] = relationship()  # noqa: F821
    interests: Mapped[list["ExpressionOfInterest"]] = relationship(
        back_populates="offer"
    )


class ExpressionOfInterest(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A company's/partner's expression of interest in an offered technology."""

    __tablename__ = "expressions_of_interest"
    __table_args__ = (
        Index("ix_interest_tenant", "tenant_id"),
        Index("ix_interest_offer", "offer_id"),
        Index("ix_interest_status", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("technology_offers.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_document: Mapped[str | None] = mapped_column(String(32))
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(32))
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default=INTEREST_STATUS_NEW, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    offer: Mapped["TechnologyOffer"] = relationship(back_populates="interests")
    negotiations: Mapped[list["Negotiation"]] = relationship(back_populates="interest")


class InterestInteraction(UUIDPrimaryKeyMixin, Base):
    """Append-only interaction log for an expression of interest."""

    __tablename__ = "interest_interactions"
    __table_args__ = (
        Index("ix_interest_interactions_interest", "interest_id", "created_at"),
        Index("ix_interest_interactions_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    interest_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("expressions_of_interest.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Negotiation(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A negotiation derived from an expression of interest.

    The stage is advanced ONLY through the declared pipeline edges (validated by
    the router). Advancing a negotiation NEVER changes a contract's legal status.
    """

    __tablename__ = "negotiations"
    __table_args__ = (
        Index("ix_negotiations_tenant", "tenant_id"),
        Index("ix_negotiations_interest", "interest_id"),
        Index("ix_negotiations_stage", "stage"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    interest_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("expressions_of_interest.id", ondelete="SET NULL"),
    )
    offer_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("technology_offers.id", ondelete="SET NULL"),
    )
    stage: Mapped[str] = mapped_column(String(24), default=NEG_STAGE_NEW, nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    next_step: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    interest: Mapped["ExpressionOfInterest | None"] = relationship(
        back_populates="negotiations"
    )
    history: Mapped[list["NegotiationHistory"]] = relationship(
        back_populates="negotiation", cascade="all, delete-orphan"
    )


class NegotiationHistory(UUIDPrimaryKeyMixin, Base):
    """Append-only stage history of a negotiation."""

    __tablename__ = "negotiation_history"
    __table_args__ = (
        Index("ix_negotiation_history_neg", "negotiation_id", "created_at"),
        Index("ix_negotiation_history_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    negotiation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("negotiations.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_stage: Mapped[str | None] = mapped_column(String(24))
    to_stage: Mapped[str] = mapped_column(String(24), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    justification: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    negotiation: Mapped["Negotiation"] = relationship(back_populates="history")


class License(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A license or assignment instrument formalising a transfer."""

    __tablename__ = "licenses"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_licenses_tenant_code"),
        Index("ix_licenses_tenant", "tenant_id"),
        Index("ix_licenses_asset", "asset_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    license_type: Mapped[str] = mapped_column(String(16), default="LICENSE", nullable=False)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ip_assets.id", ondelete="SET NULL")
    )
    negotiation_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("negotiations.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    exclusive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    start_date: Mapped[datetime | None] = mapped_column(Date)
    end_date: Mapped[datetime | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Contract(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A technology-transfer contract (and its amendments).

    ``status`` is the LEGAL state and is changed only by an explicit contract
    operation — never by the negotiation pipeline. ``registered_amount`` is what
    was agreed; received values are tracked on ``Royalty`` (distinct).
    """

    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_contracts_tenant_code"),
        Index("ix_contracts_tenant", "tenant_id"),
        Index("ix_contracts_license", "license_id"),
        Index("ix_contracts_status", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    license_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("licenses.id", ondelete="SET NULL")
    )
    parent_contract_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=CONTRACT_STATUS_DRAFT, nullable=False)
    is_amendment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    signed_at: Mapped[datetime | None] = mapped_column(Date)
    effective_from: Mapped[datetime | None] = mapped_column(Date)
    effective_until: Mapped[datetime | None] = mapped_column(Date)
    registered_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL", nullable=False)
    conditions: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    parties: Mapped[list["ContractParty"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    obligations: Mapped[list["ContractObligation"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )
    royalties: Mapped[list["Royalty"]] = relationship(
        back_populates="contract", cascade="all, delete-orphan"
    )


class ContractParty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A party of a contract (with its role)."""

    __tablename__ = "contract_parties"
    __table_args__ = (Index("ix_contract_parties_contract", "contract_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(16), default="OTHER", nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    document: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(255))
    representative: Mapped[str | None] = mapped_column(String(255))

    contract: Mapped["Contract"] = relationship(back_populates="parties")


class ContractObligation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An obligation arising from a contract (delivery, payment, report...)."""

    __tablename__ = "contract_obligations"
    __table_args__ = (
        Index("ix_contract_obligations_contract", "contract_id"),
        Index("ix_contract_obligations_due", "due_date"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), default="OTHER", nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(16), default=OBLIGATION_STATUS_PENDING, nullable=False
    )
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    evidence: Mapped[str | None] = mapped_column(Text)
    fulfilled_at: Mapped[datetime | None] = mapped_column(Date)

    contract: Mapped["Contract"] = relationship(back_populates="obligations")


class Royalty(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A royalty entry: expected vs registered vs actually received (all distinct).

    All monetary fields are ``Numeric(18, 2)`` (Decimal) — no floating point.
    """

    __tablename__ = "royalties"
    __table_args__ = (
        Index("ix_royalties_contract", "contract_id"),
        Index("ix_royalties_period", "period"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    period: Mapped[str] = mapped_column(String(16), nullable=False)  # e.g. 2026-01
    expected_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    registered_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    received_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL", nullable=False)
    due_date: Mapped[datetime | None] = mapped_column(Date)
    received_at: Mapped[datetime | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    contract: Mapped["Contract"] = relationship(back_populates="royalties")




