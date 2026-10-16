"""Dashboard / summary statistics endpoints."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_access_context, require_permission
from app.models import (
    Company,
    Customer,
    Marca,
    Patente,
    PatenteConteudo,
    Tenant,
    User,
)
from app.rbac import AccessContext
from app.schemas.crm import BusinessDashboard
from app.services import crm as crm_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/business", response_model=BusinessDashboard)
def business_dashboard(
    months: int = Query(default=12, ge=1, le=24),
    tenant_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("CRM_DASHBOARD_VIEW")),
) -> BusinessDashboard:
    """Commercial/operational dashboard of the authenticated tenant.

    This is the endpoint the Overview screen consumes. Unlike ``/summary`` it
    never mixes the global INPI base with the tenant's own performance: every
    number here comes from records the tenant actually owns (clients, funnel,
    proposals, follow-ups, monitored PI assets).

    A master admin may inspect all tenants (``tenant_id=None``); an ordinary user
    is always restricted to their own tenant by ``AccessContext``.
    """
    scope = None if ctx.user.is_master_admin else ctx.user.tenant_id
    if ctx.user.is_master_admin and tenant_id is not None:
        scope = tenant_id
    payload = crm_service.build_business_dashboard(db, tenant_id=scope, months=months)
    return BusinessDashboard.model_validate(payload)


def _situacao_group(descricao: str | None, codigo: str | None) -> str:
    """Bucket a situação description into a semantic group for the donut."""
    text = (descricao or codigo or "").lower()
    if "vigor" in text or "concedid" in text or "registro de marca" in text:
        return "Ativos"
    if "arquivad" in text or "extint" in text or "caduc" in text or "nulid" in text:
        return "Encerrados"
    if "exig" in text or "oposi" in text or "pendente" in text or "aguardando" in text:
        return "Em análise"
    return "Outros"


@router.get("/summary")
def summary(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(get_access_context),
) -> dict:
    """Return headline counts and chart series for the dashboard.

    Data counts (marcas/patentes) are global PI data shared across tenants.
    Administrative/CRM counts are tenant-scoped (global for the master admin).
    """
    marcas_total = db.execute(select(func.count(Marca.codigo_interno))).scalar_one()
    patentes_total = db.execute(select(func.count(Patente.codigo_interno))).scalar_one()

    result: dict = {
        "marcas": int(marcas_total),
        "patentes": int(patentes_total),
        "is_master_admin": ctx.user.is_master_admin,
        "modules": ctx.modules,
    }

    # --- Administrative / CRM counts ---------------------------------------
    scope_tenant = None if ctx.user.is_master_admin else ctx.user.tenant_id

    def _count(column, model) -> int:
        conditions = [model.deleted_at.is_(None)]
        if scope_tenant is not None:
            conditions.append(model.tenant_id == scope_tenant)
        return int(db.execute(select(func.count(column)).where(*conditions)).scalar_one())

    if ctx.user.is_master_admin:
        result["tenants"] = int(
            db.execute(
                select(func.count(Tenant.id)).where(Tenant.deleted_at.is_(None))
            ).scalar_one()
        )
        result["users"] = int(
            db.execute(
                select(func.count(User.id)).where(User.deleted_at.is_(None))
            ).scalar_one()
        )
    else:
        result["users"] = int(
            db.execute(
                select(func.count(User.id)).where(
                    User.tenant_id == ctx.user.tenant_id, User.deleted_at.is_(None)
                )
            ).scalar_one()
        )
    result["companies"] = _count(Company.id, Company)
    result["customers"] = _count(Customer.id, Customer)

    # --- Chart series & widgets --------------------------------------------
    result["portfolio_evolution"] = _portfolio_evolution(db)
    result["situacao_distribution"] = _situacao_distribution(db)
    result["latest_events"] = _latest_events(db)
    result["upcoming_deadlines"] = _upcoming_deadlines(db)

    # --- Latest marca deposits (kept for backward compatibility) -----------
    latest_marcas = (
        db.execute(
            select(Marca.numero_inpi, Marca.elemento_nominativo, Marca.data_deposito)
            .where(Marca.data_deposito.is_not(None))
            .order_by(Marca.data_deposito.desc())
            .limit(5)
        )
        .all()
    )
    result["latest_marcas"] = [
        {
            "numero_inpi": r[0],
            "elemento_nominativo": r[1],
            "data_deposito": r[2].isoformat() if r[2] else None,
        }
        for r in latest_marcas
    ]

    return result


def _portfolio_evolution(db: Session) -> list[dict]:
    """Marcas vs Patentes deposits per year (last 6 available years)."""

    def _by_year(model, date_col) -> dict[int, int]:
        rows = db.execute(
            select(
                func.extract("year", date_col).label("ano"),
                func.count(model.codigo_interno),
            )
            .where(date_col.is_not(None))
            .group_by("ano")
            .order_by("ano")
        ).all()
        return {int(r[0]): int(r[1]) for r in rows if r[0] is not None}

    marcas = _by_year(Marca, Marca.data_deposito)
    patentes = _by_year(Patente, Patente.data_deposito)
    years = sorted(set(marcas) | set(patentes))[-6:]
    return [
        {"ano": y, "marcas": marcas.get(y, 0), "patentes": patentes.get(y, 0)}
        for y in years
    ]


def _situacao_distribution(db: Session) -> list[dict]:
    rows = (
        db.execute(
            select(
                Marca.descricao_situacao,
                Marca.codigo_situacao,
                func.count(Marca.codigo_interno),
            ).group_by(Marca.descricao_situacao, Marca.codigo_situacao)
        )
        .all()
    )
    buckets: dict[str, int] = {}
    for descricao, codigo, count in rows:
        key = _situacao_group(descricao, codigo)
        buckets[key] = buckets.get(key, 0) + int(count)
    order = ["Ativos", "Em análise", "Encerrados", "Outros"]
    series = [
        {"label": k, "value": buckets.get(k, 0)}
        for k in order
        if buckets.get(k, 0) > 0
    ]
    return series or [{"label": "Outros", "value": 0}]


def _latest_events(db: Session, limit: int = 6) -> list[dict]:
    marcas = (
        db.execute(
            select(Marca.elemento_nominativo, Marca.numero_inpi, Marca.data_deposito)
            .where(Marca.data_deposito.is_not(None))
            .order_by(Marca.data_deposito.desc())
            .limit(limit)
        )
        .all()
    )
    # The patent title lives on the ``patentes_conteudo`` table (the biblio table
    # itself has no ``titulo`` column), so join it in instead of selecting it
    # from ``patentes`` directly.
    patentes = (
        db.execute(
            select(
                PatenteConteudo.titulo,
                Patente.numero_inpi,
                Patente.data_deposito,
            )
            .select_from(Patente)
            .outerjoin(
                PatenteConteudo,
                PatenteConteudo.codigo_interno == Patente.codigo_interno,
            )
            .where(Patente.data_deposito.is_not(None))
            .order_by(Patente.data_deposito.desc())
            .limit(limit)
        )
        .all()
    )
    events = [
        {
            "tipo": "marca",
            "titulo": r[0] or "—",
            "numero_inpi": r[1],
            "data": r[2].isoformat() if r[2] else None,
        }
        for r in marcas
    ] + [
        {
            "tipo": "patente",
            "titulo": r[0] or "—",
            "numero_inpi": r[1],
            "data": r[2].isoformat() if r[2] else None,
        }
        for r in patentes
    ]
    events.sort(key=lambda e: e["data"] or "", reverse=True)
    return events[:limit]


def _upcoming_deadlines(db: Session, limit: int = 5) -> list[dict]:
    today = date.today()
    rows = (
        db.execute(
            select(
                Marca.elemento_nominativo,
                Marca.numero_inpi,
                Marca.data_vigencia,
                Marca.descricao_situacao,
            )
            .where(Marca.data_vigencia.is_not(None), Marca.data_vigencia >= today)
            .order_by(Marca.data_vigencia.asc())
            .limit(limit)
        )
        .all()
    )
    return [
        {
            "titulo": r[0] or "—",
            "numero_inpi": r[1],
            "data_vigencia": r[2].isoformat() if r[2] else None,
            "situacao": r[3],
            "dias_restantes": (r[2] - today).days if r[2] else None,
        }
        for r in rows
    ]
