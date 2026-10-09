"""FastAPI dependencies: authentication, authorization and tenant isolation.

The tenant is ALWAYS derived from the authenticated user (token), never from the
request body/query. Administrative endpoints require master admin or a specific
permission.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.rbac import AccessContext, build_access_context
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Não autenticado") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise _unauthorized()
    try:
        payload = decode_access_token(credentials.credentials)
    except ExpiredSignatureError:
        raise _unauthorized("Token expirado")
    except InvalidTokenError:
        raise _unauthorized("Token inválido")

    if payload.get("type") != "access":
        raise _unauthorized("Tipo de token inválido")

    sub = payload.get("sub")
    if not sub:
        raise _unauthorized()

    try:
        user_id = uuid.UUID(sub)
    except (ValueError, TypeError):
        raise _unauthorized()

    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise _unauthorized("Usuário não encontrado")
    if not user.active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Usuário inativo"
        )
    # Tenant active check (master admin has no tenant requirement).
    if not user.is_master_admin:
        if user.tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Usuário sem tenant"
            )
        tenant = user.tenant
        if tenant is None or not tenant.active or tenant.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Tenant inativo"
            )
    return user


def get_access_context(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AccessContext:
    return build_access_context(db, user)


def require_permission(code: str) -> Callable:
    """Dependency factory enforcing a permission code."""

    def _checker(ctx: AccessContext = Depends(get_access_context)) -> AccessContext:
        if not ctx.has_permission(code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permissão necessária: {code}",
            )
        return ctx

    return _checker


def require_module(code: str) -> Callable:
    def _checker(ctx: AccessContext = Depends(get_access_context)) -> AccessContext:
        if not ctx.has_module(code):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Módulo não habilitado: {code}",
            )
        return ctx

    return _checker


def require_master_admin(
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_master_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito ao Master Admin",
        )
    return user


def client_meta(
    x_forwarded_for: str | None = Header(default=None),
    user_agent: str | None = Header(default=None),
) -> dict[str, str | None]:
    ip = None
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    return {"ip": ip, "user_agent": user_agent}
