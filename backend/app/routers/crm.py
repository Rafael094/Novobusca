"""Tenant-scoped commercial CRM endpoints (``/api/crm``).

Completes the commercial layer on top of the existing CRM entities:

* ``/crm/opportunities``  — leads and opportunities (funnel stages)
* ``/crm/proposals``      — commercial proposals and their lifecycle
* ``/crm/activities``     — follow-ups and interaction history
* ``/crm/dashboard``      — commercial aggregates of the authenticated tenant
* ``/crm/convert``        — lead → customer conversion (anti-duplication)

Isolation is enforced here and never trusted from the client: the tenant always
comes from the authenticated user. A master admin may filter by ``tenant_id``;
every other user is confined to their own tenant.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models import Company, Customer, Person, User
from app.models.crm import (
    ACTIVITY_KINDS,
    ACTIVITY_OUTCOMES,
    ACTIVITY_SUBJECT_TYPES,
    OPPORTUNITY_STAGES,
    PROPOSAL_STATUSES,
    CrmActivity,
    CrmOpportunity,
    CrmProposal,
)
from app.rbac import AccessContext
from app.schemas.crm import (
    ActivityCreate,
    ActivityOut,
    ActivityUpdate,
    BusinessDashboard,
    OpportunityConvert,
    OpportunityCreate,
    OpportunityOut,
    OpportunityStageChange,
    OpportunityUpdate,
    PaginatedActivities,
    PaginatedOpportunities,
    PaginatedProposals,
    ProposalCreate,
    ProposalOut,
    ProposalStatusChange,
    ProposalUpdate,
)
from app.services import crm as crm_service

router = APIRouter(prefix="/crm", tags=["crm"])


# --- Tenant scoping helpers -------------------------------------------------
def _scoped_tenant(ctx: AccessContext, requested: uuid.UUID | None) -> uuid.UUID | None:
    """Tenant to filter by (``None`` = all tenants, master admin only)."""
    if ctx.user.is_master_admin:
        return requested
    if requested is not None and requested != ctx.user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é permitido acessar dados de outro tenant",
        )
    return ctx.user.tenant_id


def _write_tenant(ctx: AccessContext, requested: uuid.UUID | None) -> uuid.UUID:
    """Tenant to assign on create; must be the caller's tenant when not master."""
    if ctx.user.is_master_admin:
        tenant = requested or ctx.user.tenant_id
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="tenant_id é obrigatório para o Master Admin",
            )
        return tenant
    if requested is not None and requested != ctx.user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é permitido criar registros em outro tenant",
        )
    if ctx.user.tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Usuário sem tenant"
        )
    return ctx.user.tenant_id


def _assert_tenant(ctx: AccessContext, tenant_id: uuid.UUID) -> None:
    if ctx.user.is_master_admin:
        return
    if tenant_id != ctx.user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Registro não encontrado"
        )


def _paginate(page: int, page_size: int, total: int) -> dict:
    return {"page": page, "page_size": page_size, "total": int(total)}


# --- Enrichment -------------------------------------------------------------
def _names_for(db: Session, rows) -> tuple[dict, dict, dict, dict]:
    """Batch-resolve the display names used by the list/detail payloads.

    Four small ``IN`` queries instead of per-row lookups — no N+1.
    """
    customer_ids = {r.customer_id for r in rows if getattr(r, "customer_id", None)}
    company_ids = {r.company_id for r in rows if getattr(r, "company_id", None)}
    person_ids = {r.contact_id for r in rows if getattr(r, "contact_id", None)}
    user_ids = {r.owner_id for r in rows if getattr(r, "owner_id", None)}

    customers = (
        {
            c.id: c.name
            for c in db.execute(
                select(Customer).where(Customer.id.in_(customer_ids))
            ).scalars()
        }
        if customer_ids
        else {}
    )
    companies = (
        {
            c.id: c.company_name
            for c in db.execute(select(Company).where(Company.id.in_(company_ids))).scalars()
        }
        if company_ids
        else {}
    )
    people = (
        {
            p.id: p.name
            for p in db.execute(select(Person).where(Person.id.in_(person_ids))).scalars()
        }
        if person_ids
        else {}
    )
    users = (
        {
            p.user_id: p.name
            for p in db.execute(select(Person).where(Person.user_id.in_(user_ids))).scalars()
        }
        if user_ids
        else {}
    )
    return customers, companies, people, users


