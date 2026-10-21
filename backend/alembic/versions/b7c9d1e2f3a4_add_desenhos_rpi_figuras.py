"""add desenhos_rpi_figuras table

Revision ID: b7c9d1e2f3a4
Revises: a9b8c7d6e5f4
Create Date: 2026-10-20

Registra a procedência das figuras de Desenho Industrial referenciadas pelo XML
semanal da RPI. O binário continua no volume de dados, servido pela API a partir
de ``desenhos_figuras``; esta tabela permite auditar de qual edição/processo a
imagem veio, retomar downloads pendentes e reprocessar sem tocar no dump de DI.
Espelha ``marcas_rpi_imagens``.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b7c9d1e2f3a4"
down_revision = "a9b8c7d6e5f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "desenhos_rpi_figuras",
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
            name="uq_desenhos_rpi_figuras_rpi_processo",
        ),
    )
    op.create_index(
        "ix_desenhos_rpi_figuras_status",
        "desenhos_rpi_figuras",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_desenhos_rpi_figuras_processo",
        "desenhos_rpi_figuras",
        ["numero_processo"],
        unique=False,
    )
    op.create_index(
        "ix_desenhos_rpi_figuras_codigo",
        "desenhos_rpi_figuras",
        ["codigo_interno"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_desenhos_rpi_figuras_codigo", table_name="desenhos_rpi_figuras"
    )
    op.drop_index(
        "ix_desenhos_rpi_figuras_processo", table_name="desenhos_rpi_figuras"
    )
    op.drop_index(
        "ix_desenhos_rpi_figuras_status", table_name="desenhos_rpi_figuras"
    )
    op.drop_table("desenhos_rpi_figuras")
