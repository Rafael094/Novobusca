"use client";

import { useState } from "react";

import {
  Badge,
  Button,
  EmptyState,
  ErrorNote,
  Input,
  Modal,
  Select,
  Spinner,
  Textarea,
} from "@/components/ui";
import {
  useCreateNitEvaluation,
  useNitEvaluations,
} from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";

const KIND_LABELS: Record<string, string> = {
  TECHNICAL: "Técnico",
  LEGAL: "Jurídico",
  COMMERCIAL: "Comercial",
};

const OUTCOME_TONES: Record<string, "green" | "red" | "amber" | "slate"> = {
  FAVORABLE: "green",
  UNFAVORABLE: "red",
  CONDITIONAL: "amber",
  PENDING: "slate",
};

/** Evaluations (pareceres) panel: list + registration form for authorized users. */
export function EvaluationsPanel({ disclosureId }: { disclosureId: string }) {
  const { has } = useAuth();
  const { data, isLoading, error } = useNitEvaluations(disclosureId);
  const [openNew, setOpenNew] = useState(false);

  const canCreate = has("NIT_EVALUATION_CREATE");

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-slate-700">Pareceres registrados</p>
        {canCreate && <Button onClick={() => setOpenNew(true)}>Novo parecer</Button>}
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}
      {isLoading ? (
        <Spinner />
      ) : data && data.length > 0 ? (
        <ul className="space-y-3">
          {data.map((e) => (
            <li
              key={e.id}
              className="rounded-lg border border-gray-100 px-4 py-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="blue">{KIND_LABELS[e.kind] || e.kind}</Badge>
                <Badge tone={OUTCOME_TONES[e.outcome] || "slate"}>
                  {e.outcome}
                </Badge>
                {e.trl_level ? (
                  <Badge tone="slate">TRL {e.trl_level}</Badge>
                ) : null}
              </div>
              {e.summary && (
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-700">
                  {e.summary}
                </p>
              )}
              <p className="mt-1 text-xs text-slate-400">
                {new Date(e.created_at).toLocaleString("pt-BR")}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState title="Nenhum parecer registrado" />
      )}

      <NewEvaluationModal
        disclosureId={disclosureId}
        open={openNew}
        onClose={() => setOpenNew(false)}
      />
    </div>
  );
}

function NewEvaluationModal({
  disclosureId,
  open,
  onClose,
}: {
  disclosureId: string;
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateNitEvaluation(disclosureId);
  const [kind, setKind] = useState("TECHNICAL");
  const [outcome, setOutcome] = useState("PENDING");
  const [summary, setSummary] = useState("");
  const [risks, setRisks] = useState("");
  const [recommendations, setRecommendations] = useState("");
  const [trl, setTrl] = useState("");

  function submit() {
    create.mutate(
      {
        kind,
        outcome,
        summary: summary || null,
        risks: risks || null,
        recommendations: recommendations || null,
        trl_level: trl ? Number(trl) : null,
      },
      {
        onSuccess: () => {
          setSummary("");
          setRisks("");
          setRecommendations("");
          setTrl("");
          onClose();
        },
      },
    );
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Registrar parecer"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button onClick={submit} disabled={create.isPending}>
            {create.isPending ? "Salvando…" : "Registrar"}
          </Button>
        </>
      }
    >
      {create.error ? (
        <div className="mb-3">
          <ErrorNote>{(create.error as Error).message}</ErrorNote>
        </div>
      ) : null}
      <div className="space-y-3">
        <Select label="Tipo" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="TECHNICAL">Técnico</option>
          <option value="LEGAL">Jurídico</option>
          <option value="COMMERCIAL">Comercial</option>
        </Select>
        <Select
          label="Resultado"
          value={outcome}
          onChange={(e) => setOutcome(e.target.value)}
        >
          <option value="PENDING">Pendente</option>
          <option value="FAVORABLE">Favorável</option>
          <option value="CONDITIONAL">Condicional</option>
          <option value="UNFAVORABLE">Desfavorável</option>
        </Select>
        <Textarea
          label="Parecer"
          rows={4}
          value={summary}
          onChange={(e) => setSummary(e.target.value)}
        />
        <Textarea
          label="Riscos identificados"
          rows={2}
          value={risks}
          onChange={(e) => setRisks(e.target.value)}
        />
        <Textarea
          label="Recomendações"
          rows={2}
          value={recommendations}
          onChange={(e) => setRecommendations(e.target.value)}
        />
        <Input
          label="TRL (1–9, opcional)"
          type="number"
          min={1}
          max={9}
          value={trl}
          onChange={(e) => setTrl(e.target.value)}
        />
      </div>
    </Modal>
  );
}
