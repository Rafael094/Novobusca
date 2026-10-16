"use client";

/** React Query hooks wrapping the typed API client. */

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiFetch, fetchBlobUrl } from "./api";
import { API_BASE_URL, ApiError, tokens } from "./api";
import type {
  AdminGroup,
  AdminModule,
  AdminResource,
  AdminRole,
  AdminTenant,
  AdminUser,
  AdminUserPolicy,
  AnalysisReport,
  AnalysisStatus,
  BusinessDashboard,
  Company,
  CrmActivity,
  Customer,
  ChatResponse,
  ChatStatus,
  DashboardSummary,
  Dataset,
  EffectiveAccess,
  ImportRecord,
  Marca,
  MarcaDetail,
  Monitoramento,
  NitAsset,
  NitAssetDetail,
  NitAgendaItem,
  NitCommittee,
  NitCommitteeDetail,
  NitCommitteeMember,
  NitDashboard,
  NitDeadlineAlert,
  NitDecision,
  NitDisclosure,
  NitDisclosureDetail,
  NitDocument,
  NitDocumentAcl,
  NitEvaluation,
  NitInteraction,
  NitInterest,
  NitMeeting,
  NitNegotiation,
  NitNegotiationDetail,
  NitObligation,
  NitObligationAlert,
  NitOffer,
  NitPortfolioView,
  NitRoyalty,
  NitRoyaltySummary,
  NitContract,
  NitContractDetail,
  NitIncubationStage,
  NitIndicators,
  NitFormictReport,
  NitNotification,
  NitNotificationList,
  NitNotificationPreference,
  NitEmailMessage,
  NitPortalAccess,
  NitPortalRequest,
  NitPortalRequestDetail,
  NitSavedReport,
  NitIntegrationEndpoint,
  NitIntegrationDelivery,
  NitParticipation,
  NitParticipationDetail,
  NitProgram,
  NitProject,
  NitProjectDetail,
  NitProjectFunder,
  NitProjectMember,
  NitProjectMilestone,
  NitStartup,
  NitStartupMember,
  NitTrl,
  NitVoteTally,
  NitWorkflowStatus,
  Opportunity,
  Paginated,
  PaginatedNit,
  Patente,
  PatenteDetail,
  Person,
  PolicyDecision,
  Proposal,
  SyncStatus,
  Unity,
} from "./types";

function toQuery(params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : "";
}

// --- Dashboard --------------------------------------------------------------
export function useDashboard() {
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiFetch<DashboardSummary>("/api/dashboard/summary"),
  });
}

// --- Marcas -----------------------------------------------------------------
export type MatchMode = "exact" | "prefix" | "contains";

export type MarcaFilters = {
  q?: string;
  numero_inpi?: string;
  situacao?: string;
  data_deposito_from?: string;
  data_deposito_to?: string;
  match_mode?: MatchMode;
  page?: number;
  page_size?: number;
  /**
   * When false the query is not executed — used by the Marcas screen so that no
   * records load until the user actually submits a search (spec section 4).
   */
  enabled?: boolean;
};

export function useMarcas(filters: MarcaFilters) {
  const { enabled = true, ...params } = filters;
  return useQuery({
    queryKey: ["marcas", params],
    queryFn: () => apiFetch<Paginated<Marca>>(`/api/marcas/search${toQuery(params)}`),
    placeholderData: (prev) => prev,
    enabled,
  });
}

export function useMarca(codigo: string | null) {
  return useQuery({
    queryKey: ["marca", codigo],
    queryFn: () => apiFetch<MarcaDetail>(`/api/marcas/${codigo}`),
    enabled: !!codigo,
  });
}

/**
 * Selective monitoring of a single marca (section 4). The mutation only touches
 * the specific record — monitoring is never global or automatic.
 */
export function useSetMarcaMonitoramento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ codigo, active }: { codigo: string; active: boolean }) =>
      apiFetch<Monitoramento>(`/api/marcas/${codigo}/monitoramento`, {
        method: "POST",
        body: JSON.stringify({ active }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["marcas"] });
      qc.invalidateQueries({ queryKey: ["marcas-monitoramento"] });
      qc.invalidateQueries({ queryKey: ["marca"] });
    },
  });
}

export function useMarcasMonitoramento(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["marcas-monitoramento", page, pageSize],
    queryFn: () =>
      apiFetch<Paginated<Monitoramento>>(
        `/api/marcas/monitoramento${toQuery({ page, page_size: pageSize })}`,
      ),
  });
}

/**
 * Fetch the marca logo as an object URL (auth-protected endpoint).
 * Enables only when the marca actually has a stored image (`tem_logo`).
 * Revokes the created object URL when the code changes / on unmount.
 */
export function useMarcaLogo(codigo: string | null, enabled: boolean) {
  return useQuery({
    queryKey: ["marca-logo", codigo],
    queryFn: async () => {
      const url = await fetchBlobUrl(`/api/marcas/${codigo}/logo`);
      return url;
    },
    enabled: !!codigo && enabled,
    gcTime: 0,
    staleTime: Infinity,
  });
}

// --- Patentes ---------------------------------------------------------------
export type PatenteFilters = {
  q?: string;
  numero_inpi?: string;
  data_deposito_from?: string;
  data_deposito_to?: string;
  page?: number;
  page_size?: number;
  /** When false the query does not run (used by the Patentes screen). */
  enabled?: boolean;
};

export function usePatentes(filters: PatenteFilters) {
  const { enabled = true, ...params } = filters;
  return useQuery({
    queryKey: ["patentes", params],
    queryFn: () =>
      apiFetch<Paginated<Patente>>(`/api/patentes/search${toQuery(params)}`),
    placeholderData: (prev) => prev,
    enabled,
  });
}

