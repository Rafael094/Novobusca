"""Idempotent NIT workflow seed (decisions E1/E2/E4).

Creates the default workflow states and transitions for a tenant. The workflow is
data (not code), so an institution can adjust it later without a migration.

Default flow::

    PROPOSAL ──triage──▶ TRIAGE ──parecer──▶ EVALUATION ──decisão──▶ DECISION ──▶ CLOSED
        │                    │                     │                     │
        └──rejeitar──────────┴──rejeitar───────────┴──rejeitar───────────┘──▶ REJECTED

Authority is explicit per edge: triage requires ``NIT_WORKFLOW_TRIAGE``, the
parecer step requires ``NIT_EVALUATION_CREATE``, decision requires ``NIT_DECISION``.
Rejection edges require the same authority as the stage they leave.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.nit import (
    WF_CLOSED,
    WF_DECISION,
    WF_EVALUATION,
    WF_PROPOSAL,
    WF_REJECTED,
    WF_TRIAGE,
    WorkflowState,
    WorkflowTransition,
)

# (code, name, description, sort_order, is_initial, is_terminal)
_DEFAULT_STATES: list[tuple[str, str, str, int, bool, bool]] = [
    (WF_PROPOSAL, "Proposta", "Comunicação registrada, aguardando triagem", 0, True, False),
    (WF_TRIAGE, "Triagem", "Verificação de completude e enquadramento", 1, False, False),
    (WF_EVALUATION, "Avaliação", "Pareceres técnico, jurídico e comercial", 2, False, False),
    (WF_DECISION, "Decisão", "Decisão da instância competente", 3, False, False),
    (WF_CLOSED, "Encerrado", "Processo concluído", 4, False, True),
    (WF_REJECTED, "Rejeitado", "Processo encerrado sem prosseguimento", 5, False, True),
]

# (from_state, to_state, name, required_permission, requires_justification)
_DEFAULT_TRANSITIONS: list[tuple[str, str, str, str | None, bool]] = [
    (WF_PROPOSAL, WF_TRIAGE, "Iniciar triagem", "NIT_WORKFLOW_TRIAGE", False),
    (WF_TRIAGE, WF_EVALUATION, "Enviar para avaliação", "NIT_WORKFLOW_TRIAGE", False),
    (WF_TRIAGE, WF_PROPOSAL, "Devolver ao proponente", "NIT_WORKFLOW_TRIAGE", True),
    (WF_EVALUATION, WF_DECISION, "Encaminhar para decisão", "NIT_EVALUATION_CREATE", False),
    (WF_EVALUATION, WF_TRIAGE, "Devolver à triagem", "NIT_EVALUATION_CREATE", True),
    (WF_DECISION, WF_CLOSED, "Aprovar e encerrar", "NIT_DECISION", True),
    (WF_DECISION, WF_REJECTED, "Rejeitar", "NIT_DECISION", True),
    (WF_PROPOSAL, WF_REJECTED, "Rejeitar na triagem", "NIT_WORKFLOW_TRIAGE", True),
    (WF_TRIAGE, WF_REJECTED, "Rejeitar na triagem", "NIT_WORKFLOW_TRIAGE", True),
    (WF_EVALUATION, WF_REJECTED, "Rejeitar após avaliação", "NIT_EVALUATION_CREATE", True),
]


def seed_tenant_workflow(db: Session, tenant_id: uuid.UUID) -> None:
    """Create/refresh the default workflow for ``tenant_id`` (idempotent)."""
    existing_states = {
        s.code
        for s in db.execute(
            select(WorkflowState).where(WorkflowState.tenant_id == tenant_id)
        ).scalars()
    }
    for code, name, description, order, is_initial, is_terminal in _DEFAULT_STATES:
        if code in existing_states:
            continue
        db.add(
            WorkflowState(
                tenant_id=tenant_id,
                code=code,
                name=name,
                description=description,
                sort_order=order,
                is_initial=is_initial,
                is_terminal=is_terminal,
                active=True,
            )
        )
    db.flush()

    existing_edges = {
        (t.from_state, t.to_state)
        for t in db.execute(
            select(WorkflowTransition).where(
                WorkflowTransition.tenant_id == tenant_id
            )
        ).scalars()
    }
    for order, (frm, to, name, perm, justify) in enumerate(_DEFAULT_TRANSITIONS):
        if (frm, to) in existing_edges:
            continue
        db.add(
            WorkflowTransition(
                tenant_id=tenant_id,
                from_state=frm,
                to_state=to,
                name=name,
                required_permission=perm,
                required_role_code=None,
                requires_justification=justify,
                sort_order=order,
                active=True,
            )
        )
    db.flush()
