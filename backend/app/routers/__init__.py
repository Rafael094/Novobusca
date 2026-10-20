"""Routers package.

``api_router`` aggregates every sub-router under the ``/api`` prefix.
"""

from fastapi import APIRouter

from app.routers import (
    analises,
    auth,
    chat,
    clientes,
    crm,
    dashboard,
    desenhos,
    marcas,
    patentes,
    search,
    software,
)
from app.routers.admin import router as admin_router
from app.routers.nit import router as nit_router

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(dashboard.router)
api_router.include_router(marcas.router)
api_router.include_router(patentes.router)
api_router.include_router(desenhos.router)
api_router.include_router(software.router)
api_router.include_router(search.router)
api_router.include_router(clientes.router)
api_router.include_router(crm.router)
api_router.include_router(analises.router)
api_router.include_router(chat.router)
api_router.include_router(nit_router)
api_router.include_router(admin_router)

__all__ = ["api_router"]
