"""IntelliINPI API application factory and ASGI entrypoint.

Run locally with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.logging_config import (
    REQUEST_ID_HEADER,
    new_request_id,
    set_request_id,
    setup_logging,
)
from app.routers import api_router

logger = logging.getLogger("intelliinpi.api")

setup_logging()

DESCRIPTION = """
**IntelliINPI** — plataforma local multi-tenant para pesquisa de marcas e
patentes a partir das bases de dados abertos oficiais do INPI.

* Autenticação JWT (access + refresh opaco).
* Isolamento multi-tenant derivado exclusivamente do usuário autenticado.
* RBAC extensível (Tenant → Usuário → Papel → Módulo → Permissão).
* Pesquisa em marcas e patentes com paginação, filtros e exportação CSV.
"""


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assigns/propagates a correlation id for every request.

    The id comes from the incoming ``X-Request-ID`` header when present (so a
    gateway/proxy can correlate), otherwise a new one is generated. It is
    echoed back in the response header and attached to log records.
    """

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        rid = request.headers.get(REQUEST_ID_HEADER) or new_request_id()
        set_request_id(rid)
        try:
            response = await call_next(request)
        finally:
            set_request_id(rid)
        response.headers[REQUEST_ID_HEADER] = rid
        return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="IntelliINPI API",
        version="1.0.0",
        description=DESCRIPTION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIdMiddleware)

    app.include_router(api_router)

    @app.get("/api/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok", "service": "intelliinpi", "version": "1.0.0"}

    @app.exception_handler(IntegrityError)
    async def _integrity_error(request: Request, exc: IntegrityError) -> JSONResponse:
        # A database constraint violation (unique/foreign key) is a client-visible
        # conflict, not a 500. The SQL text is logged, never returned.
        logger.warning(
            "IntegrityError on %s %s",
            request.method,
            request.url.path,
            extra={"context": {"error": exc.orig.__class__.__name__}},
        )
        return JSONResponse(
            status_code=409,
            content={"detail": "Conflito: o registro viola uma restrição de integridade."},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Log the full exception with stack trace; return a safe generic message.
        logger.exception(
            "Erro interno não tratado em %s %s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno do servidor."},
        )

    return app


app = create_app()
