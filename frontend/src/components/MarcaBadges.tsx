"use client";

/** Small, real-data badges for marcas: situação and apresentação (tipo). */

import {
  SITUACAO_TONE_CLASSES,
  apresentacaoInfo,
  situacaoTone,
} from "@/lib/marcas";

export function SituacaoBadge({
  codigo,
  descricao,
}: {
  codigo: string | null;
  descricao: string | null;
}) {
  const text = descricao?.trim() || codigo?.trim() || "—";
  const tone = situacaoTone(codigo);
  return (
    <span
      className={`inline-flex max-w-full items-center truncate rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${SITUACAO_TONE_CLASSES[tone]}`}
      title={text}
    >
      {text}
    </span>
  );
}

export function ApresentacaoBadge({ descricao }: { descricao: string | null }) {
  const { short } = apresentacaoInfo(descricao);
  if (!short || short === "—") return <span className="text-slate-400">—</span>;
  return (
    <span className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
      {short}
    </span>
  );
}
