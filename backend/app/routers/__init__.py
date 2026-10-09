"""Routers package.

``api_router`` aggregates every sub-router under the ``/api`` prefix.
"""

from fastapi import APIRouter

from app.routers import (
    analises,
    auth,
    clientes,
    dashboard,
    marcas,
    patentes,
    search,
)
from app.routers.admin import router as admin_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(marcas.router)
api_router.include_router(patentes.router)
api_router.include_router(search.router)
api_router.include_router(clientes.router)
api_router.include_router(analises.router)
api_router.include_router(admin_router)

__all__ = ["api_router"]
