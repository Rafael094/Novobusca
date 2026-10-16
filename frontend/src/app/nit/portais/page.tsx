"use client";

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
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { useAuth } from "@/app/auth-context";
import {
  useNitPortalAccess,
  useNitPortalRequests,
  useRevokePortalAccess,
} from "@/lib/hooks";
import { NewAccessModal, TriageButton } from "./PortalWidgets";

const KIND_LABELS: Record<string, string> = {
  RESEARCHER: "Pesquisador",
  COMPANY: "Empresa",
};

export default function PortalsPage() {
  const { has } = useAuth();
  const { data: access, isLoading, error } = useNitPortalAccess();
  const { data: requests } = useNitPortalRequests();
  const revoke = useRevokePortalAccess();
  const [openNew, setOpenNew] = useState(false);

  const canManage = has("NIT_PORTAL_MANAGE");
  const canTriage = has("NIT_PORTAL_REQUEST_MANAGE");

  return (
    <AppShell>
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Portais externos</h1>
          <p className="text-sm text-slate-500">
            Acesso explícito, revogável e limitado para pesquisadores e empresas. Uma
            concessão nunca confere permissões internas.
          </p>
        </div>
        {canManage && <Button onClick={() => setOpenNew(true)}>Nova concessão</Button>}
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}

      <Card className="mb-6">
        <CardHeader title="Concessões de acesso" />
        <CardBody className="p-0">
          {isLoading ? (
            <div className="p-5">
              <Spinner />
            </div>
          ) : (
            <Table>
              <thead className="bg-slate-50">
                <tr>
                  <Th>Portal</Th>
                  <Th>Nome</Th>
                  <Th>E-mail</Th>
                  <Th>Situação</Th>
                  <Th />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {access && access.length > 0 ? (
                  access.map((a) => (
                    <tr key={a.id}>
                      <Td>
                        <Badge tone={a.portal_kind === "COMPANY" ? "blue" : "slate"}>
                          {KIND_LABELS[a.portal_kind] || a.portal_kind}
                        </Badge>
                      </Td>
                      <Td>{a.name}</Td>
                      <Td>{a.email}</Td>
                      <Td>
                        <Badge tone={a.status === "ACTIVE" ? "green" : "red"}>
                          {a.status === "ACTIVE" ? "Ativo" : "Revogado"}
                        </Badge>
                      </Td>
                      <Td>
                        {canManage && a.status === "ACTIVE" ? (
                          <Button
                            variant="ghost"
                            disabled={revoke.isPending}
                            onClick={() => revoke.mutate(a.id)}
                          >
                            Revogar
                          </Button>
                        ) : null}
                      </Td>
                    </tr>
                  ))
                ) : (
                  <EmptyRow colSpan={5} message="Nenhuma concessão registrada." />
                )}
              </tbody>
            </Table>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Solicitações externas"
          subtitle="Enviadas pelos portais e triadas internamente"
        />
        <CardBody className="p-0">
          <Table>
            <thead className="bg-slate-50">
              <tr>
                <Th>Tipo</Th>
                <Th>Assunto</Th>
                <Th>Situação</Th>
                <Th />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {requests && requests.length > 0 ? (
                requests.map((r) => (
                  <tr key={r.id}>
                    <Td>{r.request_type}</Td>
                    <Td>{r.subject}</Td>
                    <Td>
                      <Badge
                        tone={
                          r.status === "ACCEPTED"
                            ? "green"
                            : r.status === "REJECTED"
                              ? "red"
                              : r.status === "NEW"
                                ? "amber"
                                : "slate"
                        }
                      >
                        {r.status}
                      </Badge>
                    </Td>
                    <Td>{canTriage ? <TriageButton requestId={r.id} /> : null}</Td>
                  </tr>
                ))
              ) : (
                <EmptyRow colSpan={4} message="Nenhuma solicitação recebida." />
              )}
            </tbody>
          </Table>
        </CardBody>
      </Card>

      <NewAccessModal open={openNew} onClose={() => setOpenNew(false)} />
    </AppShell>
  );
}
