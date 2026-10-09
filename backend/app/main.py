"""IntelliINPI API application factory and ASGI entrypoint.

Run locally with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import api_router

DESCRIPTION = """
**IntelliINPI** — plataforma local multi-tenant para pesquisa de marcas e
patentes a partir das bases de dados abertos oficiais do INPI.

* Autenticação JWT (access + refresh opaco).
* Isolamento multi-tenant derivado exclusivamente do usuário autenticado.
* RBAC extensível (Tenant → Usuário → Papel → Módulo → Permissão).
* Pesquisa em marcas e patentes com paginação, filtros e exportação CSV.
"""


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

    app.include_router(api_router)

    @app.get("/api/health", tags=["health"])
    def health() -> dict:
        return {"status": "ok", "service": "intelliinpi", "version": "1.0.0"}

    @app.exception_handler(Exception)
    async def _unhandled(_request, exc: Exception) -> JSONResponse:  # pragma: no cover
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno do servidor."},
        )

    return app


app = create_app()
