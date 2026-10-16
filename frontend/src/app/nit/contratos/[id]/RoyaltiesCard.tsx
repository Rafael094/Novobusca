"use client";

import { useState } from "react";

import {
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Input,
  Modal,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";
import {
  useCreateRoyalty,
  useNitRoyalties,
  useNitRoyaltySummary,
} from "@/lib/hooks";

function brl(value: string | null): string {
  if (value === null || value === undefined) return "—";
  return `R$ ${Number(value).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}`;
}

/** Royalties table with distinct expected/registered/received columns. */
export function RoyaltiesCard({
  contractId,
  canManage,
}: {
  contractId: string;
  canManage: boolean;
}) {
  const { data, isLoading } = useNitRoyalties(contractId);
  const [open, setOpen] = useState(false);

  return (
    <Card>
      <CardHeader
        title="Royalties"
        subtitle="Valores esperados, registrados e recebidos são distintos"
        action={
          canManage ? (
            <Button variant="secondary" onClick={() => setOpen(true)}>
              Novo lançamento
            </Button>
          ) : undefined
        }
      />
      <CardBody>
        {isLoading ? (
          <Spinner />
        ) : data && data.length > 0 ? (
          <Table>
            <thead className="bg-slate-50">
              <tr>
                <Th>Período</Th>
                <Th>Esperado</Th>
                <Th>Registrado</Th>
                <Th>Recebido</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data.map((r) => (
                <tr key={r.id}>
                  <Td className="font-medium text-slate-700">{r.period}</Td>
                  <Td>{brl(r.expected_amount)}</Td>
                  <Td>{brl(r.registered_amount)}</Td>
                  <Td>{brl(r.received_amount)}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        ) : (
          <EmptyState title="Nenhum lançamento" />
        )}

        <NewRoyaltyModal
          contractId={contractId}
          open={open}
          onClose={() => setOpen(false)}
        />
      </CardBody>
    </Card>
  );
}

/** Decimal-exact financial summary (registered - received = pending). */
export function RoyaltySummaryCard({ contractId }: { contractId: string }) {
  const { data, isLoading } = useNitRoyaltySummary(contractId);
  if (isLoading) return <Spinner />;
  if (!data) return null;
  return (
    <dl className="space-y-2 text-sm">
      <Row label="Total esperado" value={brl(data.total_expected)} />
      <Row label="Total registrado" value={brl(data.total_registered)} />
      <Row label="Total recebido" value={brl(data.total_received)} />
      <Row label="Pendente" value={brl(data.pending)} strong />
      <Row label="Lançamentos" value={String(data.entries)} />
    </dl>
  );
}

function Row({
  label,
  value,
  strong,
}: {
  label: string;
  value: string;
  strong?: boolean;
}) {
  return (
    <div className="flex items-center justify-between">
      <dt className="text-slate-500">{label}</dt>
      <dd className={strong ? "font-semibold text-slate-800" : "text-slate-700"}>
        {value}
      </dd>
    </div>
  );
}

function NewRoyaltyModal({
  contractId,
  open,
  onClose,
}: {
  contractId: string;
  open: boolean;
  onClose: () => void;
}) {
  const create = useCreateRoyalty(contractId);
  const [period, setPeriod] = useState("");
  const [expected, setExpected] = useState("");
  const [registered, setRegistered] = useState("");
  const [received, setReceived] = useState("");

  function toPayload(v: string) {
    return v.trim() ? v.trim() : null;
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Novo lançamento de royalty"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            disabled={!period.trim() || create.isPending}
            onClick={() =>
              create.mutate(
                {
                  period,
                  expected_amount: toPayload(expected),
                  registered_amount: toPayload(registered),
                  received_amount: toPayload(received),
                },
                {
                  onSuccess: () => {
                    setPeriod("");
                    setExpected("");
                    setRegistered("");
                    setReceived("");
                    onClose();
                  },
                },
              )
            }
          >
            {create.isPending ? "Salvando…" : "Adicionar"}
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
          label="Período"
          placeholder="Ex.: 2026-01"
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
        />
        <Input
          label="Valor esperado"
          placeholder="Ex.: 1000.00"
          value={expected}
          onChange={(e) => setExpected(e.target.value)}
        />
        <Input
          label="Valor registrado"
          placeholder="Ex.: 1000.00"
          value={registered}
          onChange={(e) => setRegistered(e.target.value)}
        />
        <Input
          label="Valor recebido"
          placeholder="Ex.: 500.00"
          value={received}
          onChange={(e) => setReceived(e.target.value)}
        />
      </div>
    </Modal>
  );
}
