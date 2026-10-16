"use client";

/**
 * Funnel — the commercial funnel widget of the Overview.
 *
 * Renders exactly the stages it receives (real data from the backend). Bars are
 * proportional to the largest stage so the shape is meaningful even when the
 * counts are small; a stage with zero opportunities shows a muted bar instead of
 * disappearing, so the funnel always reads as a funnel.
 */

import Link from "next/link";

import type { FunnelStage } from "@/lib/types";

const BAR_COLORS = [
  "bg-brand-500",
  "bg-brand-500",
  "bg-brand-600",
  "bg-amber-500",
  "bg-amber-500",
  "bg-emerald-500",
  "bg-red-400",
];

function formatValue(value: string | null): string | null {
  if (!value) return null;
  const numeric = Number(value);
  if (Number.isNaN(numeric)) return null;
  return numeric.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

export function Funnel({
  stages,
  hrefFor,
}: {
  stages: FunnelStage[];
  /** Target screen for a stage click (e.g. filtering opportunities). */
  hrefFor?: (stage: FunnelStage) => string;
}) {
  const max = Math.max(1, ...stages.map((s) => s.count));
  const total = stages.reduce((acc, s) => acc + s.count, 0);

  return (
    <div className="space-y-3">
      {total === 0 && (
        <p className="rounded-lg bg-slate-50 px-4 py-6 text-center text-sm text-slate-500">
          Nenhuma oportunidade cadastrada ainda. Cadastre um lead para começar a
          acompanhar o funil comercial.
        </p>
      )}

      {total > 0 &&
        stages.map((stage, index) => {
          const pct = Math.round((stage.count / max) * 100);
          const value = formatValue(stage.value);
          const inner = (
            <>
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm font-medium text-slate-700">
                  {stage.label}
                </span>
                <span className="flex items-baseline gap-2">
                  <span className="text-sm font-semibold text-slate-800">
                    {stage.count.toLocaleString("pt-BR")}
                  </span>
                  {value && (
                    <span className="text-xs text-slate-400">{value}</span>
                  )}
                </span>
              </div>
              <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                <div
                  className={`h-full rounded-full transition-all ${BAR_COLORS[index % BAR_COLORS.length]}`}
                  style={{ width: `${stage.count === 0 ? 2 : pct}%` }}
                />
              </div>
            </>
          );

          const href = hrefFor?.(stage);
          return href ? (
            <Link
              key={stage.stage}
              href={href}
              className="-mx-2 block rounded-lg px-2 py-1.5 transition hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
            >
              {inner}
            </Link>
          ) : (
            <div key={stage.stage} className="px-0 py-1.5">
              {inner}
            </div>
          );
        })}
    </div>
  );
}

export default Funnel;
