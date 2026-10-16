"""Commercial CRM domain services.

Everything the CRM needs to be *correct* lives here, not in the router:

* ``next_opportunity_code`` / ``next_proposal_code`` — per-tenant sequential
  codes (``OPP-000123`` / ``PRO-000123``), generated inside the caller's
  transaction and guarded by the ``(tenant_id, code)`` unique constraint.
* ``apply_opportunity_stage`` / ``apply_proposal_status`` — validate the
  transition against the vocabularies in ``app.models.crm`` and record the
  lifecycle side effects (send date, reply date, decision date, lost reason).
* ``convert_opportunity_to_customer`` — turns a won opportunity into a
  ``Customer`` (reusing an existing row when possible, so clients are never
  duplicated) and back-fills the links. Executed inside a single transaction by
  the router: either the customer is created *and* linked, or nothing changes.
* ``build_business_dashboard`` — the tenant-scoped aggregates of the Overview.

No value is ever fabricated: a missing number is reported as 0, and a ratio that
cannot be computed is returned as ``None``.
"""

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import and_, func, literal_column, or_, select
from sqlalchemy.orm import Session

from app.models import (
    Company,
    Customer,
    Marca,
    MarcaMonitoramento,
    Patente,
    PatenteConteudo,
    PatenteMonitoramento,
    Person,
    User,
)
from app.models.crm import (
    OPPORTUNITY_STAGE_LABELS,
    OPPORTUNITY_STAGES,
    OPPORTUNITY_TRANSITIONS,
    PROPOSAL_CLOSED_STATUSES,
    PROPOSAL_OPEN_STATUSES,
    PROPOSAL_STATUS_LABELS,
    PROPOSAL_TRANSITIONS,
    CrmActivity,
    CrmOpportunity,
    CrmProposal,
)

# --- Codes -------------------------------------------------------------------


def _next_code(db: Session, model, prefix: str, tenant_id: uuid.UUID) -> str:
    """Return the next ``PREFIX-NNNNNN`` code for the tenant.

    The code is derived from the current count of rows for the tenant, which the
    ``(tenant_id, code)`` unique constraint protects against collisions. The
    caller is expected to retry (or let the integrity handler answer 409) if two
    requests race; the CRM is a low-volume, human-paced flow.
    """
    existing = db.execute(
        select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
    ).scalar_one()
    return f"{prefix}-{int(existing) + 1:06d}"


def next_opportunity_code(db: Session, tenant_id: uuid.UUID) -> str:
    return _next_code(db, CrmOpportunity, "OPP", tenant_id)


def next_proposal_code(db: Session, tenant_id: uuid.UUID) -> str:
    return _next_code(db, CrmProposal, "PRO", tenant_id)


# --- Transitions -------------------------------------------------------------


def apply_opportunity_stage(
    db: Session,
    opportunity: CrmOpportunity,
    *,
    new_stage: str,
    lost_reason: str | None = None,
    customer_id: uuid.UUID | None = None,
) -> CrmOpportunity:
    """Validate and apply an opportunity stage change.

    ``WON`` requires a linked customer (existing or created by conversion) and
    ``LOST`` requires a reason — both business rules are enforced here so the
    database never holds a won deal without a client nor a loss without motive.
    """
    if new_stage not in OPPORTUNITY_STAGES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Etapa inválida: {new_stage}",
        )
    current = opportunity.stage or "NEW"
    if new_stage == current:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A oportunidade já está na etapa {OPPORTUNITY_STAGE_LABELS.get(current, current)}.",
        )
    allowed = OPPORTUNITY_TRANSITIONS.get(current, ())
    if new_stage not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Transição não permitida: "
                f"{OPPORTUNITY_STAGE_LABELS.get(current, current)} → "
                f"{OPPORTUNITY_STAGE_LABELS.get(new_stage, new_stage)}."
            ),
        )

    if new_stage == "WON":
        target_customer = customer_id or opportunity.customer_id
        if target_customer is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Uma oportunidade só pode ser marcada como Aprovada quando "
                    "estiver vinculada a um cliente. Use a conversão em cliente."
                ),
            )
        opportunity.customer_id = target_customer
        opportunity.lost_reason = None
    if new_stage == "LOST":
        if not (lost_reason or opportunity.lost_reason):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Informe o motivo da perda.",
            )
        opportunity.lost_reason = lost_reason or opportunity.lost_reason

    if customer_id is not None:
        opportunity.customer_id = customer_id

    opportunity.stage = new_stage
    return opportunity


