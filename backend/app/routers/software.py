"""Programas de Computador (software) search, detail and export endpoints.

Replicates the architecture of ``routers/patentes.py`` (search with pagination,
selective per-user monitoring, N+1-free detail aggregation, CSV export). Data is
loaded by ``python -m ingestion.import_all --category programas_de_computador``;
this router is DB-only and never calls the INPI during a request.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_permission
from app.export import rows_to_csv
from app.models import (
    Software,
    SoftwareAutor,
    SoftwareCampos,
    SoftwareDespacho,
    SoftwareLinguagem,
    SoftwareMonitoramento,
    SoftwareTipo,
    SoftwareTitular,
)
from app.rbac import AccessContext
from app.schemas.search import (
    MonitoramentoOut,
    MonitoramentoUpdate,
    PaginatedMonitoramentos,
    Pagination,
)
from app.schemas.software import PaginatedSoftwares, SoftwareDetail, SoftwareOut

router = APIRouter(prefix="/softwares", tags=["softwares"])


def _base_query(
    q: str | None,
    numero_inpi: str | None,
    situacao: str | None,
    data_deposito_from: str | None,
    data_deposito_to: str | None,
):
    stmt = select(Software)
    if q:
        stmt = stmt.where(Software.titulo.ilike(f"%{q}%"))
    if numero_inpi:
        stmt = stmt.where(Software.numero_inpi == numero_inpi)
    if situacao:
        stmt = stmt.where(Software.codigo_situacao == situacao)
    if data_deposito_from:
        stmt = stmt.where(Software.data_deposito >= data_deposito_from)
    if data_deposito_to:
        stmt = stmt.where(Software.data_deposito <= data_deposito_to)
    return stmt


def _load_titulares(db: Session, codigos: list[str]) -> dict[str, list[str]]:
    if not codigos:
        return {}
    out: dict[str, list[str]] = {}
    for codigo, nome in db.execute(
        select(SoftwareTitular.codigo_interno, SoftwareTitular.nome)
        .where(SoftwareTitular.codigo_interno.in_(codigos))
        .order_by(SoftwareTitular.codigo_interno, SoftwareTitular.nome)
    ):
        if nome:
            out.setdefault(codigo, []).append(nome)
    return out


def _load_linguagens(db: Session, codigos: list[str]) -> dict[str, list[str]]:
    if not codigos:
        return {}
    out: dict[str, list[str]] = {}
    for codigo, linguagem in db.execute(
        select(SoftwareLinguagem.codigo_interno, SoftwareLinguagem.linguagem)
        .where(SoftwareLinguagem.codigo_interno.in_(codigos))
        .order_by(SoftwareLinguagem.codigo_interno, SoftwareLinguagem.linguagem)
    ):
        if linguagem:
            out.setdefault(codigo, []).append(linguagem)
    return out


def _load_monitoramento(
    db: Session, codigos: list[str], user_id: uuid.UUID
) -> dict[str, SoftwareMonitoramento]:
    if not codigos:
        return {}
    stmt = select(SoftwareMonitoramento).where(
        SoftwareMonitoramento.codigo_interno.in_(codigos),
        SoftwareMonitoramento.user_id == user_id,
        SoftwareMonitoramento.deleted_at.is_(None),
        SoftwareMonitoramento.active.is_(True),
    )
    return {m.codigo_interno: m for m in db.execute(stmt).scalars()}


@router.get("/search", response_model=PaginatedSoftwares)
def search_softwares(
    q: str | None = None,
    numero_inpi: str | None = None,
    situacao: str | None = None,
    data_deposito_from: str | None = None,
    data_deposito_to: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("SOFTWARES_SEARCH")),
) -> PaginatedSoftwares:
    stmt = _base_query(q, numero_inpi, situacao, data_deposito_from, data_deposito_to)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(Software.data_deposito.desc().nullslast())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    page_ids = [r.codigo_interno for r in rows]
    titulares = _load_titulares(db, page_ids)
    linguagens = _load_linguagens(db, page_ids)
    monitorados = _load_monitoramento(db, page_ids, ctx.user.id)

    items: list[SoftwareOut] = []
    for r in rows:
        out = SoftwareOut.model_validate(r)
        nomes = titulares.get(r.codigo_interno, [])
        out.titulares = nomes
        out.num_titulares = len(nomes)
        out.titular_principal = nomes[0] if nomes else None
        out.linguagens = linguagens.get(r.codigo_interno, [])
        mon = monitorados.get(r.codigo_interno)
        out.monitorada = mon is not None
        out.monitoramento_id = mon.id if mon is not None else None
        items.append(out)

    return PaginatedSoftwares(
        pagination=Pagination(page=page, page_size=page_size, total=int(total)),
        items=items,
    )


@router.get("/export")
def export_softwares(
    q: str | None = None,
    numero_inpi: str | None = None,
    situacao: str | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("SOFTWARES_EXPORT")),
) -> StreamingResponse:
    stmt = _base_query(q, numero_inpi, situacao, None, None).limit(50000)
    rows = db.execute(stmt).scalars().all()
    data = [
        {
            "codigo_interno": r.codigo_interno,
            "numero_inpi": r.numero_inpi,
            "titulo": r.titulo,
            "data_deposito": r.data_deposito,
            "data_concessao": r.data_concessao,
            "codigo_situacao": r.codigo_situacao,
            "descricao_situacao": r.descricao_situacao,
        }
        for r in rows
    ]
    return rows_to_csv(
        data,
        [
            "codigo_interno",
            "numero_inpi",
            "titulo",
            "data_deposito",
            "data_concessao",
            "codigo_situacao",
            "descricao_situacao",
        ],
        filename="programas_de_computador.csv",
    )


# --- Selective monitoring (declared BEFORE /{codigo_interno}) ---------------


@router.get("/monitoramento", response_model=PaginatedMonitoramentos)
def list_monitoramento(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("SOFTWARES_VIEW")),
) -> PaginatedMonitoramentos:
    conditions = [
        SoftwareMonitoramento.user_id == ctx.user.id,
        SoftwareMonitoramento.deleted_at.is_(None),
        SoftwareMonitoramento.active.is_(True),
    ]
    total = db.execute(
        select(func.count(SoftwareMonitoramento.id)).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(
            SoftwareMonitoramento,
            Software.titulo,
            Software.numero_inpi,
            Software.descricao_situacao,
            Software.data_deposito,
        )
        .outerjoin(
            Software, Software.codigo_interno == SoftwareMonitoramento.codigo_interno
        )
        .where(*conditions)
        .order_by(SoftwareMonitoramento.monitored_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items: list[MonitoramentoOut] = []
    for row, titulo, numero_inpi, situacao, data_deposito in rows:
        out = MonitoramentoOut.model_validate(row)
        out.tipo = "software"
        out.titulo = titulo
        out.numero_inpi = numero_inpi
        out.situacao = situacao
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
    ctx: AccessContext = Depends(require_permission("SOFTWARES_MONITOR")),
) -> MonitoramentoOut:
    software = db.execute(
        select(Software).where(Software.codigo_interno == codigo_interno)
    ).scalar_one_or_none()
    if software is None:
        raise HTTPException(status_code=404, detail="Programa de computador não encontrado")
    row = db.execute(
        select(SoftwareMonitoramento).where(
            SoftwareMonitoramento.codigo_interno == codigo_interno,
            SoftwareMonitoramento.user_id == ctx.user.id,
        )
    ).scalar_one_or_none()
    if row is None:
        row = SoftwareMonitoramento(
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
    ctx: AccessContext = Depends(require_permission("SOFTWARES_MONITOR")),
) -> dict:
    row = db.execute(
        select(SoftwareMonitoramento).where(
            SoftwareMonitoramento.codigo_interno == codigo_interno,
            SoftwareMonitoramento.user_id == ctx.user.id,
            SoftwareMonitoramento.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Monitoramento não encontrado")
    row.active = False
    row.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "Monitoramento removido."}


@router.get("/{codigo_interno}", response_model=SoftwareDetail)
def get_software(
    codigo_interno: str,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("SOFTWARES_VIEW")),
) -> SoftwareDetail:
    software = db.execute(
        select(Software).where(Software.codigo_interno == codigo_interno)
    ).scalar_one_or_none()
    if software is None:
        raise HTTPException(status_code=404, detail="Programa de computador não encontrado")

    titulares = db.execute(
        select(SoftwareTitular).where(SoftwareTitular.codigo_interno == codigo_interno)
    ).scalars().all()
    autores = db.execute(
        select(SoftwareAutor).where(SoftwareAutor.codigo_interno == codigo_interno)
    ).scalars().all()
    tipos = db.execute(
        select(SoftwareTipo).where(SoftwareTipo.codigo_interno == codigo_interno)
    ).scalars().all()
    campos = db.execute(
        select(SoftwareCampos).where(SoftwareCampos.codigo_interno == codigo_interno)
    ).scalars().all()
    linguagens = db.execute(
        select(SoftwareLinguagem).where(
            SoftwareLinguagem.codigo_interno == codigo_interno
        )
    ).scalars().all()
    despachos = db.execute(
        select(SoftwareDespacho)
        .where(SoftwareDespacho.codigo_interno == codigo_interno)
        .order_by(SoftwareDespacho.data_rpi.desc().nullslast())
    ).scalars().all()

    detail = SoftwareDetail.model_validate(software)
    nomes = [t.nome for t in titulares if t.nome]
    detail.titulares = nomes
    detail.num_titulares = len(nomes)
    detail.titular_principal = nomes[0] if nomes else None
    detail.linguagens = [l.linguagem for l in linguagens if l.linguagem]
    detail.titulares_detalhe = [
        {
            "nome": t.nome,
            "cpf_cnpj": t.cpf_cnpj,
            "tipo_pessoa": t.tipo_pessoa,
            "pais": t.pais,
            "estado": t.estado,
        }
        for t in titulares
    ]
    detail.autores = [
        {"autor": a.autor, "pais": a.pais, "estado": a.estado} for a in autores
    ]
    detail.tipos = [
        {"tipo": t.tipo, "campo_aplicacao": t.campo_aplicacao} for t in tipos
    ]
    detail.campos = [{"campo": c.campo, "valor": c.valor} for c in campos]
    detail.despachos = [
        {
            "numero_rpi": d.numero_rpi,
            "data_rpi": d.data_rpi,
            "codigo_despacho": (d.codigo_despacho or "").strip() or None,
            "descricao_despacho": d.descricao_despacho,
            "complemento_despacho": d.complemento_despacho,
        }
        for d in despachos
    ]
    return detail