export function usePatente(codigo: string | null) {
  return useQuery({
    queryKey: ["patente", codigo],
    queryFn: () => apiFetch<PatenteDetail>(`/api/patentes/${codigo}`),
    enabled: !!codigo,
  });
}

/** Selective monitoring of a single patente (section 4). */
export function useSetPatenteMonitoramento() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ codigo, active }: { codigo: string; active: boolean }) =>
      apiFetch<Monitoramento>(`/api/patentes/${codigo}/monitoramento`, {
        method: "POST",
        body: JSON.stringify({ active }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["patentes"] });
      qc.invalidateQueries({ queryKey: ["patentes-monitoramento"] });
      qc.invalidateQueries({ queryKey: ["patente"] });
    },
  });
}

export function usePatentesMonitoramento(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ["patentes-monitoramento", page, pageSize],
    queryFn: () =>
      apiFetch<Paginated<Monitoramento>>(
        `/api/patentes/monitoramento${toQuery({ page, page_size: pageSize })}`,
      ),
  });
}

// --- Global search ----------------------------------------------------------
export function useGlobalSearch(q: string) {
  return useQuery({
    queryKey: ["global-search", q],
    queryFn: () => apiFetch<{
      query: string;
      marcas: Array<Record<string, unknown>>;
      patentes: Array<Record<string, unknown>>;
    }>(`/api/search?q=${encodeURIComponent(q)}`),
    enabled: q.trim().length >= 2,
  });
}

// --- Admin: ingestion -------------------------------------------------------
export function useDatasets() {
  return useQuery({
    queryKey: ["datasets"],
    queryFn: () => apiFetch<Dataset[]>("/api/admin/inpi/datasets"),
  });
}

export function useImports() {
  return useQuery({
    queryKey: ["imports"],
    queryFn: () =>
      apiFetch<ImportRecord[]>("/api/admin/inpi/imports?limit=50"),
    refetchInterval: 5000,
  });
}

export function useSyncStatus() {
  return useQuery({
    queryKey: ["sync-status"],
    queryFn: () => apiFetch<SyncStatus>("/api/admin/inpi/status"),
    refetchInterval: 5000,
  });
}

export function useTriggerSync() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      category?: string;
      dataset?: string;
      force?: boolean;
    }) =>
      apiFetch("/api/admin/inpi/sync", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sync-status"] });
      qc.invalidateQueries({ queryKey: ["imports"] });
    },
  });
}

// --- CRM: companies ---------------------------------------------------------
export type CompanyFilters = {
  q?: string;
  active?: boolean;
  page?: number;
  page_size?: number;
};

export function useCompanies(filters: CompanyFilters) {
  return useQuery({
    queryKey: ["companies", filters],
    queryFn: () =>
      apiFetch<Paginated<Company>>(`/api/clientes/companies${toQuery(filters)}`),
    placeholderData: (prev) => prev,
  });
}

export function useCreateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Company>) =>
      apiFetch<Company>("/api/clientes/companies", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });
}

export function useUpdateCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<Company> & { id: string }) =>
      apiFetch<Company>(`/api/clientes/companies/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });
}

export function useDeleteCompany() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/clientes/companies/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
  });
}

// --- CRM: customers ---------------------------------------------------------
export type CustomerFilters = {
  q?: string;
  active?: boolean;
  company_id?: string;
  page?: number;
  page_size?: number;
};

export function useCustomers(filters: CustomerFilters) {
  return useQuery({
    queryKey: ["customers", filters],
    queryFn: () =>
      apiFetch<Paginated<Customer>>(`/api/clientes/customers${toQuery(filters)}`),
    placeholderData: (prev) => prev,
  });
}

export function useCreateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Customer>) =>
      apiFetch<Customer>("/api/clientes/customers", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["customers"] });
      qc.invalidateQueries({ queryKey: ["companies"] });
    },
  });
}

export function useUpdateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<Customer> & { id: string }) =>
      apiFetch<Customer>(`/api/clientes/customers/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });
}

export function useDeleteCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/clientes/customers/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });
}

// --- CRM: people ------------------------------------------------------------
export function usePeople(filters: { q?: string; page?: number }) {
  return useQuery({
    queryKey: ["people", filters],
    queryFn: () =>
      apiFetch<Paginated<Person>>(`/api/clientes/people${toQuery(filters)}`),
    placeholderData: (prev) => prev,
  });
}

export function useCreatePerson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Partial<Person>) =>
      apiFetch<Person>("/api/clientes/people", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["people"] }),
  });
}

export function useUpdatePerson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Partial<Person> & { id: string }) =>
      apiFetch<Person>(`/api/clientes/people/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["people"] }),
  });
}

export function useDeletePerson() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/clientes/people/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["people"] }),
  });
}

// --- AI analysis ------------------------------------------------------------
export function useAnalysisStatus() {
  return useQuery({
    queryKey: ["analysis-status"],
    queryFn: () => apiFetch<AnalysisStatus>("/api/analises/status"),
  });
}

export type AnalysisInput = {
  brand_name: string;
  nice_classes: string[];
  holder?: string;
  presentation?: string;
  nature?: string;
  options?: {
    include_patentes?: boolean;
    include_fonetic?: boolean;
    include_visual?: boolean;
    strict_nice?: boolean;
  };
};

export function useRunAnalysis() {
  return useMutation({
    mutationFn: (payload: AnalysisInput) =>
      apiFetch<AnalysisReport>("/api/analises", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}

// --- Admin: users -----------------------------------------------------------
export function useAdminUsers(tenantId?: string) {
  return useQuery({
    queryKey: ["admin-users", tenantId],
    queryFn: () =>
      apiFetch<AdminUser[]>(`/api/admin/users${toQuery({ tenant_id: tenantId })}`),
  });
}

export function useCreateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<AdminUser>("/api/admin/users", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });
}

export function useUpdateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & Record<string, unknown>) =>
      apiFetch<AdminUser>(`/api/admin/users/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });
}

