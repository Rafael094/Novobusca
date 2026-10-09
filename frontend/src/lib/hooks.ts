"use client";

/** React Query hooks wrapping the typed API client. */

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { apiFetch, fetchBlobUrl } from "./api";
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
  Company,
  Customer,
  DashboardSummary,
  Dataset,
  EffectiveAccess,
  ImportRecord,
  Marca,
  MarcaDetail,
  Monitoramento,
  Paginated,
  Patente,
  PatenteDetail,
  Person,
  PolicyDecision,
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
