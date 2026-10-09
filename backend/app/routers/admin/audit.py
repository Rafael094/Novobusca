"""Audit log viewing (master admin / AUDIT_VIEW permission)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_permission
from app.models import AuditLog
from app.rbac import AccessContext
from app.schemas.auth import AuditLogOut

router = APIRouter(prefix="/audit")


@router.get("", response_model=list[AuditLogOut])
def list_audit(
    tenant_id: uuid.UUID | None = None,
    action: str | None = None,
    user_id: uuid.UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("AUDIT_VIEW")),
) -> list[AuditLogOut]:
    limit = max(1, min(limit, 500))
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if not ctx.user.is_master_admin:
        # Non-master admins only ever see their own tenant's audit trail.
        stmt = stmt.where(AuditLog.tenant_id == ctx.user.tenant_id)
    elif tenant_id is not None:
        stmt = stmt.where(AuditLog.tenant_id == tenant_id)
    if action is not None:
        stmt = stmt.where(AuditLog.action == action)
    if user_id is not None:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if date_from is not None:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(AuditLog.created_at <= date_to)
    stmt = stmt.offset(offset).limit(limit)
    logs = db.execute(stmt).scalars().all()
    return [AuditLogOut.model_validate(log) for log in logs]
