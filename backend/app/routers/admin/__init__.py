"""Admin router package."""

from fastapi import APIRouter

from app.routers.admin import (
    access_control,
    audit,
    inpi_sync,
    modules,
    roles,
    tenants,
    users,
)

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(tenants.router)
router.include_router(users.router)
router.include_router(modules.router)
router.include_router(roles.router)
router.include_router(access_control.router)
router.include_router(inpi_sync.router)
router.include_router(audit.router)
