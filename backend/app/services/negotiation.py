"""Negotiation pipeline engine (phase F3).

The pipeline is an explicit, ordered state machine. A stage can only advance
along a declared edge; attempting an undeclared transition raises
:class:`InvalidStage`. Advancing a negotiation NEVER changes a contract's legal
status (that is a separate, explicit contract operation).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.nit_f3 import (
    NEG_STAGE_APPROVAL,
    NEG_STAGE_CLOSED,
    NEG_STAGE_CONTRACTING,
    NEG_STAGE_FIRST_CONTACT,
    NEG_STAGE_NEW,
    NEG_STAGE_NEGOTIATION,
    NEG_STAGE_QUALIFICATION,
    NEG_STAGE_TECHNICAL,
    NEG_TERMINAL,
    Negotiation,
    NegotiationHistory,
)

# Declared edges of the pipeline (from -> allowed next stages).
PIPELINE_EDGES: dict[str, tuple[str, ...]] = {
    NEG_STAGE_NEW: (NEG_STAGE_QUALIFICATION, NEG_STAGE_CLOSED),
    NEG_STAGE_QUALIFICATION: (NEG_STAGE_FIRST_CONTACT, NEG_STAGE_CLOSED),
    NEG_STAGE_FIRST_CONTACT: (NEG_STAGE_TECHNICAL, NEG_STAGE_CLOSED),
    NEG_STAGE_TECHNICAL: (NEG_STAGE_NEGOTIATION, NEG_STAGE_CLOSED),
    NEG_STAGE_NEGOTIATION: (NEG_STAGE_APPROVAL, NEG_STAGE_CLOSED),
    NEG_STAGE_APPROVAL: (NEG_STAGE_CONTRACTING, NEG_STAGE_CLOSED),
    NEG_STAGE_CONTRACTING: (NEG_STAGE_CLOSED,),
    NEG_STAGE_CLOSED: (),
}

STAGE_LABELS: dict[str, str] = {
    NEG_STAGE_NEW: "Novo interesse",
    NEG_STAGE_QUALIFICATION: "Qualificação",
    NEG_STAGE_FIRST_CONTACT: "Contato inicial",
    NEG_STAGE_TECHNICAL: "Discussão técnica",
    NEG_STAGE_NEGOTIATION: "Negociação",
    NEG_STAGE_APPROVAL: "Aprovação",
    NEG_STAGE_CONTRACTING: "Contratação",
    NEG_STAGE_CLOSED: "Encerrado",
}


class NegotiationError(Exception):
    """Base class for negotiation rule violations."""


class InvalidStage(NegotiationError):
    """The requested stage transition is not a declared pipeline edge."""


class NegotiationClosed(NegotiationError):
    """The negotiation is in a terminal stage."""


def allowed_next(stage: str) -> tuple[str, ...]:
    return PIPELINE_EDGES.get(stage, ())


def advance(
    db: Session,
    *,
    negotiation: Negotiation,
    to_stage: str,
    actor_id,
    justification: str | None = None,
    expected_version: int | None = None,
) -> Negotiation:
    """Advance the negotiation to ``to_stage`` if the edge is declared.

    The caller owns the transaction/commit. On success a history row is appended
    and ``version`` is incremented (optimistic concurrency).
    """
    if negotiation.stage in NEG_TERMINAL:
        raise NegotiationClosed("A negociação está encerrada.")
    if expected_version is not None and negotiation.version != expected_version:
        raise NegotiationError(
            "A negociação foi alterada por outra operação. Recarregue e tente novamente."
        )
    if to_stage not in allowed_next(negotiation.stage):
        raise InvalidStage(
            f"Transição de etapa inválida: {negotiation.stage} → {to_stage}."
        )

    from_stage = negotiation.stage
    negotiation.stage = to_stage
    negotiation.version = negotiation.version + 1
    db.add(
        NegotiationHistory(
            tenant_id=negotiation.tenant_id,
            negotiation_id=negotiation.id,
            from_stage=from_stage,
            to_stage=to_stage,
            actor_id=actor_id,
            justification=justification,
        )
    )
    db.flush()
    return negotiation