def apply_proposal_status(
    db: Session,
    proposal: CrmProposal,
    *,
    new_status: str,
    mark_sent: bool = False,
    mark_reply: bool = False,
    decision_notes: str | None = None,
) -> CrmProposal:
    """Validate and apply a proposal status change, recording its side effects.

    * ``SENT`` (or ``mark_sent``) stamps ``sent_at`` when it is not set yet, so
      the "enviada" moment reflects reality instead of an estimate.
    * ``mark_reply`` stamps ``replied_at`` when the prospect answers.
    * ``APPROVED``/``REJECTED`` stamp ``decision_at`` and (optionally) the notes.

    Approving a proposal does NOT create a trademark/patent nor execute a
    service: that separation is intentional.
    """
    from app.models.crm import PROPOSAL_STATUSES  # local import to avoid cycles

    if new_status not in PROPOSAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Status inválido: {new_status}",
        )
    current = proposal.status or "DRAFT"
    if new_status == current and not (mark_sent or mark_reply):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A proposta já está com o status {PROPOSAL_STATUS_LABELS.get(current, current)}.",
        )
    if new_status != current:
        allowed = PROPOSAL_TRANSITIONS.get(current, ())
        if new_status not in allowed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Transição não permitida: "
                    f"{PROPOSAL_STATUS_LABELS.get(current, current)} → "
                    f"{PROPOSAL_STATUS_LABELS.get(new_status, new_status)}."
                ),
            )

    now = datetime.now(timezone.utc)
    proposal.status = new_status

    if mark_sent or new_status == "SENT":
        if proposal.sent_at is None:
            proposal.sent_at = now
    if mark_reply or new_status == "AWAITING_REPLY":
        proposal.replied_at = now
    if new_status in ("APPROVED", "REJECTED"):
        proposal.decision_at = now
        if decision_notes:
            proposal.decision_notes = decision_notes

    return proposal


# --- Lead -> Customer conversion --------------------------------------------


def _normalise_document(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits or None


def find_existing_customer(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    name: str | None,
    document: str | None,
    email: str | None,
) -> Customer | None:
    """Look for an existing customer of the tenant to avoid duplicating it.

    Matching order (most reliable first): document, then e-mail, then exact
    name. Only live (not soft-deleted) rows are considered.
    """
    base = [Customer.tenant_id == tenant_id, Customer.deleted_at.is_(None)]
    doc = _normalise_document(document)
    if doc:
        rows = db.execute(
            select(Customer).where(*base, Customer.document == doc).limit(1)
        ).scalars().all()
        if rows:
            return rows[0]
    if email:
        rows = db.execute(
            select(Customer).where(*base, func.lower(Customer.email) == email.lower()).limit(1)
        ).scalars().all()
        if rows:
            return rows[0]
    if name:
        rows = db.execute(
            select(Customer).where(*base, func.lower(Customer.name) == name.lower()).limit(1)
        ).scalars().all()
        if rows:
            return rows[0]
    return None


def convert_opportunity_to_customer(
    db: Session,
    opportunity: CrmOpportunity,
    *,
    tenant_id: uuid.UUID,
    name: str | None = None,
    document: str | None = None,
    email: str | None = None,
    phone: str | None = None,
    force_new: bool = False,
) -> tuple[Customer, bool]:
    """Convert a won opportunity into a ``Customer``.

    Returns ``(customer, created)``. Unless ``force_new`` is set the service
    first searches for an existing customer of the tenant (document → e-mail →
    name) and reuses it, which is what prevents duplicated clients during
    conversion. The opportunity is linked to the resulting customer and moved to
    the ``WON`` stage.

    The caller must run this inside a transaction: the customer creation and the
    opportunity/proposal back-fill either both succeed or both roll back.
    """
    if opportunity.customer_id is not None and not force_new:
        existing = db.get(Customer, opportunity.customer_id)
        if existing is not None and existing.deleted_at is None:
            customer = existing
            created = False
        else:
            customer, created = _resolve_customer(
                db, tenant_id, opportunity, name, document, email, phone
            )
    else:
        customer, created = _resolve_customer(
            db, tenant_id, opportunity, name, document, email, phone
        )

    opportunity.customer_id = customer.id
    opportunity.stage = "WON"
    opportunity.lost_reason = None

    # Preserve the commercial history: link every proposal of this opportunity.
    proposals = db.execute(
        select(CrmProposal).where(
            CrmProposal.opportunity_id == opportunity.id,
            CrmProposal.deleted_at.is_(None),
        )
    ).scalars().all()
    for proposal in proposals:
        if proposal.customer_id is None:
            proposal.customer_id = customer.id

    return customer, created


def _resolve_customer(
    db: Session,
    tenant_id: uuid.UUID,
    opportunity: CrmOpportunity,
    name: str | None,
    document: str | None,
    email: str | None,
    phone: str | None,
) -> tuple[Customer, bool]:
    resolved_name = (name or opportunity.lead_name or opportunity.title or "").strip()
    if not resolved_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Informe o nome do cliente para concluir a conversão.",
        )
    existing = find_existing_customer(
        db, tenant_id, name=resolved_name, document=document, email=email
    )
    if existing is not None:
        return existing, False

    customer = Customer(
        tenant_id=tenant_id,
        company_id=opportunity.company_id,
        name=resolved_name,
        document=_normalise_document(document),
        email=email,
        phone=phone,
        notes=f"Convertido da oportunidade {opportunity.code}.",
        active=True,
    )
    db.add(customer)
    db.flush()
    return customer, True


