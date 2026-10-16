"""NIT phase F4 ORM models — R&D projects, startups/spin-offs and incubation.

Conventions (same invariants as F1–F3): tenant-scoped, standard mixins, monetary
values in ``Numeric(18, 2)``. Financing amounts are only stored when a real source
provides them — the system NEVER invents funding values.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

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
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

# --- Vocabularies -----------------------------------------------------------

PROJECT_STATUS_PLANNED = "PLANNED"
PROJECT_STATUS_ACTIVE = "ACTIVE"
PROJECT_STATUS_COMPLETED = "COMPLETED"
PROJECT_STATUS_CANCELLED = "CANCELLED"
PROJECT_STATUSES: tuple[str, ...] = (
    PROJECT_STATUS_PLANNED,
    PROJECT_STATUS_ACTIVE,
    PROJECT_STATUS_COMPLETED,
    PROJECT_STATUS_CANCELLED,
)

PROJECT_MEMBER_ROLES: tuple[str, ...] = (
    "COORDINATOR",
    "RESEARCHER",
    "SCHOLARSHIP_HOLDER",
    "TECHNICIAN",
    "PARTNER",
    "OTHER",
)

MILESTONE_STATUS_PENDING = "PENDING"
MILESTONE_STATUS_DONE = "DONE"
MILESTONE_STATUS_LATE = "LATE"
MILESTONE_STATUSES: tuple[str, ...] = (
    MILESTONE_STATUS_PENDING,
    MILESTONE_STATUS_DONE,
    MILESTONE_STATUS_LATE,
)

PROJECT_ASSET_RELATIONS: tuple[str, ...] = (
    "ORIGIN",
    "RESULT",
    "RELATED",
)

STARTUP_STATUS_IDEATION = "IDEATION"
STARTUP_STATUS_INCUBATED = "INCUBATED"
STARTUP_STATUS_GRADUATED = "GRADUATED"
STARTUP_STATUS_ACTIVE = "ACTIVE"
STARTUP_STATUS_CLOSED = "CLOSED"
STARTUP_STATUSES: tuple[str, ...] = (
    STARTUP_STATUS_IDEATION,
    STARTUP_STATUS_INCUBATED,
    STARTUP_STATUS_GRADUATED,
    STARTUP_STATUS_ACTIVE,
    STARTUP_STATUS_CLOSED,
)

INCUBATION_STAGE_STATUSES: tuple[str, ...] = (
    "PLANNED",
    "IN_PROGRESS",
    "COMPLETED",
    "DROPPED",
)


class Project(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """An R&D project (projeto de pesquisa e desenvolvimento) of the NIT."""

    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_projects_tenant_code"),
        Index("ix_projects_tenant", "tenant_id"),
        Index("ix_projects_status", "status"),
        Index("ix_projects_unity", "unity_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    unity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("unities.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    objective: Mapped[str | None] = mapped_column(Text)
    technology_area: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default=PROJECT_STATUS_PLANNED, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    coordinator_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members: Mapped[list["ProjectMember"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    funders: Mapped[list["ProjectFunder"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    milestones: Mapped[list["ProjectMilestone"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    asset_links: Mapped[list["ProjectAssetLink"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A member of a project team."""

    __tablename__ = "project_members"
    __table_args__ = (Index("ix_project_members_project", "project_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(24), default="RESEARCHER", nullable=False)
    institution: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="members")


class ProjectFunder(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A funding source of a project (amount only when a real source provides it)."""

    __tablename__ = "project_funders"
    __table_args__ = (Index("ix_project_funders_project", "project_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    document: Mapped[str | None] = mapped_column(String(32))
    instrument: Mapped[str | None] = mapped_column(String(128))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="funders")


class ProjectMilestone(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A project milestone/deliverable with an optional due date."""

    __tablename__ = "project_milestones"
    __table_args__ = (
        Index("ix_project_milestones_project", "project_id"),
        Index("ix_project_milestones_due", "due_date"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(
        String(16), default=MILESTONE_STATUS_PENDING, nullable=False
    )
    completed_at: Mapped[date | None] = mapped_column(Date)

    project: Mapped["Project"] = relationship(back_populates="milestones")


class ProjectAssetLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """N:N link between a project and an institutional asset (with a relation kind)."""

    __tablename__ = "project_asset_links"
    __table_args__ = (
        UniqueConstraint("project_id", "asset_id", name="uq_project_asset_links_pair"),
        Index("ix_project_asset_links_project", "project_id"),
        Index("ix_project_asset_links_asset", "asset_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ip_assets.id", ondelete="CASCADE"), nullable=False
    )
    relation: Mapped[str] = mapped_column(String(16), default="RESULT", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    project: Mapped["Project"] = relationship(back_populates="asset_links")


class Startup(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A startup or spin-off related to a project/asset.

    Being linked to an asset does NOT make the startup its owner — ownership is a
    separate legal relation and is never inferred here.
    """

    __tablename__ = "startups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_startups_tenant_code"),
        Index("ix_startups_tenant", "tenant_id"),
        Index("ix_startups_status", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cnpj: Mapped[str | None] = mapped_column(String(18))
    status: Mapped[str] = mapped_column(String(16), default=STARTUP_STATUS_IDEATION, nullable=False)
    stage: Mapped[str | None] = mapped_column(String(64))
    founded_at: Mapped[date | None] = mapped_column(Date)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL")
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ip_assets.id", ondelete="SET NULL")
    )
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    members: Mapped[list["StartupMember"]] = relationship(
        back_populates="startup", cascade="all, delete-orphan"
    )
    incubations: Mapped[list["IncubationParticipation"]] = relationship(
        back_populates="startup", cascade="all, delete-orphan"
    )


class StartupMember(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A founder/team member of a startup."""

    __tablename__ = "startup_members"
    __table_args__ = (Index("ix_startup_members_startup", "startup_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("startups.id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(64))
    is_founder: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    startup: Mapped["Startup"] = relationship(back_populates="members")


class IncubationProgram(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """An incubation program run by the institution."""

    __tablename__ = "incubation_programs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_incubation_programs_tenant_code"),
        Index("ix_incubation_programs_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    criteria: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    participations: Mapped[list["IncubationParticipation"]] = relationship(
        back_populates="program", cascade="all, delete-orphan"
    )


class IncubationParticipation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A startup's participation in an incubation program, with tracked stages."""

    __tablename__ = "incubation_participations"
    __table_args__ = (
        UniqueConstraint(
            "program_id", "startup_id", name="uq_incubation_participations_pair"
        ),
        Index("ix_incubation_participations_program", "program_id"),
        Index("ix_incubation_participations_startup", "startup_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    program_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("incubation_programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    startup_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("startups.id", ondelete="CASCADE"), nullable=False
    )
    entry_date: Mapped[date | None] = mapped_column(Date)
    exit_date: Mapped[date | None] = mapped_column(Date)
    exit_status: Mapped[str | None] = mapped_column(String(64))
    notes: Mapped[str | None] = mapped_column(Text)

    program: Mapped["IncubationProgram"] = relationship(back_populates="participations")
    startup: Mapped["Startup"] = relationship(back_populates="incubations")
    stages: Mapped[list["IncubationStage"]] = relationship(
        back_populates="participation", cascade="all, delete-orphan"
    )


class IncubationStage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A tracked follow-up stage (mentoring/milestone) of an incubation."""

    __tablename__ = "incubation_stages"
    __table_args__ = (
        Index("ix_incubation_stages_participation", "participation_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    participation_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("incubation_participations.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="MENTORING", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="PLANNED", nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[date | None] = mapped_column(Date)
    result: Mapped[str | None] = mapped_column(Text)

    participation: Mapped["IncubationParticipation"] = relationship(
        back_populates="stages"
    )



