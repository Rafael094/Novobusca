"use client";

import { useState } from "react";

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
  statusTone,
} from "@/components/ui";
import { useDatasets, useImports, useSyncStatus, useTriggerSync } from "@/lib/hooks";

export default function AdminPage() {
  const status = useSyncStatus();
  const datasets = useDatasets();
  const imports = useImports();
  const trigger = useTriggerSync();
  const [category, setCategory] = useState("marcas");
  const [force, setForce] = useState(false);

  const imported = status.data?.datasets.imported ?? 0;
  const total = status.data?.datasets.total ?? 0;
  const progress = total > 0 ? Math.round((imported / total) * 100) : 0;

  return (
    <>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">
          Administração · Sincronização INPI
        </h1>
        <p className="text-sm text-slate-500">
          Status dos datasets e disparo de importações.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <p className="text-sm text-slate-500">Datasets importados</p>
          <p className="mt-1 text-2xl font-bold text-brand-700">
            {status.data ? `${imported} / ${total}` : "…"}
          </p>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-brand-600 transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </Card>
        <Card className="p-5">
          <p className="text-sm text-slate-500">Datasets com falha</p>
          <p className="mt-1 text-2xl font-bold text-red-600">
            {status.data ? status.data.datasets.failed : "…"}
          </p>
        </Card>
        <Card className="p-5">
          <p className="text-sm text-slate-500">Imports em execução</p>
          <p className="mt-1 text-2xl font-bold text-amber-600">
            {status.data ? status.data.imports_running : "…"}
          </p>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader
          title="Disparar sincronização"
          subtitle="Importação completa ou incremental"
        />
        <CardBody>
          <div className="flex flex-wrap items-center gap-3">
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm outline-none focus:border-brand-500"
            >
              <option value="marcas">Marcas</option>
              <option value="patentes">Patentes</option>
            </select>
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input
                type="checkbox"
                checked={force}
                onChange={(e) => setForce(e.target.checked)}
              />
              Forçar reimportação (completa)
            </label>
            <Button
              onClick={() => trigger.mutate({ category, force })}
              disabled={trigger.isPending}
            >
              {trigger.isPending ? "Iniciando…" : "Sincronizar"}
            </Button>
          </div>
          {trigger.isError && (
            <div className="mt-3">
              <ErrorNote>
                {trigger.error instanceof Error
                  ? trigger.error.message
                  : "Falha ao disparar sincronização."}
              </ErrorNote>
            </div>
          )}
          {trigger.isSuccess && (
            <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
              Ingestão iniciada para: {category}.
            </p>
          )}
        </CardBody>
      </Card>

      <Card className="mt-6">
        <CardHeader title="Datasets" />
        {datasets.isLoading ? (
          <CardBody>
            <Spinner />
          </CardBody>
        ) : (
          <Table>
            <thead className="bg-slate-50">
              <tr>
                <Th>Nome</Th>
                <Th>Categoria</Th>
                <Th>Status</Th>
                <Th>Data ref.</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {datasets.data?.map((d) => (
                <tr key={d.id} className="hover:bg-slate-50">
                  <Td className="font-medium text-slate-700">{d.name}</Td>
                  <Td>{d.category}</Td>
                  <Td>
                    <Badge tone={statusTone(d.status)}>{d.status}</Badge>
                  </Td>
                  <Td>{d.reference_date || "—"}</Td>
                </tr>
              ))}
              {datasets.data && datasets.data.length === 0 && (
                <EmptyRow colSpan={4} message="Nenhum dataset registrado." />
              )}
            </tbody>
          </Table>
        )}
      </Card>

      <Card className="mt-6">
        <CardHeader
          title="Importações recentes"
          subtitle="Atualização automática a cada 5s"
        />
        <Table>
          <thead className="bg-slate-50">
            <tr>
              <Th>Status</Th>
              <Th>Rows lidas</Th>
              <Th>Inseridas</Th>
              <Th>Erros</Th>
              <Th>Início</Th>
              <Th>Progresso</Th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {imports.data?.map((r) => {
              const pct =
                r.rows_read > 0
                  ? Math.min(
                      100,
                      Math.round((r.rows_inserted / r.rows_read) * 100),
                    )
                  : 0;
              return (
                <tr key={r.id} className="hover:bg-slate-50">
                  <Td>
                    <Badge tone={statusTone(r.status)}>{r.status}</Badge>
                  </Td>
                  <Td>{r.rows_read.toLocaleString("pt-BR")}</Td>
                  <Td>{r.rows_inserted.toLocaleString("pt-BR")}</Td>
                  <Td>{r.error_count}</Td>
                  <Td>{new Date(r.started_at).toLocaleString("pt-BR")}</Td>
                  <Td>
                    <div className="h-2 w-28 overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-brand-600"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </Td>
                </tr>
              );
            })}
            {imports.data && imports.data.length === 0 && (
              <EmptyRow colSpan={6} message="Nenhuma importação registrada." />
            )}
          </tbody>
        </Table>
      </Card>
    </>
  );
}
