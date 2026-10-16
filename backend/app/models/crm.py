"""Tenant-scoped commercial CRM models: opportunities, proposals and activities.

This module completes the IntelliINPI commercial layer on top of the entities
that already exist (``Customer``, ``Company``, ``Person``, ``Unity``). It does
NOT introduce a second notion of "client": a won opportunity links to a
``Customer`` row, either an existing one (choice) or one created by the
conversion flow (see ``app/services/crm.py``).

Lifecycle
---------
``CrmOpportunity``
    A lead / business opportunity moving through the commercial funnel:

        NEW -> QUALIFICATION -> PROPOSAL -> SENT -> NEGOTIATION -> WON | LOST

    ``WON`` requires a ``customer_id`` (existing or created by conversion) and
    ``LOST`` requires a ``lost_reason``.

``CrmProposal``
    A commercial proposal, optionally attached to an opportunity and/or a
    customer. Its own lifecycle is independent from the opportunity:

        DRAFT -> PENDING_SEND -> SENT -> AWAITING_REPLY -> NEGOTIATION
              -> APPROVED | REJECTED | EXPIRED | CANCELLED

    Approving a proposal does NOT register a trademark/patent and does NOT
    execute any service — that distinction is preserved on purpose.

``CrmActivity``
    A follow-up / interaction record (call, meeting, e-mail, note, task). It is
    ``subject_type``+``subject_id`` polymorphic so the same timeline works for an
    opportunity, a proposal, a customer or a company.

Every table is tenant-scoped through ``tenant_id`` (uuid FK to ``tenants``), the
same isolation guarantee used by every other tenant entity.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

# --- Vocabulary (single source of truth, mirrored by the frontend) -----------

#: Commercial funnel stages of an opportunity, in display order.
OPPORTUNITY_STAGES: list[str] = [
    "NEW",
    "QUALIFICATION",
    "PROPOSAL",
    "SENT",
    "NEGOTIATION",
    "WON",
    "LOST",
]

#: Human labels for the funnel stages (pt-BR).
OPPORTUNITY_STAGE_LABELS: dict[str, str] = {
    "NEW": "Novo lead",
    "QUALIFICATION": "Qualificação",
    "PROPOSAL": "Preparação da proposta",
    "SENT": "Proposta enviada",
    "NEGOTIATION": "Em negociação",
    "WON": "Aprovada",
    "LOST": "Perdida",
}

#: Allowed opportunity transitions (enforced in the service layer).
OPPORTUNITY_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "NEW": ("QUALIFICATION", "WON", "LOST"),
    "QUALIFICATION": ("PROPOSAL", "NEGOTIATION", "WON", "LOST"),
    "PROPOSAL": ("SENT", "NEGOTIATION", "WON", "LOST"),
    "SENT": ("NEGOTIATION", "WON", "LOST"),
    "NEGOTIATION": ("SENT", "WON", "LOST"),
    "WON": (),
    "LOST": ("QUALIFICATION",),
}

#: Commercial proposal statuses, in display order.
PROPOSAL_STATUSES: list[str] = [
    "DRAFT",
    "PENDING_SEND",
    "SENT",
    "AWAITING_REPLY",
    "NEGOTIATION",
    "APPROVED",
    "REJECTED",
    "EXPIRED",
    "CANCELLED",
]

#: Human labels for the proposal statuses (pt-BR).
PROPOSAL_STATUS_LABELS: dict[str, str] = {
    "DRAFT": "Rascunho",
    "PENDING_SEND": "Pendente de envio",
    "SENT": "Enviada",
    "AWAITING_REPLY": "Aguardando retorno",
    "NEGOTIATION": "Em negociação",
    "APPROVED": "Aprovada",
    "REJECTED": "Recusada",
    "EXPIRED": "Expirada",
    "CANCELLED": "Cancelada",
}

#: Statuses considered "open" (still actionable) by the dashboard.
PROPOSAL_OPEN_STATUSES: tuple[str, ...] = (
    "DRAFT",
    "PENDING_SEND",
    "SENT",
    "AWAITING_REPLY",
    "NEGOTIATION",
)

#: Terminal statuses that no longer require action.
PROPOSAL_CLOSED_STATUSES: tuple[str, ...] = (
    "APPROVED",
    "REJECTED",
    "EXPIRED",
    "CANCELLED",
)

#: Allowed proposal transitions (enforced in the service layer).
PROPOSAL_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "DRAFT": ("PENDING_SEND", "SENT", "CANCELLED"),
    "PENDING_SEND": ("SENT", "DRAFT", "CANCELLED"),
    "SENT": ("AWAITING_REPLY", "NEGOTIATION", "APPROVED", "REJECTED", "CANCELLED"),
    "AWAITING_REPLY": ("NEGOTIATION", "APPROVED", "REJECTED", "EXPIRED", "CANCELLED"),
    "NEGOTIATION": ("AWAITING_REPLY", "APPROVED", "REJECTED", "EXPIRED", "CANCELLED"),
    "APPROVED": ("CANCELLED",),
    "REJECTED": ("NEGOTIATION",),
    "EXPIRED": ("NEGOTIATION",),
    "CANCELLED": (),
}

#: Activity kinds (follow-up types).
ACTIVITY_KINDS: list[str] = ["CALL", "MEETING", "EMAIL", "NOTE", "TASK", "OTHER"]

#: Human labels for the activity kinds (pt-BR).
ACTIVITY_KIND_LABELS: dict[str, str] = {
    "CALL": "Ligação",
    "MEETING": "Reunião",
    "EMAIL": "E-mail / contato",
    "NOTE": "Anotação",
    "TASK": "Tarefa",
    "OTHER": "Outro",
}

#: Activity outcomes.
ACTIVITY_OUTCOMES: list[str] = ["PENDING", "DONE", "NO_ANSWER", "RESCHEDULED"]

#: Human labels for the outcomes (pt-BR).
ACTIVITY_OUTCOME_LABELS: dict[str, str] = {
    "PENDING": "Pendente",
    "DONE": "Concluída",
    "NO_ANSWER": "Sem resposta",
    "RESCHEDULED": "Reagendada",
}

#: Polymorphic targets supported by ``CrmActivity.subject_type``.
ACTIVITY_SUBJECT_TYPES: tuple[str, ...] = (
    "OPPORTUNITY",
    "PROPOSAL",
    "CUSTOMER",
    "COMPANY",
)

#: Commercial origins (how the contact arrived).
OPPORTUNITY_SOURCES: list[str] = [
    "INBOUND",
    "OUTBOUND",
    "REFERRAL",
    "EVENT",
    "PARTNER",
    "WEBSITE",
    "OTHER",
]

#: Human labels for the origins (pt-BR).
OPPORTUNITY_SOURCE_LABELS: dict[str, str] = {
    "INBOUND": "Contato recebido",
    "OUTBOUND": "Prospecção ativa",
    "REFERRAL": "Indicação",
    "EVENT": "Evento",
    "PARTNER": "Parceiro",
    "WEBSITE": "Site",
    "OTHER": "Outro",
}


class CrmOpportunity(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A lead / commercial opportunity moving through the tenant's funnel."""

    __tablename__ = "crm_opportunities"
    __table_args__ = (
        Index("ix_crm_opportunities_tenant", "tenant_id"),
        Index("ix_crm_opportunities_stage", "tenant_id", "stage"),
        Index("ix_crm_opportunities_customer", "customer_id"),
        Index("ix_crm_opportunities_owner", "owner_id"),
        UniqueConstraint("tenant_id", "code", name="uq_crm_opportunities_tenant_code"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    #: Short human-readable code, unique per tenant (e.g. ``OPP-000123``).
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    #: Display name of the lead/organisation while it is not yet a customer.
    lead_name: Mapped[str | None] = mapped_column(String(255))
    #: Contact person of the lead (optional link to the identity model).
    contact_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL")
    )
    #: Set once the opportunity is won/converted (never a second "customer" row).
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL")
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL")
    )
    #: Commercial owner (the user responsible for the deal).
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    stage: Mapped[str] = mapped_column(String(32), default="NEW", nullable=False)
    source: Mapped[str | None] = mapped_column(String(32))
    #: Service of interest (free text; no product catalogue exists yet).
    service_interest: Mapped[str | None] = mapped_column(String(255))
    estimated_value: Mapped[object | None] = mapped_column(Numeric(18, 2))
    #: 0-100; only persisted when the operator actually enters it.
    probability: Mapped[int | None] = mapped_column()
    next_action: Mapped[str | None] = mapped_column(String(255))
    next_action_at: Mapped[object | None] = mapped_column(Date)
    expected_close_at: Mapped[object | None] = mapped_column(Date)
    lost_reason: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship()  # noqa: F821
    customer: Mapped["Customer | None"] = relationship()  # noqa: F821
    contact: Mapped["Person | None"] = relationship()  # noqa: F821
    proposals: Mapped[list["CrmProposal"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )


class CrmProposal(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A commercial proposal, optionally linked to an opportunity and customer."""

    __tablename__ = "crm_proposals"
    __table_args__ = (
        Index("ix_crm_proposals_tenant", "tenant_id"),
        Index("ix_crm_proposals_status", "tenant_id", "status"),
        Index("ix_crm_proposals_opportunity", "opportunity_id"),
        Index("ix_crm_proposals_customer", "customer_id"),
        UniqueConstraint("tenant_id", "code", name="uq_crm_proposals_tenant_code"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    #: Services offered (free text; the UI stores one per line).
    services: Mapped[str | None] = mapped_column(Text)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("crm_opportunities.id", ondelete="SET NULL")
    )
    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL")
    )
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", nullable=False)
    total_value: Mapped[object | None] = mapped_column(Numeric(18, 2))
    sent_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[object | None] = mapped_column(Date)
    #: Last time a reply from the prospect was registered.
    replied_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    decision_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    decision_notes: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship()  # noqa: F821
    opportunity: Mapped["CrmOpportunity | None"] = relationship(back_populates="proposals")
    customer: Mapped["Customer | None"] = relationship()  # noqa: F821


class CrmActivity(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A follow-up / interaction linked polymorphically to a CRM subject."""

    __tablename__ = "crm_activities"
    __table_args__ = (
        Index("ix_crm_activities_tenant", "tenant_id"),
        Index("ix_crm_activities_subject", "tenant_id", "subject_type", "subject_id"),
        Index("ix_crm_activities_due", "tenant_id", "due_at"),
        Index("ix_crm_activities_owner", "owner_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), default="NOTE", nullable=False)
    subject_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    #: When the interaction happened (may be in the future for scheduled tasks).
    occurred_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    tenant: Mapped["Tenant"] = relationship()  # noqa: F821


__all__ = [
    "ACTIVITY_KINDS",
    "ACTIVITY_KIND_LABELS",
    "ACTIVITY_OUTCOMES",
    "ACTIVITY_OUTCOME_LABELS",
    "ACTIVITY_SUBJECT_TYPES",
    "CrmActivity",
    "CrmOpportunity",
    "CrmProposal",
    "OPPORTUNITY_SOURCES",
    "OPPORTUNITY_SOURCE_LABELS",
    "OPPORTUNITY_STAGES",
    "OPPORTUNITY_STAGE_LABELS",
    "OPPORTUNITY_TRANSITIONS",
    "PROPOSAL_CLOSED_STATUSES",
    "PROPOSAL_OPEN_STATUSES",
    "PROPOSAL_STATUSES",
    "PROPOSAL_STATUS_LABELS",
    "PROPOSAL_TRANSITIONS",
]



