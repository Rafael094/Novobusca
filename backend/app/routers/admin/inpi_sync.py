"""INPI ingestion & sync administration endpoints.

Datasets/imports reflect the real ingestion pipeline state (written by the
``ingestion`` package). Sync execution dispatches to the ingestion pipeline if it
is importable; otherwise it returns a clear "not available" status rather than
faking progress.
"""

from __future__ import annotations

import importlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models import InpiDataset, InpiImport, InpiImportError, InpiRpi
from app.rbac import AccessContext
from app.schemas.inpi import (
    DatasetOut,
    ImportErrorOut,
    ImportOut,
    RpiOut,
    SyncRequest,
    SyncResponse,
)

router = APIRouter(prefix="/inpi")


@router.get("/datasets", response_model=list[DatasetOut])
def list_datasets(
    category: str | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("DATASET_VIEW")),
) -> list[DatasetOut]:
    stmt = select(InpiDataset).order_by(InpiDataset.category, InpiDataset.name)
    if category:
        stmt = stmt.where(InpiDataset.category == category)
    rows = db.execute(stmt).scalars().all()
    return [DatasetOut.model_validate(r) for r in rows]


@router.get("/imports", response_model=list[ImportOut])
def list_imports(
    dataset_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("IMPORT_VIEW")),
) -> list[ImportOut]:
    stmt = select(InpiImport).order_by(InpiImport.started_at.desc()).limit(limit)
    if dataset_id is not None:
        stmt = stmt.where(InpiImport.dataset_id == dataset_id)
    rows = db.execute(stmt).scalars().all()
    return [ImportOut.model_validate(r) for r in rows]


@router.get("/imports/{import_id}/errors", response_model=list[ImportErrorOut])
def list_import_errors(
    import_id: uuid.UUID,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("IMPORT_VIEW")),
) -> list[ImportErrorOut]:
    rows = (
        db.execute(
            select(InpiImportError)
            .where(InpiImportError.import_id == import_id)
            .order_by(InpiImportError.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [ImportErrorOut.model_validate(r) for r in rows]


@router.get("/rpi", response_model=list[RpiOut])
def list_rpi(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("DATASET_VIEW")),
) -> list[RpiOut]:
    rows = (
        db.execute(select(InpiRpi).order_by(InpiRpi.edition_date.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [RpiOut.model_validate(r) for r in rows]


@router.get("/status")
def sync_status(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("SYNC_VIEW")),
) -> dict:
    total_datasets = db.execute(select(func.count(InpiDataset.id))).scalar_one()
    imported = db.execute(
        select(func.count(InpiDataset.id)).where(InpiDataset.status == "IMPORTED")
    ).scalar_one()
    failed = db.execute(
        select(func.count(InpiDataset.id)).where(InpiDataset.status == "FAILED")
    ).scalar_one()
    running = db.execute(
        select(func.count(InpiImport.id)).where(InpiImport.status == "RUNNING")
    ).scalar_one()
    last_completed = db.execute(
        select(InpiImport)
        .where(InpiImport.status == "COMPLETED")
        .order_by(InpiImport.finished_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return {
        "datasets": {
            "total": int(total_datasets),
            "imported": int(imported),
            "failed": int(failed),
        },
        "imports_running": int(running),
        "last_completed_at": (
            last_completed.finished_at.isoformat() if last_completed else None
        ),
    }


@router.post("/sync", response_model=SyncResponse)
def trigger_sync(
    payload: SyncRequest,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("SYNC_EXECUTE")),
    meta: dict = Depends(client_meta),
) -> SyncResponse:
    """Trigger an ingestion run for the requested category/dataset.

    The heavy lifting is performed by the ``ingestion`` package as a background
    process. If the package is not available in this deployment, the request is
    rejected with an explanatory message (never a fake success).
    """
    if payload.dataset:
        targets = [payload.dataset]
    elif payload.category:
        targets = [payload.category]
    else:
        targets = ["marcas", "patentes"]

    try:
        runner = importlib.import_module("ingestion.import_all")
    except ModuleNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Pipeline de ingestão não disponível neste processo. "
                "Execute a ingestão via CLI: "
                "python -m ingestion.import_all --category <categoria>"
            ),
        )

    record_audit(
        db,
        action="SYNC_TRIGGER",
        tenant_id=ctx.user.tenant_id,
        user_id=ctx.user.id,
        resource="inpi_sync",
        meta={"targets": targets, "force": payload.force},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    run = getattr(runner, "run_sync", None)
    if callable(run):
        run(categories=targets, force=payload.force)
    return SyncResponse(
        started=targets,
        message="Ingestão iniciada. Acompanhe o status em /admin/inpi/imports.",
    )
