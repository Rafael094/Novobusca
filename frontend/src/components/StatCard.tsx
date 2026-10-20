"use client";

/**
 * StatCard — a single KPI tile of the business dashboard.
 *
 * Design rules (kept deliberately strict so every module looks the same):
 * * a neutral title, a large value and — only when it can be computed from real
 *   data — a small variation/detail line;
 * * an optional link turns the whole card into navigation, never a decorative
 *   button;
 * * tone drives the icon chip colour, not the value colour, so a wall of cards
 *   stays readable.
 */

import Link from "next/link";
import type { ReactNode } from "react";

export type StatTone = "brand" | "green" | "amber" | "red" | "slate" | "violet";

const TONE_CHIP: Record<StatTone, string> = {
  brand: "bg-brand-50 text-brand-700",
  green: "bg-emerald-50 text-emerald-600",
  amber: "bg-amber-50 text-amber-600",
  red: "bg-red-50 text-red-600",
  slate: "bg-slate-100 text-slate-600",
  violet: "bg-violet-50 text-violet-600",
};

export function StatCard({
  label,
  value,
  detail,
  period,
  tone = "brand",
  icon,
  href,
  hint,
}: {
  label: string;
  value: number | string;
  /** Secondary line — usually a comparison. Omit it when uncomputable. */
  detail?: string | null;
  /** Reference period shown under the value (e.g. "últimos 12 meses"). */
  period?: string;
  tone?: StatTone;
  icon?: ReactNode;
  /** When present the card becomes a link to the related screen. */
  href?: string;
  hint?: string;
}) {
  const displayed =
    typeof value === "number" ? value.toLocaleString("pt-BR") : value;

  const body = (
    <>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium" style={{ color: "var(--text-muted)" }}>{label}</p>
        {icon && (
          <span
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-base ${TONE_CHIP[tone]}`}
            aria-hidden="true"
          >
            {icon}
          </span>
        )}
      </div>
      <p className="mt-3 text-3xl font-bold leading-none" style={{ color: "var(--text-main)" }}>
        {displayed}
      </p>
      {detail && <p className="mt-2 text-xs" style={{ color: "var(--text-muted)" }}>{detail}</p>}
      {period && !detail && <p className="mt-2 text-xs" style={{ color: "var(--text-faint)" }}>{period}</p>}
      {hint && <p className="mt-2 text-xs" style={{ color: "var(--text-faint)" }}>{hint}</p>}
    </>
  );

  const base = "block rounded-xl border p-5 shadow-card transition";
  const baseStyle: React.CSSProperties = {
    background: "var(--bg-card)",
    borderColor: "var(--border-color)",
  };

  if (href) {
    return (
      <Link
        href={href}
        style={baseStyle}
        className={`${base} hover:border-brand-200 hover:shadow-soft focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500`}
        title={hint}
      >
        {body}
      </Link>
    );
  }
  return <div className={base} style={baseStyle}>{body}</div>;
}

export default StatCard;
