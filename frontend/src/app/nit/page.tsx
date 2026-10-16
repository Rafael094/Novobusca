"use client";

import Link from "next/link";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Spinner,
} from "@/components/ui";
import { useNitDashboard } from "@/lib/hooks";

/** NIT operational dashboard — every number comes from real API queries. */
export default function NitDashboardPage() {
  const { data, isLoading, error } = useNitDashboard();

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Painel do NIT</h1>
        <p className="text-sm text-slate-500">
          Indicadores operacionais do Núcleo de Inovação Tecnológica.
        </p>
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}

      {isLoading ? (
        <Spinner />
      ) : data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="Comunicações" value={data.disclosure_total} />
            <Metric label="Ativos institucionais" value={data.assets_total} />
            <Metric label="Documentos" value={data.documents_total} />
            <Metric
              label="Novas (30 dias)"
              value={data.disclosure_created_last_30_days}
            />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader
                title="Comunicações por etapa"
                subtitle="Distribuição atual do workflow"
              />
              <CardBody>
                <Breakdown rows={data.disclosures_by_status} />
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Ativos por tipo"
                subtitle="Composição do portfólio institucional"
              />
              <CardBody>
                <Breakdown rows={data.assets_by_type} />
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Áreas tecnológicas"
                subtitle="Comunicações por área declarada"
              />
              <CardBody>
                <Breakdown rows={data.disclosures_by_area} />
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Pareceres"
                subtitle="Avaliações registradas e pendentes"
              />
              <CardBody>
                <div className="flex items-center gap-4">
                  <BigNumber label="Total" value={data.evaluations_total} />
                  <BigNumber
                    label="Pendentes"
                    value={data.pending_evaluations}
                  />
                </div>
              </CardBody>
            </Card>
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/nit/comunicacoes"
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              Ver comunicações
            </Link>
            <Link
              href="/nit/ativos"
              className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Ver portfólio
            </Link>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardBody>
        <p className="text-sm text-slate-500">{label}</p>
        <p className="mt-1 text-3xl font-bold text-slate-800">{value}</p>
      </CardBody>
    </Card>
  );
}

function BigNumber({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <p className="text-3xl font-bold text-slate-800">{value}</p>
      <p className="text-sm text-slate-500">{label}</p>
    </div>
  );
}

function Breakdown({ rows }: { rows: Record<string, number> }) {
  const entries = Object.entries(rows).sort((a, b) => b[1] - a[1]);
  if (entries.length === 0) {
    return <EmptyState title="Sem dados" description="Nenhum registro ainda." />;
  }
  const total = entries.reduce((acc, [, v]) => acc + v, 0) || 1;
  return (
    <div className="space-y-2">
      {entries.map(([key, value]) => (
        <div key={key} className="flex items-center gap-3">
          <span className="w-40 shrink-0 truncate text-sm text-slate-600">
            {key}
          </span>
          <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
            <span
              className="block h-full rounded-full bg-brand-500"
              style={{ width: `${Math.round((value / total) * 100)}%` }}
            />
          </span>
          <Badge tone="slate">{value}</Badge>
        </div>
      ))}
    </div>
  );
}
