"""NIT F5 — integration registry and outbox (``/api/nit/integrations``).

Endpoints are declarative: registering one performs nothing. Events are queued as
``IntegrationDelivery`` rows that remain ``PENDING`` until a real adapter marks
them sent. This module never claims a delivery it did not perform.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_permission
from app.models.nit_f5 import IntegrationDelivery, IntegrationEndpoint
from app.rbac import AccessContext
from app.routers.nit._common import (
    assert_same_tenant,
    list_scope,
    scoped_tenant,
    write_tenant,
)
from app.schemas.nit_f5 import (
    IntegrationDeliveryCreate,
    IntegrationDeliveryOut,
    IntegrationEndpointCreate,
    IntegrationEndpointOut,
)
from app.services.notifications import queue_integration_event

router = APIRouter(prefix="/integrations", tags=["nit"])


@router.get("/endpoints", response_model=list[IntegrationEndpointOut])
def list_endpoints(
    kind: str | None = Query(default=None, pattern="^(SIGA|SEI|EMAIL|WEBHOOK)$"),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_INTEGRATION_VIEW")),
) -> list[IntegrationEndpointOut]:
    scope = list_scope(ctx)
    conditions = [IntegrationEndpoint.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(IntegrationEndpoint.tenant_id == scope)
    if kind:
        conditions.append(IntegrationEndpoint.kind == kind)
    rows = db.execute(
        select(IntegrationEndpoint)
        .where(*conditions)
        .order_by(IntegrationEndpoint.created_at.desc())
    ).scalars()
    return [IntegrationEndpointOut.model_validate(r) for r in rows]


@router.post(
    "/endpoints",
    response_model=IntegrationEndpointOut,
    status_code=status.HTTP_201_CREATED,
)
def create_endpoint(
    payload: IntegrationEndpointCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_INTEGRATION_MANAGE")),
) -> IntegrationEndpointOut:
    tenant = write_tenant(ctx, None)
    existing = db.execute(
        select(IntegrationEndpoint).where(
            IntegrationEndpoint.tenant_id == tenant,
            IntegrationEndpoint.name == payload.name,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe uma integração com este nome",
        )
    endpoint = IntegrationEndpoint(tenant_id=tenant, **payload.model_dump())
    db.add(endpoint)
    db.commit()
    db.refresh(endpoint)
    return IntegrationEndpointOut.model_validate(endpoint)


@router.post(
    "/endpoints/{endpoint_id}/deliveries",
    response_model=IntegrationDeliveryOut,
    status_code=status.HTTP_201_CREATED,
)
def queue_delivery(
    endpoint_id: uuid.UUID,
    payload: IntegrationDeliveryCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_INTEGRATION_MANAGE")),
) -> IntegrationDeliveryOut:
    endpoint = db.get(IntegrationEndpoint, endpoint_id)
    if endpoint is None or endpoint.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Integração não encontrada"
        )
    assert_same_tenant(ctx, endpoint.tenant_id)
    delivery = IntegrationDelivery(
        tenant_id=endpoint.tenant_id,
        endpoint_id=endpoint.id,
        event=payload.event,
        payload=payload.payload,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return IntegrationDeliveryOut.model_validate(delivery)


@router.get("/deliveries", response_model=list[IntegrationDeliveryOut])
def list_deliveries(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_INTEGRATION_VIEW")),
) -> list[IntegrationDeliveryOut]:
    scope = list_scope(ctx)
    conditions = []
    if scope is not None:
        conditions.append(IntegrationDelivery.tenant_id == scope)
    if status_filter:
        conditions.append(IntegrationDelivery.status == status_filter)
    rows = db.execute(
        select(IntegrationDelivery)
        .where(*conditions)
        .order_by(IntegrationDelivery.created_at.desc())
        .limit(200)
    ).scalars()
    return [IntegrationDeliveryOut.model_validate(r) for r in rows]


@router.post("/broadcast", response_model=list[IntegrationDeliveryOut])
def broadcast_event(
    payload: IntegrationDeliveryCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_INTEGRATION_MANAGE")),
) -> list[IntegrationDeliveryOut]:
    """Queue an event to every enabled endpoint of the tenant (outbox pattern)."""
    deliveries = queue_integration_event(
        db,
        tenant_id=ctx.user.tenant_id,
        event=payload.event,
        payload=payload.payload,
    )
    db.commit()
    return [IntegrationDeliveryOut.model_validate(d) for d in deliveries]
