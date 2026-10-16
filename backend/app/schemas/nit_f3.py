"""Pydantic schemas for NIT phase F3: catalog, interests, negotiations, contracts.

Monetary fields use ``Decimal`` (Pydantic) so they serialise as exact numbers —
never floating point.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# --- Technology offers ------------------------------------------------------
class OfferBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    public_summary: str | None = None
    technology_area: str | None = Field(default=None, max_length=128)
    maturity: str | None = Field(default=None, max_length=64)
    modality: str = Field(default="LICENSING", pattern="^(LICENSING|ASSIGNMENT|CO_DEVELOPMENT|SERVICE|OTHER)$")
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: str | None = Field(default=None, max_length=255)
    conditions: str | None = None
    asset_id: uuid.UUID | None = None
    unity_id: uuid.UUID | None = None


class OfferCreate(OfferBase):
    pass


class OfferUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    public_summary: str | None = None
    technology_area: str | None = None
    maturity: str | None = None
    modality: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    conditions: str | None = None
    status: str | None = Field(default=None, pattern="^(DRAFT|PUBLISHED|SUSPENDED|CLOSED)$")
    active: bool | None = None


class OfferOut(OfferBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    status: str
    responsible_id: uuid.UUID | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


class PaginatedOffers(BaseModel):
    items: list[OfferOut]
    page: int
    page_size: int
    total: int


# --- Expressions of interest ------------------------------------------------
class InterestCreate(BaseModel):
    """A partner/company registers interest in a PUBLISHED offer.

    NOTE: no ``tenant_id`` — derived from the auth context; and the offer must be
    visible (published) to the caller's tenant.
    """

    organization_name: str = Field(min_length=1, max_length=255)
    organization_document: str | None = Field(default=None, max_length=32)
    contact_name: str | None = Field(default=None, max_length=255)
    contact_email: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=32)
    message: str | None = None


class InterestUpdate(BaseModel):
    status: str | None = Field(
        default=None, pattern="^(NEW|QUALIFYING|IN_NEGOTIATION|DECLINED|CONVERTED)$"
    )
    owner_id: uuid.UUID | None = None
    active: bool | None = None


class InterestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    offer_id: uuid.UUID
    organization_name: str
    organization_document: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    message: str | None = None
    status: str
    owner_id: uuid.UUID | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


class PaginatedInterests(BaseModel):
    items: list[InterestOut]
    page: int
    page_size: int
    total: int


class InteractionIn(BaseModel):
    kind: str = Field(min_length=1, max_length=32)
    summary: str = Field(min_length=1)


class InteractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    interest_id: uuid.UUID
    kind: str
    summary: str
    actor_id: uuid.UUID | None = None
    created_at: datetime


# --- Negotiations -----------------------------------------------------------
class NegotiationCreate(BaseModel):
    interest_id: uuid.UUID | None = None
    offer_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    next_step: str | None = None
    notes: str | None = None


class NegotiationUpdate(BaseModel):
    owner_id: uuid.UUID | None = None
    next_step: str | None = None
    notes: str | None = None


class NegotiationAdvance(BaseModel):
    to_stage: str
    justification: str | None = None
    expected_version: int | None = Field(default=None, ge=0)


class NegotiationHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    from_stage: str | None = None
    to_stage: str
    actor_id: uuid.UUID | None = None
    justification: str | None = None
    created_at: datetime


class NegotiationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    interest_id: uuid.UUID | None = None
    offer_id: uuid.UUID | None = None
    stage: str
    stage_label: str | None = None
    owner_id: uuid.UUID | None = None
    next_step: str | None = None
    notes: str | None = None
    version: int
    active: bool
    created_at: datetime
    updated_at: datetime


class NegotiationDetail(NegotiationOut):
    allowed_next: list[str] = []
    history: list[NegotiationHistoryOut] = []


# --- Licenses ---------------------------------------------------------------
class LicenseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    license_type: str = Field(default="LICENSE", pattern="^(LICENSE|ASSIGNMENT)$")
    asset_id: uuid.UUID | None = None
    negotiation_id: uuid.UUID | None = None
    exclusive: bool = False
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None


class LicenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    license_type: str
    asset_id: uuid.UUID | None = None
    negotiation_id: uuid.UUID | None = None
    title: str
    exclusive: bool
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = None
    active: bool
    created_at: datetime


# --- Contracts --------------------------------------------------------------
class PartyIn(BaseModel):
    role: str = Field(default="OTHER", max_length=16)
    name: str = Field(min_length=1, max_length=255)
    document: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    representative: str | None = Field(default=None, max_length=255)


class PartyOut(PartyIn):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    contract_id: uuid.UUID


class ContractCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    license_id: uuid.UUID | None = None
    parent_contract_id: uuid.UUID | None = None
    is_amendment: bool = False
    signed_at: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    registered_amount: Decimal | None = None
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    conditions: str | None = None
    notes: str | None = None
    responsible_id: uuid.UUID | None = None
    parties: list[PartyIn] = []


class ContractUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(
        default=None, pattern="^(DRAFT|ACTIVE|EXPIRED|TERMINATED)$"
    )
    signed_at: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    registered_amount: Decimal | None = None
    currency: str | None = None
    conditions: str | None = None
    notes: str | None = None
    responsible_id: uuid.UUID | None = None
    active: bool | None = None


class ContractOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    title: str
    license_id: uuid.UUID | None = None
    parent_contract_id: uuid.UUID | None = None
    is_amendment: bool
    status: str
    signed_at: date | None = None
    effective_from: date | None = None
    effective_until: date | None = None
    registered_amount: Decimal | None = None
    currency: str
    conditions: str | None = None
    notes: str | None = None
    responsible_id: uuid.UUID | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


class ContractDetail(ContractOut):
    parties: list[PartyOut] = []


class PaginatedContracts(BaseModel):
    items: list[ContractOut]
    page: int
    page_size: int
    total: int


# --- Obligations ------------------------------------------------------------
class ObligationCreate(BaseModel):
    kind: str = Field(default="OTHER", max_length=16)
    description: str = Field(min_length=1)
    due_date: date | None = None
    responsible_id: uuid.UUID | None = None


class ObligationUpdate(BaseModel):
    kind: str | None = None
    description: str | None = None
    due_date: date | None = None
    status: str | None = Field(
        default=None, pattern="^(PENDING|DONE|LATE|WAIVED)$"
    )
    responsible_id: uuid.UUID | None = None
    evidence: str | None = None
    fulfilled_at: date | None = None


class ObligationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    contract_id: uuid.UUID
    kind: str
    description: str
    due_date: date | None = None
    status: str
    responsible_id: uuid.UUID | None = None
    evidence: str | None = None
    fulfilled_at: date | None = None
    created_at: datetime


# --- Royalties --------------------------------------------------------------
class RoyaltyCreate(BaseModel):
    period: str = Field(min_length=1, max_length=16)
    expected_amount: Decimal | None = None
    registered_amount: Decimal | None = None
    received_amount: Decimal | None = None
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    due_date: date | None = None
    received_at: date | None = None
    notes: str | None = None


class RoyaltyUpdate(BaseModel):
    expected_amount: Decimal | None = None
    registered_amount: Decimal | None = None
    received_amount: Decimal | None = None
    due_date: date | None = None
    received_at: date | None = None
    notes: str | None = None


class RoyaltyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    contract_id: uuid.UUID
    period: str
    expected_amount: Decimal | None = None
    registered_amount: Decimal | None = None
    received_amount: Decimal | None = None
    currency: str
    due_date: date | None = None
    received_at: date | None = None
    notes: str | None = None
    created_at: datetime


class RoyaltySummary(BaseModel):
    contract_id: uuid.UUID
    total_expected: Decimal
    total_registered: Decimal
    total_received: Decimal
    pending: Decimal
    entries: int


class ObligationAlert(BaseModel):
    obligation_id: uuid.UUID
    contract_id: uuid.UUID
    contract_code: str
    description: str
    due_date: date
    days_to_due: int
    severity: str
    status: str

