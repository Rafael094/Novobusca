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
  // Enriched marca data (marcas only; null/default for patentes).
  data_publicacao: string | null;
  data_concessao: string | null;
  data_vigencia: string | null;
  descricao_apresentacao: string | null;
  descricao_natureza: string | null;
  titulares: string[];
  titular_principal: string | null;
  num_titulares: number;
  total_despachos: number;
  data_ultimo_despacho: string | null;
  ultimo_despacho: string | null;
  // Vencimento (derived from data_vigencia by the backend).
  dias_para_vencer: number | null;
  vencido: boolean;
  vence_em_breve: boolean;
  // Logotipo.
  tem_logo: boolean;
  logo_status: string | null;
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

// --- NIT (F1) ---------------------------------------------------------------
export type PaginatedNit<T> = {
  items: T[];
  page: number;
  page_size: number;
  total: number;
};

export type ConfidentialityLevel =
  | "PUBLIC"
  | "INTERNAL"
  | "RESTRICTED"
  | "CONFIDENTIAL";

export type NitInventor = {
  id: string;
  tenant_id: string;
  disclosure_id: string;
  name: string;
  kind: "INTERNAL" | "EXTERNAL";
  person_id: string | null;
  user_id: string | null;
  document: string | null;
  email: string | null;
  institution: string | null;
  share_percent: number | null;
  is_primary: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type NitDisclosure = {
  id: string;
  tenant_id: string;
  protocol: string;
  title: string;
  summary: string | null;
  description: string | null;
  context: string | null;
  technology_area: string | null;
  keywords: string | null;
  unity_id: string | null;
  confidentiality_level: ConfidentialityLevel;
  status: string;
  submitted_at: string;
  submitted_by_id: string | null;
  responsible_id: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
};

export type NitDisclosureDetail = NitDisclosure & {
  inventors: NitInventor[];
};

export type NitDocument = {
  id: string;
  tenant_id: string;
  disclosure_id: string | null;
  asset_id: string | null;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  checksum_sha256: string;
  confidentiality_level: ConfidentialityLevel;
  title: string | null;
  description: string | null;
  scan_status: string;
  uploaded_by_id: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type NitDocumentAcl = {
  id: string;
  subject_kind: "USER" | "ROLE" | "UNITY";
  subject_id: string;
  permission: "READ" | "WRITE" | "MANAGE";
  created_at: string;
};

export type NitDocumentDetail = NitDocument & { acls: NitDocumentAcl[] };

export type NitWorkflowTransition = {
  id: string;
  from_state: string;
  to_state: string;
  name: string;
  required_permission: string | null;
  required_role_code: string | null;
  requires_justification: boolean;
};

export type NitWorkflowHistory = {
  id: string;
  from_state: string | null;
  to_state: string;
  actor_id: string | null;
  justification: string | null;
  version: number;
  created_at: string;
};

export type NitWorkflowStatus = {
  disclosure_id: string;
  current_state: string;
  current_state_name: string | null;
  version: number;
  is_terminal: boolean;
  available_transitions: NitWorkflowTransition[];
  history: NitWorkflowHistory[];
};

export type NitEvaluation = {
  id: string;
  tenant_id: string;
  disclosure_id: string;
  kind: "TECHNICAL" | "LEGAL" | "COMMERCIAL";
  evaluator_id: string | null;
  outcome: string;
  summary: string | null;
  criteria: string | null;
  technological_potential: string | null;
  market_potential: string | null;
  risks: string | null;
  recommendations: string | null;
  trl_level: number | null;
  confidentiality_level: ConfidentialityLevel;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type NitPublicLink = {
  id: string;
  source: "INPI_MARCA" | "INPI_PATENTE";
  external_ref: string;
  label: string | null;
  synced_at: string;
};

export type NitAsset = {
  id: string;
  tenant_id: string;
  code: string;
  title: string;
  description: string | null;
  asset_type: string;
  status: string;
  technology_area: string | null;
  unity_id: string | null;
  disclosure_id: string | null;
  confidentiality_level: ConfidentialityLevel;
  deposited_at: string | null;
  granted_at: string | null;
  expires_at: string | null;
  responsible_id: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type NitAssetDetail = NitAsset & { public_links: NitPublicLink[] };

export type NitDashboard = {
  disclosure_total: number;
  disclosures_by_status: Record<string, number>;
  disclosures_by_area: Record<string, number>;
  documents_total: number;
  assets_total: number;
  assets_by_status: Record<string, number>;
  assets_by_type: Record<string, number>;
  evaluations_total: number;
  pending_evaluations: number;
  disclosure_created_last_30_days: number;
};

// --- NIT F2 (committees, TRL, portfolio) ------------------------------------
export type NitTrl = {
  id: string;
  tenant_id: string;
  disclosure_id: string | null;
  asset_id: string | null;
  level: number;
  previous_level: number | null;
  rationale: string;
  evidence: string | null;
  evaluator_id: string | null;
  created_at: string;
};

export type NitCommittee = {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
  description: string | null;
  status: string;
  quorum: number;
  simple_majority: boolean;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type NitCommitteeMember = {
  id: string;
  committee_id: string;
  name: string;
  user_id: string | null;
  person_id: string | null;
  role_title: string | null;
  kind: "VOTING" | "ADVISORY";
  valid_from: string | null;
  valid_until: string | null;
  active: boolean;
  created_at: string;
};

export type NitCommitteeDetail = NitCommittee & {
  members: NitCommitteeMember[];
};

export type NitMeeting = {
  id: string;
  committee_id: string;
  title: string;
  scheduled_at: string;
  held_at: string | null;
  status: string;
  location: string | null;
  minutes: string | null;
  created_at: string;
};

export type NitAgendaItem = {
  id: string;
  meeting_id: string;
  disclosure_id: string | null;
  asset_id: string | null;
  title: string;
  summary: string | null;
  status: string;
  sort_order: number;
};

export type NitVoteTally = {
  approvals: number;
  rejections: number;
  abstentions: number;
  impeded: number;
  valid: number;
  quorum: number;
  can_approve: boolean;
};

export type NitDecision = {
  id: string;
  item_id: string;
  outcome: "APPROVED" | "REJECTED" | "DEFERRED";
  justification: string | null;
  approvals: number;
  rejections: number;
  abstentions: number;
  impeded: number;
  decided_by_id: string | null;
  decided_at: string;
};

export type NitPortfolioAsset = {
  id: string;
  code: string;
  title: string;
  asset_type: string;
  status: string;
  technology_area: string | null;
  unity_id: string | null;
  deposited_at: string | null;
  granted_at: string | null;
  expires_at: string | null;
  days_to_expiry: number | null;
  trl_level: number | null;
};

export type NitPortfolioView = {
  items: NitPortfolioAsset[];
  total: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  expiring_soon: number;
  expired: number;
};

export type NitDeadlineAlert = {
  asset_id: string;
  code: string;
  title: string;
  expires_at: string;
  days_to_expiry: number;
  severity: string;
};

// --- NIT F3 (technology transfer, contracts) --------------------------------
export type NitOffer = {
  id: string;
  tenant_id: string;
  code: string;
  title: string;
  public_summary: string | null;
  technology_area: string | null;
  maturity: string | null;
  modality: string;
  contact_name: string | null;
  contact_email: string | null;
  conditions: string | null;
  asset_id: string | null;
  unity_id: string | null;
  status: string;
  responsible_id: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type NitInterest = {
  id: string;
  tenant_id: string;
  offer_id: string;
  organization_name: string;
  organization_document: string | null;
  contact_name: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  message: string | null;
  status: string;
  owner_id: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type NitInteraction = {
  id: string;
  interest_id: string;
  kind: string;
  summary: string;
  actor_id: string | null;
  created_at: string;
};

export type NitNegotiation = {
  id: string;
  tenant_id: string;
  interest_id: string | null;
  offer_id: string | null;
  stage: string;
  stage_label: string | null;
  owner_id: string | null;
  next_step: string | null;
  notes: string | null;
  version: number;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type NitNegotiationDetail = NitNegotiation & {
  allowed_next: string[];
  history: {
    id: string;
    from_stage: string | null;
    to_stage: string;
    actor_id: string | null;
    justification: string | null;
    created_at: string;
  }[];
};

export type NitContract = {
  id: string;
  tenant_id: string;
  code: string;
  title: string;
  license_id: string | null;
  parent_contract_id: string | null;
  is_amendment: boolean;
  status: string;
  signed_at: string | null;
  effective_from: string | null;
  effective_until: string | null;
  registered_amount: string | null;
  currency: string;
  conditions: string | null;
  notes: string | null;
  responsible_id: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type NitContractParty = {
  id: string;
  contract_id: string;
  role: string;
  name: string;
  document: string | null;
  email: string | null;
  representative: string | null;
};

export type NitContractDetail = NitContract & { parties: NitContractParty[] };

export type NitObligation = {
  id: string;
  contract_id: string;
  kind: string;
  description: string;
  due_date: string | null;
  status: string;
  responsible_id: string | null;
  evidence: string | null;
  fulfilled_at: string | null;
  created_at: string;
};

export type NitRoyalty = {
  id: string;
  contract_id: string;
  period: string;
  expected_amount: string | null;
  registered_amount: string | null;
  received_amount: string | null;
  currency: string;
  due_date: string | null;
  received_at: string | null;
  notes: string | null;
  created_at: string;
};

export type NitRoyaltySummary = {
  contract_id: string;
  total_expected: string;
  total_registered: string;
  total_received: string;
  pending: string;
  entries: number;
};

export type NitObligationAlert = {
  obligation_id: string;
  contract_id: string;
  contract_code: string;
  description: string;
  due_date: string;
  days_to_due: number;
  severity: string;
  status: string;
};

// --- NIT F4 (projects, startups, incubation, indicators) --------------------
export type NitProject = {
  id: string;
  tenant_id: string;
  code: string;
  title: string;
  description: string | null;
  objective: string | null;
  technology_area: string | null;
  status: string;
  start_date: string | null;
  end_date: string | null;
  unity_id: string | null;
  coordinator_id: string | null;
  notes: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type NitProjectMember = {
  id: string;
  project_id: string;
  name: string;
  role: string;
  person_id: string | null;
  user_id: string | null;
  institution: string | null;
  active: boolean;
  created_at: string;
};

export type NitProjectFunder = {
  id: string;
  project_id: string;
  name: string;
  document: string | null;
  instrument: string | null;
  amount: string | null;
  currency: string;
};

export type NitProjectMilestone = {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  due_date: string | null;
  status: string;
  completed_at: string | null;
  created_at: string;
};

export type NitProjectAssetLink = {
  id: string;
  project_id: string;
  asset_id: string;
  relation: string;
  notes: string | null;
};

export type NitProjectDetail = NitProject & {
  members: NitProjectMember[];
  funders: NitProjectFunder[];
  milestones: NitProjectMilestone[];
  asset_links: NitProjectAssetLink[];
};

export type NitStartup = {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
  description: string | null;
  cnpj: string | null;
  status: string;
  stage: string | null;
  founded_at: string | null;
  project_id: string | null;
  asset_id: string | null;
  responsible_id: string | null;
  notes: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type NitStartupMember = {
  id: string;
  startup_id: string;
  name: string;
  role: string | null;
  person_id: string | null;
  user_id: string | null;
  is_founder: boolean;
};

export type NitProgram = {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
  description: string | null;
  criteria: string | null;
  start_date: string | null;
  end_date: string | null;
  active: boolean;
  created_at: string;
};

export type NitParticipation = {
  id: string;
  program_id: string;
  startup_id: string;
  entry_date: string | null;
  exit_date: string | null;
  exit_status: string | null;
  notes: string | null;
  created_at: string;
};

export type NitIncubationStage = {
  id: string;
  participation_id: string;
  title: string;
  kind: string;
  status: string;
  due_date: string | null;
  completed_at: string | null;
  result: string | null;
  created_at: string;
};

export type NitParticipationDetail = NitParticipation & {
  stages: NitIncubationStage[];
};

export type NitIndicators = {
  disclosure_total: number;
  disclosures_by_status: Record<string, number>;
  disclosures_by_area: Record<string, number>;
  average_triage_days: number | null;
  pending_evaluations: number;
  assets_total: number;
  assets_by_stage: Record<string, number>;
  offers_published: number;
  negotiations_in_progress: number;
  contracts_active: number;
  obligations_due_soon: number;
  projects_total: number;
  projects_active: number;
  startups_total: number;
  startups_incubated: number;
  period_from: string | null;
  period_to: string | null;
};

export type NitFormictReport = {
  disclaimer: string;
  generated_at: string;
  institution: string | null;
  contracts_active: number;
  contracts_total: number;
  total_registered: string;
  total_received: string;
  technologies_offered: number;
  transfers_effective: number;
  projects_active: number;
  startups_supported: number;
};

// --- NIT F5 (notifications, portals, BI, integrations) ----------------------
export type NitNotification = {
  id: string;
  kind: string;
  severity: string;
  title: string;
  body: string | null;
  link: string | null;
  resource_type: string | null;
  resource_id: string | null;
  read_at: string | null;
  created_at: string;
};

export type NitNotificationList = {
  items: NitNotification[];
  page: number;
  page_size: number;
  total: number;
  unread: number;
};

export type NitNotificationPreference = {
  id: string;
  kind: string;
  in_app_enabled: boolean;
  email_enabled: boolean;
};

export type NitEmailMessage = {
  id: string;
  to_email: string;
  subject: string;
  body: string;
  kind: string;
  status: string;
  error: string | null;
  sent_at: string | null;
  created_at: string;
};

export type NitPortalAccess = {
  id: string;
  tenant_id: string;
  portal_kind: string;
  email: string;
  name: string;
  organization: string | null;
  subject_type: string | null;
  subject_id: string | null;
  status: string;
  expires_at: string | null;
  notes: string | null;
  created_at: string;
  access_token?: string;
};

export type NitPortalRequest = {
  id: string;
  access_id: string;
  request_type: string;
  subject: string;
  message: string | null;
  payload: Record<string, unknown> | null;
  status: string;
  triaged_by: string | null;
  triaged_at: string | null;
  created_at: string;
};

export type NitPortalRequestNote = {
  id: string;
  author_id: string | null;
  body: string;
  created_at: string;
};

export type NitPortalRequestDetail = NitPortalRequest & {
  notes: NitPortalRequestNote[];
};

export type NitSavedReport = {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  metrics: string[];
  filters: Record<string, unknown>;
  visibility: string;
  created_at: string;
};

export type NitIntegrationEndpoint = {
  id: string;
  tenant_id: string;
  kind: string;
  name: string;
  description: string | null;
  config: Record<string, unknown>;
  enabled: boolean;
  created_at: string;
};

export type NitIntegrationDelivery = {
  id: string;
  endpoint_id: string;
  event: string;
  payload: Record<string, unknown>;
  status: string;
  error: string | null;
  delivered_at: string | null;
  created_at: string;
};

// --- CRM comercial (oportunidades, propostas, atividades) --------------------
export type OpportunityStage =
  | "NEW"
  | "QUALIFICATION"
  | "PROPOSAL"
  | "SENT"
  | "NEGOTIATION"
  | "WON"
  | "LOST";

export const OPPORTUNITY_STAGE_LABELS: Record<OpportunityStage, string> = {
  NEW: "Novo lead",
  QUALIFICATION: "Qualificação",
  PROPOSAL: "Preparação da proposta",
  SENT: "Proposta enviada",
  NEGOTIATION: "Em negociação",
  WON: "Aprovada",
  LOST: "Perdida",
};

export type ProposalStatus =
  | "DRAFT"
  | "PENDING_SEND"
  | "SENT"
  | "AWAITING_REPLY"
  | "NEGOTIATION"
  | "APPROVED"
  | "REJECTED"
  | "EXPIRED"
  | "CANCELLED";

export const PROPOSAL_STATUS_LABELS: Record<ProposalStatus, string> = {
  DRAFT: "Rascunho",
  PENDING_SEND: "Pendente de envio",
  SENT: "Enviada",
  AWAITING_REPLY: "Aguardando retorno",
  NEGOTIATION: "Em negociação",
  APPROVED: "Aprovada",
  REJECTED: "Recusada",
  EXPIRED: "Expirada",
  CANCELLED: "Cancelada",
};

export type ActivityKind = "CALL" | "MEETING" | "EMAIL" | "NOTE" | "TASK" | "OTHER";

export const ACTIVITY_KINDS: ActivityKind[] = [
  "CALL",
  "MEETING",
  "EMAIL",
  "NOTE",
  "TASK",
  "OTHER",
];

export const ACTIVITY_KIND_LABELS: Record<ActivityKind, string> = {
  CALL: "Ligação",
  MEETING: "Reunião",
  EMAIL: "E-mail / contato",
  NOTE: "Anotação",
  TASK: "Tarefa",
  OTHER: "Outro",
};

export type ActivityOutcome = "PENDING" | "DONE" | "NO_ANSWER" | "RESCHEDULED";

export const ACTIVITY_OUTCOME_LABELS: Record<ActivityOutcome, string> = {
  PENDING: "Pendente",
  DONE: "Concluída",
  NO_ANSWER: "Sem resposta",
  RESCHEDULED: "Reagendada",
};

export type ActivitySubjectType = "OPPORTUNITY" | "PROPOSAL" | "CUSTOMER" | "COMPANY";

export type Opportunity = {
  id: string;
  tenant_id: string;
  code: string;
  title: string;
  lead_name: string | null;
  contact_id: string | null;
  customer_id: string | null;
  company_id: string | null;
  owner_id: string | null;
  stage: OpportunityStage;
  source: string | null;
  service_interest: string | null;
  estimated_value: string | null;
  probability: number | null;
  next_action: string | null;
  next_action_at: string | null;
  expected_close_at: string | null;
  lost_reason: string | null;
  notes: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
  customer_name: string | null;
  company_name: string | null;
  contact_name: string | null;
  owner_name: string | null;
  proposal_count: number;
};

export type Proposal = {
  id: string;
  tenant_id: string;
  code: string;
  title: string;
  description: string | null;
  services: string | null;
  opportunity_id: string | null;
  customer_id: string | null;
  owner_id: string | null;
  status: ProposalStatus;
  total_value: string | null;
  valid_until: string | null;
  notes: string | null;
  sent_at: string | null;
  replied_at: string | null;
  decision_at: string | null;
  decision_notes: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
  opportunity_title: string | null;
  customer_name: string | null;
  owner_name: string | null;
  is_overdue: boolean;
};

// --- Assistente (chat) ------------------------------------------------------

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

export type ChatResponse = {
  answer: string;
  sources: string[];
  ai_available: boolean;
  model: string | null;
};

export type ChatStatus = {
  configured: boolean;
  model: string;
  documents: number;
  sections: number;
  message: string;
};


export type CrmActivity = {
  id: string;
  tenant_id: string;
  kind: ActivityKind;
  subject_type: ActivitySubjectType;
  subject_id: string;
  title: string;
  notes: string | null;
  outcome: ActivityOutcome;
  occurred_at: string | null;
  due_at: string | null;
  completed_at: string | null;
  owner_id: string | null;
  created_by: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
  owner_name: string | null;
};

// --- Business dashboard (Visão Geral do negócio) ----------------------------
export type BusinessCounters = {
  active_customers: number;
  total_customers: number;
  new_customers_period: number;
  open_opportunities: number;
  proposals_to_send: number;
  proposals_awaiting_reply: number;
  proposals_approved: number;
  proposals_rejected: number;
  proposals_open: number;
  proposals_overdue: number;
  monitored_marcas: number;
  monitored_patentes: number;
  critical_alerts: number;
  conversion_rate: number | null;
};

export type BusinessPeriod = {
  date_from: string;
  date_to: string;
  months: number;
};

export type EvolutionPoint = {
  label: string;
  new_customers: number;
  proposals_sent: number;
  proposals_approved: number;
  opportunities_won: number;
};

export type FunnelStage = {
  stage: OpportunityStage;
  label: string;
  count: number;
  value: string | null;
};

export type PendingProposalReason =
  | "TO_SEND"
  | "AWAITING_REPLY"
  | "NEAR_DUE"
  | "OVERDUE"
  | "APPROVED_NO_CUSTOMER";

export const PENDING_REASON_LABELS: Record<PendingProposalReason, string> = {
  TO_SEND: "Precisa ser enviada",
  AWAITING_REPLY: "Aguardando retorno",
  NEAR_DUE: "Vence em breve",
  OVERDUE: "Vencida",
  APPROVED_NO_CUSTOMER: "Aprovada: vincular cliente",
};

export type PendingProposal = {
  id: string;
  code: string;
  title: string;
  status: ProposalStatus;
  status_label: string;
  customer_name: string | null;
  opportunity_title: string | null;
  owner_name: string | null;
  total_value: string | null;
  sent_at: string | null;
  valid_until: string | null;
  days_to_due: number | null;
  reason: PendingProposalReason;
};

export type RecentActivityItem = {
  kind: string;
  title: string;
  description: string | null;
  status: string | null;
  at: string;
  link: string | null;
};

export type UpcomingDeadlineItem = {
  domain: "COMMERCIAL" | "PROPRIEDADE_INTELECTUAL" | string;
  title: string;
  subtitle: string | null;
  due_at: string | null;
  days_remaining: number | null;
  tone: string;
  link: string | null;
};

export type BusinessDashboard = {
  generated_at: string;
  scope: string;
  period: BusinessPeriod;
  counters: BusinessCounters;
  evolution: EvolutionPoint[];
  funnel: FunnelStage[];
  pending_proposals: PendingProposal[];
  deadlines: UpcomingDeadlineItem[];
  recent_activity: RecentActivityItem[];
};

