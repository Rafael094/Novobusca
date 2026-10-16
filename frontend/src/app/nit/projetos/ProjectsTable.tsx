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
import type { NitProject, PaginatedNit } from "@/lib/types";

export const PROJECT_STATUS_LABELS: Record<string, string> = {
  PLANNED: "Planejado",
  ACTIVE: "Em execução",
  COMPLETED: "Concluído",
  CANCELLED: "Cancelado",
};

export function ProjectsTable({
  data,
  isLoading,
  page,
  pageSize,
  onPage,
}: {
  data: PaginatedNit<NitProject> | undefined;
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
                <Th>Área</Th>
                <Th>Situação</Th>
                <Th>Início</Th>
                <Th>Fim</Th>
                <Th />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {data && data.items.length > 0 ? (
                data.items.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/60">
                    <Td className="font-medium text-slate-700">{p.code}</Td>
                    <Td>{p.title}</Td>
                    <Td>{p.technology_area || "—"}</Td>
                    <Td>
                      <Badge
                        tone={p.status === "ACTIVE" ? "green" : p.status === "CANCELLED" ? "red" : "slate"}
                      >
                        {PROJECT_STATUS_LABELS[p.status] || p.status}
                      </Badge>
                    </Td>
                    <Td>{p.start_date || "—"}</Td>
                    <Td>{p.end_date || "—"}</Td>
                    <Td>
                      <Link
                        href={`/nit/projetos/${p.id}`}
                        className="text-sm font-medium text-brand-700 hover:underline"
                      >
                        Abrir
                      </Link>
                    </Td>
                  </tr>
                ))
              ) : (
                <EmptyRow colSpan={7} message="Nenhum projeto encontrado." />
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


