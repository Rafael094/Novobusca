"""NIT — Comunicação de invenção endpoints (``/api/nit/disclosures``).

Tenant isolation and unity scope are enforced here (never trusted from the
client). The protocol is generated server-side inside the creation transaction;
concurrent duplicates are impossible thanks to ``uq_disclosures_tenant_protocol``
(the router retries once on conflict).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models.nit import (
    WF_PROPOSAL,
    DisclosureInventor,
    Evaluation,
    InventionDisclosure,
    WorkflowHistory,
    WorkflowInstance,
    WorkflowState,
)
from app.rbac import AccessContext
from app.routers.nit._common import (
    assert_same_tenant,
    assert_unity_scope,
    list_scope,
    scoped_tenant,
    write_tenant,
)
from app.schemas.nit import (
    DisclosureCreate,
    DisclosureDetail,
    DisclosureOut,
    DisclosureUpdate,
    EvaluationCreate,
    EvaluationOut,
    InventorOut,
    PaginatedDisclosures,
    TransitionRequest,
    WorkflowHistoryOut,
    WorkflowStatusOut,
    WorkflowTransitionOut,
)
from app.services import protocol as protocol_service
from app.services.workflow import (
    InvalidTransition,
    JustificationRequired,
    TransitionNotAllowed,
    WorkflowClosed,
    WorkflowConflict,
    apply_transition,
    available_transitions,
)

router = APIRouter(prefix="/disclosures", tags=["nit"])

_WORKFLOW_ERRORS = (
    InvalidTransition,
    TransitionNotAllowed,
    JustificationRequired,
    WorkflowClosed,
)


def _get_or_404(
    db: Session, ctx: AccessContext, disclosure_id: uuid.UUID
) -> InventionDisclosure:
    disclosure = db.get(InventionDisclosure, disclosure_id)
    if disclosure is None or disclosure.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comunicação não encontrada"
        )
    assert_same_tenant(ctx, disclosure.tenant_id)
    return disclosure


def _detail(db: Session, disclosure: InventionDisclosure) -> DisclosureDetail:
    detail = DisclosureDetail.model_validate(disclosure)
    detail.inventors = [
        InventorOut.model_validate(i)
        for i in db.execute(
            select(DisclosureInventor).where(
                DisclosureInventor.disclosure_id == disclosure.id
            )
        ).scalars()
    ]
    return detail


@router.get("", response_model=PaginatedDisclosures)
def list_disclosures(
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    technology_area: str | None = None,
    unity_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_DISCLOSURE_VIEW")),
) -> PaginatedDisclosures:
    scope = list_scope(ctx, tenant_id)
    conditions = [InventionDisclosure.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(InventionDisclosure.tenant_id == scope)
    if status_filter:
        conditions.append(InventionDisclosure.status == status_filter)
    if technology_area:
        conditions.append(InventionDisclosure.technology_area == technology_area)
    if unity_id is not None:
        conditions.append(InventionDisclosure.unity_id == unity_id)
    if q:
        like = f"%{q}%"
        conditions.append(
            or_(
                InventionDisclosure.title.ilike(like),
                InventionDisclosure.protocol.ilike(like),
                InventionDisclosure.keywords.ilike(like),
            )
        )

    total = db.execute(
        select(func.count()).select_from(InventionDisclosure).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(InventionDisclosure)
            .where(*conditions)
            .order_by(InventionDisclosure.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedDisclosures(
        items=[DisclosureOut.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total),
    )


@router.post("", response_model=DisclosureDetail, status_code=status.HTTP_201_CREATED)
def create_disclosure(
    payload: DisclosureCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_DISCLOSURE_CREATE")),
    meta: dict = Depends(client_meta),
) -> DisclosureDetail:
    tenant = write_tenant(ctx, None)
    assert_unity_scope(db, ctx, tenant, payload.unity_id)

    disclosure = InventionDisclosure(
        tenant_id=tenant,
        unity_id=payload.unity_id,
        protocol="",  # assigned below, inside the same transaction
        title=payload.title,
        summary=payload.summary,
        description=payload.description,
        context=payload.context,
        technology_area=payload.technology_area,
        keywords=payload.keywords,
        status=WF_PROPOSAL,
        confidentiality_level=payload.confidentiality_level,
        submitted_by_id=ctx.user.id,
        responsible_id=payload.responsible_id,
        active=True,
    )

    # The unique index (tenant_id, protocol) is the final guarantee: a concurrent
    # submission either wins the sequence or is retried once.
    last_error: IntegrityError | None = None
    for _ in range(3):
        disclosure.protocol = protocol_service.next_protocol(db, tenant)
        try:
            with db.begin_nested():
                db.add(disclosure)
                db.flush()
            last_error = None
            break
        except IntegrityError as exc:  # concurrent protocol collision
            last_error = exc
            if disclosure in db:
                db.expunge(disclosure)
    if last_error is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Não foi possível gerar o protocolo. Tente novamente.",
        )

    for inv in payload.inventors:
        db.add(
            DisclosureInventor(
                tenant_id=tenant,
                disclosure_id=disclosure.id,
                name=inv.name,
                kind=inv.kind,
                person_id=inv.person_id,
                user_id=inv.user_id,
                document=inv.document,
                email=inv.email,
                institution=inv.institution,
                share_percent=inv.share_percent,
                is_primary=inv.is_primary,
                notes=inv.notes,
            )
        )

    # Start the workflow instance in the tenant's initial state.
    initial = db.execute(
        select(WorkflowState).where(
            WorkflowState.tenant_id == tenant, WorkflowState.is_initial.is_(True)
        )
    ).scalar_one_or_none()
    db.add(
        WorkflowInstance(
            tenant_id=tenant,
            disclosure_id=disclosure.id,
            current_state=initial.code if initial else WF_PROPOSAL,
            version=0,
        )
    )
    record_audit(
        db,
        action="NIT_DISCLOSURE_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="invention_disclosure",
        resource_id=disclosure.id,
        meta={"protocol": disclosure.protocol},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(disclosure)
    return _detail(db, disclosure)


@router.get("/{disclosure_id}", response_model=DisclosureDetail)
def get_disclosure(
    disclosure_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_DISCLOSURE_VIEW")),
) -> DisclosureDetail:
    return _detail(db, _get_or_404(db, ctx, disclosure_id))


@router.patch("/{disclosure_id}", response_model=DisclosureDetail)
def update_disclosure(
    disclosure_id: uuid.UUID,
    payload: DisclosureUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_DISCLOSURE_EDIT")),
) -> DisclosureDetail:
    disclosure = _get_or_404(db, ctx, disclosure_id)
    data = payload.model_dump(exclude_unset=True)
    if "unity_id" in data:
        assert_unity_scope(db, ctx, disclosure.tenant_id, data["unity_id"])
    for field, value in data.items():
        setattr(disclosure, field, value)
    db.commit()
    db.refresh(disclosure)
    return _detail(db, disclosure)


@router.delete("/{disclosure_id}")
def delete_disclosure(
    disclosure_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_DISCLOSURE_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    disclosure = _get_or_404(db, ctx, disclosure_id)
    # Logical delete preserves the dossier history and audit trail.
    from app.mixins import utcnow

    disclosure.deleted_at = utcnow()
    disclosure.active = False
    record_audit(
        db,
        action="NIT_DISCLOSURE_DELETE",
        tenant_id=disclosure.tenant_id,
        user_id=ctx.user.id,
        resource="invention_disclosure",
        resource_id=disclosure.id,
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    return {"status": "deleted", "id": str(disclosure.id)}


# --- Workflow ---------------------------------------------------------------
@router.get("/{disclosure_id}/workflow", response_model=WorkflowStatusOut)
def get_workflow(
    disclosure_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_WORKFLOW_VIEW")),
) -> WorkflowStatusOut:
    disclosure = _get_or_404(db, ctx, disclosure_id)
    instance = db.execute(
        select(WorkflowInstance).where(WorkflowInstance.disclosure_id == disclosure.id)
    ).scalar_one_or_none()
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow não iniciado"
        )
    state = db.execute(
        select(WorkflowState).where(
            WorkflowState.tenant_id == disclosure.tenant_id,
            WorkflowState.code == instance.current_state,
        )
    ).scalar_one_or_none()
    edges = available_transitions(
        db, tenant_id=disclosure.tenant_id, from_state=instance.current_state
    )
    history = db.execute(
        select(WorkflowHistory)
        .where(WorkflowHistory.instance_id == instance.id)
        .order_by(WorkflowHistory.created_at.desc())
    ).scalars()
    return WorkflowStatusOut(
        disclosure_id=disclosure.id,
        current_state=instance.current_state,
        current_state_name=state.name if state else None,
        version=instance.version,
        is_terminal=bool(state.is_terminal) if state else False,
        available_transitions=[WorkflowTransitionOut.model_validate(e) for e in edges],
        history=[WorkflowHistoryOut.model_validate(h) for h in history],
    )


@router.post("/{disclosure_id}/workflow/transition", response_model=WorkflowStatusOut)
def transition_workflow(
    disclosure_id: uuid.UUID,
    payload: TransitionRequest,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_WORKFLOW_VIEW")),
    meta: dict = Depends(client_meta),
) -> WorkflowStatusOut:
    disclosure = _get_or_404(db, ctx, disclosure_id)
    instance = db.execute(
        select(WorkflowInstance)
        .where(WorkflowInstance.disclosure_id == disclosure.id)
        .with_for_update()
    ).scalar_one_or_none()
    if instance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow não iniciado"
        )
    try:
        result = apply_transition(
            db,
            ctx=ctx,
            instance=instance,
            to_state=payload.to_state,
            justification=payload.justification,
            expected_version=payload.expected_version,
        )
    except WorkflowConflict as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except _WORKFLOW_ERRORS as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # Keep the disclosure's denormalised ``status`` in sync with the workflow.
    disclosure.status = result.to_state
    record_audit(
        db,
        action="NIT_WORKFLOW_TRANSITION",
        tenant_id=disclosure.tenant_id,
        user_id=ctx.user.id,
        resource="invention_disclosure",
        resource_id=disclosure.id,
        meta={"from": result.from_state, "to": result.to_state, "version": result.version},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    return get_workflow(disclosure_id, db=db, ctx=ctx)


# --- Evaluations ------------------------------------------------------------
@router.get("/{disclosure_id}/evaluations", response_model=list[EvaluationOut])
def list_evaluations(
    disclosure_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_EVALUATION_VIEW")),
) -> list[EvaluationOut]:
    disclosure = _get_or_404(db, ctx, disclosure_id)
    rows = db.execute(
        select(Evaluation)
        .where(
            Evaluation.disclosure_id == disclosure.id,
            Evaluation.deleted_at.is_(None),
        )
        .order_by(Evaluation.created_at.desc())
    ).scalars()
    return [EvaluationOut.model_validate(r) for r in rows]


@router.post(
    "/{disclosure_id}/evaluations",
    response_model=EvaluationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_evaluation(
    disclosure_id: uuid.UUID,
    payload: EvaluationCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_EVALUATION_CREATE")),
    meta: dict = Depends(client_meta),
) -> EvaluationOut:
    disclosure = _get_or_404(db, ctx, disclosure_id)
    evaluation = Evaluation(
        tenant_id=disclosure.tenant_id,
        disclosure_id=disclosure.id,
        kind=payload.kind,
        evaluator_id=payload.evaluator_id or ctx.user.id,
        outcome=payload.outcome,
        summary=payload.summary,
        criteria=payload.criteria,
        technological_potential=payload.technological_potential,
        market_potential=payload.market_potential,
        risks=payload.risks,
        recommendations=payload.recommendations,
        trl_level=payload.trl_level,
        confidentiality_level=payload.confidentiality_level,
        active=True,
    )
    db.add(evaluation)
    record_audit(
        db,
        action="NIT_EVALUATION_CREATE",
        tenant_id=disclosure.tenant_id,
        user_id=ctx.user.id,
        resource="evaluation",
        resource_id=evaluation.id,
        meta={"disclosure_id": str(disclosure.id), "kind": payload.kind},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(evaluation)
    return EvaluationOut.model_validate(evaluation)




