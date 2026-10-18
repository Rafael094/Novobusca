"""add marcas_peticoes + marcas_pepi_sync tables

Revision ID: a1c2e3f4b5d6
Revises: e1a2b3c4d5e6
Create Date: 2026-10-17

Petições (documentos GRU) de um processo de marca. NÃO fazem parte dos CSVs de
dados abertos do INPI — só existem na aplicação de consulta pePI
(``busca.inpi.gov.br``), atrás de uma sessão anônima. O worker
``ingestion.peticoes`` lê a página de detalhe
(``MarcasServletController?Action=detail&CodPedido=<codigo_interno>``) e grava
os registros aqui, uma linha por protocolo.

Tabelas:
  * ``marcas_peticoes``  — os documentos (protocolo, data, serviço, cliente...);
  * ``marcas_pepi_sync`` — estado/fila da sincronização por ``codigo_interno``
    (resumo/re-tentativa/TTL do worker), espelhando o ``status`` de
    ``marcas_logos``.

Ambas são ADITIVAS: nenhuma tabela existente é alterada (os dados públicos e os
índices de busca ficam intactos).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a1c2e3f4b5d6"
down_revision = "e1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marcas_peticoes",
        sa.Column("codigo_interno", sa.String(length=64), nullable=False),
        sa.Column("numero_inpi", sa.String(length=32), nullable=True),
        sa.Column("protocolo", sa.String(length=32), nullable=False),
        sa.Column("data_protocolo", sa.Date(), nullable=True),
        sa.Column("codigo_servico", sa.String(length=16), nullable=True),
        sa.Column("descricao_servico", sa.Text(), nullable=True),
        sa.Column("cliente", sa.Text(), nullable=True),
        sa.Column(
            "pagamento_conciliado",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("banco_codigo", sa.String(length=8), nullable=True),
        sa.Column("banco_nome", sa.Text(), nullable=True),
        sa.Column("data_pagamento", sa.Date(), nullable=True),
        sa.Column("valor_pagamento", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("delivery", sa.Text(), nullable=True),
        sa.Column("data_delivery", sa.Date(), nullable=True),
        sa.Column(
            "tem_imagem",
            sa.Boolean(),
            server_default=sa.text("false"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "codigo_interno", "protocolo", name="uq_marcas_peticoes_codigo_protocolo"
        ),
    )
    op.create_index(
        "ix_marcas_peticoes_codigo_interno",
        "marcas_peticoes",
        ["codigo_interno"],
        unique=False,
    )

    op.create_table(
        "marcas_pepi_sync",
        sa.Column("codigo_interno", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'PENDING'"),
            nullable=False,
        ),
        sa.Column(
            "peticoes_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("revista", sa.String(length=32), nullable=True),
        sa.Column("dados_atualizados_em", sa.Date(), nullable=True),
        sa.Column(
            "tentativas", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("sincronizado_em", sa.DateTime(timezone=True), nullable=True),
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
            "codigo_interno", name="uq_marcas_pepi_sync_codigo_interno"
        ),
    )
    op.create_index(
        "ix_marcas_pepi_sync_status", "marcas_pepi_sync", ["status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_marcas_pepi_sync_status", table_name="marcas_pepi_sync")
    op.drop_table("marcas_pepi_sync")
    op.drop_index(
        "ix_marcas_peticoes_codigo_interno", table_name="marcas_peticoes"
    )
    op.drop_table("marcas_peticoes")
