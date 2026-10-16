"use client";

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
  Spinner,
} from "@/components/ui";
import { useAuth } from "@/app/auth-context";
import { useNitPrograms } from "@/lib/hooks";
import { EnrollModal, NewProgramModal } from "./IncubationModals";

export default function IncubationPage() {
  const { has } = useAuth();
  const { data: programs, isLoading, error } = useNitPrograms();
  const canManage = has("NIT_STARTUP_MANAGE");
  const [openNew, setOpenNew] = useState(false);
  const [enrollProgram, setEnrollProgram] = useState<string | null>(null);

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Incubação</h1>
          <p className="text-sm text-slate-500">
            Programas de incubação, participações de startups e fases de acompanhamento.
          </p>
        </div>
        {canManage && <Button onClick={() => setOpenNew(true)}>Novo programa</Button>}
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}
      {isLoading ? <Spinner /> : null}

      {programs && programs.length === 0 ? (
        <Card>
          <CardBody>
            <EmptyState title="Nenhum programa de incubação cadastrado" />
          </CardBody>
        </Card>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        {programs?.map((p) => (
          <Card key={p.id}>
            <CardHeader
              title={p.name}
              subtitle={p.code}
              action={
                canManage ? (
                  <Button variant="secondary" onClick={() => setEnrollProgram(p.id)}>
                    Inscrever startup
                  </Button>
                ) : undefined
              }
            />
            <CardBody className="space-y-2 text-sm text-slate-600">
              <p>{p.description || "Sem descrição."}</p>
              <p className="text-xs text-slate-400">
                Período: {p.start_date || "—"} → {p.end_date || "—"}
              </p>
              <Badge tone={p.active ? "green" : "slate"}>
                {p.active ? "Ativo" : "Inativo"}
              </Badge>
            </CardBody>
          </Card>
        ))}
      </div>

      <NewProgramModal open={openNew} onClose={() => setOpenNew(false)} />
      {enrollProgram ? (
        <EnrollModal programId={enrollProgram} onClose={() => setEnrollProgram(null)} />
      ) : null}
    </AppShell>
  );
}
