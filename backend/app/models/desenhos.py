"""Normalized ORM models for the INPI Desenho Industrial (DI) datasets.

Mirrors the official INPI open-data CSVs under ``/download/desenhos_industriais``
(``DI_DADOS_BIBLIOGRAFICOS.csv`` and the related child tables). Column names
mirror the source CSVs so the DuckDB loader (``ingestion.load``) can match them
case/accent-insensitively — exactly the same strategy used for ``marcas`` and
``patentes``.

Keyed by ``codigo_interno`` (the INPI internal process code). Image figures
(``DI_FIGURAS_*.ZIP``, tens of GB) are intentionally NOT modelled as bulk
tables — they follow the same on-demand/worker image strategy as the marca
logotipos (see ``DesenhoFigura``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Date, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Desenho(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """DI_DADOS_BIBLIOGRAFICOS.csv — biblio record of a design application."""

    __tablename__ = "desenhos"
    __table_args__ = (
        UniqueConstraint("codigo_interno", name="uq_desenhos_codigo_interno"),
        Index("ix_desenhos_numero_inpi", "numero_inpi"),
        Index("ix_desenhos_data_deposito", "data_deposito"),
        Index("ix_desenhos_codigo_situacao", "codigo_situacao"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    data_deposito: Mapped[object | None] = mapped_column(Date)
    data_concessao: Mapped[object | None] = mapped_column(Date)
    data_publicacao: Mapped[object | None] = mapped_column(Date)
    data_vigencia: Mapped[object | None] = mapped_column(Date)
    titulo: Mapped[str | None] = mapped_column(Text)
    codigo_situacao: Mapped[str | None] = mapped_column(String(16))
    descricao_situacao: Mapped[str | None] = mapped_column(Text)

    depositantes: Mapped[list["DesenhoDepositante"]] = relationship(
        primaryjoin="Desenho.codigo_interno == foreign(DesenhoDepositante.codigo_interno)",
        viewonly=True,
    )


class DesenhoConteudo(UUIDPrimaryKeyMixin, Base):
    """DI_CONTEUDO.csv — object/title/campo de aplicação descriptive content."""

    __tablename__ = "desenhos_conteudo"
    __table_args__ = (Index("ix_desenhos_conteudo_codigo_interno", "codigo_interno"),)

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    titulo: Mapped[str | None] = mapped_column(Text)
    campo_aplicacao: Mapped[str | None] = mapped_column(Text)
    descricao: Mapped[str | None] = mapped_column(Text)


class DesenhoDepositante(UUIDPrimaryKeyMixin, Base):
    """DI_DEPOSITANTES.csv — applicants/holders of the design."""

    __tablename__ = "desenhos_depositantes"
    __table_args__ = (
        Index("ix_desenhos_dep_codigo_interno", "codigo_interno"),
        Index("ix_desenhos_dep_nome", "nome"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    ordem: Mapped[str | None] = mapped_column(String(16))
    nome: Mapped[str | None] = mapped_column(Text)
    cpf_cnpj: Mapped[str | None] = mapped_column(String(32))
    tipo_pessoa: Mapped[str | None] = mapped_column(String(32))
    pais: Mapped[str | None] = mapped_column(String(64))
    estado: Mapped[str | None] = mapped_column(String(64))


class DesenhoAutor(UUIDPrimaryKeyMixin, Base):
    """DI_AUTORES.csv — designers (authors) of the design."""

    __tablename__ = "desenhos_autores"
    __table_args__ = (
        Index("ix_desenhos_aut_codigo_interno", "codigo_interno"),
        Index("ix_desenhos_aut_autor", "autor"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    ordem: Mapped[str | None] = mapped_column(String(16))
    autor: Mapped[str | None] = mapped_column(Text)
    pais: Mapped[str | None] = mapped_column(String(64))
    estado: Mapped[str | None] = mapped_column(String(64))


class DesenhoProcurador(UUIDPrimaryKeyMixin, Base):
    """DI_PROCURADORES.csv — legal representatives/attorneys."""

    __tablename__ = "desenhos_procuradores"
    __table_args__ = (Index("ix_desenhos_proc_codigo_interno", "codigo_interno"),)

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    procurador: Mapped[str | None] = mapped_column(Text)
    cpf_cnpj: Mapped[str | None] = mapped_column(String(32))
    tipo_pessoa: Mapped[str | None] = mapped_column(String(32))


class DesenhoClassificacao(UUIDPrimaryKeyMixin, Base):
    """DI_CLASSIFICACOES.csv — Locarno classification of the design."""

    __tablename__ = "desenhos_classificacoes"
    __table_args__ = (
        Index("ix_desenhos_class_codigo_interno", "codigo_interno"),
        Index("ix_desenhos_class_locarno", "classificacao_locarno"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    ordem: Mapped[str | None] = mapped_column(String(16))
    classificacao_locarno: Mapped[str | None] = mapped_column(String(32))
    descricao_locarno: Mapped[str | None] = mapped_column(Text)


class DesenhoPrioridade(UUIDPrimaryKeyMixin, Base):
    """DI_PRIORIDADES.csv — unionist priorities claimed."""

    __tablename__ = "desenhos_prioridades"
    __table_args__ = (Index("ix_desenhos_prio_codigo_interno", "codigo_interno"),)

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    pais_prioridade: Mapped[str | None] = mapped_column(String(64))
    numero_prioridade: Mapped[str | None] = mapped_column(String(64))
    data_prioridade: Mapped[object | None] = mapped_column(Date)


class DesenhoDespacho(UUIDPrimaryKeyMixin, Base):
    """DI_DESPACHOS.csv — RPI publications/despachos for the design process."""

    __tablename__ = "desenhos_despachos"
    __table_args__ = (
        Index("ix_desenhos_desp_codigo_interno", "codigo_interno"),
        Index("ix_desenhos_desp_codigo_despacho", "codigo_despacho"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    numero_rpi: Mapped[str | None] = mapped_column(String(32))
    data_rpi: Mapped[object | None] = mapped_column(Date)
    codigo_despacho: Mapped[str | None] = mapped_column(String(32))
    descricao_despacho: Mapped[str | None] = mapped_column(Text)
    complemento_despacho: Mapped[str | None] = mapped_column(Text)


class DesenhoVinculo(UUIDPrimaryKeyMixin, Base):
    """DI_VINCULOS.csv — links between processes (divisions, etc.)."""

    __tablename__ = "desenhos_vinculos"
    __table_args__ = (
        Index("ix_desenhos_vinc_derivado", "codigo_interno_derivado"),
        Index("ix_desenhos_vinc_origem", "codigo_interno_origem"),
    )

    codigo_interno_derivado: Mapped[str | None] = mapped_column(String(64))
    numero_inpi_derivado: Mapped[str | None] = mapped_column(String(32))
    codigo_interno_origem: Mapped[str | None] = mapped_column(String(64))
    numero_inpi_origem: Mapped[str | None] = mapped_column(String(32))
    data_vinculo: Mapped[object | None] = mapped_column(Date)
    tipo_vinculo: Mapped[str | None] = mapped_column(String(64))


class DesenhoFigura(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Locally downloaded figure/image of a design (``DI_FIGURAS_*``).

    The INPI figure bundles are tens of GB of ZIPs — far too large to store on
    the Oracle Free Tier VM. This table records only the *metadata* (same
    pattern as ``marcas_logos``): the binary lives on object storage / disk and
    the row lets the API decide whether an image exists without touching the
    filesystem, and lets the worker resume. ``status``: OK / SEM_IMAGEM / ERROR.
    """

    __tablename__ = "desenhos_figuras"
    __table_args__ = (
        UniqueConstraint("codigo_interno", name="uq_desenhos_figuras_codigo_interno"),
        Index("ix_desenhos_fig_status", "status"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    arquivo: Mapped[str | None] = mapped_column(Text)
    mime: Mapped[str | None] = mapped_column(String(64))
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    erro: Mapped[str | None] = mapped_column(Text)
    baixado_em: Mapped[datetime | None] = mapped_column()


class DesenhoRpiFigura(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Procedência de uma figura de DI referenciada pelo XML da RPI.

    ``desenhos_figuras`` é a fonte que a API lê; esta tabela registra **de qual
    edição/processo/arquivo** a imagem veio, inclusive quando o processo ainda
    não existe no dump de ``desenhos`` (``codigo_interno`` nulo). Isso permite
    auditoria, resume por edição e reprocessamento sem baixar tudo de novo.

    ``status`` segue o mesmo vocabulário de ``desenhos_figuras``:
    ``PENDING``/``OK``/``SEM_IMAGEM``/``ERROR``. ``OK``/``SEM_IMAGEM`` são
    terminais no resume; ``ERROR`` volta na próxima rodada.
    """

    __tablename__ = "desenhos_rpi_figuras"
    __table_args__ = (
        UniqueConstraint(
            "numero_rpi",
            "numero_processo",
            name="uq_desenhos_rpi_figuras_rpi_processo",
        ),
        Index("ix_desenhos_rpi_figuras_status", "status"),
        Index("ix_desenhos_rpi_figuras_processo", "numero_processo"),
        Index("ix_desenhos_rpi_figuras_codigo", "codigo_interno"),
    )

    numero_rpi: Mapped[str] = mapped_column(String(32), nullable=False)
    numero_processo: Mapped[str] = mapped_column(String(32), nullable=False)
    nome_imagem: Mapped[str | None] = mapped_column(String(255))
    codigo_interno: Mapped[str | None] = mapped_column(String(64))
    arquivo: Mapped[str | None] = mapped_column(Text)
    mime: Mapped[str | None] = mapped_column(String(64))
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    erro: Mapped[str | None] = mapped_column(Text)
    origem_url: Mapped[str | None] = mapped_column(Text)
    baixado_em: Mapped[datetime | None] = mapped_column()
