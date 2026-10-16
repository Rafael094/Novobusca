"""Workflow engine for the NIT process (decisions E1/E2/E4).

Rules (enforced here, never inferred from the client):

* Only edges declared in ``WorkflowTransition`` for the tenant are allowed.
* An edge may require a permission (``required_permission``) and/or a role
  (``required_role_code``) — an undeclared or unauthorized edge is rejected.
* A transition requiring a justification is rejected without one.
* Optimistic concurrency: the caller passes the ``version`` it read; a mismatch
  raises :class:`WorkflowConflict` (HTTP 409) to prevent duplicate transitions.
* Every accepted transition appends an immutable ``WorkflowHistory`` row.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.nit import (
    TERMINAL_STATES,
    WorkflowHistory,
    WorkflowInstance,
    WorkflowTransition,
)
from app.rbac import AccessContext


class WorkflowError(Exception):
    """Base class for workflow rule violations (mapped to HTTP 4xx by callers)."""


class InvalidTransition(WorkflowError):
    """The requested edge does not exist in the tenant's workflow."""


class TransitionNotAllowed(WorkflowError):
    """The actor lacks the required permission/role for the edge."""


class JustificationRequired(WorkflowError):
    """The edge mandates a justification that was not supplied."""


class WorkflowConflict(WorkflowError):
    """The instance version changed (optimistic concurrency) — retry."""


class WorkflowClosed(WorkflowError):
    """The workflow is already in a terminal state."""


@dataclass(frozen=True)
class TransitionResult:
    instance: WorkflowInstance
    from_state: str | None
    to_state: str
    version: int


def available_transitions(
    db: Session, *, tenant_id: uuid.UUID, from_state: str
) -> list[WorkflowTransition]:
    return list(
        db.execute(
            select(WorkflowTransition)
            .where(
                WorkflowTransition.tenant_id == tenant_id,
                WorkflowTransition.from_state == from_state,
                WorkflowTransition.active.is_(True),
            )
            .order_by(WorkflowTransition.sort_order)
        ).scalars()
    )


def _authorize(ctx: AccessContext, transition: WorkflowTransition) -> None:
    """Raise :class:`TransitionNotAllowed` unless the actor may use the edge."""
    # A user is always allowed to act on their own behalf only via a declared edge
    # with no authority requirement; otherwise the declared requirements apply.
    if transition.required_permission and not ctx.has_permission(
        transition.required_permission
    ):
        raise TransitionNotAllowed(
            f"Permissão necessária para esta transição: {transition.required_permission}"
        )
    if transition.required_role_code:
        # A declared role requirement is authoritative: BOTH the permission (if
        # any) and the role must be present. A holding role never bypasses it
        # unless it is in the actor's effective roles.
        if transition.required_role_code not in ctx.roles:
            raise TransitionNotAllowed(
                "Papel necessário para esta transição: "
                f"{transition.required_role_code}"
            )


def apply_transition(
    db: Session,
    *,
    ctx: AccessContext,
    instance: WorkflowInstance,
    to_state: str,
    justification: str | None,
    expected_version: int | None,
) -> TransitionResult:
    """Validate and apply a transition, appending immutable history.

    The caller is responsible for the outer transaction/commit. On success the
    instance version is incremented and a ``WorkflowHistory`` row is added.
    """
    if instance.current_state in TERMINAL_STATES:
        raise WorkflowClosed(
            "O processo está encerrado e não aceita novas transições."
        )

    if expected_version is not None and instance.version != expected_version:
        raise WorkflowConflict(
            "O processo foi alterado por outra operação. Recarregue e tente novamente."
        )

    edge = db.execute(
        select(WorkflowTransition).where(
            WorkflowTransition.tenant_id == instance.tenant_id,
            WorkflowTransition.from_state == instance.current_state,
            WorkflowTransition.to_state == to_state,
            WorkflowTransition.active.is_(True),
        )
    ).scalar_one_or_none()
    if edge is None:
        raise InvalidTransition(
            f"Transição inválida: {instance.current_state} → {to_state}."
        )

    _authorize(ctx, edge)

    if edge.requires_justification and not (justification and justification.strip()):
        raise JustificationRequired("Esta transição exige justificativa.")

    from_state = instance.current_state
    instance.current_state = to_state
    instance.version = instance.version + 1
    history = WorkflowHistory(
        tenant_id=instance.tenant_id,
        instance_id=instance.id,
        disclosure_id=instance.disclosure_id,
        from_state=from_state,
        to_state=to_state,
        actor_id=ctx.user.id,
        justification=(justification or None),
        version=instance.version,
    )
    db.add(history)
    db.flush()
    return TransitionResult(
        instance=instance, from_state=from_state, to_state=to_state, version=instance.version
    )
