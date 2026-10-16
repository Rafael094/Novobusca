"""NIT domain ORM models — communication of invention, confidential documents,
workflow, evaluations and institutional IP assets (phase F1).

Design invariants (see ``docs/ARQUITETURA_ALVO_NIT.md`` §5.3):

* Every tenant-owned entity uses ``UUIDPrimaryKeyMixin`` + ``TimestampMixin`` +
  ``SoftDeleteMixin`` + ``tenant_id``.
* ``InventionDocument.confidentiality_level`` is NOT NULL and defaults to
  ``INTERNAL`` (never ``PUBLIC``) — access additionally requires an explicit ACL
  entry and RBAC.
* Workflow transitions only follow the edges declared in ``WorkflowTransition``
  (never a free-form status field).
* ``IPAssetPublicLink`` links to the GLOBAL public INPI tables (``marcas`` /
  ``patentes``) **without a hard FK**, preserving ``source`` + ``external_ref``
  + ``synced_at`` for provenance.
* Uniqueness: ``(tenant_id, protocol)`` on ``InventionDisclosure`` and
  ``(tenant_id, asset_id, source, external_ref)`` on ``IPAssetPublicLink``.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

# --- Controlled vocabularies (kept as plain strings; extensible via migration) ---

# Confidentiality levels (decision D1 — 4 levels, conservative default INTERNAL).
CONFIDENTIALITY_PUBLIC = "PUBLIC"
CONFIDENTIALITY_INTERNAL = "INTERNAL"
CONFIDENTIALITY_RESTRICTED = "RESTRICTED"
CONFIDENTIALITY_CONFIDENTIAL = "CONFIDENTIAL"
CONFIDENTIALITY_LEVELS: tuple[str, ...] = (
    CONFIDENTIALITY_PUBLIC,
    CONFIDENTIALITY_INTERNAL,
    CONFIDENTIALITY_RESTRICTED,
    CONFIDENTIALITY_CONFIDENTIAL,
)
# Only PUBLIC documents may ever be served without an ACL + audit trail.
NON_PUBLIC_CONFIDENTIALITY: frozenset[str] = frozenset(
    {CONFIDENTIALITY_INTERNAL, CONFIDENTIALITY_RESTRICTED, CONFIDENTIALITY_CONFIDENTIAL}
)

# Workflow states (decision E1 — proposal → triage → evaluation → decision → closed).
WF_PROPOSAL = "PROPOSAL"
WF_TRIAGE = "TRIAGE"
WF_EVALUATION = "EVALUATION"
WF_DECISION = "DECISION"
WF_CLOSED = "CLOSED"
WF_REJECTED = "REJECTED"
WORKFLOW_STATES: tuple[str, ...] = (
    WF_PROPOSAL,
    WF_TRIAGE,
    WF_EVALUATION,
    WF_DECISION,
    WF_CLOSED,
    WF_REJECTED,
)
TERMINAL_STATES: frozenset[str] = frozenset({WF_CLOSED, WF_REJECTED})

# Evaluation kinds (decision E3 — technical/legal/commercial).
EVALUATION_TECHNICAL = "TECHNICAL"
EVALUATION_LEGAL = "LEGAL"
EVALUATION_COMMERCIAL = "COMMERCIAL"
EVALUATION_KINDS: tuple[str, ...] = (
    EVALUATION_TECHNICAL,
    EVALUATION_LEGAL,
    EVALUATION_COMMERCIAL,
)
EVALUATION_OUTCOMES: tuple[str, ...] = ("FAVORABLE", "UNFAVORABLE", "CONDITIONAL", "PENDING")

# IP asset types and statuses.
ASSET_TYPE_PATENT = "PATENT"
ASSET_TYPE_TRADEMARK = "TRADEMARK"
ASSET_TYPE_SOFTWARE = "SOFTWARE"
ASSET_TYPE_CULTIVAR = "CULTIVAR"
ASSET_TYPE_KNOWHOW = "KNOWHOW"
ASSET_TYPE_OTHER = "OTHER"
ASSET_TYPES: tuple[str, ...] = (
    ASSET_TYPE_PATENT,
    ASSET_TYPE_TRADEMARK,
    ASSET_TYPE_SOFTWARE,
    ASSET_TYPE_CULTIVAR,
    ASSET_TYPE_KNOWHOW,
    ASSET_TYPE_OTHER,
)

ASSET_STATUS_PROSPECT = "PROSPECT"
ASSET_STATUS_PROTECTED = "PROTECTED"
ASSET_STATUS_LICENSED = "LICENSED"
ASSET_STATUS_TRANSFERRED = "TRANSFERRED"
ASSET_STATUS_ARCHIVED = "ARCHIVED"
ASSET_STATUSES: tuple[str, ...] = (
    ASSET_STATUS_PROSPECT,
    ASSET_STATUS_PROTECTED,
    ASSET_STATUS_LICENSED,
    ASSET_STATUS_TRANSFERRED,
    ASSET_STATUS_ARCHIVED,
)

# Public-link sources (referencial, no hard FK to the global tables).
PUBLIC_LINK_INPI_MARCA = "INPI_MARCA"
PUBLIC_LINK_INPI_PATENTE = "INPI_PATENTE"
PUBLIC_LINK_SOURCES: tuple[str, ...] = (PUBLIC_LINK_INPI_MARCA, PUBLIC_LINK_INPI_PATENTE)

# Inventor participation kinds.
INVENTOR_INTERNAL = "INTERNAL"
INVENTOR_EXTERNAL = "EXTERNAL"
INVENTOR_KINDS: tuple[str, ...] = (INVENTOR_INTERNAL, INVENTOR_EXTERNAL)

# ACL subject kinds and permission levels.
ACL_SUBJECT_USER = "USER"
ACL_SUBJECT_ROLE = "ROLE"
ACL_SUBJECT_UNITY = "UNITY"
ACL_SUBJECT_KINDS: tuple[str, ...] = (ACL_SUBJECT_USER, ACL_SUBJECT_ROLE, ACL_SUBJECT_UNITY)

ACL_READ = "READ"
ACL_WRITE = "WRITE"
ACL_MANAGE = "MANAGE"
ACL_PERMISSIONS: tuple[str, ...] = (ACL_READ, ACL_WRITE, ACL_MANAGE)


class InventionDisclosure(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Comunicação de invenção — the pre-deposit record submitted by a researcher.

    The owning tenant is ALWAYS derived from the authenticated user's access
    context, never from the request body. ``protocol`` is unique per tenant and
    generated transactionally by ``services/protocol.py``.
    """

    __tablename__ = "invention_disclosures"
    __table_args__ = (
        UniqueConstraint("tenant_id", "protocol", name="uq_disclosures_tenant_protocol"),
        Index("ix_disclosures_tenant", "tenant_id"),
        Index("ix_disclosures_unity", "unity_id"),
        Index("ix_disclosures_status", "status"),
        Index("ix_disclosures_tenant_created", "tenant_id", "created_at"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    unity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("unities.id", ondelete="SET NULL")
    )
    protocol: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)
    technology_area: Mapped[str | None] = mapped_column(String(128))
    keywords: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default=WF_PROPOSAL, nullable=False)
    confidentiality_level: Mapped[str] = mapped_column(
        String(32), default=CONFIDENTIALITY_INTERNAL, nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    inventors: Mapped[list["DisclosureInventor"]] = relationship(
        back_populates="disclosure", cascade="all, delete-orphan"
    )
    documents: Mapped[list["InventionDocument"]] = relationship(
        back_populates="disclosure"
    )
    workflow: Mapped["WorkflowInstance | None"] = relationship(
        back_populates="disclosure", uselist=False
    )
    evaluations: Mapped[list["Evaluation"]] = relationship(back_populates="disclosure")
    assets: Mapped[list["IPAsset"]] = relationship(back_populates="disclosure")


class DisclosureInventor(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Inventor (internal or external) attached to a disclosure.

    External inventors may exist without a login account (``person_id`` /
    ``user_id`` optional) — decision P3.
    """

    __tablename__ = "disclosure_inventors"
    __table_args__ = (
        Index("ix_disclosure_inventors_disclosure", "disclosure_id"),
        Index("ix_disclosure_inventors_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    disclosure_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("invention_disclosures.id", ondelete="CASCADE"),
        nullable=False,
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), default=INVENTOR_INTERNAL, nullable=False)
    document: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(255))
    institution: Mapped[str | None] = mapped_column(String(255))
    share_percent: Mapped[int | None] = mapped_column(Integer)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    disclosure: Mapped["InventionDisclosure"] = relationship(back_populates="inventors")


class InventionDocument(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A confidential document attached to a disclosure/asset dossier.

    * ``storage_key`` is an OPAQUE physical key generated by the storage service
      (``documents/{tenant_id}/{document_id}``) — the original filename is kept
      ONLY in ``original_filename`` (display) and never used as a path, which
      removes path-traversal and overwrite risks.
    * ``confidentiality_level`` is NOT NULL; the column default is ``INTERNAL``
      so a document is never accidentally public.
    * ``checksum_sha256`` + ``size_bytes`` + ``mime_type`` are computed by the
      server from the real bytes (never trusted from the client).
    """

    __tablename__ = "invention_documents"
    __table_args__ = (
        Index("ix_invention_documents_tenant", "tenant_id"),
        Index("ix_invention_documents_disclosure", "disclosure_id"),
        Index("ix_invention_documents_asset", "asset_id"),
        UniqueConstraint("storage_key", name="uq_invention_documents_storage_key"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    disclosure_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invention_disclosures.id", ondelete="CASCADE")
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ip_assets.id", ondelete="CASCADE")
    )
    uploaded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    confidentiality_level: Mapped[str] = mapped_column(
        String(32), default=CONFIDENTIALITY_INTERNAL, nullable=False
    )
    title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    # Malware scan state (decision D3): PENDING / CLEAN / INFECTED / SKIPPED.
    scan_status: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False)
    scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Retention/legal-hold markers (decision D4) — informational in F1.
    retain_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    disclosure: Mapped["InventionDisclosure | None"] = relationship(
        back_populates="documents"
    )
    asset: Mapped["IPAsset | None"] = relationship(back_populates="documents")
    acls: Mapped[list["DocumentAcl"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentAcl(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Explicit ACL entry granting access to a document.

    The subject is one of: a user, a role code, or a unity. Access is granted ONLY
    when (a) the caller passes the RBAC permission check AND (b) an ACL entry
    matches the caller (directly, via a role, or via a unity). A non-PUBLIC
    document without ACL is accessible to no one but the tenant's NIT managers.
    """

    __tablename__ = "document_acls"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "subject_kind",
            "subject_id",
            name="uq_document_acl_subject",
        ),
        Index("ix_document_acls_document", "document_id"),
        Index("ix_document_acls_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("invention_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    subject_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    # User id / unity id (UUID) or role code (string), depending on subject_kind.
    subject_id: Mapped[str] = mapped_column(String(64), nullable=False)
    permission: Mapped[str] = mapped_column(String(16), default=ACL_READ, nullable=False)
    granted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    document: Mapped["InventionDocument"] = relationship(back_populates="acls")


class WorkflowState(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A workflow state, configurable per tenant (decision E2).

    ``code`` is unique per tenant (e.g. ``PROPOSAL``). ``is_initial`` marks the
    state a new disclosure starts in; ``is_terminal`` marks end states.
    """

    __tablename__ = "workflow_states"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_workflow_states_tenant_code"),
        Index("ix_workflow_states_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_initial: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WorkflowTransition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A permitted edge between two workflow states for a tenant.

    A transition MAY require a specific permission (``required_permission`` — a
    code from ``constants.PERMISSIONS``) and/or a specific role
    (``required_role_code``). When both are null anyone with the workflow
    sub-permission may move the case (used only for non-sensitive steps). The
    server NEVER infers authority: an undeclared edge is rejected.
    """

    __tablename__ = "workflow_transitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "from_state",
            "to_state",
            name="uq_workflow_transitions_edge",
        ),
        Index("ix_workflow_transitions_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    from_state: Mapped[str] = mapped_column(String(32), nullable=False)
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    required_permission: Mapped[str | None] = mapped_column(String(64))
    required_role_code: Mapped[str | None] = mapped_column(String(64))
    # Whether a justification/comment is mandatory for this edge.
    requires_justification: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WorkflowInstance(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Live workflow state of a disclosure (1:1 with the disclosure).

    ``version`` implements optimistic concurrency: a transition must present the
    version it read; a mismatch yields 409, preventing duplicate/lost updates.
    """

    __tablename__ = "workflow_instances"
    __table_args__ = (
        UniqueConstraint("disclosure_id", name="uq_workflow_instances_disclosure"),
        Index("ix_workflow_instances_tenant", "tenant_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    disclosure_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("invention_disclosures.id", ondelete="CASCADE"),
        nullable=False,
    )
    current_state: Mapped[str] = mapped_column(
        String(32), default=WF_PROPOSAL, nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    disclosure: Mapped["InventionDisclosure"] = relationship(back_populates="workflow")
    history: Mapped[list["WorkflowHistory"]] = relationship(
        back_populates="instance", cascade="all, delete-orphan"
    )


class WorkflowHistory(UUIDPrimaryKeyMixin, Base):
    """Immutable, append-only record of every workflow transition.

    The row is never updated or deleted by the application (no soft-delete, no
    ``updated_at``): it is the audit trail of the process.
    """

    __tablename__ = "workflow_history"
    __table_args__ = (
        Index("ix_workflow_history_instance", "instance_id", "created_at"),
        Index("ix_workflow_history_tenant", "tenant_id"),
        Index("ix_workflow_history_disclosure", "disclosure_id"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    instance_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workflow_instances.id", ondelete="CASCADE"),
        nullable=False,
    )
    disclosure_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("invention_disclosures.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_state: Mapped[str | None] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    justification: Mapped[str | None] = mapped_column(Text)
    # Snapshot of the instance version AFTER this transition (1-based).
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    instance: Mapped["WorkflowInstance"] = relationship(back_populates="history")


class Evaluation(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """A structured parecer (technical/legal/commercial) on a disclosure.

    Restricted to the assignee, NIT evaluators and managers by RBAC; the
    ``outcome`` field records the evaluator's recommendation, not the final
    institutional decision (that is a workflow transition).
    """

    __tablename__ = "evaluations"
    __table_args__ = (
        Index("ix_evaluations_tenant", "tenant_id"),
        Index("ix_evaluations_disclosure", "disclosure_id"),
        Index("ix_evaluations_kind", "kind"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    disclosure_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("invention_disclosures.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), default=EVALUATION_TECHNICAL, nullable=False)
    evaluator_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    outcome: Mapped[str] = mapped_column(String(16), default="PENDING", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    criteria: Mapped[str | None] = mapped_column(Text)
    technological_potential: Mapped[str | None] = mapped_column(Text)
    market_potential: Mapped[str | None] = mapped_column(Text)
    risks: Mapped[str | None] = mapped_column(Text)
    recommendations: Mapped[str | None] = mapped_column(Text)
    # TRL/maturity is recorded from F2 onward; kept nullable and never auto-filled.
    trl_level: Mapped[int | None] = mapped_column(Integer)
    confidentiality_level: Mapped[str] = mapped_column(
        String(32), default=CONFIDENTIALITY_INTERNAL, nullable=False
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    disclosure: Mapped["InventionDisclosure"] = relationship(back_populates="evaluations")


class IPAsset(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    """Institutional IP asset — the tenant's internal, editable portfolio item.

    Distinct from the public INPI record (global, read-only). The origin
    disclosure is OPTIONAL (decision I1): an asset may exist without one.
    """

    __tablename__ = "ip_assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_ip_assets_tenant_code"),
        Index("ix_ip_assets_tenant", "tenant_id"),
        Index("ix_ip_assets_unity", "unity_id"),
        Index("ix_ip_assets_type", "asset_type"),
        Index("ix_ip_assets_status", "status"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    unity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("unities.id", ondelete="SET NULL")
    )
    disclosure_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("invention_disclosures.id", ondelete="SET NULL")
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    asset_type: Mapped[str] = mapped_column(String(16), default=ASSET_TYPE_OTHER, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=ASSET_STATUS_PROSPECT, nullable=False)
    technology_area: Mapped[str | None] = mapped_column(String(128))
    confidentiality_level: Mapped[str] = mapped_column(
        String(32), default=CONFIDENTIALITY_INTERNAL, nullable=False
    )
    # Free-form operational dates kept nullable (no invented legal deadlines).
    deposited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    responsible_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    disclosure: Mapped["InventionDisclosure | None"] = relationship(back_populates="assets")
    documents: Mapped[list["InventionDocument"]] = relationship(back_populates="asset")
    public_links: Mapped[list["IPAssetPublicLink"]] = relationship(
        back_populates="asset", cascade="all, delete-orphan"
    )


class IPAssetPublicLink(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Referential link from an internal asset to a GLOBAL public INPI record.

    NO hard FK is used (the ``marcas``/``patentes`` tables are global, imported
    and may be reimported). Provenance is preserved via ``source`` +
    ``external_ref`` (the INPI ``codigo_interno``) + ``synced_at``.
    """

    __tablename__ = "ip_asset_public_links"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "asset_id",
            "source",
            "external_ref",
            name="uq_ip_asset_public_links_target",
        ),
        Index("ix_ip_asset_public_links_asset", "asset_id"),
        Index("ix_ip_asset_public_links_tenant", "tenant_id"),
        Index("ix_ip_asset_public_links_ref", "source", "external_ref"),
    )

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("ip_assets.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    external_ref: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str | None] = mapped_column(String(255))
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    asset: Mapped["IPAsset"] = relationship(back_populates="public_links")






