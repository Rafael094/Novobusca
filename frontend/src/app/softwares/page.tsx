"use client";

import { useEffect, useState } from "react";

import AppShell from "@/components/AppShell";
import { MonitoramentoToggle } from "@/components/ui";
import {
  useSetSoftwareMonitoramento,
  useSoftware,
  useSoftwares,
} from "@/lib/hooks";
import { formatDate } from "@/lib/marcas";

/**
 * Programas de Computador (Software) — busca + modal de detalhe (espelha
 * Marcas/Patentes). Começa vazia; monitoramento seletivo por item.
 */
export default function SoftwaresPage() {
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const { data, isFetching, error } = useSoftwares({
    q: submitted ? q || undefined : undefined,
    page,
    page_size: 20,
    enabled: submitted,
  });
  const monitor = useSetSoftwareMonitoramento();

  const totalPages = data
    ? Math.max(1, Math.ceil(data.pagination.total / data.pagination.page_size))
    : 1;

  return (
    <AppShell>
      <h1 className="mb-4 text-xl font-bold" style={{ color: "var(--text-main)" }}>
        Programas de Computador
      </h1>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          setPage(1);
          setSubmitted(true);
        }}
        className="mb-4 flex flex-wrap gap-2"
      >
        <div className="search-box flex-1">
          <svg className="search-box__icon" viewBox="0 0 20 20" aria-hidden="true">
            <path d="M8 2a6 6 0 104.47 10.03l4.25 4.24 1.41-1.41-4.24-4.25A6 6 0 008 2zm0 2a4 4 0 110 8 4 4 0 010-8z" />
          </svg>
          <input
            className="search-box__input"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Buscar por título do programa de computador…"
          />
        </div>
        <button type="submit" className="btn-primary">
          Buscar
        </button>
      </form>

      {error && (
        <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
          {error instanceof Error ? error.message : "Erro na busca."}
        </p>
      )}

      {!submitted && (
        <div
          className="rounded-xl border border-dashed px-6 py-12 text-center shadow-card"
          style={{ background: "var(--bg-card)", borderColor: "var(--border-strong)" }}
        >
          <p className="text-base font-medium" style={{ color: "var(--text-main)" }}>
            Realize uma pesquisa para visualizar programas de computador
          </p>
          <p className="mx-auto mt-1 max-w-xl text-sm" style={{ color: "var(--text-muted)" }}>
            Nenhum registro é carregado automaticamente. Informe o título e clique em{" "}
            <span className="font-medium">Buscar</span>.
          </p>
        </div>
      )}

      {submitted && (
        <div
          className="scrollbar-thin overflow-x-auto rounded-xl border shadow-card"
          style={{ background: "var(--bg-card)", borderColor: "var(--border-color)" }}
        >
          <table className="min-w-full text-sm">
            <thead style={{ background: "var(--bg-subtle)", color: "var(--text-muted)" }}>
              <tr>
                <th className="px-4 py-2 text-left font-medium">Título</th>
                <th className="px-4 py-2 text-left font-medium">Nº INPI</th>
                <th className="px-4 py-2 text-left font-medium">Titular</th>
                <th className="px-4 py-2 text-left font-medium">Linguagens</th>
                <th className="px-4 py-2 text-left font-medium">Situação</th>
                <th className="px-4 py-2 text-left font-medium">Monitoramento</th>
              </tr>
            </thead>
            <tbody className="divide-y" style={{ borderColor: "var(--border-color)" }}>
              {data?.items.map((s) => (
                <tr
                  key={s.id}
                  onClick={() => setSelected(s.codigo_interno)}
                  className="cursor-pointer hover:bg-brand-50/50"
                >
                  <td className="max-w-md truncate px-4 py-2 font-medium" style={{ color: "var(--text-main)" }}>
                    {s.titulo || "—"}
                  </td>
                  <td className="px-4 py-2" style={{ color: "var(--text-muted)" }}>{s.numero_inpi || "—"}</td>
                  <td className="max-w-[200px] truncate px-4 py-2" style={{ color: "var(--text-muted)" }}>
                    {s.titular_principal || "—"}
                    {s.num_titulares > 1 && (
                      <span className="ml-1 text-xs">+{s.num_titulares - 1}</span>
                    )}
                  </td>
                  <td className="max-w-[160px] truncate px-4 py-2" style={{ color: "var(--text-muted)" }}>
                    {s.linguagens.length > 0 ? s.linguagens.join(", ") : "—"}
                  </td>
                  <td className="px-4 py-2" style={{ color: "var(--text-muted)" }}>{s.descricao_situacao || "—"}</td>
                  <td className="px-4 py-2">
                    <MonitoramentoToggle
                      active={s.monitorada}
                      busy={monitor.isPending && monitor.variables?.codigo === s.codigo_interno}
                      onChange={(next) => monitor.mutate({ codigo: s.codigo_interno, active: next })}
                    />
                  </td>
                </tr>
              ))}
              {data && data.items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-4 py-6 text-center" style={{ color: "var(--text-faint)" }}>
                    Nenhum resultado.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {submitted && (
        <div className="mt-3 flex items-center justify-between text-sm" style={{ color: "var(--text-muted)" }}>
          <span>
            {data ? `${data.pagination.total.toLocaleString("pt-BR")} resultados` : ""}
            {isFetching ? " · carregando…" : ""}
          </span>
          <div className="flex items-center gap-2">
            <button disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} className="btn-ghost h-9 px-3 disabled:opacity-40">
              Anterior
            </button>
            <span>{page} / {totalPages}</span>
            <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} className="btn-ghost h-9 px-3 disabled:opacity-40">
              Próxima
            </button>
          </div>
        </div>
      )}

      <SoftwareDetailModal codigo={selected} onClose={() => setSelected(null)} />
    </AppShell>
  );
}

