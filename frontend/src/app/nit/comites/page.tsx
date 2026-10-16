"use client";

import Link from "next/link";
import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  CardBody,
  EmptyState,
  ErrorNote,
  Input,
  Modal,
  Spinner,
} from "@/components/ui";
import { useCreateNitCommittee, useNitCommittees } from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";

export default function NitCommitteesPage() {
  const { has } = useAuth();
  const { data, isLoading, error } = useNitCommittees();
  const [openNew, setOpenNew] = useState(false);
  const canManage = has("NIT_COMMITTEE_MANAGE");

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Comitês</h1>
          <p className="text-sm text-slate-500">
            Comitês de inovação, membros, reuniões e decisões.
          </p>
        </div>
        {canManage && <Button onClick={() => setOpenNew(true)}>Novo comitê</Button>}
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}

      {isLoading ? (
        <Spinner />
      ) : data && data.length > 0 ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((c) => (
            <Card key={c.id}>
              <CardBody>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                      {c.code}
                    </p>
                    <p className="font-semibold text-slate-800">{c.name}</p>
                  </div>
                  <Badge tone={c.status === "ACTIVE" ? "green" : "slate"}>
                    {c.status === "ACTIVE" ? "Ativo" : "Inativo"}
                  </Badge>
                </div>
                <p className="mt-2 text-sm text-slate-500">
                  Quórum mínimo: <strong>{c.quorum}</strong>
                </p>
                <Link
                  href={`/nit/comites/${c.id}`}
                  className="mt-3 inline-block text-sm font-medium text-brand-700 hover:underline"
                >
                  Abrir comitê
                </Link>
              </CardBody>
            </Card>
          ))}
        </div>
      ) : (
        <Card>
          <CardBody>
            <EmptyState
              title="Nenhum comitê cadastrado"
              description="Crie um comitê para registrar reuniões, votos e decisões."
            />
          </CardBody>
        </Card>
      )}

      <NewCommitteeModal open={openNew} onClose={() => setOpenNew(false)} />
    </AppShell>
  );
}

function NewCommitteeModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateNitCommittee();
  const [name, setName] = useState("");
  const [quorum, setQuorum] = useState("2");
  const [majority, setMajority] = useState(true);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Novo comitê"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={!name.trim() || create.isPending}
            onClick={() =>
              create.mutate(
                {
                  name,
                  quorum: Number(quorum) || 1,
                  simple_majority: majority,
                },
                { onSuccess: onClose },
              )
            }
          >
            {create.isPending ? "Criando…" : "Criar"}
          </Button>
        </>
      }
    >
      {create.error ? (
        <div className="mb-3">
          <ErrorNote>{(create.error as Error).message}</ErrorNote>
        </div>
      ) : null}
      <div className="space-y-3">
        <Input
          label="Nome"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <Input
          label="Quórum mínimo (votos válidos)"
          type="number"
          min={1}
          value={quorum}
          onChange={(e) => setQuorum(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={majority}
            onChange={(e) => setMajority(e.target.checked)}
          />
          Exigir maioria simples para aprovação
        </label>
      </div>
    </Modal>
  );
}
