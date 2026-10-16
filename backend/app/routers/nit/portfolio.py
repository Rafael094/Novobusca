"""NIT F2 — TRL/maturity and advanced portfolio endpoints (``/api/nit``).

* ``/trl``            — append-only TRL history with mandatory rationale (never auto).
* ``/portfolio``      — advanced views: by type/status/unity, real deadline alerts.
* ``/portfolio/export`` — authorized CSV export of the portfolio.
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models.nit import IPAsset, InventionDisclosure
from app.models.nit_f2 import TechnologyReadinessLevel
from app.rbac import AccessContext
from app.routers.nit._common import assert_same_tenant, list_scope, scoped_tenant
from app.schemas.nit_f2 import (
    DeadlineAlert,
    PortfolioAsset,
    PortfolioView,
    TrlCreate,
    TrlOut,
)

router = APIRouter(tags=["nit"])

EXPIRING_SOON_DAYS = 90


def _latest_trl(db: Session, *, disclosure_id=None, asset_id=None) -> int | None:
    q = select(TechnologyReadinessLevel).order_by(
        TechnologyReadinessLevel.created_at.desc()
    )
    if disclosure_id is not None:
        q = q.where(TechnologyReadinessLevel.disclosure_id == disclosure_id)
    else:
        q = q.where(TechnologyReadinessLevel.asset_id == asset_id)
    row = db.execute(q).scalars().first()
    return row.level if row else None


# --- TRL --------------------------------------------------------------------
@router.get("/trl/history", response_model=list[TrlOut])
def trl_history(
    disclosure_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_TRL_VIEW")),
) -> list[TrlOut]:
    scope = list_scope(ctx)
    conditions = []
    if scope is not None:
        conditions.append(TechnologyReadinessLevel.tenant_id == scope)
    if disclosure_id is not None:
        conditions.append(TechnologyReadinessLevel.disclosure_id == disclosure_id)
    if asset_id is not None:
        conditions.append(TechnologyReadinessLevel.asset_id == asset_id)
    rows = db.execute(
        select(TechnologyReadinessLevel)
        .where(*conditions)
        .order_by(TechnologyReadinessLevel.created_at.desc())
    ).scalars()
    return [TrlOut.model_validate(r) for r in rows]


@router.post("/trl", response_model=TrlOut, status_code=status.HTTP_201_CREATED)
def record_trl(
    payload: TrlCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_TRL_MANAGE")),
    meta: dict = Depends(client_meta),
) -> TrlOut:
    if (payload.disclosure_id is None) == (payload.asset_id is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe exatamente um: disclosure_id ou asset_id",
        )

    tenant = None
    previous = None
    if payload.disclosure_id is not None:
        disclosure = db.get(InventionDisclosure, payload.disclosure_id)
        if disclosure is None or disclosure.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Comunicação não encontrada"
            )
        assert_same_tenant(ctx, disclosure.tenant_id)
        tenant = disclosure.tenant_id
        previous = _latest_trl(db, disclosure_id=disclosure.id)
    else:
        asset = db.get(IPAsset, payload.asset_id)
        if asset is None or asset.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Ativo não encontrado"
            )
        assert_same_tenant(ctx, asset.tenant_id)
        tenant = asset.tenant_id
        previous = _latest_trl(db, asset_id=asset.id)

    entry = TechnologyReadinessLevel(
        tenant_id=tenant,
        disclosure_id=payload.disclosure_id,
        asset_id=payload.asset_id,
        level=payload.level,
        previous_level=previous,
        rationale=payload.rationale,
        evidence=payload.evidence,
        evaluator_id=ctx.user.id,
    )
    db.add(entry)
    record_audit(
        db,
        action="NIT_TRL_RECORD",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="trl_history",
        resource_id=entry.id,
        meta={"level": payload.level, "previous": previous},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(entry)
    return TrlOut.model_validate(entry)


# --- Portfolio --------------------------------------------------------------
def _portfolio_rows(
    db: Session,
    scope: uuid.UUID | None,
    *,
    asset_type=None,
    status_filter=None,
    unity_id=None,
) -> list[IPAsset]:
    conditions = [IPAsset.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(IPAsset.tenant_id == scope)
    if asset_type:
        conditions.append(IPAsset.asset_type == asset_type)
    if status_filter:
        conditions.append(IPAsset.status == status_filter)
    if unity_id is not None:
        conditions.append(IPAsset.unity_id == unity_id)
    return list(db.execute(select(IPAsset).where(*conditions)).scalars())


@router.get("/portfolio", response_model=PortfolioView)
def portfolio(
    asset_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    unity_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PORTFOLIO_VIEW")),
) -> PortfolioView:
    scope = list_scope(ctx)
    rows = _portfolio_rows(
        db, scope, asset_type=asset_type, status_filter=status_filter, unity_id=unity_id
    )
    now = datetime.now(timezone.utc)
    items: list[PortfolioAsset] = []
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    expiring = expired = 0
    for a in rows:
        days = None
        if a.expires_at is not None:
            days = (a.expires_at - now).days
            if days < 0:
                expired += 1
            elif days <= EXPIRING_SOON_DAYS:
                expiring += 1
        by_type[a.asset_type] = by_type.get(a.asset_type, 0) + 1
        by_status[a.status] = by_status.get(a.status, 0) + 1
        items.append(
            PortfolioAsset(
                id=a.id,
                code=a.code,
                title=a.title,
                asset_type=a.asset_type,
                status=a.status,
                technology_area=a.technology_area,
                unity_id=a.unity_id,
                deposited_at=a.deposited_at,
                granted_at=a.granted_at,
                expires_at=a.expires_at,
                days_to_expiry=days,
                trl_level=_latest_trl(db, asset_id=a.id),
            )
        )
    return PortfolioView(
        items=items,
        total=len(items),
        by_type=by_type,
        by_status=by_status,
        expiring_soon=expiring,
        expired=expired,
    )


@router.get("/portfolio/alerts", response_model=list[DeadlineAlert])
def portfolio_alerts(
    days: int = Query(default=EXPIRING_SOON_DAYS, ge=1, le=3650),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PORTFOLIO_VIEW")),
) -> list[DeadlineAlert]:
    """Assets whose validity expires within ``days`` (or already expired).

    No expiry date is ever invented: only rows with a real ``expires_at`` appear.
    """
    scope = list_scope(ctx)
    now = datetime.now(timezone.utc)
    conditions = [
        IPAsset.deleted_at.is_(None),
        IPAsset.expires_at.is_not(None),
    ]
    if scope is not None:
        conditions.append(IPAsset.tenant_id == scope)
    rows = db.execute(
        select(IPAsset).where(*conditions)
    ).scalars()
    alerts: list[DeadlineAlert] = []
    for a in rows:
        d = (a.expires_at - now).days
        if d > days:
            continue
        severity = "expired" if d < 0 else ("critical" if d <= 30 else "warning")
        alerts.append(
            DeadlineAlert(
                asset_id=a.id,
                code=a.code,
                title=a.title,
                expires_at=a.expires_at,
                days_to_expiry=d,
                severity=severity,
            )
        )
    alerts.sort(key=lambda x: x.days_to_expiry)
    return alerts


@router.get("/portfolio/export")
def export_portfolio(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PORTFOLIO_EXPORT")),
    meta: dict = Depends(client_meta),
) -> Response:
    scope = list_scope(ctx)
    rows = _portfolio_rows(db, scope)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["codigo", "titulo", "tipo", "situacao", "area", "deposito", "concessao", "vigencia", "trl"]
    )
    for a in rows:
        writer.writerow(
            [
                a.code,
                a.title,
                a.asset_type,
                a.status,
                a.technology_area or "",
                a.deposited_at.isoformat() if a.deposited_at else "",
                a.granted_at.isoformat() if a.granted_at else "",
                a.expires_at.isoformat() if a.expires_at else "",
                _latest_trl(db, asset_id=a.id) or "",
            ]
        )
    record_audit(
        db,
        action="NIT_PORTFOLIO_EXPORT",
        tenant_id=scope,
        user_id=ctx.user.id,
        resource="ip_asset",
        meta={"rows": len(rows)},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="portfolio_nit.csv"'},
    )

