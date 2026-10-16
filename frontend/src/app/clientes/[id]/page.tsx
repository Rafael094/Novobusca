"use client";

/**
 * Detalhe do cliente (``/clientes/[id]``) — the portfolio view of one client.
 *
 * Centralises everything the tenant knows about a client so the operator does
 * not have to hunt across modules: cadastral data, commercial history
 * (opportunities + proposals) and follow-ups.
 *
 * Sections without data render a contextual empty state instead of a fabricated
 * one, and the page only shows what the backend actually returns.
 */

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import AppShell from "@/components/AppShell";
import PageHeader from "@/components/PageHeader";
import {
  Badge,
  Card,
  CardBody,
  ErrorNote,
  Spinner,
  Tabs,
  statusTone,
} from "@/components/ui";
import {
  useCrmActivities,
  useCustomers,
  useOpportunities,
  useProposals,
} from "@/lib/hooks";
import {
  ACTIVITY_KIND_LABELS,
  OPPORTUNITY_STAGE_LABELS,
  PROPOSAL_STATUS_LABELS,
} from "@/lib/types";

function currency(value: string | null): string {
  if (!value) return "—";
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return "—";
  return numeric.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export default function ClienteDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? "";
  const [tab, setTab] = useState("dados");

  const customers = useCustomers({ page: 1, page_size: 100 });
  const customer = customers.data?.items.find((c) => c.id === id);
  const opportunities = useOpportunities({ customer_id: id, page_size: 50 });
  const proposals = useProposals({ customer_id: id, page_size: 50 });

  return (
    <AppShell>
      <PageHeader
        breadcrumb="CRM · Clientes"
        title={customer?.name ?? "Cliente"}
        description="Carteira, histórico comercial e acompanhamento deste cliente."
        actions={
          <Link
            href="/clientes"
            className="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Voltar
          </Link>
        }
      />

      {customers.isLoading && <Spinner />}
      {customers.error && (
        <ErrorNote>
          {customers.error instanceof Error
            ? customers.error.message
            : "Erro ao carregar."}
        </ErrorNote>
      )}

      {!customers.isLoading && !customer && (
        <Card>
          <CardBody>
            <p className="py-8 text-center text-sm text-slate-500">
              Cliente não encontrado ou sem permissão de acesso.
            </p>
          </CardBody>
        </Card>
      )}

      {customer && (
        <Card>
          <Tabs
            active={tab}
            onChange={setTab}
            tabs={[
              { id: "dados", label: "Dados cadastrais" },
              { id: "oportunidades", label: "Oportunidades" },
              { id: "propostas", label: "Propostas" },
              { id: "atividades", label: "Atividades" },
            ]}
          />
          <CardBody>
            {tab === "dados" && <DadosCadastrais customer={customer} />}
            {tab === "oportunidades" && (
              <HistoricoOportunidades
                items={opportunities.data?.items ?? []}
                loading={opportunities.isLoading}
              />
            )}
            {tab === "propostas" && (
              <HistoricoPropostas
                items={proposals.data?.items ?? []}
                loading={proposals.isLoading}
              />
            )}
            {tab === "atividades" && <HistoricoAtividades id={id} />}
          </CardBody>
        </Card>
      )}
    </AppShell>
  );
}

function DadosCadastrais({
  customer,
}: {
  customer: {
    name: string;
    code: string | null;
    document: string | null;
    email: string | null;
    phone: string | null;
    company_name: string | null;
    person_name: string | null;
    active: boolean;
    notes: string | null;
  };
}) {
  return (
    <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <Field label="Nome" value={customer.name} />
      <Field label="Código" value={customer.code} />
      <Field label="Documento" value={customer.document} />
      <Field label="E-mail" value={customer.email} />
      <Field label="Telefone" value={customer.phone} />
      <Field
        label="Empresa / pessoa"
        value={customer.company_name || customer.person_name}
      />
      <div>
        <dt className="text-xs uppercase text-slate-400">Situação</dt>
        <dd>
          <Badge tone={customer.active ? "green" : "slate"}>
            {customer.active ? "Ativo" : "Inativo"}
          </Badge>
        </dd>
      </div>
      <div className="sm:col-span-2 lg:col-span-3">
        <dt className="text-xs uppercase text-slate-400">Observações</dt>
        <dd className="text-sm text-slate-700">{customer.notes || "—"}</dd>
      </div>
    </dl>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs uppercase text-slate-400">{label}</dt>
      <dd className="text-sm text-slate-700">{value || "—"}</dd>
    </div>
  );
}