export function useDeactivateUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/admin/users/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-users"] }),
  });
}

// --- Admin: tenants ---------------------------------------------------------
export function useAdminTenants() {
  return useQuery({
    queryKey: ["admin-tenants"],
    queryFn: () => apiFetch<AdminTenant[]>("/api/admin/tenants"),
  });
}

export function useCreateTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<AdminTenant>("/api/admin/tenants", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-tenants"] }),
  });
}

export function useUpdateTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & Record<string, unknown>) =>
      apiFetch<AdminTenant>(`/api/admin/tenants/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-tenants"] }),
  });
}

// --- Admin: modules & roles -------------------------------------------------
export function useAdminModules() {
  return useQuery({
    queryKey: ["admin-modules"],
    queryFn: () => apiFetch<AdminModule[]>("/api/admin/modules"),
  });
}

export function useAdminRoles() {
  return useQuery({
    queryKey: ["admin-roles"],
    queryFn: () => apiFetch<AdminRole[]>("/api/admin/roles"),
  });
}

export function useAdminPermissions() {
  return useQuery({
    queryKey: ["admin-permissions"],
    queryFn: () =>
      apiFetch<Array<{ id: string; code: string; name: string; module_code: string | null }>>(
        "/api/admin/permissions",
      ),
  });
}

// --- Admin: resources & policies (RBAC section 3) ---------------------------
export function useAdminResources(moduleCode?: string) {
  return useQuery({
    queryKey: ["admin-resources", moduleCode],
    queryFn: () =>
      apiFetch<AdminResource[]>(
        `/api/admin/resources${toQuery({ module_code: moduleCode })}`,
      ),
  });
}

export function useAdminGroups() {
  return useQuery({
    queryKey: ["admin-groups"],
    queryFn: () => apiFetch<AdminGroup[]>("/api/admin/groups"),
  });
}

export function useCreateGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<AdminGroup>("/api/admin/groups", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-groups"] }),
  });
}

export function useAdminUserPolicies(userId?: string) {
  return useQuery({
    queryKey: ["admin-user-policies", userId],
    queryFn: () =>
      apiFetch<AdminUserPolicy[]>(
        `/api/admin/user-policies${toQuery({ user_id: userId })}`,
      ),
  });
}

export function useSetUserPolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      user_id: string;
      resource_id: string;
      decision?: PolicyDecision;
      company_id?: string | null;
      unity_id?: string | null;
    }) =>
      apiFetch<AdminUserPolicy>("/api/admin/user-policies", {
        method: "POST",
        body: JSON.stringify({ decision: "ALLOWED", ...payload }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-user-policies"] }),
  });
}

export function useDeleteUserPolicy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/admin/user-policies/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-user-policies"] }),
  });
}

export function useEffectiveAccess(userId: string | null) {
  return useQuery({
    queryKey: ["effective-access", userId],
    queryFn: () =>
      apiFetch<EffectiveAccess>(`/api/admin/users/${userId}/effective-access`),
    enabled: !!userId,
  });
}

// --- Clientes: unities ------------------------------------------------------
export function useUnities(companyId?: string) {
  return useQuery({
    queryKey: ["unities", companyId],
    queryFn: () =>
      apiFetch<{ pagination: unknown; items: Unity[] }>(
        `/api/clientes/unities${toQuery({ company_id: companyId })}`,
      ),
  });
}

// --- NIT (F1) ---------------------------------------------------------------
export function useNitDashboard() {
  return useQuery({
    queryKey: ["nit-dashboard"],
    queryFn: () => apiFetch<NitDashboard>("/api/nit/dashboard"),
  });
}

export type NitDisclosureFilters = {
  q?: string;
  status?: string;
  technology_area?: string;
  unity_id?: string;
  page?: number;
  page_size?: number;
};

export function useNitDisclosures(filters: NitDisclosureFilters) {
  return useQuery({
    queryKey: ["nit-disclosures", filters],
    queryFn: () =>
      apiFetch<PaginatedNit<NitDisclosure>>(`/api/nit/disclosures${toQuery(filters)}`),
    placeholderData: (prev) => prev,
  });
}

export function useNitDisclosure(id: string | null) {
  return useQuery({
    queryKey: ["nit-disclosure", id],
    queryFn: () => apiFetch<NitDisclosureDetail>(`/api/nit/disclosures/${id}`),
    enabled: !!id,
  });
}

export function useCreateNitDisclosure() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitDisclosureDetail>("/api/nit/disclosures", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-disclosures"] });
      qc.invalidateQueries({ queryKey: ["nit-dashboard"] });
    },
  });
}

export function useUpdateNitDisclosure(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitDisclosureDetail>(`/api/nit/disclosures/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-disclosure", id] }),
  });
}

export function useNitWorkflow(disclosureId: string | null) {
  return useQuery({
    queryKey: ["nit-workflow", disclosureId],
    queryFn: () =>
      apiFetch<NitWorkflowStatus>(`/api/nit/disclosures/${disclosureId}/workflow`),
    enabled: !!disclosureId,
  });
}