# --- Business dashboard ------------------------------------------------------

#: Statuses that mean "the proposal still needs to be sent".
_TO_SEND_STATUSES = ("DRAFT", "PENDING_SEND")
#: Statuses that mean "sent, waiting for the prospect".
_AWAITING_STATUSES = ("SENT", "AWAITING_REPLY", "NEGOTIATION")


def _month_buckets(months: int, today: date) -> list[str]:
    """Return the ``YYYY-MM`` labels of the last ``months`` months (oldest first)."""
    labels: list[str] = []
    year, month = today.year, today.month
    for _ in range(months):
        labels.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(labels))


def _scoped(column, tenant_id: uuid.UUID | None):
    """Optional tenant predicate (``None`` = master admin, all tenants)."""
    return [] if tenant_id is None else [column == tenant_id]


def build_business_dashboard(
    db: Session,
    *,
    tenant_id: uuid.UUID | None,
    months: int = 12,
) -> dict:
    """Compute the commercial dashboard payload for one tenant (or all).

    ``tenant_id=None`` is only passed by the master admin and means "all
    tenants" — an ordinary user always gets their own tenant.
    """
    today = date.today()
    months = max(1, min(months, 24))
    labels = _month_buckets(months, today)
    first_label = labels[0]
    period_from = date(int(first_label[:4]), int(first_label[5:7]), 1)

    opp = [CrmOpportunity.deleted_at.is_(None), *_scoped(CrmOpportunity.tenant_id, tenant_id)]
    prop = [CrmProposal.deleted_at.is_(None), *_scoped(CrmProposal.tenant_id, tenant_id)]
    cust = [Customer.deleted_at.is_(None), *_scoped(Customer.tenant_id, tenant_id)]

    def _count(conds, model) -> int:
        return int(
            db.execute(select(func.count()).select_from(model).where(*conds)).scalar_one()
        )

    active_customers = int(
        db.execute(
            select(func.count()).select_from(Customer).where(*cust, Customer.active.is_(True))
        ).scalar_one()
    )
    total_customers = _count(cust, Customer)
    new_customers_period = int(
        db.execute(
            select(func.count())
            .select_from(Customer)
            .where(
                *cust,
                Customer.created_at
                >= datetime(period_from.year, period_from.month, 1, tzinfo=timezone.utc),
            )
        ).scalar_one()
    )

    stage_counts = {
        str(k): int(v)
        for k, v in db.execute(
            select(CrmOpportunity.stage, func.count()).where(*opp).group_by(CrmOpportunity.stage)
        ).all()
    }
    open_opportunities = sum(v for k, v in stage_counts.items() if k not in ("WON", "LOST"))

    status_counts = {
        str(k): int(v)
        for k, v in db.execute(
            select(CrmProposal.status, func.count()).where(*prop).group_by(CrmProposal.status)
        ).all()
    }
    proposals_to_send = sum(status_counts.get(s, 0) for s in _TO_SEND_STATUSES)
    proposals_awaiting_reply = sum(status_counts.get(s, 0) for s in _AWAITING_STATUSES)
    proposals_approved = status_counts.get("APPROVED", 0)
    proposals_rejected = status_counts.get("REJECTED", 0)
    proposals_open = sum(status_counts.get(s, 0) for s in PROPOSAL_OPEN_STATUSES)
    proposals_overdue = int(
        db.execute(
            select(func.count())
            .select_from(CrmProposal)
            .where(
                *prop,
                CrmProposal.valid_until.is_not(None),
                CrmProposal.valid_until < today,
                CrmProposal.status.in_(PROPOSAL_OPEN_STATUSES),
            )
        ).scalar_one()
    )

    monitored_marcas = int(
        db.execute(
            select(func.count())
            .select_from(MarcaMonitoramento)
            .where(
                MarcaMonitoramento.deleted_at.is_(None),
                MarcaMonitoramento.active.is_(True),
                *_scoped(MarcaMonitoramento.tenant_id, tenant_id),
            )
        ).scalar_one()
    )
    monitored_patentes = int(
        db.execute(
            select(func.count())
            .select_from(PatenteMonitoramento)
            .where(
                PatenteMonitoramento.deleted_at.is_(None),
                PatenteMonitoramento.active.is_(True),
                *_scoped(PatenteMonitoramento.tenant_id, tenant_id),
            )
        ).scalar_one()
    )

    stage_values = {
        str(k): v
        for k, v in db.execute(
            select(CrmOpportunity.stage, func.sum(CrmOpportunity.estimated_value))
            .where(*opp)
            .group_by(CrmOpportunity.stage)
        ).all()
    }
    funnel = [
        {
            "stage": stage,
            "label": OPPORTUNITY_STAGE_LABELS.get(stage, stage),
            "count": stage_counts.get(stage, 0),
            "value": (
                f"{Decimal(stage_values[stage]):.2f}"
                if stage_values.get(stage) is not None
                else None
            ),
        }
        for stage in OPPORTUNITY_STAGES
    ]

    pending = _pending_proposals(db, tenant_id=tenant_id, today=today, limit=10)
    deadlines = _upcoming_deadlines(db, tenant_id=tenant_id, today=today, limit=10)
    recent = _recent_activity(db, tenant_id=tenant_id, limit=12)

    # Alerts that demand attention: urgent proposals + commercial follow-ups due
    # today/past. Deliberately commercial-only so the commercial and the IP
    # domains stay separated in the Overview.
    critical_alerts = sum(1 for p in pending if p["reason"] in ("OVERDUE", "NEAR_DUE"))
    critical_alerts += int(
        db.execute(
            select(func.count())
            .select_from(CrmActivity)
            .where(
                CrmActivity.deleted_at.is_(None),
                CrmActivity.active.is_(True),
                CrmActivity.outcome == "PENDING",
                CrmActivity.due_at.is_not(None),
                func.date(CrmActivity.due_at) <= today,
                *_scoped(CrmActivity.tenant_id, tenant_id),
            )
        ).scalar_one()
    )

    closed = proposals_approved + proposals_rejected
    conversion_rate = round(proposals_approved * 100.0 / closed, 1) if closed else None

    return {
        "generated_at": datetime.now(timezone.utc),
        "scope": "all_tenants" if tenant_id is None else "tenant",
        "period": {"date_from": period_from, "date_to": today, "months": months},
        "counters": {
            "active_customers": active_customers,
            "total_customers": total_customers,
            "new_customers_period": new_customers_period,
            "open_opportunities": open_opportunities,
            "proposals_to_send": proposals_to_send,
            "proposals_awaiting_reply": proposals_awaiting_reply,
            "proposals_approved": proposals_approved,
            "proposals_rejected": proposals_rejected,
            "proposals_open": proposals_open,
            "proposals_overdue": proposals_overdue,
            "monitored_marcas": monitored_marcas,
            "monitored_patentes": monitored_patentes,
            "critical_alerts": critical_alerts,
            "conversion_rate": conversion_rate,
        },
        "evolution": _build_evolution(db, labels=labels, tenant_id=tenant_id),
        "funnel": funnel,
        "pending_proposals": pending,
        "deadlines": deadlines,
        "recent_activity": recent,
    }


