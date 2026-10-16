"""NIT F5 — BI reports (``/api/nit/bi``).

A saved report only selects which REAL metrics run: the definition stores metric
keys and filter values (never results or fabricated numbers). Running a report
executes the same real queries as ``/indicators`` and freezes the result in an
append-only ``ReportRun`` so a past snapshot can be audited.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models.nit_f5 import ReportRun, SavedReport
from app.rbac import AccessContext
from app.routers.nit._common import assert_same_tenant, scoped_tenant, write_tenant
from app.schemas.nit_f4 import InstitutionalIndicators
from app.schemas.nit_f5 import SavedReportCreate, SavedReportOut
from app.services.indicators import compute_indicators

router = APIRouter(prefix="/bi", tags=["nit"])

# Metric keys a report may select. Each maps to a REAL indicator field.
ALLOWED_METRICS: tuple[str, ...] = tuple(InstitutionalIndicators.model_fields.keys())


@router.get("/metrics", response_model=list[str])
def list_metrics(
    ctx: AccessContext = Depends(require_permission("NIT_BI_VIEW")),
) -> list[str]:
    """The metric keys a report can select (all derive from real queries)."""
    return list(ALLOWED_METRICS)


@router.get("/reports", response_model=list[SavedReportOut])
def list_reports(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_BI_VIEW")),
) -> list[SavedReportOut]:
    scope = scoped_tenant(ctx, None, allow_all=True)
    conditions = [SavedReport.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(SavedReport.tenant_id == scope)
    rows = db.execute(
        select(SavedReport).where(*conditions).order_by(SavedReport.created_at.desc())
    ).scalars()
    return [SavedReportOut.model_validate(r) for r in rows]


@router.post("/reports", response_model=SavedReportOut, status_code=status.HTTP_201_CREATED)
def create_report(
    payload: SavedReportCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_BI_MANAGE")),
) -> SavedReportOut:
    invalid = [m for m in payload.metrics if m not in ALLOWED_METRICS]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Métricas inválidas: {', '.join(invalid)}",
        )
    tenant = write_tenant(ctx, None)
    existing = db.execute(
        select(SavedReport).where(
            SavedReport.tenant_id == tenant, SavedReport.name == payload.name
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Já existe um relatório com este nome"
        )
    report = SavedReport(tenant_id=tenant, created_by=ctx.user.id, **payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return SavedReportOut.model_validate(report)


def _report_or_404(db: Session, ctx: AccessContext, report_id: uuid.UUID) -> SavedReport:
    report = db.get(SavedReport, report_id)
    if report is None or report.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Relatório não encontrado"
        )
    assert_same_tenant(ctx, report.tenant_id)
    return report


@router.post("/reports/{report_id}/run", response_model=dict)
def run_report(
    report_id: uuid.UUID,
    days: int = 30,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_BI_VIEW")),
) -> dict:
    """Execute the selected REAL metrics and freeze the result in an append-only run."""
    report = _report_or_404(db, ctx, report_id)
    indicators = compute_indicators(db, report.tenant_id, days)
    full = indicators.model_dump(mode="json")
    selected = report.metrics or list(ALLOWED_METRICS)
    result = {key: full.get(key) for key in selected if key in full}
    run = ReportRun(
        tenant_id=report.tenant_id,
        report_id=report.id,
        ran_by=ctx.user.id,
        result=result,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return {"report_id": str(report.id), "result": result, "run_id": str(run.id)}


@router.get("/reports/{report_id}/export")
def export_report(
    report_id: uuid.UUID,
    days: int = 30,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_BI_VIEW")),
    meta: dict = Depends(client_meta),
) -> Response:
    """CSV export of a report run (values come from the real indicator queries)."""
    report = _report_or_404(db, ctx, report_id)
    indicators = compute_indicators(db, report.tenant_id, days)
    full = indicators.model_dump(mode="json")
    selected = report.metrics or list(ALLOWED_METRICS)
    lines = ["indicador,valor"]
    for key in selected:
        if key in full:
            lines.append(f"{key},{full[key]}")
    record_audit(
        db,
        action="NIT_BI_REPORT_EXPORT",
        tenant_id=report.tenant_id,
        user_id=ctx.user.id,
        resource="saved_report",
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return Response(
        content="\n".join(lines),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="bi_{report.id}.csv"'},
    )

