"""Notification dispatch for the NIT (F5).

Design rules:

* Every notification is **persisted** (in-app) for the target user before any
  e-mail is queued. Nothing is silently dropped.
* E-mail is only *queued* in the ``nit_email_messages`` outbox with status
  ``QUEUED``. No transport is invoked here — a real provider must be wired to
  advance the status to ``SENT``. We never claim delivery we did not perform.
* Integration events follow the same outbox discipline.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.nit_f5 import (
    DELIVERY_PENDING,
    EMAIL_STATUS_QUEUED,
    EmailMessage,
    ExternalPortalAccess,
    IntegrationDelivery,
    IntegrationEndpoint,
    Notification,
    NotificationPreference,
)

DEFAULT_KIND = "GENERIC"


def _prefers_email(db: Session, user_id: uuid.UUID, kind: str) -> bool:
    """A user must explicitly opt in to e-mail for a kind (default is off)."""
    pref = db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id,
            NotificationPreference.kind == kind,
        )
    ).scalar_one_or_none()
    return bool(pref and pref.email_enabled)


def notify_user(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    title: str,
    body: str | None = None,
    kind: str = DEFAULT_KIND,
    severity: str = "INFO",
    link: str | None = None,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
    email: str | None = None,
) -> Notification:
    """Persist an in-app notification and, if opted in, queue an e-mail."""
    notification = Notification(
        tenant_id=tenant_id,
        user_id=user_id,
        kind=kind,
        severity=severity,
        title=title,
        body=body,
        link=link,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    db.add(notification)
    if email and _prefers_email(db, user_id, kind):
        db.add(
            EmailMessage(
                tenant_id=tenant_id,
                to_email=email,
                subject=title,
                body=body or title,
                kind=kind,
                status=EMAIL_STATUS_QUEUED,
            )
        )
    return notification


def notify_portal_grantee(
    db: Session,
    *,
    access: ExternalPortalAccess,
    title: str,
    body: str | None = None,
    kind: str = "PORTAL_REQUEST",
) -> EmailMessage:
    """Queue an outbound e-mail to an external portal grantee.

    External grantees have no user account, so only a queued e-mail is produced.
    """
    message = EmailMessage(
        tenant_id=access.tenant_id,
        to_email=access.email,
        subject=title,
        body=body or title,
        kind=kind,
        status=EMAIL_STATUS_QUEUED,
    )
    db.add(message)
    return message


def queue_integration_event(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    event: str,
    payload: dict,
    kinds: tuple[str, ...] | None = None,
) -> list[IntegrationDelivery]:
    """Queue an event to every enabled integration endpoint of the tenant.

    Deliveries stay ``PENDING`` — no outbound call is made here.
    """
    conditions = [
        IntegrationEndpoint.tenant_id == tenant_id,
        IntegrationEndpoint.enabled.is_(True),
        IntegrationEndpoint.deleted_at.is_(None),
    ]
    if kinds:
        conditions.append(IntegrationEndpoint.kind.in_(kinds))
    endpoints = db.execute(
        select(IntegrationEndpoint).where(*conditions)
    ).scalars()
    deliveries: list[IntegrationDelivery] = []
    for endpoint in endpoints:
        delivery = IntegrationDelivery(
            tenant_id=tenant_id,
            endpoint_id=endpoint.id,
            event=event,
            payload=payload,
            status=DELIVERY_PENDING,
        )
        db.add(delivery)
        deliveries.append(delivery)
    return deliveries
