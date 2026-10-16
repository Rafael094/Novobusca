"""NIT F2 — committee endpoints (``/api/nit/committees``).

Committees, members, meetings, agenda items, votes and decisions. Every access is
tenant-scoped; decisions are validated by ``services/committee.py`` (quorum and
majority) and never set by a client without authority.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import record_audit
from app.db import get_db
from app.deps import client_meta, require_permission
from app.models.nit import InventionDisclosure, IPAsset
from app.models.nit_f2 import (
    AGENDA_ITEM_STATUS_DECIDED,
    Committee,
    CommitteeAgendaItem,
    CommitteeDecision,
    CommitteeMeeting,
    CommitteeMember,
    CommitteeVote,
)
from app.rbac import AccessContext
from app.routers.nit._common import (
    assert_same_tenant,
    list_scope,
    scoped_tenant,
    write_tenant,
)
from app.schemas.nit_f2 import (
    AgendaItemIn,
    AgendaItemOut,
    CommitteeCreate,
    CommitteeDetail,
    CommitteeMemberIn,
    CommitteeMemberOut,
    CommitteeOut,
    CommitteeUpdate,
    DecisionIn,
    DecisionOut,
    MeetingCreate,
    MeetingOut,
    MeetingUpdate,
    VoteIn,
    VoteOut,
    VoteTallyOut,
)
from app.services.committee import (
    DecisionNotAllowed,
    check_can_decide,
    tally_votes,
)

router = APIRouter(prefix="/committees", tags=["nit"])


def _committee_or_404(
    db: Session, ctx: AccessContext, committee_id: uuid.UUID
) -> Committee:
    committee = db.get(Committee, committee_id)
    if committee is None or committee.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comitê não encontrado")
    assert_same_tenant(ctx, committee.tenant_id)
    return committee


def _next_committee_code(db: Session, tenant_id: uuid.UUID) -> str:
    total = db.execute(
        select(func.count()).select_from(Committee).where(Committee.tenant_id == tenant_id)
    ).scalar_one()
    candidate = int(total) + 1
    for _ in range(10000):
        code = f"COM-{candidate:04d}"
        exists = db.execute(
            select(Committee.id).where(
                Committee.tenant_id == tenant_id, Committee.code == code
            )
        ).first()
        if exists is None:
            return code
        candidate += 1
    raise HTTPException(  # pragma: no cover
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Não foi possível gerar o código do comitê",
    )


@router.get("", response_model=list[CommitteeOut])
def list_committees(
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_VIEW")),
) -> list[CommitteeOut]:
    scope = list_scope(ctx)
    conditions = [Committee.deleted_at.is_(None)]
    if scope is not None:
        conditions.append(Committee.tenant_id == scope)
    rows = db.execute(
        select(Committee).where(*conditions).order_by(Committee.name)
    ).scalars()
    return [CommitteeOut.model_validate(r) for r in rows]


@router.post("", response_model=CommitteeDetail, status_code=status.HTTP_201_CREATED)
def create_committee(
    payload: CommitteeCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_MANAGE")),
    meta: dict = Depends(client_meta),
) -> CommitteeDetail:
    tenant = write_tenant(ctx, None)
    committee = Committee(
        tenant_id=tenant,
        code=_next_committee_code(db, tenant),
        name=payload.name,
        description=payload.description,
        quorum=payload.quorum,
        simple_majority=payload.simple_majority,
        active=True,
    )
    db.add(committee)
    record_audit(
        db,
        action="NIT_COMMITTEE_CREATE",
        tenant_id=tenant,
        user_id=ctx.user.id,
        resource="committee",
        resource_id=committee.id,
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(committee)
    detail = CommitteeDetail.model_validate(committee)
    detail.members = []
    return detail


@router.get("/{committee_id}", response_model=CommitteeDetail)
def get_committee(
    committee_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_VIEW")),
) -> CommitteeDetail:
    committee = _committee_or_404(db, ctx, committee_id)
    detail = CommitteeDetail.model_validate(committee)
    detail.members = [
        CommitteeMemberOut.model_validate(m)
        for m in db.execute(
            select(CommitteeMember).where(CommitteeMember.committee_id == committee.id)
        ).scalars()
    ]
    return detail


@router.patch("/{committee_id}", response_model=CommitteeOut)
def update_committee(
    committee_id: uuid.UUID,
    payload: CommitteeUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_MANAGE")),
) -> CommitteeOut:
    committee = _committee_or_404(db, ctx, committee_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(committee, field, value)
    db.commit()
    db.refresh(committee)
    return CommitteeOut.model_validate(committee)


@router.post(
    "/{committee_id}/members",
    response_model=CommitteeMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    committee_id: uuid.UUID,
    payload: CommitteeMemberIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_MANAGE")),
) -> CommitteeMemberOut:
    committee = _committee_or_404(db, ctx, committee_id)
    member = CommitteeMember(
        tenant_id=committee.tenant_id,
        committee_id=committee.id,
        name=payload.name,
        user_id=payload.user_id,
        person_id=payload.person_id,
        role_title=payload.role_title,
        kind=payload.kind,
        valid_from=payload.valid_from,
        valid_until=payload.valid_until,
        active=True,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return CommitteeMemberOut.model_validate(member)


# --- Meetings ---------------------------------------------------------------
@router.post(
    "/{committee_id}/meetings",
    response_model=MeetingOut,
    status_code=status.HTTP_201_CREATED,
)
def create_meeting(
    committee_id: uuid.UUID,
    payload: MeetingCreate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_MEETING_MANAGE")),
) -> MeetingOut:
    committee = _committee_or_404(db, ctx, committee_id)
    meeting = CommitteeMeeting(
        tenant_id=committee.tenant_id,
        committee_id=committee.id,
        title=payload.title,
        scheduled_at=payload.scheduled_at,
        location=payload.location,
        created_by_id=ctx.user.id,
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    return MeetingOut.model_validate(meeting)


@router.get("/{committee_id}/meetings", response_model=list[MeetingOut])
def list_meetings(
    committee_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_VIEW")),
) -> list[MeetingOut]:
    committee = _committee_or_404(db, ctx, committee_id)
    rows = db.execute(
        select(CommitteeMeeting)
        .where(
            CommitteeMeeting.committee_id == committee.id,
            CommitteeMeeting.deleted_at.is_(None),
        )
        .order_by(CommitteeMeeting.scheduled_at.desc())
    ).scalars()
    return [MeetingOut.model_validate(r) for r in rows]


@router.patch("/meetings/{meeting_id}", response_model=MeetingOut)
def update_meeting(
    meeting_id: uuid.UUID,
    payload: MeetingUpdate,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_MEETING_MANAGE")),
) -> MeetingOut:
    meeting = db.get(CommitteeMeeting, meeting_id)
    if meeting is None or meeting.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reunião não encontrada")
    assert_same_tenant(ctx, meeting.tenant_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(meeting, field, value)
    db.commit()
    db.refresh(meeting)
    return MeetingOut.model_validate(meeting)


@router.get("/meetings/{meeting_id}/items", response_model=list[AgendaItemOut])
def list_agenda_items(
    meeting_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_VIEW")),
) -> list[AgendaItemOut]:
    meeting = db.get(CommitteeMeeting, meeting_id)
    if meeting is None or meeting.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reunião não encontrada")
    assert_same_tenant(ctx, meeting.tenant_id)
    rows = db.execute(
        select(CommitteeAgendaItem)
        .where(CommitteeAgendaItem.meeting_id == meeting.id)
        .order_by(CommitteeAgendaItem.sort_order)
    ).scalars()
    return [AgendaItemOut.model_validate(r) for r in rows]


@router.post(
    "/meetings/{meeting_id}/items",
    response_model=AgendaItemOut,
    status_code=status.HTTP_201_CREATED,
)
def add_agenda_item(
    meeting_id: uuid.UUID,
    payload: AgendaItemIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_MEETING_MANAGE")),
) -> AgendaItemOut:
    meeting = db.get(CommitteeMeeting, meeting_id)
    if meeting is None or meeting.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reunião não encontrada")
    assert_same_tenant(ctx, meeting.tenant_id)

    # Referenced entities must belong to the same tenant.
    if payload.disclosure_id is not None:
        disclosure = db.get(InventionDisclosure, payload.disclosure_id)
        if disclosure is None or disclosure.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Comunicação inválida",
            )
        assert_same_tenant(ctx, disclosure.tenant_id)
    if payload.asset_id is not None:
        asset = db.get(IPAsset, payload.asset_id)
        if asset is None or asset.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Ativo inválido"
            )
        assert_same_tenant(ctx, asset.tenant_id)

    item = CommitteeAgendaItem(
        tenant_id=meeting.tenant_id,
        meeting_id=meeting.id,
        disclosure_id=payload.disclosure_id,
        asset_id=payload.asset_id,
        title=payload.title,
        summary=payload.summary,
        sort_order=payload.sort_order,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return AgendaItemOut.model_validate(item)


# --- Votes & decisions ------------------------------------------------------
def _item_or_404(
    db: Session, ctx: AccessContext, item_id: uuid.UUID
) -> CommitteeAgendaItem:
    item = db.get(CommitteeAgendaItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item não encontrado")
    assert_same_tenant(ctx, item.tenant_id)
    return item


def _meeting_committee(db: Session, item: CommitteeAgendaItem) -> Committee:
    meeting = db.get(CommitteeMeeting, item.meeting_id)
    assert meeting is not None
    return db.get(Committee, meeting.committee_id)  # type: ignore[return-value]


@router.get("/items/{item_id}/votes", response_model=VoteTallyOut)
def get_votes(
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_VIEW")),
) -> VoteTallyOut:
    item = _item_or_404(db, ctx, item_id)
    committee = _meeting_committee(db, item)
    tally = tally_votes(db, item)
    can_approve = (
        tally.valid >= committee.quorum
        and (not committee.simple_majority or tally.approvals > tally.rejections)
    )
    return VoteTallyOut(
        approvals=tally.approvals,
        rejections=tally.rejections,
        abstentions=tally.abstentions,
        impeded=tally.impeded,
        valid=tally.valid,
        quorum=committee.quorum,
        can_approve=can_approve,
    )


@router.post(
    "/items/{item_id}/votes",
    response_model=VoteOut,
    status_code=status.HTTP_201_CREATED,
)
def cast_vote(
    item_id: uuid.UUID,
    payload: VoteIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_VOTE")),
    meta: dict = Depends(client_meta),
) -> VoteOut:
    item = _item_or_404(db, ctx, item_id)

    member = db.get(CommitteeMember, payload.member_id)
    if member is None or member.committee_id != db.get(
        CommitteeMeeting, item.meeting_id
    ).committee_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Membro não pertence ao comitê deste item",
        )
    assert_same_tenant(ctx, member.tenant_id)
    if not member.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Membro inativo"
        )

    existing = db.execute(
        select(CommitteeVote).where(
            CommitteeVote.item_id == item.id, CommitteeVote.member_id == member.id
        )
    ).scalar_one_or_none()

    # A declared conflict of interest always becomes an IMPEDED vote.
    vote_value = "IMPEDED" if payload.conflict_of_interest else payload.vote
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este membro já votou neste item.",
        )

    vote = CommitteeVote(
        tenant_id=item.tenant_id,
        item_id=item.id,
        member_id=member.id,
        voter_user_id=ctx.user.id,
        vote=vote_value,
        conflict_of_interest=payload.conflict_of_interest,
        comment=payload.comment,
    )
    db.add(vote)
    record_audit(
        db,
        action="NIT_COMMITTEE_VOTE",
        tenant_id=item.tenant_id,
        user_id=ctx.user.id,
        resource="committee_vote",
        resource_id=vote.id,
        meta={"item_id": str(item.id), "vote": vote_value},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(vote)
    return VoteOut.model_validate(vote)


@router.post("/items/{item_id}/decision", response_model=DecisionOut)
def decide_item(
    item_id: uuid.UUID,
    payload: DecisionIn,
    db: Session = Depends(get_db),
    ctx: AccessContext = Depends(require_permission("NIT_COMMITTEE_DECIDE")),
    meta: dict = Depends(client_meta),
) -> DecisionOut:
    item = _item_or_404(db, ctx, item_id)
    committee = _meeting_committee(db, item)
    tally = tally_votes(db, item)

    try:
        check_can_decide(committee, tally, payload.outcome)
    except DecisionNotAllowed as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    if item.decision is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este item já possui decisão registrada.",
        )

    decision = CommitteeDecision(
        tenant_id=item.tenant_id,
        item_id=item.id,
        outcome=payload.outcome,
        justification=payload.justification,
        approvals=tally.approvals,
        rejections=tally.rejections,
        abstentions=tally.abstentions,
        impeded=tally.impeded,
        decided_by_id=ctx.user.id,
    )
    db.add(decision)
    item.status = AGENDA_ITEM_STATUS_DECIDED
    record_audit(
        db,
        action="NIT_COMMITTEE_DECISION",
        tenant_id=item.tenant_id,
        user_id=ctx.user.id,
        resource="committee_decision",
        resource_id=decision.id,
        meta={"item_id": str(item.id), "outcome": payload.outcome},
        ip=meta.get("ip"),
        user_agent=meta.get("user_agent"),
        commit=False,
    )
    db.commit()
    db.refresh(decision)
    return DecisionOut.model_validate(decision)



