"""widen marcas_classificacoes_viena text columns

Revision ID: a1b2c3d4e5f6
Revises: 612d99e9df03
Create Date: 2026-10-07

The official INPI ``MARCAS_CLASSIFICACOES_VIENA.csv`` stores a descriptive
label in ``classificacao_viena`` (observed up to ~187 chars, e.g. "Letras ou
algarismos representando um ser humano ou uma parte do corpo humano, ...")
and a ``revisao_viena`` value with trailing spaces. The original
``varchar(32)``/``varchar(16)`` widths rejected the real data.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "612d99e9df03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "marcas_classificacoes_viena",
        "classificacao_viena",
        existing_type=sa.String(length=32),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "marcas_classificacoes_viena",
        "revisao_viena",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "marcas_classificacoes_viena",
        "revisao_viena",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=True,
    )
    op.alter_column(
        "marcas_classificacoes_viena",
        "classificacao_viena",
        existing_type=sa.Text(),
        type_=sa.String(length=32),
        existing_nullable=True,
    )