export function useNitTransition(disclosureId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      to_state: string;
      justification?: string;
      expected_version?: number;
    }) =>
      apiFetch<NitWorkflowStatus>(
        `/api/nit/disclosures/${disclosureId}/workflow/transition`,
        { method: "POST", body: JSON.stringify(payload) },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-workflow", disclosureId] });
      qc.invalidateQueries({ queryKey: ["nit-disclosure", disclosureId] });
      qc.invalidateQueries({ queryKey: ["nit-disclosures"] });
    },
  });
}

export function useNitEvaluations(disclosureId: string | null) {
  return useQuery({
    queryKey: ["nit-evaluations", disclosureId],
    queryFn: () =>
      apiFetch<NitEvaluation[]>(`/api/nit/disclosures/${disclosureId}/evaluations`),
    enabled: !!disclosureId,
  });
}

export function useCreateNitEvaluation(disclosureId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitEvaluation>(`/api/nit/disclosures/${disclosureId}/evaluations`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["nit-evaluations", disclosureId] }),
  });
}

export function useNitDocuments(params: {
  disclosure_id?: string;
  asset_id?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: ["nit-documents", params],
    queryFn: () =>
      apiFetch<PaginatedNit<NitDocument>>(`/api/nit/documents${toQuery(params)}`),
    placeholderData: (prev) => prev,
  });
}

export function useUploadNitDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: {
      file: File;
      disclosure_id?: string;
      asset_id?: string;
      confidentiality_level: string;
      title?: string;
    }) => {
      const form = new FormData();
      form.append("file", input.file);
      if (input.disclosure_id) form.append("disclosure_id", input.disclosure_id);
      if (input.asset_id) form.append("asset_id", input.asset_id);
      form.append("confidentiality_level", input.confidentiality_level);
      if (input.title) form.append("title", input.title);

      const headers = new Headers();
      const access = tokens.access;
      if (access) headers.set("Authorization", `Bearer ${access}`);
      const res = await fetch(`${API_BASE_URL}/api/nit/documents`, {
        method: "POST",
        headers,
        body: form,
      });
      const text = await res.text();
      const body = text ? JSON.parse(text) : null;
      if (!res.ok) {
        const detail = (body && (body.detail || body.message)) || `Erro ${res.status}`;
        throw new ApiError(
          res.status,
          typeof detail === "string" ? detail : JSON.stringify(detail),
        );
      }
      return body as NitDocument;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-documents"] });
      qc.invalidateQueries({ queryKey: ["nit-dashboard"] });
    },
  });
}

/** Download a NIT document through the authenticated endpoint as a Blob. */
export async function downloadNitDocument(id: string, filename: string) {
  const blobUrl = await fetchBlobUrl(`/api/nit/documents/${id}/download`);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(blobUrl);
}

export function useSetNitDocumentAcl(documentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: {
      subject_kind: string;
      subject_id: string;
      permission?: string;
    }) =>
      apiFetch<NitDocumentAcl>(`/api/nit/documents/${documentId}/acl`, {
        method: "POST",
        body: JSON.stringify({ permission: "READ", ...payload }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-documents"] }),
  });
}

export type NitAssetFilters = {
  q?: string;
  asset_type?: string;
  status?: string;
  unity_id?: string;
  page?: number;
  page_size?: number;
};

export function useNitAssets(filters: NitAssetFilters) {
  return useQuery({
    queryKey: ["nit-assets", filters],
    queryFn: () =>
      apiFetch<PaginatedNit<NitAsset>>(`/api/nit/assets${toQuery(filters)}`),
    placeholderData: (prev) => prev,
  });
}

export function useNitAsset(id: string | null) {
  return useQuery({
    queryKey: ["nit-asset", id],
    queryFn: () => apiFetch<NitAssetDetail>(`/api/nit/assets/${id}`),
    enabled: !!id,
  });
}

export function useCreateNitAsset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitAssetDetail>("/api/nit/assets", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-assets"] });
      qc.invalidateQueries({ queryKey: ["nit-dashboard"] });
    },
  });
}

// --- NIT F2: TRL ------------------------------------------------------------
export function useNitTrlHistory(params: { disclosure_id?: string; asset_id?: string }) {
  return useQuery({
    queryKey: ["nit-trl", params],
    queryFn: () =>
      apiFetch<NitTrl[]>(`/api/nit/trl/history${toQuery(params)}`),
  });
}

export function useRecordNitTrl() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitTrl>("/api/nit/trl", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-trl"] });
      qc.invalidateQueries({ queryKey: ["nit-portfolio"] });
    },
  });
}

// --- NIT F2: committees -----------------------------------------------------
export function useNitCommittees() {
  return useQuery({
    queryKey: ["nit-committees"],
    queryFn: () => apiFetch<NitCommittee[]>("/api/nit/committees"),
  });
}

export function useNitCommittee(id: string | null) {
  return useQuery({
    queryKey: ["nit-committee", id],
    queryFn: () => apiFetch<NitCommitteeDetail>(`/api/nit/committees/${id}`),
    enabled: !!id,
  });
}

export function useCreateNitCommittee() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitCommitteeDetail>("/api/nit/committees", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-committees"] }),
  });
}

export function useAddCommitteeMember(committeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitCommitteeMember>(
        `/api/nit/committees/${committeeId}/members`,
        { method: "POST", body: JSON.stringify(payload) },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-committee", committeeId] }),
  });
}

