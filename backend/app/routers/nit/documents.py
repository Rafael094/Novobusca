"""NIT — confidential document endpoints (``/api/nit/documents``).

Access rules (deny-by-default):

* The tenant is derived from the authenticated user; cross-tenant ids yield 404/403.
* Reading a document requires ``NIT_DOCUMENT_VIEW`` AND (public OR an explicit ACL
  entry matching the caller). ``NIT_DOCUMENT_MANAGE`` grants access within tenant.
* Upload validates the REAL content type (magic bytes) and size; the physical key
  is opaque (``documents/{tenant}/{document_id}``) so traversal/overwrite is impossible.
* Every download of a non-PUBLIC document is audited.
* Downloads are streamed from the private backend through this authenticated
  endpoint — there is NEVER a permanent public URL.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models.nit import (
    CONFIDENTIALITY_PUBLIC,
    DocumentAcl,
    InventionDisclosure,
    InventionDocument,
)
from app.rbac import AccessContext
from app.routers.nit._common import (
    assert_same_tenant,
    can_access_document,
    list_scope,
    scoped_tenant,
    write_tenant,
)
from app.schemas.nit import (
    DocumentAclIn,
    DocumentAclOut,
    DocumentDetail,
    DocumentOut,
    PaginatedDocuments,
)
from app.services import storage

router = APIRouter(prefix="/documents", tags=["nit"])

# Hard cap on how much we will read from the request before rejecting (guards a
# malicious huge upload from exhausting memory): ceiling + 1 byte.
_READ_MARGIN = 1024 * 1024


def _load_or_404(
    db: Session, ctx: AccessContext, document_id: uuid.UUID
) -> InventionDocument:
    document = db.get(InventionDocument, document_id)
    if document is None or document.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado"
        )
    # Cross-tenant ids are indistinguishable from missing ones (no enumeration).
    if not ctx.user.is_master_admin and document.tenant_id != ctx.user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado"
        )
    return document


@router.get("", response_model=PaginatedDocuments)
def list_documents(
    disclosure_id: uuid.UUID | None = None,
    asset_id: uuid.UUID | None = None,
    confidentiality_level: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_DOCUMENT_VIEW")),
) -> PaginatedDocuments:
    scope = list_scope(ctx)
    conditions = [InventionDocument.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(InventionDocument.tenant_id == scope)
    if disclosure_id is not None:
        conditions.append(InventionDocument.disclosure_id == disclosure_id)
    if asset_id is not None:
        conditions.append(InventionDocument.asset_id == asset_id)
    if confidentiality_level:
        conditions.append(
            InventionDocument.confidentiality_level == confidentiality_level
        )
    total = db.execute(
        select(func.count()).select_from(InventionDocument).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(InventionDocument)
            .where(*conditions)
            .order_by(InventionDocument.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedDocuments(
        items=[DocumentOut.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total),
    )


@router.post("", response_model=DocumentDetail, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    disclosure_id: uuid.UUID | None = Form(default=None),
    asset_id: uuid.UUID | None = Form(default=None),
    confidentiality_level: str = Form(default="INTERNAL"),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_DOCUMENT_UPLOAD")),
    meta: dict = Depends(client_meta),
) -> DocumentDetail:
    from app.services.storage import FileTooLarge, StorageError, UnsupportedFileType

    if confidentiality_level not in {
        "PUBLIC",
        "INTERNAL",
        "RESTRICTED",
        "CONFIDENTIAL",
    }:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nível de confidencialidade inválido",
        )
    if disclosure_id is None and asset_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe disclosure_id ou asset_id para o documento",
        )

    tenant = write_tenant(ctx, None)

    # Validate the parent belongs to this tenant (no cross-tenant attach).
    if disclosure_id is not None:
        parent = db.get(InventionDisclosure, disclosure_id)
        if parent is None or parent.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Comunicação não encontrada"
            )
        assert_same_tenant(ctx, parent.tenant_id)
        tenant = parent.tenant_id

    data = await file.read(storage.settings.document_max_size_bytes + _READ_MARGIN)
    document_id = uuid.uuid4()
    key = storage.build_storage_key(tenant, document_id)
    try:
        stored = storage.get_storage().put(key, data)
    except FileTooLarge as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))
    except UnsupportedFileType as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    safe_name = (file.filename or "documento")[:255]
    document = InventionDocument(
        id=document_id,
        tenant_id=tenant,
        disclosure_id=disclosure_id,
        asset_id=asset_id,
        uploaded_by_id=ctx.user.id,
        original_filename=safe_name,
        storage_key=stored.key,
        mime_type=stored.detected_mime,
        size_bytes=stored.size_bytes,
        checksum_sha256=stored.sha256,
        confidentiality_level=confidentiality_level,
        title=title,
        description=description,
        scan_status="PENDING",
        active=True,
    )
    db.add(document)
    record_audit(
        db,
        action="NIT_DOCUMENT_UPLOAD",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="invention_document",
        resource_id=document.id,
        meta={
            "filename": safe_name,
            "size": stored.size_bytes,
            "level": confidentiality_level,
        },
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(document)
    return DocumentDetail.model_validate(document)


@router.get("/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_DOCUMENT_VIEW")),
) -> DocumentDetail:
    document = _load_or_404(db, ctx, document_id)
    if not can_access_document(db, ctx, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Acesso ao documento negado"
        )
    detail = DocumentDetail.model_validate(document)
    detail.acls = [
        DocumentAclOut.model_validate(a)
        for a in db.execute(
            select(DocumentAcl).where(DocumentAcl.document_id == document.id)
        ).scalars()
    ]
    return detail


@router.get("/{document_id}/download")
def download_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_DOCUMENT_VIEW")),
    meta: dict = Depends(client_meta),
) -> Response:
    document = _load_or_404(db, ctx, document_id)
    if not can_access_document(db, ctx, document):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Acesso ao documento negado"
        )
    try:
        content = storage.get_storage().get(document.storage_key)
    except storage.StorageError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    # Audit EVERY non-public download (decision D5).
    if document.confidentiality_level != CONFIDENTIALITY_PUBLIC:
        record_audit(
            db,
            action="NIT_DOCUMENT_DOWNLOAD",
            tenant_id=document.tenant_id,
            user_id=ctx.user.id,
            resource="invention_document",
            resource_id=document.id,
            meta={"level": document.confidentiality_level},
            ip=meta.get("ip"),
            user_agent=meta.get("user_agent"),
        )

    # ``attachment`` + a sanitised ASCII filename; never inline for confidential
    # files (avoids browser rendering/PDF script execution).
    safe = document.original_filename.replace('"', "")
    return Response(
        content=content,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{safe}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/{document_id}/acl", response_model=DocumentAclOut, status_code=status.HTTP_201_CREATED
)
def add_acl(
    document_id: uuid.UUID,
    payload: DocumentAclIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_DOCUMENT_MANAGE")),
    meta: dict = Depends(client_meta),
) -> DocumentAclOut:
    document = _load_or_404(db, ctx, document_id)
    assert_same_tenant(ctx, document.tenant_id)

    # Role ACL subjects must reference a real role code.
    if payload.subject_kind == "ROLE":
        from app.models import Role

        exists = db.execute(
            select(Role).where(Role.code == payload.subject_id)
        ).scalar_one_or_none()
        if exists is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Papel inexistente",
            )

    existing = db.execute(
        select(DocumentAcl).where(
            DocumentAcl.document_id == document.id,
            DocumentAcl.subject_kind == payload.subject_kind,
            DocumentAcl.subject_id == payload.subject_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.permission = payload.permission
        acl = existing
    else:
        acl = DocumentAcl(
            tenant_id=document.tenant_id,
            document_id=document.id,
            subject_kind=payload.subject_kind,
            subject_id=payload.subject_id,
            permission=payload.permission,
            granted_by_id=ctx.user.id,
        )
        db.add(acl)
    record_audit(
        db,
        action="NIT_DOCUMENT_ACL_SET",
        tenant_id=document.tenant_id,
        user_id=ctx.user.id,
        resource="invention_document",
        resource_id=document.id,
        meta={"subject_kind": payload.subject_kind, "subject_id": payload.subject_id},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(acl)
    return DocumentAclOut.model_validate(acl)


@router.delete("/{document_id}")
def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_DOCUMENT_MANAGE")),
    meta: dict = Depends(client_meta),
) -> dict:
    document = _load_or_404(db, ctx, document_id)
    assert_same_tenant(ctx, document.tenant_id)
    from app.mixins import utcnow

    document.deleted_at = utcnow()
    document.active = False
    record_audit(
        db,
        action="NIT_DOCUMENT_DELETE",
        tenant_id=document.tenant_id,
        user_id=ctx.user.id,
        resource="invention_document",
        resource_id=document.id,
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    return {"status": "deleted", "id": str(document.id)}


