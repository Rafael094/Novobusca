"""NIT F5 — developer tooling (``/api/nit/dev``).

Exposes the generated TypeScript types (from the live OpenAPI schema) so the
frontend can be regenerated instead of hand-edited, reducing contract drift
(R-18). Access is gated by an integration-style permission; it returns no data.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse

from app.deps import require_permission
from app.rbac import AccessContext
from app.services.ts_types import generate_types

router = APIRouter(prefix="/dev", tags=["nit"])


@router.get("/ts-types", response_class=PlainTextResponse)
def ts_types(
    request: Request,
    ctx: AccessContext = Depends(require_permission("NIT_INTEGRATION_VIEW")),
) -> PlainTextResponse:
    """Return TypeScript declarations generated from the app's OpenAPI schema."""
    openapi = request.app.openapi()
    content = generate_types(openapi)
    return PlainTextResponse(
        content=content,
        headers={"Content-Disposition": 'inline; filename="nit-api-types.ts"'},
    )
