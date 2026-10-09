"use client";

import AppShell from "@/components/AppShell";
import { DonutChart, LineChart } from "@/components/charts";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  ErrorNote,
  Spinner,
} from "@/components/ui";
import { useDashboard } from "@/lib/hooks";

export default function RelatoriosPage() {
  const { data, isLoading, error } = useDashboard();

  function exportCsv() {
    if (!data) return;
    const rows = [
      ["Indicador", "Valor"],
      ["Marcas", String(data.marcas)],
      ["Patentes", String(data.patentes)],
      ["Clientes", String(data.customers ?? 0)],
      ["Empresas", String(data.companies ?? 0)],
      ["Usuários", String(data.users)],
    ];
    const csv = rows.map((r) => r.join(";")).join("\n");
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "relatorio-intelliinpi.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const evolution = data?.portfolio_evolution ?? [];

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Relatórios</h1>
          <p className="text-sm text-slate-500">
            Indicadores consolidados do portfólio.
          </p>
        </div>
        <Button variant="secondary" onClick={exportCsv} disabled={!data}>
          Exportar CSV
        </Button>
      </div>

      {isLoading && <Spinner />}
      {error && (
        <ErrorNote>
          {error instanceof Error ? error.message : "Erro ao carregar."}
        </ErrorNote>
      )}

      {data && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="grid grid-cols-2 gap-4 lg:col-span-1">
            <Metric label="Marcas" value={data.marcas} />
            <Metric label="Patentes" value={data.patentes} />
            <Metric label="Clientes" value={data.customers ?? 0} />
            <Metric label="Empresas" value={data.companies ?? 0} />
          </div>

          <Card className="lg:col-span-2">
            <CardHeader
              title="Evolução do portfólio"
              subtitle="Depósitos por ano"
            />
            <CardBody>
              {evolution.length > 0 ? (
                <LineChart
                  labels={evolution.map((e) => String(e.ano))}
                  series={[
                    {
                      name: "Marcas",
                      color: "#2563eb",
                      values: evolution.map((e) => e.marcas),
                    },
                    {
                      name: "Patentes",
                      color: "#f59e0b",
                      values: evolution.map((e) => e.patentes),
                    },
                  ]}
                />
              ) : (
                <p className="py-8 text-center text-sm text-slate-400">
                  Sem dados de depósito importados.
                </p>
              )}
            </CardBody>
          </Card>

          <Card className="lg:col-span-3">
            <CardHeader title="Situação das marcas" />
            <CardBody>
              <DonutChart
                data={(data.situacao_distribution ?? []).map((s) => ({
                  label: s.label,
                  value: s.value,
                }))}
                centerLabel="marcas"
              />
            </CardBody>
          </Card>
        </div>
      )}
    </AppShell>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <Card className="p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-brand-700">
        {value.toLocaleString("pt-BR")}
      </p>
    </Card>
  );
}
