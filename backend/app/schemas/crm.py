"""Schemas for the commercial CRM (opportunities, proposals, activities).

All money is carried as ``Decimal`` at the API boundary (serialised as a string
by Pydantic, matching the NIT convention) and never fabricamos valores: a field
left empty stays empty.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# --- Literals mirroring the model vocabularies ------------------------------

OpportunityStage = Literal[
    "NEW", "QUALIFICATION", "PROPOSAL", "SENT", "NEGOTIATION", "WON", "LOST"
]
ProposalStatus = Literal[
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
ActivityKind = Literal["CALL", "MEETING", "EMAIL", "NOTE", "TASK", "OTHER"]
ActivityOutcome = Literal["PENDING", "DONE", "NO_ANSWER", "RESCHEDULED"]
ActivitySubjectType = Literal["OPPORTUNITY", "PROPOSAL", "CUSTOMER", "COMPANY"]
OpportunitySource = Literal[
    "INBOUND", "OUTBOUND", "REFERRAL", "EVENT", "PARTNER", "WEBSITE", "OTHER"
]


# --- Opportunity -------------------------------------------------------------
class OpportunityBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    lead_name: str | None = Field(default=None, max_length=255)
    contact_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    source: OpportunitySource | None = None
    service_interest: str | None = Field(default=None, max_length=255)
    estimated_value: Decimal | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    next_action: str | None = Field(default=None, max_length=255)
    next_action_at: date | None = None
    expected_close_at: date | None = None
    notes: str | None = None


class OpportunityCreate(OpportunityBase):
    stage: OpportunityStage = "NEW"


class OpportunityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    lead_name: str | None = None
    contact_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    company_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    source: OpportunitySource | None = None
    service_interest: str | None = None
    estimated_value: Decimal | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    next_action: str | None = None
    next_action_at: date | None = None
    expected_close_at: date | None = None
    notes: str | None = None
    active: bool | None = None


class OpportunityStageChange(BaseModel):
    stage: OpportunityStage
    lost_reason: str | None = Field(default=None, max_length=255)
    customer_id: uuid.UUID | None = None
    notes: str | None = None


class OpportunityConvert(BaseModel):
    """Payload of ``POST /api/crm/opportunities/{id}/convert``.

    An empty payload converts the lead using its own data. When ``customer_id``
    is given the opportunity is linked to that existing customer (never
    duplicated); otherwise the service searches for a match and only creates a
    new ``Customer`` when none is found — unless ``force_new`` is set.
    """

    customer_id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=255)
    document: str | None = Field(default=None, max_length=32)
    email: str | None = None
    phone: str | None = Field(default=None, max_length=32)
    force_new: bool = False


class OpportunityOut(OpportunityBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    stage: str
    lost_reason: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    # Joined display fields (filled by the router; never stored twice).
    customer_name: str | None = None
    company_name: str | None = None
    contact_name: str | None = None
    owner_name: str | None = None
    proposal_count: int = 0


class PaginatedOpportunities(BaseModel):
    pagination: dict
    items: list[OpportunityOut]


# --- Proposal ----------------------------------------------------------------
class ProposalBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    services: str | None = None
    opportunity_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    total_value: Decimal | None = None
    valid_until: date | None = None
    notes: str | None = None


class ProposalCreate(ProposalBase):
    status: ProposalStatus = "DRAFT"


class ProposalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    services: str | None = None
    opportunity_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    total_value: Decimal | None = None
    valid_until: date | None = None
    notes: str | None = None
    active: bool | None = None


class ProposalStatusChange(BaseModel):
    status: ProposalStatus
    #: ``sent`` records the actual send date; ``reply`` records the return.
    mark_sent: bool = False
    mark_reply: bool = False
    decision_notes: str | None = None


class ProposalOut(ProposalBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    status: str
    sent_at: datetime | None = None
    replied_at: datetime | None = None
    decision_at: datetime | None = None
    decision_notes: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    # Joined display fields.
    opportunity_title: str | None = None
    customer_name: str | None = None
    owner_name: str | None = None
    # Derived: ``valid_until`` in the past and not yet closed.
    is_overdue: bool = False


class PaginatedProposals(BaseModel):
    pagination: dict
    items: list[ProposalOut]


# --- Activity ----------------------------------------------------------------
class ActivityBase(BaseModel):
    kind: ActivityKind = "NOTE"
    subject_type: ActivitySubjectType
    subject_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    notes: str | None = None
    outcome: ActivityOutcome = "PENDING"
    occurred_at: datetime | None = None
    due_at: datetime | None = None
    owner_id: uuid.UUID | None = None


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    kind: ActivityKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = None
    outcome: ActivityOutcome | None = None
    occurred_at: datetime | None = None
    due_at: datetime | None = None
    owner_id: uuid.UUID | None = None
    active: bool | None = None


class ActivityOut(ActivityBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    completed_at: datetime | None = None
    created_by: uuid.UUID | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    owner_name: str | None = None


class PaginatedActivities(BaseModel):
    pagination: dict
    items: list[ActivityOut]


# --- Dashboard (commercial aggregates of the authenticated tenant) -----------
class BusinessCounters(BaseModel):
    """Headline numbers for the business dashboard."""

    active_customers: int
    total_customers: int
    new_customers_period: int
    open_opportunities: int
    proposals_to_send: int
    proposals_awaiting_reply: int
    proposals_approved: int
    proposals_rejected: int
    proposals_open: int
    proposals_overdue: int
    monitored_marcas: int
    monitored_patentes: int
    critical_alerts: int
    #: approved / (approved + rejected) over the period, in percent (None when
    #: there is not enough history to compute it — never fabricated).
    conversion_rate: float | None = None


class BusinessPeriod(BaseModel):
    date_from: date
    date_to: date
    months: int


class EvolutionPoint(BaseModel):
    """One bucket of the commercial evolution chart."""

    label: str  # e.g. "2026-03"
    new_customers: int
    proposals_sent: int
    proposals_approved: int
    opportunities_won: int


class FunnelStage(BaseModel):
    stage: str
    label: str
    count: int
    #: Aggregated estimated value of the opportunities in the stage (string or
    #: None when no opportunity in the stage has a value).
    value: str | None = None


class PendingProposal(BaseModel):
    id: uuid.UUID
    code: str
    title: str
    status: str
    status_label: str
    customer_name: str | None = None
    opportunity_title: str | None = None
    owner_name: str | None = None
    total_value: str | None = None
    sent_at: datetime | None = None
    valid_until: date | None = None
    days_to_due: int | None = None
    reason: str  # TO_SEND | AWAITING_REPLY | NEAR_DUE | OVERDUE | APPROVED_NO_CUSTOMER


class RecentActivityItem(BaseModel):
    kind: str  # customer | proposal | opportunity | activity | monitoring | alert
    title: str
    description: str | None = None
    status: str | None = None
    at: datetime
    link: str | None = None


class UpcomingDeadlineItem(BaseModel):
    domain: str  # "COMMERCIAL" | "PROPRIEDADE_INTELECTUAL"
    title: str
    subtitle: str | None = None
    due_at: date | None = None
    days_remaining: int | None = None
    tone: str  # green | amber | red
    link: str | None = None


class BusinessDashboard(BaseModel):
    """Payload of ``GET /api/dashboard/business``.

    Every number is scoped to the authenticated tenant (master admin: all).
    Global INPI base statistics are intentionally NOT part of this payload;
    they belong to the search/report modules.
    """

    generated_at: datetime
    scope: str  # "tenant" | "all_tenants"
    period: BusinessPeriod
    counters: BusinessCounters
    evolution: list[EvolutionPoint]
    funnel: list[FunnelStage]
    pending_proposals: list[PendingProposal]
    deadlines: list[UpcomingDeadlineItem]
    recent_activity: list[RecentActivityItem]


