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
  Select,
  Spinner,
} from "@/components/ui";
import {
  useNitContract,
  useUpdateNitContract,
} from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";
import { CONTRACT_STATUS_LABELS } from "../ContractsTable";
import { ObligationsCard } from "./ObligationsCard";
import { RoyaltiesCard, RoyaltySummaryCard } from "./RoyaltiesCard";

export default function ContractDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? null;
  const { has } = useAuth();
  const { data, isLoading, error } = useNitContract(id);
  const update = useUpdateNitContract(id ?? "");
  const canManage = has("NIT_CONTRACT_MANAGE");

  return (
    <AppShell>
      <div className="mb-4">
        <Link href="/nit/contratos" className="text-sm text-brand-700 hover:underline">
          ← Voltar para contratos
        </Link>
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}
      {isLoading ? <Spinner /> : null}

      {data ? (
        <>
          <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                {data.code}
              </p>
              <h1 className="text-2xl font-bold text-slate-800">{data.title}</h1>
            </div>
            <div className="flex items-center gap-2">
              <Badge tone={data.status === "ACTIVE" ? "green" : "slate"}>
                {CONTRACT_STATUS_LABELS[data.status] || data.status}
              </Badge>
              {canManage && (
                <Select
                  value={data.status}
                  onChange={(e) => update.mutate({ status: e.target.value })}
                >
                  {Object.entries(CONTRACT_STATUS_LABELS).map(([k, label]) => (
                    <option key={k} value={k}>
                      {label}
                    </option>
                  ))}
                </Select>
              )}
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-6">
              <PartiesCard data={data} />
              {id ? <ObligationsCard contractId={id} /> : null}
              {id ? <RoyaltiesCard contractId={id} canManage={canManage} /> : null}
            </div>

            <Card>
              <CardHeader title="Resumo financeiro" />
              <CardBody>{id ? <RoyaltySummaryCard contractId={id} /> : null}</CardBody>
            </Card>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}

function PartiesCard({ data }: { data: { parties: { id: string; role: string; name: string }[] } }) {
  return (
    <Card>
      <CardHeader title="Partes" />
      <CardBody>
        {data.parties.length === 0 ? (
          <EmptyState title="Sem partes registradas" />
        ) : (
          <ul className="divide-y divide-gray-50">
            {data.parties.map((p) => (
              <li key={p.id} className="flex items-center justify-between py-2">
                <span className="text-sm text-slate-700">{p.name}</span>
                <Badge tone="slate">{p.role}</Badge>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}
