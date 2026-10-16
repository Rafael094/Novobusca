"""Sequential, concurrency-safe protocol generation (decision A3).

A protocol has the shape ``NIT-{YYYY}-{SEQ:4d}`` and is unique per tenant
(``UniqueConstraint(tenant_id, protocol)``). The sequence restarts every year.

Concurrency: the function computes the next value inside the SAME transaction as
the INSERT and relies on the unique constraint as the final guarantee. Callers
retry on ``IntegrityError`` (see ``allocate_protocol``) so two concurrent
submissions can never persist duplicate protocols.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.nit import InventionDisclosure

PROTOCOL_PREFIX = "NIT"


def _year() -> int:
    return datetime.now(timezone.utc).year


def peek_next_sequence(db: Session, tenant_id: uuid.UUID, year: int) -> int:
    """Return the next sequence number for ``tenant_id``/``year`` (best effort).

    ``peek`` is only a preview; the authoritative value is the one produced while
    the INSERT is pending (the unique index decides in a race).
    """
    prefix = f"{PROTOCOL_PREFIX}-{year}-"
    last = db.execute(
        select(func.max(InventionDisclosure.protocol)).where(
            InventionDisclosure.tenant_id == tenant_id,
            InventionDisclosure.protocol.like(f"{prefix}%"),
        )
    ).scalar_one_or_none()
    if not last:
        return 1
    try:
        return int(last.rsplit("-", 1)[1]) + 1
    except (IndexError, ValueError):  # pragma: no cover - defensive
        return 1


def format_protocol(year: int, sequence: int) -> str:
    return f"{PROTOCOL_PREFIX}-{year}-{sequence:04d}"


def next_protocol(db: Session, tenant_id: uuid.UUID) -> str:
    """Compute the next protocol string (does NOT commit).

    Must be called within the disclosure-creation transaction so the sequence and
    the INSERT are atomic with respect to the unique constraint.
    """
    year = _year()
    sequence = peek_next_sequence(db, tenant_id, year)
    return format_protocol(year, sequence)
