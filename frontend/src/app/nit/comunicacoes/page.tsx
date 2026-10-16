"use client";

import Link from "next/link";
import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  CardBody,
  EmptyRow,
  ErrorNote,
  Input,
  Pagination,
  Select,
  Spinner,
  Table,
  Td,
  Th,
  statusTone,
} from "@/components/ui";
import { useNitDisclosures } from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";
import { NewDisclosureModal } from "./NewDisclosureModal";

const STATUS_LABELS: Record<string, string> = {
  PROPOSAL: "Proposta",
  TRIAGE: "Triagem",
  EVALUATION: "Avaliação",
  DECISION: "Decisão",
  CLOSED: "Encerrado",
  REJECTED: "Rejeitado",
};

export default function NitDisclosuresPage() {
  const { has } = useAuth();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [area, setArea] = useState("");
  const [page, setPage] = useState(1);
  const [openNew, setOpenNew] = useState(false);

  const pageSize = 20;
  const { data, isLoading, error } = useNitDisclosures({
    q: q || undefined,
    status: status || undefined,
    technology_area: area || undefined,
    page,
    page_size: pageSize,
  });

  const canCreate = has("NIT_DISCLOSURE_CREATE");

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Comunicações</h1>
          <p className="text-sm text-slate-500">
            Registro e tramitação de comunicações de invenção.
          </p>
        </div>
        {canCreate && (
          <Button onClick={() => setOpenNew(true)}>Nova comunicação</Button>
        )}
      </div>

      <Card className="mb-4">
        <CardBody className="grid gap-3 sm:grid-cols-3">
          <Input
            label="Buscar"
            placeholder="Título, protocolo ou palavra-chave"
            value={q}
            onChange={(e) => {
              setPage(1);
              setQ(e.target.value);
            }}
          />
          <Select
            label="Etapa"
            value={status}
            onChange={(e) => {
              setPage(1);
              setStatus(e.target.value);
            }}
          >
            <option value="">Todas</option>
            {Object.entries(STATUS_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
          <Input
            label="Área tecnológica"
            value={area}
            onChange={(e) => {
              setPage(1);
              setArea(e.target.value);
            }}
          />
        </CardBody>
      </Card>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}

      <Card>
        {isLoading ? (
          <CardBody>
            <Spinner />
          </CardBody>
        ) : (
          <>
            <Table>
              <thead className="bg-slate-50">
                <tr>
                  <Th>Protocolo</Th>
                  <Th>Título</Th>
                  <Th>Área</Th>
                  <Th>Etapa</Th>
                  <Th>Sigilo</Th>
                  <Th />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data && data.items.length > 0 ? (
                  data.items.map((d) => (
                    <tr key={d.id} className="hover:bg-slate-50/60">
                      <Td className="font-medium text-slate-700">{d.protocol}</Td>
                      <Td>{d.title}</Td>
                      <Td>{d.technology_area || "—"}</Td>
                      <Td>
                        <Badge tone={statusTone(d.status)}>
                          {STATUS_LABELS[d.status] || d.status}
                        </Badge>
                      </Td>
                      <Td>{d.confidentiality_level}</Td>
                      <Td>
                        <Link
                          href={`/nit/comunicacoes/${d.id}`}
                          className="text-sm font-medium text-brand-700 hover:underline"
                        >
                          Abrir dossiê
                        </Link>
                      </Td>
                    </tr>
                  ))
                ) : (
                  <EmptyRow colSpan={6} message="Nenhuma comunicação encontrada." />
                )}
              </tbody>
            </Table>
            {data && (
              <Pagination
                page={page}
                pageSize={pageSize}
                total={data.total}
                onPage={setPage}
              />
            )}
          </>
        )}
      </Card>

      <NewDisclosureModal open={openNew} onClose={() => setOpenNew(false)} />
    </AppShell>
  );
}
