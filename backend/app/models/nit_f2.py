"""NIT phase F2 ORM models — committees, TRL history and portfolio deadlines.

All entities are tenant-scoped (``UUIDPrimaryKeyMixin`` + ``TimestampMixin`` +
``SoftDeleteMixin`` + ``tenant_id``) following the F1 invariants.

Design notes:

* ``TechnologyReadinessLevel`` (TRL) changes are **never automatic**: a level is
  recorded only by a human evaluator together with a justification and evidence.
* Committees keep members with a validity window; a member who declared a conflict
  of interest is recorded with ``conflict_of_interest=True`` and cannot vote on the
  affected item (enforced in the service layer).
* ``CommitteeDecision`` is append-only: the final decision of an item.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Date,
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

# --- Controlled vocabularies ------------------------------------------------

COMMITTEE_STATUS_ACTIVE = "ACTIVE"
COMMITTEE_STATUS_INACTIVE = "INACTIVE"
COMMITTEE_STATUSES: tuple[str, ...] = (COMMITTEE_STATUS_ACTIVE, COMMITTEE_STATUS_INACTIVE)

MEETING_STATUS_SCHEDULED = "SCHEDULED"
MEETING_STATUS_HELD = "HELD"
MEETING_STATUS_CANCELLED = "CANCELLED"
MEETING_STATUSES: tuple[str, ...] = (
    MEETING_STATUS_SCHEDULED,
    MEETING_STATUS_HELD,
    MEETING_STATUS_CANCELLED,
)

AGENDA_ITEM_STATUS_PENDING = "PENDING"
AGENDA_ITEM_STATUS_DECIDED = "DECIDED"
AGENDA_ITEM_STATUS_WITHDRAWN = "WITHDRAWN"
AGENDA_ITEM_STATUSES: tuple[str, ...] = (
    AGENDA_ITEM_STATUS_PENDING,
    AGENDA_ITEM_STATUS_DECIDED,
    AGENDA_ITEM_STATUS_WITHDRAWN,
)

# Vote options for a committee member on an agenda item.
VOTE_APPROVE = "APPROVE"
VOTE_REJECT = "REJECT"
VOTE_ABSTAIN = "ABSTAIN"
VOTE_IMPEDED = "IMPEDED"
VOTE_OPTIONS: tuple[str, ...] = (VOTE_APPROVE, VOTE_REJECT, VOTE_ABSTAIN, VOTE_IMPEDED)

DECISION_APPROVED = "APPROVED"
DECISION_REJECTED = "REJECTED"
DECISION_DEFERRED = "DEFERRED"
DECISION_OUTCOMES: tuple[str, ...] = (
    DECISION_APPROVED,
    DECISION_REJECTED,
    DECISION_DEFERRED,
)

COMMITTEE_MEMBER_KINDS: tuple[str, ...] = ("VOTING", "ADVISORY")


class TechnologyReadinessLevel(UUIDPrimaryKeyMixin, Base):
    """Append-only TRL (maturity) history entry for a disclosure or an asset.

    Exactly ONE of ``disclosure_id`` / ``asset_id`` is set. The level is never
    derived automatically — an evaluator records it with a justification and an
    evidence reference (decision: no automatic TRL).
    """

    __tablename__ = "trl_history"
    __table_args__ = (
        Index("ix_trl_history_tenant", "tenant_id"),
        Index("ix_trl_history_disclosure", "disclosure_id"),
        Index("ix_trl_history_asset", "asset_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    disclosure_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invention_disclosures.id", ondelete="CASCADE")
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ip_assets.id", ondelete="CASCADE")
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)  # TRL 1..9
    previous_level: Mapped[int | None] = mapped_column(Integer)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)
    evaluator_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Committee(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A committee (comitê) of the tenant, e.g. the institutional innovation committee."""

    __tablename__ = "committees"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_committees_tenant_code"),
        Index("ix_committees_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), default=COMMITTEE_STATUS_ACTIVE, nullable=False
    )
    # Minimum number of VALID votes required for a decision to be valid.
    quorum: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # Whether an APPROVE outcome requires strictly more approvals than rejections.
    simple_majority: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members: Mapped[list["CommitteeMember"]] = relationship(
        back_populates="committee", cascade="all, delete-orphan"
    )
    meetings: Mapped[list["CommitteeMeeting"]] = relationship(back_populates="committee")


class CommitteeMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A member of a committee with a validity window and a role in the committee."""

    __tablename__ = "committee_members"
    __table_args__ = (
        Index("ix_committee_members_committee", "committee_id"),
        Index("ix_committee_members_user", "user_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    committee_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("committees.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_title: Mapped[str | None] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16), default="VOTING", nullable=False)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    committee: Mapped["Committee"] = relationship(back_populates="members")


class CommitteeMeeting(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A committee meeting (reunião) with its scheduled date and status."""

    __tablename__ = "committee_meetings"
    __table_args__ = (
        Index("ix_committee_meetings_committee", "committee_id"),
        Index("ix_committee_meetings_tenant", "tenant_id"),
        Index("ix_committee_meetings_date", "scheduled_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    committee_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("committees.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    held_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(16), default=MEETING_STATUS_SCHEDULED, nullable=False
    )
    location: Mapped[str | None] = mapped_column(String(255))
    minutes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    committee: Mapped["Committee"] = relationship(back_populates="meetings")
    items: Mapped[list["CommitteeAgendaItem"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )


class CommitteeAgendaItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An item under evaluation in a meeting, linked to a disclosure or an asset."""

    __tablename__ = "committee_agenda_items"
    __table_args__ = (
        Index("ix_committee_agenda_items_meeting", "meeting_id"),
        Index("ix_committee_agenda_items_disclosure", "disclosure_id"),
        Index("ix_committee_agenda_items_asset", "asset_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    meeting_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("committee_meetings.id", ondelete="CASCADE"),
        nullable=False,
    )
    disclosure_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invention_disclosures.id", ondelete="CASCADE")
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ip_assets.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16), default=AGENDA_ITEM_STATUS_PENDING, nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    meeting: Mapped["CommitteeMeeting"] = relationship(back_populates="items")
    votes: Mapped[list["CommitteeVote"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
    decision: Mapped["CommitteeDecision | None"] = relationship(
        back_populates="item", uselist=False, cascade="all, delete-orphan"
    )


class CommitteeVote(UUIDPrimaryKeyMixin, Base):
    """A single member's vote on an agenda item (append-only, one per member).

    ``conflict_of_interest`` marks a member who declared a conflict; such a vote is
    recorded as ``IMPEDED`` and does not count toward the quorum (service-enforced).
    """

    __tablename__ = "committee_votes"
    __table_args__ = (
        UniqueConstraint(
            "item_id", "member_id", name="uq_committee_votes_item_member"
        ),
        Index("ix_committee_votes_item", "item_id"),
        Index("ix_committee_votes_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("committee_agenda_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("committee_members.id", ondelete="CASCADE"),
        nullable=False,
    )
    voter_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    vote: Mapped[str] = mapped_column(String(16), nullable=False)
    conflict_of_interest: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    item: Mapped["CommitteeAgendaItem"] = relationship(back_populates="votes")


class CommitteeDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The final, append-only decision recorded for an agenda item.

    A decision is only persisted when the quorum and majority rules of the parent
    committee are satisfied (enforced by ``services/committee.py``).
    """

    __tablename__ = "committee_decisions"
    __table_args__ = (
        UniqueConstraint("item_id", name="uq_committee_decisions_item"),
        Index("ix_committee_decisions_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("committee_agenda_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    justification: Mapped[str | None] = mapped_column(Text)
    approvals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    abstentions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impeded: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    decided_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    item: Mapped["CommitteeAgendaItem"] = relationship(back_populates="decision")



