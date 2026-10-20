"""add marcas_rpi_imagens table

Revision ID: a9b8c7d6e5f4
Revises: f1a2b3c4d5e7
Create Date: 2026-10-20

Registra a procedência das figuras/logotipos de marcas referenciados pelo XML
semanal da RPI (``<nome-imagem>``). O binário continua no volume de dados,
servido pela API a partir de ``marcas_logos``; esta tabela permite auditar de
qual edição/processo/arquivo a imagem veio, retomar downloads pendentes e
reprocessar sem tocar no dump de marcas.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a9b8c7d6e5f4"
down_revision = "f1a2b3c4d5e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marcas_rpi_imagens",
        sa.Column("numero_rpi", sa.String(length=32), nullable=False),
        sa.Column("numero_processo", sa.String(length=32), nullable=False),
        sa.Column("nome_imagem", sa.String(length=255), nullable=True),
        sa.Column("codigo_interno", sa.String(length=64), nullable=True),
        sa.Column("arquivo", sa.Text(), nullable=True),
        sa.Column("mime", sa.String(length=64), nullable=True),
        sa.Column("bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column(
            "tentativas",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("origem_url", sa.Text(), nullable=True),
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
            "numero_rpi",
            "numero_processo",
            name="uq_marcas_rpi_imagens_rpi_processo",
        ),
    )
    op.create_index(
        "ix_marcas_rpi_imagens_status",
        "marcas_rpi_imagens",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_marcas_rpi_imagens_processo",
        "marcas_rpi_imagens",
        ["numero_processo"],
        unique=False,
    )
    op.create_index(
        "ix_marcas_rpi_imagens_codigo",
        "marcas_rpi_imagens",
        ["codigo_interno"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_marcas_rpi_imagens_codigo", table_name="marcas_rpi_imagens"
    )
    op.drop_index(
        "ix_marcas_rpi_imagens_processo", table_name="marcas_rpi_imagens"
    )
    op.drop_index(
        "ix_marcas_rpi_imagens_status", table_name="marcas_rpi_imagens"
    )
    op.drop_table("marcas_rpi_imagens")
