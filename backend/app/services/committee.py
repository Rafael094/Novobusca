"""Committee decision rules (phase F2).

Enforces, in one place, the rules that decide whether an agenda item may be
decided:

* Quorum: the number of VALID votes (excluding ``IMPEDED``/abstentions from members
  with a declared conflict of interest) must reach the committee's ``quorum``.
* Majority: with ``simple_majority`` an ``APPROVED`` outcome requires strictly more
  approvals than rejections; a tie cannot approve.
* A member with a declared conflict of interest on an item is recorded as
  ``IMPEDED`` and never counts toward the quorum.

The module never decides an outcome on its own: it either allows the caller's
requested outcome or raises :class:`DecisionNotAllowed`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.nit_f2 import (
    DECISION_APPROVED,
    DECISION_DEFERRED,
    DECISION_OUTCOMES,
    VOTE_ABSTAIN,
    VOTE_APPROVE,
    VOTE_IMPEDED,
    VOTE_REJECT,
    Committee,
    CommitteeAgendaItem,
    CommitteeVote,
)


class CommitteeError(Exception):
    """Base class for committee rule violations (mapped to HTTP 4xx by callers)."""


class DecisionNotAllowed(CommitteeError):
    """The requested outcome violates quorum/majority rules."""


class InvalidVote(CommitteeError):
    """The vote option is unknown or the voter is not a valid member."""


@dataclass(frozen=True)
class VoteTally:
    approvals: int
    rejections: int
    abstentions: int
    impeded: int

    @property
    def valid(self) -> int:
        """Votes that count toward the quorum (approvals + rejections)."""
        return self.approvals + self.rejections


def tally_votes(db: Session, item: CommitteeAgendaItem) -> VoteTally:
    """Count the votes cast on an item, excluding impeded/conflicted members."""
    rows = db.execute(
        select(CommitteeVote).where(CommitteeVote.item_id == item.id)
    ).scalars()
    approvals = rejections = abstentions = impeded = 0
    for v in rows:
        if v.vote == VOTE_APPROVE:
            approvals += 1
        elif v.vote == VOTE_REJECT:
            rejections += 1
        elif v.vote == VOTE_ABSTAIN:
            abstentions += 1
        elif v.vote == VOTE_IMPEDED or v.conflict_of_interest:
            impeded += 1
    return VoteTally(approvals, rejections, abstentions, impeded)


def check_can_decide(
    committee: Committee, tally: VoteTally, requested_outcome: str
) -> None:
    """Raise :class:`DecisionNotAllowed` unless the requested outcome is valid."""
    if requested_outcome not in DECISION_OUTCOMES:
        raise DecisionNotAllowed(f"Resultado de decisão inválido: {requested_outcome}")

    if requested_outcome == DECISION_DEFERRED:
        # Deferring never decides the merits, so it is always allowed by the engine
        # (the caller still needs the DECIDE permission).
        return

    if tally.valid < committee.quorum:
        raise DecisionNotAllowed(
            f"Quórum insuficiente: {tally.valid} voto(s) válido(s) de um mínimo de "
            f"{committee.quorum}."
        )

    if committee.simple_majority:
        if requested_outcome == DECISION_APPROVED and tally.approvals <= tally.rejections:
            raise DecisionNotAllowed(
                "Maioria simples não atingida: aprovações não superam rejeições."
            )
