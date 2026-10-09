"""Password hashing (Argon2id) and JWT token utilities.

Secrets are read exclusively from environment settings; nothing is hardcoded.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.config import settings

# Argon2id parameters (sensible defaults for a local/server deployment).
_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _ph.check_needs_rehash(hashed)
    except (VerificationError, InvalidHashError):
        return True


# --- JWT --------------------------------------------------------------------


def _create_token(payload: dict, secret: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    to_encode = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(to_encode, secret, algorithm=settings.jwt_algorithm)


def create_access_token(*, user_id: uuid.UUID, tenant_id: uuid.UUID | None) -> str:
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id) if tenant_id else None,
        "type": "access",
    }
    return _create_token(
        payload,
        settings.jwt_secret,
        timedelta(minutes=settings.jwt_access_ttl_minutes),
    )


def create_refresh_token(*, user_id: uuid.UUID) -> str:
    payload = {"sub": str(user_id), "type": "refresh"}
    return _create_token(
        payload,
        settings.jwt_refresh_secret,
        timedelta(days=settings.jwt_refresh_ttl_days),
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def decode_refresh_token(token: str) -> dict:
    return jwt.decode(
        token, settings.jwt_refresh_secret, algorithms=[settings.jwt_algorithm]
    )


def hash_token(token: str) -> str:
    """SHA256 hex digest — used to store refresh tokens without the raw value."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_opaque_token() -> str:
    return secrets.token_urlsafe(48)
