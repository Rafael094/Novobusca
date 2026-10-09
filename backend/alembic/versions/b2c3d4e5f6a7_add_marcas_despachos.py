"""add marcas_despachos table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-07

Imports the official INPI ``MARCAS_DESPACHOS.csv`` (RPI publications/despachos
for trademark applications). Columns mirror the source CSV exactly:
``codigo_interno, numero_inpi, numero_rpi, data_rpi, codigo_despacho,
descricao_despacho, complemento_despacho``.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marcas_despachos",
        sa.Column("codigo_interno", sa.String(length=64), nullable=False),
        sa.Column("numero_inpi", sa.String(length=32), nullable=True),
        sa.Column("numero_rpi", sa.String(length=32), nullable=True),
        sa.Column("data_rpi", sa.Date(), nullable=True),
        sa.Column("codigo_despacho", sa.String(length=32), nullable=True),
        sa.Column("descricao_despacho", sa.Text(), nullable=True),
        sa.Column("complemento_despacho", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_marcas_desp_codigo_interno", "marcas_despachos", ["codigo_interno"], unique=False
    )
    op.create_index(
        "ix_marcas_desp_codigo_despacho", "marcas_despachos", ["codigo_despacho"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_marcas_desp_codigo_despacho", table_name="marcas_despachos")
    op.drop_index("ix_marcas_desp_codigo_interno", table_name="marcas_despachos")
    op.drop_table("marcas_despachos")
