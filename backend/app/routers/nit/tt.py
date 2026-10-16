"""NIT F3 — technology transfer (``/api/nit/tt``): offers, interests, negotiations.

The public catalog exposes ONLY ``PUBLISHED`` offers belonging to the caller's
tenant. Internal documents/confidential data are never part of an offer payload.
Interest data is never exposed to other partners.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models.nit import IPAsset
from app.models.nit_f3 import (
    INTEREST_STATUS_CONVERTED,
    INTEREST_STATUS_NEW,
    OFFER_STATUS_DRAFT,
    OFFER_STATUS_PUBLISHED,
    ExpressionOfInterest,
    InterestInteraction,
    Negotiation,
    NegotiationHistory,
    TechnologyOffer,
)
from app.rbac import AccessContext
from app.routers.nit._common import (
    assert_same_tenant,
    list_scope,
    scoped_tenant,
    write_tenant,
)
from app.schemas.nit_f3 import (
    InteractionIn,
    InteractionOut,
    InterestCreate,
    InterestOut,
    InterestUpdate,
    NegotiationAdvance,
    NegotiationCreate,
    NegotiationDetail,
    NegotiationHistoryOut,
    NegotiationOut,
    NegotiationUpdate,
    OfferCreate,
    OfferOut,
    OfferUpdate,
    PaginatedInterests,
    PaginatedOffers,
)
from app.services.negotiation import (
    InvalidStage,
    NegotiationClosed,
    NegotiationError,
    advance as advance_negotiation,
    allowed_next,
    STAGE_LABELS,
)

router = APIRouter(prefix="/tt", tags=["nit"])


def _offer_or_404(db: Session, ctx: AccessContext, offer_id: uuid.UUID) -> TechnologyOffer:
    offer = db.get(TechnologyOffer, offer_id)
    if offer is None or offer.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Oferta não encontrada")
    assert_same_tenant(ctx, offer.tenant_id)
    return offer


def _next_offer_code(db: Session, tenant_id: uuid.UUID) -> str:
    total = db.execute(
        select(func.count()).select_from(TechnologyOffer).where(
            TechnologyOffer.tenant_id == tenant_id
        )
    ).scalar_one()
    candidate = int(total) + 1
    for _ in range(10000):
        code = f"OFT-{candidate:04d}"
        exists = db.execute(
            select(TechnologyOffer.id).where(
                TechnologyOffer.tenant_id == tenant_id, TechnologyOffer.code == code
            )
        ).first()
        if exists is None:
            return code
        candidate += 1
    raise HTTPException(  # pragma: no cover
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Não foi possível gerar o código da oferta",
    )


# --- Offers (internal management) -------------------------------------------
@router.get("/offers", response_model=PaginatedOffers)
def list_offers(
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_OFFER_VIEW")),
) -> PaginatedOffers:
    scope = list_scope(ctx)
    conditions = [TechnologyOffer.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(TechnologyOffer.tenant_id == scope)
    if status_filter:
        conditions.append(TechnologyOffer.status == status_filter)
    if q:
        like = f"%{q}%"
        conditions.append(
            or_(
                TechnologyOffer.title.ilike(like),
                TechnologyOffer.code.ilike(like),
            )
        )
    total = db.execute(
        select(func.count()).select_from(TechnologyOffer).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(TechnologyOffer)
            .where(*conditions)
            .order_by(TechnologyOffer.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedOffers(
        items=[OfferOut.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total),
    )


@router.get("/catalog", response_model=PaginatedOffers)
def public_catalog(
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_OFFER_VIEW")),
) -> PaginatedOffers:
    """Catalog of PUBLISHED technologies (only the public fields are returned)."""
    scope = list_scope(ctx)
    conditions = [
        TechnologyOffer.deleted_at.is_(None),
        TechnologyOffer.status == OFFER_STATUS_PUBLISHED,
        TechnologyOffer.active.is_(True),
    ]
    if scope is not None:
        conditions.append(TechnologyOffer.tenant_id == scope)
    if q:
        like = f"%{q}%"
        conditions.append(TechnologyOffer.title.ilike(like))
    total = db.execute(
        select(func.count()).select_from(TechnologyOffer).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(TechnologyOffer)
            .where(*conditions)
            .order_by(TechnologyOffer.title)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedOffers(
        items=[OfferOut.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total),
    )


@router.post("/offers", response_model=OfferOut, status_code=status.HTTP_201_CREATED)
def create_offer(
    payload: OfferCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_OFFER_MANAGE")),
    meta: dict = Depends(client_meta),
) -> OfferOut:
    tenant = write_tenant(ctx, None)
    if payload.asset_id is not None:
        asset = db.get(IPAsset, payload.asset_id)
        if asset is None or asset.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ativo inválido"
            )
        assert_same_tenant(ctx, asset.tenant_id)

    offer = TechnologyOffer(
        tenant_id=tenant,
        code=_next_offer_code(db, tenant),
        title=payload.title,
        public_summary=payload.public_summary,
        technology_area=payload.technology_area,
        maturity=payload.maturity,
        modality=payload.modality,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        conditions=payload.conditions,
        asset_id=payload.asset_id,
        unity_id=payload.unity_id,
        status=OFFER_STATUS_DRAFT,
        responsible_id=ctx.user.id,
        active=True,
    )
    db.add(offer)
    record_audit(
        db,
        action="NIT_OFFER_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="technology_offer",
        resource_id=offer.id,
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(offer)
    return OfferOut.model_validate(offer)


@router.get("/offers/{offer_id}", response_model=OfferOut)
def get_offer(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_OFFER_VIEW")),
) -> OfferOut:
    return OfferOut.model_validate(_offer_or_404(db, ctx, offer_id))


@router.patch("/offers/{offer_id}", response_model=OfferOut)
def update_offer(
    offer_id: uuid.UUID,
    payload: OfferUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_OFFER_MANAGE")),
) -> OfferOut:
    offer = _offer_or_404(db, ctx, offer_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(offer, field, value)
    db.commit()
    db.refresh(offer)
    return OfferOut.model_validate(offer)


# --- Expressions of interest -------------------------------------------------
@router.get("/interests", response_model=PaginatedInterests)
def list_interests(
    offer_id: uuid.UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_INTEREST_VIEW")),
) -> PaginatedInterests:
    scope = list_scope(ctx)
    conditions = [ExpressionOfInterest.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(ExpressionOfInterest.tenant_id == scope)
    if offer_id is not None:
        conditions.append(ExpressionOfInterest.offer_id == offer_id)
    if status_filter:
        conditions.append(ExpressionOfInterest.status == status_filter)
    total = db.execute(
        select(func.count()).select_from(ExpressionOfInterest).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(ExpressionOfInterest)
            .where(*conditions)
            .order_by(ExpressionOfInterest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedInterests(
        items=[InterestOut.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total),
    )


@router.post(
    "/offers/{offer_id}/interests",
    response_model=InterestOut,
    status_code=status.HTTP_201_CREATED,
)
def register_interest(
    offer_id: uuid.UUID,
    payload: InterestCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_INTEREST_CREATE")),
    meta: dict = Depends(client_meta),
) -> InterestOut:
    offer = _offer_or_404(db, ctx, offer_id)
    # Only PUBLISHED offers accept expressions of interest.
    if offer.status != OFFER_STATUS_PUBLISHED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A oferta não está publicada para manifestações de interesse.",
        )
    interest = ExpressionOfInterest(
        tenant_id=offer.tenant_id,
        offer_id=offer.id,
        organization_name=payload.organization_name,
        organization_document=payload.organization_document,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        message=payload.message,
        status=INTEREST_STATUS_NEW,
        owner_id=ctx.user.id,
        active=True,
    )
    db.add(interest)
    record_audit(
        db,
        action="NIT_INTEREST_CREATE",
        tenant_id=offer.tenant_id,
        user_id=ctx.user.id,
        resource="expression_of_interest",
        resource_id=interest.id,
        meta={"offer_id": str(offer.id)},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(interest)
    return InterestOut.model_validate(interest)


def _interest_or_404(
    db: Session, ctx: AccessContext, interest_id: uuid.UUID
) -> ExpressionOfInterest:
    interest = db.get(ExpressionOfInterest, interest_id)
    if interest is None or interest.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Manifestação não encontrada"
        )
    assert_same_tenant(ctx, interest.tenant_id)
    return interest


@router.patch("/interests/{interest_id}", response_model=InterestOut)
def update_interest(
    interest_id: uuid.UUID,
    payload: InterestUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_INTEREST_MANAGE")),
) -> InterestOut:
    interest = _interest_or_404(db, ctx, interest_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(interest, field, value)
    db.commit()
    db.refresh(interest)
    return InterestOut.model_validate(interest)


@router.post(
    "/interests/{interest_id}/interactions",
    response_model=InteractionOut,
    status_code=status.HTTP_201_CREATED,
)
def add_interaction(
    interest_id: uuid.UUID,
    payload: InteractionIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_INTEREST_MANAGE")),
) -> InteractionOut:
    interest = _interest_or_404(db, ctx, interest_id)
    row = InterestInteraction(
        tenant_id=interest.tenant_id,
        interest_id=interest.id,
        kind=payload.kind,
        summary=payload.summary,
        actor_id=ctx.user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return InteractionOut.model_validate(row)


@router.get(
    "/interests/{interest_id}/interactions", response_model=list[InteractionOut]
)
def list_interactions(
    interest_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_INTEREST_VIEW")),
) -> list[InteractionOut]:
    interest = _interest_or_404(db, ctx, interest_id)
    rows = db.execute(
        select(InterestInteraction)
        .where(InterestInteraction.interest_id == interest.id)
        .order_by(InterestInteraction.created_at.desc())
    ).scalars()
    return [InteractionOut.model_validate(r) for r in rows]


# --- Negotiations ------------------------------------------------------------
def _negotiation_or_404(
    db: Session, ctx: AccessContext, negotiation_id: uuid.UUID
) -> Negotiation:
    neg = db.get(Negotiation, negotiation_id)
    if neg is None or neg.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Negociação não encontrada"
        )
    assert_same_tenant(ctx, neg.tenant_id)
    return neg


def _neg_detail(db: Session, neg: Negotiation) -> NegotiationDetail:
    detail = NegotiationDetail.model_validate(neg)
    detail.stage_label = STAGE_LABELS.get(neg.stage)
    detail.allowed_next = list(allowed_next(neg.stage))
    detail.history = [
        NegotiationHistoryOut.model_validate(h)
        for h in db.execute(
            select(NegotiationHistory)
            .where(NegotiationHistory.negotiation_id == neg.id)
            .order_by(NegotiationHistory.created_at.desc())
        ).scalars()
    ]
    return detail


@router.get("/negotiations", response_model=list[NegotiationOut])
def list_negotiations(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_NEGOTIATION_VIEW")),
) -> list[NegotiationOut]:
    scope = list_scope(ctx)
    conditions = [Negotiation.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(Negotiation.tenant_id == scope)
    rows = db.execute(
        select(Negotiation).where(*conditions).order_by(Negotiation.created_at.desc())
    ).scalars()
    out: list[NegotiationOut] = []
    for r in rows:
        item = NegotiationOut.model_validate(r)
        item.stage_label = STAGE_LABELS.get(r.stage)
        out.append(item)
    return out


@router.post(
    "/negotiations", response_model=NegotiationDetail, status_code=status.HTTP_201_CREATED
)
def create_negotiation(
    payload: NegotiationCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_NEGOTIATION_MANAGE")),
) -> NegotiationDetail:
    tenant = write_tenant(ctx, None)
    interest = None
    if payload.interest_id is not None:
        interest = _interest_or_404(db, ctx, payload.interest_id)
        interest.status = "IN_NEGOTIATION"
    offer_id = payload.offer_id or (interest.offer_id if interest else None)

    neg = Negotiation(
        tenant_id=tenant,
        interest_id=payload.interest_id,
        offer_id=offer_id,
        stage="NEW",
        owner_id=payload.owner_id or ctx.user.id,
        next_step=payload.next_step,
        notes=payload.notes,
        version=0,
        active=True,
    )
    db.add(neg)
    db.flush()
    db.add(
        NegotiationHistory(
            tenant_id=tenant,
            negotiation_id=neg.id,
            from_stage=None,
            to_stage="NEW",
            actor_id=ctx.user.id,
            justification="Negociação criada",
        )
    )
    db.commit()
    db.refresh(neg)
    return _neg_detail(db, neg)


@router.get("/negotiations/{negotiation_id}", response_model=NegotiationDetail)
def get_negotiation(
    negotiation_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_NEGOTIATION_VIEW")),
) -> NegotiationDetail:
    return _neg_detail(db, _negotiation_or_404(db, ctx, negotiation_id))


@router.patch("/negotiations/{negotiation_id}", response_model=NegotiationOut)
def update_negotiation(
    negotiation_id: uuid.UUID,
    payload: NegotiationUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_NEGOTIATION_MANAGE")),
) -> NegotiationOut:
    neg = _negotiation_or_404(db, ctx, negotiation_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(neg, field, value)
    db.commit()
    db.refresh(neg)
    out = NegotiationOut.model_validate(neg)
    out.stage_label = STAGE_LABELS.get(neg.stage)
    return out


@router.post(
    "/negotiations/{negotiation_id}/advance", response_model=NegotiationDetail
)
def advance_negotiation_route(
    negotiation_id: uuid.UUID,
    payload: NegotiationAdvance,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_NEGOTIATION_MANAGE")),
    meta: dict = Depends(client_meta),
) -> NegotiationDetail:
    neg = _negotiation_or_404(db, ctx, negotiation_id)
    try:
        advance_negotiation(
            db,
            negotiation=neg,
            to_stage=payload.to_stage,
            actor_id=ctx.user.id,
            justification=payload.justification,
            expected_version=payload.expected_version,
        )
    except NegotiationClosed as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except InvalidStage as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except NegotiationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    # Advancing the pipeline NEVER changes a contract's status; reaching
    # CONTRACTING only marks the linked interest as converted.
    if payload.to_stage == "CONTRACTING" and neg.interest_id is not None:
        interest = db.get(ExpressionOfInterest, neg.interest_id)
        if interest is not None:
            interest.status = INTEREST_STATUS_CONVERTED

    record_audit(
        db,
        action="NIT_NEGOTIATION_ADVANCE",
        tenant_id=neg.tenant_id,
        user_id=ctx.user.id,
        resource="negotiation",
        resource_id=neg.id,
        meta={"stage": payload.to_stage},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    return _neg_detail(db, neg)




