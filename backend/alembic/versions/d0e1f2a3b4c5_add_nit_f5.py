"""add NIT phase F5 tables (notifications, portals, BI, integrations)

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-10-10

Additive migration for phase F5. Creates only NEW tables; no existing table is
altered. JSONB columns hold report definitions/outbox payloads (never fabricated
financial values). Downgrade drops in reverse dependency order.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def _ts(name: str):
    return sa.Column(
        name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )


def _tenant_fk():
    return sa.Column(
        "tenant_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )


def _user_fk(name: str = "user_id", ondelete: str = "CASCADE"):
    return sa.Column(
        name,
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete=ondelete),
    )


def upgrade() -> None:
    _notifications()
    _portals()
    _bi()
    _integrations()


def _notifications() -> None:
    op.create_table(
        "nit_notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        _user_fk(),
        sa.Column("kind", sa.String(32), nullable=False, server_default="GENERIC"),
        sa.Column("severity", sa.String(16), nullable=False, server_default="INFO"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("link", sa.String(512)),
        sa.Column("resource_type", sa.String(64)),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_nit_notifications_user", "nit_notifications", ["user_id"])
    op.create_index("ix_nit_notifications_tenant", "nit_notifications", ["tenant_id"])
    op.create_index(
        "ix_nit_notifications_unread", "nit_notifications", ["user_id", "read_at"]
    )

    op.create_table(
        "nit_notification_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        _user_fk(),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("user_id", "kind", name="uq_nit_notif_pref_user_kind"),
    )
    op.create_index("ix_nit_notif_pref_user", "nit_notification_preferences", ["user_id"])

    op.create_table(
        "nit_email_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column("to_email", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="GENERIC"),
        sa.Column("status", sa.String(16), nullable=False, server_default="QUEUED"),
        sa.Column("error", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        _user_fk("created_by", ondelete="SET NULL"),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_nit_email_status", "nit_email_messages", ["status"])
    op.create_index("ix_nit_email_tenant", "nit_email_messages", ["tenant_id"])


def _portals() -> None:
    op.create_table(
        "nit_portal_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column("portal_kind", sa.String(16), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("organization", sa.String(255)),
        sa.Column("subject_type", sa.String(64)),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True)),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("access_token", sa.String(64), nullable=False),
        sa.Column("notes", sa.Text()),
        _user_fk("granted_by", ondelete="SET NULL"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "tenant_id", "portal_kind", "email", name="uq_nit_portal_access_email"
        ),
    )
    op.create_index("ix_nit_portal_access_tenant", "nit_portal_access", ["tenant_id"])
    op.create_index("ix_nit_portal_access_status", "nit_portal_access", ["status"])

    op.create_table(
        "nit_portal_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column(
            "access_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nit_portal_access.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_type", sa.String(32), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("message", sa.Text()),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column("status", sa.String(16), nullable=False, server_default="NEW"),
        _user_fk("triaged_by", ondelete="SET NULL"),
        sa.Column("triaged_at", sa.DateTime(timezone=True)),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_nit_portal_requests_access", "nit_portal_requests", ["access_id"])
    op.create_index("ix_nit_portal_requests_tenant", "nit_portal_requests", ["tenant_id"])
    op.create_index("ix_nit_portal_requests_status", "nit_portal_requests", ["status"])

    op.create_table(
        "nit_portal_request_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nit_portal_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _user_fk("author_id", ondelete="SET NULL"),
        sa.Column("body", sa.Text(), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_nit_portal_notes_request", "nit_portal_request_notes", ["request_id"])


def _bi() -> None:
    op.create_table(
        "nit_saved_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("metrics", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("filters", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("visibility", sa.String(16), nullable=False, server_default="TENANT"),
        _user_fk("created_by", ondelete="SET NULL"),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "name", name="uq_nit_saved_reports_name"),
    )
    op.create_index("ix_nit_saved_reports_tenant", "nit_saved_reports", ["tenant_id"])

    op.create_table(
        "nit_report_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column(
            "report_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nit_saved_reports.id", ondelete="CASCADE"),
            nullable=False,
        ),
        _user_fk("ran_by", ondelete="SET NULL"),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default="{}"),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_nit_report_runs_report", "nit_report_runs", ["report_id"])
    op.create_index("ix_nit_report_runs_tenant", "nit_report_runs", ["tenant_id"])


def _integrations() -> None:
    op.create_table(
        "nit_integration_endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "name", name="uq_nit_integration_name"),
    )
    op.create_index("ix_nit_integration_tenant", "nit_integration_endpoints", ["tenant_id"])
    op.create_index("ix_nit_integration_kind", "nit_integration_endpoints", ["kind"])

    op.create_table(
        "nit_integration_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column(
            "endpoint_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("nit_integration_endpoints.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("error", sa.Text()),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index(
        "ix_nit_integration_deliveries_endpoint",
        "nit_integration_deliveries",
        ["endpoint_id"],
    )
    op.create_index(
        "ix_nit_integration_deliveries_status", "nit_integration_deliveries", ["status"]
    )


def downgrade() -> None:
    op.drop_table("nit_integration_deliveries")
    op.drop_table("nit_integration_endpoints")
    op.drop_table("nit_report_runs")
    op.drop_table("nit_saved_reports")
    op.drop_table("nit_portal_request_notes")
    op.drop_table("nit_portal_requests")
    op.drop_table("nit_portal_access")
    op.drop_table("nit_email_messages")
    op.drop_table("nit_notification_preferences")
    op.drop_table("nit_notifications")


