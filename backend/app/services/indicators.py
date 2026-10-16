"""Institutional indicators computation (F4/F5).

Every value here is derived from REAL queries over the tenant's records. Nothing
is estimated, projected or fabricated: when there is insufficient real data the
field is ``None`` (e.g. average triage time).

This module is the single source of truth for indicators so the ``/indicators``
endpoint and the BI reports (``/bi``) cannot drift apart.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.nit import (
    TERMINAL_STATES,
    Evaluation,
    IPAsset,
    InventionDisclosure,
)
from app.models.nit_f3 import (
    Contract,
    ContractObligation,
    Negotiation,
    TechnologyOffer,
)
from app.models.nit_f4 import Project, Startup
from app.schemas.nit_f4 import InstitutionalIndicators


def _grouped(db: Session, model, column, tenant_id) -> dict[str, int]:
    conditions = []
    if tenant_id is not None:
        conditions.append(model.tenant_id == tenant_id)
    if hasattr(model, "deleted_at"):
        conditions.append(model.deleted_at.is_(None))
    rows = db.execute(
        select(column, func.count()).where(*conditions).group_by(column)
    ).all()
    return {str(k): int(v) for k, v in rows if k is not None}


def _count(db: Session, model, tenant_id, *extra) -> int:
    conditions = []
    if tenant_id is not None:
        conditions.append(model.tenant_id == tenant_id)
    if hasattr(model, "deleted_at"):
        conditions.append(model.deleted_at.is_(None))
    if extra:
        conditions.extend(extra)
    return int(
        db.execute(select(func.count()).select_from(model).where(*conditions)).scalar_one()
    )


def compute_indicators(
    db: Session, tenant_id: uuid.UUID | None, days: int = 30
) -> InstitutionalIndicators:
    """Compute the institutional indicators for one tenant.

    ``tenant_id=None`` aggregates **every** tenant — the master admin's
    cross-tenant view. Ordinary callers always pass their own tenant id.
    """
    now = datetime.now(timezone.utc)
    period_from = now - timedelta(days=days)

    disclosure_total = _count(db, InventionDisclosure, tenant_id)
    pending_evaluations = _count(
        db, Evaluation, tenant_id, Evaluation.outcome == "PENDING"
    )

    triage_conditions = [
        InventionDisclosure.deleted_at.is_(None),
        InventionDisclosure.status.notin_(["PROPOSAL", *sorted(TERMINAL_STATES)]),
    ]
    if tenant_id is not None:
        triage_conditions.append(InventionDisclosure.tenant_id == tenant_id)
    triaged = db.execute(
        select(InventionDisclosure.submitted_at, InventionDisclosure.updated_at).where(
            *triage_conditions
        )
    ).all()
    if triaged:
        deltas = [(u - s).total_seconds() / 86400 for s, u in triaged if s and u]
        average_triage = round(sum(deltas) / len(deltas), 2) if deltas else None
    else:
        average_triage = None

    contracts_active = _count(db, Contract, tenant_id, Contract.status == "ACTIVE")
    obligations_due_soon = 0
    today = now.date()
    due_conditions = [
        ContractObligation.status == "PENDING",
        ContractObligation.due_date.is_not(None),
    ]
    if tenant_id is not None:
        due_conditions.append(ContractObligation.tenant_id == tenant_id)
    due_rows = db.execute(
        select(ContractObligation).where(*due_conditions)
    ).scalars()
    for o in due_rows:
        if 0 <= (o.due_date - today).days <= 60:
            obligations_due_soon += 1

    return InstitutionalIndicators(
        disclosure_total=disclosure_total,
        disclosures_by_status=_grouped(
            db, InventionDisclosure, InventionDisclosure.status, tenant_id
        ),
        disclosures_by_area=_grouped(
            db, InventionDisclosure, InventionDisclosure.technology_area, tenant_id
        ),
        average_triage_days=average_triage,
        pending_evaluations=pending_evaluations,
        assets_total=_count(db, IPAsset, tenant_id),
        assets_by_stage=_grouped(db, IPAsset, IPAsset.status, tenant_id),
        offers_published=_count(
            db, TechnologyOffer, tenant_id, TechnologyOffer.status == "PUBLISHED"
        ),
        negotiations_in_progress=_count(
            db, Negotiation, tenant_id, Negotiation.stage != "CLOSED"
        ),
        contracts_active=contracts_active,
        obligations_due_soon=obligations_due_soon,
        projects_total=_count(db, Project, tenant_id),
        projects_active=_count(db, Project, tenant_id, Project.status == "ACTIVE"),
        startups_total=_count(db, Startup, tenant_id),
        startups_incubated=_count(db, Startup, tenant_id, Startup.status == "INCUBATED"),
        period_from=period_from,
        period_to=now,
    )
