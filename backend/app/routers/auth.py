"""Authentication endpoints: login, refresh, logout, me.

Security notes:
- Login never reveals whether the email exists (generic error).
- Tenant is derived from the authenticated user, never trusted from the client.
- Failed logins are rate-limited and audited.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jwt import ExpiredSignatureError, InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.config import settings
from app.db import get_db
from app.deps import client_meta, get_access_context
from app.models import RefreshToken, User
from app.rbac import AccessContext
from app.rate_limit import login_limiter
from app.schemas.auth import LoginRequest, MeResponse, RefreshRequest, TokenResponse
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_GENERIC_LOGIN_ERROR = "Credenciais inválidas."


def _issue_tokens(db: Session, user: User, meta: dict) -> TokenResponse:
    access = create_access_token(user_id=user.id, tenant_id=user.tenant_id)
    refresh = create_refresh_token(user_id=user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh),
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=settings.jwt_refresh_ttl_days),
            ip=meta.get("ip"),
            user_agent=meta.get("user_agent"),
        )
    )
    db.commit()
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.jwt_access_ttl_minutes * 60,
    )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    meta: dict = Depends(client_meta),
) -> TokenResponse:
    client_ip = meta.get("ip") or (request.client.host if request.client else "unknown")
    if not login_limiter.allow(client_ip):
        record_audit(
            db,
            action="LOGIN_BLOCKED_RATE_LIMIT",
            meta={"email": payload.email},
            ip=client_ip,
            user_agent=meta.get("user_agent"),
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Muitas tentativas de login. Tente novamente mais tarde.",
        )

    user = db.execute(
        select(User).where(
            User.email == payload.email.lower(), User.deleted_at.is_(None)
        )
    ).scalar_one_or_none()

    if user is None or not verify_password(payload.password, user.password_hash):
        record_audit(
            db,
            action="LOGIN_FAILED",
            meta={"email": payload.email},
            ip=client_ip,
            user_agent=meta.get("user_agent"),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_GENERIC_LOGIN_ERROR
        )

    if not user.active:
        record_audit(
            db,
            action="LOGIN_FAILED_INACTIVE",
            user_id=user.id,
            tenant_id=user.tenant_id,
            ip=client_ip,
            user_agent=meta.get("user_agent"),
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=_GENERIC_LOGIN_ERROR
        )

    if not user.is_master_admin:
        tenant = user.tenant
        if tenant is None or not tenant.active or tenant.deleted_at is not None:
            record_audit(
                db,
                action="LOGIN_FAILED_TENANT_INACTIVE",
                user_id=user.id,
                tenant_id=user.tenant_id,
                ip=client_ip,
                user_agent=meta.get("user_agent"),
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=_GENERIC_LOGIN_ERROR
            )

    user.last_login_at = datetime.now(timezone.utc)
    login_limiter.reset(client_ip)
    tokens = _issue_tokens(db, user, meta)
    record_audit(
        db,
        action="LOGIN",
        user_id=user.id,
        tenant_id=user.tenant_id,
        ip=client_ip,
        user_agent=meta.get("user_agent"),
    )
    return tokens


@router.post("/refresh", response_model=TokenResponse)
def refresh(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
    meta: dict = Depends(client_meta),
) -> TokenResponse:
    try:
        decoded = decode_refresh_token(payload.refresh_token)
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expirado"
        )
    except InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido"
        )

    token_hash = hash_token(payload.refresh_token)
    stored = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()
    if stored is None or stored.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token inválido"
        )
    if stored.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expirado"
        )

    user = db.get(User, uuid.UUID(decoded["sub"]))
    if user is None or user.deleted_at is not None or not user.active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido"
        )

    stored.revoked_at = datetime.now(timezone.utc)
    tokens = _issue_tokens(db, user, meta)
    record_audit(
        db,
        action="TOKEN_REFRESH",
        user_id=user.id,
        tenant_id=user.tenant_id,
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return tokens


@router.post("/logout")
def logout(
    payload: RefreshRequest,
    db: Session = Depends(get_db),
    meta: dict = Depends(client_meta),
) -> dict:
    token_hash = hash_token(payload.refresh_token)
    stored = db.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).scalar_one_or_none()
    user_id = None
    tenant_id = None
    if stored is not None:
        stored.revoked_at = datetime.now(timezone.utc)
        user_id = stored.user_id
        user = db.get(User, stored.user_id)
        tenant_id = user.tenant_id if user else None
        db.commit()
    record_audit(
        db,
        action="LOGOUT",
        user_id=user_id,
        tenant_id=tenant_id,
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
    )
    return {"detail": "Logout realizado com sucesso."}


@router.get("/me", response_model=MeResponse)
def me(ctx: AccessContext = Depends(get_access_context)) -> MeResponse:
    user = ctx.user
    return MeResponse(
        id=user.id,
        name=user.name,
        email=user.email,
        is_master_admin=user.is_master_admin,
        tenant_id=user.tenant_id,
        tenant_name=user.tenant.social_reason if user.tenant else None,
        person_id=user.person_id,
        roles=ctx.roles,
        modules=ctx.modules,
        permissions=sorted(ctx.permissions),
        resources=sorted(ctx.resources),
    )
