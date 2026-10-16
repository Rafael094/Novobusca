"""NIT phase F5 ORM models — notifications, external portals, BI and integrations.

Conventions (same invariants as F1–F4): tenant-scoped, standard mixins. This phase
adds outreach/self-service infrastructure. Two hard rules are encoded here:

* External portal access is granted explicitly and is **read/scope-limited** — an
  external grantee never inherits internal NIT permissions.
* Notifications and integration deliveries are **queued** (outbox pattern). Nothing
  is claimed to have been delivered unless a real transport marked it so; e-mail
  and third-party integrations are inert until a real provider is configured.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

# --- Vocabularies -----------------------------------------------------------

NOTIFICATION_SEVERITIES: tuple[str, ...] = ("INFO", "WARNING", "CRITICAL")

NOTIFICATION_KINDS: tuple[str, ...] = (
    "DISCLOSURE_STATUS",
    "EVALUATION_ASSIGNED",
    "NEGOTIATION_UPDATE",
    "OBLIGATION_DUE",
    "PORTAL_REQUEST",
    "GENERIC",
)

EMAIL_STATUS_QUEUED = "QUEUED"
EMAIL_STATUS_SENT = "SENT"
EMAIL_STATUS_FAILED = "FAILED"
EMAIL_STATUSES: tuple[str, ...] = (
    EMAIL_STATUS_QUEUED,
    EMAIL_STATUS_SENT,
    EMAIL_STATUS_FAILED,
)

PORTAL_KIND_RESEARCHER = "RESEARCHER"
PORTAL_KIND_COMPANY = "COMPANY"
PORTAL_KINDS: tuple[str, ...] = (PORTAL_KIND_RESEARCHER, PORTAL_KIND_COMPANY)

PORTAL_ACCESS_ACTIVE = "ACTIVE"
PORTAL_ACCESS_REVOKED = "REVOKED"
PORTAL_ACCESS_STATUSES: tuple[str, ...] = (
    PORTAL_ACCESS_ACTIVE,
    PORTAL_ACCESS_REVOKED,
)

PORTAL_REQUEST_TYPES: tuple[str, ...] = (
    "DISCLOSURE_SUBMISSION",
    "INTEREST_EXPRESSION",
    "NDA_REQUEST",
    "INFORMATION",
)

PORTAL_REQUEST_STATUSES: tuple[str, ...] = (
    "NEW",
    "TRIAGED",
    "ACCEPTED",
    "REJECTED",
)

INTEGRATION_KINDS: tuple[str, ...] = ("SIGA", "SEI", "EMAIL", "WEBHOOK")

DELIVERY_PENDING = "PENDING"
DELIVERY_SENT = "SENT"
DELIVERY_FAILED = "FAILED"
DELIVERY_STATUSES: tuple[str, ...] = (
    DELIVERY_PENDING,
    DELIVERY_SENT,
    DELIVERY_FAILED,
)


# --- Notifications ----------------------------------------------------------
class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An in-app notification addressed to a specific user of a tenant."""

    __tablename__ = "nit_notifications"
    __table_args__ = (
        Index("ix_nit_notifications_user", "user_id"),
        Index("ix_nit_notifications_tenant", "tenant_id"),
        Index("ix_nit_notifications_unread", "user_id", "read_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), default="GENERIC", nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="INFO", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(512))
    resource_type: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NotificationPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Per-user opt-in for each notification kind (in-app and e-mail)."""

    __tablename__ = "nit_notification_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", name="uq_nit_notif_pref_user_kind"),
        Index("ix_nit_notif_pref_user", "user_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class EmailMessage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Queued e-mail (outbox). Stays ``QUEUED`` until a real transport sends it."""

    __tablename__ = "nit_email_messages"
    __table_args__ = (
        Index("ix_nit_email_status", "status"),
        Index("ix_nit_email_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    to_email: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="GENERIC", nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=EMAIL_STATUS_QUEUED, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )


# --- External portals -------------------------------------------------------
class ExternalPortalAccess(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """An explicit grant of portal access to an external person/company.

    A grant never confers internal NIT permissions; it only allows the holder to
    see/submit within the scope identified by ``subject_type``/``subject_id``.
    """

    __tablename__ = "nit_portal_access"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "portal_kind", "email", name="uq_nit_portal_access_email"
        ),
        Index("ix_nit_portal_access_tenant", "tenant_id"),
        Index("ix_nit_portal_access_status", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    portal_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    organization: Mapped[str | None] = mapped_column(String(255))
    subject_type: Mapped[str | None] = mapped_column(String(64))
    subject_id: Mapped[uuid.UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(16), default=PORTAL_ACCESS_ACTIVE, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    access_token: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    requests: Mapped[list["PortalRequest"]] = relationship(
        back_populates="access", cascade="all, delete-orphan"
    )


class PortalRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A self-service request submitted from an external portal."""

    __tablename__ = "nit_portal_requests"
    __table_args__ = (
        Index("ix_nit_portal_requests_access", "access_id"),
        Index("ix_nit_portal_requests_tenant", "tenant_id"),
        Index("ix_nit_portal_requests_status", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    access_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("nit_portal_access.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_type: Mapped[str] = mapped_column(String(32), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="NEW", nullable=False)
    triaged_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    triaged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    access: Mapped["ExternalPortalAccess"] = relationship(back_populates="requests")
    notes: Mapped[list["PortalRequestNote"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )


class PortalRequestNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An internal triage note attached to a portal request (append-only log)."""

    __tablename__ = "nit_portal_request_notes"
    __table_args__ = (Index("ix_nit_portal_notes_request", "request_id"),)

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("nit_portal_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    request: Mapped["PortalRequest"] = relationship(back_populates="notes")


# --- BI reports -------------------------------------------------------------
class SavedReport(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A saved BI report definition (metric keys + filter values), tenant-scoped.

    The definition only selects which REAL metrics/queries run; it never stores or
    fabricates values. Results are produced on demand by the indicators engine.
    """

    __tablename__ = "nit_saved_reports"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_nit_saved_reports_name"),
        Index("ix_nit_saved_reports_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    filters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    visibility: Mapped[str] = mapped_column(String(16), default="TENANT", nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    runs: Mapped[list["ReportRun"]] = relationship(
        back_populates="report", cascade="all, delete-orphan"
    )


class ReportRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An append-only record of a BI report execution and its frozen result."""

    __tablename__ = "nit_report_runs"
    __table_args__ = (
        Index("ix_nit_report_runs_report", "report_id"),
        Index("ix_nit_report_runs_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("nit_saved_reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    ran_by: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    report: Mapped["SavedReport"] = relationship(back_populates="runs")


# --- Integrations -----------------------------------------------------------
class IntegrationEndpoint(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A registered external integration (SIGA/SEI/e-mail/webhook).

    The endpoint is a declarative registry entry. It performs NOTHING by itself:
    deliveries are queued and stay ``PENDING`` until a real adapter is configured.
    """

    __tablename__ = "nit_integration_endpoints"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_nit_integration_name"),
        Index("ix_nit_integration_tenant", "tenant_id"),
        Index("ix_nit_integration_kind", "kind"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    deliveries: Mapped[list["IntegrationDelivery"]] = relationship(
        back_populates="endpoint", cascade="all, delete-orphan"
    )


class IntegrationDelivery(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An outbox entry for an integration event (queued until a real transport)."""

    __tablename__ = "nit_integration_deliveries"
    __table_args__ = (
        Index("ix_nit_integration_deliveries_endpoint", "endpoint_id"),
        Index("ix_nit_integration_deliveries_status", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("nit_integration_endpoints.id", ondelete="CASCADE"),
        nullable=False,
    )
    event: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(16), default=DELIVERY_PENDING, nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    endpoint: Mapped["IntegrationEndpoint"] = relationship(back_populates="deliveries")



