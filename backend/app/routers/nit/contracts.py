"""NIT F3 — contracts, licenses, obligations and royalties (``/api/nit/contracts``).

Rules:

* Monetary fields are ``Decimal`` end-to-end (no float). Registered vs received
  values are kept in distinct fields; the API never sums them into one.
* A contract's ``status`` changes only through an explicit contract operation —
  never through the negotiation pipeline.
* Contractual documents are handled by the F1 confidential-document module.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models.nit import IPAsset
from app.models.nit_f3 import (
    Contract,
    ContractObligation,
    ContractParty,
    License,
    Negotiation,
    Royalty,
)
from app.rbac import AccessContext
from app.routers.nit._common import (
    assert_same_tenant,
    list_scope,
    scoped_tenant,
    write_tenant,
)
from app.schemas.nit_f3 import (
    ContractCreate,
    ContractDetail,
    ContractOut,
    ContractUpdate,
    LicenseCreate,
    LicenseOut,
    ObligationAlert,
    ObligationCreate,
    ObligationOut,
    ObligationUpdate,
    PaginatedContracts,
    PartyIn,
    PartyOut,
    RoyaltyCreate,
    RoyaltyOut,
    RoyaltySummary,
    RoyaltyUpdate,
)

router = APIRouter(prefix="/contracts", tags=["nit"])

OBLIGATION_ALERT_DAYS = 60


def _next_code(db: Session, model, tenant_id: uuid.UUID, prefix: str) -> str:
    total = db.execute(
        select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
    ).scalar_one()
    candidate = int(total) + 1
    for _ in range(10000):
        code = f"{prefix}-{candidate:04d}"
        exists = db.execute(
            select(model.id).where(model.tenant_id == tenant_id, model.code == code)
        ).first()
        if exists is None:
            return code
        candidate += 1
    raise HTTPException(  # pragma: no cover
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Não foi possível gerar o código sequencial",
    )


def _contract_or_404(db: Session, ctx: AccessContext, contract_id: uuid.UUID) -> Contract:
    contract = db.get(Contract, contract_id)
    if contract is None or contract.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contrato não encontrado")
    assert_same_tenant(ctx, contract.tenant_id)
    return contract


# --- Licenses ---------------------------------------------------------------
@router.get("/licenses", response_model=list[LicenseOut])
def list_licenses(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_CONTRACT_VIEW")),
) -> list[LicenseOut]:
    scope = list_scope(ctx)
    conditions = [License.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(License.tenant_id == scope)
    rows = db.execute(
        select(License).where(*conditions).order_by(License.created_at.desc())
    ).scalars()
    return [LicenseOut.model_validate(r) for r in rows]


@router.post("/licenses", response_model=LicenseOut, status_code=status.HTTP_201_CREATED)
def create_license(
    payload: LicenseCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_CONTRACT_MANAGE")),
) -> LicenseOut:
    tenant = write_tenant(ctx, None)
    if payload.asset_id is not None:
        asset = db.get(IPAsset, payload.asset_id)
        if asset is None or asset.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ativo inválido"
            )
        assert_same_tenant(ctx, asset.tenant_id)
    if payload.negotiation_id is not None:
        neg = db.get(Negotiation, payload.negotiation_id)
        if neg is None or neg.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Negociação inválida",
            )
        assert_same_tenant(ctx, neg.tenant_id)

    lic = License(
        tenant_id=tenant,
        code=_next_code(db, License, tenant, "LIC"),
        license_type=payload.license_type,
        asset_id=payload.asset_id,
        negotiation_id=payload.negotiation_id,
        title=payload.title,
        exclusive=payload.exclusive,
        start_date=payload.start_date,
        end_date=payload.end_date,
        notes=payload.notes,
        active=True,
    )
    db.add(lic)
    db.commit()
    db.refresh(lic)
    return LicenseOut.model_validate(lic)


# --- Contracts --------------------------------------------------------------
@router.get("", response_model=PaginatedContracts)
def list_contracts(
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_CONTRACT_VIEW")),
) -> PaginatedContracts:
    scope = list_scope(ctx)
    conditions = [Contract.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(Contract.tenant_id == scope)
    if status_filter:
        conditions.append(Contract.status == status_filter)
    if q:
        like = f"%{q}%"
        conditions.append(or_(Contract.title.ilike(like), Contract.code.ilike(like)))
    total = db.execute(
        select(func.count()).select_from(Contract).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(Contract)
            .where(*conditions)
            .order_by(Contract.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedContracts(
        items=[ContractOut.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total),
    )


@router.post("", response_model=ContractDetail, status_code=status.HTTP_201_CREATED)
def create_contract(
    payload: ContractCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_CONTRACT_MANAGE")),
    meta: dict = Depends(client_meta),
) -> ContractDetail:
    tenant = write_tenant(ctx, None)
    if payload.license_id is not None:
        lic = db.get(License, payload.license_id)
        if lic is None or lic.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Licença inválida"
            )
        assert_same_tenant(ctx, lic.tenant_id)
    if payload.parent_contract_id is not None:
        parent = db.get(Contract, payload.parent_contract_id)
        if parent is None or parent.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Contrato original inválido",
            )
        assert_same_tenant(ctx, parent.tenant_id)

    contract = Contract(
        tenant_id=tenant,
        code=_next_code(db, Contract, tenant, "CT"),
        title=payload.title,
        license_id=payload.license_id,
        parent_contract_id=payload.parent_contract_id,
        is_amendment=payload.is_amendment,
        signed_at=payload.signed_at,
        effective_from=payload.effective_from,
        effective_until=payload.effective_until,
        registered_amount=payload.registered_amount,
        currency=payload.currency,
        conditions=payload.conditions,
        notes=payload.notes,
        responsible_id=payload.responsible_id or ctx.user.id,
        active=True,
    )
    db.add(contract)
    db.flush()
    for party in payload.parties:
        db.add(ContractParty(tenant_id=tenant, contract_id=contract.id, **party.model_dump()))
    record_audit(
        db,
        action="NIT_CONTRACT_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="contract",
        resource_id=contract.id,
        meta={"code": contract.code},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(contract)
    return _contract_detail(db, contract)


def _contract_detail(db: Session, contract: Contract) -> ContractDetail:
    detail = ContractDetail.model_validate(contract)
    detail.parties = [
        PartyOut.model_validate(p)
        for p in db.execute(
            select(ContractParty).where(ContractParty.contract_id == contract.id)
        ).scalars()
    ]
    return detail


@router.get("/{contract_id}", response_model=ContractDetail)
def get_contract(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_CONTRACT_VIEW")),
) -> ContractDetail:
    return _contract_detail(db, _contract_or_404(db, ctx, contract_id))


@router.patch("/{contract_id}", response_model=ContractOut)
def update_contract(
    contract_id: uuid.UUID,
    payload: ContractUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_CONTRACT_MANAGE")),
    meta: dict = Depends(client_meta),
) -> ContractOut:
    contract = _contract_or_404(db, ctx, contract_id)
    data = payload.model_dump(exclude_unset=True)
    status_changed = "status" in data and data["status"] != contract.status
    for field, value in data.items():
        setattr(contract, field, value)
    if status_changed:
        record_audit(
            db,
            action="NIT_CONTRACT_STATUS_CHANGE",
            tenant_id=contract.tenant_id,
            user_id=ctx.user.id,
            resource="contract",
            resource_id=contract.id,
            meta={"status": contract.status},
            ip=meta.get("ip"),
            user_agent=meta.get("user_agent"),
            commit=False,
        )
    db.commit()
    db.refresh(contract)
    return ContractOut.model_validate(contract)


@router.post(
    "/{contract_id}/parties", response_model=PartyOut, status_code=status.HTTP_201_CREATED
)
def add_party(
    contract_id: uuid.UUID,
    payload: PartyIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_CONTRACT_MANAGE")),
) -> PartyOut:
    contract = _contract_or_404(db, ctx, contract_id)
    party = ContractParty(
        tenant_id=contract.tenant_id, contract_id=contract.id, **payload.model_dump()
    )
    db.add(party)
    db.commit()
    db.refresh(party)
    return PartyOut.model_validate(party)


# --- Obligations ------------------------------------------------------------
@router.get("/{contract_id}/obligations", response_model=list[ObligationOut])
def list_obligations(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_OBLIGATION_VIEW")),
) -> list[ObligationOut]:
    contract = _contract_or_404(db, ctx, contract_id)
    rows = db.execute(
        select(ContractObligation)
        .where(ContractObligation.contract_id == contract.id)
        .order_by(ContractObligation.due_date.asc().nulls_last())
    ).scalars()
    return [ObligationOut.model_validate(r) for r in rows]


@router.post(
    "/{contract_id}/obligations",
    response_model=ObligationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_obligation(
    contract_id: uuid.UUID,
    payload: ObligationCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_OBLIGATION_MANAGE")),
) -> ObligationOut:
    contract = _contract_or_404(db, ctx, contract_id)
    row = ContractObligation(
        tenant_id=contract.tenant_id,
        contract_id=contract.id,
        kind=payload.kind,
        description=payload.description,
        due_date=payload.due_date,
        responsible_id=payload.responsible_id or ctx.user.id,
        status="PENDING",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ObligationOut.model_validate(row)


@router.patch("/obligations/{obligation_id}", response_model=ObligationOut)
def update_obligation(
    obligation_id: uuid.UUID,
    payload: ObligationUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_OBLIGATION_MANAGE")),
) -> ObligationOut:
    row = db.get(ContractObligation, obligation_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Obrigação não encontrada"
        )
    assert_same_tenant(ctx, row.tenant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return ObligationOut.model_validate(row)


@router.get("/obligations/alerts", response_model=list[ObligationAlert])
def obligation_alerts(
    days: int = Query(default=OBLIGATION_ALERT_DAYS, ge=1, le=3650),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_OBLIGATION_VIEW")),
) -> list[ObligationAlert]:
    """Pending obligations due within ``days`` (or overdue). Only real due dates."""
    scope = list_scope(ctx)
    conditions = [
        ContractObligation.status == "PENDING",
        ContractObligation.due_date.is_not(None),
    ]
    if scope is not None:
        conditions.append(ContractObligation.tenant_id == scope)
    today = datetime.now(timezone.utc).date()
    rows = db.execute(
        select(ContractObligation).where(*conditions)
    ).scalars()
    alerts: list[ObligationAlert] = []
    for o in rows:
        d = (o.due_date - today).days
        if d > days:
            continue
        severity = "overdue" if d < 0 else ("critical" if d <= 15 else "warning")
        contract = db.get(Contract, o.contract_id)
        alerts.append(
            ObligationAlert(
                obligation_id=o.id,
                contract_id=o.contract_id,
                contract_code=contract.code if contract else "",
                description=o.description,
                due_date=o.due_date,
                days_to_due=d,
                severity=severity,
                status=o.status,
            )
        )
    alerts.sort(key=lambda x: x.days_to_due)
    return alerts


# --- Royalties --------------------------------------------------------------
@router.get("/{contract_id}/royalties", response_model=list[RoyaltyOut])
def list_royalties(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_ROYALTY_VIEW")),
) -> list[RoyaltyOut]:
    contract = _contract_or_404(db, ctx, contract_id)
    rows = db.execute(
        select(Royalty)
        .where(Royalty.contract_id == contract.id)
        .order_by(Royalty.period.desc())
    ).scalars()
    return [RoyaltyOut.model_validate(r) for r in rows]


@router.post(
    "/{contract_id}/royalties",
    response_model=RoyaltyOut,
    status_code=status.HTTP_201_CREATED,
)
def create_royalty(
    contract_id: uuid.UUID,
    payload: RoyaltyCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_ROYALTY_MANAGE")),
) -> RoyaltyOut:
    contract = _contract_or_404(db, ctx, contract_id)
    row = Royalty(
        tenant_id=contract.tenant_id,
        contract_id=contract.id,
        period=payload.period,
        expected_amount=payload.expected_amount,
        registered_amount=payload.registered_amount,
        received_amount=payload.received_amount,
        currency=payload.currency,
        due_date=payload.due_date,
        received_at=payload.received_at,
        notes=payload.notes,
        created_by_id=ctx.user.id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return RoyaltyOut.model_validate(row)


@router.patch("/royalties/{royalty_id}", response_model=RoyaltyOut)
def update_royalty(
    royalty_id: uuid.UUID,
    payload: RoyaltyUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_ROYALTY_MANAGE")),
) -> RoyaltyOut:
    row = db.get(Royalty, royalty_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Royalty não encontrado"
        )
    assert_same_tenant(ctx, row.tenant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return RoyaltyOut.model_validate(row)


@router.get("/{contract_id}/royalties/summary", response_model=RoyaltySummary)
def royalty_summary(
    contract_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_ROYALTY_VIEW")),
) -> RoyaltySummary:
    """Monetary totals using Decimal arithmetic (never floating point)."""
    contract = _contract_or_404(db, ctx, contract_id)
    rows = db.execute(
        select(Royalty).where(Royalty.contract_id == contract.id)
    ).scalars()
    total_expected = Decimal("0")
    total_registered = Decimal("0")
    total_received = Decimal("0")
    entries = 0
    for r in rows:
        entries += 1
        total_expected += r.expected_amount or Decimal("0")
        total_registered += r.registered_amount or Decimal("0")
        total_received += r.received_amount or Decimal("0")
    return RoyaltySummary(
        contract_id=contract.id,
        total_expected=total_expected,
        total_registered=total_registered,
        total_received=total_received,
        pending=total_registered - total_received,
        entries=entries,
    )