def _proposal_counts(db: Session, opportunity_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not opportunity_ids:
        return {}
    rows = db.execute(
        select(CrmProposal.opportunity_id, func.count())
        .where(
            CrmProposal.opportunity_id.in_(opportunity_ids),
            CrmProposal.deleted_at.is_(None),
        )
        .group_by(CrmProposal.opportunity_id)
    ).all()
    return {oid: int(count) for oid, count in rows}


def _opportunity_out(
    opportunity: CrmOpportunity,
    customers: dict,
    companies: dict,
    people: dict,
    users: dict,
    proposal_count: int,
) -> OpportunityOut:
    out = OpportunityOut.model_validate(opportunity)
    out.customer_name = customers.get(opportunity.customer_id)
    out.company_name = companies.get(opportunity.company_id)
    out.contact_name = people.get(opportunity.contact_id)
    out.owner_name = users.get(opportunity.owner_id)
    out.proposal_count = proposal_count
    return out


def _proposal_out(proposal: CrmProposal, customers: dict, users: dict, opp_titles: dict) -> ProposalOut:
    out = ProposalOut.model_validate(proposal)
    out.customer_name = customers.get(proposal.customer_id)
    out.owner_name = users.get(proposal.owner_id)
    out.opportunity_title = opp_titles.get(proposal.opportunity_id)
    out.is_overdue = bool(
        proposal.valid_until
        and proposal.valid_until < datetime.now(timezone.utc).date()
        and proposal.status in crm_service.PROPOSAL_OPEN_STATUSES
    )
    return out


# --- Reference validation ---------------------------------------------------
def _validate_references(db: Session, tenant: uuid.UUID, data: dict) -> None:
    """Reject references that do not belong to the tenant (IDOR-safe).

    Return 422 with a specific message so the UI can point at the offending
    field instead of silently storing a cross-tenant link.
    """
    checks = (
        ("customer_id", Customer),
        ("company_id", Company),
        ("contact_id", Person),
    )
    for field, model in checks:
        value = data.get(field)
        if value is None:
            continue
        row = db.get(model, value)
        if row is None or row.deleted_at is not None or row.tenant_id != tenant:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field} inválido para o tenant autenticado.",
            )
    owner_id = data.get("owner_id")
    if owner_id is not None:
        owner = db.get(User, owner_id)
        if owner is None or owner.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="owner_id inválido.",
            )
        if not owner.is_master_admin and owner.tenant_id != tenant:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="owner_id pertence a outro tenant.",
            )


