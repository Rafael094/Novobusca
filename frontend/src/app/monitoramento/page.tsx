"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import AppShell from "@/components/AppShell";
import MarcaDetailModal from "@/components/MarcaDetailModal";
import PageHeader from "@/components/PageHeader";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  ErrorNote,
  Spinner,
} from "@/components/ui";
import {
  useMarcaLogo,
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
  // Marca whose detail modal is open (spec section 6: "Ver" opens the modal).
  const [selectedMarca, setSelectedMarca] = useState<string | null>(null);

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
      <PageHeader
        title="Monitoramento"
        description="Acompanhamento seletivo das marcas e patentes que você marcou para monitorar."
      />

      {isLoading && <Spinner />}
      {error && (
        <ErrorNote>
          {error instanceof Error ? error.message : "Erro ao carregar."}
        </ErrorNote>
      )}

      {!isLoading && !error && totalMonitored === 0 && (
        <Card>
          <CardBody>
            <div className="mx-auto max-w-2xl py-6 text-center">
              <span
                className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-brand-50 text-2xl text-brand-700"
                aria-hidden="true"
              >
                🛰
              </span>
              <h2 className="mt-4 text-lg font-semibold text-slate-800">
                Configure seu monitoramento
              </h2>
              <p className="mt-2 text-sm text-slate-500">
                O monitoramento do IntelliINPI é <strong>seletivo</strong>: nada é
                acompanhado automaticamente. Você escolhe, item a item, quais
                marcas e patentes acompanhar.
              </p>
              <ul className="mx-auto mt-4 max-w-md space-y-2 text-left text-sm text-slate-600">
                <li className="flex gap-2">
                  <span className="text-brand-600">•</span>
                  Acompanhe a tramitação e os despachos dos processos dos seus
                  clientes.
                </li>
                <li className="flex gap-2">
                  <span className="text-brand-600">•</span>
                  Veja prazos e vencimentos no painel de Visão Geral e nas
                  propostas pendentes.
                </li>
                <li className="flex gap-2">
                  <span className="text-brand-600">•</span>
                  Remova um item a qualquer momento, sem perder o histórico.
                </li>
              </ul>
              <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
                <Link href="/marcas">
                  <Button>Monitorar uma marca</Button>
                </Link>
                <Link href="/patentes">
                  <Button variant="secondary">Monitorar uma patente</Button>
                </Link>
              </div>
              <p className="mt-4 text-xs text-slate-400">
                Para ativar o monitoramento, use a coluna &quot;Monitoramento&quot;
                nas telas de Marcas e Patentes.
              </p>
            </div>
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
            onView={(codigo) => setSelectedMarca(codigo)}
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

      {/* Marca detail modal (spec section 6): "Ver" opens it in place. */}
      <MarcaDetailModal
        codigoInterno={selectedMarca}
        onClose={() => setSelectedMarca(null)}
      />
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
  onView,
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
  onView?: (codigo: string) => void;
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
          <MonitoramentoRow
            key={m.id}
            m={m}
            tone={tone}
            busy={busyId === m.codigo_interno}
            onRemove={() => onRemove(m.codigo_interno)}
            onView={onView}
          />
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


/**
 * One monitored item. Marcas are shown with *all* available data — logotipo,
 * datas (depósito/publicação/concessão/vigência), apresentação/natureza,
 * titulares, agregado de despachos and the vencimento status. Patentes keep the
 * compact layout (their enriched fields are not part of this change).
 */
function MonitoramentoRow({
  m,
  tone,
  busy,
  onRemove,
  onView,
}: {
  m: Monitoramento;
  tone: "blue" | "slate";
  busy: boolean;
  onRemove: () => void;
  onView?: (codigo: string) => void;
}) {
  const isMarca = m.tipo !== "patente";

  return (
    <div className="flex items-start justify-between gap-3 border-b border-gray-50 pb-3 last:border-0">
      <div className="flex min-w-0 flex-1 items-start gap-3">
        {isMarca && <MarcaMonitoradaLogo m={m} />}

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="truncate text-sm font-medium text-slate-700">
              {m.titulo || "—"}
            </p>
            {m.situacao && <Badge tone={tone}>{m.situacao}</Badge>}
            {isMarca && <VencimentoBadge m={m} />}
          </div>

          <p className="mt-0.5 text-xs text-slate-400">
            {m.numero_inpi || m.codigo_interno}
          </p>

          {isMarca && <MarcaDetalhes m={m} />}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 pt-0.5">
        {isMarca ? (
          // Section 6: "Ver" opens the marca detail modal in place — it no
          // longer navigates to /marcas (which lost the selected item).
          <button
            type="button"
            onClick={() => onView?.(m.codigo_interno)}
            className="text-xs font-medium text-brand-600 hover:text-brand-700"
          >
            Ver
          </button>
        ) : (
          <Link
            href="/patentes"
            className="text-xs font-medium text-brand-600 hover:text-brand-700"
          >
            Ver
          </Link>
        )}
        <button
          type="button"
          disabled={busy}
          onClick={onRemove}
          title="Remover do monitoramento"
          className="rounded-lg border border-gray-200 px-2 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "…" : "Remover"}
        </button>
      </div>
    </div>
  );
}

/** Dates, apresentação/natureza and titulares/despachos for a monitored marca. */
function MarcaDetalhes({ m }: { m: Monitoramento }) {
  const hasTitular = m.num_titulares > 0;
  const hasDespacho = m.total_despachos > 0;
  return (
    <>
      <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-500">
        <FieldLabel label="Depósito" value={formatDate(m.data_deposito)} />
        <FieldLabel label="Publicação" value={formatDate(m.data_publicacao)} />
        <FieldLabel label="Concessão" value={formatDate(m.data_concessao)} />
        <FieldLabel label="Vigência" value={formatDate(m.data_vigencia)} />
        {m.descricao_apresentacao && (
          <FieldLabel label="Apresentação" value={m.descricao_apresentacao} />
        )}
        {m.descricao_natureza && (
          <FieldLabel label="Natureza" value={m.descricao_natureza} />
        )}
      </div>

      {(hasTitular || hasDespacho) && (
        <div className="mt-2 space-y-0.5 text-xs text-slate-500">
          {hasTitular && (
            <p>
              <span className="text-slate-400">Titulares: </span>
              {m.titular_principal || `${m.num_titulares} titular(es)`}
              {m.num_titulares > 1 && (
                <span className="text-slate-400"> (+{m.num_titulares - 1})</span>
              )}
            </p>
          )}
          {hasDespacho && (
            <p>
              <span className="text-slate-400">Último despacho: </span>
              {m.ultimo_despacho ? `${m.ultimo_despacho} ` : ""}
              {m.data_ultimo_despacho
                ? `(${formatDate(m.data_ultimo_despacho)})`
                : ""}
              <span className="text-slate-400"> · {m.total_despachos} no total</span>
            </p>
          )}
        </div>
      )}
    </>
  );
}

/**
 * "Vigência" badge derived from the backend's ``dias_para_vencer``: red when
 * expired, amber when expiring within the window, green while far from expiry.
 */
function VencimentoBadge({ m }: { m: Monitoramento }) {
  if (m.data_vigencia == null || m.dias_para_vencer == null) return null;
  if (m.vencido) {
    return <Badge tone="red">Vencida há {Math.abs(m.dias_para_vencer)}d</Badge>;
  }
  if (m.vence_em_breve) {
    return <Badge tone="amber">Vence em {m.dias_para_vencer}d</Badge>;
  }
  return <Badge tone="green">Vigente</Badge>;
}

/** Small labelled field used inside the monitored marca card. */
function FieldLabel({ label, value }: { label: string; value: string }) {
  return (
    <p className="truncate">
      <span className="text-slate-400">{label}: </span>
      <span className="text-slate-600">{value}</span>
    </p>
  );
}

/**
 * Logotipo slot for a monitored marca. Logotipos are downloaded by the offline
 * worker (`python -m ingestion.logos`); the endpoint only serves what is stored
 * and a placeholder is shown while/if the image is absent.
 */
function MarcaMonitoradaLogo({ m }: { m: Monitoramento }) {
  const logo = useMarcaLogo(m.codigo_interno, m.tem_logo);

  // Revoke the object URL when it is replaced / on unmount.
  useEffect(() => {
    const url = logo.data;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [logo.data]);

  if (m.tem_logo && logo.data) {
    return (
      <div className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={logo.data}
          alt={`Logotipo de ${m.titulo ?? "marca"}`}
          className="h-full w-full object-contain"
        />
      </div>
    );
  }

  return (
    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 text-center text-[9px] font-semibold uppercase tracking-wide text-slate-400">
      Sem imagem
    </div>
  );
}


