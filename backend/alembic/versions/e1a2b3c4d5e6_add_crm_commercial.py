"""add CRM commercial tables (opportunities, proposals, activities)

Revision ID: e1a2b3c4d5e6
Revises: d0e1f2a3b4c5
Create Date: 2026-10-10

Additive migration for the commercial CRM layer. Creates only NEW tables
(``crm_opportunities``, ``crm_proposals``, ``crm_activities``) and the RBAC
catalogue rows (permissions + resources) needed by them; no existing table is
altered and no demonstration data is inserted.

The new rows are inserted idempotently (``WHERE NOT EXISTS``) so re-running the
migration (or running it on a database already seeded by ``app.seed``) is safe.
Downgrade removes the tables and the permissions/resources introduced here.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e1a2b3c4d5e6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


# --- RBAC additions (module_code, code, name) -------------------------------
NEW_PERMISSIONS: list[tuple[str, str, str]] = [
    ("CLIENTES", "CRM_DASHBOARD_VIEW", "Visualizar o painel comercial (CRM)"),
    ("CLIENTES", "CRM_OPPORTUNITY_VIEW", "Visualizar leads e oportunidades"),
    ("CLIENTES", "CRM_OPPORTUNITY_MANAGE", "Gerenciar leads e oportunidades"),
    ("CLIENTES", "CRM_PROPOSAL_VIEW", "Visualizar propostas comerciais"),
    ("CLIENTES", "CRM_PROPOSAL_MANAGE", "Gerenciar propostas comerciais"),
    ("CLIENTES", "CRM_ACTIVITY_VIEW", "Visualizar atividades e follow-ups"),
    ("CLIENTES", "CRM_ACTIVITY_MANAGE", "Registrar atividades e follow-ups"),
]

# --- RBAC additions (module_code, code, name, description, control) ---------
NEW_RESOURCES: list[tuple[str, str, str, str, bool]] = [
    ("CLIENTES", "clientes:opportunity", "Oportunidades (CRM)",
     "Leads e oportunidades do funil comercial", True),
    ("CLIENTES", "clientes:proposal", "Propostas comerciais",
     "Propostas comerciais e seu ciclo de vida", True),
    ("CLIENTES", "clientes:activity", "Atividades comerciais",
     "Follow-ups e histórico de interações comerciais", True),
    ("CLIENTES", "clientes:crm_dashboard", "Painel comercial",
     "Indicadores comerciais do tenant", False),
]


def _uuid_col(name: str, *, nullable: bool = True):
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def _tenant_fk():
    return sa.Column(
        "tenant_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )


def _base_columns() -> list[sa.Column]:
    """id / created_at / updated_at / deleted_at shared by every CRM table."""
    return [
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    _create_opportunities()
    _create_proposals()
    _create_activities()
    _seed_rbac_catalogue()


def _create_opportunities() -> None:
    op.create_table(
        "crm_opportunities",
        *_base_columns(),
        _tenant_fk(),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("lead_name", sa.String(255), nullable=True),
        _uuid_col("contact_id"),
        _uuid_col("customer_id"),
        _uuid_col("company_id"),
        _uuid_col("owner_id"),
        sa.Column("stage", sa.String(32), nullable=False, server_default="NEW"),
        sa.Column("source", sa.String(32), nullable=True),
        sa.Column("service_interest", sa.String(255), nullable=True),
        sa.Column("estimated_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("probability", sa.Integer(), nullable=True),
        sa.Column("next_action", sa.String(255), nullable=True),
        sa.Column("next_action_at", sa.Date(), nullable=True),
        sa.Column("expected_close_at", sa.Date(), nullable=True),
        sa.Column("lost_reason", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["contact_id"], ["people.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_crm_opportunities_tenant_code"),
    )
    op.create_index("ix_crm_opportunities_tenant", "crm_opportunities", ["tenant_id"])
    op.create_index("ix_crm_opportunities_stage", "crm_opportunities", ["tenant_id", "stage"])
    op.create_index("ix_crm_opportunities_customer", "crm_opportunities", ["customer_id"])
    op.create_index("ix_crm_opportunities_owner", "crm_opportunities", ["owner_id"])


def _create_proposals() -> None:
    op.create_table(
        "crm_proposals",
        *_base_columns(),
        _tenant_fk(),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("services", sa.Text(), nullable=True),
        _uuid_col("opportunity_id"),
        _uuid_col("customer_id"),
        _uuid_col("owner_id"),
        sa.Column("status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("total_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_notes", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["crm_opportunities.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_crm_proposals_tenant_code"),
    )
    op.create_index("ix_crm_proposals_tenant", "crm_proposals", ["tenant_id"])
    op.create_index("ix_crm_proposals_status", "crm_proposals", ["tenant_id", "status"])
    op.create_index("ix_crm_proposals_opportunity", "crm_proposals", ["opportunity_id"])
    op.create_index("ix_crm_proposals_customer", "crm_proposals", ["customer_id"])


def _create_activities() -> None:
    op.create_table(
        "crm_activities",
        *_base_columns(),
        _tenant_fk(),
        sa.Column("kind", sa.String(32), nullable=False, server_default="NOTE"),
        sa.Column("subject_type", sa.String(32), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        _uuid_col("owner_id"),
        _uuid_col("created_by"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_crm_activities_tenant", "crm_activities", ["tenant_id"])
    op.create_index(
        "ix_crm_activities_subject",
        "crm_activities",
        ["tenant_id", "subject_type", "subject_id"],
    )
    op.create_index("ix_crm_activities_due", "crm_activities", ["tenant_id", "due_at"])
    op.create_index("ix_crm_activities_owner", "crm_activities", ["owner_id"])


def _seed_rbac_catalogue() -> None:
    """Insert the new permissions/resources without disturbing existing rows."""
    bind = op.get_bind()

    for module_code, code, name in NEW_PERMISSIONS:
        bind.execute(
            sa.text(
                "INSERT INTO permissions (id, module_id, code, name, created_at, updated_at) "
                "SELECT gen_random_uuid(), m.id, CAST(:code AS varchar), "
                "CAST(:name AS varchar), now(), now() "
                "FROM modules m WHERE m.code = CAST(:module AS varchar) "
                "AND NOT EXISTS (SELECT 1 FROM permissions p "
                "WHERE p.code = CAST(:code AS varchar))"
            ),
            {"code": code, "name": name, "module": module_code},
        )

    for module_code, code, name, description, control in NEW_RESOURCES:
        bind.execute(
            sa.text(
                "INSERT INTO resources "
                "(id, module_id, code, name, description, control_company_unity, "
                " created_at, updated_at) "
                "SELECT gen_random_uuid(), m.id, CAST(:code AS varchar), "
                "CAST(:name AS varchar), CAST(:description AS text), "
                "CAST(:control AS boolean), now(), now() "
                "FROM modules m WHERE m.code = CAST(:module AS varchar) "
                "AND NOT EXISTS (SELECT 1 FROM resources r "
                "WHERE r.code = CAST(:code AS varchar))"
            ),
            {
                "code": code,
                "name": name,
                "description": description,
                "control": control,
                "module": module_code,
            },
        )

    # Grant the new permissions to the system roles that must keep full access.
    # (There is no ``role_resources`` table in this schema — resources are granted
    # through policies, so only role/permission grants are needed here.)
    for role_code in ("SUPER_ADMIN", "TENANT_ADMIN"):
        for _module, code, _name in NEW_PERMISSIONS:
            bind.execute(
                sa.text(
                    "INSERT INTO role_permissions "
                    "(id, role_id, permission_id, created_at, updated_at) "
                    "SELECT gen_random_uuid(), r.id, p.id, now(), now() "
                    "FROM roles r, permissions p "
                    "WHERE r.code = CAST(:role AS varchar) "
                    "AND p.code = CAST(:perm AS varchar) "
                    "AND NOT EXISTS ("
                    "  SELECT 1 FROM role_permissions rp "
                    "  WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
                ),
                {"role": role_code, "perm": code},
            )


def downgrade() -> None:
    bind = op.get_bind()

    # Remove the RBAC catalogue rows introduced by this revision.
    for _module, code, _name in NEW_PERMISSIONS:
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id IN "
                "(SELECT id FROM permissions WHERE code = CAST(:code AS varchar))"
            ),
            {"code": code},
        )
        bind.execute(
            sa.text("DELETE FROM permissions WHERE code = CAST(:code AS varchar)"),
            {"code": code},
        )
    for _module, code, _n, _d, _c in NEW_RESOURCES:
        bind.execute(
            sa.text("DELETE FROM resources WHERE code = CAST(:code AS varchar)"),
            {"code": code},
        )

    op.drop_index("ix_crm_activities_owner", table_name="crm_activities")
    op.drop_index("ix_crm_activities_due", table_name="crm_activities")
    op.drop_index("ix_crm_activities_subject", table_name="crm_activities")
    op.drop_index("ix_crm_activities_tenant", table_name="crm_activities")
    op.drop_table("crm_activities")

    op.drop_index("ix_crm_proposals_customer", table_name="crm_proposals")
    op.drop_index("ix_crm_proposals_opportunity", table_name="crm_proposals")
    op.drop_index("ix_crm_proposals_status", table_name="crm_proposals")
    op.drop_index("ix_crm_proposals_tenant", table_name="crm_proposals")
    op.drop_table("crm_proposals")

    op.drop_index("ix_crm_opportunities_owner", table_name="crm_opportunities")
    op.drop_index("ix_crm_opportunities_customer", table_name="crm_opportunities")
    op.drop_index("ix_crm_opportunities_stage", table_name="crm_opportunities")
    op.drop_index("ix_crm_opportunities_tenant", table_name="crm_opportunities")
    op.drop_table("crm_opportunities")