# --- Opportunities ----------------------------------------------------------
@router.get("/opportunities", response_model=PaginatedOpportunities)
def list_opportunities(
    q: str | None = None,
    stage: str | None = None,
    customer_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    active: bool | None = None,
    tenant_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_OPPORTUNITY_VIEW")),
) -> PaginatedOpportunities:
    tenant = _scoped_tenant(ctx, tenant_id)
    conditions = [CrmOpportunity.deleted_at.is_(None)]
    if tenant is not None:
        conditions.append(CrmOpportunity.tenant_id == tenant)
    if q:
        like = f"%{q.lower()}%"
        conditions.append(
            or_(
                func.lower(CrmOpportunity.title).like(like),
                func.lower(CrmOpportunity.lead_name).like(like),
                func.lower(CrmOpportunity.code).like(like),
            )
        )
    if stage:
        conditions.append(CrmOpportunity.stage == stage)
    if customer_id:
        conditions.append(CrmOpportunity.customer_id == customer_id)
    if owner_id:
        conditions.append(CrmOpportunity.owner_id == owner_id)
    if active is not None:
        conditions.append(CrmOpportunity.active.is_(active))

    total = db.execute(
        select(func.count()).select_from(CrmOpportunity).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(CrmOpportunity)
            .where(*conditions)
            .order_by(CrmOpportunity.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    customers, companies, people, users = _names_for(db, rows)
    counts = _proposal_counts(db, [r.id for r in rows])
    return PaginatedOpportunities(
        pagination=_paginate(page, page_size, total),
        items=[
            _opportunity_out(r, customers, companies, people, users, counts.get(r.id, 0))
            for r in rows
        ],
    )


@router.post(
    "/opportunities",
    response_model=OpportunityOut,
    status_code=status.HTTP_201_CREATED,
)
def create_opportunity(
    payload: OpportunityCreate,
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_OPPORTUNITY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> OpportunityOut:
    tenant = _write_tenant(ctx, tenant_id)
    data = payload.model_dump()
    stage = data.pop("stage", "NEW")
    _validate_references(db, tenant, data)
    opportunity = CrmOpportunity(
        tenant_id=tenant,
        code=crm_service.next_opportunity_code(db, tenant),
        stage="NEW",
        **data,
    )
    db.add(opportunity)
    db.flush()
    if stage != "NEW":
        crm_service.apply_opportunity_stage(db, opportunity, new_stage=stage)
    db.commit()
    db.refresh(opportunity)
    record_audit(
        db,
        action="CRM_OPPORTUNITY_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="crm:opportunity",
        resource_id=str(opportunity.id),
        meta={"code": opportunity.code, "stage": opportunity.stage},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    customers, companies, people, users = _names_for(db, [opportunity])
    return _opportunity_out(opportunity, customers, companies, people, users, 0)


def _get_opportunity(db: Session, opportunity_id: uuid.UUID) -> CrmOpportunity:
    opportunity = db.get(CrmOpportunity, opportunity_id)
    if opportunity is None or opportunity.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Oportunidade não encontrada"
        )
    return opportunity


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityOut)
def get_opportunity(
    opportunity_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_OPPORTUNITY_VIEW")),
) -> OpportunityOut:
    opportunity = _get_opportunity(db, opportunity_id)
    _assert_tenant(ctx, opportunity.tenant_id)
    customers, companies, people, users = _names_for(db, [opportunity])
    counts = _proposal_counts(db, [opportunity.id])
    return _opportunity_out(
        opportunity, customers, companies, people, users, counts.get(opportunity.id, 0)
    )


@router.patch("/opportunities/{opportunity_id}", response_model=OpportunityOut)
def update_opportunity(
    opportunity_id: uuid.UUID,
    payload: OpportunityUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_OPPORTUNITY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> OpportunityOut:
    opportunity = _get_opportunity(db, opportunity_id)
    _assert_tenant(ctx, opportunity.tenant_id)
    data = payload.model_dump(exclude_unset=True)
    _validate_references(db, opportunity.tenant_id, data)
    for field, value in data.items():
        setattr(opportunity, field, value)
    db.commit()
    db.refresh(opportunity)
    record_audit(
        db,
        action="CRM_OPPORTUNITY_UPDATE",
        tenant_id=opportunity.tenant_id,
        user_id=ctx.user.id,
        resource="crm:opportunity",
        resource_id=str(opportunity.id),
        meta={"fields": sorted(data.keys())},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    customers, companies, people, users = _names_for(db, [opportunity])
    counts = _proposal_counts(db, [opportunity.id])
    return _opportunity_out(
        opportunity, customers, companies, people, users, counts.get(opportunity.id, 0)
    )


@router.post("/opportunities/{opportunity_id}/stage", response_model=OpportunityOut)
def change_opportunity_stage(
    opportunity_id: uuid.UUID,
    payload: OpportunityStageChange,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_OPPORTUNITY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> OpportunityOut:
    opportunity = _get_opportunity(db, opportunity_id)
    _assert_tenant(ctx, opportunity.tenant_id)
    previous = opportunity.stage
    crm_service.apply_opportunity_stage(
        db,
        opportunity,
        new_stage=payload.stage,
        lost_reason=payload.lost_reason,
        customer_id=payload.customer_id,
    )
    if payload.notes:
        opportunity.notes = (
            f"{opportunity.notes}\n{payload.notes}" if opportunity.notes else payload.notes
        )
    db.commit()
    db.refresh(opportunity)
    record_audit(
        db,
        action="CRM_OPPORTUNITY_STAGE",
        tenant_id=opportunity.tenant_id,
        user_id=ctx.user.id,
        resource="crm:opportunity",
        resource_id=str(opportunity.id),
        meta={"from": previous, "to": opportunity.stage},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    customers, companies, people, users = _names_for(db, [opportunity])
    counts = _proposal_counts(db, [opportunity.id])
    return _opportunity_out(
        opportunity, customers, companies, people, users, counts.get(opportunity.id, 0)
    )


@router.delete("/opportunities/{opportunity_id}")
def delete_opportunity(
    opportunity_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_OPPORTUNITY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    opportunity = _get_opportunity(db, opportunity_id)
    _assert_tenant(ctx, opportunity.tenant_id)
    opportunity.active = False
    opportunity.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(
        db,
        action="CRM_OPPORTUNITY_SOFT_DELETE",
        tenant_id=opportunity.tenant_id,
        user_id=ctx.user.id,
        resource="crm:opportunity",
        resource_id=str(opportunity.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Oportunidade desativada (soft delete)."}


def _opportunity_proposals(db: Session, opportunity_id: uuid.UUID) -> list[CrmProposal]:
    return list(
        db.execute(
            select(CrmProposal).where(
                CrmProposal.opportunity_id == opportunity_id,
                CrmProposal.deleted_at.is_(None),
            )
        )
        .scalars()
        .all()
    )


@router.post("/opportunities/{opportunity_id}/convert", response_model=OpportunityOut)
def convert_opportunity(
    opportunity_id: uuid.UUID,
    payload: OpportunityConvert,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_OPPORTUNITY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> OpportunityOut:
    """Turn a lead into a customer, preserving the whole commercial history.

    Runs inside a single transaction: the customer creation (when needed), the
    opportunity link and the proposal back-fill either all commit or all roll
    back. Approving a proposal is NOT the same as registering a trademark — this
    endpoint only performs the commercial conversion.
    """
    opportunity = _get_opportunity(db, opportunity_id)
    _assert_tenant(ctx, opportunity.tenant_id)

    if payload.customer_id is not None:
        linked = db.get(Customer, payload.customer_id)
        if (
            linked is None
            or linked.deleted_at is not None
            or linked.tenant_id != opportunity.tenant_id
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cliente inválido para o tenant autenticado.",
            )
        opportunity.customer_id = linked.id
        opportunity.stage = "WON"
        opportunity.lost_reason = None
        for proposal in _opportunity_proposals(db, opportunity.id):
            if proposal.customer_id is None:
                proposal.customer_id = linked.id
        customer, created = linked, False
    else:
        customer, created = crm_service.convert_opportunity_to_customer(
            db,
            opportunity,
            tenant_id=opportunity.tenant_id,
            name=payload.name,
            document=payload.document,
            email=payload.email,
            phone=payload.phone,
            force_new=payload.force_new,
        )

    db.commit()
    db.refresh(opportunity)
    record_audit(
        db,
        action="CRM_OPPORTUNITY_CONVERT",
        tenant_id=opportunity.tenant_id,
        user_id=ctx.user.id,
        resource="crm:opportunity",
        resource_id=str(opportunity.id),
        meta={
            "customer_id": str(customer.id),
            "customer_created": created,
            "customer_name": customer.name,
        },
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    customers, companies, people, users = _names_for(db, [opportunity])
    counts = _proposal_counts(db, [opportunity.id])
    return _opportunity_out(
        opportunity, customers, companies, people, users, counts.get(opportunity.id, 0)
    )




# --- Proposals --------------------------------------------------------------
def _get_proposal(db: Session, proposal_id: uuid.UUID) -> CrmProposal:
    proposal = db.get(CrmProposal, proposal_id)
    if proposal is None or proposal.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Proposta não encontrada"
        )
    return proposal


def _proposals_context(db: Session, rows) -> tuple[dict, dict, dict]:
    """Batch-resolve customer names, owner names and opportunity titles."""
    customer_ids = {r.customer_id for r in rows if r.customer_id}
    user_ids = {r.owner_id for r in rows if r.owner_id}
    opp_ids = {r.opportunity_id for r in rows if r.opportunity_id}
    customers = (
        {
            c.id: c.name
            for c in db.execute(select(Customer).where(Customer.id.in_(customer_ids))).scalars()
        }
        if customer_ids
        else {}
    )
    users = (
        {
            p.user_id: p.name
            for p in db.execute(select(Person).where(Person.user_id.in_(user_ids))).scalars()
        }
        if user_ids
        else {}
    )
    opp_titles = (
        {
            o.id: o.title
            for o in db.execute(
                select(CrmOpportunity).where(CrmOpportunity.id.in_(opp_ids))
            ).scalars()
        }
        if opp_ids
        else {}
    )
    return customers, users, opp_titles


@router.get("/proposals", response_model=PaginatedProposals)
def list_proposals(
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    customer_id: uuid.UUID | None = None,
    opportunity_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    overdue_only: bool = False,
    active: bool | None = None,
    tenant_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_PROPOSAL_VIEW")),
) -> PaginatedProposals:
    tenant = _scoped_tenant(ctx, tenant_id)
    conditions = [CrmProposal.deleted_at.is_(None)]
    if tenant is not None:
        conditions.append(CrmProposal.tenant_id == tenant)
    if q:
        like = f"%{q.lower()}%"
        conditions.append(
            or_(
                func.lower(CrmProposal.title).like(like),
                func.lower(CrmProposal.code).like(like),
            )
        )
    if status_filter:
        conditions.append(CrmProposal.status == status_filter)
    if customer_id:
        conditions.append(CrmProposal.customer_id == customer_id)
    if opportunity_id:
        conditions.append(CrmProposal.opportunity_id == opportunity_id)
    if owner_id:
        conditions.append(CrmProposal.owner_id == owner_id)
    if active is not None:
        conditions.append(CrmProposal.active.is_(active))
    if overdue_only:
        conditions.append(CrmProposal.valid_until.is_not(None))
        conditions.append(CrmProposal.valid_until < datetime.now(timezone.utc).date())
        conditions.append(CrmProposal.status.in_(crm_service.PROPOSAL_OPEN_STATUSES))

    total = db.execute(
        select(func.count()).select_from(CrmProposal).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(CrmProposal)
            .where(*conditions)
            .order_by(CrmProposal.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    customers, users, opp_titles = _proposals_context(db, rows)
    return PaginatedProposals(
        pagination=_paginate(page, page_size, total),
        items=[_proposal_out(r, customers, users, opp_titles) for r in rows],
    )



@router.post(
    "/proposals", response_model=ProposalOut, status_code=status.HTTP_201_CREATED
)
def create_proposal(
    payload: ProposalCreate,
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_PROPOSAL_MANAGE")),
    meta: dict = Depends(client_meta),
) -> ProposalOut:
    tenant = _write_tenant(ctx, tenant_id)
    data = payload.model_dump()
    requested_status = data.pop("status", "DRAFT")
    _validate_references(db, tenant, data)
    if data.get("opportunity_id") is not None:
        opportunity = db.get(CrmOpportunity, data["opportunity_id"])
        if opportunity is None or opportunity.tenant_id != tenant:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="opportunity_id inválido para o tenant autenticado.",
            )
    proposal = CrmProposal(
        tenant_id=tenant,
        code=crm_service.next_proposal_code(db, tenant),
        status="DRAFT",
        **data,
    )
    db.add(proposal)
    db.flush()
    if requested_status != "DRAFT":
        crm_service.apply_proposal_status(db, proposal, new_status=requested_status)
    db.commit()
    db.refresh(proposal)
    record_audit(
        db,
        action="CRM_PROPOSAL_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="crm:proposal",
        resource_id=str(proposal.id),
        meta={"code": proposal.code, "status": proposal.status},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    customers, users, opp_titles = _proposals_context(db, [proposal])
    return _proposal_out(proposal, customers, users, opp_titles)


@router.get("/proposals/{proposal_id}", response_model=ProposalOut)
def get_proposal(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_PROPOSAL_VIEW")),
) -> ProposalOut:
    proposal = _get_proposal(db, proposal_id)
    _assert_tenant(ctx, proposal.tenant_id)
    customers, users, opp_titles = _proposals_context(db, [proposal])
    return _proposal_out(proposal, customers, users, opp_titles)


@router.patch("/proposals/{proposal_id}", response_model=ProposalOut)
def update_proposal(
    proposal_id: uuid.UUID,
    payload: ProposalUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_PROPOSAL_MANAGE")),
    meta: dict = Depends(client_meta),
) -> ProposalOut:
    proposal = _get_proposal(db, proposal_id)
    _assert_tenant(ctx, proposal.tenant_id)
    data = payload.model_dump(exclude_unset=True)
    _validate_references(db, proposal.tenant_id, data)
    for field, value in data.items():
        setattr(proposal, field, value)
    db.commit()
    db.refresh(proposal)
    record_audit(
        db,
        action="CRM_PROPOSAL_UPDATE",
        tenant_id=proposal.tenant_id,
        user_id=ctx.user.id,
        resource="crm:proposal",
        resource_id=str(proposal.id),
        meta={"fields": sorted(data.keys())},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    customers, users, opp_titles = _proposals_context(db, [proposal])
    return _proposal_out(proposal, customers, users, opp_titles)


@router.post("/proposals/{proposal_id}/status", response_model=ProposalOut)
def change_proposal_status(
    proposal_id: uuid.UUID,
    payload: ProposalStatusChange,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_PROPOSAL_MANAGE")),
    meta: dict = Depends(client_meta),
) -> ProposalOut:
    proposal = _get_proposal(db, proposal_id)
    _assert_tenant(ctx, proposal.tenant_id)
    previous = proposal.status
    crm_service.apply_proposal_status(
        db,
        proposal,
        new_status=payload.status,
        mark_sent=payload.mark_sent,
        mark_reply=payload.mark_reply,
        decision_notes=payload.decision_notes,
    )
    db.commit()
    db.refresh(proposal)
    record_audit(
        db,
        action="CRM_PROPOSAL_STATUS",
        tenant_id=proposal.tenant_id,
        user_id=ctx.user.id,
        resource="crm:proposal",
        resource_id=str(proposal.id),
        meta={"from": previous, "to": proposal.status},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    customers, users, opp_titles = _proposals_context(db, [proposal])
    return _proposal_out(proposal, customers, users, opp_titles)


@router.delete("/proposals/{proposal_id}")
def delete_proposal(
    proposal_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_PROPOSAL_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    proposal = _get_proposal(db, proposal_id)
    _assert_tenant(ctx, proposal.tenant_id)
    proposal.active = False
    proposal.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(
        db,
        action="CRM_PROPOSAL_SOFT_DELETE",
        tenant_id=proposal.tenant_id,
        user_id=ctx.user.id,
        resource="crm:proposal",
        resource_id=str(proposal.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Proposta desativada (soft delete)."}



# --- Activities -------------------------------------------------------------
@router.get("/activities", response_model=PaginatedActivities)
def list_activities(
    subject_type: str | None = None,
    subject_id: uuid.UUID | None = None,
    kind: str | None = None,
    outcome: str | None = None,
    owner_id: uuid.UUID | None = None,
    pending_only: bool = False,
    tenant_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_ACTIVITY_VIEW")),
) -> PaginatedActivities:
    tenant = _scoped_tenant(ctx, tenant_id)
    conditions = [CrmActivity.deleted_at.is_(None)]
    if tenant is not None:
        conditions.append(CrmActivity.tenant_id == tenant)
    if subject_type:
        conditions.append(CrmActivity.subject_type == subject_type)
    if subject_id:
        conditions.append(CrmActivity.subject_id == subject_id)
    if kind:
        conditions.append(CrmActivity.kind == kind)
    if outcome:
        conditions.append(CrmActivity.outcome == outcome)
    if owner_id:
        conditions.append(CrmActivity.owner_id == owner_id)
    if pending_only:
        conditions.append(CrmActivity.outcome == "PENDING")

    total = db.execute(
        select(func.count()).select_from(CrmActivity).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(CrmActivity)
            .where(*conditions)
            .order_by(CrmActivity.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    owner_ids = {r.owner_id for r in rows if r.owner_id}
    owners = (
        {
            u.id: u.name
            for u in db.execute(select(User).where(User.id.in_(owner_ids))).scalars()
        }
        if owner_ids
        else {}
    )
    items: list[ActivityOut] = []
    for row in rows:
        out = ActivityOut.model_validate(row)
        out.owner_name = owners.get(row.owner_id)
        items.append(out)
    return PaginatedActivities(pagination=_paginate(page, page_size, total), items=items)


def _validate_subject(
    db: Session, tenant: uuid.UUID, subject_type: str, subject_id: uuid.UUID
) -> None:
    """Ensure the polymorphic activity target exists inside the tenant."""
    if subject_type not in ACTIVITY_SUBJECT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"subject_type inválido: {subject_type}",
        )
    model = {
        "OPPORTUNITY": CrmOpportunity,
        "PROPOSAL": CrmProposal,
        "CUSTOMER": Customer,
        "COMPANY": Company,
    }[subject_type]
    row = db.get(model, subject_id)
    if row is None or getattr(row, "deleted_at", None) is not None or row.tenant_id != tenant:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="subject_id inválido para o tenant autenticado.",
        )




@router.post(
    "/activities", response_model=ActivityOut, status_code=status.HTTP_201_CREATED
)
def create_activity(
    payload: ActivityCreate,
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_ACTIVITY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> ActivityOut:
    tenant = _write_tenant(ctx, tenant_id)
    _validate_subject(db, tenant, payload.subject_type, payload.subject_id)
    data = payload.model_dump()
    if data.get("owner_id") is None:
        data["owner_id"] = ctx.user.id
    activity = CrmActivity(tenant_id=tenant, created_by=ctx.user.id, **data)
    db.add(activity)
    db.commit()
    db.refresh(activity)
    record_audit(
        db,
        action="CRM_ACTIVITY_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="crm:activity",
        resource_id=str(activity.id),
        meta={"kind": activity.kind, "subject_type": activity.subject_type},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    out = ActivityOut.model_validate(activity)
    if activity.owner_id:
        owner_person = db.execute(select(Person).where(Person.user_id == activity.owner_id)).scalars().first() if activity.owner_id else None
        out.owner_name = owner_person.name if owner_person else None
    return out


@router.patch("/activities/{activity_id}", response_model=ActivityOut)
def update_activity(
    activity_id: uuid.UUID,
    payload: ActivityUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_ACTIVITY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> ActivityOut:
    activity = db.get(CrmActivity, activity_id)
    if activity is None or activity.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Atividade não encontrada"
        )
    _assert_tenant(ctx, activity.tenant_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(activity, field, value)
    # Completing a follow-up stamps the completion moment.
    if data.get("outcome") in ("DONE", "NO_ANSWER") and activity.completed_at is None:
        activity.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(activity)
    record_audit(
        db,
        action="CRM_ACTIVITY_UPDATE",
        tenant_id=activity.tenant_id,
        user_id=ctx.user.id,
        resource="crm:activity",
        resource_id=str(activity.id),
        meta={"fields": sorted(data.keys())},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    out = ActivityOut.model_validate(activity)
    if activity.owner_id:
        owner_person = db.execute(select(Person).where(Person.user_id == activity.owner_id)).scalars().first() if activity.owner_id else None
        out.owner_name = owner_person.name if owner_person else None
    return out


@router.delete("/activities/{activity_id}")
def delete_activity(
    activity_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_ACTIVITY_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    activity = db.get(CrmActivity, activity_id)
    if activity is None or activity.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Atividade não encontrada"
        )
    _assert_tenant(ctx, activity.tenant_id)
    activity.active = False
    activity.deleted_at = datetime.now(timezone.utc)
    db.commit()
    record_audit(
        db,
        action="CRM_ACTIVITY_SOFT_DELETE",
        tenant_id=activity.tenant_id,
        user_id=ctx.user.id,
        resource="crm:activity",
        resource_id=str(activity.id),
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Atividade desativada (soft delete)."}


# --- Dashboard (commercial aggregates) --------------------------------------
@router.get("/dashboard", response_model=BusinessDashboard)
def crm_dashboard(
    months: int = Query(default=12, ge=1, le=24),
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_DASHBOARD_VIEW")),
) -> BusinessDashboard:
    tenant = _scoped_tenant(ctx, tenant_id)
    payload = crm_service.build_business_dashboard(
        db, tenant_id=tenant, months=months
    )
    return BusinessDashboard.model_validate(payload)
