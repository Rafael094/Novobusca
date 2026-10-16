"use client";

import Link from "next/link";

import {
  Badge,
  Card,
  CardBody,
  EmptyRow,
  Pagination,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";
import type { NitStartup, PaginatedNit } from "@/lib/types";

export const STARTUP_STATUS_LABELS: Record<string, string> = {
  IDEATION: "Ideação",
  PROTOTYPE: "Protótipo",
  OPERATION: "Operação",
  SCALE: "Escala",
  INCUBATED: "Incubada",
  GRADUATED: "Graduada",
  CLOSED: "Encerrada",
};

export function StartupsTable({
  data,
  isLoading,
  page,
  pageSize,
  onPage,
}: {
  data: PaginatedNit<NitStartup> | undefined;
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
                <Th>Nome</Th>
                <Th>Estágio</Th>
                <Th>Situação</Th>
                <Th>CNPJ</Th>
                <Th />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data && data.items.length > 0 ? (
                data.items.map((s) => (
                  <tr key={s.id} className="hover:bg-slate-50/60">
                    <Td className="font-medium text-slate-700">{s.code}</Td>
                    <Td>{s.name}</Td>
                    <Td>{s.stage || "—"}</Td>
                    <Td>
                      <Badge
                        tone={
                          s.status === "INCUBATED"
                            ? "green"
                            : s.status === "CLOSED"
                              ? "red"
                              : "slate"
                        }
                      >
                        {STARTUP_STATUS_LABELS[s.status] || s.status}
                      </Badge>
                    </Td>
                    <Td>{s.cnpj || "—"}</Td>
                    <Td>
                      <Link
                        href={`/nit/startups/${s.id}`}
                        className="text-sm font-medium text-brand-700 hover:underline"
                      >
                        Abrir
                      </Link>
                    </Td>
                  </tr>
                ))
              ) : (
                <EmptyRow colSpan={6} message="Nenhuma startup encontrada." />
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
