"use client";

import { useState } from "react";

import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyRow,
  Spinner,
  Table,
  Tabs,
  Td,
  Th,
} from "@/components/ui";
import { useAdminModules, useAdminRoles } from "@/lib/hooks";

export default function ModulosPage() {
  const [tab, setTab] = useState("modules");
  const modules = useAdminModules();
  const roles = useAdminRoles();

  return (
    <>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Módulos & Papéis</h1>
        <p className="text-sm text-slate-500">
          Catálogo de módulos e papéis de controle de acesso.
        </p>
      </div>

      <Card>
        <Tabs
          active={tab}
          onChange={setTab}
          tabs={[
            { id: "modules", label: "Módulos" },
            { id: "roles", label: "Papéis" },
          ]}
        />
        <CardBody>
          {tab === "modules" && (
            <div className="rounded-xl border border-gray-100">
              <Table>
                <thead className="bg-slate-50">
                  <tr>
                    <Th>Código</Th>
                    <Th>Nome</Th>
                    <Th>Descrição</Th>
                    <Th>Status</Th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {modules.isLoading && (
                    <tr>
                      <td colSpan={4} className="px-4 py-6">
                        <Spinner />
                      </td>
                    </tr>
                  )}
                  {modules.data?.map((m) => (
                    <tr key={m.id} className="hover:bg-slate-50">
                      <Td className="font-mono text-xs text-slate-500">{m.code}</Td>
                      <Td className="font-medium text-slate-700">{m.name}</Td>
                      <Td>{m.description || "—"}</Td>
                      <Td>
                        <Badge tone={m.active ? "green" : "slate"}>
                          {m.active ? "Ativo" : "Inativo"}
                        </Badge>
                      </Td>
                    </tr>
                  ))}
                  {modules.data && modules.data.length === 0 && (
                    <EmptyRow colSpan={4} message="Nenhum módulo." />
                  )}
                </tbody>
              </Table>
            </div>
          )}

          {tab === "roles" && (
            <div className="space-y-3">
              {roles.isLoading && <Spinner />}
              {roles.data?.map((r) => (
                <div
                  key={r.id}
                  className="rounded-xl border border-gray-100 p-4"
                >
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-slate-700">{r.name}</span>
                      <Badge tone="blue">{r.code}</Badge>
                      {r.is_system && <Badge tone="amber">sistema</Badge>}
                    </div>
                    <span className="text-xs text-slate-400">
                      {r.permissions.length} permissão(ões)
                    </span>
                  </div>
                  {r.description && (
                    <p className="mb-2 text-sm text-slate-500">{r.description}</p>
                  )}
                  <div className="flex flex-wrap gap-1">
                    {r.permissions.slice(0, 20).map((p) => (
                      <span
                        key={p}
                        className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-500"
                      >
                        {p}
                      </span>
                    ))}
                    {r.permissions.length > 20 && (
                      <span className="text-xs text-slate-400">
                        +{r.permissions.length - 20}
                      </span>
                    )}
                  </div>
                </div>
              ))}
              {roles.data && roles.data.length === 0 && (
                <EmptyRow colSpan={1} message="Nenhum papel." />
              )}
            </div>
          )}
        </CardBody>
      </Card>
    </>
  );
}
