"use client";

import Link from "next/link";

import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyRow,
  Pagination,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";
import type { NitContract, NitObligationAlert, PaginatedNit } from "@/lib/types";

export const CONTRACT_STATUS_LABELS: Record<string, string> = {
  DRAFT: "Rascunho",
  ACTIVE: "Vigente",
  EXPIRED: "Expirado",
  TERMINATED: "Rescindido",
};

export function ObligationAlertsCard({
  alerts,
}: {
  alerts: NitObligationAlert[] | undefined;
}) {
  if (!alerts || alerts.length === 0) return null;
  return (
    <Card className="mb-4 border-amber-100">
      <CardHeader
        title="Obrigações próximas do vencimento"
        subtitle="Somente obrigações pendentes com prazo registrado"
      />
      <CardBody>
        <ul className="space-y-2">
          {alerts.map((a) => (
            <li
              key={a.obligation_id}
              className="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2"
            >
              <div>
                <p className="text-sm text-slate-700">{a.description}</p>
                <p className="text-xs text-slate-400">
                  {a.contract_code} · vence em{" "}
                  {new Date(a.due_date).toLocaleDateString("pt-BR")}
                </p>
              </div>
              <Badge
                tone={
                  a.severity === "overdue"
                    ? "red"
                    : a.severity === "critical"
                      ? "orange"
                      : "amber"
                }
              >
                {a.days_to_due < 0
                  ? `${Math.abs(a.days_to_due)}d atrasado`
                  : `${a.days_to_due}d`}
              </Badge>
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

export function ContractsTable({
  data,
  isLoading,
  page,
  pageSize,
  onPage,
}: {
  data: PaginatedNit<NitContract> | undefined;
  isLoading: boolean;
  page: number;
  pageSize: number;
  onPage: (page: number) => void;
}) {
  return (
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
                <Th>Código</Th>
                <Th>Título</Th>
                <Th>Situação</Th>
                <Th>Valor registrado</Th>
                <Th />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data && data.items.length > 0 ? (
                data.items.map((c) => (
                  <tr key={c.id} className="hover:bg-slate-50/60">
                    <Td className="font-medium text-slate-700">{c.code}</Td>
                    <Td>{c.title}</Td>
                    <Td>
                      <Badge
                        tone={
                          c.status === "ACTIVE"
                            ? "green"
                            : c.status === "TERMINATED"
                              ? "red"
                              : "slate"
                        }
                      >
                        {CONTRACT_STATUS_LABELS[c.status] || c.status}
                      </Badge>
                    </Td>
                    <Td>
                      {c.registered_amount
                        ? `R$ ${Number(c.registered_amount).toLocaleString("pt-BR", {
                            minimumFractionDigits: 2,
                          })}`
                        : "—"}
                    </Td>
                    <Td>
                      <Link
                        href={`/nit/contratos/${c.id}`}
                        className="text-sm font-medium text-brand-700 hover:underline"
                      >
                        Abrir
                      </Link>
                    </Td>
                  </tr>
                ))
              ) : (
                <EmptyRow colSpan={5} message="Nenhum contrato encontrado." />
              )}
            </tbody>
          </Table>
          {data && (
            <Pagination
              page={page}
              pageSize={pageSize}
              total={data.total}
              onPage={onPage}
            />
          )}
        </>
      )}
    </Card>
  );
}
