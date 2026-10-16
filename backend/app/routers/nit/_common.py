"""Shared helpers for the NIT routers: tenant/unity scoping and ACL resolution.

Every NIT endpoint derives the tenant from the authenticated access context
(never from the request). These helpers implement the isolation rules once so no
router forgets them:

* ``write_tenant`` — the tenant a NEW record belongs to.
* ``scoped_tenant`` — the tenant to FILTER a list by.
* ``assert_same_tenant`` — reject cross-tenant access by a guessed id (403).
* ``assert_unity_scope`` — validate an optional unity belongs to the tenant.
* ``can_access_document`` — RBAC + explicit ACL check for document access.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Unity
from app.models.nit import (
    ACL_MANAGE,
    ACL_READ,
    ACL_SUBJECT_ROLE,
    ACL_SUBJECT_UNITY,
    ACL_SUBJECT_USER,
    ACL_WRITE,
    CONFIDENTIALITY_PUBLIC,
    DocumentAcl,
    InventionDocument,
)
from app.rbac import AccessContext


def write_tenant(ctx: AccessContext, requested: uuid.UUID | None) -> uuid.UUID:
    """Tenant to assign on create (master admin may target any tenant)."""
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


def scoped_tenant(
    ctx: AccessContext,
    requested: uuid.UUID | None,
    *,
    allow_all: bool = False,
) -> uuid.UUID | None:
    """Tenant to filter by.

    * Master admin: defaults to *their own* tenant so the module is usable;
      passing ``requested`` targets another tenant. Only when ``allow_all`` is
      true does an absent ``requested`` mean "every tenant" (``None``) -- used by
      cross-tenant list endpoints that tolerate a ``None`` scope.
    * Any other user: ``ctx.user.tenant_id`` (403 when ``requested`` diverges).
    """
    if ctx.user.is_master_admin:
        if requested is not None:
            return requested
        return None if allow_all else ctx.user.tenant_id
    if requested is not None and requested != ctx.user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é permitido acessar dados de outro tenant",
        )
    return ctx.user.tenant_id


def list_scope(ctx: AccessContext, requested: uuid.UUID | None = None) -> uuid.UUID | None:
    """Tenant filter for **list/read** endpoints, tolerant of a ``None`` scope.

    Unlike :func:`scoped_tenant`, an absent scope never silently falls back to
    the master admin's own (usually empty) tenant:

    * Master admin: ``requested`` selects a specific tenant; when omitted the
      caller sees **every tenant** (``None``) — the cross-tenant administrative
      reach the master admin already has everywhere else. This is what keeps
      the NIT module populated instead of showing an empty screen.
    * Ordinary user: always their own tenant; a diverging ``requested`` is
      rejected with 403.

    Callers apply the returned scope **only when it is not ``None``**::

        scope = list_scope(ctx)
        conditions = [Model.deleted_at.is_(None)]
        if scope is not None:
            conditions.append(Model.tenant_id == scope)
    """
    if ctx.user.is_master_admin:
        return requested
    if requested is not None and requested != ctx.user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não é permitido acessar dados de outro tenant",
        )
    return ctx.user.tenant_id


def assert_same_tenant(ctx: AccessContext, tenant_id: uuid.UUID) -> None:
    """Raise 403 when a record belongs to another tenant (IDOR protection)."""
    if ctx.user.is_master_admin:
        return
    if tenant_id != ctx.user.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado: registro de outro tenant",
        )


def assert_unity_scope(
    db: Session, ctx: AccessContext, tenant_id: uuid.UUID, unity_id: uuid.UUID | None
) -> None:
    """Validate a referenced unity exists AND belongs to ``tenant_id``.

    This blocks cross-tenant (or cross-institution) references passed by id.
    """
    if unity_id is None:
        return
    unity = db.get(Unity, unity_id)
    if unity is None or unity.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unidade inválida para este tenant",
        )


def _has_acl(
    db: Session, ctx: AccessContext, document: InventionDocument, levels: set[str]
) -> bool:
    """True when an explicit ACL entry grants at least one of ``levels``.

    ``MANAGE`` is the strongest permission and satisfies ``READ``/``WRITE``.
    """
    effective = set(levels)
    if ACL_READ in effective or ACL_WRITE in effective:
        effective.add(ACL_MANAGE)
    acls = db.execute(
        select(DocumentAcl).where(DocumentAcl.document_id == document.id)
    ).scalars()
    role_codes = set(ctx.roles)
    unity_ids = {str(u) for u in ctx.unities}
    for acl in acls:
        if acl.permission not in effective:
            continue
        if acl.subject_kind == ACL_SUBJECT_USER and acl.subject_id == str(ctx.user.id):
            return True
        if acl.subject_kind == ACL_SUBJECT_ROLE and acl.subject_id in role_codes:
            return True
        if acl.subject_kind == ACL_SUBJECT_UNITY and acl.subject_id in unity_ids:
            return True
    return False


def can_access_document(
    db: Session,
    ctx: AccessContext,
    document: InventionDocument,
    *,
    write: bool = False,
) -> bool:
    """RBAC + ACL decision for reading/writing a document.

    * Another tenant => never.
    * Master admin => always.
    * ``NIT_DOCUMENT_MANAGE`` => always (within the tenant).
    * ``PUBLIC`` document => any caller holding ``NIT_DOCUMENT_VIEW``.
    * Otherwise => requires an explicit ACL entry matching the caller.
    """
    if ctx.user.is_master_admin:
        return True
    if document.tenant_id != ctx.user.tenant_id:
        return False
    if ctx.has_permission("NIT_DOCUMENT_MANAGE"):
        return True
    if write:
        return _has_acl(db, ctx, document, {ACL_MANAGE})
    if document.confidentiality_level == CONFIDENTIALITY_PUBLIC and ctx.has_permission(
        "NIT_DOCUMENT_VIEW"
    ):
        return True
    if not ctx.has_permission("NIT_DOCUMENT_VIEW"):
        return False
    return _has_acl(db, ctx, document, {ACL_READ, ACL_WRITE})
