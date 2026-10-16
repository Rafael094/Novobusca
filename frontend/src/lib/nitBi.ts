/**
 * NIT BI — pretty labels for the real indicator keys.
 *
 * A saved report stores the *keys* returned by ``GET /api/nit/bi/metrics``
 * (which are the field names of ``InstitutionalIndicators``). Those keys are
 * the contract with the backend and must NEVER be translated on the wire — the
 * backend whitelists them and the CSV export writes them verbatim.
 *
 * This module only maps a key to a human, pt-BR label for display, so the
 * screen speaks Portuguese while the payload stays stable. The mapping lives in
 * one place to avoid divergent copies across the BI and indicators screens.
 */

/** key → pt-BR label. Keys absent from the map fall back to a humanised key. */
export const METRIC_LABELS: Record<string, string> = {
  disclosure_total: "Comunicações de invenção",
  disclosures_by_status: "Comunicações por situação",
  disclosures_by_area: "Comunicações por área",
  average_triage_days: "Tempo médio de triagem (dias)",
  pending_evaluations: "Avaliações pendentes",
  assets_total: "Ativos institucionais",
  assets_by_stage: "Ativos por estágio",
  offers_published: "Ofertas publicadas",
  negotiations_in_progress: "Negociações em curso",
  contracts_active: "Contratos vigentes",
  obligations_due_soon: "Obrigações a vencer",
  projects_total: "Projetos de P&D",
  projects_active: "Projetos ativos",
  startups_total: "Startups",
  startups_incubated: "Startups incubadas",
  period_from: "Início do período",
  period_to: "Fim do período",
};

/**
 * Human, pt-BR label for a metric key.
 *
 * Falls back to the raw key when it is unknown (e.g. a metric added to the
 * backend before this map was updated) — never hides the metric.
 */
export function metricLabel(key: string): string {
  return METRIC_LABELS[key] ?? key;
}
