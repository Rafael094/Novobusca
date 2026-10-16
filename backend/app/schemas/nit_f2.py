"""Pydantic schemas for NIT phase F2: committees, TRL and portfolio views."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --- TRL --------------------------------------------------------------------
class TrlCreate(BaseModel):
    level: int = Field(ge=1, le=9)
    rationale: str = Field(min_length=1)
    evidence: str | None = None
    disclosure_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None


class TrlOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    disclosure_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None
    level: int
    previous_level: int | None = None
    rationale: str
    evidence: str | None = None
    evaluator_id: uuid.UUID | None = None
    created_at: datetime


# --- Committees -------------------------------------------------------------
class CommitteeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    quorum: int = Field(default=1, ge=1)
    simple_majority: bool = True


class CommitteeUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, pattern="^(ACTIVE|INACTIVE)$")
    quorum: int | None = Field(default=None, ge=1)
    simple_majority: bool | None = None
    active: bool | None = None


class CommitteeMemberIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    user_id: uuid.UUID | None = None
    person_id: uuid.UUID | None = None
    role_title: str | None = Field(default=None, max_length=128)
    kind: str = Field(default="VOTING", pattern="^(VOTING|ADVISORY)$")
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class CommitteeMemberOut(CommitteeMemberIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    committee_id: uuid.UUID
    active: bool
    created_at: datetime


class CommitteeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    name: str
    description: str | None = None
    status: str
    quorum: int
    simple_majority: bool
    active: bool
    created_at: datetime
    updated_at: datetime


class CommitteeDetail(CommitteeOut):
    members: list[CommitteeMemberOut] = []


class MeetingCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    scheduled_at: datetime
    location: str | None = Field(default=None, max_length=255)


class MeetingUpdate(BaseModel):
    title: str | None = None
    scheduled_at: datetime | None = None
    held_at: datetime | None = None
    status: str | None = Field(default=None, pattern="^(SCHEDULED|HELD|CANCELLED)$")
    location: str | None = None
    minutes: str | None = None


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    committee_id: uuid.UUID
    title: str
    scheduled_at: datetime
    held_at: datetime | None = None
    status: str
    location: str | None = None
    minutes: str | None = None
    created_at: datetime


class AgendaItemIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str | None = None
    disclosure_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None
    sort_order: int = 0


class AgendaItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    meeting_id: uuid.UUID
    disclosure_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None
    title: str
    summary: str | None = None
    status: str
    sort_order: int


class VoteIn(BaseModel):
    member_id: uuid.UUID
    vote: str = Field(pattern="^(APPROVE|REJECT|ABSTAIN|IMPEDED)$")
    conflict_of_interest: bool = False
    comment: str | None = None


class VoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    item_id: uuid.UUID
    member_id: uuid.UUID
    voter_user_id: uuid.UUID | None = None
    vote: str
    conflict_of_interest: bool
    comment: str | None = None
    created_at: datetime


class DecisionIn(BaseModel):
    outcome: str = Field(pattern="^(APPROVED|REJECTED|DEFERRED)$")
    justification: str | None = None


class DecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    item_id: uuid.UUID
    outcome: str
    justification: str | None = None
    approvals: int
    rejections: int
    abstentions: int
    impeded: int
    decided_by_id: uuid.UUID | None = None
    decided_at: datetime


class VoteTallyOut(BaseModel):
    approvals: int
    rejections: int
    abstentions: int
    impeded: int
    valid: int
    quorum: int
    can_approve: bool


# --- Portfolio --------------------------------------------------------------
class PortfolioAsset(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    asset_type: str
    status: str
    technology_area: str | None = None
    unity_id: uuid.UUID | None = None
    deposited_at: datetime | None = None
    granted_at: datetime | None = None
    expires_at: datetime | None = None
    days_to_expiry: int | None = None
    trl_level: int | None = None


class PortfolioView(BaseModel):
    items: list[PortfolioAsset]
    total: int
    by_type: dict[str, int]
    by_status: dict[str, int]
    expiring_soon: int
    expired: int


class DeadlineAlert(BaseModel):
    asset_id: uuid.UUID
    code: str
    title: str
    expires_at: datetime
    days_to_expiry: int
    severity: str
