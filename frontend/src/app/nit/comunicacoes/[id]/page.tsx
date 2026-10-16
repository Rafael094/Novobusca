"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Spinner,
  Tabs,
  statusTone,
} from "@/components/ui";
import { useNitDisclosure } from "@/lib/hooks";
import { WorkflowPanel } from "./WorkflowPanel";
import { EvaluationsPanel } from "./EvaluationsPanel";
import { DocumentsPanel } from "./DocumentsPanel";

const STATUS_LABELS: Record<string, string> = {
  PROPOSAL: "Proposta",
  TRIAGE: "Triagem",
  EVALUATION: "Avaliação",
  DECISION: "Decisão",
  CLOSED: "Encerrado",
  REJECTED: "Rejeitado",
};

export default function DisclosureDossierPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? null;
  const { data, isLoading, error } = useNitDisclosure(id);
  const [tab, setTab] = useState("info");

  return (
    <AppShell>
      <div className="mb-4">
        <Link
          href="/nit/comunicacoes"
          className="text-sm text-brand-700 hover:underline"
        >
          ← Voltar para comunicações
        </Link>
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}
      {isLoading ? <Spinner /> : null}

      {data ? (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                {data.protocol}
              </p>
              <h1 className="text-2xl font-bold text-slate-800">{data.title}</h1>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={statusTone(data.status)}>
                {STATUS_LABELS[data.status] || data.status}
              </Badge>
              <Badge tone="slate">{data.confidentiality_level}</Badge>
            </div>
          </div>

          <Card>
            <Tabs
              tabs={[
                { id: "info", label: "Dossiê" },
                { id: "workflow", label: "Workflow" },
                { id: "evaluations", label: "Pareceres" },
                { id: "documents", label: "Documentos" },
              ]}
              active={tab}
              onChange={setTab}
            />

            <CardBody>
              {tab === "info" ? <InfoTab data={data} /> : null}
              {tab === "workflow" ? <WorkflowPanel disclosureId={data.id} /> : null}
              {tab === "evaluations" ? (
                <EvaluationsPanel disclosureId={data.id} />
              ) : null}
              {tab === "documents" ? (
                <DocumentsPanel disclosureId={data.id} />
              ) : null}
            </CardBody>
          </Card>
        </>
      ) : null}
    </AppShell>
  );
}

function InfoTab({
  data,
}: {
  data: {
    summary: string | null;
    description: string | null;
    context: string | null;
    technology_area: string | null;
    keywords: string | null;
    submitted_at: string;
    inventors: { id: string; name: string; kind: string; institution: string | null }[];
  };
}) {
  return (
    <div className="space-y-5">
      <Field label="Resumo" value={data.summary} />
      <Field label="Descrição" value={data.description} />
      <Field label="Contexto" value={data.context} />
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Área tecnológica" value={data.technology_area} />
        <Field label="Palavras-chave" value={data.keywords} />
        <Field
          label="Submetida em"
          value={new Date(data.submitted_at).toLocaleString("pt-BR")}
        />
      </div>

      <div>
        <p className="mb-2 text-sm font-medium text-slate-700">Inventores</p>
        {data.inventors.length === 0 ? (
          <EmptyState title="Sem inventores registrados" />
        ) : (
          <ul className="space-y-1">
            {data.inventors.map((i) => (
              <li
                key={i.id}
                className="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2 text-sm"
              >
                <span className="text-slate-700">{i.name}</span>
                <Badge tone={i.kind === "EXTERNAL" ? "amber" : "blue"}>
                  {i.kind === "EXTERNAL" ? "Externo" : "Interno"}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <p className="mt-0.5 whitespace-pre-wrap text-sm text-slate-700">
        {value || "—"}
      </p>
    </div>
  );
}
