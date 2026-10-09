"use client";

import { useState } from "react";

import AppShell from "@/components/AppShell";
import {
  Badge,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Spinner,
} from "@/components/ui";
import {
  useMarcasMonitoramento,
  usePatentesMonitoramento,
  useSetMarcaMonitoramento,
  useSetPatenteMonitoramento,
} from "@/lib/hooks";
import { formatDate } from "@/lib/marcas";
import type { Monitoramento, Paginated } from "@/lib/types";

/**
 * Monitoramento page (spec section 4).
 *
 * Shows ONLY what the current user chose to watch — the selective per-user
 * watch lists (`GET /api/marcas/monitoramento` / `GET /api/patentes/monitoramento`).
 * Nothing is listed globally: a row appears here only after the user activates
 * the "Monitoramento" toggle for that specific marca/patente on the search
 * screens. Turning the toggle off here removes it from the list.
 */
export default function MonitoramentoPage() {
  const [marcaPage, setMarcaPage] = useState(1);
  const [patentePage, setPatentePage] = useState(1);

  const marcas = useMarcasMonitoramento(marcaPage, 20);
  const patentes = usePatentesMonitoramento(patentePage, 20);

  const toggleMarca = useSetMarcaMonitoramento();
  const togglePatente = useSetPatenteMonitoramento();

  const isLoading = marcas.isLoading || patentes.isLoading;
  const error = marcas.error || patentes.error;
  const totalMonitored =
    (marcas.data?.pagination.total ?? 0) +
    (patentes.data?.pagination.total ?? 0);

  return (
    <AppShell>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-800">Monitoramento</h1>
        <p className="text-sm text-slate-500">
          Acompanhamento seletivo das marcas e patentes que você marcou para
          monitorar.
        </p>
      </div>

      {isLoading && <Spinner />}
      {error && (
        <ErrorNote>
          {error instanceof Error ? error.message : "Erro ao carregar."}
        </ErrorNote>
      )}

      {!isLoading && !error && totalMonitored === 0 && (
        <Card>
          <CardBody>
            <EmptyState
              title="Você ainda não monitora nenhuma marca ou patente."
              description='Use a coluna "Monitoramento" nas telas de Marcas e Patentes para acompanhar itens específicos.'
            />
          </CardBody>
        </Card>
      )}

      {!isLoading && totalMonitored > 0 && (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <MonitoramentoList
            title="Marcas monitoradas"
            tipo="marca"
            tone="blue"
            data={marcas.data}
            isFetching={marcas.isFetching}
            page={marcaPage}
            onPage={setMarcaPage}
            busyId={
              toggleMarca.isPending ? toggleMarca.variables?.codigo : undefined
            }
            onRemove={(codigo) => toggleMarca.mutate({ codigo, active: false })}
          />

          <MonitoramentoList
            title="Patentes monitoradas"
            tipo="patente"
            tone="slate"
            data={patentes.data}
            isFetching={patentes.isFetching}
            page={patentePage}
            onPage={setPatentePage}
            busyId={
              togglePatente.isPending ? togglePatente.variables?.codigo : undefined
            }
            onRemove={(codigo) => togglePatente.mutate({ codigo, active: false })}
          />
        </div>
      )}
    </AppShell>
  );
}


/**
 * One watch-list column (marcas or patentes). Renders only the current user's
 * monitored items; "Remover" deactivates monitoring for that specific record.
 */
function MonitoramentoList({
  title,
  tipo,
  tone,
  data,
  isFetching,
  page,
  onPage,
  busyId,
  onRemove,
}: {
  title: string;
  tipo: "marca" | "patente";
  tone: "blue" | "slate";
  data: Paginated<Monitoramento> | undefined;
  isFetching: boolean;
  page: number;
  onPage: (next: number) => void;
  busyId?: string;
  onRemove: (codigo: string) => void;
}) {
  const items = data?.items ?? [];
  const total = data?.pagination.total ?? 0;
  const totalPages = data
    ? Math.max(1, Math.ceil(data.pagination.total / data.pagination.page_size))
    : 1;

  return (
    <Card>
      <CardHeader
        title={title}
        subtitle={
          total > 0
            ? `${total} ${total === 1 ? "item" : "itens"} sob acompanhamento`
            : undefined
        }
      />
      <CardBody className="space-y-3">
        {items.length === 0 && (
          <EmptyState
            title={
              tipo === "marca"
                ? "Nenhuma marca monitorada."
                : "Nenhuma patente monitorada."
            }
            description={
              isFetching
                ? "Atualizando…"
                : "Ative o monitoramento nas telas de busca."
            }
          />
        )}

        {items.map((m) => (
          <div
            key={m.id}
            className="flex items-center justify-between gap-3 border-b border-gray-50 pb-2 last:border-0"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-700">
                {m.titulo || "—"}
              </p>
              <p className="text-xs text-slate-400">
                {m.numero_inpi || m.codigo_interno}
                {m.data_deposito ? ` · ${formatDate(m.data_deposito)}` : ""}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {m.situacao && <Badge tone={tone}>{m.situacao}</Badge>}
              <button
                type="button"
                disabled={busyId === m.codigo_interno}
                onClick={() => onRemove(m.codigo_interno)}
                title="Remover do monitoramento"
                className="rounded-lg border border-gray-200 px-2 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {busyId === m.codigo_interno ? "…" : "Remover"}
              </button>
            </div>
          </div>
        ))}

        {totalPages > 1 && (
          <div className="flex items-center justify-between pt-1">
            <button
              type="button"
              disabled={page <= 1}
              onClick={() => onPage(page - 1)}
              className="rounded-lg border border-gray-200 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Anterior
            </button>
            <span className="text-xs text-slate-400">
              Página {page} de {totalPages}
            </span>
            <button
              type="button"
              disabled={page >= totalPages}
              onClick={() => onPage(page + 1)}
              className="rounded-lg border border-gray-200 px-3 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              Próxima
            </button>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

