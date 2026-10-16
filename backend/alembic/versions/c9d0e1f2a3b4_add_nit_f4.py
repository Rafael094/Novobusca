"""add NIT phase F4 tables (projects, startups, incubation)

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-10-09

Additive migration for phase F4. Creates only NEW tables; no existing table is
altered. Monetary columns use ``Numeric(18, 2)``. Downgrade drops in reverse
dependency order.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def _ts(name: str):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    _projects()
    _startups()
    _incubation()


def _tenant_fk():
    return sa.Column(
        "tenant_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )


def _projects() -> None:
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column(
            "unity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("unities.id", ondelete="SET NULL")
        ),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("objective", sa.Text()),
        sa.Column("technology_area", sa.String(128)),
        sa.Column("status", sa.String(16), nullable=False, server_default="PLANNED"),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column(
            "coordinator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("notes", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "code", name="uq_projects_tenant_code"),
    )
    op.create_index("ix_projects_tenant", "projects", ["tenant_id"])
    op.create_index("ix_projects_status", "projects", ["status"])
    op.create_index("ix_projects_unity", "projects", ["unity_id"])

    op.create_table(
        "project_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("people.id", ondelete="SET NULL")
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(24), nullable=False, server_default="RESEARCHER"),
        sa.Column("institution", sa.String(255)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_project_members_project", "project_members", ["project_id"])

    op.create_table(
        "project_funders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("document", sa.String(32)),
        sa.Column("instrument", sa.String(128)),
        sa.Column("amount", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_project_funders_project", "project_funders", ["project_id"])

    op.create_table(
        "project_milestones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("due_date", sa.Date()),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("completed_at", sa.Date()),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_project_milestones_project", "project_milestones", ["project_id"])
    op.create_index("ix_project_milestones_due", "project_milestones", ["due_date"])

    op.create_table(
        "project_asset_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("ip_assets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relation", sa.String(16), nullable=False, server_default="RESULT"),
        sa.Column("notes", sa.Text()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("project_id", "asset_id", name="uq_project_asset_links_pair"),
    )
    op.create_index("ix_project_asset_links_project", "project_asset_links", ["project_id"])
    op.create_index("ix_project_asset_links_asset", "project_asset_links", ["asset_id"])


def _startups() -> None:
    op.create_table(
        "startups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("cnpj", sa.String(18)),
        sa.Column("status", sa.String(16), nullable=False, server_default="IDEATION"),
        sa.Column("stage", sa.String(64)),
        sa.Column("founded_at", sa.Date()),
        sa.Column(
            "project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="SET NULL")
        ),
        sa.Column(
            "asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ip_assets.id", ondelete="SET NULL")
        ),
        sa.Column(
            "responsible_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("notes", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "code", name="uq_startups_tenant_code"),
    )
    op.create_index("ix_startups_tenant", "startups", ["tenant_id"])
    op.create_index("ix_startups_status", "startups", ["status"])

    op.create_table(
        "startup_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column(
            "startup_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("startups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("people.id", ondelete="SET NULL")
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(64)),
        sa.Column("is_founder", sa.Boolean(), nullable=False, server_default=sa.false()),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_startup_members_startup", "startup_members", ["startup_id"])


def _incubation() -> None:
    op.create_table(
        "incubation_programs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("criteria", sa.Text()),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "code", name="uq_incubation_programs_tenant_code"),
    )
    op.create_index("ix_incubation_programs_tenant", "incubation_programs", ["tenant_id"])

    op.create_table(
        "incubation_participations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column(
            "program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incubation_programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "startup_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("startups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("entry_date", sa.Date()),
        sa.Column("exit_date", sa.Date()),
        sa.Column("exit_status", sa.String(64)),
        sa.Column("notes", sa.Text()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint(
            "program_id", "startup_id", name="uq_incubation_participations_pair"
        ),
    )
    op.create_index("ix_incubation_participations_program", "incubation_participations", ["program_id"])
    op.create_index("ix_incubation_participations_startup", "incubation_participations", ["startup_id"])

    op.create_table(
        "incubation_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        _tenant_fk(),
        sa.Column(
            "participation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("incubation_participations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False, server_default="MENTORING"),
        sa.Column("status", sa.String(16), nullable=False, server_default="PLANNED"),
        sa.Column("due_date", sa.Date()),
        sa.Column("completed_at", sa.Date()),
        sa.Column("result", sa.Text()),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_incubation_stages_participation", "incubation_stages", ["participation_id"])


def downgrade() -> None:
    op.drop_table("incubation_stages")
    op.drop_table("incubation_participations")
    op.drop_table("incubation_programs")
    op.drop_table("startup_members")
    op.drop_table("startups")
    op.drop_table("project_asset_links")
    op.drop_table("project_milestones")
    op.drop_table("project_funders")
    op.drop_table("project_members")
    op.drop_table("projects")


