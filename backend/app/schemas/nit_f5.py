"""Pydantic schemas for NIT phase F5: notifications, portals, BI, integrations."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --- Notifications ----------------------------------------------------------
class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    severity: str
    title: str
    body: str | None = None
    link: str | None = None
    resource_type: str | None = None
    resource_id: uuid.UUID | None = None
    read_at: datetime | None = None
    created_at: datetime


class PaginatedNotifications(BaseModel):
    items: list[NotificationOut]
    page: int
    page_size: int
    total: int
    unread: int


class NotificationPreferenceIn(BaseModel):
    kind: str = Field(min_length=1, max_length=32)
    in_app_enabled: bool = True
    email_enabled: bool = False


class NotificationPreferenceOut(NotificationPreferenceIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID


class EmailMessageIn(BaseModel):
    to_email: str = Field(min_length=3, max_length=320)
    subject: str = Field(min_length=1, max_length=255)
    body: str = Field(min_length=1)
    kind: str = Field(default="GENERIC", max_length=32)


class EmailMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    to_email: str
    subject: str
    body: str
    kind: str
    status: str
    error: str | None = None
    sent_at: datetime | None = None
    created_at: datetime


# --- External portals -------------------------------------------------------
class PortalAccessCreate(BaseModel):
    portal_kind: str = Field(pattern="^(RESEARCHER|COMPANY)$")
    email: str = Field(min_length=3, max_length=320)
    name: str = Field(min_length=1, max_length=255)
    organization: str | None = Field(default=None, max_length=255)
    subject_type: str | None = Field(default=None, max_length=64)
    subject_id: uuid.UUID | None = None
    expires_at: datetime | None = None
    notes: str | None = None


class PortalAccessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    portal_kind: str
    email: str
    name: str
    organization: str | None = None
    subject_type: str | None = None
    subject_id: uuid.UUID | None = None
    status: str
    expires_at: datetime | None = None
    notes: str | None = None
    created_at: datetime


class PortalAccessCreated(PortalAccessOut):
    """Create-only view: reveals the grant token exactly once to staff."""

    access_token: str


class PortalRequestCreate(BaseModel):
    request_type: str = Field(pattern="^(DISCLOSURE_SUBMISSION|INTEREST_EXPRESSION|NDA_REQUEST|INFORMATION)$")
    subject: str = Field(min_length=1, max_length=255)
    message: str | None = None
    payload: dict | None = None


class PortalRequestTriage(BaseModel):
    status: str = Field(pattern="^(NEW|TRIAGED|ACCEPTED|REJECTED)$")
    note: str | None = None


class PortalRequestNoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    author_id: uuid.UUID | None = None
    body: str
    created_at: datetime


class PortalRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    access_id: uuid.UUID
    request_type: str
    subject: str
    message: str | None = None
    payload: dict | None = None
    status: str
    triaged_by: uuid.UUID | None = None
    triaged_at: datetime | None = None
    created_at: datetime


class PortalRequestDetail(PortalRequestOut):
    notes: list[PortalRequestNoteOut] = []


# --- BI reports -------------------------------------------------------------
class SavedReportCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    metrics: list[str] = Field(default_factory=list)
    filters: dict = Field(default_factory=dict)
    visibility: str = Field(default="TENANT", pattern="^(TENANT|PRIVATE)$")


class SavedReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    description: str | None = None
    metrics: list
    filters: dict
    visibility: str
    created_at: datetime


class ReportRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    ran_by: uuid.UUID | None = None
    result: dict
    created_at: datetime


# --- Integrations -----------------------------------------------------------
class IntegrationEndpointCreate(BaseModel):
    kind: str = Field(pattern="^(SIGA|SEI|EMAIL|WEBHOOK)$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    config: dict = Field(default_factory=dict)
    enabled: bool = False


class IntegrationEndpointOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    kind: str
    name: str
    description: str | None = None
    config: dict
    enabled: bool
    created_at: datetime


class IntegrationDeliveryCreate(BaseModel):
    event: str = Field(min_length=1, max_length=64)
    payload: dict = Field(default_factory=dict)


class IntegrationDeliveryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    endpoint_id: uuid.UUID
    event: str
    payload: dict
    status: str
    error: str | None = None
    delivered_at: datetime | None = None
    created_at: datetime

