"use client";

import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Button,
  Card,
  CardBody,
  EmptyRow,
  ErrorNote,
  Pagination,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { downloadNitDocument, useNitDocuments } from "@/lib/hooks";

const LEVEL_TONES: Record<string, "green" | "blue" | "amber" | "red"> = {
  PUBLIC: "green",
  INTERNAL: "blue",
  RESTRICTED: "amber",
  CONFIDENTIAL: "red",
};

export default function NitDocumentsPage() {
  const [page, setPage] = useState(1);
  const pageSize = 20;
  const { data, isLoading, error } = useNitDocuments({
    page,
    page_size: pageSize,
  });

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Documentos</h1>
        <p className="text-sm text-slate-500">
          Documentos confidenciais do NIT, visíveis somente a usuários autorizados.
        </p>
      </div>

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
                  <Th>Arquivo</Th>
                  <Th>Tipo</Th>
                  <Th>Sigilo</Th>
                  <Th>Enviado em</Th>
                  <Th />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {data && data.items.length > 0 ? (
                  data.items.map((doc) => (
                    <tr key={doc.id} className="hover:bg-slate-50/60">
                      <Td className="font-medium text-slate-700">
                        {doc.title || doc.original_filename}
                      </Td>
                      <Td>{doc.mime_type}</Td>
                      <Td>
                        <Badge
                          tone={LEVEL_TONES[doc.confidentiality_level] || "slate"}
                        >
                          {doc.confidentiality_level}
                        </Badge>
                      </Td>
                      <Td>
                        {new Date(doc.created_at).toLocaleDateString("pt-BR")}
                      </Td>
                      <Td>
                        <Button
                          variant="secondary"
                          className="px-3 py-1.5"
                          onClick={() =>
                            downloadNitDocument(
                              doc.id,
                              doc.original_filename,
                            ).catch(() => undefined)
                          }
                        >
                          Baixar
                        </Button>
                      </Td>
                    </tr>
                  ))
                ) : (
                  <EmptyRow colSpan={5} message="Nenhum documento disponível." />
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
    </AppShell>
  );
}
