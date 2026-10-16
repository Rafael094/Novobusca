"""NIT F4 — R&D project endpoints (``/api/nit/projects``).

Projects, team members, funders, milestones and N:N asset links. Every reference
(asset, unity) must belong to the caller's tenant. No funding value is invented:
``amount`` is stored only when a real source provides it.
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
    Project,
    ProjectAssetLink,
    ProjectFunder,
    ProjectMember,
    ProjectMilestone,
)
from app.rbac import AccessContext
from app.routers.nit._common import (
    assert_same_tenant,
    assert_unity_scope,
    list_scope,
    scoped_tenant,
    write_tenant,
)
from app.schemas.nit_f4 import (
    AssetLinkIn,
    AssetLinkOut,
    PaginatedProjects,
    ProjectCreate,
    ProjectDetail,
    ProjectFunderIn,
    ProjectFunderOut,
    ProjectMemberIn,
    ProjectMemberOut,
    ProjectMilestoneIn,
    ProjectMilestoneOut,
    ProjectOut,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["nit"])


def _project_or_404(db: Session, ctx: AccessContext, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projeto não encontrado")
    assert_same_tenant(ctx, project.tenant_id)
    return project


def _next_project_code(db: Session, tenant_id: uuid.UUID) -> str:
    total = db.execute(
        select(func.count()).select_from(Project).where(Project.tenant_id == tenant_id)
    ).scalar_one()
    candidate = int(total) + 1
    for _ in range(10000):
        code = f"PRJ-{candidate:04d}"
        exists = db.execute(
            select(Project.id).where(Project.tenant_id == tenant_id, Project.code == code)
        ).first()
        if exists is None:
            return code
        candidate += 1
    raise HTTPException(  # pragma: no cover
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Não foi possível gerar o código do projeto",
    )


def _detail(db: Session, project: Project) -> ProjectDetail:
    detail = ProjectDetail.model_validate(project)
    detail.members = [
        ProjectMemberOut.model_validate(r)
        for r in db.execute(
            select(ProjectMember).where(ProjectMember.project_id == project.id)
        ).scalars()
    ]
    detail.funders = [
        ProjectFunderOut.model_validate(r)
        for r in db.execute(
            select(ProjectFunder).where(ProjectFunder.project_id == project.id)
        ).scalars()
    ]
    detail.milestones = [
        ProjectMilestoneOut.model_validate(r)
        for r in db.execute(
            select(ProjectMilestone)
            .where(ProjectMilestone.project_id == project.id)
            .order_by(ProjectMilestone.due_date.asc().nulls_last())
        ).scalars()
    ]
    detail.asset_links = [
        AssetLinkOut.model_validate(r)
        for r in db.execute(
            select(ProjectAssetLink).where(ProjectAssetLink.project_id == project.id)
        ).scalars()
    ]
    return detail


@router.get("", response_model=PaginatedProjects)
def list_projects(
    q: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PROJECT_VIEW")),
) -> PaginatedProjects:
    scope = list_scope(ctx)
    conditions = [Project.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(Project.tenant_id == scope)
    if status_filter:
        conditions.append(Project.status == status_filter)
    if q:
        like = f"%{q}%"
        conditions.append(or_(Project.title.ilike(like), Project.code.ilike(like)))
    total = db.execute(
        select(func.count()).select_from(Project).where(*conditions)
    ).scalar_one()
    rows = (
        db.execute(
            select(Project)
            .where(*conditions)
            .order_by(Project.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return PaginatedProjects(
        items=[ProjectOut.model_validate(r) for r in rows],
        page=page,
        page_size=page_size,
        total=int(total),
    )


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PROJECT_CREATE")),
    meta: dict = Depends(client_meta),
) -> ProjectDetail:
    tenant = write_tenant(ctx, None)
    assert_unity_scope(db, ctx, tenant, payload.unity_id)
    project = Project(
        tenant_id=tenant,
        code=_next_project_code(db, tenant),
        title=payload.title,
        description=payload.description,
        objective=payload.objective,
        technology_area=payload.technology_area,
        status=payload.status,
        start_date=payload.start_date,
        end_date=payload.end_date,
        unity_id=payload.unity_id,
        coordinator_id=payload.coordinator_id or ctx.user.id,
        notes=payload.notes,
        active=True,
    )
    db.add(project)
    record_audit(
        db,
        action="NIT_PROJECT_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="project",
        resource_id=project.id,
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(project)
    return _detail(db, project)


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PROJECT_VIEW")),
) -> ProjectDetail:
    return _detail(db, _project_or_404(db, ctx, project_id))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PROJECT_MANAGE")),
) -> ProjectOut:
    project = _project_or_404(db, ctx, project_id)
    data = payload.model_dump(exclude_unset=True)
    if "unity_id" in data:
        assert_unity_scope(db, ctx, project.tenant_id, data["unity_id"])
    for field, value in data.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return ProjectOut.model_validate(project)


@router.delete("/{project_id}")
def delete_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PROJECT_MANAGE")),
) -> dict:
    project = _project_or_404(db, ctx, project_id)
    from app.mixins import utcnow

    project.deleted_at = utcnow()
    project.active = False
    db.commit()
    return {"status": "deleted", "id": str(project.id)}


# --- Members ----------------------------------------------------------------
@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    project_id: uuid.UUID,
    payload: ProjectMemberIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PROJECT_MANAGE")),
) -> ProjectMemberOut:
    project = _project_or_404(db, ctx, project_id)
    member = ProjectMember(
        tenant_id=project.tenant_id, project_id=project.id, **payload.model_dump()
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return ProjectMemberOut.model_validate(member)


# --- Funders ----------------------------------------------------------------
@router.post(
    "/{project_id}/funders",
    response_model=ProjectFunderOut,
    status_code=status.HTTP_201_CREATED,
)
def add_funder(
    project_id: uuid.UUID,
    payload: ProjectFunderIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PROJECT_MANAGE")),
) -> ProjectFunderOut:
    project = _project_or_404(db, ctx, project_id)
    funder = ProjectFunder(
        tenant_id=project.tenant_id, project_id=project.id, **payload.model_dump()
    )
    db.add(funder)
    db.commit()
    db.refresh(funder)
    return ProjectFunderOut.model_validate(funder)


# --- Milestones -------------------------------------------------------------
@router.post(
    "/{project_id}/milestones",
    response_model=ProjectMilestoneOut,
    status_code=status.HTTP_201_CREATED,
)
def add_milestone(
    project_id: uuid.UUID,
    payload: ProjectMilestoneIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PROJECT_MANAGE")),
) -> ProjectMilestoneOut:
    project = _project_or_404(db, ctx, project_id)
    milestone = ProjectMilestone(
        tenant_id=project.tenant_id, project_id=project.id, **payload.model_dump()
    )
    db.add(milestone)
    db.commit()
    db.refresh(milestone)
    return ProjectMilestoneOut.model_validate(milestone)


@router.patch("/milestones/{milestone_id}", response_model=ProjectMilestoneOut)
def update_milestone(
    milestone_id: uuid.UUID,
    payload: ProjectMilestoneIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PROJECT_MANAGE")),
) -> ProjectMilestoneOut:
    milestone = db.get(ProjectMilestone, milestone_id)
    if milestone is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Marco não encontrado"
        )
    assert_same_tenant(ctx, milestone.tenant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(milestone, field, value)
    if milestone.status == "DONE" and milestone.completed_at is None:
        milestone.completed_at = date.today()
    db.commit()
    db.refresh(milestone)
    return ProjectMilestoneOut.model_validate(milestone)


# --- Asset links ------------------------------------------------------------
@router.post(
    "/{project_id}/assets",
    response_model=AssetLinkOut,
    status_code=status.HTTP_201_CREATED,
)
def link_asset(
    project_id: uuid.UUID,
    payload: AssetLinkIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_PROJECT_MANAGE")),
) -> AssetLinkOut:
    project = _project_or_404(db, ctx, project_id)
    asset = db.get(IPAsset, payload.asset_id)
    if asset is None or asset.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ativo inválido"
        )
    assert_same_tenant(ctx, asset.tenant_id)

    existing = db.execute(
        select(ProjectAssetLink).where(
            ProjectAssetLink.project_id == project.id,
            ProjectAssetLink.asset_id == asset.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ativo já vinculado ao projeto"
        )

    link = ProjectAssetLink(
        tenant_id=project.tenant_id,
        project_id=project.id,
        asset_id=asset.id,
        relation=payload.relation,
        notes=payload.notes,
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return AssetLinkOut.model_validate(link)