def _build_evolution(db: Session, *, labels: list[str], tenant_id: uuid.UUID | None) -> list[dict]:
    """Monthly series of new customers, proposals sent/approved and deals won."""
    buckets = {
        label: {
            "new_customers": 0,
            "proposals_sent": 0,
            "proposals_approved": 0,
            "opportunities_won": 0,
        }
        for label in labels
    }
    window = set(labels)

    def _apply(rows, key) -> None:
        for label, count in rows:
            if label in window:
                buckets[label][key] += int(count)

    # ``to_char`` with a *literal* format string: passing it as a bound parameter
    # makes SELECT and GROUP BY produce two different parameters, which Postgres
    # rejects as "column must appear in the GROUP BY clause".
    month_expr = lambda col: func.to_char(col, literal_column("'YYYY-MM'"))  # noqa: E731

    _apply(
        db.execute(
            select(month_expr(Customer.created_at).label("bucket"), func.count())
            .where(Customer.deleted_at.is_(None), *_scoped(Customer.tenant_id, tenant_id))
            .group_by(month_expr(Customer.created_at))
        ).all(),
        "new_customers",
    )
    _apply(
        db.execute(
            select(month_expr(CrmProposal.sent_at).label("bucket"), func.count())
            .where(
                CrmProposal.deleted_at.is_(None),
                CrmProposal.sent_at.is_not(None),
                *_scoped(CrmProposal.tenant_id, tenant_id),
            )
            .group_by(month_expr(CrmProposal.sent_at))
        ).all(),
        "proposals_sent",
    )
    _apply(
        db.execute(
            select(month_expr(CrmProposal.decision_at).label("bucket"), func.count())
            .where(
                CrmProposal.deleted_at.is_(None),
                CrmProposal.decision_at.is_not(None),
                CrmProposal.status == "APPROVED",
                *_scoped(CrmProposal.tenant_id, tenant_id),
            )
            .group_by(month_expr(CrmProposal.decision_at))
        ).all(),
        "proposals_approved",
    )
    _apply(
        db.execute(
            select(month_expr(CrmOpportunity.updated_at).label("bucket"), func.count())
            .where(
                CrmOpportunity.deleted_at.is_(None),
                CrmOpportunity.stage == "WON",
                *_scoped(CrmOpportunity.tenant_id, tenant_id),
            )
            .group_by(month_expr(CrmOpportunity.updated_at))
        ).all(),
        "opportunities_won",
    )

    return [{"label": label, **buckets[label]} for label in labels]


