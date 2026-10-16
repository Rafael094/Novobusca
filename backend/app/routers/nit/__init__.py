"""NIT routers package — aggregates the F1 sub-routers under ``/nit``."""

from fastapi import APIRouter

from app.routers.nit import (
    assets,
    bi,
    committees,
    contracts,
    dashboard,
    devtools,
    disclosures,
    documents,
    indicators,
    integrations,
    notifications,
    portal,
    portfolio,
    projects,
    startups,
    tt,
    workflow,
)

router = APIRouter(prefix="/nit", tags=["nit"])
router.include_router(dashboard.router)
router.include_router(disclosures.router)
router.include_router(documents.router)
router.include_router(workflow.router)
router.include_router(assets.router)
router.include_router(committees.router)
router.include_router(portfolio.router)
router.include_router(tt.router)
router.include_router(contracts.router)
router.include_router(projects.router)
router.include_router(startups.router)
router.include_router(indicators.router)
router.include_router(notifications.router)
router.include_router(portal.router)
router.include_router(bi.router)
router.include_router(integrations.router)
router.include_router(devtools.router)

__all__ = ["router"]
