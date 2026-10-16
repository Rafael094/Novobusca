"use client";

import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  CardBody,
  EmptyState,
  ErrorNote,
  Spinner,
} from "@/components/ui";
import {
  useAdvanceNegotiation,
  useNitNegotiation,
  useNitNegotiations,
} from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";
import type { NitNegotiation } from "@/lib/types";

const STAGE_LABELS: Record<string, string> = {
  NEW: "Novo interesse",
  QUALIFICATION: "Qualificação",
  FIRST_CONTACT: "Contato inicial",
  TECHNICAL_DISCUSSION: "Discussão técnica",
  NEGOTIATION: "Negociação",
  APPROVAL: "Aprovação",
  CONTRACTING: "Contratação",
  CLOSED: "Encerrado",
};

export default function NitNegotiationsPage() {
  const { data, isLoading, error } = useNitNegotiations();
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Negociações</h1>
        <p className="text-sm text-slate-500">
          Pipeline de transferência tecnológica — etapas e histórico.
        </p>
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}
      {isLoading ? <Spinner /> : null}

      {data && data.length === 0 ? (
        <Card>
          <CardBody>
            <EmptyState
              title="Nenhuma negociação"
              description="Inicie uma negociação a partir de uma manifestação de interesse."
            />
          </CardBody>
        </Card>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-2 space-y-2">
          {data?.map((neg) => (
            <button
              key={neg.id}
              onClick={() => setSelected(neg.id)}
              className={`w-full rounded-lg border px-4 py-3 text-left transition ${
                selected === neg.id
                  ? "border-brand-500 bg-brand-50"
                  : "border-gray-100 hover:bg-slate-50"
              }`}
            >
              <p className="text-sm font-medium text-slate-700">
                {STAGE_LABELS[neg.stage] || neg.stage}
              </p>
              <p className="text-xs text-slate-400">
                v{neg.version} · {new Date(neg.created_at).toLocaleDateString("pt-BR")}
              </p>
            </button>
          ))}
        </div>
        <div className="lg:col-span-3">
          {selected ? (
            <NegotiationDetail id={selected} />
          ) : (
            <Card>
              <CardBody>
                <EmptyState title="Selecione uma negociação" />
              </CardBody>
            </Card>
          )}
        </div>
      </div>
    </AppShell>
  );
}

function NegotiationDetail({ id }: { id: string }) {
  const { has } = useAuth();
  const { data, isLoading } = useNitNegotiation(id);
  const advance = useAdvanceNegotiation(id);
  const canManage = has("NIT_NEGOTIATION_MANAGE");

  if (isLoading) return <Spinner />;
  if (!data) return null;

  return (
    <Card>
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="blue">{data.stage_label || STAGE_LABELS[data.stage]}</Badge>
          <span className="text-xs text-slate-400">versão {data.version}</span>
        </div>

        {canManage && data.allowed_next.length > 0 ? (
          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">
              Avançar para
            </p>
            <div className="flex flex-wrap gap-2">
              {data.allowed_next.map((stage) => (
                <Button
                  key={stage}
                  variant="secondary"
                  disabled={advance.isPending}
                  onClick={() =>
                    advance.mutate({
                      to_stage: stage,
                      expected_version: data.version,
                    })
                  }
                >
                  {STAGE_LABELS[stage] || stage}
                </Button>
              ))}
            </div>
          </div>
        ) : null}

        {advance.error ? (
          <ErrorNote>{(advance.error as Error).message}</ErrorNote>
        ) : null}

        <div>
          <p className="mb-2 text-sm font-medium text-slate-700">Histórico</p>
          {data.history.length === 0 ? (
            <EmptyState title="Sem movimentações" />
          ) : (
            <ol className="space-y-2 border-l border-gray-100 pl-4 text-sm">
              {data.history.map((h) => (
                <li key={h.id}>
                  <p className="text-slate-700">
                    {h.from_stage
                      ? `${STAGE_LABELS[h.from_stage] || h.from_stage} → `
                      : ""}
                    <span className="font-medium">
                      {STAGE_LABELS[h.to_stage] || h.to_stage}
                    </span>
                  </p>
                  <p className="text-xs text-slate-400">
                    {new Date(h.created_at).toLocaleString("pt-BR")}
                  </p>
                </li>
              ))}
            </ol>
          )}
        </div>
      </CardBody>
    </Card>
  );
}