export function useNitMeetings(committeeId: string | null) {
  return useQuery({
    queryKey: ["nit-meetings", committeeId],
    queryFn: () =>
      apiFetch<NitMeeting[]>(`/api/nit/committees/${committeeId}/meetings`),
    enabled: !!committeeId,
  });
}

export function useCreateNitMeeting(committeeId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitMeeting>(`/api/nit/committees/${committeeId}/meetings`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-meetings", committeeId] }),
  });
}

export function useAddAgendaItem(meetingId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitAgendaItem>(`/api/nit/committees/meetings/${meetingId}/items`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["nit-agenda-items", meetingId] }),
  });
}

export function useNitAgendaItems(meetingId: string | null) {
  return useQuery({
    queryKey: ["nit-agenda-items", meetingId],
    queryFn: () =>
      apiFetch<NitAgendaItem[]>(`/api/nit/committees/meetings/${meetingId}/items`),
    enabled: !!meetingId,
  });
}

export function useItemVotes(itemId: string | null) {
  return useQuery({
    queryKey: ["nit-votes", itemId],
    queryFn: () => apiFetch<NitVoteTally>(`/api/nit/committees/items/${itemId}/votes`),
    enabled: !!itemId,
  });
}

export function useCastVote(itemId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<unknown>(`/api/nit/committees/items/${itemId}/votes`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-votes", itemId] }),
  });
}

export function useDecideItem(itemId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { outcome: string; justification?: string }) =>
      apiFetch<NitDecision>(`/api/nit/committees/items/${itemId}/decision`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-votes", itemId] }),
  });
}

// --- NIT F2: portfolio ------------------------------------------------------
export function useNitPortfolio(params: {
  asset_type?: string;
  status?: string;
  unity_id?: string;
}) {
  return useQuery({
    queryKey: ["nit-portfolio", params],
    queryFn: () => apiFetch<NitPortfolioView>(`/api/nit/portfolio${toQuery(params)}`),
  });
}

export function useNitPortfolioAlerts(days = 90) {
  return useQuery({
    queryKey: ["nit-portfolio-alerts", days],
    queryFn: () =>
      apiFetch<NitDeadlineAlert[]>(`/api/nit/portfolio/alerts${toQuery({ days })}`),
  });
}

// --- NIT F3: catalog and offers ---------------------------------------------
export function useNitOffers(params: { q?: string; status?: string; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["nit-offers", params],
    queryFn: () => apiFetch<PaginatedNit<NitOffer>>(`/api/nit/tt/offers${toQuery(params)}`),
    placeholderData: (prev) => prev,
  });
}

export function useNitCatalog(params: { q?: string; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["nit-catalog", params],
    queryFn: () => apiFetch<PaginatedNit<NitOffer>>(`/api/nit/tt/catalog${toQuery(params)}`),
    placeholderData: (prev) => prev,
  });
}

export function useCreateNitOffer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitOffer>("/api/nit/tt/offers", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-offers"] }),
  });
}

export function useUpdateNitOffer(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitOffer>(`/api/nit/tt/offers/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-offers"] });
      qc.invalidateQueries({ queryKey: ["nit-catalog"] });
    },
  });
}

// --- NIT F3: interests and negotiations -------------------------------------
export function useNitInterests(params: { offer_id?: string; status?: string; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["nit-interests", params],
    queryFn: () => apiFetch<PaginatedNit<NitInterest>>(`/api/nit/tt/interests${toQuery(params)}`),
    placeholderData: (prev) => prev,
  });
}

export function useRegisterInterest(offerId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitInterest>(`/api/nit/tt/offers/${offerId}/interests`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-interests"] }),
  });
}

export function useNitNegotiations() {
  return useQuery({
    queryKey: ["nit-negotiations"],
    queryFn: () => apiFetch<NitNegotiation[]>("/api/nit/tt/negotiations"),
  });
}

export function useNitNegotiation(id: string | null) {
  return useQuery({
    queryKey: ["nit-negotiation", id],
    queryFn: () => apiFetch<NitNegotiationDetail>(`/api/nit/tt/negotiations/${id}`),
    enabled: !!id,
  });
}

export function useCreateNegotiation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitNegotiationDetail>("/api/nit/tt/negotiations", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-negotiations"] }),
  });
}

export function useAdvanceNegotiation(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { to_stage: string; expected_version?: number; justification?: string }) =>
      apiFetch<NitNegotiationDetail>(`/api/nit/tt/negotiations/${id}/advance`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-negotiation", id] });
      qc.invalidateQueries({ queryKey: ["nit-negotiations"] });
    },
  });
}

export function useAddInteraction(interestId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { kind: string; summary: string }) =>
      apiFetch<NitInteraction>(`/api/nit/tt/interests/${interestId}/interactions`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["nit-interactions", interestId] }),
  });
}

export function useInteractions(interestId: string | null) {
  return useQuery({
    queryKey: ["nit-interactions", interestId],
    queryFn: () =>
      apiFetch<NitInteraction[]>(`/api/nit/tt/interests/${interestId}/interactions`),
    enabled: !!interestId,
  });
}

// --- NIT F3: contracts ------------------------------------------------------
export function useNitContracts(params: { q?: string; status?: string; page?: number; page_size?: number }) {
  return useQuery({
    queryKey: ["nit-contracts", params],
    queryFn: () =>
      apiFetch<PaginatedNit<NitContract>>(`/api/nit/contracts${toQuery(params)}`),
    placeholderData: (prev) => prev,
  });
}

export function useNitContract(id: string | null) {
  return useQuery({
    queryKey: ["nit-contract", id],
    queryFn: () => apiFetch<NitContractDetail>(`/api/nit/contracts/${id}`),
    enabled: !!id,
  });
}

export function useCreateNitContract() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitContractDetail>("/api/nit/contracts", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-contracts"] }),
  });
}

export function useUpdateNitContract(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitContract>(`/api/nit/contracts/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-contract", id] });
      qc.invalidateQueries({ queryKey: ["nit-contracts"] });
    },
  });
}

