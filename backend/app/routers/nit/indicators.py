"""NIT F4 — institutional indicators and FORMICT support report (``/api/nit``).

Every indicator is computed from REAL queries over the tenant's records (see
``services/indicators.py``). The FORMICT report is explicitly an INTERNAL SUPPORT
document, not the official submission, and does not invent fields,
classifications or legal calculations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models.nit_f3 import (
    Contract,
    Royalty,
    TechnologyOffer,
)
from app.models.nit_f4 import Project, Startup
from app.rbac import AccessContext
from app.routers.nit._common import list_scope
from app.schemas.nit_f4 import FormictReport, InstitutionalIndicators
from app.services.indicators import _count, compute_indicators

router = APIRouter(tags=["nit"])

FORMICT_DISCLAIMER = (
    "Relatório INTERNO de apoio ao levantamento institucional. NÃO é o formulário "
    "oficial do FORMICT nem substitui a submissão à autoridade competente. Campos, "
    "classificações e cálculos legais devem ser confirmados com as fontes oficiais."
)


def _resolve_tenant(ctx: AccessContext):
    """Tenant scope for indicator endpoints.

    ``None`` means "every tenant" and is only reachable by a master admin; an
    ordinary user always resolves to their own tenant (see ``list_scope``).
    """
    return list_scope(ctx)


@router.get("/indicators", response_model=InstitutionalIndicators)
def indicators(
    days: int = Query(default=30, ge=1, le=3650),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_INDICATOR_VIEW")),
) -> InstitutionalIndicators:
    tenant = _resolve_tenant(ctx)
    return compute_indicators(db, tenant, days)


@router.get("/formict", response_model=FormictReport)
def formict_report(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_FORMICT_VIEW")),
) -> FormictReport:
    """Internal support report — explicitly NOT the official FORMICT submission."""
    tenant = _resolve_tenant(ctx)
    contracts_total = _count(db, Contract, tenant)
    contracts_active = _count(db, Contract, tenant, Contract.status == "ACTIVE")

    royalty_conditions = []
    if tenant is not None:
        royalty_conditions.append(Royalty.tenant_id == tenant)
    total_registered = db.execute(
        select(func.coalesce(func.sum(Royalty.registered_amount), 0)).where(
            *royalty_conditions
        )
    ).scalar_one()
    total_received = db.execute(
        select(func.coalesce(func.sum(Royalty.received_amount), 0)).where(
            *royalty_conditions
        )
    ).scalar_one()

    return FormictReport(
        disclaimer=FORMICT_DISCLAIMER,
        generated_at=datetime.now(timezone.utc),
        institution=str(tenant) if tenant is not None else "Todas as instituições",
        contracts_active=contracts_active,
        contracts_total=contracts_total,
        total_registered=Decimal(total_registered or 0),
        total_received=Decimal(total_received or 0),
        technologies_offered=_count(
            db, TechnologyOffer, tenant, TechnologyOffer.status == "PUBLISHED"
        ),
        transfers_effective=_count(db, Contract, tenant, Contract.status == "ACTIVE"),
        projects_active=_count(db, Project, tenant, Project.status == "ACTIVE"),
        startups_supported=_count(db, Startup, tenant),
    )


@router.get("/formict/export")
def formict_export(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_FORMICT_EXPORT")),
    meta: dict = Depends(client_meta),
) -> Response:
    """CSV export of the internal support report (still not the official form)."""
    report = formict_report(db=db, ctx=ctx)
    lines = [
        f"# {FORMICT_DISCLAIMER}",
        "indicador,valor",
        f"contracts_active,{report.contracts_active}",
        f"contracts_total,{report.contracts_total}",
        f"total_registered,{report.total_registered}",
        f"total_received,{report.total_received}",
        f"technologies_offered,{report.technologies_offered}",
        f"transfers_effective,{report.transfers_effective}",
        f"projects_active,{report.projects_active}",
        f"startups_supported,{report.startups_supported}",
        f"generated_at,{report.generated_at.isoformat()}",
    ]
    record_audit(
        db,
        action="NIT_FORMICT_EXPORT",
        tenant_id=ctx.user.tenant_id,
        user_id=ctx.user.id,
        resource="formict_report",
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return Response(
        content="\n".join(lines),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="formict_apoio.csv"'},
    )

