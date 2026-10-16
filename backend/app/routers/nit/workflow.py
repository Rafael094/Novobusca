"""NIT — workflow configuration and inspection (``/api/nit/workflow``).

Exposes the tenant's states/transitions (read-only for viewers; management of
the configuration requires ``NIT_WORKFLOW_MANAGE``). The transition itself lives
under ``/disclosures/{id}/workflow/transition`` because it mutates a disclosure.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_permission
from app.models.nit import WorkflowState, WorkflowTransition
from app.rbac import AccessContext
from app.routers.nit._common import list_scope
from app.schemas.nit import WorkflowStateOut, WorkflowTransitionOut

router = APIRouter(tags=["nit"])


@router.get("/workflow/states", response_model=list[WorkflowStateOut])
def list_states(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_WORKFLOW_VIEW")),
) -> list[WorkflowStateOut]:
    scope = list_scope(ctx)
    conditions = [WorkflowState.active.is_(True)]
    if scope is not None:
        conditions.append(WorkflowState.tenant_id == scope)
    rows = db.execute(
        select(WorkflowState)
        .where(*conditions)
        .order_by(WorkflowState.sort_order)
    ).scalars()
    return [WorkflowStateOut.model_validate(r) for r in rows]


@router.get("/workflow/transitions", response_model=list[WorkflowTransitionOut])
def list_transitions(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_WORKFLOW_VIEW")),
) -> list[WorkflowTransitionOut]:
    scope = list_scope(ctx)
    conditions = [WorkflowTransition.active.is_(True)]
    if scope is not None:
        conditions.append(WorkflowTransition.tenant_id == scope)
    rows = db.execute(
        select(WorkflowTransition)
        .where(*conditions)
        .order_by(WorkflowTransition.sort_order)
    ).scalars()
    return [WorkflowTransitionOut.model_validate(r) for r in rows]