export function useNitObligations(contractId: string | null) {
  return useQuery({
    queryKey: ["nit-obligations", contractId],
    queryFn: () =>
      apiFetch<NitObligation[]>(`/api/nit/contracts/${contractId}/obligations`),
    enabled: !!contractId,
  });
}

export function useCreateObligation(contractId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitObligation>(`/api/nit/contracts/${contractId}/obligations`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["nit-obligations", contractId] }),
  });
}

export function useUpdateObligation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      apiFetch<NitObligation>(`/api/nit/contracts/obligations/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-obligations"] }),
  });
}

export function useNitObligationAlerts(days = 60) {
  return useQuery({
    queryKey: ["nit-obligation-alerts", days],
    queryFn: () =>
      apiFetch<NitObligationAlert[]>(
        `/api/nit/contracts/obligations/alerts${toQuery({ days })}`,
      ),
  });
}

export function useNitRoyalties(contractId: string | null) {
  return useQuery({
    queryKey: ["nit-royalties", contractId],
    queryFn: () => apiFetch<NitRoyalty[]>(`/api/nit/contracts/${contractId}/royalties`),
    enabled: !!contractId,
  });
}

export function useNitRoyaltySummary(contractId: string | null) {
  return useQuery({
    queryKey: ["nit-royalty-summary", contractId],
    queryFn: () =>
      apiFetch<NitRoyaltySummary>(
        `/api/nit/contracts/${contractId}/royalties/summary`,
      ),
    enabled: !!contractId,
  });
}

export function useCreateRoyalty(contractId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitRoyalty>(`/api/nit/contracts/${contractId}/royalties`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-royalties", contractId] });
      qc.invalidateQueries({ queryKey: ["nit-royalty-summary", contractId] });
    },
  });
}

// --- F4: projects -----------------------------------------------------------
export function useNitProjects(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["nit-projects", params],
    queryFn: () => apiFetch<PaginatedNit<NitProject>>(`/api/nit/projects${toQuery(params)}`),
  });
}

export function useNitProject(projectId: string | null) {
  return useQuery({
    queryKey: ["nit-project", projectId],
    queryFn: () => apiFetch<NitProjectDetail>(`/api/nit/projects/${projectId}`),
    enabled: !!projectId,
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitProject>("/api/nit/projects", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-projects"] }),
  });
}

export function useUpdateProject(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitProject>(`/api/nit/projects/${projectId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-projects"] });
      qc.invalidateQueries({ queryKey: ["nit-project", projectId] });
    },
  });
}

export function useCreateProjectMember(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitProjectMember>(`/api/nit/projects/${projectId}/members`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-project", projectId] }),
  });
}

export function useCreateProjectFunder(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitProjectFunder>(`/api/nit/projects/${projectId}/funders`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-project", projectId] }),
  });
}

export function useCreateProjectMilestone(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitProjectMilestone>(`/api/nit/projects/${projectId}/milestones`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-project", projectId] }),
  });
}

export function useUpdateProjectMilestone(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      apiFetch<NitProjectMilestone>(`/api/nit/projects/milestones/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-project", projectId] }),
  });
}

export function useLinkProjectAsset(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<Record<string, unknown>>(`/api/nit/projects/${projectId}/assets`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-project", projectId] }),
  });
}

// --- F4: startups & incubation ----------------------------------------------
export function useNitStartups(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["nit-startups", params],
    queryFn: () => apiFetch<PaginatedNit<NitStartup>>(`/api/nit/startups${toQuery(params)}`),
  });
}

export function useNitStartup(startupId: string | null) {
  return useQuery({
    queryKey: ["nit-startup", startupId],
    queryFn: () => apiFetch<NitStartup & { members: NitStartupMember[] }>(
      `/api/nit/startups/${startupId}`,
    ),
    enabled: !!startupId,
  });
}

export function useCreateStartup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitStartup>("/api/nit/startups", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-startups"] }),
  });
}

export function useUpdateStartup(startupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitStartup>(`/api/nit/startups/${startupId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-startups"] });
      qc.invalidateQueries({ queryKey: ["nit-startup", startupId] });
    },
  });
}

export function useCreateStartupMember(startupId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitStartupMember>(`/api/nit/startups/${startupId}/members`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-startup", startupId] }),
  });
}

export function useNitPrograms() {
  return useQuery({
    queryKey: ["nit-programs"],
    queryFn: () => apiFetch<NitProgram[]>("/api/nit/startups/programs/list"),
  });
}

export function useCreateProgram() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitProgram>("/api/nit/startups/programs/list", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-programs"] }),
  });
}

export function useCreateParticipation(programId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitParticipation>(
        `/api/nit/startups/programs/list/${programId}/participations`,
        { method: "POST", body: JSON.stringify(payload) },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-startups"] });
      qc.invalidateQueries({ queryKey: ["nit-participation"] });
    },
  });
}

export function useParticipation(participationId: string | null) {
  return useQuery({
    queryKey: ["nit-participation", participationId],
    queryFn: () =>
      apiFetch<NitParticipationDetail>(`/api/nit/startups/participations/${participationId}`),
    enabled: !!participationId,
  });
}

