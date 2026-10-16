"""add NIT domain tables (disclosures, documents, workflow, assets)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-09

Additive migration for phase F1. Creates ONLY new tables (+ their indexes and
constraints); no existing table is altered, so the current data and the public
INPI tables are untouched. The downgrade drops the new tables in reverse
dependency order.

Tables:
  * ``invention_disclosures`` + ``disclosure_inventors``
  * ``invention_documents`` + ``document_acls``
  * ``workflow_states`` + ``workflow_transitions`` + ``workflow_instances`` +
    ``workflow_history``
  * ``evaluations``
  * ``ip_assets`` + ``ip_asset_public_links``
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _disclosures()
    _assets()
    _documents()
    _workflow()
    _evaluations()


def _disclosures() -> None:
    op.create_table(
        "invention_disclosures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("unities.id", ondelete="SET NULL"),
        ),
        sa.Column("protocol", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("context", sa.Text()),
        sa.Column("technology_area", sa.String(128)),
        sa.Column("keywords", sa.String(512)),
        sa.Column("status", sa.String(32), nullable=False, server_default="PROPOSAL"),
        sa.Column(
            "confidentiality_level",
            sa.String(32),
            nullable=False,
            server_default="INTERNAL",
        ),
        sa.Column(
            "submitted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "submitted_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "responsible_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "protocol", name="uq_disclosures_tenant_protocol"),
    )
    op.create_index("ix_disclosures_tenant", "invention_disclosures", ["tenant_id"])
    op.create_index("ix_disclosures_unity", "invention_disclosures", ["unity_id"])
    op.create_index("ix_disclosures_status", "invention_disclosures", ["status"])
    op.create_index(
        "ix_disclosures_tenant_created", "invention_disclosures", ["tenant_id", "created_at"]
    )

    op.create_table(
        "disclosure_inventors",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "disclosure_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invention_disclosures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("people.id", ondelete="SET NULL")
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="INTERNAL"),
        sa.Column("document", sa.String(32)),
        sa.Column("email", sa.String(255)),
        sa.Column("institution", sa.String(255)),
        sa.Column("share_percent", sa.Integer()),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_disclosure_inventors_disclosure", "disclosure_inventors", ["disclosure_id"])
    op.create_index("ix_disclosure_inventors_tenant", "disclosure_inventors", ["tenant_id"])


def _documents() -> None:
    op.create_table(
        "invention_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "disclosure_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invention_disclosures.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ip_assets.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "uploaded_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column(
            "confidentiality_level",
            sa.String(32),
            nullable=False,
            server_default="INTERNAL",
        ),
        sa.Column("title", sa.String(255)),
        sa.Column("description", sa.Text()),
        sa.Column("scan_status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("scanned_at", sa.DateTime(timezone=True)),
        sa.Column("retain_until", sa.DateTime(timezone=True)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("storage_key", name="uq_invention_documents_storage_key"),
    )
    op.create_index("ix_invention_documents_tenant", "invention_documents", ["tenant_id"])
    op.create_index("ix_invention_documents_disclosure", "invention_documents", ["disclosure_id"])
    op.create_index("ix_invention_documents_asset", "invention_documents", ["asset_id"])

    op.create_table(
        "document_acls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invention_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("subject_kind", sa.String(16), nullable=False),
        sa.Column("subject_id", sa.String(64), nullable=False),
        sa.Column("permission", sa.String(16), nullable=False, server_default="READ"),
        sa.Column(
            "granted_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "document_id", "subject_kind", "subject_id", name="uq_document_acl_subject"
        ),
    )
    op.create_index("ix_document_acls_document", "document_acls", ["document_id"])
    op.create_index("ix_document_acls_tenant", "document_acls", ["tenant_id"])


def _workflow() -> None:
    op.create_table(
        "workflow_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_initial", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "code", name="uq_workflow_states_tenant_code"),
    )
    op.create_index("ix_workflow_states_tenant", "workflow_states", ["tenant_id"])

    op.create_table(
        "workflow_transitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_state", sa.String(32), nullable=False),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("required_permission", sa.String(64)),
        sa.Column("required_role_code", sa.String(64)),
        sa.Column(
            "requires_justification", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id", "from_state", "to_state", name="uq_workflow_transitions_edge"
        ),
    )
    op.create_index("ix_workflow_transitions_tenant", "workflow_transitions", ["tenant_id"])

    op.create_table(
        "workflow_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "disclosure_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invention_disclosures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("current_state", sa.String(32), nullable=False, server_default="PROPOSAL"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("disclosure_id", name="uq_workflow_instances_disclosure"),
    )
    op.create_index("ix_workflow_instances_tenant", "workflow_instances", ["tenant_id"])

    op.create_table(
        "workflow_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "instance_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_instances.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "disclosure_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invention_disclosures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_state", sa.String(32)),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column(
            "actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("justification", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_workflow_history_instance", "workflow_history", ["instance_id", "created_at"])
    op.create_index("ix_workflow_history_tenant", "workflow_history", ["tenant_id"])
    op.create_index("ix_workflow_history_disclosure", "workflow_history", ["disclosure_id"])


def _evaluations() -> None:
    op.create_table(
        "evaluations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "disclosure_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invention_disclosures.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False, server_default="TECHNICAL"),
        sa.Column(
            "evaluator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("outcome", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("summary", sa.Text()),
        sa.Column("criteria", sa.Text()),
        sa.Column("technological_potential", sa.Text()),
        sa.Column("market_potential", sa.Text()),
        sa.Column("risks", sa.Text()),
        sa.Column("recommendations", sa.Text()),
        sa.Column("trl_level", sa.Integer()),
        sa.Column(
            "confidentiality_level",
            sa.String(32),
            nullable=False,
            server_default="INTERNAL",
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_evaluations_tenant", "evaluations", ["tenant_id"])
    op.create_index("ix_evaluations_disclosure", "evaluations", ["disclosure_id"])
    op.create_index("ix_evaluations_kind", "evaluations", ["kind"])


def _assets() -> None:
    op.create_table(
        "ip_assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "unity_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("unities.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "disclosure_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invention_disclosures.id", ondelete="SET NULL"),
        ),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("asset_type", sa.String(16), nullable=False, server_default="OTHER"),
        sa.Column("status", sa.String(16), nullable=False, server_default="PROSPECT"),
        sa.Column("technology_area", sa.String(128)),
        sa.Column(
            "confidentiality_level",
            sa.String(32),
            nullable=False,
            server_default="INTERNAL",
        ),
        sa.Column("deposited_at", sa.DateTime(timezone=True)),
        sa.Column("granted_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column(
            "responsible_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "code", name="uq_ip_assets_tenant_code"),
    )
    op.create_index("ix_ip_assets_tenant", "ip_assets", ["tenant_id"])
    op.create_index("ix_ip_assets_unity", "ip_assets", ["unity_id"])
    op.create_index("ix_ip_assets_type", "ip_assets", ["asset_type"])
    op.create_index("ix_ip_assets_status", "ip_assets", ["status"])

    op.create_table(
        "ip_asset_public_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ip_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("external_ref", sa.String(64), nullable=False),
        sa.Column("label", sa.String(255)),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "tenant_id",
            "asset_id",
            "source",
            "external_ref",
            name="uq_ip_asset_public_links_target",
        ),
    )
    op.create_index("ix_ip_asset_public_links_asset", "ip_asset_public_links", ["asset_id"])
    op.create_index("ix_ip_asset_public_links_tenant", "ip_asset_public_links", ["tenant_id"])
    op.create_index(
        "ix_ip_asset_public_links_ref", "ip_asset_public_links", ["source", "external_ref"]
    )


def downgrade() -> None:
    # Reverse dependency order: children before parents. ``invention_documents``
    # references BOTH ``invention_disclosures`` and ``ip_assets``, so it must be
    # dropped before ``ip_assets``.
    op.drop_table("ip_asset_public_links")
    op.drop_table("document_acls")
    op.drop_table("invention_documents")
    op.drop_table("ip_assets")
    op.drop_table("evaluations")
    op.drop_table("workflow_history")
    op.drop_table("workflow_instances")
    op.drop_table("workflow_transitions")
    op.drop_table("workflow_states")
    op.drop_table("disclosure_inventors")
    op.drop_table("invention_disclosures")






