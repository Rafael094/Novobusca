"use client";

/**
 * Visão Geral — the business dashboard.
 *
 * Rewritten so the numbers describe **this tenant's operation**, not the global
 * INPI base. Every value comes from ``GET /api/dashboard/business``:
 * commercial counters, the funnel, the proposals that need action, deadlines
 * (commercial and PI, clearly separated) and the real activity timeline.
 *
 * Where a comparison cannot be computed from real history it is *omitted* —
 * never invented.
 */

import Link from "next/link";
import { useState } from "react";

import AppShell from "@/components/AppShell";
import { LineChart } from "@/components/charts";
import Funnel from "@/components/Funnel";
import PageHeader from "@/components/PageHeader";
import StatCard from "@/components/StatCard";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  ErrorNote,
  Spinner,
  statusTone,
} from "@/components/ui";
import { useBusinessDashboard } from "@/lib/hooks";
import { PENDING_REASON_LABELS } from "@/lib/types";

function currency(value: string | null): string {
  if (!value) return "—";
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "—";
  return numeric.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

const ACTIVITY_ICONS: Record<string, string> = {
  customer: "👥",
  proposal: "📄",
  opportunity: "🎯",
  activity: "📞",
  monitoring: "🛰",
  alert: "⚠",
};

export default function DashboardPage() {
  const [months, setMonths] = useState(12);
  const { data, isLoading, error } = useBusinessDashboard(months);

  const evolution = data?.evolution ?? [];
  const chartLabels = evolution.map((e) => e.label.slice(5)); // MM
  const series = [
    {
      name: "Novos clientes",
      color: "#2563eb",
      values: evolution.map((e) => e.new_customers),
    },
    {
      name: "Propostas enviadas",
      color: "#f59e0b",
      values: evolution.map((e) => e.proposals_sent),
    },
    {
      name: "Propostas aprovadas",
      color: "#10b981",
      values: evolution.map((e) => e.proposals_approved),
    },
    {
      name: "Oportunidades ganhas",
      color: "#8b5cf6",
      values: evolution.map((e) => e.opportunities_won),
    },
  ];
  const hasEvolution = evolution.some(
    (e) =>
      e.new_customers +
        e.proposals_sent +
        e.proposals_approved +
        e.opportunities_won >
      0,
  );

  return (
    <AppShell>
      <PageHeader
        title="Visão Geral"
        description="Desempenho comercial e operacional da sua operação."
        actions={
          <div className="flex items-center gap-2">
            <select
              value={months}
              onChange={(e) => setMonths(Number(e.target.value))}
              className="rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-slate-600"
              aria-label="Período"
            >
              <option value={12}>Últimos 12 meses</option>
              <option value={24}>Últimos 24 meses</option>
            </select>
            <Link href="/crm/oportunidades">
              <Button>+ Nova oportunidade</Button>
            </Link>
          </div>
        }
      />

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
              label="Clientes ativos"
              value={data.counters.active_customers}
              detail={`${data.counters.new_customers_period} novos no período`}
              tone="brand"
              icon="👥"
              href="/clientes"
            />
            <StatCard
              label="Oportunidades em negociação"
              value={data.counters.open_opportunities}
              detail={`${data.counters.proposals_open} propostas abertas`}
              tone="violet"
              icon="🎯"
              href="/crm/oportunidades"
            />
            <StatCard
              label="Propostas a enviar"
              value={data.counters.proposals_to_send}
              hint="Propostas em rascunho ou pendentes de envio"
              tone="amber"
              icon="📤"
              href="/crm/propostas"
            />
            <StatCard
              label="Propostas aguardando retorno"
              value={data.counters.proposals_awaiting_reply}
              hint="Enviadas, aguardando resposta do cliente"
              tone="slate"
              icon="⏳"
              href="/crm/propostas"
            />
            <StatCard
              label="Propostas aprovadas"
              value={data.counters.proposals_approved}
              detail={`Conversão: ${
                data.counters.conversion_rate === null
                  ? "sem histórico decisório"
                  : `${data.counters.conversion_rate}%`
              }`}
              tone="green"
              icon="✅"
              href="/crm/propostas"
            />
            <StatCard
              label="Marcas monitoradas"
              value={data.counters.monitored_marcas}
              tone="brand"
              icon="®"
              href="/monitoramento"
            />
            <StatCard
              label="Patentes monitoradas"
              value={data.counters.monitored_patentes}
              tone="brand"
              icon="📄"
              href="/monitoramento"
            />
            <StatCard
              label="Alertas críticos"
              value={data.counters.critical_alerts}
              hint="Propostas vencidas/próximas e follow-ups em atraso"
              tone="red"
              icon="⚠"
              href="/crm/propostas"
            />
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader
                title="Evolução comercial"
                subtitle={`Últimos ${months} meses`}
              />
              <CardBody>
                {hasEvolution ? (
                  <LineChart labels={chartLabels} series={series} />
                ) : (
                  <div className="py-8 text-center">
                    <p className="text-sm text-slate-500">
                      Ainda não há histórico comercial suficiente para exibir o
                      gráfico.
                    </p>
                    <p className="mt-1 text-xs text-slate-400">
                      Cadastre clientes, oportunidades e propostas para começar a
                      acompanhar a evolução.
                    </p>
                    <Link
                      href="/crm/oportunidades"
                      className="mt-3 inline-block"
                    >
                      <Button variant="secondary">Cadastrar oportunidade</Button>
                    </Link>
                  </div>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Funil de vendas"
                subtitle="Etapas do comercial"
              />
              <CardBody>
                <Funnel
                  stages={data.funnel}
                  hrefFor={(stage) => `/crm/oportunidades?stage=${stage.stage}`}
                />
              </CardBody>
            </Card>
          </div>

          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader
                title="Propostas que precisam de ação"
                subtitle="Priorizadas por urgência"
                action={
                  <Link
                    href="/crm/propostas"
                    className="text-xs font-medium text-brand-600 hover:underline"
                  >
                    Ver todas
                  </Link>
                }
              />
              <CardBody className="p-0">
                {data.pending_proposals.length === 0 ? (
                  <p className="px-5 py-8 text-center text-sm text-slate-400">
                    Nenhuma proposta pendente.
                  </p>
                ) : (
                  <div className="divide-y divide-gray-50">
                    {data.pending_proposals.map((p) => (
                      <div
                        key={p.id}
                        className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
                      >
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-800">
                            {p.title}
                          </p>
                          <p className="text-xs text-slate-400">
                            {p.code}
                            {p.customer_name ? ` · ${p.customer_name}` : ""}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <Badge tone="amber">
                            {PENDING_REASON_LABELS[p.reason]}
                          </Badge>
                          <span className="text-sm font-medium text-slate-700">
                            {currency(p.total_value)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Atividade recente"
                subtitle="Eventos reais da sua operação"
              />
              <CardBody className="space-y-3">
                {data.recent_activity.length === 0 && (
                  <p className="py-4 text-center text-sm text-slate-400">
                    Nenhuma atividade registrada ainda.
                  </p>
                )}
                {data.recent_activity.map((item, index) => (
                  <div
                    key={`${item.kind}-${index}`}
                    className="flex items-start gap-3 border-b border-gray-50 pb-3 last:border-0 last:pb-0"
                  >
                    <span className="mt-0.5 text-base" aria-hidden="true">
                      {ACTIVITY_ICONS[item.kind] ?? "•"}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-slate-700">
                        {item.title}
                      </p>
                      <p className="text-xs text-slate-400">
                        {new Date(item.at).toLocaleDateString("pt-BR")}
                        {item.status ? ` · ${item.status}` : ""}
                      </p>
                    </div>
                    {item.link && (
                      <Link
                        href={item.link}
                        className="shrink-0 text-xs text-brand-600 hover:underline"
                      >
                        Abrir
                      </Link>
                    )}
                  </div>
                ))}
              </CardBody>
            </Card>
          </div>

          <Card className="mt-6">
            <CardHeader
              title="Próximos prazos e alertas"
              subtitle="Prazos comerciais separados dos prazos de propriedade intelectual"
            />
            <CardBody className="p-0">
              {data.deadlines.length === 0 ? (
                <p className="px-5 py-8 text-center text-sm text-slate-400">
                  Nenhum prazo registrado.
                </p>
              ) : (
                <div className="divide-y divide-gray-50">
                  {data.deadlines.map((d, index) => (
                    <div
                      key={`${d.title}-${index}`}
                      className="flex flex-wrap items-center justify-between gap-3 px-5 py-3"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-800">
                          {d.title}
                        </p>
                        <p className="text-xs text-slate-400">
                          {d.subtitle || "—"}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <Badge
                          tone={d.domain === "COMMERCIAL" ? "blue" : "slate"}
                        >
                          {d.domain === "COMMERCIAL"
                            ? "Comercial"
                            : "Propriedade intelectual"}
                        </Badge>
                        <Badge
                          tone={
                            d.tone === "red"
                              ? "red"
                              : d.tone === "amber"
                                ? "amber"
                                : "green"
                          }
                        >
                          {d.days_remaining === null
                            ? "—"
                            : `${d.days_remaining} dias`}
                        </Badge>
                        {d.link && (
                          <Link
                            href={d.link}
                            className="text-xs text-brand-600 hover:underline"
                          >
                            Abrir
                          </Link>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>

          {data.counters.proposals_rejected > 0 && (
            <p className="mt-4 text-xs text-slate-400">
              {data.counters.proposals_rejected} proposta(s) recusada(s) no
              período. Os indicadores acima consideram apenas os dados do seu
              tenant.
            </p>
          )}
        </>
      )}
    </AppShell>
  );
}

