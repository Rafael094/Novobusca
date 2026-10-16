"""add NIT phase F2 tables (committees, votes, decisions, TRL)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-09

Additive migration: creates only NEW tables for phase F2. No existing table is
altered. The downgrade drops them in reverse dependency order.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _trl()
    _committees()
    _meetings()
    _votes_decisions()


def _trl() -> None:
    op.create_table(
        "trl_history",
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
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("previous_level", sa.Integer()),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text()),
        sa.Column(
            "evaluator_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_trl_history_tenant", "trl_history", ["tenant_id"])
    op.create_index("ix_trl_history_disclosure", "trl_history", ["disclosure_id"])
    op.create_index("ix_trl_history_asset", "trl_history", ["asset_id"])


def _committees() -> None:
    op.create_table(
        "committees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("quorum", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("simple_majority", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "code", name="uq_committees_tenant_code"),
    )
    op.create_index("ix_committees_tenant", "committees", ["tenant_id"])

    op.create_table(
        "committee_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "committee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("committees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column(
            "person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("people.id", ondelete="SET NULL")
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("role_title", sa.String(128)),
        sa.Column("kind", sa.String(16), nullable=False, server_default="VOTING"),
        sa.Column("valid_from", sa.DateTime(timezone=True)),
        sa.Column("valid_until", sa.DateTime(timezone=True)),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_committee_members_committee", "committee_members", ["committee_id"])
    op.create_index("ix_committee_members_user", "committee_members", ["user_id"])


def _meetings() -> None:
    op.create_table(
        "committee_meetings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "committee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("committees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("held_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False, server_default="SCHEDULED"),
        sa.Column("location", sa.String(255)),
        sa.Column("minutes", sa.Text()),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_committee_meetings_committee", "committee_meetings", ["committee_id"])
    op.create_index("ix_committee_meetings_tenant", "committee_meetings", ["tenant_id"])
    op.create_index("ix_committee_meetings_date", "committee_meetings", ["scheduled_at"])

    op.create_table(
        "committee_agenda_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "meeting_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("committee_meetings.id", ondelete="CASCADE"),
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
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_committee_agenda_items_meeting", "committee_agenda_items", ["meeting_id"])
    op.create_index("ix_committee_agenda_items_disclosure", "committee_agenda_items", ["disclosure_id"])
    op.create_index("ix_committee_agenda_items_asset", "committee_agenda_items", ["asset_id"])


def _votes_decisions() -> None:
    op.create_table(
        "committee_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("committee_agenda_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "member_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("committee_members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "voter_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("vote", sa.String(16), nullable=False),
        sa.Column("conflict_of_interest", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("item_id", "member_id", name="uq_committee_votes_item_member"),
    )
    op.create_index("ix_committee_votes_item", "committee_votes", ["item_id"])
    op.create_index("ix_committee_votes_tenant", "committee_votes", ["tenant_id"])

    op.create_table(
        "committee_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("committee_agenda_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("justification", sa.Text()),
        sa.Column("approvals", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rejections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("abstentions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("impeded", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "decided_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("item_id", name="uq_committee_decisions_item"),
    )
    op.create_index("ix_committee_decisions_tenant", "committee_decisions", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("committee_decisions")
    op.drop_table("committee_votes")
    op.drop_table("committee_agenda_items")
    op.drop_table("committee_meetings")
    op.drop_table("committee_members")
    op.drop_table("committees")
    op.drop_table("trl_history")


