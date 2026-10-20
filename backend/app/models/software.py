"""Normalized ORM models for the INPI Programa de Computador (software) datasets.

Mirrors the official INPI open-data CSVs under
``/download/programas_de_computador`` (``PROG_COMP_DADOS_BASICOS.csv`` and the
related child tables). Column names mirror the source CSVs so the DuckDB loader
(``ingestion.load``) can match them case/accent-insensitively — the same
strategy used for ``marcas`` and ``patentes``.

Keyed by ``codigo_interno`` (the INPI internal process code).
"""

from __future__ import annotations

from sqlalchemy import Date, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Software(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """PROG_COMP_DADOS_BASICOS.csv — basic record of a software registration."""

    __tablename__ = "softwares"
    __table_args__ = (
        UniqueConstraint("codigo_interno", name="uq_softwares_codigo_interno"),
        Index("ix_softwares_numero_inpi", "numero_inpi"),
        Index("ix_softwares_data_deposito", "data_deposito"),
        Index("ix_softwares_codigo_situacao", "codigo_situacao"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    data_deposito: Mapped[object | None] = mapped_column(Date)
    data_concessao: Mapped[object | None] = mapped_column(Date)
    data_publicacao: Mapped[object | None] = mapped_column(Date)
    data_criacao: Mapped[object | None] = mapped_column(Date)
    titulo: Mapped[str | None] = mapped_column(Text)
    codigo_situacao: Mapped[str | None] = mapped_column(String(16))
    descricao_situacao: Mapped[str | None] = mapped_column(Text)

    titulares: Mapped[list["SoftwareTitular"]] = relationship(
        primaryjoin="Software.codigo_interno == foreign(SoftwareTitular.codigo_interno)",
        viewonly=True,
    )


class SoftwareCampos(UUIDPrimaryKeyMixin, Base):
    """PROG_COMP_CAMPOS.csv — free-form descriptive fields of the program."""

    __tablename__ = "softwares_campos"
    __table_args__ = (Index("ix_softwares_campos_codigo_interno", "codigo_interno"),)

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    campo: Mapped[str | None] = mapped_column(Text)
    valor: Mapped[str | None] = mapped_column(Text)


class SoftwareTitular(UUIDPrimaryKeyMixin, Base):
    """PROG_COMP_TITULAR.csv — holders of the software registration."""

    __tablename__ = "softwares_titulares"
    __table_args__ = (
        Index("ix_softwares_tit_codigo_interno", "codigo_interno"),
        Index("ix_softwares_tit_nome", "nome"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    ordem: Mapped[str | None] = mapped_column(String(16))
    nome: Mapped[str | None] = mapped_column(Text)
    cpf_cnpj: Mapped[str | None] = mapped_column(String(32))
    tipo_pessoa: Mapped[str | None] = mapped_column(String(32))
    pais: Mapped[str | None] = mapped_column(String(64))
    estado: Mapped[str | None] = mapped_column(String(64))


class SoftwareAutor(UUIDPrimaryKeyMixin, Base):
    """PROG_COMP_AUTORES.csv — authors (creators) of the program."""

    __tablename__ = "softwares_autores"
    __table_args__ = (
        Index("ix_softwares_aut_codigo_interno", "codigo_interno"),
        Index("ix_softwares_aut_autor", "autor"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    ordem: Mapped[str | None] = mapped_column(String(16))
    autor: Mapped[str | None] = mapped_column(Text)
    pais: Mapped[str | None] = mapped_column(String(64))
    estado: Mapped[str | None] = mapped_column(String(64))


class SoftwareLinguagem(UUIDPrimaryKeyMixin, Base):
    """PROG_COMP_LINGUAGEM.csv — programming languages declared."""

    __tablename__ = "softwares_linguagens"
    __table_args__ = (Index("ix_softwares_ling_codigo_interno", "codigo_interno"),)

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    linguagem: Mapped[str | None] = mapped_column(Text)


class SoftwareTipo(UUIDPrimaryKeyMixin, Base):
    """PROG_COMP_TIPO.csv — program type/field of application."""

    __tablename__ = "softwares_tipos"
    __table_args__ = (Index("ix_softwares_tipo_codigo_interno", "codigo_interno"),)

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    tipo: Mapped[str | None] = mapped_column(Text)
    campo_aplicacao: Mapped[str | None] = mapped_column(Text)


class SoftwareDespacho(UUIDPrimaryKeyMixin, Base):
    """PROG_COMP_DESPACHOS.csv — RPI publications/despachos for the process."""

    __tablename__ = "softwares_despachos"
    __table_args__ = (
        Index("ix_softwares_desp_codigo_interno", "codigo_interno"),
        Index("ix_softwares_desp_codigo_despacho", "codigo_despacho"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    numero_rpi: Mapped[str | None] = mapped_column(String(32))
    data_rpi: Mapped[object | None] = mapped_column(Date)
    codigo_despacho: Mapped[str | None] = mapped_column(String(32))
    descricao_despacho: Mapped[str | None] = mapped_column(Text)
    complemento_despacho: Mapped[str | None] = mapped_column(Text)
