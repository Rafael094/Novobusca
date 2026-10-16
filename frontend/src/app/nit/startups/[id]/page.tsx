"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
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
import { useCreateStartupMember, useNitStartup } from "@/lib/hooks";
import { STARTUP_STATUS_LABELS } from "../StartupsTable";

export default function StartupDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? null;
  const { has } = useAuth();
  const { data, isLoading, error } = useNitStartup(id);
  const canManage = has("NIT_STARTUP_MANAGE");

  return (
    <AppShell>
      <div className="mb-4">
        <Link href="/nit/startups" className="text-sm text-brand-700 hover:underline">
          ← Voltar para startups
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
              <h1 className="text-2xl font-bold text-slate-800">{data.name}</h1>
            </div>
            <Badge tone={data.status === "INCUBATED" ? "green" : "slate"}>
              {STARTUP_STATUS_LABELS[data.status] || data.status}
            </Badge>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <MembersCard startupId={data.id} members={data.members} canManage={canManage} />
            </div>

            <Card>
              <CardHeader title="Ficha da startup" />
              <CardBody className="space-y-2 text-sm text-slate-600">
                <Row label="Estágio" value={data.stage || "—"} />
                <Row label="CNPJ" value={data.cnpj || "—"} />
                <Row label="Fundação" value={data.founded_at || "—"} />
                <Row
                  label="Projeto de origem"
                  value={data.project_id ? data.project_id : "—"}
                />
                <Row label="Descrição" value={data.description || "—"} />
                <p className="pt-2 text-xs text-slate-400">
                  Vínculo com um ativo não implica propriedade da startup.
                </p>
              </CardBody>
            </Card>
          </div>
        </>
      ) : null}
    </AppShell>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 border-b border-gray-50 py-1.5">
      <span className="text-slate-400">{label}</span>
      <span className="text-right break-all text-slate-700">{value}</span>
    </div>
  );
}

function MembersCard({
  startupId,
  members,
  canManage,
}: {
  startupId: string;
  members: { id: string; name: string; role: string | null; is_founder: boolean }[];
  canManage: boolean;
}) {
  const create = useCreateStartupMember(startupId);
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [isFounder, setIsFounder] = useState(false);

  return (
    <Card>
      <CardHeader title="Sócios e equipe" />
      <CardBody>
        {members.length === 0 ? (
          <EmptyState title="Sem integrantes registrados" />
        ) : (
          <ul className="divide-y divide-gray-50">
            {members.map((m) => (
              <li key={m.id} className="flex items-center justify-between py-2">
                <span className="text-sm text-slate-700">
                  {m.name}
                  {m.is_founder ? " (fundador)" : ""}
                </span>
                <span className="text-xs text-slate-400">{m.role || "—"}</span>
              </li>
            ))}
          </ul>
        )}
        {canManage && (
          <div className="mt-4 grid gap-2 sm:grid-cols-4">
            <Input label="Nome" value={name} onChange={(e) => setName(e.target.value)} />
            <Input
              label="Papel (opcional)"
              value={role}
              onChange={(e) => setRole(e.target.value)}
            />
            <label className="flex items-end gap-2 pb-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={isFounder}
                onChange={(e) => setIsFounder(e.target.checked)}
              />
              Fundador
            </label>
            <div className="flex items-end">
              <Button
                disabled={!name.trim() || create.isPending}
                onClick={() =>
                  create.mutate(
                    { name, role: role || null, is_founder: isFounder },
                    {
                      onSuccess: () => {
                        setName("");
                        setRole("");
                        setIsFounder(false);
                      },
                    },
                  )
                }
              >
                Adicionar
              </Button>
            </div>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
