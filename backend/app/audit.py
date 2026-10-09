"""Audit logging helpers."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models import AuditLog


def record_audit(
    db: Session,
    *,
    action: str,
    tenant_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    resource: str | None = None,
    resource_id: str | None = None,
    meta: dict | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
    commit: bool = True,
) -> AuditLog:
    """Persist an audit log entry.

    By default the row is committed immediately so audit entries survive even if
    the surrounding request later fails.
    """
    entry = AuditLog(
        action=action,
        tenant_id=tenant_id,
        user_id=user_id,
        resource=resource,
        resource_id=str(resource_id) if resource_id is not None else None,
        meta=meta,
        ip=ip,
        user_agent=user_agent,
    )
    db.add(entry)
    if commit:
        db.commit()
    return entry
