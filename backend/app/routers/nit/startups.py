"""NIT F4 — startup / spin-off and incubation endpoints (``/api/nit/startups``).

Being linked to an asset does NOT make a startup its owner; ownership is never
inferred. Incubation programs and their participations/stages are tenant-scoped.
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models.nit import IPAsset
from app.models.nit_f4 import (
    IncubationParticipation,
    IncubationProgram,
    IncubationStage,
    Project,
    Startup,
    StartupMember,
)
from app.rbac import AccessContext
from app.routers.nit._common import (
    assert_same_tenant,
    list_scope,
    scoped_tenant,
    write_tenant,
)
from app.schemas.nit_f4 import (
    PaginatedStartups,
    ParticipationCreate,
    ParticipationDetail,
    ParticipationOut,
    ProgramCreate,
    ProgramOut,
    StageCreate,
    StageOut,
    StartupCreate,
    StartupMemberIn,
    StartupMemberOut,
    StartupOut,
    StartupUpdate,
)

router = APIRouter(prefix="/startups", tags=["nit"])


def _startup_or_404(db: Session, ctx: AccessContext, startup_id: uuid.UUID) -> Startup:
    startup = db.get(Startup, startup_id)
    if startup is None or startup.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Startup não encontrada")
    assert_same_tenant(ctx, startup.tenant_id)
    return startup


def _next_code(db: Session, model, tenant_id: uuid.UUID, prefix: str) -> str:
    total = db.execute(
        select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
    ).scalar_one()
    candidate = int(total) + 1
    for _ in range(10000):
        code = f"{prefix}-{candidate:04d}"
        exists = db.execute(
            select(model.id).where(model.tenant_id == tenant_id, model.code == code)
        ).first()
        if exists is None:
            return code
        candidate += 1
    raise HTTPException(  # pragma: no cover
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Não foi possível gerar o código sequencial",
    )


def _member_list(db: Session, startup: Startup) -> list[StartupMemberOut]:
    return [
        StartupMemberOut.model_validate(r)
        for r in db.execute(
            select(StartupMember).where(StartupMember.startup_id == startup.id)
        ).scalars()
    ]


@router.get("", response_model=PaginatedStartups)
def list_startups(
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_STARTUP_VIEW")),
) -> PaginatedStartups:
    scope = list_scope(ctx)
    conditions = [Startup.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(Startup.tenant_id == scope)
    if status_filter:
        conditions.append(Startup.status == status_filter)
    if q:
        like = f"%{q}%"
        conditions.append(or_(Startup.name.ilike(like), Startup.code.ilike(like)))
    total = db.execute(
        select(func.count()).select_from(Startup).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(Startup)
            .where(*conditions)
            .order_by(Startup.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedStartups(
        items=[StartupOut.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total),
    )


@router.post("", response_model=StartupOut, status_code=status.HTTP_201_CREATED)
def create_startup(
    payload: StartupCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_STARTUP_MANAGE")),
    meta: dict = Depends(client_meta),
) -> StartupOut:
    tenant = write_tenant(ctx, None)
    if payload.project_id is not None:
        project = db.get(Project, payload.project_id)
        if project is None or project.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Projeto inválido"
            )
        assert_same_tenant(ctx, project.tenant_id)
    if payload.asset_id is not None:
        asset = db.get(IPAsset, payload.asset_id)
        if asset is None or asset.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ativo inválido"
            )
        assert_same_tenant(ctx, asset.tenant_id)

    startup = Startup(
        tenant_id=tenant,
        code=_next_code(db, Startup, tenant, "STP"),
        **payload.model_dump(),
        active=True,
    )
    db.add(startup)
    record_audit(
        db,
        action="NIT_STARTUP_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="startup",
        resource_id=startup.id,
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(startup)
    return StartupOut.model_validate(startup)


@router.get("/{startup_id}", response_model=StartupOut)
def get_startup(
    startup_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_STARTUP_VIEW")),
) -> StartupOut:
    return StartupOut.model_validate(_startup_or_404(db, ctx, startup_id))


@router.patch("/{startup_id}", response_model=StartupOut)
def update_startup(
    startup_id: uuid.UUID,
    payload: StartupUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_STARTUP_MANAGE")),
) -> StartupOut:
    startup = _startup_or_404(db, ctx, startup_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(startup, field, value)
    db.commit()
    db.refresh(startup)
    return StartupOut.model_validate(startup)


@router.get("/{startup_id}/members", response_model=list[StartupMemberOut])
def list_members(
    startup_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_STARTUP_VIEW")),
) -> list[StartupMemberOut]:
    return _member_list(db, _startup_or_404(db, ctx, startup_id))


@router.post(
    "/{startup_id}/members",
    response_model=StartupMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    startup_id: uuid.UUID,
    payload: StartupMemberIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_STARTUP_MANAGE")),
) -> StartupMemberOut:
    startup = _startup_or_404(db, ctx, startup_id)
    member = StartupMember(
        tenant_id=startup.tenant_id, startup_id=startup.id, **payload.model_dump()
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return StartupMemberOut.model_validate(member)


# --- Incubation programs ----------------------------------------------------
@router.get("/programs/list", response_model=list[ProgramOut])
def list_programs(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_STARTUP_VIEW")),
) -> list[ProgramOut]:
    scope = list_scope(ctx)
    conditions = [IncubationProgram.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(IncubationProgram.tenant_id == scope)
    rows = db.execute(
        select(IncubationProgram).where(*conditions).order_by(IncubationProgram.name)
    ).scalars()
    return [ProgramOut.model_validate(r) for r in rows]


@router.post(
    "/programs/list", response_model=ProgramOut, status_code=status.HTTP_201_CREATED
)
def create_program(
    payload: ProgramCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_STARTUP_MANAGE")),
) -> ProgramOut:
    tenant = write_tenant(ctx, None)
    program = IncubationProgram(
        tenant_id=tenant,
        code=_next_code(db, IncubationProgram, tenant, "INC"),
        **payload.model_dump(),
        active=True,
    )
    db.add(program)
    db.commit()
    db.refresh(program)
    return ProgramOut.model_validate(program)


@router.post(
    "/programs/list/{program_id}/participations",
    response_model=ParticipationOut,
    status_code=status.HTTP_201_CREATED,
)
def add_participation(
    program_id: uuid.UUID,
    payload: ParticipationCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_STARTUP_MANAGE")),
) -> ParticipationOut:
    program = db.get(IncubationProgram, program_id)
    if program is None or program.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Programa não encontrado"
        )
    assert_same_tenant(ctx, program.tenant_id)
    startup = _startup_or_404(db, ctx, payload.startup_id)

    existing = db.execute(
        select(IncubationParticipation).where(
            IncubationParticipation.program_id == program.id,
            IncubationParticipation.startup_id == startup.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Startup já participa deste programa",
        )

    participation = IncubationParticipation(
        tenant_id=program.tenant_id,
        program_id=program.id,
        startup_id=startup.id,
        entry_date=payload.entry_date or date.today(),
        notes=payload.notes,
    )
    db.add(participation)
    # Marking the startup as incubated is a convenience flag, not ownership.
    startup.status = "INCUBATED"
    db.commit()
    db.refresh(participation)
    return ParticipationOut.model_validate(participation)


@router.get(
    "/participations/{participation_id}", response_model=ParticipationDetail
)
def get_participation(
    participation_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_STARTUP_VIEW")),
) -> ParticipationDetail:
    participation = db.get(IncubationParticipation, participation_id)
    if participation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Participação não encontrada"
        )
    assert_same_tenant(ctx, participation.tenant_id)
    detail = ParticipationDetail.model_validate(participation)
    detail.stages = [
        StageOut.model_validate(r)
        for r in db.execute(
            select(IncubationStage).where(
                IncubationStage.participation_id == participation.id
            )
        ).scalars()
    ]
    return detail


@router.post(
    "/participations/{participation_id}/stages",
    response_model=StageOut,
    status_code=status.HTTP_201_CREATED,
)
def add_stage(
    participation_id: uuid.UUID,
    payload: StageCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_STARTUP_MANAGE")),
) -> StageOut:
    participation = db.get(IncubationParticipation, participation_id)
    if participation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Participação não encontrada"
        )
    assert_same_tenant(ctx, participation.tenant_id)
    stage = IncubationStage(
        tenant_id=participation.tenant_id,
        participation_id=participation.id,
        **payload.model_dump(),
    )
    if stage.status == "COMPLETED" and stage.completed_at is None:
        stage.completed_at = date.today()
    db.add(stage)
    db.commit()
    db.refresh(stage)
    return StageOut.model_validate(stage)


