"use client";

import { useState } from "react";

import AppShell from "@/components/AppShell";
import { MonitoramentoToggle } from "@/components/ui";
import {
  usePatente,
  usePatentes,
  useSetPatenteMonitoramento,
} from "@/lib/hooks";

/**
 * Patentes page.
 *
 * IMPORTANT (spec section 4): the screen starts EMPTY — no records load on
 * entry; only the search filters plus a guidance message. The "Monitoramento"
 * column toggles monitoring for individual patentes only (never globally).
 */
export default function PatentesPage() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const { data, isFetching, error } = usePatentes({
    q: submitted ? q || undefined : undefined,
    page,
    page_size: 20,
    enabled: submitted,
  });
  const detail = usePatente(selected);
  const monitor = useSetPatenteMonitoramento();

  const totalPages = data
    ? Math.max(1, Math.ceil(data.pagination.total / data.pagination.page_size))
    : 1;

  return (
    <AppShell>
      <h1 className="mb-4 text-xl font-bold text-slate-800">Patentes</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          setSubmitted(true);
        }}
        className="mb-4 flex flex-wrap gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Buscar por título, resumo, número INPI/PCT…"
          className="min-w-[280px] flex-1 rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
        />
        <button
          type="submit"
          className="rounded-lg bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700"
        >
          Buscar
        </button>
      </form>

      {error && (
        <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error instanceof Error ? error.message : "Erro na busca."}
        </p>
      )}

      {/* Initial guidance: nothing is loaded until the user searches. */}
      {!submitted && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center shadow-card">
          <p className="text-base font-medium text-slate-700">
            Realize uma pesquisa para visualizar patentes
          </p>
          <p className="mx-auto mt-1 max-w-xl text-sm text-slate-500">
            Nenhum registro é carregado automaticamente. Informe o título, o resumo
            ou o número INPI/PCT acima e clique em{" "}
            <span className="font-medium text-slate-600">Buscar</span>. Você também
            pode ativar o monitoramento de patentes específicas pela coluna{" "}
            <span className="font-medium text-slate-600">Monitoramento</span>.
          </p>
        </div>
      )}

      {submitted && (
      <div className="overflow-hidden rounded-xl border border-gray-100 bg-white shadow-card">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Título</th>
              <th className="px-4 py-2 font-medium">Nº INPI</th>
              <th className="px-4 py-2 font-medium">Depósito</th>
              <th className="px-4 py-2 font-medium">PCT</th>
              <th className="px-4 py-2 font-medium">Monitoramento</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data?.items.map((p) => (
              <tr
                key={p.id}
                onClick={() => setSelected(p.codigo_interno)}
                className="cursor-pointer hover:bg-brand-50/50"
              >
                <td className="max-w-md truncate px-4 py-2 font-medium text-slate-700">
                  {p.titulo || "—"}
                </td>
                <td className="px-4 py-2 text-slate-600">{p.numero_inpi || "—"}</td>
                <td className="px-4 py-2 text-slate-600">{p.data_deposito || "—"}</td>
                <td className="px-4 py-2 text-slate-600">{p.numero_pct || "—"}</td>
                {/* Selective monitoring — per-row, never global. */}
                <td className="px-4 py-2">
                  <MonitoramentoToggle
                    active={p.monitorada}
                    busy={
                      monitor.isPending &&
                      monitor.variables?.codigo === p.codigo_interno
                    }
                    onChange={(next) =>
                      monitor.mutate({ codigo: p.codigo_interno, active: next })
                    }
                  />
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-400">
                  Nenhum resultado.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      )}

      {submitted && (
      <div className="mt-3 flex items-center justify-between text-sm text-slate-500">
        <span>
          {data ? `${data.pagination.total.toLocaleString("pt-BR")} resultados` : ""}
          {isFetching ? " · carregando…" : ""}
        </span>
        <div className="flex items-center gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="rounded-lg border border-slate-300 px-3 py-1 disabled:opacity-40"
          >
            Anterior
          </button>
          <span>
            {page} / {totalPages}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-lg border border-slate-300 px-3 py-1 disabled:opacity-40"
          >
            Próxima
          </button>
        </div>
      </div>
      )}

      {selected && (
        <div className="fixed inset-0 z-40 flex justify-end bg-black/30">
          <div className="h-full w-full max-w-lg overflow-y-auto bg-white p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-slate-800">
                Detalhe da patente
              </h2>
              <button
                onClick={() => setSelected(null)}
                className="text-slate-400 hover:text-slate-700"
              >
                ✕
              </button>
            </div>

            {detail.isLoading && <p className="text-slate-500">Carregando…</p>}
            {detail.data && (
              <div className="space-y-4 text-sm">
                <h3 className="font-semibold text-brand-700">
                  {detail.data.titulo || "—"}
                </h3>
                <dl className="grid grid-cols-2 gap-3">
                  <Field label="Nº INPI" value={detail.data.numero_inpi} />
                  <Field label="Código interno" value={detail.data.codigo_interno} />
                  <Field label="Depósito" value={detail.data.data_deposito} />
                  <Field label="Publicação" value={detail.data.data_publicacao} />
                </dl>

                {detail.data.resumo && (
                  <div>
                    <h4 className="mb-1 font-semibold text-slate-700">Resumo</h4>
                    <p className="whitespace-pre-line text-slate-600">
                      {detail.data.resumo}
                    </p>
                  </div>
                )}

                <Section title="Depositantes" items={detail.data.depositantes} />
                <Section title="Inventores" items={detail.data.inventores} />
                <Section
                  title="Classificação IPC"
                  items={detail.data.classificacoes_ipc}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </AppShell>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs uppercase text-slate-400">{label}</dt>
      <dd className="text-slate-700">{value || "—"}</dd>
    </div>
  );
}

function Section({
  title,
  items,
}: {
  title: string;
  items: Array<Record<string, unknown>>;
}) {
  if (!items || items.length === 0) return null;
  return (
    <div>
      <h4 className="mb-1 font-semibold text-slate-700">{title}</h4>
      <ul className="divide-y divide-slate-100 text-slate-600">
        {items.map((row, i) => (
          <li key={i} className="py-1">
            {Object.values(row)
              .filter((v) => v != null && v !== "")
              .join(" · ")}
          </li>
        ))}
      </ul>
    </div>
  );
}