def _pending_proposals(
    db: Session,
    *,
    tenant_id: uuid.UUID | None,
    today: date,
    limit: int = 10,
) -> list[dict]:
    """Proposals that require action, most urgent first.

    Priority: overdue → to send → approved without customer → awaiting reply →
    near due. Each row explains *why* it is listed (``reason``) so the UI can
    guide the operator instead of just showing a status.
    """
    rows = (
        db.execute(
            select(CrmProposal, Customer.name, CrmOpportunity.title, Person.name)
            .outerjoin(Customer, Customer.id == CrmProposal.customer_id)
            .outerjoin(CrmOpportunity, CrmOpportunity.id == CrmProposal.opportunity_id)
            .outerjoin(Person, Person.user_id == CrmProposal.owner_id)
            .where(
                CrmProposal.deleted_at.is_(None),
                CrmProposal.active.is_(True),
                CrmProposal.status.in_(PROPOSAL_OPEN_STATUSES + ("APPROVED",)),
                *_scoped(CrmProposal.tenant_id, tenant_id),
            )
        )
        .all()
    )

    items: list[dict] = []
    for proposal, customer_name, opp_title, owner_name in rows:
        days_to_due = (
            (proposal.valid_until - today).days if proposal.valid_until else None
        )
        if days_to_due is not None and days_to_due < 0:
            reason = "OVERDUE"
        elif proposal.status in _TO_SEND_STATUSES:
            reason = "TO_SEND"
        elif proposal.status == "APPROVED" and proposal.customer_id is None:
            reason = "APPROVED_NO_CUSTOMER"
        elif proposal.status in ("SENT", "AWAITING_REPLY", "NEGOTIATION"):
            reason = "AWAITING_REPLY"
        elif days_to_due is not None and days_to_due <= 15:
            reason = "NEAR_DUE"
        else:
            continue

        items.append(
            {
                "id": proposal.id,
                "code": proposal.code,
                "title": proposal.title,
                "status": proposal.status,
                "status_label": PROPOSAL_STATUS_LABELS.get(
                    proposal.status, proposal.status
                ),
                "customer_name": customer_name,
                "opportunity_title": opp_title,
                "owner_name": owner_name,
                "total_value": (
                    f"{Decimal(proposal.total_value):.2f}"
                    if proposal.total_value is not None
                    else None
                ),
                "sent_at": proposal.sent_at,
                "valid_until": proposal.valid_until,
                "days_to_due": days_to_due,
                "reason": reason,
            }
        )

    order = {
        "OVERDUE": 0,
        "TO_SEND": 1,
        "APPROVED_NO_CUSTOMER": 2,
        "AWAITING_REPLY": 3,
        "NEAR_DUE": 4,
    }
    items.sort(key=lambda i: (order.get(i["reason"], 9), i["days_to_due"] if i["days_to_due"] is not None else 9999))
    return items[:limit]