function SoftwareDetailModal({
  codigo,
  onClose,
}: {
  codigo: string | null;
  onClose: () => void;
}) {
  const detail = useSoftware(codigo);

  useEffect(() => {
    if (!codigo) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [codigo, onClose]);

  if (!codigo) return null;
  const s = detail.data;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6" role="dialog" aria-modal="true">
      <div className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm" onClick={onClose} />
      <div
        className="relative z-10 flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border shadow-soft"
        style={{ background: "var(--bg-card)", borderColor: "var(--border-color)" }}
      >
        <div className="flex shrink-0 items-center justify-between border-b px-6 py-4" style={{ borderColor: "var(--border-color)" }}>
          <h2 className="text-lg font-bold" style={{ color: "var(--text-main)" }}>
            Detalhe do programa de computador
          </h2>
          <button onClick={onClose} aria-label="Fechar" className="rounded-lg p-1.5 hover:text-brand-500" style={{ color: "var(--text-muted)" }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="scrollbar-thin flex-1 overflow-y-auto px-6 py-5">
          {detail.isLoading && <p className="py-10 text-center" style={{ color: "var(--text-muted)" }}>Carregando…</p>}
          {s && (
            <div className="space-y-5 text-sm">
              <div className="rounded-xl bg-brand-50/60 p-4">
                <h3 className="text-xl font-bold text-brand-700">{s.titulo || "—"}</h3>
                <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>
                  Processo nº <span className="font-semibold">{s.numero_inpi || "—"}</span> · Código interno {s.codigo_interno}
                  {s.descricao_situacao ? ` · ${s.descricao_situacao}` : ""}
                </p>
              </div>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <Card title="Identificação do processo">
                  <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
                    <Field label="Nº INPI" value={s.numero_inpi} />
                    <Field label="Código interno" value={s.codigo_interno} />
                    <Field label="Depósito" value={formatDate(s.data_deposito)} />
                    <Field label="Criação" value={formatDate(s.data_criacao)} />
                    <Field label="Publicação" value={formatDate(s.data_publicacao)} />
                    <Field label="Concessão" value={formatDate(s.data_concessao)} />
                    <Field label="Linguagens" value={s.linguagens.join(", ") || null} />
                  </dl>
                </Card>
                <Card title={`Titulares (${s.num_titulares})`}>
                  {s.titulares.length === 0 ? (
                    <p className="text-xs italic" style={{ color: "var(--text-faint)" }}>Sem titulares registrados.</p>
                  ) : (
                    <ul className="divide-y text-slate-600" style={{ borderColor: "var(--border-color)" }}>
                      {s.titulares.map((n, i) => (
                        <li key={i} className="py-1.5 font-medium" style={{ color: "var(--text-main)" }}>{n}</li>
                      ))}
                    </ul>
                  )}
                </Card>
                <Section title="Autores" items={s.autores} />
                <Section title="Tipo / campo de aplicação" items={s.tipos} />
                <Section title="Campos" items={s.campos} />
              </div>
              <Card title={`Histórico de publicações (RPI) / despachos (${s.despachos.length})`}>
                {s.despachos.length === 0 ? (
                  <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 ring-1 ring-inset ring-amber-600/20">
                    Nenhum despacho localmente para este processo.
                  </p>
                ) : (
                  <ol className="divide-y text-slate-600" style={{ borderColor: "var(--border-color)" }}>
                    {s.despachos.map((row, i) => (
                      <li key={i} className="py-1.5">
                        {Object.values(row).filter((v) => v != null && v !== "").join(" · ")}
                      </li>
                    ))}
                  </ol>
                )}
              </Card>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-xs uppercase" style={{ color: "var(--text-faint)" }}>{label}</dt>
      <dd style={{ color: "var(--text-main)" }}>{value || "—"}</dd>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border p-4 shadow-card" style={{ background: "var(--bg-card)", borderColor: "var(--border-color)" }}>
      <h4 className="mb-2 border-b pb-1 text-xs font-semibold uppercase tracking-wide" style={{ color: "var(--text-muted)", borderColor: "var(--border-color)" }}>
        {title}
      </h4>
      {children}
    </section>
  );
}

function Section({ title, items }: { title: string; items: Array<Record<string, unknown>> }) {
  if (!items || items.length === 0) return null;
  return (
    <Card title={title}>
      <ul className="divide-y text-slate-600" style={{ borderColor: "var(--border-color)" }}>
        {items.map((row, i) => (
          <li key={i} className="py-1" style={{ color: "var(--text-muted)" }}>
            {Object.values(row).filter((v) => v != null && v !== "").join(" · ")}
          </li>
        ))}
      </ul>
    </Card>
  );
}
