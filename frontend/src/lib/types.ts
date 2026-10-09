/** Shared API types mirrored from the backend Pydantic schemas. */

export type Pagination = {
  page: number;
  page_size: number;
  total: number;
};

export type MarcaClassificacao = {
  tipo: "nice" | "nacional" | "viena" | string;
  codigo: string;
  descricao: string | null;
};

export type Marca = {
  id: string;
  codigo_interno: string;
  numero_inpi: string | null;
  data_deposito: string | null;
  data_concessao: string | null;
  descricao_apresentacao: string | null;
  descricao_natureza: string | null;
  elemento_nominativo: string | null;
  codigo_situacao: string | null;
  descricao_situacao: string | null;
  // Source of truth for titulares; principal/num are derived for presentation.
  titulares: string[];
  titular_principal: string | null;
  num_titulares: number;
  classificacoes: MarcaClassificacao[];
  // Selective monitoring (section 4): true only for the current user's watch.
  monitorada: boolean;
  monitoramento_id: string | null;
};

/** A user's own selective-monitoring row for one marca/patente. */
export type Monitoramento = {
  id: string;
  tenant_id: string;
  user_id: string;
  codigo_interno: string;
  /** "marca" | "patente" — set by the list endpoints. */
  tipo: string;
  active: boolean;
  notes: string | null;
  monitored_at: string | null;
  // Display fields joined from the underlying marca/patente (null if absent).
  titulo: string | null;
  numero_inpi: string | null;
  situacao: string | null;
  data_deposito: string | null;
};

export type MarcaDetail = Marca & {
  data_publicacao: string | null;
  data_vigencia: string | null;
  traducao: string | null;
  apostila: string | null;
  depositantes: Array<{
    nome?: string;
    cnpj_cpf_titular?: string;
    tipo_pfpj_titular?: string;
    pais?: string;
    estado?: string;
  }>;
  representantes_legais: Array<{
    nome?: string;
    cnpj_cpf?: string;
    tipo_pfpj?: string;
  }>;
  classificacoes_nacionais: Array<{ classe?: string; especificacao?: string }>;
  classificacoes_nice: Array<{
    edicao_nice?: string;
    classe_nice?: string;
    especificacao?: string;
  }>;
  classificacoes_viena: Array<{
    simbolo?: string;
    classificacao_viena?: string;
    revisao_viena?: string;
  }>;
  despachos: Array<{
    numero_rpi?: string | null;
    data_rpi?: string | null;
    codigo_despacho?: string | null;
    descricao_despacho?: string | null;
    complemento_despacho?: string | null;
  }>;
  // Logotipo (imagem) baixado do pePI. `tem_logo` só é true quando há imagem
  // real armazenada; `logo_status` reflete o processamento (OK/SEM_IMAGEM/...).
  tem_logo: boolean;
  logo_status: string | null;
};

export type Patente = {
  id: string;
  codigo_interno: string;
  numero_inpi: string | null;
  data_deposito: string | null;
  data_publicacao: string | null;
  numero_pct: string | null;
  titulo: string | null;
  // Selective monitoring (section 4): true only for the current user's watch.
  monitorada: boolean;
  monitoramento_id: string | null;
};

export type PatenteDetail = Patente & {
  data_protocolo: string | null;
  numero_wo: string | null;
  data_publicacao_wo: string | null;
  data_entrada_fase_nacional: string | null;
  sigilo: string | null;
  resumo: string | null;
  depositantes: Array<Record<string, unknown>>;
  inventores: Array<Record<string, unknown>>;
  procuradores: Array<Record<string, unknown>>;
  prioridades: Array<Record<string, unknown>>;
  classificacoes_ipc: Array<Record<string, unknown>>;
  despachos: Array<Record<string, unknown>>;
};

export type Paginated<T> = {
  pagination: Pagination;
  items: T[];
};

export type DashboardSummary = {
  marcas: number;
  patentes: number;
  is_master_admin: boolean;
  modules: string[];
  users: number;
  tenants?: number;
  companies?: number;
  customers?: number;
  latest_marcas: Array<{
    numero_inpi: string | null;
    elemento_nominativo: string | null;
    data_deposito: string | null;
  }>;
  portfolio_evolution?: Array<{ ano: number; marcas: number; patentes: number }>;
  situacao_distribution?: Array<{ label: string; value: number }>;
  latest_events?: Array<{
    tipo: string;
    titulo: string;
    numero_inpi: string | null;
    data: string | null;
  }>;
  upcoming_deadlines?: Array<{
    titulo: string;
    numero_inpi: string | null;
    data_vigencia: string | null;
    situacao: string | null;
    dias_restantes: number | null;
  }>;
};

export type Dataset = {
  id: string;
  name: string;
  category: string;
  status: string;
  description?: string | null;
  file_size?: number | null;
  reference_date?: string | null;
};

export type ImportRecord = {
  id: string;
  dataset_id: string;
  status: string;
  rows_read: number;
  rows_inserted: number;
  error_count: number;
  started_at: string;
  finished_at: string | null;
};

export type SyncStatus = {
  datasets: { total: number; imported: number; failed: number };
  imports_running: number;
  last_completed_at: string | null;
};