def _deadline_tone(days: int | None) -> str:
    if days is None:
        return "slate"
    if days <= 15:
        return "red"
    if days <= 60:
        return "amber"
    return "green"


def _upcoming_deadlines(
    db: Session,
    *,
    tenant_id: uuid.UUID | None,
    today: date,
    limit: int = 10,
) -> list[dict]:
    """Commercial deadlines plus the user's monitored PI dates.

    The two domains are returned with an explicit ``domain`` tag so the UI can
    keep them apart — the Overview never mixes commercial and PI deadlines.
    Only real dates stored in the database are used (no estimated INPI dates).
    """
    items: list[dict] = []

    # --- Commercial: pending follow-ups with a due date --------------------
    activities = (
        db.execute(
            select(CrmActivity, CrmOpportunity.title, CrmProposal.title)
            .outerjoin(
                CrmOpportunity,
                and_(
                    CrmActivity.subject_type == "OPPORTUNITY",
                    CrmOpportunity.id == CrmActivity.subject_id,
                ),
            )
            .outerjoin(
                CrmProposal,
                and_(
                    CrmActivity.subject_type == "PROPOSAL",
                    CrmProposal.id == CrmActivity.subject_id,
                ),
            )
            .where(
                CrmActivity.deleted_at.is_(None),
                CrmActivity.active.is_(True),
                CrmActivity.outcome == "PENDING",
                CrmActivity.due_at.is_not(None),
                *_scoped(CrmActivity.tenant_id, tenant_id),
            )
            .order_by(CrmActivity.due_at.asc())
            .limit(limit)
        )
        .all()
    )
    for activity, opp_title, prop_title in activities:
        due = activity.due_at.date() if activity.due_at else None
        days = (due - today).days if due else None
        items.append(
            {
                "domain": "COMMERCIAL",
                "title": activity.title,
                "subtitle": opp_title or prop_title or "Follow-up comercial",
                "due_at": due,
                "days_remaining": days,
                "tone": _deadline_tone(days),
                "link": "/crm/atividades",
            }
        )

    # --- Commercial: proposal validity -------------------------------------
    proposals = (
        db.execute(
            select(CrmProposal, Customer.name)
            .outerjoin(Customer, Customer.id == CrmProposal.customer_id)
            .where(
                CrmProposal.deleted_at.is_(None),
                CrmProposal.active.is_(True),
                CrmProposal.valid_until.is_not(None),
                CrmProposal.status.in_(PROPOSAL_OPEN_STATUSES),
                *_scoped(CrmProposal.tenant_id, tenant_id),
            )
            .order_by(CrmProposal.valid_until.asc())
            .limit(limit)
        )
        .all()
    )
    for proposal, customer_name in proposals:
        days = (proposal.valid_until - today).days
        items.append(
            {
                "domain": "COMMERCIAL",
                "title": f"Validade da proposta {proposal.code}",
                "subtitle": customer_name or proposal.title,
                "due_at": proposal.valid_until,
                "days_remaining": days,
                "tone": _deadline_tone(days),
                "link": "/crm/propostas",
            }
        )

    # --- IP: monitored marca vigências -------------------------------------
    marcas = (
        db.execute(
            select(
                MarcaMonitoramento.codigo_interno,
                Marca.elemento_nominativo,
                Marca.numero_inpi,
                Marca.data_vigencia,
            )
            .select_from(MarcaMonitoramento)
            .outerjoin(Marca, Marca.codigo_interno == MarcaMonitoramento.codigo_interno)
            .where(
                MarcaMonitoramento.deleted_at.is_(None),
                MarcaMonitoramento.active.is_(True),
                Marca.data_vigencia.is_not(None),
                Marca.data_vigencia >= today,
                *_scoped(MarcaMonitoramento.tenant_id, tenant_id),
            )
            .order_by(Marca.data_vigencia.asc())
            .limit(limit)
        )
        .all()
    )
    for codigo, nominativo, numero, vigencia in marcas:
        days = (vigencia - today).days
        items.append(
            {
                "domain": "PROPRIEDADE_INTELECTUAL",
                "title": nominativo or numero or codigo,
                "subtitle": "Vigência de marca monitorada",
                "due_at": vigencia,
                "days_remaining": days,
                "tone": _deadline_tone(days),
                "link": "/monitoramento",
            }
        )

    # --- IP: monitored patente deposits (baseline for deadlines) -----------
    patentes = (
        db.execute(
            select(
                PatenteMonitoramento.codigo_interno,
                Patente.numero_inpi,
                PatenteConteudo.titulo,
                Patente.data_deposito,
            )
            .select_from(PatenteMonitoramento)
            .outerjoin(
                Patente, Patente.codigo_interno == PatenteMonitoramento.codigo_interno
            )
            .outerjoin(
                PatenteConteudo,
                PatenteConteudo.codigo_interno == PatenteMonitoramento.codigo_interno,
            )
            .where(
                PatenteMonitoramento.deleted_at.is_(None),
                PatenteMonitoramento.active.is_(True),
                *_scoped(PatenteMonitoramento.tenant_id, tenant_id),
            )
            .order_by(Patente.data_deposito.desc())
            .limit(limit)
        )
        .all()
    )
    for codigo, numero, titulo, deposito in patentes:
        if deposito is None:
            continue
        days = (deposito - today).days
        items.append(
            {
                "domain": "PROPRIEDADE_INTELECTUAL",
                "title": titulo or numero or codigo,
                "subtitle": "Depósito de patente monitorada",
                "due_at": deposito,
                "days_remaining": days,
                "tone": _deadline_tone(days),
                "link": "/monitoramento",
            }
        )

    items.sort(
        key=lambda i: i["days_remaining"] if i["days_remaining"] is not None else 9999
    )
    return items[:limit]


