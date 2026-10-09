"""Patentes (patent) search, detail and export endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_permission
from app.export import rows_to_csv
from app.models import (
    Patente,
    PatenteClassificacaoIpc,
    PatenteConteudo,
    PatenteDepositante,
    PatenteDespacho,
    PatenteInventor,
    PatenteMonitoramento,
    PatentePrioridade,
    PatenteProcurador,
)
from app.rbac import AccessContext
from app.schemas.search import (
    MonitoramentoOut,
    MonitoramentoUpdate,
    PaginatedMonitoramentos,
    PaginatedPatentes,
    Pagination,
    PatenteDetail,
    PatenteOut,
)

router = APIRouter(prefix="/patentes", tags=["patentes"])


def _base_query(
    q: str | None,
    numero_inpi: str | None,
    data_deposito_from: str | None,
    data_deposito_to: str | None,
):
    stmt = select(Patente)
    if q:
        like = f"%{q}%"
        # Search title/abstract via a correlated EXISTS on the conteudo table.
        conteudo = select(PatenteConteudo.codigo_interno).where(
            PatenteConteudo.codigo_interno == Patente.codigo_interno,
            or_(
                PatenteConteudo.titulo.ilike(like),
                PatenteConteudo.resumo.ilike(like),
            ),
        )
        stmt = stmt.where(
            or_(
                Patente.numero_inpi.ilike(like),
                Patente.numero_pct.ilike(like),
                Patente.codigo_interno.in_(conteudo),
            )
        )
    if numero_inpi:
        stmt = stmt.where(Patente.numero_inpi == numero_inpi)
    if data_deposito_from:
        stmt = stmt.where(Patente.data_deposito >= data_deposito_from)
    if data_deposito_to:
        stmt = stmt.where(Patente.data_deposito <= data_deposito_to)
    return stmt


@router.get("/search", response_model=PaginatedPatentes)
def search_patentes(
    q: str | None = None,
    numero_inpi: str | None = None,
    data_deposito_from: str | None = None,
    data_deposito_to: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("PATENTES_SEARCH")),
) -> PaginatedPatentes:
    stmt = _base_query(q, numero_inpi, data_deposito_from, data_deposito_to)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(Patente.data_deposito.desc().nullslast())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    codes = [r.codigo_interno for r in rows]
    monitorados: dict[str, PatenteMonitoramento] = {}
    if codes:
        for mon in db.execute(
            select(PatenteMonitoramento).where(
                PatenteMonitoramento.codigo_interno.in_(codes),
                PatenteMonitoramento.user_id == ctx.user.id,
                PatenteMonitoramento.deleted_at.is_(None),
                PatenteMonitoramento.active.is_(True),
            )
        ).scalars():
            monitorados[mon.codigo_interno] = mon
    items = []
    for r in rows:
        out = PatenteOut.model_validate(r)
        mon = monitorados.get(r.codigo_interno)
        out.monitorada = mon is not None
        out.monitoramento_id = mon.id if mon is not None else None
        items.append(out)
    return PaginatedPatentes(
        pagination=Pagination(page=page, page_size=page_size, total=int(total)),
        items=items,
    )


@router.get("/export")
def export_patentes(
    q: str | None = None,
    numero_inpi: str | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("PATENTES_EXPORT")),
) -> StreamingResponse:
    stmt = _base_query(q, numero_inpi, None, None).limit(50000)
    rows = db.execute(stmt).scalars().all()
    data = [
        {
            "codigo_interno": r.codigo_interno,
            "numero_inpi": r.numero_inpi,
            "data_deposito": r.data_deposito,
            "data_publicacao": r.data_publicacao,
            "numero_pct": r.numero_pct,
        }
        for r in rows
    ]
    return rows_to_csv(
        data,
        ["codigo_interno", "numero_inpi", "data_deposito", "data_publicacao", "numero_pct"],
        filename="patentes.csv",
    )


# --- Selective monitoring (section 4) ---------------------------------------
# Monitoring is NEVER global/automatic — a row exists only for the specific
# patente the current user chose to watch (tenant derived from the token).
# Declared BEFORE ``GET /{codigo_interno}`` so the literal path wins over the
# path parameter (FastAPI matches routes in declaration order).


@router.get("/monitoramento", response_model=PaginatedMonitoramentos)
def list_monitoramento(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("PATENTES_VIEW")),
) -> PaginatedMonitoramentos:
    """List the current user's monitored patentes (their own watch list only)."""
    conditions = [
        PatenteMonitoramento.user_id == ctx.user.id,
        PatenteMonitoramento.deleted_at.is_(None),
        PatenteMonitoramento.active.is_(True),
    ]
    total = db.execute(
        select(func.count(PatenteMonitoramento.id)).where(*conditions)
    ).scalar_one()
    # Join the patente biblio + conteudo rows so the watch list can display the
    # title/number without an extra request per row (outer joins: rows may vanish).
    rows = db.execute(
        select(
            PatenteMonitoramento,
            Patente.numero_inpi,
            Patente.data_deposito,
            PatenteConteudo.titulo,
        )
        .outerjoin(
            Patente, Patente.codigo_interno == PatenteMonitoramento.codigo_interno
        )
        .outerjoin(
            PatenteConteudo,
            PatenteConteudo.codigo_interno == PatenteMonitoramento.codigo_interno,
        )
        .where(*conditions)
        .order_by(PatenteMonitoramento.monitored_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items: list[MonitoramentoOut] = []
    for row, numero_inpi, data_deposito, titulo in rows:
        out = MonitoramentoOut.model_validate(row)
        out.tipo = "patente"
        out.titulo = titulo
        out.numero_inpi = numero_inpi
        out.data_deposito = data_deposito
        items.append(out)
    return PaginatedMonitoramentos(
        pagination=Pagination(page=page, page_size=page_size, total=int(total)),
        items=items,
    )


@router.post("/{codigo_interno}/monitoramento", response_model=MonitoramentoOut)
def set_monitoramento(
    codigo_interno: str,
    payload: MonitoramentoUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("PATENTES_MONITOR")),
) -> MonitoramentoOut:
    """Activate/deactivate monitoring for ONE patente (selective, per user)."""
    patente = db.execute(
        select(Patente).where(Patente.codigo_interno == codigo_interno)
    ).scalar_one_or_none()
    if patente is None:
        raise HTTPException(status_code=404, detail="Patente não encontrada")

    row = db.execute(
        select(PatenteMonitoramento).where(
            PatenteMonitoramento.codigo_interno == codigo_interno,
            PatenteMonitoramento.user_id == ctx.user.id,
        )
    ).scalar_one_or_none()
    if row is None:
        row = PatenteMonitoramento(
            tenant_id=ctx.user.tenant_id,
            user_id=ctx.user.id,
            codigo_interno=codigo_interno,
            active=payload.active,
            notes=payload.notes,
        )
        db.add(row)
    else:
        row.active = payload.active
        row.deleted_at = None
        if payload.notes is not None:
            row.notes = payload.notes
    db.commit()
    db.refresh(row)
    return MonitoramentoOut.model_validate(row)


@router.delete("/{codigo_interno}/monitoramento")
def remove_monitoramento(
    codigo_interno: str,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("PATENTES_MONITOR")),
) -> dict:
    """Stop monitoring this patente entirely (soft delete of the watch row)."""
    row = db.execute(
        select(PatenteMonitoramento).where(
            PatenteMonitoramento.codigo_interno == codigo_interno,
            PatenteMonitoramento.user_id == ctx.user.id,
            PatenteMonitoramento.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Monitoramento não encontrado")
    row.active = False
    row.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "Monitoramento removido."}



@router.get("/{codigo_interno}", response_model=PatenteDetail)
def get_patente(
    codigo_interno: str,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("PATENTES_VIEW")),
) -> PatenteDetail:
    patente = db.execute(
        select(Patente).where(Patente.codigo_interno == codigo_interno)
    ).scalar_one_or_none()
    if patente is None:
        raise HTTPException(status_code=404, detail="Patente não encontrada")

    conteudo = db.execute(
        select(PatenteConteudo).where(
            PatenteConteudo.codigo_interno == codigo_interno
        )
    ).scalar_one_or_none()
    depositantes = db.execute(
        select(PatenteDepositante).where(
            PatenteDepositante.codigo_interno == codigo_interno
        )
    ).scalars().all()
    inventores = db.execute(
        select(PatenteInventor).where(
            PatenteInventor.codigo_interno == codigo_interno
        )
    ).scalars().all()
    procuradores = db.execute(
        select(PatenteProcurador).where(
            PatenteProcurador.codigo_interno == codigo_interno
        )
    ).scalars().all()
    prioridades = db.execute(
        select(PatentePrioridade).where(
            PatentePrioridade.codigo_interno == codigo_interno
        )
    ).scalars().all()
    ipc = db.execute(
        select(PatenteClassificacaoIpc).where(
            PatenteClassificacaoIpc.codigo_interno == codigo_interno
        )
    ).scalars().all()
    despachos = db.execute(
        select(PatenteDespacho)
        .where(PatenteDespacho.codigo_interno == codigo_interno)
        .order_by(PatenteDespacho.data_rpi.desc().nullslast())
    ).scalars().all()

    detail = PatenteDetail.model_validate(patente)
    detail.titulo = conteudo.titulo if conteudo else None
    detail.resumo = conteudo.resumo if conteudo else None
    detail.depositantes = [
        {"depositante": d.depositante, "cgccpfdepositante": d.cgccpfdepositante, "pais": d.pais}
        for d in depositantes
    ]
    detail.inventores = [
        {"autor": i.autor, "pais": i.pais} for i in inventores
    ]
    detail.procuradores = [
        {"procurador": p.procurador, "cgccpfprocurador": p.cgccpfprocurador}
        for p in procuradores
    ]
    detail.prioridades = [
        {
            "pais_prioridade": p.pais_prioridade,
            "numero_prioridade": p.numero_prioridade,
            "data_prioridade": p.data_prioridade,
        }
        for p in prioridades
    ]
    detail.classificacoes_ipc = [
        {"simbolo": c.simbolo, "versao": c.versao} for c in ipc
    ]
    detail.despachos = [
        {
            "numero_rpi": d.numero_rpi,
            "data_rpi": d.data_rpi,
            "codigo_despacho": d.codigo_despacho,
            "complemento_despacho": d.complemento_despacho,
        }
        for d in despachos
    ]
    return detail


# The monitoring endpoints are declared ABOVE `GET /{codigo_interno}` on
# purpose: FastAPI matches routes in declaration order, so a literal
# ``/monitoramento`` must come before the ``{codigo_interno}`` path parameter
# (otherwise it would be captured as a patente code).



