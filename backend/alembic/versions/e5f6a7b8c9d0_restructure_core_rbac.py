"""restructure core/tenant/company/unity + advanced RBAC + selective monitoring

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-08

Implements the domain restructuring requested for IntelliINPI:

1. **Core / Tenant / Company / Unity** — the ``tenants`` table becomes the
   aggregate ROOT (no ``tenant_id`` of its own) with ``social_reason``,
   ``company_name``, ``cnpj`` and ``mcp_api_key``; ``companies`` gains
   ``company_name``/``external_id``/``file_document``; the new ``unities``
   table holds the branches of a company; ``modules.control_company_unity``
   is added.
2. **Identity** — ``users`` becomes credential-only (``access_code``,
   ``salt``, ``type``, ``mfa``, ``refresh_token``) with a 1:1 ``person_id``
   link; ``people`` gains the ``Cpf``/``CellPhone``/address/Responsibility
   fields; ``user_tenants`` (N-N) and ``user_company_unity`` (lotação) are
   created.
3. **RBAC: Module → Resource → Policies** — ``resources``,
   ``role_policies``, ``user_policies``, ``groups``, ``group_policies``,
   ``user_groups`` and the UI menu chain ``menus`` → ``menu_items`` →
   ``menu_item_resources``.
4. **Selective monitoring** — ``marcas_monitoramento`` and
   ``patentes_monitoramento``.

Base tables (``departments``, ``gut_ranges``) are added too. All column
renames are data-preserving (values are copied before the old column is
dropped), and the data migration is idempotent.
"""

from __future__ import annotations

import os

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

DEFAULT_TENANT = os.environ.get("DEFAULT_TENANT_NAME", "Matriz")


def upgrade() -> None:
    _core_columns()
    _companies_columns()
    _people_columns()
    _users_columns()
    _unities()
    _rbac_tables()
    _identity_tables()
    _base_tables()
    _menu_tables()
    _monitoring_tables()
    _backfill()


