"use client";

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
} from "@/components/ui";
import { useNitPortfolio, useNitPortfolioAlerts } from "@/lib/hooks";
import { downloadNitPortfolio } from "@/lib/portfolio";

const TYPE_LABELS: Record<string, string> = {
  PATENT: "Patente",
  TRADEMARK: "Marca",
  SOFTWARE: "Software",
  CULTIVAR: "Cultivar",
  KNOWHOW: "Know-how",
  OTHER: "Outro",
};

export default function NitPortfolioPage() {
  const [assetType, setAssetType] = useState("");
  const { data, isLoading, error } = useNitPortfolio({
    asset_type: assetType || undefined,
  });
  const { data: alerts } = useNitPortfolioAlerts(90);

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Portfólio avançado</h1>
          <p className="text-sm text-slate-500">
            Visões por tipo/situação, maturidade (TRL) e prazos de vigência.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={assetType}
            onChange={(e) => setAssetType(e.target.value)}
            className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
          >
            <option value="">Todos os tipos</option>
            {Object.entries(TYPE_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </select>
          <button
            onClick={() => downloadNitPortfolio().catch(() => undefined)}
            className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Exportar CSV
          </button>
        </div>
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}

      {isLoading ? (
        <Spinner />
      ) : data ? (
        <>
          <div className="grid gap-4 sm:grid-cols-4">
            <Metric label="Ativos" value={data.total} tone="blue" />
            <Metric label="A vencer (90d)" value={data.expiring_soon} tone="amber" />
            <Metric label="Vencidos" value={data.expired} tone="red" />
            <Metric
              label="Com TRL"
              value={data.items.filter((i) => i.trl_level).length}
              tone="green"
            />
          </div>

          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title="Composição por tipo" />
              <CardBody>
                {Object.keys(data.by_type).length === 0 ? (
                  <EmptyState title="Sem ativos" />
                ) : (
                  <ul className="space-y-1 text-sm">
                    {Object.entries(data.by_type).map(([k, v]) => (
                      <li key={k} className="flex justify-between">
                        <span className="text-slate-600">
                          {TYPE_LABELS[k] || k}
                        </span>
                        <span className="font-medium text-slate-800">{v}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Alertas de vencimento"
                subtitle="Somente ativos com data de vigência registrada"
              />
              <CardBody>
                {!alerts || alerts.length === 0 ? (
                  <EmptyState title="Nenhum prazo próximo" />
                ) : (
                  <ul className="space-y-2">
                    {alerts.map((a) => (
                      <li
                        key={a.asset_id}
                        className="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2"
                      >
                        <div>
                          <p className="text-sm font-medium text-slate-700">
                            {a.code} — {a.title}
                          </p>
                          <p className="text-xs text-slate-400">
                            Vence em{" "}
                            {new Date(a.expires_at).toLocaleDateString("pt-BR")}
                          </p>
                        </div>
                        <Badge
                          tone={
                            a.severity === "expired"
                              ? "red"
                              : a.severity === "critical"
                                ? "orange"
                                : "amber"
                          }
                        >
                          {a.days_to_expiry < 0
                            ? `${Math.abs(a.days_to_expiry)}d vencido`
                            : `${a.days_to_expiry}d`}
                        </Badge>
                      </li>
                    ))}
                  </ul>
                )}
              </CardBody>
            </Card>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "blue" | "amber" | "red" | "green";
}) {
  const colors: Record<string, string> = {
    blue: "text-brand-700",
    amber: "text-amber-600",
    red: "text-red-600",
    green: "text-emerald-600",
  };
  return (
    <Card>
      <CardBody>
        <p className="text-sm text-slate-500">{label}</p>
        <p className={`mt-1 text-3xl font-bold ${colors[tone]}`}>{value}</p>
      </CardBody>
    </Card>
  );
}
