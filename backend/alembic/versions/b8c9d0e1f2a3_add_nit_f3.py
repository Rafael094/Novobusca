"""add NIT phase F3 tables (technology transfer, contracts, royalties)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-09

Additive migration: creates only NEW tables for phase F3. Monetary columns use
``Numeric(18, 2)``. No existing table is altered. The downgrade drops the new
tables in reverse dependency order.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    _offers_and_interests()
    _negotiations()
    _licenses_and_contracts()
    _obligations_and_royalties()


def _money():
    return sa.Numeric(18, 2)


def _ts(name: str):
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def _offers_and_interests() -> None:
    op.create_table(
        "technology_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ip_assets.id", ondelete="SET NULL")
        ),
        sa.Column(
            "unity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("unities.id", ondelete="SET NULL")
        ),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("public_summary", sa.Text()),
        sa.Column("technology_area", sa.String(128)),
        sa.Column("maturity", sa.String(64)),
        sa.Column("modality", sa.String(32), nullable=False, server_default="LICENSING"),
        sa.Column("contact_name", sa.String(255)),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("conditions", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column(
            "responsible_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "code", name="uq_technology_offers_tenant_code"),
    )
    op.create_index("ix_technology_offers_tenant", "technology_offers", ["tenant_id"])
    op.create_index("ix_technology_offers_status", "technology_offers", ["status"])

    op.create_table(
        "expressions_of_interest",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "offer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("technology_offers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("organization_name", sa.String(255), nullable=False),
        sa.Column("organization_document", sa.String(32)),
        sa.Column("contact_name", sa.String(255)),
        sa.Column("contact_email", sa.String(255)),
        sa.Column("contact_phone", sa.String(32)),
        sa.Column("message", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False, server_default="NEW"),
        sa.Column(
            "owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_interest_tenant", "expressions_of_interest", ["tenant_id"])
    op.create_index("ix_interest_offer", "expressions_of_interest", ["offer_id"])
    op.create_index("ix_interest_status", "expressions_of_interest", ["status"])

    op.create_table(
        "interest_interactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "interest_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expressions_of_interest.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        _ts("created_at"),
    )
    op.create_index("ix_interest_interactions_interest", "interest_interactions", ["interest_id", "created_at"])
    op.create_index("ix_interest_interactions_tenant", "interest_interactions", ["tenant_id"])


def _negotiations() -> None:
    op.create_table(
        "negotiations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "interest_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("expressions_of_interest.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "offer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("technology_offers.id", ondelete="SET NULL"),
        ),
        sa.Column("stage", sa.String(24), nullable=False, server_default="NEW"),
        sa.Column(
            "owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("next_step", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_negotiations_tenant", "negotiations", ["tenant_id"])
    op.create_index("ix_negotiations_interest", "negotiations", ["interest_id"])
    op.create_index("ix_negotiations_stage", "negotiations", ["stage"])

    op.create_table(
        "negotiation_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "negotiation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("negotiations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("from_stage", sa.String(24)),
        sa.Column("to_stage", sa.String(24), nullable=False),
        sa.Column(
            "actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")
        ),
        sa.Column("justification", sa.Text()),
        _ts("created_at"),
    )
    op.create_index("ix_negotiation_history_neg", "negotiation_history", ["negotiation_id", "created_at"])
    op.create_index("ix_negotiation_history_tenant", "negotiation_history", ["tenant_id"])


def _licenses_and_contracts() -> None:
    op.create_table(
        "licenses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("license_type", sa.String(16), nullable=False, server_default="LICENSE"),
        sa.Column(
            "asset_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ip_assets.id", ondelete="SET NULL")
        ),
        sa.Column(
            "negotiation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("negotiations.id", ondelete="SET NULL"),
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("exclusive", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "code", name="uq_licenses_tenant_code"),
    )
    op.create_index("ix_licenses_tenant", "licenses", ["tenant_id"])
    op.create_index("ix_licenses_asset", "licenses", ["asset_id"])

    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "license_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("licenses.id", ondelete="SET NULL")
        ),
        sa.Column(
            "parent_contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contracts.id", ondelete="SET NULL"),
        ),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("is_amendment", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("signed_at", sa.Date()),
        sa.Column("effective_from", sa.Date()),
        sa.Column("effective_until", sa.Date()),
        sa.Column("registered_amount", _money()),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("conditions", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "responsible_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        _ts("created_at"),
        _ts("updated_at"),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "code", name="uq_contracts_tenant_code"),
    )
    op.create_index("ix_contracts_tenant", "contracts", ["tenant_id"])
    op.create_index("ix_contracts_license", "contracts", ["license_id"])
    op.create_index("ix_contracts_status", "contracts", ["status"])

    op.create_table(
        "contract_parties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False, server_default="OTHER"),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("document", sa.String(32)),
        sa.Column("email", sa.String(255)),
        sa.Column("representative", sa.String(255)),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_contract_parties_contract", "contract_parties", ["contract_id"])


def _obligations_and_royalties() -> None:
    op.create_table(
        "contract_obligations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(16), nullable=False, server_default="OTHER"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column(
            "responsible_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("evidence", sa.Text()),
        sa.Column("fulfilled_at", sa.Date()),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_contract_obligations_contract", "contract_obligations", ["contract_id"])
    op.create_index("ix_contract_obligations_due", "contract_obligations", ["due_date"])

    op.create_table(
        "royalties",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "contract_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period", sa.String(16), nullable=False),
        sa.Column("expected_amount", _money()),
        sa.Column("registered_amount", _money()),
        sa.Column("received_amount", _money()),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("due_date", sa.Date()),
        sa.Column("received_at", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_royalties_contract", "royalties", ["contract_id"])
    op.create_index("ix_royalties_period", "royalties", ["period"])


def downgrade() -> None:
    op.drop_table("royalties")
    op.drop_table("contract_obligations")
    op.drop_table("contract_parties")
    op.drop_table("contracts")
    op.drop_table("licenses")
    op.drop_table("negotiation_history")
    op.drop_table("negotiations")
    op.drop_table("interest_interactions")
    op.drop_table("expressions_of_interest")
    op.drop_table("technology_offers")



