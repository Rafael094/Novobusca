"use client";

import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Input,
  Spinner,
} from "@/components/ui";
import { useAuth } from "@/app/auth-context";
import {
  useCreateSavedReport,
  useNitBiMetrics,
  useNitSavedReports,
  useRunSavedReport,
} from "@/lib/hooks";
import { metricLabel } from "@/lib/nitBi";

export default function BiPage() {
  const { has } = useAuth();
  const { data: metrics } = useNitBiMetrics();
  const { data: reports, isLoading, error } = useNitSavedReports();
  const create = useCreateSavedReport();
  const run = useRunSavedReport();

  const canManage = has("NIT_BI_MANAGE");
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [result, setResult] = useState<Record<string, unknown> | null>(null);

  const chosen = Object.entries(selected)
    .filter(([, v]) => v)
    .map(([k]) => k);

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">BI & Relatórios</h1>
        <p className="text-sm text-slate-500">
          Relatórios somente selecionam métricas reais. Nenhum valor é estimado ou
          inventado — quando não há dados, o campo é nulo.
        </p>
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}

      {canManage ? (
        <Card className="mb-6">
          <CardHeader title="Novo relatório" subtitle="Escolha as métricas reais" />
          <CardBody>
            <div className="mb-3">
              <Input label="Nome" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="mb-4 grid gap-2 sm:grid-cols-3">
              {metrics?.map((m) => (
                <label key={m} className="flex items-center gap-2 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    checked={!!selected[m]}
                    onChange={(e) => setSelected({ ...selected, [m]: e.target.checked })}
                  />
                  {metricLabel(m)}
                </label>
              ))}
            </div>
            {create.error ? (
              <div className="mb-3">
                <ErrorNote>{(create.error as Error).message}</ErrorNote>
              </div>
            ) : null}
            <Button
              disabled={!name.trim() || chosen.length === 0 || create.isPending}
              onClick={() =>
                create.mutate(
                  { name, metrics: chosen },
                  {
                    onSuccess: () => {
                      setName("");
                      setSelected({});
                    },
                  },
                )
              }
            >
              Criar relatório
            </Button>
          </CardBody>
        </Card>
      ) : null}

      {isLoading ? <Spinner /> : null}

      <div className="grid gap-4 md:grid-cols-2">
        {reports?.length === 0 ? (
          <Card>
            <CardBody>
              <EmptyState title="Nenhum relatório salvo" />
            </CardBody>
          </Card>
        ) : null}
        {reports?.map((r) => (
          <Card key={r.id}>
            <CardHeader title={r.name} subtitle={`${r.metrics.length} métrica(s)`} />
            <CardBody>
              <div className="mb-3 flex flex-wrap gap-1">
                {r.metrics.map((m) => (
                  <Badge key={m} tone="slate">
                    {metricLabel(m)}
                  </Badge>
                ))}
              </div>
              <div className="flex gap-2">
                <Button
                  variant="secondary"
                  disabled={run.isPending}
                  onClick={() =>
                    run.mutate(
                      { id: r.id },
                      { onSuccess: (data) => setResult(data.result) },
                    )
                  }
                >
                  Executar
                </Button>
                <Button
                  variant="ghost"
                  onClick={() =>
                    window.open(`/api/nit/bi/reports/${r.id}/export`, "_blank")
                  }
                >
                  Exportar CSV
                </Button>
              </div>
            </CardBody>
          </Card>
        ))}
      </div>

      {result ? (
        <Card className="mt-6">
          <CardHeader title="Resultado da execução" subtitle="Consulta real" />
          <CardBody>
            <ul className="divide-y divide-gray-50">
              {Object.entries(result).map(([k, v]) => (
                <li key={k} className="flex justify-between py-1.5 text-sm">
                  <span className="text-slate-500">{metricLabel(k)}</span>
                  <span className="font-medium text-slate-800">
                    {typeof v === "object" && v !== null ? JSON.stringify(v) : String(v)}
                  </span>
                </li>
              ))}
            </ul>
          </CardBody>
        </Card>
      ) : null}
    </AppShell>
  );
}
