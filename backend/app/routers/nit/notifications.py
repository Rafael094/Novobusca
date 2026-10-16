"""NIT F5 — notifications (``/api/nit/notifications``).

Notifications are always tenant- and user-scoped: a caller only ever sees its own
notifications. E-mail is only queued (see ``services/notifications.py``); the
endpoints here never claim a delivery that a real transport did not perform.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_permission
from app.models.nit_f5 import (
    NOTIFICATION_KINDS,
    EmailMessage,
    Notification,
    NotificationPreference,
)
from app.rbac import AccessContext
from app.schemas.nit_f5 import (
    EmailMessageIn,
    EmailMessageOut,
    NotificationOut,
    NotificationPreferenceIn,
    NotificationPreferenceOut,
    PaginatedNotifications,
)

router = APIRouter(prefix="/notifications", tags=["nit"])


@router.get("", response_model=PaginatedNotifications)
def list_notifications(
    unread_only: bool = False,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_NOTIFICATION_VIEW")),
) -> PaginatedNotifications:
    conditions = [
        Notification.tenant_id == ctx.user.tenant_id,
        Notification.user_id == ctx.user.id,
    ]
    if unread_only:
        conditions.append(Notification.read_at.is_(None))
    total = int(
        db.execute(
            select(func.count()).select_from(Notification).where(*conditions)
        ).scalar_one()
    )
    unread = int(
        db.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.tenant_id == ctx.user.tenant_id,
                Notification.user_id == ctx.user.id,
                Notification.read_at.is_(None),
            )
        ).scalar_one()
    )
    rows = db.execute(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars()
    return PaginatedNotifications(
        items=[NotificationOut.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=total,
        unread=unread,
    )


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_NOTIFICATION_VIEW")),
) -> NotificationOut:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != ctx.user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notificação não encontrada"
        )
    if notification.read_at is None:
        notification.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(notification)
    return NotificationOut.model_validate(notification)


@router.post("/read-all", response_model=dict)
def mark_all_read(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_NOTIFICATION_VIEW")),
) -> dict:
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(Notification).where(
            Notification.tenant_id == ctx.user.tenant_id,
            Notification.user_id == ctx.user.id,
            Notification.read_at.is_(None),
        )
    ).scalars()
    count = 0
    for row in rows:
        row.read_at = now
        count += 1
    db.commit()
    return {"updated": count}


@router.get("/preferences", response_model=list[NotificationPreferenceOut])
def list_preferences(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_NOTIFICATION_VIEW")),
) -> list[NotificationPreferenceOut]:
    rows = db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == ctx.user.id)
    ).scalars()
    return [NotificationPreferenceOut.model_validate(r) for r in rows]


@router.put("/preferences", response_model=NotificationPreferenceOut)
def upsert_preference(
    payload: NotificationPreferenceIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_NOTIFICATION_VIEW")),
) -> NotificationPreferenceOut:
    if payload.kind not in NOTIFICATION_KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tipo de notificação inválido",
        )
    pref = db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == ctx.user.id,
            NotificationPreference.kind == payload.kind,
        )
    ).scalar_one_or_none()
    if pref is None:
        pref = NotificationPreference(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            kind=payload.kind,
            in_app_enabled=payload.in_app_enabled,
            email_enabled=payload.email_enabled,
        )
        db.add(pref)
    else:
        pref.in_app_enabled = payload.in_app_enabled
        pref.email_enabled = payload.email_enabled
    db.commit()
    db.refresh(pref)
    return NotificationPreferenceOut.model_validate(pref)


# --- E-mail outbox (queue only) --------------------------------------------
@router.get("/emails", response_model=list[EmailMessageOut])
def list_emails(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_NOTIFICATION_MANAGE")),
) -> list[EmailMessageOut]:
    conditions = [EmailMessage.tenant_id == ctx.user.tenant_id]
    if status_filter:
        conditions.append(EmailMessage.status == status_filter)
    rows = db.execute(
        select(EmailMessage)
        .where(*conditions)
        .order_by(EmailMessage.created_at.desc())
        .limit(200)
    ).scalars()
    return [EmailMessageOut.model_validate(r) for r in rows]


@router.post("/emails", response_model=EmailMessageOut, status_code=status.HTTP_201_CREATED)
def queue_email(
    payload: EmailMessageIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_NOTIFICATION_MANAGE")),
) -> EmailMessageOut:
    """Queue an e-mail. It remains ``QUEUED`` until a real transport sends it."""
    message = EmailMessage(
        tenant_id=ctx.user.tenant_id,
        to_email=payload.to_email,
        subject=payload.subject,
        body=payload.body,
        kind=payload.kind,
        created_by=ctx.user.id,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return EmailMessageOut.model_validate(message)

