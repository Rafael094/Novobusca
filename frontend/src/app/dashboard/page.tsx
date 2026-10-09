"use client";

import Link from "next/link";

import AppShell from "@/components/AppShell";
import { DonutChart, LineChart } from "@/components/charts";
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  ErrorNote,
  Spinner,
} from "@/components/ui";
import { useDashboard } from "@/lib/hooks";

type Tone = "brand" | "green" | "amber" | "red" | "slate";

const STAT_STYLES: Record<Tone, { bg: string; text: string }> = {
  brand: { bg: "bg-brand-50", text: "text-brand-700" },
  green: { bg: "bg-emerald-50", text: "text-emerald-600" },
  amber: { bg: "bg-amber-50", text: "text-amber-600" },
  red: { bg: "bg-red-50", text: "text-red-600" },
  slate: { bg: "bg-slate-100", text: "text-slate-700" },
};

function StatCard({
  label,
  value,
  tone = "brand",
  icon,
}: {
  label: string;
  value: number | string;
  tone?: Tone;
  icon: string;
}) {
  const s = STAT_STYLES[tone];
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-slate-500">{label}</p>
          <p className={`mt-1 text-3xl font-bold ${s.text}`}>
            {typeof value === "number" ? value.toLocaleString("pt-BR") : value}
          </p>
        </div>
        <span
          className={`flex h-11 w-11 items-center justify-center rounded-xl text-xl ${s.bg}`}
        >
          {icon}
        </span>
      </div>
    </Card>
  );
}

export default function DashboardPage() {
  const { data, isLoading, error } = useDashboard();

  const evolution = data?.portfolio_evolution ?? [];
  const lines = [
    { name: "Marcas", color: "#2563eb", values: evolution.map((e) => e.marcas) },
    { name: "Patentes", color: "#f59e0b", values: evolution.map((e) => e.patentes) },
  ];

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Visão Geral</h1>
          <p className="text-sm text-slate-500">
            Panorama do portfólio de marcas e patentes.
          </p>
        </div>
        <Link
          href="/analises"
          className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          + Nova Análise IA
        </Link>
      </div>

      {isLoading && <Spinner />}
      {error && (
        <ErrorNote>
          {error instanceof Error ? error.message : "Erro ao carregar."}
        </ErrorNote>
      )}

      {data && (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Clientes"
              value={data.customers ?? data.users}
              tone="brand"
              icon="👥"
            />
            <StatCard
              label="Marcas monitoradas"
              value={data.marcas}
              tone="green"
              icon="®"
            />
            <StatCard label="Patentes" value={data.patentes} tone="slate" icon="📄" />
            <StatCard
              label="Alertas críticos"
              value={(data.upcoming_deadlines ?? []).filter(
                (d) => (d.dias_restantes ?? 999) <= 90,
              ).length}
              tone="red"
              icon="⚠"
            />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader
                title="Evolução do portfólio"
                subtitle="Depósitos por ano — Marcas vs Patentes"
              />
              <CardBody>
                {evolution.length > 0 ? (
                  <LineChart
                    labels={evolution.map((e) => String(e.ano))}
                    series={lines}
                  />
                ) : (
                  <p className="py-8 text-center text-sm text-slate-400">
                    Sem dados de depósito importados.
                  </p>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Situação das marcas" subtitle="Distribuição geral" />
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

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title="Últimos eventos do INPI" />
              <CardBody className="space-y-3">
                {(data.latest_events ?? []).map((e, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between border-b border-gray-50 pb-2 last:border-0"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-700">
                        {e.titulo}
                      </p>
                      <p className="text-xs text-slate-400">{e.numero_inpi || "—"}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge tone={e.tipo === "marca" ? "blue" : "slate"}>
                        {e.tipo}
                      </Badge>
                      <span className="text-xs text-slate-400">
                        {e.data ? new Date(e.data).toLocaleDateString("pt-BR") : "—"}
                      </span>
                    </div>
                  </div>
                ))}
                {(data.latest_events ?? []).length === 0 && (
                  <p className="py-4 text-center text-sm text-slate-400">
                    Nenhum evento recente.
                  </p>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader title="Próximos prazos" subtitle="Vigências mais próximas" />
              <CardBody className="space-y-3">
                {(data.upcoming_deadlines ?? []).map((d, i) => {
                  const dias = d.dias_restantes ?? 0;
                  const tone = dias <= 90 ? "red" : dias <= 365 ? "amber" : "green";
                  return (
                    <div
                      key={i}
                      className="flex items-center justify-between border-b border-gray-50 pb-2 last:border-0"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-700">
                          {d.titulo}
                        </p>
                        <p className="text-xs text-slate-400">
                          {d.data_vigencia
                            ? new Date(d.data_vigencia).toLocaleDateString("pt-BR")
                            : "—"}
                        </p>
                      </div>
                      <Badge tone={tone}>{dias} dias</Badge>
                    </div>
                  );
                })}
                {(data.upcoming_deadlines ?? []).length === 0 && (
                  <p className="py-4 text-center text-sm text-slate-400">
                    Nenhum prazo futuro cadastrado.
                  </p>
                )}
              </CardBody>
            </Card>
          </div>

          <Card className="mt-6">
            <CardHeader title="Módulos habilitados" />
            <CardBody className="flex flex-wrap gap-2">
              {data.modules.map((m) => (
                <Badge key={m} tone="blue">
                  {m}
                </Badge>
              ))}
              {data.modules.length === 0 && (
                <span className="text-sm text-slate-400">
                  Nenhum módulo atribuído.
                </span>
              )}
            </CardBody>
          </Card>
        </>
      )}
    </AppShell>
  );
}
