"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Input,
  Select,
  Spinner,
} from "@/components/ui";
import { useAuth } from "@/app/auth-context";
import {
  useCreateProjectFunder,
  useCreateProjectMember,
  useCreateProjectMilestone,
  useNitProject,
  useUpdateProjectMilestone,
} from "@/lib/hooks";
import { PROJECT_STATUS_LABELS } from "../ProjectsTable";

export default function ProjectDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params?.id ?? null;
  const { has } = useAuth();
  const { data, isLoading, error } = useNitProject(id);
  const canManage = has("NIT_PROJECT_MANAGE");

  return (
    <AppShell>
      <div className="mb-4">
        <Link href="/nit/projetos" className="text-sm text-brand-700 hover:underline">
          ← Voltar para projetos
        </Link>
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}
      {isLoading ? <Spinner /> : null}

      {data ? (
        <>
          <div className="mb-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              {data.code}
            </p>
            <h1 className="text-2xl font-bold text-slate-800">{data.title}</h1>
            <p className="mt-1 text-sm text-slate-500">
              {PROJECT_STATUS_LABELS[data.status] || data.status}
              {data.technology_area ? ` · ${data.technology_area}` : ""}
            </p>
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="space-y-6 lg:col-span-2">
              <MembersCard projectId={data.id} members={data.members} canManage={canManage} />
              <MilestonesCard
                projectId={data.id}
                milestones={data.milestones}
                canManage={canManage}
              />
              <FundersCard projectId={data.id} funders={data.funders} canManage={canManage} />
              <AssetLinksCard links={data.asset_links} />
            </div>

            <Card>
              <CardHeader title="Ficha do projeto" />
              <CardBody className="space-y-2 text-sm text-slate-600">
                <Row label="Início" value={data.start_date || "—"} />
                <Row label="Fim" value={data.end_date || "—"} />
                <Row label="Objetivo" value={data.objective || "—"} />
                <Row label="Descrição" value={data.description || "—"} />
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
      <span className="text-right text-slate-700">{value}</span>
    </div>
  );
}

function MembersCard({
  projectId,
  members,
  canManage,
}: {
  projectId: string;
  members: { id: string; name: string; role: string; institution: string | null }[];
  canManage: boolean;
}) {
  const create = useCreateProjectMember(projectId);
  const [name, setName] = useState("");
  const [role, setRole] = useState("RESEARCHER");

  return (
    <Card>
      <CardHeader title="Equipe" />
      <CardBody>
        {members.length === 0 ? (
          <EmptyState title="Sem integrantes registrados" />
        ) : (
          <ul className="divide-y divide-gray-50">
            {members.map((m) => (
              <li key={m.id} className="flex items-center justify-between py-2">
                <span className="text-sm text-slate-700">
                  {m.name}
                  {m.institution ? ` · ${m.institution}` : ""}
                </span>
                <span className="text-xs text-slate-400">{m.role}</span>
              </li>
            ))}
          </ul>
        )}
        {canManage && (
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <Input label="Nome" value={name} onChange={(e) => setName(e.target.value)} />
            <Input label="Papel" value={role} onChange={(e) => setRole(e.target.value)} />
            <div className="flex items-end">
              <Button
                disabled={!name.trim() || create.isPending}
                onClick={() => create.mutate({ name, role }, { onSuccess: () => setName("") })}
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

function MilestonesCard({
  projectId,
  milestones,
  canManage,
}: {
  projectId: string;
  milestones: { id: string; title: string; status: string; due_date: string | null }[];
  canManage: boolean;
}) {
  const create = useCreateProjectMilestone(projectId);
  const update = useUpdateProjectMilestone(projectId);
  const [title, setTitle] = useState("");

  return (
    <Card>
      <CardHeader title="Marcos" />
      <CardBody>
        {milestones.length === 0 ? (
          <EmptyState title="Sem marcos registrados" />
        ) : (
          <ul className="divide-y divide-gray-50">
            {milestones.map((m) => (
              <li key={m.id} className="flex items-center justify-between py-2">
                <span className="text-sm text-slate-700">{m.title}</span>
                {canManage ? (
                  <Select
                    value={m.status}
                    onChange={(e) =>
                      update.mutate({
                        id: m.id,
                        payload: { title: m.title, status: e.target.value },
                      })
                    }
                  >
                    <option value="PENDING">Pendente</option>
                    <option value="DONE">Concluído</option>
                    <option value="LATE">Atrasado</option>
                  </Select>
                ) : (
                  <span className="text-xs text-slate-400">{m.status}</span>
                )}
              </li>
            ))}
          </ul>
        )}
        {canManage && (
          <div className="mt-4 flex items-end gap-2">
            <Input label="Novo marco" value={title} onChange={(e) => setTitle(e.target.value)} />
            <Button
              disabled={!title.trim() || create.isPending}
              onClick={() =>
                create.mutate({ title, status: "PENDING" }, { onSuccess: () => setTitle("") })
              }
            >
              Adicionar
            </Button>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function FundersCard({
  projectId,
  funders,
  canManage,
}: {
  projectId: string;
  funders: { id: string; name: string; amount: string | null; instrument: string | null }[];
  canManage: boolean;
}) {
  const create = useCreateProjectFunder(projectId);
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("");

  return (
    <Card>
      <CardHeader title="Financiadores" />
      <CardBody>
        {funders.length === 0 ? (
          <EmptyState title="Sem financiadores registrados" />
        ) : (
          <ul className="divide-y divide-gray-50">
            {funders.map((f) => (
              <li key={f.id} className="flex items-center justify-between py-2">
                <span className="text-sm text-slate-700">
                  {f.name}
                  {f.instrument ? ` · ${f.instrument}` : ""}
                </span>
                <span className="text-sm text-slate-600">
                  {f.amount
                    ? `R$ ${Number(f.amount).toLocaleString("pt-BR", {
                        minimumFractionDigits: 2,
                      })}`
                    : "—"}
                </span>
              </li>
            ))}
          </ul>
        )}
        {canManage && (
          <div className="mt-4 grid gap-2 sm:grid-cols-3">
            <Input label="Nome" value={name} onChange={(e) => setName(e.target.value)} />
            <Input
              label="Valor (opcional)"
              placeholder="Ex.: 50000.00"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
            <div className="flex items-end">
              <Button
                disabled={!name.trim() || create.isPending}
                onClick={() =>
                  create.mutate(
                    { name, amount: amount || null },
                    {
                      onSuccess: () => {
                        setName("");
                        setAmount("");
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

function AssetLinksCard({
  links,
}: {
  links: { id: string; asset_id: string; relation: string }[];
}) {
  return (
    <Card>
      <CardHeader title="Ativos vinculados" />
      <CardBody>
        {links.length === 0 ? (
          <EmptyState title="Nenhum ativo vinculado" />
        ) : (
          <ul className="divide-y divide-gray-50">
            {links.map((l) => (
              <li key={l.id} className="flex items-center justify-between py-2">
                <Link
                  href={`/nit/ativos/${l.asset_id}`}
                  className="text-sm text-brand-700 hover:underline"
                >
                  {l.asset_id}
                </Link>
                <span className="text-xs text-slate-400">{l.relation}</span>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}


