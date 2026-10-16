"use client";

import Link from "next/link";
import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyRow,
  ErrorNote,
  Input,
  Pagination,
  Select,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { useNitContracts, useNitObligationAlerts } from "@/lib/hooks";
import { useAuth } from "@/app/auth-context";
import { NewContractModal } from "./NewContractModal";
import {
  CONTRACT_STATUS_LABELS,
  ObligationAlertsCard,
  ContractsTable,
} from "./ContractsTable";

export default function NitContractsPage() {
  const { has } = useAuth();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [openNew, setOpenNew] = useState(false);

  const pageSize = 20;
  const { data, isLoading, error } = useNitContracts({
    q: q || undefined,
    status: status || undefined,
    page,
    page_size: pageSize,
  });
  const { data: alerts } = useNitObligationAlerts(60);

  const canManage = has("NIT_CONTRACT_MANAGE");

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Contratos e Licenças</h1>
          <p className="text-sm text-slate-500">
            Instrumentos de transferência, obrigações e royalties.
          </p>
        </div>
        {canManage && <Button onClick={() => setOpenNew(true)}>Novo contrato</Button>}
      </div>

      <ObligationAlertsCard alerts={alerts} />

      <Card className="mb-4">
        <CardBody className="grid gap-3 sm:grid-cols-2">
          <Input
            label="Buscar"
            placeholder="Código ou título"
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
            {Object.entries(CONTRACT_STATUS_LABELS).map(([k, label]) => (
              <option key={k} value={k}>
                {label}
              </option>
            ))}
          </Select>
        </CardBody>
      </Card>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}

      <ContractsTable
        data={data}
        isLoading={isLoading}
        page={page}
        pageSize={pageSize}
        onPage={setPage}
      />

      <NewContractModal open={openNew} onClose={() => setOpenNew(false)} />
    </AppShell>
  );
}