function HistoricoOportunidades({
  items,
  loading,
}: {
  items: Array<{
    id: string;
    code: string;
    title: string;
    stage: keyof typeof OPPORTUNITY_STAGE_LABELS;
    estimated_value: string | null;
  }>;
  loading: boolean;
}) {
  if (loading) return <Spinner />;
  if (items.length === 0)
    return (
      <p className="py-8 text-center text-sm text-slate-400">
        Nenhuma oportunidade vinculada a este cliente.
      </p>
    );
  return (
    <ul className="divide-y divide-gray-50">
      {items.map((o) => (
        <li key={o.id} className="flex items-center justify-between gap-3 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-700">
              {o.title}
            </p>
            <p className="text-xs text-slate-400">{o.code}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge tone={statusTone(o.stage)}>
              {OPPORTUNITY_STAGE_LABELS[o.stage]}
            </Badge>
            <span className="text-sm text-slate-600">
              {currency(o.estimated_value)}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

function HistoricoPropostas({
  items,
  loading,
}: {
  items: Array<{
    id: string;
    code: string;
    title: string;
    status: keyof typeof PROPOSAL_STATUS_LABELS;
    total_value: string | null;
    valid_until: string | null;
    is_overdue: boolean;
  }>;
  loading: boolean;
}) {
  if (loading) return <Spinner />;
  if (items.length === 0)
    return (
      <p className="py-8 text-center text-sm text-slate-400">
        Nenhuma proposta vinculada a este cliente.
      </p>
    );
  return (
    <ul className="divide-y divide-gray-50">
      {items.map((p) => (
        <li key={p.id} className="flex items-center justify-between gap-3 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-700">
              {p.title}
            </p>
            <p className="text-xs text-slate-400">
              {p.code}
              {p.valid_until
                ? ` · válida até ${new Date(p.valid_until).toLocaleDateString("pt-BR")}`
                : ""}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Badge tone={statusTone(p.status)}>
              {PROPOSAL_STATUS_LABELS[p.status]}
            </Badge>
            {p.is_overdue && <Badge tone="red">Vencida</Badge>}
            <span className="text-sm text-slate-600">
              {currency(p.total_value)}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}

function HistoricoAtividades({ id }: { id: string }) {
  const activities = useCrmActivities({
    subject_type: "CUSTOMER",
    subject_id: id,
    page_size: 50,
  });
  if (activities.isLoading) return <Spinner />;
  const items = activities.data?.items ?? [];
  if (items.length === 0)
    return (
      <p className="py-8 text-center text-sm text-slate-400">
        Nenhuma atividade registrada para este cliente.
      </p>
    );
  return (
    <ul className="divide-y divide-gray-50">
      {items.map((a) => (
        <li key={a.id} className="flex items-start justify-between gap-3 py-3">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-slate-700">
              {a.title}
            </p>
            <p className="text-xs text-slate-400">
              {ACTIVITY_KIND_LABELS[a.kind]}
              {a.due_at
                ? ` · ${new Date(a.due_at).toLocaleDateString("pt-BR")}`
                : ""}
            </p>
          </div>
          <Badge tone={statusTone(a.outcome)}>
            {a.outcome === "DONE"
              ? "Concluída"
              : a.outcome === "PENDING"
                ? "Pendente"
                : a.outcome === "NO_ANSWER"
                  ? "Sem resposta"
                  : "Reagendada"}
          </Badge>
        </li>
      ))}
    </ul>
  );
}

