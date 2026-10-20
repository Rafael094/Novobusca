"""add desenhos industriais and software (programa de computador) tables

Revision ID: f1a2b3c4d5e7
Revises: a1c2e3f4b5d6
Create Date: 2026-10-20

Creates the full schema for two new INPI modules, replicating the
marcas/patentes structure WITHOUT ingesting any data (the initial load runs on
the Oracle server at deploy time via ``python -m ingestion.import_all
--category desenhos_industriais`` / ``--category programas_de_computador``).

Tables:
  * Desenho Industrial: desenhos (+ conteudo, depositantes, autores,
    procuradores, classificacoes [Locarno], prioridades, despachos, vinculos,
    figuras [metadata only], monitoramento).
  * Software: softwares (+ campos, titulares, autores, linguagens, tipos,
    despachos, monitoramento).

Column names mirror the official open-data CSVs so the DuckDB loader matches
them case/accent-insensitively.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "f1a2b3c4d5e7"
down_revision = "a1c2e3f4b5d6"
branch_labels = None
depends_on = None


def _str(n):
    return sa.String(length=n)


def upgrade() -> None:
    # ======================= DESENHOS INDUSTRIAIS =======================
    op.create_table(
        "desenhos",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("data_deposito", sa.Date(), nullable=True),
        sa.Column("data_concessao", sa.Date(), nullable=True),
        sa.Column("data_publicacao", sa.Date(), nullable=True),
        sa.Column("data_vigencia", sa.Date(), nullable=True),
        sa.Column("titulo", sa.Text(), nullable=True),
        sa.Column("codigo_situacao", _str(16), nullable=True),
        sa.Column("descricao_situacao", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo_interno", name="uq_desenhos_codigo_interno"),
    )
    op.create_index("ix_desenhos_numero_inpi", "desenhos", ["numero_inpi"])
    op.create_index("ix_desenhos_data_deposito", "desenhos", ["data_deposito"])
    op.create_index("ix_desenhos_codigo_situacao", "desenhos", ["codigo_situacao"])

    op.create_table(
        "desenhos_conteudo",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("titulo", sa.Text(), nullable=True),
        sa.Column("campo_aplicacao", sa.Text(), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_desenhos_conteudo_codigo_interno", "desenhos_conteudo", ["codigo_interno"])

    op.create_table(
        "desenhos_depositantes",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("ordem", _str(16), nullable=True),
        sa.Column("nome", sa.Text(), nullable=True),
        sa.Column("cpf_cnpj", _str(32), nullable=True),
        sa.Column("tipo_pessoa", _str(32), nullable=True),
        sa.Column("pais", _str(64), nullable=True),
        sa.Column("estado", _str(64), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_desenhos_dep_codigo_interno", "desenhos_depositantes", ["codigo_interno"])
    op.create_index("ix_desenhos_dep_nome", "desenhos_depositantes", ["nome"])

    op.create_table(
        "desenhos_autores",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("ordem", _str(16), nullable=True),
        sa.Column("autor", sa.Text(), nullable=True),
        sa.Column("pais", _str(64), nullable=True),
        sa.Column("estado", _str(64), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_desenhos_aut_codigo_interno", "desenhos_autores", ["codigo_interno"])
    op.create_index("ix_desenhos_aut_autor", "desenhos_autores", ["autor"])

    op.create_table(
        "desenhos_procuradores",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("procurador", sa.Text(), nullable=True),
        sa.Column("cpf_cnpj", _str(32), nullable=True),
        sa.Column("tipo_pessoa", _str(32), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_desenhos_proc_codigo_interno", "desenhos_procuradores", ["codigo_interno"])

    op.create_table(
        "desenhos_classificacoes",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("ordem", _str(16), nullable=True),
        sa.Column("classificacao_locarno", _str(32), nullable=True),
        sa.Column("descricao_locarno", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_desenhos_class_codigo_interno", "desenhos_classificacoes", ["codigo_interno"])
    op.create_index("ix_desenhos_class_locarno", "desenhos_classificacoes", ["classificacao_locarno"])

    op.create_table(
        "desenhos_prioridades",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("pais_prioridade", _str(64), nullable=True),
        sa.Column("numero_prioridade", _str(64), nullable=True),
        sa.Column("data_prioridade", sa.Date(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_desenhos_prio_codigo_interno", "desenhos_prioridades", ["codigo_interno"])

    op.create_table(
        "desenhos_despachos",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("numero_rpi", _str(32), nullable=True),
        sa.Column("data_rpi", sa.Date(), nullable=True),
        sa.Column("codigo_despacho", _str(32), nullable=True),
        sa.Column("descricao_despacho", sa.Text(), nullable=True),
        sa.Column("complemento_despacho", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_desenhos_desp_codigo_interno", "desenhos_despachos", ["codigo_interno"])
    op.create_index("ix_desenhos_desp_codigo_despacho", "desenhos_despachos", ["codigo_despacho"])

    op.create_table(
        "desenhos_vinculos",
        sa.Column("codigo_interno_derivado", _str(64), nullable=True),
        sa.Column("numero_inpi_derivado", _str(32), nullable=True),
        sa.Column("codigo_interno_origem", _str(64), nullable=True),
        sa.Column("numero_inpi_origem", _str(32), nullable=True),
        sa.Column("data_vinculo", sa.Date(), nullable=True),
        sa.Column("tipo_vinculo", _str(64), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_desenhos_vinc_derivado", "desenhos_vinculos", ["codigo_interno_derivado"])
    op.create_index("ix_desenhos_vinc_origem", "desenhos_vinculos", ["codigo_interno_origem"])

    op.create_table(
        "desenhos_figuras",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("arquivo", sa.Text(), nullable=True),
        sa.Column("mime", _str(64), nullable=True),
        sa.Column("bytes", sa.BigInteger(), nullable=True),
        sa.Column("sha256", _str(64), nullable=True),
        sa.Column("status", _str(16), nullable=False, server_default="PENDING"),
        sa.Column("tentativas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column("baixado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo_interno", name="uq_desenhos_figuras_codigo_interno"),
    )
    op.create_index("ix_desenhos_fig_codigo_interno", "desenhos_figuras", ["codigo_interno"])
    op.create_index("ix_desenhos_fig_status", "desenhos_figuras", ["status"])

    op.create_table(
        "desenhos_monitoramento",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("monitored_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "codigo_interno", name="uq_desenhos_monitoramento_tenant_codigo"),
    )
    op.create_index("ix_desenhos_monitoramento_tenant", "desenhos_monitoramento", ["tenant_id"])
    op.create_index("ix_desenhos_monitoramento_codigo", "desenhos_monitoramento", ["codigo_interno"])

    # =================== PROGRAMAS DE COMPUTADOR (software) ===================
    op.create_table(
        "softwares",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("data_deposito", sa.Date(), nullable=True),
        sa.Column("data_concessao", sa.Date(), nullable=True),
        sa.Column("data_publicacao", sa.Date(), nullable=True),
        sa.Column("data_criacao", sa.Date(), nullable=True),
        sa.Column("titulo", sa.Text(), nullable=True),
        sa.Column("codigo_situacao", _str(16), nullable=True),
        sa.Column("descricao_situacao", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("codigo_interno", name="uq_softwares_codigo_interno"),
    )
    op.create_index("ix_softwares_numero_inpi", "softwares", ["numero_inpi"])
    op.create_index("ix_softwares_data_deposito", "softwares", ["data_deposito"])
    op.create_index("ix_softwares_codigo_situacao", "softwares", ["codigo_situacao"])

    op.create_table(
        "softwares_campos",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("campo", sa.Text(), nullable=True),
        sa.Column("valor", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_softwares_campos_codigo_interno", "softwares_campos", ["codigo_interno"])

    op.create_table(
        "softwares_titulares",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("ordem", _str(16), nullable=True),
        sa.Column("nome", sa.Text(), nullable=True),
        sa.Column("cpf_cnpj", _str(32), nullable=True),
        sa.Column("tipo_pessoa", _str(32), nullable=True),
        sa.Column("pais", _str(64), nullable=True),
        sa.Column("estado", _str(64), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_softwares_tit_codigo_interno", "softwares_titulares", ["codigo_interno"])
    op.create_index("ix_softwares_tit_nome", "softwares_titulares", ["nome"])

    op.create_table(
        "softwares_autores",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("ordem", _str(16), nullable=True),
        sa.Column("autor", sa.Text(), nullable=True),
        sa.Column("pais", _str(64), nullable=True),
        sa.Column("estado", _str(64), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_softwares_aut_codigo_interno", "softwares_autores", ["codigo_interno"])
    op.create_index("ix_softwares_aut_autor", "softwares_autores", ["autor"])

    op.create_table(
        "softwares_linguagens",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("linguagem", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_softwares_ling_codigo_interno", "softwares_linguagens", ["codigo_interno"])

    op.create_table(
        "softwares_tipos",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("tipo", sa.Text(), nullable=True),
        sa.Column("campo_aplicacao", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_softwares_tipo_codigo_interno", "softwares_tipos", ["codigo_interno"])

    op.create_table(
        "softwares_despachos",
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("numero_inpi", _str(32), nullable=True),
        sa.Column("numero_rpi", _str(32), nullable=True),
        sa.Column("data_rpi", sa.Date(), nullable=True),
        sa.Column("codigo_despacho", _str(32), nullable=True),
        sa.Column("descricao_despacho", sa.Text(), nullable=True),
        sa.Column("complemento_despacho", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_softwares_desp_codigo_interno", "softwares_despachos", ["codigo_interno"])
    op.create_index("ix_softwares_desp_codigo_despacho", "softwares_despachos", ["codigo_despacho"])

    op.create_table(
        "softwares_monitoramento",
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("codigo_interno", _str(64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("monitored_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "codigo_interno", name="uq_softwares_monitoramento_tenant_codigo"),
    )
    op.create_index("ix_softwares_monitoramento_tenant", "softwares_monitoramento", ["tenant_id"])
    op.create_index("ix_softwares_monitoramento_codigo", "softwares_monitoramento", ["codigo_interno"])


def downgrade() -> None:
    for tbl in (
        "softwares_monitoramento",
        "softwares_despachos",
        "softwares_tipos",
        "softwares_linguagens",
        "softwares_autores",
        "softwares_titulares",
        "softwares_campos",
        "softwares",
        "desenhos_monitoramento",
        "desenhos_figuras",
        "desenhos_vinculos",
        "desenhos_despachos",
        "desenhos_prioridades",
        "desenhos_classificacoes",
        "desenhos_procuradores",
        "desenhos_autores",
        "desenhos_depositantes",
        "desenhos_conteudo",
        "desenhos",
    ):
        op.drop_table(tbl)
