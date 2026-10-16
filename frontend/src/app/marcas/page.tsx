"use client";

import { useEffect, useState } from "react";

import AppShell from "@/components/AppShell";
import { ApresentacaoBadge, SituacaoBadge } from "@/components/MarcaBadges";
import { MonitoramentoToggle } from "@/components/ui";
import {
  useMarca,
  useMarcaLogo,
  useMarcas,
  useSetMarcaMonitoramento,
} from "@/lib/hooks";
import type { MatchMode } from "@/lib/hooks";
import { classificacaoLabel, formatDate } from "@/lib/marcas";
import type { Marca, MarcaDetail } from "@/lib/types";

const MATCH_MODE_LABELS: Record<MatchMode, string> = {
  exact: "Exata",
  prefix: "Começa com",
  contains: "Contém",
};

/**
 * Marcas page.
 *
 * IMPORTANT (spec section 4): the screen starts EMPTY. No records are loaded on
 * entry — only the search form is shown together with a message telling the user
 * to run a search. The "Monitoramento" column lets the user toggle monitoring
 * for individual marcas only (never globally).
 */
export default function MarcasPage() {
  const [q, setQ] = useState("");
  const [situacao, setSituacao] = useState("");
  const [matchMode, setMatchMode] = useState<MatchMode>("exact");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  // A search only happens after the user submits the form at least once.
  const [submitted, setSubmitted] = useState(false);

  const { data, isFetching, error } = useMarcas({
    q: submitted ? q || undefined : undefined,
    situacao: submitted ? situacao || undefined : undefined,
    match_mode: matchMode,
    page,
    page_size: 20,
    enabled: submitted,
  });
  const detail = useMarca(selected);
  const monitor = useSetMarcaMonitoramento();

  const totalPages = data
    ? Math.max(1, Math.ceil(data.pagination.total / data.pagination.page_size))
    : 1;

  return (
    <AppShell>
      <h1 className="mb-4 text-xl font-bold text-slate-800">Marcas</h1>

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
          placeholder="Buscar por marca…"
          className="min-w-[240px] flex-1 rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
        />
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <span className="whitespace-nowrap">Correspondência</span>
          <select
            value={matchMode}
            onChange={(e) => {
              setMatchMode(e.target.value as MatchMode);
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
          >
            <option value="exact">Exata</option>
            <option value="prefix">Começa com</option>
            <option value="contains">Contém</option>
          </select>
        </label>
        <input
          value={situacao}
          onChange={(e) => setSituacao(e.target.value)}
          placeholder="Situação (código)"
          className="w-40 rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
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
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-12 text-center shadow-sm">
          <p className="text-base font-medium text-slate-700">
            Realize uma pesquisa para visualizar marcas
          </p>
          <p className="mx-auto mt-1 max-w-xl text-sm text-slate-500">
            Nenhum registro é carregado automaticamente. Preencha o nome da marca,
            a situação ou o modo de correspondência acima e clique em{" "}
            <span className="font-medium text-slate-600">Buscar</span>. Você também
            pode ativar o monitoramento de marcas específicas pela coluna{" "}
            <span className="font-medium text-slate-600">Monitoramento</span>.
          </p>
        </div>
      )}

      {submitted && (
        <p className="mb-3 text-sm text-slate-500">
          Correspondência: <span className="font-medium text-slate-700">
            {MATCH_MODE_LABELS[matchMode]}
          </span>
          {data && ` · ${data.pagination.total} resultado(s)`}
        </p>
      )}

      {/* Desktop: table */}
      <div className="scrollbar-thin hidden overflow-x-auto rounded-2xl bg-white shadow-sm md:block">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-500">
            <tr>
              <th className="px-4 py-2 font-medium">Marca</th>
              <th className="px-4 py-2 font-medium">Situação</th>
              <th className="px-4 py-2 font-medium">Titular</th>
              <th className="px-4 py-2 font-medium">Nº INPI</th>
              <th className="px-4 py-2 font-medium">Data de depósito</th>
              <th className="px-4 py-2 font-medium">Apresentação</th>
              <th className="px-4 py-2 font-medium">Classe</th>
              <th className="px-4 py-2 font-medium">Monitoramento</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {data?.items.map((m) => (
              <tr
                key={m.id}
                onClick={() => setSelected(m.codigo_interno)}
                className="cursor-pointer align-top hover:bg-brand-50/50"
              >
                <td className="px-4 py-2 font-semibold text-brand-700">
                  <span className="inline-block max-w-[220px] truncate align-bottom">
                    {m.elemento_nominativo || "—"}
                  </span>
                </td>
                <td className="px-4 py-2">
                  <SituacaoBadge
                    codigo={m.codigo_situacao}
                    descricao={m.descricao_situacao}
                  />
                </td>
                <td className="px-4 py-2 text-slate-600">
                  {m.titular_principal ? (
                    <span>
                      <span className="inline-block max-w-[200px] truncate align-bottom">
                        {m.titular_principal}
                      </span>
                      {m.num_titulares > 1 && (
                        <span className="ml-1 rounded bg-slate-100 px-1 text-xs text-slate-500">
                          +{m.num_titulares - 1}
                        </span>
                      )}
                    </span>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-2 text-slate-600">{m.numero_inpi || "—"}</td>
                <td className="px-4 py-2 text-slate-600">
                  {formatDate(m.data_deposito)}
                </td>
                <td className="px-4 py-2">
                  <ApresentacaoBadge descricao={m.descricao_apresentacao} />
                </td>
                <td className="px-4 py-2 text-slate-600">
                  {m.classificacoes.length > 0
                    ? m.classificacoes.map(classificacaoLabel).join(", ")
                    : "—"}
                </td>
                {/* Selective monitoring — per-row, never global. */}
                <td className="px-4 py-2">
                  <MonitoramentoToggle
                    active={m.monitorada}
                    busy={
                      monitor.isPending &&
                      monitor.variables?.codigo === m.codigo_interno
                    }
                    onChange={(next) =>
                      monitor.mutate({ codigo: m.codigo_interno, active: next })
                    }
                  />
                </td>
              </tr>
            ))}
            {data && data.items.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-slate-400">
                  Nenhum resultado.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Mobile: cards with the same essential information */}
      <div className="space-y-3 md:hidden">
        {data?.items.map((m) => (
          <MarcaCard
            key={m.id}
            marca={m}
            onOpen={() => setSelected(m.codigo_interno)}
            onToggleMonitor={(next) =>
              monitor.mutate({ codigo: m.codigo_interno, active: next })
            }
            monitorBusy={
              monitor.isPending && monitor.variables?.codigo === m.codigo_interno
            }
          />
        ))}
        {data && data.items.length === 0 && (
          <p className="rounded-2xl bg-white px-4 py-6 text-center text-slate-400 shadow-sm">
            Nenhum resultado.
          </p>
        )}
      </div>

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
                Detalhe da marca
              </h2>
              <button
                onClick={() => setSelected(null)}
                className="text-slate-400 hover:text-slate-700"
              >
                ✕
              </button>
            </div>

            {detail.isLoading && <p className="text-slate-500">Carregando…</p>}
            {detail.data && <MarcaDetailView marca={detail.data} />}
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

/** Titled section block for the detail view (INPI-report style). */
function SectionBlock({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-slate-200 bg-white p-3">
      <h4 className="mb-2 border-b border-slate-100 pb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
        {title}
      </h4>
      {children}
    </section>
  );
}

/** Visually distinct placeholder for data that was never imported. */
function NotImportedNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 ring-1 ring-inset ring-amber-600/20">
      {children}
    </p>
  );
}

/**
 * Marca image (logotipo) slot. Renders the real downloaded image when the
 * backend reports one (`tem_logo`); otherwise a labelled placeholder derived
 * from the apresentação (see report §3/§17.8).
 */
function MarcaImagem({ marca }: { marca: MarcaDetail }) {
  const logo = useMarcaLogo(marca.codigo_interno, marca.tem_logo);
  const isFigurativa = /figurativa|mista/i.test(
    marca.descricao_apresentacao ?? "",
  );

  // Revoke the object URL when it is replaced / on unmount.
  useEffect(() => {
    const url = logo.data;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [logo.data]);

  if (marca.tem_logo && logo.data) {
    return (
      <div className="flex h-24 w-24 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-white">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={logo.data}
          alt={`Logotipo de ${marca.elemento_nominativo ?? "marca"}`}
          className="h-full w-full object-contain"
        />
      </div>
    );
  }

  return (
    <div className="flex h-24 w-24 shrink-0 flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 text-center">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {isFigurativa
          ? "Mista/Figurativa"
          : marca.descricao_apresentacao || "Marca"}
      </span>
      <span className="mt-1 px-1 text-[10px] leading-tight text-slate-400">
        {marca.tem_logo ? "Carregando…" : "Imagem não disponível"}
      </span>
    </div>
  );
}

/** A titled list of classification codes with their optional specifications. */
function ClassList({
  label,
  items,
}: {
  label: string;
  items: Array<{ codigo?: string; detalhe?: string }>;
}) {
  return (
    <div>
      <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
        {label}
      </p>
      <ul className="list-none space-y-1">
        {items.map((it, i) => (
          <li key={i} className="text-slate-600">
            {it.codigo && <span className="font-medium">{it.codigo}</span>}
            {it.detalhe && <p className="text-xs text-slate-500">{it.detalhe}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Mobile card mirroring the table's essential columns. */
function MarcaCard({
  marca,
  onOpen,
  onToggleMonitor,
  monitorBusy,
}: {
  marca: Marca;
  onOpen: () => void;
  onToggleMonitor?: (next: boolean) => void;
  monitorBusy?: boolean;
}) {
  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm">
      <button
        onClick={onOpen}
        className="block w-full text-left hover:opacity-90"
      >
        <div className="mb-2 flex items-start justify-between gap-2">
          <span className="text-base font-semibold text-brand-700">
            {marca.elemento_nominativo || "—"}
          </span>
          <SituacaoBadge
            codigo={marca.codigo_situacao}
            descricao={marca.descricao_situacao}
          />
        </div>
        <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-sm">
          <Field label="Titular" value={
            marca.titular_principal
              ? marca.num_titulares > 1
                ? `${marca.titular_principal} (+${marca.num_titulares - 1})`
                : marca.titular_principal
              : null
          } />
          <Field label="Nº INPI" value={marca.numero_inpi} />
          <Field label="Data de depósito" value={formatDate(marca.data_deposito)} />
          <div>
            <dt className="text-xs uppercase text-slate-400">Apresentação</dt>
            <dd className="text-slate-700">
              <ApresentacaoBadge descricao={marca.descricao_apresentacao} />
            </dd>
          </div>
          <Field
            label="Classe"
            value={
              marca.classificacoes.length > 0
                ? classificacaoLabel(marca.classificacoes[0]) +
                  (marca.classificacoes.length > 1
                    ? ` (+${marca.classificacoes.length - 1})`
                    : "")
                : null
            }
          />
        </dl>
      </button>
      <div className="mt-3 flex items-center justify-between border-t border-slate-100 pt-3">
        <span className="text-xs uppercase text-slate-400">Monitoramento</span>
        {onToggleMonitor && (
          <MonitoramentoToggle
            active={marca.monitorada}
            busy={monitorBusy}
            onChange={onToggleMonitor}
          />
        )}
      </div>
    </div>
  );
}

/**
 * Detail drawer body — laid out to mirror the official INPI processo report.
 *
 * Only real, locally-available data is rendered. Sections whose source data was
 * never imported (marca image, petições, histórico RPI/despachos) are shown as
 * explicit "not available" placeholders instead of simulated content — see
 * reports/RELATORIO_RESULTADO_INPI.md §3 and §10.
 */
function MarcaDetailView({ marca }: { marca: MarcaDetail }) {
  return (
    <div className="space-y-6 text-sm">
      {/* Cabeçalho: logotipo (quando houver) + identificação principal */}
      <div className="flex gap-4">
        <MarcaImagem marca={marca} />
        <div className="min-w-0 flex-1">
          <h3
            className="truncate text-xl font-semibold text-brand-700"
            title={marca.elemento_nominativo || undefined}
          >
            {marca.elemento_nominativo || "—"}
          </h3>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <SituacaoBadge
              codigo={marca.codigo_situacao}
              descricao={marca.descricao_situacao}
            />
            <ApresentacaoBadge descricao={marca.descricao_apresentacao} />
          </div>
          <p className="mt-1 text-xs text-slate-400">
            Processo nº {marca.numero_inpi || "—"} · Código interno{" "}
            {marca.codigo_interno}
          </p>
        </div>
      </div>

      {/* Identificação do processo */}
      <SectionBlock title="Identificação do processo">
        <dl className="grid grid-cols-2 gap-x-4 gap-y-3">
          <Field label="Nº INPI" value={marca.numero_inpi} />
          <Field label="Código interno" value={marca.codigo_interno} />
          <Field label="Data de depósito" value={formatDate(marca.data_deposito)} />
          <Field label="Publicação" value={formatDate(marca.data_publicacao)} />
          <Field label="Concessão" value={formatDate(marca.data_concessao)} />
          <Field label="Vigência" value={formatDate(marca.data_vigencia)} />
          <Field label="Apresentação" value={marca.descricao_apresentacao} />
          <Field label="Natureza" value={marca.descricao_natureza} />
          <Field label="Tradução" value={marca.traducao} />
          <Field label="Apostila" value={marca.apostila} />
        </dl>
      </SectionBlock>

      {/* Titulares / Depositantes */}
      <SectionBlock
        title={`Titulares / Depositantes${
          marca.num_titulares ? ` (${marca.num_titulares})` : ""
        }`}
      >
        {marca.titulares.length === 0 ? (
          <p className="text-xs italic text-slate-400">
            Sem titulares registrados.
          </p>
        ) : (
          <ul className="list-none divide-y divide-slate-100 text-slate-600">
            {marca.depositantes.length > 0
              ? marca.depositantes.map((d, i) => (
                  <li
                    key={i}
                    className="flex flex-wrap items-baseline gap-x-2 py-1.5"
                  >
                    <span className="font-medium text-slate-700">
                      {d.nome || "—"}
                    </span>
                    {d.cnpj_cpf_titular && (
                      <span className="text-xs text-slate-400">
                        CPF/CNPJ {d.cnpj_cpf_titular}
                      </span>
                    )}
                    {(d.pais || d.estado) && (
                      <span className="text-xs text-slate-400">
                        {[d.estado, d.pais].filter(Boolean).join(" / ")}
                      </span>
                    )}
                  </li>
                ))
              : marca.titulares.map((nome, i) => (
                  <li key={i} className="py-1.5 font-medium text-slate-700">
                    {nome}
                  </li>
                ))}
          </ul>
        )}
      </SectionBlock>

      {/* Representante legal / procurador */}
      <SectionBlock
        title={`Representante legal / procurador${
          marca.representantes_legais.length > 0
            ? ` (${marca.representantes_legais.length})`
            : ""
        }`}
      >
        {marca.representantes_legais.length === 0 ? (
          <p className="text-xs italic text-slate-400">
            Nenhum representante legal registrado para este processo.
          </p>
        ) : (
          <ul className="list-none divide-y divide-slate-100 text-slate-600">
            {marca.representantes_legais.map((r, i) => (
              <li
                key={i}
                className="flex flex-wrap items-baseline gap-x-2 py-1.5"
              >
                <span className="font-medium text-slate-700">
                  {r.nome || "—"}
                </span>
                {r.cnpj_cpf && (
                  <span className="text-xs text-slate-400">
                    CPF/CNPJ {r.cnpj_cpf}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </SectionBlock>

      {/* Classes / classificações (Nice, Nacional, Viena) com especificações */}
      <SectionBlock
        title={`Classes / classificações (${marca.classificacoes.length})`}
      >
        {marca.classificacoes.length === 0 ? (
          <p className="text-xs italic text-slate-400">
            Sem classificações registradas.
          </p>
        ) : (
          <ul className="list-none divide-y divide-slate-100 text-slate-600">
            {marca.classificacoes.map((c, i) => (
              <li key={i} className="py-1.5">
                <span className="mr-1 rounded bg-slate-100 px-1 text-xs uppercase text-slate-500">
                  {c.tipo}
                </span>
                <span className="font-medium">{c.codigo}</span>
                {c.descricao && (
                  <p className="mt-0.5 text-xs text-slate-500">{c.descricao}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </SectionBlock>

      {/* Detalhes adicionais de classificação importados à parte */}
      {(marca.classificacoes_nice.length > 0 ||
        marca.classificacoes_nacionais.length > 0 ||
        marca.classificacoes_viena.length > 0) && (
        <SectionBlock title="Especificações de classificação">
          <div className="space-y-3">
            {marca.classificacoes_nice.length > 0 && (
              <ClassList
                label="Nice"
                items={marca.classificacoes_nice.map((n) => ({
                  codigo: [n.edicao_nice, n.classe_nice]
                    .filter(Boolean)
                    .join(" · "),
                  detalhe: n.especificacao,
                }))}
              />
            )}
            {marca.classificacoes_nacionais.length > 0 && (
              <ClassList
                label="Nacional"
                items={marca.classificacoes_nacionais.map((n) => ({
                  codigo: n.classe,
                  detalhe: n.especificacao,
                }))}
              />
            )}
            {marca.classificacoes_viena.length > 0 && (
              <ClassList
                label="Viena"
                items={marca.classificacoes_viena.map((v) => ({
                  codigo: [v.simbolo, v.revisao_viena]
                    .filter(Boolean)
                    .join(" · "),
                  detalhe: v.classificacao_viena,
                }))}
              />
            )}
          </div>
        </SectionBlock>
      )}

      {/* Petições — dataset não importado (relatório §10) */}
      <SectionBlock title="Petições">
        <NotImportedNote>
          As petições do processo não estão disponíveis localmente: o dataset de
          petições de marcas não faz parte dos dados abertos importados.
        </NotImportedNote>
      </SectionBlock>

      {/* Histórico de publicações (RPI) / despachos — MARCAS_DESPACHOS.csv */}
      <SectionBlock
        title={`Histórico de publicações (RPI) / despachos${
          marca.despachos.length > 0 ? ` (${marca.despachos.length})` : ""
        }`}
      >
        {marca.despachos.length === 0 ? (
          <NotImportedNote>
            Nenhum despacho publicado localmente para este processo (o dataset{" "}
            <span className="font-medium">MARCAS_DESPACHOS.csv</span> foi
            importado, mas não há registros para este código interno).
          </NotImportedNote>
        ) : (
          <ol className="list-none divide-y divide-slate-100 text-slate-600">
            {marca.despachos.map((d, i) => (
              <li key={i} className="py-2">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  {d.data_rpi && (
                    <span className="font-medium text-slate-700">
                      {formatDate(d.data_rpi)}
                    </span>
                  )}
                  {d.numero_rpi && (
                    <span className="rounded bg-slate-100 px-1 text-xs text-slate-500">
                      RPI {d.numero_rpi}
                    </span>
                  )}
                  {d.codigo_despacho && (
                    <span className="rounded bg-brand-50 px-1 text-xs font-medium text-brand-700">
                      {d.codigo_despacho}
                    </span>
                  )}
                </div>
                {d.descricao_despacho && (
                  <p className="mt-0.5 text-xs text-slate-500">
                    {d.descricao_despacho}
                  </p>
                )}
                {d.complemento_despacho && (
                  <p className="mt-0.5 text-xs italic text-slate-400">
                    {d.complemento_despacho}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </SectionBlock>
    </div>
  );
}


