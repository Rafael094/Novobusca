"""Marcas (trademark) search, detail and export endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import require_permission
from app.export import rows_to_csv
from app.models import (
    Marca,
    MarcaClassificacaoNacional,
    MarcaClassificacaoNice,
    MarcaClassificacaoViena,
    MarcaDepositante,
    MarcaDespacho,
    MarcaLogo,
    MarcaMonitoramento,
    MarcaPepiSync,
    MarcaPeticao,
)
from app.rbac import AccessContext
from app.schemas.search import (
    MarcaClassificacao,
    MarcaDetail,
    MarcaOut,
    MonitoramentoOut,
    MonitoramentoUpdate,
    PaginatedMarcas,
    PaginatedMonitoramentos,
    Pagination,
)
from app.services.marca_logos import resolve_logo_file

router = APIRouter(prefix="/marcas", tags=["marcas"])


def _base_query(
    q: str | None,
    numero_inpi: str | None,
    situacao: str | None,
    data_deposito_from: str | None,
    data_deposito_to: str | None,
    match_mode: str = "exact",
):
    stmt = select(Marca)
    if q:
        # Search only the brand name (elemento_nominativo). The other fields
        # (apresentacao / numero_inpi) are separate dimensions and must NOT be
        # OR-ed into the name match — see SPIKE_BUSCA_MARCAS_INPI_VS_INTELLIINPI.
        if match_mode == "exact":
            # Exact, case- and accent-insensitive match; uses the functional
            # btree index ix_marcas_elemento_nominativo_fold (fold(...) = fold(...)).
            stmt = stmt.where(
                func.fold(Marca.elemento_nominativo) == func.fold(q)
            )
        elif match_mode == "prefix":
            stmt = stmt.where(
                func.fold(Marca.elemento_nominativo).like(
                    func.fold(q) + "%"
                )
            )
        else:  # contains
            stmt = stmt.where(Marca.elemento_nominativo.ilike(f"%{q}%"))
    if numero_inpi:
        stmt = stmt.where(Marca.numero_inpi == numero_inpi)
    if situacao:
        stmt = stmt.where(Marca.codigo_situacao == situacao)
    if data_deposito_from:
        stmt = stmt.where(Marca.data_deposito >= data_deposito_from)
    if data_deposito_to:
        stmt = stmt.where(Marca.data_deposito <= data_deposito_to)
    return stmt


def _load_titulares(db: Session, codigos: list[str]) -> dict[str, list[str]]:
    """Return {codigo_interno: [nome, ...]} for the given page's marcas.

    A single aggregated query restricted to the page ids — no N+1. Names are
    ordered for stable presentation; ``None``/blank names are skipped.
    """
    if not codigos:
        return {}
    stmt = (
        select(
            MarcaDepositante.codigo_interno,
            MarcaDepositante.nome,
        )
        .where(MarcaDepositante.codigo_interno.in_(codigos))
        .order_by(MarcaDepositante.codigo_interno, MarcaDepositante.nome)
    )
    out: dict[str, list[str]] = {}
    for codigo, nome in db.execute(stmt):
        if nome:
            out.setdefault(codigo, []).append(nome)
    return out


def _load_classificacoes(
    db: Session, codigos: list[str]
) -> dict[str, list[MarcaClassificacao]]:
    """Return {codigo_interno: [MarcaClassificacao, ...]} for the page's marcas.

    Three aggregated queries restricted to the page ids (fixed count, no N+1).
    Descriptions are only included when actually present in the local data —
    never invented.
    """
    if not codigos:
        return {}
    out: dict[str, list[MarcaClassificacao]] = {}

    nice = db.execute(
        select(
            MarcaClassificacaoNice.codigo_interno,
            MarcaClassificacaoNice.classe_nice,
            MarcaClassificacaoNice.edicao_nice,
            MarcaClassificacaoNice.especificacao,
        )
        .where(MarcaClassificacaoNice.codigo_interno.in_(codigos))
        .order_by(MarcaClassificacaoNice.codigo_interno, MarcaClassificacaoNice.classe_nice)
    )
    for codigo, classe_nice, edicao, espec in nice:
        if not classe_nice:
            continue
        label = (
            f"NCL({edicao}) {classe_nice}" if edicao else f"NCL {classe_nice}"
        )
        out.setdefault(codigo, []).append(
            MarcaClassificacao(
                tipo="nice", codigo=label, descricao=espec or None
            )
        )

    nacional = db.execute(
        select(
            MarcaClassificacaoNacional.codigo_interno,
            MarcaClassificacaoNacional.classe,
            MarcaClassificacaoNacional.especificacao,
        )
        .where(MarcaClassificacaoNacional.codigo_interno.in_(codigos))
        .order_by(
            MarcaClassificacaoNacional.codigo_interno,
            MarcaClassificacaoNacional.classe,
        )
    )
    for codigo, classe, espec in nacional:
        if not classe:
            continue
        out.setdefault(codigo, []).append(
            MarcaClassificacao(tipo="nacional", codigo=classe, descricao=espec or None)
        )

    viena = db.execute(
        select(
            MarcaClassificacaoViena.codigo_interno,
            MarcaClassificacaoViena.simbolo,
            MarcaClassificacaoViena.classificacao_viena,
        )
        .where(MarcaClassificacaoViena.codigo_interno.in_(codigos))
        .order_by(
            MarcaClassificacaoViena.codigo_interno,
            MarcaClassificacaoViena.simbolo,
        )
    )
    for codigo, simbolo, classificacao in viena:
        if not simbolo:
            continue
        out.setdefault(codigo, []).append(
            MarcaClassificacao(
                tipo="viena", codigo=simbolo, descricao=classificacao or None
            )
        )
    return out


def _load_monitoramento(
    db: Session, codigos: list[str], user_id: uuid.UUID
) -> dict[str, MarcaMonitoramento]:
    """Return the current user's active monitoring rows for the page's marcas."""
    if not codigos:
        return {}
    stmt = select(MarcaMonitoramento).where(
        MarcaMonitoramento.codigo_interno.in_(codigos),
        MarcaMonitoramento.user_id == user_id,
        MarcaMonitoramento.deleted_at.is_(None),
        MarcaMonitoramento.active.is_(True),
    )
    return {m.codigo_interno: m for m in db.execute(stmt).scalars()}


# Window (in days) under which a still-valid marca is flagged as "expiring soon".
VENCIMENTO_BREVE_DIAS = 180


def _vencimento_status(
    data_vigencia: date | None, hoje: date | None = None
) -> tuple[int | None, bool, bool]:
    """Return ``(dias_para_vencer, vencido, vence_em_breve)`` for a marca.

    ``dias_para_vencer`` is negative once past the vigência date and ``None``
    when there is no vigência recorded. ``vence_em_breve`` marks still-valid
    marcas whose vigência falls within ``VENCIMENTO_BREVE_DIAS``.
    """
    if data_vigencia is None:
        return None, False, False
    hoje = hoje or datetime.now(timezone.utc).date()
    dias = (data_vigencia - hoje).days
    vencido = dias < 0
    return dias, vencido, (not vencido and dias <= VENCIMENTO_BREVE_DIAS)


def _load_despacho_agg(
    db: Session, codigos: list[str]
) -> dict[str, tuple[int, date | None, str | None]]:
    """Return {codigo: (total, data_ultimo, descricao_ultimo)} for the page.

    A single aggregated query (fixed cost, no N+1). The "último despacho" is the
    row with the most recent ``data_rpi`` (ties broken by RPI number).
    """
    if not codigos:
        return {}
    out: dict[str, tuple[int, date | None, str | None]] = {}
    totals = db.execute(
        select(MarcaDespacho.codigo_interno, func.count(MarcaDespacho.id))
        .where(MarcaDespacho.codigo_interno.in_(codigos))
        .group_by(MarcaDespacho.codigo_interno)
    ).all()
    for codigo, total in totals:
        out[codigo] = (int(total), None, None)

    # Latest despacho per marca: ordered so the first row seen per code wins.
    latest = db.execute(
        select(
            MarcaDespacho.codigo_interno,
            MarcaDespacho.data_rpi,
            MarcaDespacho.descricao_despacho,
        )
        .where(MarcaDespacho.codigo_interno.in_(codigos))
        .order_by(
            MarcaDespacho.codigo_interno,
            MarcaDespacho.data_rpi.desc().nullslast(),
            MarcaDespacho.numero_rpi.desc().nullslast(),
        )
    ).all()
    seen: set[str] = set()
    for codigo, data_rpi, descricao in latest:
        if codigo in seen:
            continue
        seen.add(codigo)
        total = out.get(codigo, (0, None, None))[0]
        out[codigo] = (total, data_rpi, descricao)
    return out


def _load_logos(db: Session, codigos: list[str]) -> dict[str, MarcaLogo]:
    """Return {codigo: MarcaLogo} for the page (single query, no N+1)."""
    if not codigos:
        return {}
    stmt = select(MarcaLogo).where(MarcaLogo.codigo_interno.in_(codigos))
    return {row.codigo_interno: row for row in db.execute(stmt).scalars()}


def _load_logo(db: Session, codigo_interno: str) -> MarcaLogo | None:
    """Return the *stored* logo row for a marca (DB-only, no INPI call).

    Logotipos are downloaded by the offline worker (``python -m
    ingestion.logos``); the API never fetches them during a request. When the
    image is absent the caller degrades to a placeholder.
    """
    return db.execute(
        select(MarcaLogo).where(MarcaLogo.codigo_interno == codigo_interno)
    ).scalar_one_or_none()


@router.get("/search", response_model=PaginatedMarcas)
def search_marcas(
    q: str | None = None,
    numero_inpi: str | None = None,
    situacao: str | None = None,
    data_deposito_from: str | None = None,
    data_deposito_to: str | None = None,
    match_mode: Literal["exact", "prefix", "contains"] = "exact",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("MARCAS_SEARCH")),
) -> PaginatedMarcas:
    stmt = _base_query(
        q, numero_inpi, situacao, data_deposito_from, data_deposito_to, match_mode
    )
    total = db.execute(
        select(func.count()).select_from(stmt.subquery())
    ).scalar_one()
    rows = (
        db.execute(
            stmt.order_by(Marca.data_deposito.desc().nullslast())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    # Aggregate relations for the current page only (fixed number of queries,
    # keyed by codigo_interno — joins never multiply the result rows).
    page_ids = [r.codigo_interno for r in rows]
    titulares = _load_titulares(db, page_ids)
    classificacoes = _load_classificacoes(db, page_ids)
    monitorados = _load_monitoramento(db, page_ids, ctx.user.id)

    items: list[MarcaOut] = []
    for r in rows:
        out = MarcaOut.model_validate(r)
        nomes = titulares.get(r.codigo_interno, [])
        out.titulares = nomes
        out.num_titulares = len(nomes)
        out.titular_principal = nomes[0] if nomes else None
        out.classificacoes = classificacoes.get(r.codigo_interno, [])
        mon = monitorados.get(r.codigo_interno)
        out.monitorada = mon is not None
        out.monitoramento_id = mon.id if mon is not None else None
        items.append(out)

    return PaginatedMarcas(
        pagination=Pagination(page=page, page_size=page_size, total=int(total)),
        items=items,
    )



@router.get("/export")
def export_marcas(
    q: str | None = None,
    numero_inpi: str | None = None,
    situacao: str | None = None,
    match_mode: Literal["exact", "prefix", "contains"] = "exact",
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("MARCAS_EXPORT")),
) -> StreamingResponse:
    stmt = _base_query(q, numero_inpi, situacao, None, None, match_mode).limit(50000)
    rows = db.execute(stmt).scalars().all()
    data = [
        {
            "codigo_interno": r.codigo_interno,
            "numero_inpi": r.numero_inpi,
            "data_deposito": r.data_deposito,
            "data_concessao": r.data_concessao,
            "elemento_nominativo": r.elemento_nominativo,
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
            "data_deposito",
            "data_concessao",
            "elemento_nominativo",
            "codigo_situacao",
            "descricao_situacao",
        ],
        filename="marcas.csv",
    )


# --- Selective monitoring (section 4) ---------------------------------------
# Monitoring is NEVER global/automatic: a row exists only for the specific
# marca the current user chose to watch. The tenant is derived from the token.


@router.get("/monitoramento", response_model=PaginatedMonitoramentos)
def list_monitoramento(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("MARCAS_VIEW")),
) -> PaginatedMonitoramentos:
    """List the current user's monitored marcas (their own watch list only).

    Each row is enriched with *all* display data of the underlying marca
    (datas de publicação/concessão/vigência, apresentação/natureza, titulares,
    agregado de despachos and the vencimento status) so the monitoring screen
    shows everything without an extra request per row.
    """
    conditions = [
        MarcaMonitoramento.user_id == ctx.user.id,
        MarcaMonitoramento.deleted_at.is_(None),
        MarcaMonitoramento.active.is_(True),
    ]
    total = db.execute(
        select(func.count(MarcaMonitoramento.id)).where(*conditions)
    ).scalar_one()
    # Join the marca biblio row so the watch list can display the name/number
    # without an extra request per row (outer join: the marca may be absent).
    rows = db.execute(
        select(
            MarcaMonitoramento,
            Marca.elemento_nominativo,
            Marca.numero_inpi,
            Marca.descricao_situacao,
            Marca.data_deposito,
            Marca.data_publicacao,
            Marca.data_concessao,
            Marca.data_vigencia,
            Marca.descricao_apresentacao,
            Marca.descricao_natureza,
        )
        .outerjoin(Marca, Marca.codigo_interno == MarcaMonitoramento.codigo_interno)
        .where(*conditions)
        .order_by(MarcaMonitoramento.monitored_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    # Aggregate the relations for the current page only (fixed number of
    # queries keyed by codigo_interno — no N+1).
    page_ids = [r[0].codigo_interno for r in rows]
    titulares = _load_titulares(db, page_ids)
    despachos = _load_despacho_agg(db, page_ids)
    logos = _load_logos(db, page_ids)

    items: list[MonitoramentoOut] = []
    for (
        row,
        nominativo,
        numero_inpi,
        situacao,
        data_deposito,
        data_publicacao,
        data_concessao,
        data_vigencia,
        descricao_apresentacao,
        descricao_natureza,
    ) in rows:
        out = MonitoramentoOut.model_validate(row)
        out.tipo = "marca"
        out.titulo = nominativo
        out.numero_inpi = numero_inpi
        out.situacao = situacao
        out.data_deposito = data_deposito
        out.data_publicacao = data_publicacao
        out.data_concessao = data_concessao
        out.data_vigencia = data_vigencia
        out.descricao_apresentacao = descricao_apresentacao
        out.descricao_natureza = descricao_natureza

        nomes = titulares.get(row.codigo_interno, [])
        out.titulares = nomes
        out.num_titulares = len(nomes)
        out.titular_principal = nomes[0] if nomes else None

        total_desp, data_ultimo, desc_ultimo = despachos.get(
            row.codigo_interno, (0, None, None)
        )
        out.total_despachos = total_desp
        out.data_ultimo_despacho = data_ultimo
        out.ultimo_despacho = desc_ultimo

        dias, vencido, breve = _vencimento_status(data_vigencia)
        out.dias_para_vencer = dias
        out.vencido = vencido
        out.vence_em_breve = breve

        # Logo: DB-only. The offline worker (``ingestion.logos``) downloads the
        # images; the API just reflects what is stored and shows a placeholder
        # whenever the image is absent.
        logo = logos.get(row.codigo_interno)
        if logo is None and row.codigo_interno:
            logo = _load_logo(db, row.codigo_interno)
        out.tem_logo = bool(logo and logo.status == "OK")
        out.logo_status = logo.status if logo else None

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
    ctx: AccessContext = Depends(require_permission("MARCAS_MONITOR")),
) -> MonitoramentoOut:
    """Activate/deactivate monitoring for ONE marca (selective, per user)."""
    marca = db.execute(
        select(Marca).where(Marca.codigo_interno == codigo_interno)
    ).scalar_one_or_none()
    if marca is None:
        raise HTTPException(status_code=404, detail="Marca não encontrada")

    row = db.execute(
        select(MarcaMonitoramento).where(
            MarcaMonitoramento.codigo_interno == codigo_interno,
            MarcaMonitoramento.user_id == ctx.user.id,
        )
    ).scalar_one_or_none()
    if row is None:
        row = MarcaMonitoramento(
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
    ctx: AccessContext = Depends(require_permission("MARCAS_MONITOR")),
) -> dict:
    """Stop monitoring this marca entirely (soft delete of the watch row)."""
    row = db.execute(
        select(MarcaMonitoramento).where(
            MarcaMonitoramento.codigo_interno == codigo_interno,
            MarcaMonitoramento.user_id == ctx.user.id,
            MarcaMonitoramento.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Monitoramento não encontrado")
    row.active = False
    row.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "Monitoramento removido."}


@router.get("/{codigo_interno}", response_model=MarcaDetail)
def get_marca(
    codigo_interno: str,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("MARCAS_VIEW")),
) -> MarcaDetail:
    marca = db.execute(
        select(Marca).where(Marca.codigo_interno == codigo_interno)
    ).scalar_one_or_none()
    if marca is None:
        raise HTTPException(status_code=404, detail="Marca não encontrada")

    depositantes = db.execute(
        select(MarcaDepositante).where(
            MarcaDepositante.codigo_interno == codigo_interno
        )
    ).scalars().all()
    cn = db.execute(
        select(MarcaClassificacaoNacional).where(
            MarcaClassificacaoNacional.codigo_interno == codigo_interno
        )
    ).scalars().all()
    nice = db.execute(
        select(MarcaClassificacaoNice).where(
            MarcaClassificacaoNice.codigo_interno == codigo_interno
        )
    ).scalars().all()
    viena = db.execute(
        select(MarcaClassificacaoViena).where(
            MarcaClassificacaoViena.codigo_interno == codigo_interno
        )
    ).scalars().all()
    despachos = db.execute(
        select(MarcaDespacho)
        .where(MarcaDespacho.codigo_interno == codigo_interno)
        .order_by(MarcaDespacho.data_rpi.desc().nullslast())
    ).scalars().all()
    logo = db.execute(
        select(MarcaLogo).where(MarcaLogo.codigo_interno == codigo_interno)
    ).scalar_one_or_none()
    peticoes = db.execute(
        select(MarcaPeticao)
        .where(MarcaPeticao.codigo_interno == codigo_interno)
        .order_by(
            MarcaPeticao.data_protocolo.desc().nullslast(),
            MarcaPeticao.protocolo.desc(),
        )
    ).scalars().all()
    pepi_sync = db.execute(
        select(MarcaPepiSync).where(MarcaPepiSync.codigo_interno == codigo_interno)
    ).scalar_one_or_none()

    # Build from explicit scalar columns (the ORM ``depositantes`` relationship
    # returns model objects that cannot satisfy the ``list[dict]`` schema field).
    detail = MarcaDetail.model_validate(
        {
            "id": marca.id,
            "codigo_interno": marca.codigo_interno,
            "numero_inpi": marca.numero_inpi,
            "data_deposito": marca.data_deposito,
            "data_concessao": marca.data_concessao,
            "descricao_apresentacao": marca.descricao_apresentacao,
            "descricao_natureza": marca.descricao_natureza,
            "elemento_nominativo": marca.elemento_nominativo,
            "codigo_situacao": marca.codigo_situacao,
            "descricao_situacao": marca.descricao_situacao,
            "data_publicacao": marca.data_publicacao,
            "data_vigencia": marca.data_vigencia,
            "traducao": marca.traducao,
            "apostila": marca.apostila,
        }
    )
    detail.depositantes = [
        {
            "nome": d.nome,
            "cnpj_cpf_titular": d.cnpj_cpf_titular,
            "tipo_pfpj_titular": d.tipo_pfpj_titular,
            "pais": d.pais,
            "estado": d.estado,
        }
        for d in depositantes
    ]
    # Representantes legais / procuradores — sourced from the depositante rows
    # (``marcas_depositantes``). De-duplicated by (name, cpf/cnpj) so a single
    # procuração shared by several titulares is listed once, preserving order.
    seen_repr: set[tuple[str, str]] = set()
    representantes: list[dict] = []
    for d in depositantes:
        nome_repr = (d.nome_representante_legal or "").strip()
        if not nome_repr:
            continue
        chave = (nome_repr, (d.cnpj_cpf_representante_legal or "").strip())
        if chave in seen_repr:
            continue
        seen_repr.add(chave)
        representantes.append(
            {
                "nome": nome_repr,
                "cnpj_cpf": d.cnpj_cpf_representante_legal,
                "tipo_pfpj": d.tipo_pfpj_representante_legal,
            }
        )
    detail.representantes_legais = representantes
    # Same derived shape as /search (source of truth = titulares list).
    nomes = [d.nome for d in depositantes if d.nome]
    detail.titulares = nomes
    detail.num_titulares = len(nomes)
    detail.titular_principal = nomes[0] if nomes else None
    detail.classificacoes = (
        _load_classificacoes(db, [codigo_interno]).get(codigo_interno, [])
    )
    detail.classificacoes_nacionais = [
        {
            "classe": c.classe,
            "especificacao": c.especificacao,
        }
        for c in cn
    ]
    detail.classificacoes_nice = [
        {
            "edicao_nice": n.edicao_nice,
            "classe_nice": n.classe_nice,
            "especificacao": n.especificacao,
        }
        for n in nice
    ]
    detail.classificacoes_viena = [
        {
            "simbolo": v.simbolo,
            "classificacao_viena": v.classificacao_viena,
            "revisao_viena": v.revisao_viena,
        }
        for v in viena
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
    detail.logo_status = logo.status if logo else None
    detail.tem_logo = bool(logo and logo.status == "OK")
    detail.peticoes = [
        {
            "protocolo": p.protocolo,
            "data_protocolo": p.data_protocolo,
            "codigo_servico": p.codigo_servico,
            "descricao_servico": p.descricao_servico,
            "cliente": p.cliente,
            "pagamento_conciliado": p.pagamento_conciliado,
            "banco_codigo": p.banco_codigo,
            "banco_nome": p.banco_nome,
            "data_pagamento": p.data_pagamento,
            "valor_pagamento": (
                float(p.valor_pagamento) if p.valor_pagamento is not None else None
            ),
            "delivery": p.delivery,
            "data_delivery": p.data_delivery,
            "tem_imagem": p.tem_imagem,
        }
        for p in peticoes
    ]
    detail.peticoes_status = pepi_sync.status if pepi_sync else None
    detail.peticoes_sincronizado_em = pepi_sync.sincronizado_em if pepi_sync else None

    # Enfileira a marca para o worker do pePI quando ainda não há linha de sync.
    # É um best-effort (não bloqueia a resposta e nunca chama o INPI aqui): o
    # worker drena a fila PENDING antes do lote em massa. A resposta já reflete o
    # enfileiramento (status "PENDING") para a UI mostrar "sincronizando…".
    if pepi_sync is None:
        try:
            db.execute(
                pg_insert(MarcaPepiSync)
                .values(codigo_interno=codigo_interno, status="PENDING")
                .on_conflict_do_nothing(index_elements=["codigo_interno"])
            )
            db.commit()
            detail.peticoes_status = "PENDING"
        except Exception:  # noqa: BLE001 - enfileirar é opcional, nunca falha a leitura
            db.rollback()
    return detail


@router.get("/{codigo_interno}/logo")
def get_marca_logo(
    codigo_interno: str,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("MARCAS_VIEW")),
) -> FileResponse:
    """Stream the stored logotipo for a marca (DB-only, no INPI call).

    The images are downloaded by the offline worker (``python -m
    ingestion.logos``); this endpoint only serves what is already stored in
    ``marcas_logos``/``data/raw/marcas/logos/...``. Returns 404 when the image
    was never downloaded (or is a placeholder / unrecoverable error).
    """
    resolved = resolve_logo_file(db, codigo_interno, allow_fetch=False)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Logotipo não disponível")
    path, mime = resolved

    return FileResponse(
        path,
        media_type=mime,
        filename=f"{codigo_interno}{path.suffix or '.jpg'}",
    )
