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
  Input,
  Select,
  Spinner,
  Table,
  Td,
  Th,
} from "@/components/ui";
import { useAuth } from "@/app/auth-context";
import {
  useCreateIntegrationEndpoint,
  useNitIntegrationDeliveries,
  useNitIntegrationEndpoints,
} from "@/lib/hooks";

const KINDS = ["SIGA", "SEI", "EMAIL", "WEBHOOK"];

export default function IntegrationsPage() {
  const { has } = useAuth();
  const { data: endpoints, isLoading, error } = useNitIntegrationEndpoints();
  const { data: deliveries } = useNitIntegrationDeliveries();
  const create = useCreateIntegrationEndpoint();
  const canManage = has("NIT_INTEGRATION_MANAGE");

  const [kind, setKind] = useState("SEI");
  const [name, setName] = useState("");
  const [enabled, setEnabled] = useState(false);

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Integrações</h1>
        <p className="text-sm text-slate-500">
          Registro declarativo de integrações (SIGA/SEI/e-mail/webhook). Eventos são
          enfileirados e permanecem &quot;Pendente&quot; até que um adaptador real os envie —
          nada é declarado entregue sem transporte real.
        </p>
      </div>

      {error ? <ErrorNote>{(error as Error).message}</ErrorNote> : null}

      {canManage ? (
        <Card className="mb-6">
          <CardHeader title="Nova integração" />
          <CardBody>
            <div className="grid gap-3 sm:grid-cols-4">
              <Select label="Tipo" value={kind} onChange={(e) => setKind(e.target.value)}>
                {KINDS.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </Select>
              <Input label="Nome" value={name} onChange={(e) => setName(e.target.value)} />
              <label className="flex items-end gap-2 pb-2 text-sm text-slate-600">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => setEnabled(e.target.checked)}
                />
                Habilitada
              </label>
              <div className="flex items-end">
                <Button
                  disabled={!name.trim() || create.isPending}
                  onClick={() =>
                    create.mutate(
                      { kind, name, enabled },
                      {
                        onSuccess: () => {
                          setName("");
                          setEnabled(false);
                        },
                      },
                    )
                  }
                >
                  Criar
                </Button>
              </div>
            </div>
            {create.error ? (
              <div className="mt-3">
                <ErrorNote>{(create.error as Error).message}</ErrorNote>
              </div>
            ) : null}
          </CardBody>
        </Card>
      ) : null}

      <Card className="mb-6">
        <CardHeader title="Integrações registradas" />
        <CardBody className="p-0">
          {isLoading ? (
            <div className="p-5">
              <Spinner />
            </div>
          ) : (
            <Table>
              <thead className="bg-slate-50">
                <tr>
                  <Th>Tipo</Th>
                  <Th>Nome</Th>
                  <Th>Estado</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {endpoints && endpoints.length > 0 ? (
                  endpoints.map((e) => (
                    <tr key={e.id}>
                      <Td>
                        <Badge tone="slate">{e.kind}</Badge>
                      </Td>
                      <Td>{e.name}</Td>
                      <Td>
                        <Badge tone={e.enabled ? "green" : "slate"}>
                          {e.enabled ? "Habilitada" : "Desabilitada"}
                        </Badge>
                      </Td>
                    </tr>
                  ))
                ) : (
                  <EmptyRow colSpan={3} message="Nenhuma integração registrada." />
                )}
              </tbody>
            </Table>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Fila de entregas (outbox)"
          subtitle="Permanecem pendentes até um transporte real"
        />
        <CardBody className="p-0">
          <Table>
            <thead className="bg-slate-50">
              <tr>
                <Th>Evento</Th>
                <Th>Situação</Th>
                <Th>Criada em</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {deliveries && deliveries.length > 0 ? (
                deliveries.map((d) => (
                  <tr key={d.id}>
                    <Td>{d.event}</Td>
                    <Td>
                      <Badge
                        tone={
                          d.status === "SENT"
                            ? "green"
                            : d.status === "FAILED"
                              ? "red"
                              : "amber"
                        }
                      >
                        {d.status}
                      </Badge>
                    </Td>
                    <Td>{new Date(d.created_at).toLocaleString("pt-BR")}</Td>
                  </tr>
                ))
              ) : (
                <EmptyRow colSpan={3} message="Nenhuma entrega enfileirada." />
              )}
            </tbody>
          </Table>
        </CardBody>
      </Card>
    </AppShell>
  );
}