export function useCreateIncubationStage(participationId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitIncubationStage>(
        `/api/nit/startups/participations/${participationId}/stages`,
        { method: "POST", body: JSON.stringify(payload) },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-participation", participationId] }),
  });
}

// --- F4: indicators & FORMICT -----------------------------------------------
export function useNitIndicators(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["nit-indicators", params],
    queryFn: () => apiFetch<NitIndicators>(`/api/nit/indicators${toQuery(params)}`),
  });
}

export function useNitFormict(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["nit-formict", params],
    queryFn: () => apiFetch<NitFormictReport>(`/api/nit/formict${toQuery(params)}`),
  });
}

// --- F5: notifications ------------------------------------------------------
export function useNitNotifications(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["nit-notifications", params],
    queryFn: () =>
      apiFetch<NitNotificationList>(`/api/nit/notifications${toQuery(params)}`),
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<NitNotification>(`/api/nit/notifications/${id}/read`, {
        method: "POST",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-notifications"] }),
  });
}

export function useMarkAllNotificationsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ updated: number }>("/api/nit/notifications/read-all", {
        method: "POST",
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-notifications"] }),
  });
}

export function useNitNotificationPreferences() {
  return useQuery({
    queryKey: ["nit-notification-preferences"],
    queryFn: () =>
      apiFetch<NitNotificationPreference[]>("/api/nit/notifications/preferences"),
  });
}

export function useUpsertNotificationPreference() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitNotificationPreference>("/api/nit/notifications/preferences", {
        method: "PUT",
        body: JSON.stringify(payload),
      }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ["nit-notification-preferences"] }),
  });
}

export function useNitEmails(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["nit-emails", params],
    queryFn: () =>
      apiFetch<NitEmailMessage[]>(`/api/nit/notifications/emails${toQuery(params)}`),
  });
}

// --- F5: external portals ---------------------------------------------------
export function useNitPortalAccess(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["nit-portal-access", params],
    queryFn: () =>
      apiFetch<NitPortalAccess[]>(`/api/nit/portal/access${toQuery(params)}`),
  });
}

export function useCreatePortalAccess() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitPortalAccess>("/api/nit/portal/access", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-portal-access"] }),
  });
}

export function useRevokePortalAccess() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch<NitPortalAccess>(`/api/nit/portal/access/${id}/revoke`, {
        method: "POST",
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-portal-access"] });
      qc.invalidateQueries({ queryKey: ["nit-portal-requests"] });
    },
  });
}

export function useNitPortalRequests(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["nit-portal-requests", params],
    queryFn: () =>
      apiFetch<NitPortalRequest[]>(`/api/nit/portal/requests${toQuery(params)}`),
  });
}

export function useNitPortalRequest(requestId: string | null) {
  return useQuery({
    queryKey: ["nit-portal-request", requestId],
    queryFn: () =>
      apiFetch<NitPortalRequestDetail>(`/api/nit/portal/requests/${requestId}`),
    enabled: !!requestId,
  });
}

export function useTriagePortalRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Record<string, unknown> }) =>
      apiFetch<NitPortalRequestDetail>(`/api/nit/portal/requests/${id}/triage`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["nit-portal-requests"] });
      qc.invalidateQueries({ queryKey: ["nit-portal-request"] });
    },
  });
}

// --- F5: BI reports ---------------------------------------------------------
export function useNitBiMetrics() {
  return useQuery({
    queryKey: ["nit-bi-metrics"],
    queryFn: () => apiFetch<string[]>("/api/nit/bi/metrics"),
  });
}

export function useNitSavedReports() {
  return useQuery({
    queryKey: ["nit-bi-reports"],
    queryFn: () => apiFetch<NitSavedReport[]>("/api/nit/bi/reports"),
  });
}

export function useCreateSavedReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitSavedReport>("/api/nit/bi/reports", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-bi-reports"] }),
  });
}

export function useRunSavedReport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, days }: { id: string; days?: number }) =>
      apiFetch<{ report_id: string; result: Record<string, unknown>; run_id: string }>(
        `/api/nit/bi/reports/${id}/run${toQuery({ days })}`,
        { method: "POST" },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-bi-reports"] }),
  });
}

// --- F5: integrations -------------------------------------------------------
export function useNitIntegrationEndpoints(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["nit-integrations", params],
    queryFn: () =>
      apiFetch<NitIntegrationEndpoint[]>(`/api/nit/integrations/endpoints${toQuery(params)}`),
  });
}

export function useCreateIntegrationEndpoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<NitIntegrationEndpoint>("/api/nit/integrations/endpoints", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["nit-integrations"] }),
  });
}

export function useNitIntegrationDeliveries(params: Record<string, unknown> = {}) {
  return useQuery({
    queryKey: ["nit-integration-deliveries", params],
    queryFn: () =>
      apiFetch<NitIntegrationDelivery[]>(
        `/api/nit/integrations/deliveries${toQuery(params)}`,
      ),
  });
}





// --- Business dashboard (Visão Geral do negócio) -----------------------------
/**
 * Commercial/operational dashboard of the authenticated tenant.
 * Every number comes from ``GET /api/dashboard/business`` (real tenant data).
 */
export function useBusinessDashboard(months = 12) {
  return useQuery({
    queryKey: ["business-dashboard", months],
    queryFn: () =>
      apiFetch<BusinessDashboard>(
        `/api/dashboard/business${toQuery({ months })}`,
      ),
  });
}

// --- CRM: opportunities ------------------------------------------------------
export type OpportunityFilters = {
  q?: string;
  stage?: string;
  customer_id?: string;
  owner_id?: string;
  active?: boolean;
  page?: number;
  page_size?: number;
};

