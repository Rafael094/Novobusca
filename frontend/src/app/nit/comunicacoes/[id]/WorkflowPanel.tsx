"use client";

import { useState } from "react";

import {
  Badge,
  Button,
  EmptyState,
  ErrorNote,
  Modal,
  Spinner,
  Textarea,
} from "@/components/ui";
import { useNitTransition, useNitWorkflow } from "@/lib/hooks";
import type { NitWorkflowTransition } from "@/lib/types";

const STATE_LABELS: Record<string, string> = {
  PROPOSAL: "Proposta",
  TRIAGE: "Triagem",
  EVALUATION: "Avaliação",
  DECISION: "Decisão",
  CLOSED: "Encerrado",
  REJECTED: "Rejeitado",
};

/** Workflow panel: current state, permitted transitions and immutable history. */
export function WorkflowPanel({ disclosureId }: { disclosureId: string }) {
  const { data, isLoading, error } = useNitWorkflow(disclosureId);
  const [pending, setPending] = useState<NitWorkflowTransition | null>(null);

  if (isLoading) return <Spinner />;
  if (error) return <ErrorNote>{(error as Error).message}</ErrorNote>;
  if (!data) return null;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <span className="text-sm text-slate-500">Etapa atual:</span>
        <Badge tone="blue">
          {data.current_state_name || STATE_LABELS[data.current_state]}
        </Badge>
        <span className="text-xs text-slate-400">versão {data.version}</span>
      </div>

      <div>
        <p className="mb-2 text-sm font-medium text-slate-700">
          Transições disponíveis
        </p>
        {data.is_terminal || data.available_transitions.length === 0 ? (
          <EmptyState
            title="Processo sem transições disponíveis"
            description={
              data.is_terminal
                ? "O processo está encerrado."
                : "Seu perfil pode não ter alçada para as próximas etapas."
            }
          />
        ) : (
          <div className="flex flex-wrap gap-2">
            {data.available_transitions.map((t) => (
              <Button
                key={t.id}
                variant="secondary"
                onClick={() => setPending(t)}
              >
                {t.name}
              </Button>
            ))}
          </div>
        )}
      </div>

      <div>
        <p className="mb-2 text-sm font-medium text-slate-700">Histórico</p>
        {data.history.length === 0 ? (
          <EmptyState title="Sem movimentações" />
        ) : (
          <ol className="space-y-3 border-l border-gray-100 pl-4">
            {data.history.map((h) => (
              <li key={h.id} className="text-sm">
                <p className="text-slate-700">
                  {h.from_state
                    ? `${STATE_LABELS[h.from_state] || h.from_state} → `
                    : ""}
                  <span className="font-medium">
                    {STATE_LABELS[h.to_state] || h.to_state}
                  </span>
                </p>
                {h.justification && (
                  <p className="text-slate-500">{h.justification}</p>
                )}
                <p className="text-xs text-slate-400">
                  {new Date(h.created_at).toLocaleString("pt-BR")}
                </p>
              </li>
            ))}
          </ol>
        )}
      </div>

      <TransitionModal
        disclosureId={disclosureId}
        transition={pending}
        version={data.version}
        onClose={() => setPending(null)}
      />
    </div>
  );
}

function TransitionModal({
  disclosureId,
  transition,
  version,
  onClose,
}: {
  disclosureId: string;
  transition: NitWorkflowTransition | null;
  version: number;
  onClose: () => void;
}) {
  const mutate = useNitTransition(disclosureId);
  const [justification, setJustification] = useState("");
  const requiresJustification = transition?.requires_justification ?? false;

  if (!transition) return null;

  return (
    <Modal
      open={!!transition}
      onClose={onClose}
      title={transition.name}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={
              mutate.isPending ||
              (requiresJustification && !justification.trim())
            }
            onClick={() =>
              mutate.mutate(
                {
                  to_state: transition.to_state,
                  justification: justification || undefined,
                  expected_version: version,
                },
                {
                  onSuccess: () => {
                    setJustification("");
                    onClose();
                  },
                },
              )
            }
          >
            {mutate.isPending ? "Aplicando…" : "Confirmar"}
          </Button>
        </>
      }
    >
      {mutate.error ? (
        <div className="mb-3">
          <ErrorNote>{(mutate.error as Error).message}</ErrorNote>
        </div>
      ) : null}
      <Textarea
        label={
          requiresJustification
            ? "Justificativa (obrigatória)"
            : "Justificativa (opcional)"
        }
        rows={3}
        value={justification}
        onChange={(e) => setJustification(e.target.value)}
      />
    </Modal>
  );
}
