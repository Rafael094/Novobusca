"""NIT F5 — external portals (``/api/nit/portal``).

Two audiences are modelled by ``ExternalPortalAccess`` grants: researchers and
companies. A grant is explicit, tenant-scoped and revocable; it never confers
internal NIT permissions. External submissions land as ``PortalRequest`` records
that internal staff triage.

The public (unauthenticated) submission endpoint requires a valid, active,
non-expired grant identified by its e-mail + a per-grant ``access_token``; there
is no way to read other grantees' data.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models.nit_f5 import (
    PORTAL_ACCESS_ACTIVE,
    ExternalPortalAccess,
    PortalRequest,
    PortalRequestNote,
)
from app.rbac import AccessContext
from app.routers.nit._common import (
    assert_same_tenant,
    list_scope,
    scoped_tenant,
    write_tenant,
)
from app.schemas.nit_f5 import (
    PortalAccessCreate,
    PortalAccessCreated,
    PortalAccessOut,
    PortalRequestCreate,
    PortalRequestDetail,
    PortalRequestNoteOut,
    PortalRequestOut,
    PortalRequestTriage,
)
from app.services.notifications import notify_portal_grantee

router = APIRouter(prefix="/portal", tags=["nit"])


def _access_or_404(db: Session, ctx: AccessContext, access_id: uuid.UUID) -> ExternalPortalAccess:
    access = db.get(ExternalPortalAccess, access_id)
    if access is None or access.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Concessão não encontrada"
        )
    assert_same_tenant(ctx, access.tenant_id)
    return access


# --- Grants (internal management) -------------------------------------------
@router.get("/access", response_model=list[PortalAccessOut])
def list_access(
    portal_kind: str | None = Query(default=None, pattern="^(RESEARCHER|COMPANY)$"),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PORTAL_VIEW")),
) -> list[PortalAccessOut]:
    scope = list_scope(ctx)
    conditions = [ExternalPortalAccess.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(ExternalPortalAccess.tenant_id == scope)
    if portal_kind:
        conditions.append(ExternalPortalAccess.portal_kind == portal_kind)
    rows = db.execute(
        select(ExternalPortalAccess)
        .where(*conditions)
        .order_by(ExternalPortalAccess.created_at.desc())
    ).scalars()
    return [PortalAccessOut.model_validate(r) for r in rows]


@router.post("/access", response_model=PortalAccessCreated, status_code=status.HTTP_201_CREATED)
def create_access(
    payload: PortalAccessCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PORTAL_MANAGE")),
) -> PortalAccessCreated:
    tenant = write_tenant(ctx, None)
    existing = db.execute(
        select(ExternalPortalAccess).where(
            ExternalPortalAccess.tenant_id == tenant,
            ExternalPortalAccess.portal_kind == payload.portal_kind,
            ExternalPortalAccess.email == payload.email,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este e-mail já possui acesso a este portal",
        )
    access = ExternalPortalAccess(
        tenant_id=tenant,
        granted_by=ctx.user.id,
        access_token=secrets.token_urlsafe(32),
        **payload.model_dump(),
    )
    db.add(access)
    db.commit()
    db.refresh(access)
    # The token is revealed exactly once, at creation time, to the granting staff.
    return PortalAccessCreated(
        **PortalAccessOut.model_validate(access).model_dump(),
        access_token=access.access_token,
    )


@router.post("/access/{access_id}/revoke", response_model=PortalAccessOut)
def revoke_access(
    access_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PORTAL_MANAGE")),
) -> PortalAccessOut:
    access = _access_or_404(db, ctx, access_id)
    if access.status != "REVOKED":
        access.status = "REVOKED"
        db.commit()
        db.refresh(access)
    return PortalAccessOut.model_validate(access)


# --- Requests (internal triage) ---------------------------------------------
@router.get("/requests", response_model=list[PortalRequestOut])
def list_requests(
    status_filter: str | None = Query(default=None, alias="status"),
    portal_kind: str | None = Query(default=None, pattern="^(RESEARCHER|COMPANY)$"),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PORTAL_REQUEST_VIEW")),
) -> list[PortalRequestOut]:
    scope = list_scope(ctx)
    conditions = []
    if scope is not None:
        conditions.append(PortalRequest.tenant_id == scope)
    if status_filter:
        conditions.append(PortalRequest.status == status_filter)
    if portal_kind:
        conditions.append(PortalRequest.access_id.in_(
            select(ExternalPortalAccess.id).where(
                ExternalPortalAccess.portal_kind == portal_kind
            )
        ))
    rows = db.execute(
        select(PortalRequest)
        .where(*conditions)
        .order_by(PortalRequest.created_at.desc())
        .limit(200)
    ).scalars()
    return [PortalRequestOut.model_validate(r) for r in rows]


@router.get("/requests/{request_id}", response_model=PortalRequestDetail)
def get_request(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PORTAL_REQUEST_VIEW")),
) -> PortalRequestDetail:
    request = db.get(PortalRequest, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Solicitação não encontrada"
        )
    assert_same_tenant(ctx, request.tenant_id)
    detail = PortalRequestDetail.model_validate(request)
    detail.notes = [
        PortalRequestNoteOut.model_validate(r)
        for r in db.execute(
            select(PortalRequestNote)
            .where(PortalRequestNote.request_id == request.id)
            .order_by(PortalRequestNote.created_at.asc())
        ).scalars()
    ]
    return detail


@router.post("/requests/{request_id}/triage", response_model=PortalRequestDetail)
def triage_request(
    request_id: uuid.UUID,
    payload: PortalRequestTriage,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PORTAL_REQUEST_MANAGE")),
    meta: dict = Depends(client_meta),
) -> PortalRequestDetail:
    request = db.get(PortalRequest, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Solicitação não encontrada"
        )
    assert_same_tenant(ctx, request.tenant_id)
    request.status = payload.status
    request.triaged_by = ctx.user.id
    request.triaged_at = datetime.now(timezone.utc)
    if payload.note:
        db.add(
            PortalRequestNote(
                tenant_id=request.tenant_id,
                request_id=request.id,
                author_id=ctx.user.id,
                body=payload.note,
            )
        )
    record_audit(
        db,
        action="NIT_PORTAL_REQUEST_TRIAGE",
        tenant_id=request.tenant_id,
        user_id=ctx.user.id,
        resource="portal_request",
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        meta={"status": payload.status},
        commit=False,
    )
    db.commit()
    db.refresh(request)
    return get_request(request_id, db=db, ctx=ctx)


# --- Public submission (token + e-mail identifies an active grant) ----------
@router.post(
    "/public/{portal_kind}/requests",
    response_model=PortalRequestOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_public_request(
    portal_kind: str,
    payload: PortalRequestCreate,
    email: str = Query(min_length=3, max_length=320),
    token: str = Query(min_length=8),
    db: Session = Depends(get_db),
) -> PortalRequestOut:
    """External submission. Requires an active grant matching ``email`` + ``token``.

    The token is compared in constant time. Revoked/expired grants are rejected.
    No internal data is returned — only the created request.
    """
    if portal_kind not in ("RESEARCHER", "COMPANY"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Portal inexistente"
        )
    access = db.execute(
        select(ExternalPortalAccess).where(
            ExternalPortalAccess.portal_kind == portal_kind,
            ExternalPortalAccess.email == email,
            ExternalPortalAccess.status == PORTAL_ACCESS_ACTIVE,
            ExternalPortalAccess.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if access is None or not secrets.compare_digest(access.access_token or "", token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Acesso inválido"
        )
    if access.expires_at is not None and access.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Acesso expirado"
        )
    request = PortalRequest(
        tenant_id=access.tenant_id,
        access_id=access.id,
        request_type=payload.request_type,
        subject=payload.subject,
        message=payload.message,
        payload=payload.payload,
    )
    db.add(request)
    notify_portal_grantee(
        db,
        access=access,
        title="Solicitação recebida",
        body="Sua solicitação foi registrada e será analisada pelo NIT.",
    )
    db.commit()
    db.refresh(request)
    return PortalRequestOut.model_validate(request)

