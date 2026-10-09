"""add companies, customers and people tables + default tenant for admin

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-07

Introduces the tenant-scoped CRM entities (``companies``, ``customers``,
``people``) and performs the multi-tenancy data migration:

  * ensures a default tenant exists (name from ``DEFAULT_TENANT_NAME``);
  * links every user still without a tenant (e.g. the pre-existing master admin)
    to it, so isolation rules hold without breaking existing access;
  * enables every active module for the default tenant;
  * grants the admin a ``SUPER_ADMIN`` role (all permissions) so no privilege is
    lost -- plus a fallback grant of every permission directly if the role is
    absent (fresh databases seeded before this migration).

The data step is idempotent and safe to re-run.
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

DEFAULT_TENANT = os.environ.get("DEFAULT_TENANT_NAME", "Matriz")


def upgrade() -> None:
    _create_companies()
    _create_people()
    _create_customers()
    _migrate_default_tenant()


def _create_companies() -> None:
    op.create_table(
        "companies",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("razao_social", sa.String(length=255), nullable=False),
        sa.Column("nome_fantasia", sa.String(length=255), nullable=True),
        sa.Column("cnpj", sa.String(length=18), nullable=True),
        sa.Column("inscricao_estadual", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("address_line", sa.String(length=255), nullable=True),
        sa.Column("address_number", sa.String(length=32), nullable=True),
        sa.Column("address_complement", sa.String(length=128), nullable=True),
        sa.Column("district", sa.String(length=128), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("zip_code", sa.String(length=16), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "cnpj", name="uq_companies_tenant_cnpj"),
    )
    op.create_index("ix_companies_tenant", "companies", ["tenant_id"], unique=False)
    op.create_index("ix_companies_razao_social", "companies", ["razao_social"], unique=False)


def _create_people() -> None:
    op.create_table(
        "people",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("document", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("job_title", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "document", name="uq_people_tenant_document"),
    )
    op.create_index("ix_people_tenant", "people", ["tenant_id"], unique=False)
    op.create_index("ix_people_name", "people", ["name"], unique=False)


def _create_customers() -> None:
    op.create_table(
        "customers",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("person_id", sa.UUID(), nullable=True),
        sa.Column("code", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("document", sa.String(length=32), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_customers_tenant_code"),
    )
    op.create_index("ix_customers_tenant", "customers", ["tenant_id"], unique=False)
    op.create_index("ix_customers_company", "customers", ["company_id"], unique=False)


def _migrate_default_tenant() -> None:
    """Data migration: default tenant + admin linkage + full access."""
    bind = op.get_bind()

    # 1. Ensure a default tenant exists; return its id.
    tenant_id = bind.execute(
        sa.text("SELECT id FROM tenants WHERE name = :n ORDER BY created_at LIMIT 1"),
        {"n": DEFAULT_TENANT},
    ).scalar()
    if tenant_id is None:
        tenant_id = bind.execute(
            sa.text(
                "INSERT INTO tenants (id, name, legal_name, active, created_at, updated_at) "
                "VALUES (gen_random_uuid(), :n, :n, true, now(), now()) RETURNING id"
            ),
            {"n": DEFAULT_TENANT},
        ).scalar()

    # 2. Link every tenant-less user (incl. the pre-existing master admin).
    bind.execute(
        sa.text("UPDATE users SET tenant_id = :t WHERE tenant_id IS NULL"),
        {"t": tenant_id},
    )

    # 3. Enable every active module for the default tenant.
    bind.execute(
        sa.text(
            "INSERT INTO tenant_modules (id, tenant_id, module_id, active, created_at, updated_at) "
            "SELECT gen_random_uuid(), :t, m.id, true, now(), now() "
            "FROM modules m "
            "WHERE m.active = true "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM tenant_modules tm "
            "  WHERE tm.tenant_id = :t AND tm.module_id = m.id)"
        ),
        {"t": tenant_id},
    )

    # 4a. Ensure a SUPER_ADMIN system role exists with every permission.
    super_admin_id = bind.execute(
        sa.text("SELECT id FROM roles WHERE tenant_id IS NULL AND code = 'SUPER_ADMIN'")
    ).scalar()
    if super_admin_id is None:
        super_admin_id = bind.execute(
            sa.text(
                "INSERT INTO roles (id, tenant_id, module_id, name, code, is_system, active, "
                "created_at, updated_at) "
                "VALUES (gen_random_uuid(), NULL, NULL, 'Super Administrador', "
                "'SUPER_ADMIN', true, true, now(), now()) RETURNING id"
            )
        ).scalar()

    bind.execute(
        sa.text(
            "INSERT INTO role_permissions (id, role_id, permission_id, created_at, updated_at) "
            "SELECT gen_random_uuid(), :r, p.id, now(), now() FROM permissions p "
            "WHERE NOT EXISTS ("
            "  SELECT 1 FROM role_permissions rp "
            "  WHERE rp.role_id = :r AND rp.permission_id = p.id)"
        ),
        {"r": super_admin_id},
    )

    # 4b. Grant the SUPER_ADMIN role to every master admin lacking it.
    bind.execute(
        sa.text(
            "INSERT INTO user_roles (id, user_id, role_id, created_at, updated_at) "
            "SELECT gen_random_uuid(), u.id, :r, now(), now() FROM users u "
            "WHERE u.is_master_admin = true "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM user_roles ur "
            "  WHERE ur.user_id = u.id AND ur.role_id = :r)"
        ),
        {"r": super_admin_id},
    )


def downgrade() -> None:
    op.drop_index("ix_customers_company", table_name="customers")
    op.drop_index("ix_customers_tenant", table_name="customers")
    op.drop_table("customers")
    op.drop_index("ix_people_name", table_name="people")
    op.drop_index("ix_people_tenant", table_name="people")
    op.drop_table("people")
    op.drop_index("ix_companies_razao_social", table_name="companies")
    op.drop_index("ix_companies_tenant", table_name="companies")
    op.drop_table("companies")