// --- CRM: companies / customers / people ------------------------------------
export type Company = {
  id: string;
  tenant_id: string;
  company_name: string;
  external_id: string | null;
  file_document: string | null;
  social_reason: string | null;
  cnpj: string | null;
  email: string | null;
  phone: string | null;
  notes: string | null;
  active: boolean;
  customer_count: number;
  unity_count: number;
  created_at: string;
};

export type UnityMatrizType = "MATRIZ" | "FILIAL";

export type Unity = {
  id: string;
  tenant_id: string;
  company_id: string;
  company_name: string | null;
  name: string;
  social_reason: string | null;
  cnpj: string | null;
  matriz_type: UnityMatrizType;
  cnes: string | null;
  sanitary_license: string | null;
  opening_hours: string | null;
  email: string | null;
  phone: string | null;
  address_line: string | null;
  address_number: string | null;
  address_complement: string | null;
  district: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  notes: string | null;
  active: boolean;
  created_at: string;
};

export type Customer = {
  id: string;
  tenant_id: string;
  company_id: string | null;
  unity_id: string | null;
  person_id: string | null;
  company_name: string | null;
  unity_name: string | null;
  person_name: string | null;
  code: string | null;
  name: string;
  document: string | null;
  email: string | null;
  phone: string | null;
  notes: string | null;
  active: boolean;
  created_at: string;
};

export type Person = {
  id: string;
  tenant_id: string | null;
  user_id: string | null;
  name: string;
  cpf: string | null;
  email: string | null;
  cell_phone: string | null;
  address_line: string | null;
  address_number: string | null;
  address_complement: string | null;
  district: string | null;
  city: string | null;
  state: string | null;
  zip_code: string | null;
  responsibility: string | null;
  job_title: string | null;
  notes: string | null;
  active: boolean;
  created_at: string;
};

// --- AI analysis ------------------------------------------------------------
export type RiskLevel = "baixo" | "moderado" | "alto" | "critico";

export type ConflictItem = {
  title: string;
  score: number;
  level: RiskLevel;
  description: string | null;
  fonte: string | null;
};

export type SimilarBrand = {
  nome: string | null;
  numero_inpi: string | null;
  situacao: string | null;
  similaridade: number;
  classes: string[];
};

export type RelatedPatent = {
  titulo: string | null;
  numero_inpi: string | null;
  depositante: string | null;
  relevancia: number;
};

export type AnalysisReport = {
  id: string | null;
  brand_name: string;
  holder: string | null;
  nice_classes: string[];
  created_at: string;
  overall_risk: RiskLevel;
  score: number;
  summary: string;
  conflicts: ConflictItem[];
  similar_brands: SimilarBrand[];
  related_patents: RelatedPatent[];
  recommendations: string[];
  ai_available: boolean;
  model: string | null;
};

export type AnalysisStatus = {
  configured: boolean;
  model: string;
  message: string;
};

// --- Admin ------------------------------------------------------------------
export type AdminUser = {
  id: string;
  access_code: string;
  email: string;
  person_id: string | null;
  tenant_id: string | null;
  tenant_name: string | null;
  type: string;
  mfa: boolean;
  active: boolean;
  is_master_admin: boolean;
  last_login_at: string | null;
  created_at: string;
  roles: Array<{ id: string; name: string; code: string }>;
};

export type AdminTenant = {
  id: string;
  social_reason: string;
  company_name: string | null;
  cnpj: string | null;
  mcp_api_key: string | null;
  email: string | null;
  phone: string | null;
  active: boolean;
  created_at: string;
  modules: string[];
  user_count: number;
};

export type AdminModule = {
  id: string;
  name: string;
  code: string;
  description: string | null;
  control_company_unity: boolean;
  sort_order: number;
  active: boolean;
};

// --- RBAC: Module → Resource → Policies -------------------------------------
export type AdminResource = {
  id: string;
  module_id: string;
  module_code: string | null;
  code: string;
  name: string;
  description: string | null;
  is_native: boolean;
  control_company_unity: boolean;
  active: boolean;
  created_at: string;
};

export type PolicyDecision = "ALLOWED" | "DENIED";

export type AdminUserPolicy = {
  id: string;
  user_id: string;
  resource_id: string;
  resource_code: string | null;
  tenant_id: string | null;
  company_id: string | null;
  unity_id: string | null;
  decision: string;
  created_at: string;
};

export type AdminGroup = {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
  description: string | null;
  active: boolean;
  created_at: string;
};

export type AdminGroupPolicy = {
  id: string;
  group_id: string;
  resource_id: string;
  resource_code: string | null;
  company_id: string | null;
  unity_id: string | null;
  decision: string;
  created_at: string;
};

export type EffectiveAccess = {
  user_id: string;
  roles: string[];
  modules: string[];
  permissions: string[];
  resources: string[];
  scoped_resources: Record<
    string,
    { company_id: string[]; unity_id: string[] }
  >;
  companies: string[];
  unities: string[];
};

export type AdminRole = {
  id: string;
  name: string;
  code: string;
  module_code: string | null;
  description: string | null;
  is_system: boolean;
  active: boolean;
  permissions: string[];
};
