"""Desenhos Industriais (industrial design) search, detail and export endpoints.

Replicates the architecture of ``routers/patentes.py`` and ``routers/marcas.py``
(search with pagination, selective per-user monitoring, detail aggregation
without N+1, CSV export). The data is loaded by the ingestion pipeline
(``python -m ingestion.import_all --category desenhos_industriais``); this router
is DB-only and never calls the INPI during a request.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_permission
from app.export import rows_to_csv
from app.models import (
    Desenho,
    DesenhoAutor,
    DesenhoClassificacao,
    DesenhoConteudo,
    DesenhoDepositante,
    DesenhoDespacho,
    DesenhoFigura,
    DesenhoMonitoramento,
    DesenhoPrioridade,
    DesenhoProcurador,
)
from app.rbac import AccessContext
from app.schemas.desenhos import DesenhoDetail, DesenhoOut, PaginatedDesenhos
from app.schemas.search import (
    MonitoramentoOut,
    MonitoramentoUpdate,
    PaginatedMonitoramentos,
    Pagination,
)

router = APIRouter(prefix="/desenhos", tags=["desenhos"])


def _base_query(
    q: str | None,
    numero_inpi: str | None,
    situacao: str | None,
    data_deposito_from: str | None,
    data_deposito_to: str | None,
):
    stmt = select(Desenho)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Desenho.titulo.ilike(like))
    if numero_inpi:
        stmt = stmt.where(Desenho.numero_inpi == numero_inpi)
    if situacao:
        stmt = stmt.where(Desenho.codigo_situacao == situacao)
    if data_deposito_from:
        stmt = stmt.where(Desenho.data_deposito >= data_deposito_from)
    if data_deposito_to:
        stmt = stmt.where(Desenho.data_deposito <= data_deposito_to)
    return stmt


def _load_titulares(db: Session, codigos: list[str]) -> dict[str, list[str]]:
    if not codigos:
        return {}
    out: dict[str, list[str]] = {}
    for codigo, nome in db.execute(
        select(DesenhoDepositante.codigo_interno, DesenhoDepositante.nome)
        .where(DesenhoDepositante.codigo_interno.in_(codigos))
        .order_by(DesenhoDepositante.codigo_interno, DesenhoDepositante.nome)
    ):
        if nome:
            out.setdefault(codigo, []).append(nome)
    return out


def _load_classificacoes(db: Session, codigos: list[str]) -> dict[str, list[str]]:
    if not codigos:
        return {}
    out: dict[str, list[str]] = {}
    for codigo, locarno in db.execute(
        select(
            DesenhoClassificacao.codigo_interno,
            DesenhoClassificacao.classificacao_locarno,
        )
        .where(DesenhoClassificacao.codigo_interno.in_(codigos))
        .order_by(
            DesenhoClassificacao.codigo_interno,
            DesenhoClassificacao.classificacao_locarno,
        )
    ):
        if locarno:
            out.setdefault(codigo, []).append(locarno)
    return out


def _load_monitoramento(
    db: Session, codigos: list[str], user_id: uuid.UUID
) -> dict[str, DesenhoMonitoramento]:
    if not codigos:
        return {}
    stmt = select(DesenhoMonitoramento).where(
        DesenhoMonitoramento.codigo_interno.in_(codigos),
        DesenhoMonitoramento.user_id == user_id,
        DesenhoMonitoramento.deleted_at.is_(None),
        DesenhoMonitoramento.active.is_(True),
    )
    return {m.codigo_interno: m for m in db.execute(stmt).scalars()}


def _load_figuras(db: Session, codigos: list[str]) -> dict[str, DesenhoFigura]:
    if not codigos:
        return {}
    stmt = select(DesenhoFigura).where(DesenhoFigura.codigo_interno.in_(codigos))
    out: dict[str, DesenhoFigura] = {}
    for row in db.execute(stmt).scalars():
        out.setdefault(row.codigo_interno, row)  # first figure per process
    return out


@router.get("/search", response_model=PaginatedDesenhos)
def search_desenhos(
    q: str | None = None,
    numero_inpi: str | None = None,
    situacao: str | None = None,
    data_deposito_from: str | None = None,
    data_deposito_to: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("DESENHOS_SEARCH")),
) -> PaginatedDesenhos:
    stmt = _base_query(q, numero_inpi, situacao, data_deposito_from, data_deposito_to)
    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(Desenho.data_deposito.desc().nullslast())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    page_ids = [r.codigo_interno for r in rows]
    titulares = _load_titulares(db, page_ids)
    classificacoes = _load_classificacoes(db, page_ids)
    monitorados = _load_monitoramento(db, page_ids, ctx.user.id)
    figuras = _load_figuras(db, page_ids)

    items: list[DesenhoOut] = []
    for r in rows:
        out = DesenhoOut.model_validate(r)
        nomes = titulares.get(r.codigo_interno, [])
        out.titulares = nomes
        out.num_titulares = len(nomes)
        out.titular_principal = nomes[0] if nomes else None
        out.classificacoes = classificacoes.get(r.codigo_interno, [])
        fig = figuras.get(r.codigo_interno)
        out.tem_figura = fig is not None and fig.status == "OK"
        out.figura_status = fig.status if fig else None
        mon = monitorados.get(r.codigo_interno)
        out.monitorada = mon is not None
        out.monitoramento_id = mon.id if mon is not None else None
        items.append(out)

    return PaginatedDesenhos(
        pagination=Pagination(page=page, page_size=page_size, total=int(total)),
        items=items,
    )


@router.get("/export")
def export_desenhos(
    q: str | None = None,
    numero_inpi: str | None = None,
    situacao: str | None = None,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("DESENHOS_EXPORT")),
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
        filename="desenhos_industriais.csv",
    )


# --- Selective monitoring (declared BEFORE /{codigo_interno}) ---------------


@router.get("/monitoramento", response_model=PaginatedMonitoramentos)
def list_monitoramento(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("DESENHOS_VIEW")),
) -> PaginatedMonitoramentos:
    conditions = [
        DesenhoMonitoramento.user_id == ctx.user.id,
        DesenhoMonitoramento.deleted_at.is_(None),
        DesenhoMonitoramento.active.is_(True),
    ]
    total = db.execute(
        select(func.count(DesenhoMonitoramento.id)).where(*conditions)
    ).scalar_one()
    rows = db.execute(
        select(
            DesenhoMonitoramento,
            Desenho.titulo,
            Desenho.numero_inpi,
            Desenho.descricao_situacao,
            Desenho.data_deposito,
        )
        .outerjoin(Desenho, Desenho.codigo_interno == DesenhoMonitoramento.codigo_interno)
        .where(*conditions)
        .order_by(DesenhoMonitoramento.monitored_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items: list[MonitoramentoOut] = []
    for row, titulo, numero_inpi, situacao, data_deposito in rows:
        out = MonitoramentoOut.model_validate(row)
        out.tipo = "desenho"
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
    ctx: AccessContext = Depends(require_permission("DESENHOS_MONITOR")),
) -> MonitoramentoOut:
    desenho = db.execute(
        select(Desenho).where(Desenho.codigo_interno == codigo_interno)
    ).scalar_one_or_none()
    if desenho is None:
        raise HTTPException(status_code=404, detail="Desenho industrial não encontrado")
    row = db.execute(
        select(DesenhoMonitoramento).where(
            DesenhoMonitoramento.codigo_interno == codigo_interno,
            DesenhoMonitoramento.user_id == ctx.user.id,
        )
    ).scalar_one_or_none()
    if row is None:
        row = DesenhoMonitoramento(
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
    ctx: AccessContext = Depends(require_permission("DESENHOS_MONITOR")),
) -> dict:
    row = db.execute(
        select(DesenhoMonitoramento).where(
            DesenhoMonitoramento.codigo_interno == codigo_interno,
            DesenhoMonitoramento.user_id == ctx.user.id,
            DesenhoMonitoramento.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Monitoramento não encontrado")
    row.active = False
    row.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "Monitoramento removido."}


@router.get("/{codigo_interno}", response_model=DesenhoDetail)
def get_desenho(
    codigo_interno: str,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("DESENHOS_VIEW")),
) -> DesenhoDetail:
    desenho = db.execute(
        select(Desenho).where(Desenho.codigo_interno == codigo_interno)
    ).scalar_one_or_none()
    if desenho is None:
        raise HTTPException(status_code=404, detail="Desenho industrial não encontrado")

    depositantes = db.execute(
        select(DesenhoDepositante).where(
            DesenhoDepositante.codigo_interno == codigo_interno
        )
    ).scalars().all()
    autores = db.execute(
        select(DesenhoAutor).where(DesenhoAutor.codigo_interno == codigo_interno)
    ).scalars().all()
    procuradores = db.execute(
        select(DesenhoProcurador).where(
            DesenhoProcurador.codigo_interno == codigo_interno
        )
    ).scalars().all()
    classificacoes = db.execute(
        select(DesenhoClassificacao).where(
            DesenhoClassificacao.codigo_interno == codigo_interno
        )
    ).scalars().all()
    prioridades = db.execute(
        select(DesenhoPrioridade).where(
            DesenhoPrioridade.codigo_interno == codigo_interno
        )
    ).scalars().all()
    despachos = db.execute(
        select(DesenhoDespacho)
        .where(DesenhoDespacho.codigo_interno == codigo_interno)
        .order_by(DesenhoDespacho.data_rpi.desc().nullslast())
    ).scalars().all()
    conteudo = db.execute(
        select(DesenhoConteudo).where(DesenhoConteudo.codigo_interno == codigo_interno)
    ).scalar_one_or_none()

    detail = DesenhoDetail.model_validate(desenho)
    nomes = [d.nome for d in depositantes if d.nome]
    detail.titulares = nomes
    detail.num_titulares = len(nomes)
    detail.titular_principal = nomes[0] if nomes else None
    detail.classificacoes = [
        c.classificacao_locarno for c in classificacoes if c.classificacao_locarno
    ]
    detail.depositantes = [
        {
            "nome": d.nome,
            "cpf_cnpj": d.cpf_cnpj,
            "tipo_pessoa": d.tipo_pessoa,
            "pais": d.pais,
            "estado": d.estado,
        }
        for d in depositantes
    ]
    detail.autores = [
        {"autor": a.autor, "pais": a.pais, "estado": a.estado} for a in autores
    ]
    detail.procuradores = [
        {"procurador": p.procurador, "cpf_cnpj": p.cpf_cnpj} for p in procuradores
    ]
    detail.classificacoes_locarno = [
        {
            "classificacao_locarno": c.classificacao_locarno,
            "descricao_locarno": c.descricao_locarno,
        }
        for c in classificacoes
    ]
    detail.prioridades = [
        {
            "pais_prioridade": p.pais_prioridade,
            "numero_prioridade": p.numero_prioridade,
            "data_prioridade": p.data_prioridade,
        }
        for p in prioridades
    ]
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
    detail.conteudo = (
        {
            "titulo": conteudo.titulo,
            "campo_aplicacao": conteudo.campo_aplicacao,
            "descricao": conteudo.descricao,
        }
        if conteudo
        else None
    )
    return detail