def _recent_activity(
    db: Session,
    *,
    tenant_id: uuid.UUID | None,
    limit: int = 12,
) -> list[dict]:
    """Chronological timeline of real events of the tenant's commercial operation.

    Sources (each one a real row): customers created, opportunities created and
    won/lost, proposals created/sent/decided, activities registered and PI items
    added to the watch list. Nothing is invented: an empty operation yields an
    empty list and the UI shows its empty state.
    """
    events: list[dict] = []

    customers = (
        db.execute(
            select(Customer.name, Customer.created_at)
            .where(Customer.deleted_at.is_(None), *_scoped(Customer.tenant_id, tenant_id))
            .order_by(Customer.created_at.desc())
            .limit(limit)
        )
        .all()
    )
    for name, at in customers:
        events.append(
            {
                "kind": "customer",
                "title": f"Cliente cadastrado: {name}",
                "description": None,
                "status": "ATIVO",
                "at": at,
                "link": "/clientes",
            }
        )

    opportunities = (
        db.execute(
            select(
                CrmOpportunity.code,
                CrmOpportunity.title,
                CrmOpportunity.stage,
                CrmOpportunity.created_at,
                CrmOpportunity.updated_at,
            )
            .where(
                CrmOpportunity.deleted_at.is_(None),
                *_scoped(CrmOpportunity.tenant_id, tenant_id),
            )
            .order_by(CrmOpportunity.updated_at.desc())
            .limit(limit)
        )
        .all()
    )
    for code, title, stage, created_at, updated_at in opportunities:
        if stage in ("WON", "LOST"):
            events.append(
                {
                    "kind": "opportunity",
                    "title": (
                        f"Oportunidade {'ganha' if stage == 'WON' else 'perdida'}: {title}"
                    ),
                    "description": code,
                    "status": OPPORTUNITY_STAGE_LABELS.get(stage, stage),
                    "at": updated_at,
                    "link": "/crm/oportunidades",
                }
            )
        else:
            events.append(
                {
                    "kind": "opportunity",
                    "title": f"Oportunidade criada: {title}",
                    "description": code,
                    "status": OPPORTUNITY_STAGE_LABELS.get(stage, stage),
                    "at": created_at,
                    "link": "/crm/oportunidades",
                }
            )

    proposals = (
        db.execute(
            select(
                CrmProposal.code,
                CrmProposal.title,
                CrmProposal.status,
                CrmProposal.created_at,
                CrmProposal.sent_at,
                CrmProposal.decision_at,
            )
            .where(
                CrmProposal.deleted_at.is_(None),
                *_scoped(CrmProposal.tenant_id, tenant_id),
            )
            .order_by(CrmProposal.updated_at.desc())
            .limit(limit)
        )
        .all()
    )
    for code, title, status, created_at, sent_at, decision_at in proposals:
        if decision_at is not None and status in ("APPROVED", "REJECTED"):
            events.append(
                {
                    "kind": "proposal",
                    "title": (
                        f"Proposta {'aprovada' if status == 'APPROVED' else 'recusada'}: {title}"
                    ),
                    "description": code,
                    "status": PROPOSAL_STATUS_LABELS.get(status, status),
                    "at": decision_at,
                    "link": "/crm/propostas",
                }
            )
        if sent_at is not None:
            events.append(
                {
                    "kind": "proposal",
                    "title": f"Proposta enviada: {title}",
                    "description": code,
                    "status": PROPOSAL_STATUS_LABELS.get(status, status),
                    "at": sent_at,
                    "link": "/crm/propostas",
                }
            )
        if sent_at is None and decision_at is None:
            events.append(
                {
                    "kind": "proposal",
                    "title": f"Proposta criada: {title}",
                    "description": code,
                    "status": PROPOSAL_STATUS_LABELS.get(status, status),
                    "at": created_at,
                    "link": "/crm/propostas",
                }
            )

    activities = (
        db.execute(
            select(CrmActivity.title, CrmActivity.kind, CrmActivity.created_at)
            .where(
                CrmActivity.deleted_at.is_(None),
                *_scoped(CrmActivity.tenant_id, tenant_id),
            )
            .order_by(CrmActivity.created_at.desc())
            .limit(limit)
        )
        .all()
    )
    for title, kind, at in activities:
        events.append(
            {
                "kind": "activity",
                "title": title,
                "description": "Follow-up comercial",
                "status": kind,
                "at": at,
                "link": "/crm/atividades",
            }
        )

    monitored = (
        db.execute(
            select(MarcaMonitoramento.codigo_interno, MarcaMonitoramento.monitored_at)
            .where(
                MarcaMonitoramento.deleted_at.is_(None),
                MarcaMonitoramento.active.is_(True),
                *_scoped(MarcaMonitoramento.tenant_id, tenant_id),
            )
            .order_by(MarcaMonitoramento.monitored_at.desc())
            .limit(limit)
        )
        .all()
    )
    for codigo, at in monitored:
        events.append(
            {
                "kind": "monitoring",
                "title": f"Marca adicionada ao monitoramento: {codigo}",
                "description": None,
                "status": "MONITORADA",
                "at": at,
                "link": "/monitoramento",
            }
        )

    events.sort(key=lambda e: e["at"], reverse=True)
    return events[:limit]










