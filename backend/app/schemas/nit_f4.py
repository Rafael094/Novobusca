"""Pydantic schemas for NIT phase F4: projects, startups, incubation, indicators."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# --- Projects ---------------------------------------------------------------
class ProjectBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    objective: str | None = None
    technology_area: str | None = Field(default=None, max_length=128)
    status: str = Field(
        default="PLANNED",
        pattern="^(PLANNED|ACTIVE|COMPLETED|CANCELLED)$",
    )
    start_date: date | None = None
    end_date: date | None = None
    unity_id: uuid.UUID | None = None
    coordinator_id: uuid.UUID | None = None
    notes: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    objective: str | None = None
    technology_area: str | None = None
    status: str | None = Field(
        default=None, pattern="^(PLANNED|ACTIVE|COMPLETED|CANCELLED)$"
    )
    start_date: date | None = None
    end_date: date | None = None
    unity_id: uuid.UUID | None = None
    coordinator_id: uuid.UUID | None = None
    notes: str | None = None
    active: bool | None = None


class ProjectOut(ProjectBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    active: bool
    created_at: datetime
    updated_at: datetime


class PaginatedProjects(BaseModel):
    items: list[ProjectOut]
    page: int
    page_size: int
    total: int


# --- Members ----------------------------------------------------------------
class ProjectMemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="RESEARCHER", max_length=24)
    person_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    institution: str | None = Field(default=None, max_length=255)


class ProjectMemberOut(ProjectMemberIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    active: bool
    created_at: datetime


# --- Funders ----------------------------------------------------------------
class ProjectFunderIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    document: str | None = Field(default=None, max_length=32)
    instrument: str | None = Field(default=None, max_length=128)
    amount: Decimal | None = None
    currency: str = Field(default="BRL", min_length=3, max_length=3)


class ProjectFunderOut(ProjectFunderIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID


# --- Milestones -------------------------------------------------------------
class ProjectMilestoneIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    due_date: date | None = None
    status: str = Field(default="PENDING", pattern="^(PENDING|DONE|LATE)$")


class ProjectMilestoneOut(ProjectMilestoneIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    completed_at: date | None = None
    created_at: datetime


# --- Asset links ------------------------------------------------------------
class AssetLinkIn(BaseModel):
    asset_id: uuid.UUID
    relation: str = Field(default="RESULT", pattern="^(ORIGIN|RESULT|RELATED)$")
    notes: str | None = None


class AssetLinkOut(AssetLinkIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID


class ProjectDetail(ProjectOut):
    members: list[ProjectMemberOut] = []
    funders: list[ProjectFunderOut] = []
    milestones: list[ProjectMilestoneOut] = []
    asset_links: list[AssetLinkOut] = []


# --- Startups ---------------------------------------------------------------
class StartupBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    cnpj: str | None = Field(default=None, max_length=18)
    status: str = Field(
        default="IDEATION",
        pattern="^(IDEATION|INCUBATED|GRADUATED|ACTIVE|CLOSED)$",
    )
    stage: str | None = Field(default=None, max_length=64)
    founded_at: date | None = None
    project_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None
    responsible_id: uuid.UUID | None = None
    notes: str | None = None


class StartupCreate(StartupBase):
    pass


class StartupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    cnpj: str | None = None
    status: str | None = Field(
        default=None, pattern="^(IDEATION|INCUBATED|GRADUATED|ACTIVE|CLOSED)$"
    )
    stage: str | None = None
    founded_at: date | None = None
    project_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None
    responsible_id: uuid.UUID | None = None
    notes: str | None = None
    active: bool | None = None


class StartupOut(StartupBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    active: bool
    created_at: datetime
    updated_at: datetime


class StartupMemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    role: str | None = Field(default=None, max_length=64)
    person_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    is_founder: bool = False


class StartupMemberOut(StartupMemberIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    startup_id: uuid.UUID


class PaginatedStartups(BaseModel):
    items: list[StartupOut]
    page: int
    page_size: int
    total: int


# --- Incubation -------------------------------------------------------------
class ProgramCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    criteria: str | None = None
    start_date: date | None = None
    end_date: date | None = None


class ProgramOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    criteria: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    active: bool
    created_at: datetime


class ParticipationCreate(BaseModel):
    startup_id: uuid.UUID
    entry_date: date | None = None
    notes: str | None = None


class ParticipationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    program_id: uuid.UUID
    startup_id: uuid.UUID
    entry_date: date | None = None
    exit_date: date | None = None
    exit_status: str | None = None
    notes: str | None = None
    created_at: datetime


class StageCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    kind: str = Field(default="MENTORING", max_length=32)
    status: str = Field(default="PLANNED", pattern="^(PLANNED|IN_PROGRESS|COMPLETED|DROPPED)$")
    due_date: date | None = None


class StageOut(StageCreate):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    participation_id: uuid.UUID
    completed_at: date | None = None
    result: str | None = None
    created_at: datetime


class ParticipationDetail(ParticipationOut):
    stages: list[StageOut] = []


# --- Indicators & FORMICT ---------------------------------------------------
class IndicatorCount(BaseModel):
    key: str
    count: int


class InstitutionalIndicators(BaseModel):
    """Indicators derived exclusively from real queries (no invented values)."""

    disclosure_total: int
    disclosures_by_status: dict[str, int]
    disclosures_by_area: dict[str, int]
    average_triage_days: float | None
    pending_evaluations: int
    assets_total: int
    assets_by_stage: dict[str, int]
    offers_published: int
    negotiations_in_progress: int
    contracts_active: int
    obligations_due_soon: int
    projects_total: int
    projects_active: int
    startups_total: int
    startups_incubated: int
    period_from: datetime | None = None
    period_to: datetime | None = None


class FormictReport(BaseModel):
    """Internal support report — NOT the official FORMICT submission."""

    disclaimer: str
    generated_at: datetime
    institution: str | None = None
    contracts_active: int
    contracts_total: int
    total_registered: Decimal
    total_received: Decimal
    technologies_offered: int
    transfers_effective: int
    projects_active: int
    startups_supported: int