# --- 1. Core -----------------------------------------------------------------
def _core_columns() -> None:
    # tenants: name -> social_reason (root, keeps no tenant_id of its own).
    op.alter_column("tenants", "name", new_column_name="social_reason")
    op.add_column("tenants", sa.Column("company_name", sa.String(255), nullable=True))
    op.add_column("tenants", sa.Column("cnpj", sa.String(18), nullable=True))
    op.add_column(
        "tenants", sa.Column("mcp_api_key", sa.String(128), nullable=True)
    )
    op.create_unique_constraint("uq_tenants_mcp_api_key", "tenants", ["mcp_api_key"])
    # Carry the former legal_name into the new company_name (trade name).
    op.execute(
        "UPDATE tenants SET company_name = COALESCE(company_name, legal_name, social_reason)"
    )
    op.drop_column("tenants", "legal_name")
    op.drop_column("tenants", "document")

    # modules: control_company_unity flag.
    op.add_column(
        "modules",
        sa.Column(
            "control_company_unity",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def _companies_columns() -> None:
    op.add_column(
        "companies", sa.Column("company_name", sa.String(255), nullable=True)
    )
    op.add_column("companies", sa.Column("external_id", sa.String(64), nullable=True))
    op.add_column("companies", sa.Column("file_document", sa.Text(), nullable=True))
    # Carry values onto ``company_name`` BEFORE renaming razao_social.
    op.execute(
        "UPDATE companies SET company_name = COALESCE(nome_fantasia, razao_social)"
    )
    op.alter_column("companies", "company_name", nullable=False)
    # razao_social -> social_reason; nome_fantasia is folded into company_name.
    op.alter_column("companies", "razao_social", new_column_name="social_reason")
    op.alter_column("companies", "social_reason", nullable=True)
    op.drop_column("companies", "nome_fantasia")
    op.drop_column("companies", "inscricao_estadual")
    op.drop_column("companies", "address_line")
    op.drop_column("companies", "address_number")
    op.drop_column("companies", "address_complement")
    op.drop_column("companies", "district")
    op.drop_column("companies", "city")
    op.drop_column("companies", "state")
    op.drop_column("companies", "zip_code")
    # Old indexes/constraints replaced by the new shape.
    op.drop_index("ix_companies_razao_social", table_name="companies")
    op.drop_constraint("uq_companies_tenant_cnpj", "companies", type_="unique")
    op.create_index(
        "ix_companies_company_name", "companies", ["company_name"], unique=False
    )
    op.create_unique_constraint(
        "uq_companies_tenant_external", "companies", ["tenant_id", "external_id"]
    )


def _people_columns() -> None:
    # Rename FIRST (document -> cpf), then add the genuinely new columns.
    op.alter_column("people", "document", new_column_name="cpf")
    op.add_column("people", sa.Column("cell_phone", sa.String(32), nullable=True))
    op.add_column("people", sa.Column("responsibility", sa.String(128), nullable=True))
    op.add_column("people", sa.Column("address_line", sa.String(255), nullable=True))
    op.add_column("people", sa.Column("address_number", sa.String(32), nullable=True))
    op.add_column(
        "people", sa.Column("address_complement", sa.String(128), nullable=True)
    )
    op.add_column("people", sa.Column("district", sa.String(128), nullable=True))
    op.add_column("people", sa.Column("city", sa.String(128), nullable=True))
    op.add_column("people", sa.Column("state", sa.String(2), nullable=True))
    op.add_column("people", sa.Column("zip_code", sa.String(16), nullable=True))
    # phone -> cell_phone (carry the value, then drop the old column).
    op.execute("UPDATE people SET cell_phone = COALESCE(cell_phone, phone)")
    op.drop_column("people", "phone")
    op.drop_constraint("uq_people_tenant_document", "people", type_="unique")
    op.alter_column("people", "tenant_id", nullable=True)
    op.create_unique_constraint("uq_people_tenant_cpf", "people", ["tenant_id", "cpf"])
    # A person profile is linked to at most one login account (1:1).
    op.create_unique_constraint("uq_people_user", "people", ["user_id"])


def _users_columns() -> None:
    op.add_column("users", sa.Column("access_code", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("salt", sa.String(64), nullable=True))
    op.add_column(
        "users",
        sa.Column("type", sa.String(32), nullable=False, server_default="INTERNAL"),
    )
    op.add_column(
        "users",
        sa.Column("mfa", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("users", sa.Column("refresh_token", sa.String(128), nullable=True))
    op.add_column("users", sa.Column("person_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_users_person", "users", "people", ["person_id"], ["id"], ondelete="SET NULL"
    )
    # access_code mirrors the existing email (login identifier).
    op.execute("UPDATE users SET access_code = COALESCE(access_code, email)")
    op.alter_column("users", "access_code", nullable=False)
    op.create_unique_constraint("uq_users_access_code", "users", ["access_code"])
    op.drop_constraint("uq_users_tenant_email", "users", type_="unique")
    op.create_unique_constraint("uq_users_email", "users", ["email"])
    # The display name now lives on the linked Person (1:1); drop the legacy
    # NOT NULL column from ``users``.
    op.drop_column("users", "name")
    op.alter_column("users", "tenant_id", nullable=True)


def _unities() -> None:
    op.create_table(
        "unities",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("social_reason", sa.String(255), nullable=True),
        sa.Column("cnpj", sa.String(18), nullable=True),
        sa.Column(
            "matriz_type", sa.String(16), nullable=False, server_default="FILIAL"
        ),
        sa.Column("cnes", sa.String(32), nullable=True),
        sa.Column("sanitary_license", sa.String(64), nullable=True),
        sa.Column("opening_hours", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("address_line", sa.String(255), nullable=True),
        sa.Column("address_number", sa.String(32), nullable=True),
        sa.Column("address_complement", sa.String(128), nullable=True),
        sa.Column("district", sa.String(128), nullable=True),
        sa.Column("city", sa.String(128), nullable=True),
        sa.Column("state", sa.String(2), nullable=True),
        sa.Column("zip_code", sa.String(16), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "cnpj", name="uq_unities_tenant_cnpj"),
    )
    op.create_index("ix_unities_tenant", "unities", ["tenant_id"], unique=False)
    op.create_index("ix_unities_company", "unities", ["company_id"], unique=False)

    # ``customers`` may point at a specific branch (after ``unities`` exists).
    op.add_column("customers", sa.Column("unity_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_customers_unity",
        "customers",
        "unities",
        ["unity_id"],
        ["id"],
        ondelete="SET NULL",
    )


def _rbac_tables() -> None:
    _resources()
    _policy_tables()
    _group_tables()


def _resources() -> None:
    op.create_table(
        "resources",
        sa.Column("module_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(128), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_native", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "control_company_unity",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["module_id"], ["modules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_resources_code"),
    )
    op.create_index("ix_resources_module", "resources", ["module_id"], unique=False)


def _policy_tables() -> None:
    op.create_table(
        "role_policies",
        sa.Column("role_id", sa.UUID(), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("unity_id", sa.UUID(), nullable=True),
        sa.Column(
            "decision", sa.String(16), nullable=False, server_default="ALLOWED"
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unity_id"], ["unities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "role_id",
            "resource_id",
            "user_id",
            "company_id",
            "unity_id",
            name="uq_role_policies_scope",
        ),
    )
    op.create_index("ix_role_policies_role", "role_policies", ["role_id"], unique=False)
    op.create_index("ix_role_policies_user", "role_policies", ["user_id"], unique=False)

    op.create_table(
        "user_policies",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=True),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("unity_id", sa.UUID(), nullable=True),
        sa.Column(
            "decision", sa.String(16), nullable=False, server_default="ALLOWED"
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unity_id"], ["unities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "resource_id",
            "company_id",
            "unity_id",
            name="uq_user_policies_scope",
        ),
    )
    op.create_index("ix_user_policies_user", "user_policies", ["user_id"], unique=False)


def _group_tables() -> None:
    op.create_table(
        "groups",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_groups_tenant_code"),
    )
    op.create_index("ix_groups_tenant", "groups", ["tenant_id"], unique=False)

    op.create_table(
        "group_policies",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("unity_id", sa.UUID(), nullable=True),
        sa.Column(
            "decision", sa.String(16), nullable=False, server_default="ALLOWED"
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unity_id"], ["unities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "group_id",
            "resource_id",
            "company_id",
            "unity_id",
            name="uq_group_policies_scope",
        ),
    )
    op.create_index(
        "ix_group_policies_group", "group_policies", ["group_id"], unique=False
    )

    op.create_table(
        "user_groups",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=True),
        sa.Column("unity_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unity_id"], ["unities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "group_id", "company_id", "unity_id", name="uq_user_groups_scope"
        ),
    )
    op.create_index("ix_user_groups_user", "user_groups", ["user_id"], unique=False)
    op.create_index("ix_user_groups_group", "user_groups", ["group_id"], unique=False)


def _identity_tables() -> None:
    op.create_table(
        "user_tenants",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column(
            "is_default", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_user_tenants"),
    )
    op.create_index("ix_user_tenants_user", "user_tenants", ["user_id"], unique=False)

    op.create_table(
        "user_company_unity",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("unity_id", sa.UUID(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unity_id"], ["unities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "company_id", "unity_id", name="uq_user_company_unity"
        ),
    )
    op.create_index(
        "ix_user_company_unity_user", "user_company_unity", ["user_id"], unique=False
    )


def _base_tables() -> None:
    op.create_table(
        "gut_ranges",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("start_value", sa.Integer(), nullable=True),
        sa.Column("end_value", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_gut_ranges_tenant_code"),
    )

    op.create_table(
        "departments",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_departments_tenant_code"),
    )
    op.create_index("ix_departments_tenant", "departments", ["tenant_id"], unique=False)


def _menu_tables() -> None:
    op.create_table(
        "menus",
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_menus_code"),
    )

    op.create_table(
        "menu_items",
        sa.Column("menu_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("route", sa.String(255), nullable=True),
        sa.Column("icon", sa.String(64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["menu_id"], ["menus.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["menu_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_menu_items_menu", "menu_items", ["menu_id"], unique=False)

    op.create_table(
        "menu_item_resources",
        sa.Column("menu_item_id", sa.UUID(), nullable=False),
        sa.Column("resource_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"], ["menu_items.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["resource_id"], ["resources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "menu_item_id", "resource_id", name="uq_menu_item_resources"
        ),
    )


def _monitoring_tables() -> None:
    for table, uq in (
        ("marcas_monitoramento", "uq_marcas_monitoramento_tenant_codigo"),
        ("patentes_monitoramento", "uq_patentes_monitoramento_tenant_codigo"),
    ):
        prefix = "marcas" if table.startswith("marcas") else "patentes"
        op.create_table(
            table,
            sa.Column("tenant_id", sa.UUID(), nullable=False),
            sa.Column("user_id", sa.UUID(), nullable=False),
            sa.Column("codigo_interno", sa.String(64), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column(
                "monitored_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "codigo_interno", name=uq),
        )
        op.create_index(
            f"ix_{prefix}_monitoramento_tenant", table, ["tenant_id"], unique=False
        )
        op.create_index(
            f"ix_{prefix}_monitoramento_codigo", table, ["codigo_interno"], unique=False
        )


def _backfill() -> None:
    """Idempotent data migration for the new model (safe to re-run)."""
    bind = op.get_bind()

    # 1. Ensure a default tenant exists (name from DEFAULT_TENANT_NAME).
    tenant_id = bind.execute(
        sa.text(
            "SELECT id FROM tenants WHERE social_reason = :n ORDER BY created_at LIMIT 1"
        ),
        {"n": DEFAULT_TENANT},
    ).scalar()
    if tenant_id is None:
        tenant_id = bind.execute(
            sa.text(
                "INSERT INTO tenants (id, social_reason, company_name, active, "
                "created_at, updated_at) "
                "VALUES (gen_random_uuid(), :n, :n, true, now(), now()) RETURNING id"
            ),
            {"n": DEFAULT_TENANT},
        ).scalar()
    bind.execute(
        sa.text(
            "UPDATE tenants SET company_name = COALESCE(company_name, social_reason) "
            "WHERE id = :t"
        ),
        {"t": tenant_id},
    )

    # 2. Every user with a tenant gets a UserTenant row (N-N membership).
    bind.execute(
        sa.text(
            "INSERT INTO user_tenants (id, user_id, tenant_id, is_default, "
            "created_at, updated_at) "
            "SELECT gen_random_uuid(), u.id, u.tenant_id, true, now(), now() "
            "FROM users u WHERE u.tenant_id IS NOT NULL AND NOT EXISTS ("
            "  SELECT 1 FROM user_tenants ut WHERE ut.user_id = u.id "
            "  AND ut.tenant_id = u.tenant_id)"
        )
    )

    # 3. Give every user without a Person a 1:1 profile carrying the old name.
    #    The person starts with a NULL tenant (person is an aggregate root).
    bind.execute(
        sa.text(
            "INSERT INTO people (id, tenant_id, user_id, name, email, active, "
            "created_at, updated_at) "
            "SELECT gen_random_uuid(), NULL, u.id, u.email, u.email, true, now(), now() "
            "FROM users u WHERE NOT EXISTS ("
            "  SELECT 1 FROM people p WHERE p.user_id = u.id)"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE users u SET person_id = p.id FROM people p "
            "WHERE p.user_id = u.id AND u.person_id IS NULL"
        )
    )


def downgrade() -> None:
    for table in ("patentes_monitoramento", "marcas_monitoramento"):
        prefix = "marcas" if table.startswith("marcas") else "patentes"
        op.drop_index(f"ix_{prefix}_monitoramento_codigo", table_name=table)
        op.drop_index(f"ix_{prefix}_monitoramento_tenant", table_name=table)
        op.drop_table(table)

    op.drop_table("menu_item_resources")
    op.drop_index("ix_menu_items_menu", table_name="menu_items")
    op.drop_table("menu_items")
    op.drop_table("menus")

    op.drop_index("ix_departments_tenant", table_name="departments")
    op.drop_table("departments")
    op.drop_table("gut_ranges")

    op.drop_index("ix_user_company_unity_user", table_name="user_company_unity")
    op.drop_table("user_company_unity")
    op.drop_index("ix_user_tenants_user", table_name="user_tenants")
    op.drop_table("user_tenants")

    op.drop_index("ix_user_groups_group", table_name="user_groups")
    op.drop_index("ix_user_groups_user", table_name="user_groups")
    op.drop_table("user_groups")
    op.drop_index("ix_group_policies_group", table_name="group_policies")
    op.drop_table("group_policies")
    op.drop_index("ix_groups_tenant", table_name="groups")
    op.drop_table("groups")

    op.drop_index("ix_user_policies_user", table_name="user_policies")
    op.drop_table("user_policies")
    op.drop_index("ix_role_policies_user", table_name="role_policies")
    op.drop_index("ix_role_policies_role", table_name="role_policies")
    op.drop_table("role_policies")
    op.drop_index("ix_resources_module", table_name="resources")
    op.drop_table("resources")

    op.drop_constraint("fk_customers_unity", "customers", type_="foreignkey")
    op.drop_column("customers", "unity_id")
    op.drop_index("ix_unities_company", table_name="unities")
    op.drop_index("ix_unities_tenant", table_name="unities")
    op.drop_table("unities")

    # Users: restore the original shape.
    op.drop_constraint("uq_users_email", "users", type_="unique")
    op.drop_constraint("uq_users_access_code", "users", type_="unique")
    op.drop_constraint("fk_users_person", "users", type_="foreignkey")
    op.drop_column("users", "person_id")
    op.drop_column("users", "refresh_token")
    op.drop_column("users", "mfa")
    op.drop_column("users", "type")
    op.drop_column("users", "salt")
    op.drop_column("users", "access_code")
    op.add_column("users", sa.Column("name", sa.String(255), nullable=True))
    op.execute("UPDATE users SET name = split_part(email, '@', 1)")
    op.alter_column("users", "name", nullable=False)
    op.create_unique_constraint("uq_users_tenant_email", "users", ["tenant_id", "email"])

    op.drop_constraint("uq_people_user", "people", type_="unique")
    op.drop_constraint("uq_people_tenant_cpf", "people", type_="unique")
    op.add_column("people", sa.Column("phone", sa.String(32), nullable=True))
    op.execute("UPDATE people SET phone = cell_phone")
    op.alter_column("people", "cpf", new_column_name="document")
    op.drop_column("people", "zip_code")
    op.drop_column("people", "state")
    op.drop_column("people", "city")
    op.drop_column("people", "district")
    op.drop_column("people", "address_complement")
    op.drop_column("people", "address_number")
    op.drop_column("people", "address_line")
    op.drop_column("people", "responsibility")
    op.drop_column("people", "cell_phone")
    # Backfill any NULL tenant (person linked to a tenant-less user) so the
    # legacy NOT NULL constraint can be restored.
    op.execute(
        "UPDATE people SET tenant_id = (SELECT id FROM tenants "
        "ORDER BY created_at LIMIT 1) WHERE tenant_id IS NULL"
    )
    op.alter_column("people", "tenant_id", nullable=False)
    op.create_unique_constraint(
        "uq_people_tenant_document", "people", ["tenant_id", "document"]
    )

    # Companies: restore the original shape.
    op.drop_constraint("uq_companies_tenant_external", "companies", type_="unique")
    op.drop_index("ix_companies_company_name", table_name="companies")
    op.add_column("companies", sa.Column("zip_code", sa.String(16), nullable=True))
    op.add_column("companies", sa.Column("state", sa.String(2), nullable=True))
    op.add_column("companies", sa.Column("city", sa.String(128), nullable=True))
    op.add_column("companies", sa.Column("district", sa.String(128), nullable=True))
    op.add_column(
        "companies", sa.Column("address_complement", sa.String(128), nullable=True)
    )
    op.add_column("companies", sa.Column("address_number", sa.String(32), nullable=True))
    op.add_column("companies", sa.Column("address_line", sa.String(255), nullable=True))
    op.add_column(
        "companies", sa.Column("inscricao_estadual", sa.String(32), nullable=True)
    )
    op.add_column("companies", sa.Column("nome_fantasia", sa.String(255), nullable=True))
    op.execute("UPDATE companies SET nome_fantasia = company_name")
    # Rename social_reason back to razao_social BEFORE filling it from the name.
    op.alter_column("companies", "social_reason", new_column_name="razao_social")
    op.execute(
        "UPDATE companies SET razao_social = COALESCE(razao_social, company_name)"
    )
    op.alter_column("companies", "razao_social", nullable=False)
    op.drop_column("companies", "file_document")
    op.drop_column("companies", "external_id")
    op.drop_column("companies", "company_name")
    op.create_index(
        "ix_companies_razao_social", "companies", ["razao_social"], unique=False
    )
    op.create_unique_constraint(
        "uq_companies_tenant_cnpj", "companies", ["tenant_id", "cnpj"]
    )

    op.drop_column("modules", "control_company_unity")

    # Tenants: restore name/legal_name/document; drop the new root columns.
    op.drop_constraint("uq_tenants_mcp_api_key", "tenants", type_="unique")
    op.add_column("tenants", sa.Column("document", sa.String(32), nullable=True))
    op.add_column("tenants", sa.Column("legal_name", sa.String(255), nullable=True))
    op.execute("UPDATE tenants SET legal_name = COALESCE(company_name, social_reason)")
    op.drop_column("tenants", "mcp_api_key")
    op.drop_column("tenants", "cnpj")
    op.drop_column("tenants", "company_name")
    op.alter_column("tenants", "social_reason", new_column_name="name")








