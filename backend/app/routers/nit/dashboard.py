"""NIT — operational dashboard/indicators (``/api/nit/dashboard``).

Every number comes from a REAL query over the tenant's records. Nothing is
fabricated, estimated or hardcoded.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_permission
from app.models.nit import (
    Evaluation,
    InventionDisclosure,
    InventionDocument,
    IPAsset,
)
from app.rbac import AccessContext
from app.routers.nit._common import list_scope
from app.schemas.nit import NitDashboard

router = APIRouter(tags=["nit"])


def _grouped_counts(db: Session, model, column, tenant_id) -> dict[str, int]:
    conditions = [model.deleted_at.is_(None)]
    if tenant_id is not None:
        conditions.append(model.tenant_id == tenant_id)
    rows = db.execute(
        select(column, func.count()).where(*conditions).group_by(column)
    ).all()
    return {str(k): int(v) for k, v in rows}


@router.get("/dashboard", response_model=NitDashboard)
def dashboard(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_REPORT_VIEW")),
) -> NitDashboard:
    tenant = list_scope(ctx)

    disclosure_conditions = [InventionDisclosure.deleted_at.is_(None)]
    recent_conditions = [
        InventionDisclosure.deleted_at.is_(None),
        InventionDisclosure.created_at >= datetime.now(timezone.utc)
        - timedelta(days=30),
    ]
    asset_conditions = [IPAsset.deleted_at.is_(None)]
    document_conditions = [InventionDocument.deleted_at.is_(None)]
    evaluation_conditions = [Evaluation.deleted_at.is_(None)]
    pending_conditions = [
        Evaluation.deleted_at.is_(None),
        Evaluation.outcome == "PENDING",
    ]
    if tenant is not None:
        disclosure_conditions.append(InventionDisclosure.tenant_id == tenant)
        recent_conditions.append(InventionDisclosure.tenant_id == tenant)
        asset_conditions.append(IPAsset.tenant_id == tenant)
        document_conditions.append(InventionDocument.tenant_id == tenant)
        evaluation_conditions.append(Evaluation.tenant_id == tenant)
        pending_conditions.append(Evaluation.tenant_id == tenant)

    disclosure_total = db.execute(
        select(func.count())
        .select_from(InventionDisclosure)
        .where(*disclosure_conditions)
    ).scalar_one()

    recent = db.execute(
        select(func.count())
        .select_from(InventionDisclosure)
        .where(*recent_conditions)
    ).scalar_one()

    assets_total = db.execute(
        select(func.count()).select_from(IPAsset).where(*asset_conditions)
    ).scalar_one()

    documents_total = db.execute(
        select(func.count())
        .select_from(InventionDocument)
        .where(*document_conditions)
    ).scalar_one()

    evaluations_total = db.execute(
        select(func.count()).select_from(Evaluation).where(*evaluation_conditions)
    ).scalar_one()
    pending_evaluations = db.execute(
        select(func.count()).select_from(Evaluation).where(*pending_conditions)
    ).scalar_one()

    return NitDashboard(
        disclosure_total=int(disclosure_total),
        disclosures_by_status=_grouped_counts(
            db, InventionDisclosure, InventionDisclosure.status, tenant
        ),
        disclosures_by_area={
            k: v
            for k, v in _grouped_counts(
                db, InventionDisclosure, InventionDisclosure.technology_area, tenant
            ).items()
            if k != "None"
        },
        documents_total=int(documents_total),
        assets_total=int(assets_total),
        assets_by_status=_grouped_counts(db, IPAsset, IPAsset.status, tenant),
        assets_by_type=_grouped_counts(db, IPAsset, IPAsset.asset_type, tenant),
        evaluations_total=int(evaluations_total),
        pending_evaluations=int(pending_evaluations),
        disclosure_created_last_30_days=int(recent),
    )
