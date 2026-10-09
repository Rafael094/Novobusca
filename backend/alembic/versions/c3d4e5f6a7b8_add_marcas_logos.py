"""add marcas_logos table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-10-07

Stores metadata for locally downloaded marcas logotipos (images fetched from the
public pePI ``LogoMarcasServletController`` via an anonymous session). Not part
of the INPI open-data CSVs; the binary lives on disk and this table only records
where/how it was obtained so the API and the resumable downloader can work.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marcas_logos",
        sa.Column("codigo_interno", sa.String(length=64), nullable=False),
        sa.Column("arquivo", sa.Text(), nullable=True),
        sa.Column("mime", sa.String(length=64), nullable=True),
        sa.Column("bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("tentativas", sa.Integer(), nullable=False),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("baixado_em", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "codigo_interno", name="uq_marcas_logos_codigo_interno"
        ),
    )
    op.create_index(
        "ix_marcas_logos_status", "marcas_logos", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_marcas_logos_status", table_name="marcas_logos")
    op.drop_table("marcas_logos")