export function useOpportunities(filters: OpportunityFilters) {
  return useQuery({
    queryKey: ["crm-opportunities", filters],
    queryFn: () =>
      apiFetch<Paginated<Opportunity>>(
        `/api/crm/opportunities${toQuery(filters)}`,
      ),
    placeholderData: (prev) => prev,
  });
}

export function useOpportunity(id: string | null) {
  return useQuery({
    queryKey: ["crm-opportunity", id],
    queryFn: () => apiFetch<Opportunity>(`/api/crm/opportunities/${id}`),
    enabled: !!id,
  });
}

function invalidateCrm(qc: ReturnType<typeof useQueryClient>) {
  qc.invalidateQueries({ queryKey: ["crm-opportunities"] });
  qc.invalidateQueries({ queryKey: ["crm-opportunity"] });
  qc.invalidateQueries({ queryKey: ["crm-proposals"] });
  qc.invalidateQueries({ queryKey: ["crm-proposal"] });
  qc.invalidateQueries({ queryKey: ["crm-activities"] });
  qc.invalidateQueries({ queryKey: ["business-dashboard"] });
  qc.invalidateQueries({ queryKey: ["customers"] });
}

// --- Assistente (chat) ------------------------------------------------------

export function useChatStatus(enabled = true) {
  return useQuery({
    queryKey: ["chat-status"],
    queryFn: () => apiFetch<ChatStatus>("/api/chat/status"),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useAskChat() {
  return useMutation({
    mutationFn: (payload: { message: string; history: { role: string; content: string }[] }) =>
      apiFetch<ChatResponse>("/api/chat", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
  });
}


export function useCreateOpportunity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<Opportunity>("/api/crm/opportunities", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => invalidateCrm(qc),
  });
}

export function useUpdateOpportunity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Record<string, unknown> & { id: string }) =>
      apiFetch<Opportunity>(`/api/crm/opportunities/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => invalidateCrm(qc),
  });
}

export function useChangeOpportunityStage() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...payload
    }: { id: string; stage: string } & Record<string, unknown>) =>
      apiFetch<Opportunity>(`/api/crm/opportunities/${id}/stage`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => invalidateCrm(qc),
  });
}

/**
 * Convert a won lead into a client.
 *
 * ``customer_id`` links an existing client (no duplication); otherwise the
 * backend searches by document/e-mail/name before creating a new ``Customer``.
 */
export function useConvertOpportunity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: { id: string } & Record<string, unknown>) =>
      apiFetch<Opportunity>(`/api/crm/opportunities/${id}/convert`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => invalidateCrm(qc),
  });
}

export function useDeleteOpportunity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/crm/opportunities/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidateCrm(qc),
  });
}



// --- CRM: proposals ----------------------------------------------------------
export type ProposalFilters = {
  q?: string;
  status?: string;
  customer_id?: string;
  opportunity_id?: string;
  owner_id?: string;
  overdue_only?: boolean;
  active?: boolean;
  page?: number;
  page_size?: number;
};

export function useProposals(filters: ProposalFilters) {
  return useQuery({
    queryKey: ["crm-proposals", filters],
    queryFn: () =>
      apiFetch<Paginated<Proposal>>(`/api/crm/proposals${toQuery(filters)}`),
    placeholderData: (prev) => prev,
  });
}

export function useProposal(id: string | null) {
  return useQuery({
    queryKey: ["crm-proposal", id],
    queryFn: () => apiFetch<Proposal>(`/api/crm/proposals/${id}`),
    enabled: !!id,
  });
}

export function useCreateProposal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<Proposal>("/api/crm/proposals", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => invalidateCrm(qc),
  });
}

export function useUpdateProposal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Record<string, unknown> & { id: string }) =>
      apiFetch<Proposal>(`/api/crm/proposals/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => invalidateCrm(qc),
  });
}

/**
 * Move a proposal through its lifecycle.
 *
 * ``mark_sent`` / ``mark_reply`` record the *actual* send and reply moments
 * (the backend stamps ``sent_at`` / ``replied_at``); approvals never register a
 * trademark or execute a service.
 */
export function useChangeProposalStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      ...payload
    }: { id: string; status: string } & Record<string, unknown>) =>
      apiFetch<Proposal>(`/api/crm/proposals/${id}/status`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => invalidateCrm(qc),
  });
}

export function useDeleteProposal() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/crm/proposals/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidateCrm(qc),
  });
}

// --- CRM: activities ---------------------------------------------------------
export type ActivityFilters = {
  subject_type?: string;
  subject_id?: string;
  kind?: string;
  outcome?: string;
  owner_id?: string;
  pending_only?: boolean;
  page?: number;
  page_size?: number;
};

export function useCrmActivities(filters: ActivityFilters) {
  return useQuery({
    queryKey: ["crm-activities", filters],
    queryFn: () =>
      apiFetch<Paginated<CrmActivity>>(`/api/crm/activities${toQuery(filters)}`),
    placeholderData: (prev) => prev,
  });
}

export function useCreateCrmActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      apiFetch<CrmActivity>("/api/crm/activities", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => invalidateCrm(qc),
  });
}

export function useUpdateCrmActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }: Record<string, unknown> & { id: string }) =>
      apiFetch<CrmActivity>(`/api/crm/activities/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => invalidateCrm(qc),
  });
}

export function useDeleteCrmActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) =>
      apiFetch(`/api/crm/activities/${id}`, { method: "DELETE" }),
    onSuccess: () => invalidateCrm(qc),
  });
}
