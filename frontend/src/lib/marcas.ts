/** Presentation helpers for marcas (badges, labels, classification formatting). */

import type { MarcaClassificacao } from "./types";

/**
 * Situation badge styling, keyed by the raw INPI ``codigo_situacao`` when
 * available. The original ``descricao_situacao`` text is ALWAYS shown verbatim;
 * colour is only an aid — never a substitute for the real value.
 */
export type SituacaoTone = "success" | "danger" | "warning" | "neutral";

export function situacaoTone(codigo: string | null | undefined): SituacaoTone {
  const code = (codigo ?? "").trim();
  // Common INPI situação codes: 100-series ~ granted/active, 8xx ~ extinct,
  // 2xx/3xx ~ under examination/oposition. These are heuristic colour hints only.
  if (code.startsWith("1")) return "success";
  if (code.startsWith("8") || code.startsWith("9")) return "danger";
  if (code.startsWith("2") || code.startsWith("3")) return "warning";
  return "neutral";
}

export const SITUACAO_TONE_CLASSES: Record<SituacaoTone, string> = {
  success: "bg-emerald-50 text-emerald-700 ring-emerald-600/20",
  danger: "bg-red-50 text-red-700 ring-red-600/20",
  warning: "bg-amber-50 text-amber-800 ring-amber-600/20",
  neutral: "bg-slate-100 text-slate-600 ring-slate-500/20",
};

/** Short tag + tone for the apresentação (tipo) of the marca. */
export type ApresentacaoInfo = { short: string; tone: SituacaoTone };

export function apresentacaoInfo(
  descricao: string | null | undefined,
): ApresentacaoInfo {
  const d = (descricao ?? "").toLowerCase();
  if (d.includes("nominativa")) return { short: "Nominativa", tone: "neutral" };
  if (d.includes("mista")) return { short: "Mista", tone: "neutral" };
  if (d.includes("figurativa")) return { short: "Figurativa", tone: "neutral" };
  if (d.includes("tridimensional")) return { short: "Tridimensional", tone: "neutral" };
  if (d.includes("posi")) return { short: "Marca de posição", tone: "neutral" };
  return { short: descricao?.trim() || "—", tone: "neutral" };
}

/** Human label for a classification ``tipo``. */
export function classificacaoTipoLabel(tipo: string): string {
  switch (tipo) {
    case "nice":
      return "Nice";
    case "nacional":
      return "Nacional";
    case "viena":
      return "Viena";
    default:
      return tipo;
  }
}

/**
 * Compact display: only the class code/number (e.g. "NCL(12) 25" or "33").
 * The full specification text is intentionally omitted from the list/table —
 * it is long and only relevant in the detail view when explicitly needed.
 */
export function classificacaoLabel(c: MarcaClassificacao): string {
  return c.codigo;
}

/** Format an ISO date (yyyy-mm-dd) as dd/mm/yyyy; passthrough when unparseable. */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!m) return value;
  return `${m[3]}/${m[2]}/${m[1]}`;
}
