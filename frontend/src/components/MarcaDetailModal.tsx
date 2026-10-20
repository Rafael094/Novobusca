"use client";

import { useEffect } from "react";

import { ApresentacaoBadge, SituacaoBadge } from "@/components/MarcaBadges";
import { useMarca, useMarcaLogo } from "@/lib/hooks";
import { classificacaoLabel, formatDate } from "@/lib/marcas";
import type { MarcaDetail } from "@/lib/types";

/**
 * Centered pop-up modal for the trademark (marca) detail (spec section 5).
 *
 * Replaces the old right-side slide-over drawer:
 *  - dimmed overlay that darkens the whole screen (focus on the modal);
 *  - wide, responsive box (max-w-5xl) to use the full width and avoid excessive
 *    scrolling;
 *  - closes on ESC and on clicking the dimmed overlay (outside the box);
 *  - fixed header "Detalhe da marca" with an X close button top-right;
 *  - a highlighted main block (elemento nominativo, status tags, natureza /
 *    apresentação, número do processo INPI) followed by the organised cards.
 *
 * Reused by the Marcas search page and the Monitoramento page so clicking "Ver"
 * opens the same modal instead of navigating away.
 */
export default function MarcaDetailModal({
  codigoInterno,
  onClose,
}: {
  codigoInterno: string | null;
  onClose: () => void;
}) {
  const detail = useMarca(codigoInterno);

  // Close on ESC + lock body scroll while the modal is open.
  useEffect(() => {
    if (!codigoInterno) return;
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
  }, [codigoInterno, onClose]);

  if (!codigoInterno) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label="Detalhe da marca"
    >
      {/* Dimmed overlay — click outside the box closes the modal */}
      <div
        className="absolute inset-0 bg-slate-900/60 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal box: wide and responsive */}
      <div
        className="relative z-10 flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border shadow-soft"
        style={{ background: "var(--bg-card)", borderColor: "var(--border-color)" }}
      >
        {/* Fixed header */}
        <div
          className="flex shrink-0 items-center justify-between border-b px-6 py-4"
          style={{ borderColor: "var(--border-color)" }}
        >
          <h2 className="text-lg font-bold" style={{ color: "var(--text-main)" }}>
            Detalhe da marca
          </h2>
          <button
            onClick={onClose}
            aria-label="Fechar"
            className="rounded-lg p-1.5 transition hover:text-brand-500"
            style={{ color: "var(--text-muted)" }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <path d="M18 6 6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Scrollable body */}
        <div className="scrollbar-thin flex-1 overflow-y-auto px-6 py-5">
          {detail.isLoading && (
            <p className="py-10 text-center" style={{ color: "var(--text-muted)" }}>Carregando…</p>
          )}
          {detail.error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {detail.error instanceof Error
                ? detail.error.message
                : "Erro ao carregar a marca."}
            </p>
          )}
          {detail.data && <MarcaDetailView marca={detail.data} />}
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

function SectionBlock({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section
      className="rounded-xl border p-4 shadow-card"
      style={{ background: "var(--bg-card)", borderColor: "var(--border-color)" }}
    >
      <h4
        className="mb-2 border-b pb-1 text-xs font-semibold uppercase tracking-wide"
        style={{ color: "var(--text-muted)", borderColor: "var(--border-color)" }}
      >
        {title}
      </h4>
      {children}
    </section>
  );
}

function NotImportedNote({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800 ring-1 ring-inset ring-amber-600/20">
      {children}
    </p>
  );
}

function MarcaImagem({ marca }: { marca: MarcaDetail }) {
  const embutida = marca.logo ?? null;
  const logo = useMarcaLogo(marca.codigo_interno, !embutida && marca.tem_logo);
  const src = embutida ?? logo.data;
  const isFigurativa = /figurativa|mista/i.test(
    marca.descricao_apresentacao ?? "",
  );

  useEffect(() => {
    const url = logo.data;
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [logo.data]);

  if (src) {
    return (
      <div className="flex h-28 w-28 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-200 bg-white">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={src}
          alt={`Logotipo de ${marca.elemento_nominativo ?? "marca"}`}
          loading="lazy"
          className="h-full w-full object-contain"
        />
      </div>
    );
  }

  return (
    <div className="flex h-28 w-28 shrink-0 flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 text-center">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">
        {isFigurativa ? "Mista/Figurativa" : marca.descricao_apresentacao || "Marca"}
      </span>
      <span className="mt-1 px-1 text-[10px] leading-tight text-slate-400">
        {marca.tem_logo ? "Carregando…" : "Imagem não disponível"}
      </span>
    </div>
  );
}

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

/**
 * Detail body — laid out to mirror the official INPI processo report, now inside
 * the centered modal. Cards are arranged in a responsive 2-column grid on wide
 * screens to use the extra width and reduce vertical scrolling.
 */
export function MarcaDetailView({ marca }: { marca: MarcaDetail }) {
  return (
    <div className="space-y-5 text-sm">
      {/* Main highlighted block */}
      <div className="flex flex-wrap items-start gap-4 rounded-xl bg-brand-50/60 p-4 ring-1 ring-inset ring-brand-600/10">
        <MarcaImagem marca={marca} />
        <div className="min-w-0 flex-1">
          <h3
            className="truncate text-2xl font-bold text-brand-700"
            title={marca.elemento_nominativo || undefined}
          >
            {marca.elemento_nominativo || "—"}
          </h3>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <SituacaoBadge
              codigo={marca.codigo_situacao}
              descricao={marca.descricao_situacao}
            />
            <ApresentacaoBadge descricao={marca.descricao_apresentacao} />
            {marca.descricao_natureza && (
              <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-slate-600 ring-1 ring-inset ring-slate-300">
                {marca.descricao_natureza}
              </span>
            )}
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Processo nº{" "}
            <span className="font-semibold text-slate-700">
              {marca.numero_inpi || "—"}
            </span>{" "}
            · Código interno {marca.codigo_interno}
          </p>
        </div>
      </div>

      {/* Cards grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
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
                    <li key={i} className="flex flex-wrap items-baseline gap-x-2 py-1.5">
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
                <li key={i} className="flex flex-wrap items-baseline gap-x-2 py-1.5">
                  <span className="font-medium text-slate-700">{r.nome || "—"}</span>
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

        <SectionBlock title={`Classes / classificações (${marca.classificacoes.length})`}>
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
      </div>

      {(marca.classificacoes_nice.length > 0 ||
        marca.classificacoes_nacionais.length > 0 ||
        marca.classificacoes_viena.length > 0) && (
        <SectionBlock title="Especificações de classificação">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {marca.classificacoes_nice.length > 0 && (
              <ClassList
                label="Nice"
                items={marca.classificacoes_nice.map((n) => ({
                  codigo: [n.edicao_nice, n.classe_nice].filter(Boolean).join(" · "),
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
                  codigo: [v.simbolo, v.revisao_viena].filter(Boolean).join(" · "),
                  detalhe: v.classificacao_viena,
                }))}
              />
            )}
          </div>
        </SectionBlock>
      )}

      <SectionBlock
        title={`Petições${marca.peticoes.length > 0 ? ` (${marca.peticoes.length})` : ""}`}
      >
        {marca.peticoes.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-600">
              <thead>
                <tr className="border-b border-slate-100 text-xs uppercase text-slate-400">
                  <th className="py-1 pr-3 font-medium">Protocolo</th>
                  <th className="py-1 pr-3 font-medium">Data</th>
                  <th className="py-1 pr-3 font-medium">Serviço</th>
                  <th className="py-1 pr-3 font-medium">Cliente</th>
                  <th className="py-1 pr-3 font-medium">Pagamento</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {marca.peticoes.map((p, i) => (
                  <tr key={`${p.protocolo}-${i}`}>
                    <td className="py-2 pr-3 font-medium text-slate-700">{p.protocolo}</td>
                    <td className="py-2 pr-3">{formatDate(p.data_protocolo)}</td>
                    <td className="py-2 pr-3">
                      {p.codigo_servico && (
                        <span className="mr-1 rounded bg-brand-50 px-1 text-xs font-medium text-brand-700">
                          {p.codigo_servico}
                        </span>
                      )}
                      {p.descricao_servico && (
                        <span className="text-xs text-slate-500">{p.descricao_servico}</span>
                      )}
                    </td>
                    <td className="py-2 pr-3">{p.cliente}</td>
                    <td className="py-2 pr-3 text-xs text-slate-500">
                      {p.pagamento_conciliado ? "Conciliado" : "—"}
                      {p.valor_pagamento != null
                        ? ` · ${p.valor_pagamento.toLocaleString("pt-BR", {
                            style: "currency",
                            currency: "BRL",
                          })}`
                        : ""}
                      {p.banco_nome ? ` · ${p.banco_nome}` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <NotImportedNote>
            {marca.peticoes_status === null ||
            marca.peticoes_status === undefined ||
            marca.peticoes_status === "PENDING"
              ? "Petições ainda não sincronizadas: a marca entrou na fila do worker do pePI (ingestion.peticoes) e aparecerá aqui após a próxima execução."
              : marca.peticoes_status === "ERROR"
                ? "Falha ao sincronizar as petições desta marca no pePI; será re-tentado."
                : "O pePI não retornou petições (documentos GRU) para este processo."}
          </NotImportedNote>
        )}
      </SectionBlock>

      <SectionBlock
        title={`Histórico de publicações (RPI) / despachos${
          marca.despachos.length > 0 ? ` (${marca.despachos.length})` : ""
        }`}
      >
        {marca.despachos.length === 0 ? (
          <NotImportedNote>
            Nenhum despacho publicado localmente para este processo (o dataset{" "}
            <span className="font-medium">MARCAS_DESPACHOS.csv</span> foi importado,
            mas não há registros para este código interno).
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
                  <p className="mt-0.5 text-xs text-slate-500">{d.descricao_despacho}</p>
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
