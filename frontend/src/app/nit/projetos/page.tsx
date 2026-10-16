"use client";

import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Button,
  Card,
  CardBody,
  ErrorNote,
  Input,
  Select,
} from "@/components/ui";
import { useAuth } from "@/app/auth-context";
import { useNitProjects } from "@/lib/hooks";
import { NewProjectModal } from "./NewProjectModal";
import { PROJECT_STATUS_LABELS, ProjectsTable } from "./ProjectsTable";

export default function NitProjectsPage() {
  const { has } = useAuth();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [openNew, setOpenNew] = useState(false);

  const pageSize = 20;
  const { data, isLoading, error } = useNitProjects({
    q: q || undefined,
    status: status || undefined,
    page,
    page_size: pageSize,
  });

  const canManage = has("NIT_PROJECT_MANAGE");

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Projetos de P&D</h1>
          <p className="text-sm text-slate-500">
            Projetos de pesquisa, equipe, financiadores, marcos e ativos vinculados.
          </p>
        </div>
        {canManage && <Button onClick={() => setOpenNew(true)}>Novo projeto</Button>}
      </div>

      <Card className="mb-4">
        <CardBody className="grid gap-3 sm:grid-cols-2">
          <Input
            label="Buscar"
            placeholder="Código, título ou área"
            value={q}
            onChange={(e) => {
              setPage(1);
              setQ(e.target.value);
            }}
          />
          <Select
            label="Situação"
            value={status}
            onChange={(e) => {
              setPage(1);
              setStatus(e.target.value);
            }}
          >
            <option value="">Todas</option>
            {Object.entries(PROJECT_STATUS_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
        </CardBody>
      </Card>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}

      <ProjectsTable
        data={data}
        isLoading={isLoading}
        page={page}
        pageSize={pageSize}
        onPage={setPage}
      />

      <NewProjectModal open={openNew} onClose={() => setOpenNew(false)} />
    </AppShell>
  );
}
