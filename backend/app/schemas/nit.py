"""Pydantic schemas for the NIT domain (comunicações de invenção, documentos,
workflow, pareceres e ativos institucionais).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# --- Inventors --------------------------------------------------------------
class InventorBase(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    kind: str = Field(default="INTERNAL", pattern="^(INTERNAL|EXTERNAL)$")
    person_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    document: str | None = Field(default=None, max_length=32)
    email: str | None = Field(default=None, max_length=255)
    institution: str | None = Field(default=None, max_length=255)
    share_percent: int | None = Field(default=None, ge=0, le=100)
    is_primary: bool = False
    notes: str | None = None


class InventorCreate(InventorBase):
    pass


class InventorOut(InventorBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    disclosure_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


# --- Disclosure -------------------------------------------------------------
class DisclosureBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str | None = None
    description: str | None = None
    context: str | None = None
    technology_area: str | None = Field(default=None, max_length=128)
    keywords: str | None = Field(default=None, max_length=512)
    unity_id: uuid.UUID | None = None
    confidentiality_level: str = Field(
        default="INTERNAL", pattern="^(PUBLIC|INTERNAL|RESTRICTED|CONFIDENTIAL)$"
    )


class DisclosureCreate(DisclosureBase):
    """Create payload.

    NOTE: there is intentionally NO ``tenant_id`` — the tenant is derived from the
    authenticated user (never trusted from the client). ``protocol`` is generated
    server-side by ``services/protocol.py``.
    """

    responsible_id: uuid.UUID | None = None
    inventors: list[InventorCreate] = []


class DisclosureUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = None
    description: str | None = None
    context: str | None = None
    technology_area: str | None = None
    keywords: str | None = None
    unity_id: uuid.UUID | None = None
    confidentiality_level: str | None = Field(
        default=None, pattern="^(PUBLIC|INTERNAL|RESTRICTED|CONFIDENTIAL)$"
    )
    responsible_id: uuid.UUID | None = None
    active: bool | None = None


class DisclosureOut(DisclosureBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    protocol: str
    status: str
    submitted_at: datetime
    submitted_by_id: uuid.UUID | None = None
    responsible_id: uuid.UUID | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class DisclosureDetail(DisclosureOut):
    inventors: list[InventorOut] = []


class PaginatedDisclosures(BaseModel):
    items: list[DisclosureOut]
    page: int
    page_size: int
    total: int


# --- Documents --------------------------------------------------------------
class DocumentAclIn(BaseModel):
    subject_kind: str = Field(pattern="^(USER|ROLE|UNITY)$")
    subject_id: str = Field(min_length=1, max_length=64)
    permission: str = Field(default="READ", pattern="^(READ|WRITE|MANAGE)$")


class DocumentAclOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    subject_kind: str
    subject_id: str
    permission: str
    created_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    disclosure_id: uuid.UUID | None = None
    asset_id: uuid.UUID | None = None
    original_filename: str
    mime_type: str
    size_bytes: int
    checksum_sha256: str
    confidentiality_level: str
    title: str | None = None
    description: str | None = None
    scan_status: str
    uploaded_by_id: uuid.UUID | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


class DocumentDetail(DocumentOut):
    acls: list[DocumentAclOut] = []


class PaginatedDocuments(BaseModel):
    items: list[DocumentOut]
    page: int
    page_size: int
    total: int


class DocumentDownloadUrl(BaseModel):
    """Short-lived, authenticated access descriptor (never a permanent public URL)."""

    document_id: uuid.UUID
    download_path: str
    expires_in_seconds: int


# --- Workflow ---------------------------------------------------------------
class WorkflowStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    code: str
    name: str
    description: str | None = None
    sort_order: int
    is_initial: bool
    is_terminal: bool


class WorkflowTransitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    from_state: str
    to_state: str
    name: str
    required_permission: str | None = None
    required_role_code: str | None = None
    requires_justification: bool


class WorkflowHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    from_state: str | None = None
    to_state: str
    actor_id: uuid.UUID | None = None
    justification: str | None = None
    version: int
    created_at: datetime


class WorkflowStatusOut(BaseModel):
    disclosure_id: uuid.UUID
    current_state: str
    current_state_name: str | None = None
    version: int
    is_terminal: bool
    available_transitions: list[WorkflowTransitionOut] = []
    history: list[WorkflowHistoryOut] = []


class TransitionRequest(BaseModel):
    to_state: str = Field(min_length=1, max_length=32)
    justification: str | None = None
    # Optimistic concurrency: the version the client read. Optional but strongly
    # recommended; when omitted the server still guards against terminal states.
    expected_version: int | None = Field(default=None, ge=0)


# --- Evaluations ------------------------------------------------------------
class EvaluationBase(BaseModel):
    kind: str = Field(default="TECHNICAL", pattern="^(TECHNICAL|LEGAL|COMMERCIAL)$")
    outcome: str = Field(
        default="PENDING", pattern="^(FAVORABLE|UNFAVORABLE|CONDITIONAL|PENDING)$"
    )
    summary: str | None = None
    criteria: str | None = None
    technological_potential: str | None = None
    market_potential: str | None = None
    risks: str | None = None
    recommendations: str | None = None
    trl_level: int | None = Field(default=None, ge=1, le=9)
    confidentiality_level: str = Field(
        default="INTERNAL", pattern="^(PUBLIC|INTERNAL|RESTRICTED|CONFIDENTIAL)$"
    )


class EvaluationCreate(EvaluationBase):
    evaluator_id: uuid.UUID | None = None


class EvaluationUpdate(BaseModel):
    outcome: str | None = Field(
        default=None, pattern="^(FAVORABLE|UNFAVORABLE|CONDITIONAL|PENDING)$"
    )
    summary: str | None = None
    criteria: str | None = None
    technological_potential: str | None = None
    market_potential: str | None = None
    risks: str | None = None
    recommendations: str | None = None
    trl_level: int | None = Field(default=None, ge=1, le=9)


class EvaluationOut(EvaluationBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    disclosure_id: uuid.UUID
    evaluator_id: uuid.UUID | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


# --- IP assets --------------------------------------------------------------
class PublicLinkIn(BaseModel):
    source: str = Field(pattern="^(INPI_MARCA|INPI_PATENTE)$")
    external_ref: str = Field(min_length=1, max_length=64)
    label: str | None = Field(default=None, max_length=255)


class PublicLinkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    source: str
    external_ref: str
    label: str | None = None
    synced_at: datetime


class AssetBase(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    asset_type: str = Field(
        default="OTHER",
        pattern="^(PATENT|TRADEMARK|SOFTWARE|CULTIVAR|KNOWHOW|OTHER)$",
    )
    status: str = Field(
        default="PROSPECT",
        pattern="^(PROSPECT|PROTECTED|LICENSED|TRANSFERRED|ARCHIVED)$",
    )
    technology_area: str | None = Field(default=None, max_length=128)
    unity_id: uuid.UUID | None = None
    confidentiality_level: str = Field(
        default="INTERNAL", pattern="^(PUBLIC|INTERNAL|RESTRICTED|CONFIDENTIAL)$"
    )
    deposited_at: datetime | None = None
    granted_at: datetime | None = None
    expires_at: datetime | None = None
    responsible_id: uuid.UUID | None = None


class AssetCreate(AssetBase):
    """Create payload — no ``tenant_id``/``code`` (both generated server-side)."""

    disclosure_id: uuid.UUID | None = None
    public_links: list[PublicLinkIn] = []


class AssetUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    asset_type: str | None = None
    status: str | None = None
    technology_area: str | None = None
    unity_id: uuid.UUID | None = None
    confidentiality_level: str | None = None
    deposited_at: datetime | None = None
    granted_at: datetime | None = None
    expires_at: datetime | None = None
    responsible_id: uuid.UUID | None = None
    active: bool | None = None


class AssetOut(AssetBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    code: str
    disclosure_id: uuid.UUID | None = None
    active: bool
    created_at: datetime
    updated_at: datetime


class AssetDetail(AssetOut):
    public_links: list[PublicLinkOut] = []


class PaginatedAssets(BaseModel):
    items: list[AssetOut]
    page: int
    page_size: int
    total: int


# --- Operational dashboard --------------------------------------------------
class NitDashboard(BaseModel):
    """Counts derived from REAL queries only (no fabricated values)."""

    disclosure_total: int
    disclosures_by_status: dict[str, int]
    disclosures_by_area: dict[str, int]
    documents_total: int
    assets_total: int
    assets_by_status: dict[str, int]
    assets_by_type: dict[str, int]
    evaluations_total: int
    pending_evaluations: int
    disclosure_created_last_30_days: int


