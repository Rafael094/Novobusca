"use client";

/**
 * CRM — Visão comercial (``/crm``).
 *
 * The commercial hub of the tenant: the same aggregates that feed the Overview,
 * but focused on the pipeline and on what needs action *today*. Everything comes
 * from the real endpoints (``/api/dashboard/business``, ``/api/crm/*``).
 */

import Link from "next/link";
import { useState } from "react";

import AppShell from "@/components/AppShell";
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

export default function CrmPage() {
  const [months, setMonths] = useState(12);
  const { data, isLoading, error } = useBusinessDashboard(months);

  return (
    <AppShell>
      <PageHeader
        breadcrumb="CRM"
        title="Visão comercial"
        description="Acompanhe clientes, o funil de vendas e as propostas que exigem ação."
        actions={
          <>
            <Link href="/crm/oportunidades">
              <Button variant="secondary">Leads e oportunidades</Button>
            </Link>
            <Link href="/crm/propostas">
              <Button>Propostas comerciais</Button>
            </Link>
          </>
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
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Clientes ativos"
              value={data.counters.active_customers}
              detail={`${data.counters.new_customers_period} novos no período`}
              tone="brand"
              icon="👥"
              href="/clientes"
            />
            <StatCard
              label="Oportunidades abertas"
              value={data.counters.open_opportunities}
              detail={`Conversão: ${
                data.counters.conversion_rate === null
                  ? "sem histórico"
                  : `${data.counters.conversion_rate}%`
              }`}
              tone="violet"
              icon="🎯"
              href="/crm/oportunidades"
            />
            <StatCard
              label="Propostas a enviar"
              value={data.counters.proposals_to_send}
              detail={`${data.counters.proposals_awaiting_reply} aguardando retorno`}
              tone="amber"
              icon="📤"
              href="/crm/propostas"
            />
            <StatCard
              label="Propostas aprovadas"
              value={data.counters.proposals_approved}
              detail={`${data.counters.proposals_rejected} recusadas`}
              tone="green"
              icon="✅"
              href="/crm/propostas"
            />
          </div>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            <Card className="lg:col-span-2">
              <CardHeader
                title="Propostas que precisam de ação"
                subtitle="Vencidas, a enviar, aguardando retorno e aprovadas sem cliente"
                action={
                  <select
                    value={months}
                    onChange={(e) => setMonths(Number(e.target.value))}
                    className="rounded-lg border border-gray-200 bg-white px-2 py-1 text-xs text-slate-600"
                    aria-label="Período de referência"
                  >
                    <option value={12}>12 meses</option>
                    <option value={24}>24 meses</option>
                  </select>
                }
              />
              <CardBody className="p-0">
                {data.pending_proposals.length === 0 ? (
                  <p className="px-5 py-8 text-center text-sm text-slate-400">
                    Nenhuma proposta pendente. Crie uma proposta em{" "}
                    <Link href="/crm/propostas" className="text-brand-600">
                      Propostas comerciais
                    </Link>
                    .
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
                            {p.owner_name ? ` · ${p.owner_name}` : ""}
                          </p>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <Badge tone="blue">
                            {PENDING_REASON_LABELS[p.reason]}
                          </Badge>
                          <Badge tone={statusTone(p.status)}>
                            {p.status_label}
                          </Badge>
                          <span className="w-24 text-right text-sm font-medium text-slate-700">
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
                title="Funil comercial"
                subtitle="Oportunidades por etapa"
              />
              <CardBody>
                <Funnel
                  stages={data.funnel}
                  hrefFor={(stage) => `/crm/oportunidades?stage=${stage.stage}`}
                />
              </CardBody>
            </Card>
          </div>
        </>
      )}
    </AppShell>
  );
}

