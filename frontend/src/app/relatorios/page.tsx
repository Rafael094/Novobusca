"use client";

/**
 * Relatórios — consolidated indicators.
 *
 * Two clearly separated blocks, so no number is ever misread as "my clients":
 *
 * * **Minha operação (tenant)** — commercial counters scoped to the caller's
 *   tenant, from ``GET /api/dashboard/business``. This is "my clients".
 * * **Base pública do INPI** — the global trademark/patent counts, explicitly
 *   labelled as the shared public base (Master Admin reach), never presented as
 *   the tenant's own portfolio.
 */

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
import { useBusinessDashboard, useDashboard } from "@/lib/hooks";

export default function RelatoriosPage() {
  const { data, isLoading, error } = useDashboard();
  const {
    data: business,
    isLoading: isBusinessLoading,
    error: businessError,
  } = useBusinessDashboard(12);

  function exportCsv() {
    const rows: string[][] = [["Bloco", "Indicador", "Valor"]];
    if (business) {
      rows.push(["Minha operação", "Clientes ativos", String(business.counters.active_customers)]);
      rows.push(["Minha operação", "Clientes (total)", String(business.counters.total_customers)]);
      rows.push(["Minha operação", "Novos clientes (12m)", String(business.counters.new_customers_period)]);
      rows.push(["Minha operação", "Oportunidades abertas", String(business.counters.open_opportunities)]);
      rows.push(["Minha operação", "Propostas a enviar", String(business.counters.proposals_to_send)]);
      rows.push(["Minha operação", "Propostas aguardando retorno", String(business.counters.proposals_awaiting_reply)]);
      rows.push(["Minha operação", "Propostas aprovadas", String(business.counters.proposals_approved)]);
      rows.push(["Minha operação", "Marcas monitoradas", String(business.counters.monitored_marcas)]);
      rows.push(["Minha operação", "Patentes monitoradas", String(business.counters.monitored_patentes)]);
      rows.push(["Minha operação", "Alertas críticos", String(business.counters.critical_alerts)]);
    }
    if (data) {
      rows.push(["Base pública INPI", "Marcas", String(data.marcas)]);
      rows.push(["Base pública INPI", "Patentes", String(data.patentes)]);
    }
    const csv = rows
      .map((r) => r.map((c) => `"${c}"`).join(";"))
      .join("\n");
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "relatorio-intelliinpi.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const evolution = data?.portfolio_evolution ?? [];
  const c = business?.counters;

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Relatórios</h1>
          <p className="text-sm text-slate-500">
            Indicadores da sua operação e da base pública do INPI.
          </p>
        </div>
        <Button variant="secondary" onClick={exportCsv} disabled={!data && !business}>
          Exportar CSV
        </Button>
      </div>

      {/* Bloco 1 — Minha operação (tenant) */}
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Minha operação
      </h2>
      {isBusinessLoading && <Spinner />}
      {businessError && (
        <ErrorNote>
          {businessError instanceof Error
            ? businessError.message
            : "Erro ao carregar os indicadores da operação."}
        </ErrorNote>
      )}
      {c && (
        <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-5">
          <Metric label="Clientes ativos" value={c.active_customers} />
          <Metric label="Clientes (total)" value={c.total_customers} />
          <Metric label="Novos clientes (12m)" value={c.new_customers_period} />
          <Metric label="Oportunidades abertas" value={c.open_opportunities} />
          <Metric label="Propostas aprovadas" value={c.proposals_approved} />
          <Metric label="Propostas a enviar" value={c.proposals_to_send} />
          <Metric label="Aguardando retorno" value={c.proposals_awaiting_reply} />
          <Metric label="Marcas monitoradas" value={c.monitored_marcas} />
          <Metric label="Patentes monitoradas" value={c.monitored_patentes} />
          <Metric label="Alertas críticos" value={c.critical_alerts} />
        </div>
      )}

      {/* Bloco 2 — Base pública do INPI (global) */}
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Base pública do INPI
      </h2>

      {isLoading && <Spinner />}
      {error && (
        <ErrorNote>
          {error instanceof Error ? error.message : "Erro ao carregar."}
        </ErrorNote>
      )}

      {data && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="grid grid-cols-2 gap-4 lg:col-span-1">
            <Metric label="Marcas" value={data.marcas} hint="Base pública compartilhada" />
            <Metric label="Patentes" value={data.patentes} hint="Base pública compartilhada" />
          </div>

          <Card className="lg:col-span-2">
            <CardHeader
              title="Evolução do portfólio"
              subtitle="Depósitos por ano — base pública do INPI"
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
            <CardHeader
              title="Situação das marcas"
              subtitle="Distribuição na base pública do INPI"
            />
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

function Metric({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint?: string;
}) {
  return (
    <Card className="p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-bold text-brand-700">
        {value.toLocaleString("pt-BR")}
      </p>
      {hint && <p className="mt-1 text-[11px] text-slate-400">{hint}</p>}
    </Card>
  );
}
