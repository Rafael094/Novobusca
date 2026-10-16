"""NIT — institutional IP asset endpoints (``/api/nit/assets``).

The asset is tenant-owned and editable; the public INPI link is referential (no
hard FK). The asset ``code`` is generated server-side per tenant.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models.nit import (
    PUBLIC_LINK_SOURCES,
    IPAsset,
    IPAssetPublicLink,
    InventionDisclosure,
)
from app.rbac import AccessContext
from app.routers.nit._common import (
    assert_same_tenant,
    assert_unity_scope,
    scoped_tenant,
    write_tenant,
)
from app.schemas.nit import (
    AssetCreate,
    AssetDetail,
    AssetOut,
    AssetUpdate,
    PaginatedAssets,
    PublicLinkIn,
    PublicLinkOut,
)

router = APIRouter(prefix="/assets", tags=["nit"])


def _next_code(db: Session, tenant_id: uuid.UUID) -> str:
    """Sequential per-tenant asset code ``ATV-{SEQ:5d}`` (unique per tenant)."""
    total = db.execute(
        select(func.count()).select_from(IPAsset).where(IPAsset.tenant_id == tenant_id)
    ).scalar_one()
    # Count-based codes can collide after deletions; the unique index catches it and
    # the loop advances until a free code is found.
    candidate = int(total) + 1
    for _ in range(10000):
        code = f"ATV-{candidate:05d}"
        exists = db.execute(
            select(IPAsset.id).where(
                IPAsset.tenant_id == tenant_id, IPAsset.code == code
            )
        ).first()
        if exists is None:
            return code
        candidate += 1
    raise HTTPException(  # pragma: no cover - defensive
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Não foi possível gerar o código do ativo",
    )


def _get_or_404(db: Session, ctx: AccessContext, asset_id: uuid.UUID) -> IPAsset:
    asset = db.get(IPAsset, asset_id)
    if asset is None or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Ativo não encontrado"
        )
    assert_same_tenant(ctx, asset.tenant_id)
    return asset


def _detail(db: Session, asset: IPAsset) -> AssetDetail:
    detail = AssetDetail.model_validate(asset)
    detail.public_links = [
        PublicLinkOut.model_validate(link)
        for link in db.execute(
            select(IPAssetPublicLink).where(IPAssetPublicLink.asset_id == asset.id)
        ).scalars()
    ]
    return detail


@router.get("", response_model=PaginatedAssets)
def list_assets(
    q: str | None = None,
    asset_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    technology_area: str | None = None,
    unity_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_ASSET_VIEW")),
) -> PaginatedAssets:
    scope = scoped_tenant(ctx, tenant_id, allow_all=True)
    conditions = [IPAsset.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(IPAsset.tenant_id == scope)
    if asset_type:
        conditions.append(IPAsset.asset_type == asset_type)
    if status_filter:
        conditions.append(IPAsset.status == status_filter)
    if technology_area:
        conditions.append(IPAsset.technology_area == technology_area)
    if unity_id is not None:
        conditions.append(IPAsset.unity_id == unity_id)
    if q:
        like = f"%{q}%"
        conditions.append(
            or_(IPAsset.title.ilike(like), IPAsset.code.ilike(like))
        )
    total = db.execute(
        select(func.count()).select_from(IPAsset).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(IPAsset)
            .where(*conditions)
            .order_by(IPAsset.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedAssets(
        items=[AssetOut.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total),
    )


@router.post("", response_model=AssetDetail, status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: AssetCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_ASSET_CREATE")),
    meta: dict = Depends(client_meta),
) -> AssetDetail:
    tenant = write_tenant(ctx, None)
    assert_unity_scope(db, ctx, tenant, payload.unity_id)

    # An optional origin disclosure must belong to the SAME tenant.
    if payload.disclosure_id is not None:
        parent = db.get(InventionDisclosure, payload.disclosure_id)
        if parent is None or parent.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Comunicação de origem inválida",
            )
        assert_same_tenant(ctx, parent.tenant_id)

    for link in payload.public_links:
        if link.source not in PUBLIC_LINK_SOURCES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Fonte de vínculo público inválida",
            )

    asset = IPAsset(
        tenant_id=tenant,
        unity_id=payload.unity_id,
        disclosure_id=payload.disclosure_id,
        code=_next_code(db, tenant),
        title=payload.title,
        description=payload.description,
        asset_type=payload.asset_type,
        status=payload.status,
        technology_area=payload.technology_area,
        confidentiality_level=payload.confidentiality_level,
        deposited_at=payload.deposited_at,
        granted_at=payload.granted_at,
        expires_at=payload.expires_at,
        responsible_id=payload.responsible_id,
        active=True,
    )
    db.add(asset)
    db.flush()
    for link in payload.public_links:
        db.add(
            IPAssetPublicLink(
                tenant_id=tenant,
                asset_id=asset.id,
                source=link.source,
                external_ref=link.external_ref,
                label=link.label,
            )
        )
    record_audit(
        db,
        action="NIT_ASSET_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="ip_asset",
        resource_id=asset.id,
        meta={"code": asset.code, "type": asset.asset_type},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(asset)
    return _detail(db, asset)


@router.get("/{asset_id}", response_model=AssetDetail)
def get_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_ASSET_VIEW")),
) -> AssetDetail:
    return _detail(db, _get_or_404(db, ctx, asset_id))


@router.patch("/{asset_id}", response_model=AssetDetail)
def update_asset(
    asset_id: uuid.UUID,
    payload: AssetUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_ASSET_EDIT")),
) -> AssetDetail:
    asset = _get_or_404(db, ctx, asset_id)
    data = payload.model_dump(exclude_unset=True)
    if "unity_id" in data:
        assert_unity_scope(db, ctx, asset.tenant_id, data["unity_id"])
    for field, value in data.items():
        setattr(asset, field, value)
    db.commit()
    db.refresh(asset)
    return _detail(db, asset)


@router.delete("/{asset_id}")
def delete_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_ASSET_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    asset = _get_or_404(db, ctx, asset_id)
    from app.mixins import utcnow

    asset.deleted_at = utcnow()
    asset.active = False
    record_audit(
        db,
        action="NIT_ASSET_DELETE",
        tenant_id=asset.tenant_id,
        user_id=ctx.user.id,
        resource="ip_asset",
        resource_id=asset.id,
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    return {"status": "deleted", "id": str(asset.id)}


@router.post(
    "/{asset_id}/public-links",
    response_model=PublicLinkOut,
    status_code=status.HTTP_201_CREATED,
)
def add_public_link(
    asset_id: uuid.UUID,
    payload: PublicLinkIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_ASSET_MANAGE")),
) -> PublicLinkOut:
    asset = _get_or_404(db, ctx, asset_id)
    if payload.source not in PUBLIC_LINK_SOURCES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Fonte de vínculo público inválida",
        )
    existing = db.execute(
        select(IPAssetPublicLink).where(
            IPAssetPublicLink.tenant_id == asset.tenant_id,
            IPAssetPublicLink.asset_id == asset.id,
            IPAssetPublicLink.source == payload.source,
            IPAssetPublicLink.external_ref == payload.external_ref,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Vínculo já existente"
        )
    link = IPAssetPublicLink(
        tenant_id=asset.tenant_id,
        asset_id=asset.id,
        source=payload.source,
        external_ref=payload.external_ref,
        label=payload.label,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return PublicLinkOut.model_validate(link)


