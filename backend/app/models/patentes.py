"""Normalized ORM models for the INPI patents (patentes) datasets.

Column names mirror the official INPI CSVs exactly (source columns preserved),
plus a few indexes for search. Keyed by numero_inpi / codigo_interno.
"""

from __future__ import annotations

from sqlalchemy import Date, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Patente(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """PATENTES_DADOS_BIBLIOGRAFICOS.csv"""

    __tablename__ = "patentes"
    __table_args__ = (
        UniqueConstraint("codigo_interno", name="uq_patentes_codigo_interno"),
        Index("ix_patentes_numero_inpi", "numero_inpi"),
        Index("ix_patentes_data_deposito", "data_deposito"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    data_deposito: Mapped[object | None] = mapped_column(Date)
    data_protocolo: Mapped[object | None] = mapped_column(Date)
    data_publicacao: Mapped[object | None] = mapped_column(Date)
    numero_pct: Mapped[str | None] = mapped_column(String(64))
    numero_wo: Mapped[str | None] = mapped_column(String(64))
    data_publicacao_wo: Mapped[object | None] = mapped_column(Date)
    data_entrada_fase_nacional: Mapped[object | None] = mapped_column(Date)
    sigilo: Mapped[str | None] = mapped_column(String(8))


class PatenteConteudo(UUIDPrimaryKeyMixin, Base):
    """PATENTES_CONTEUDO.csv"""

    __tablename__ = "patentes_conteudo"
    __table_args__ = (
        Index("ix_patentes_conteudo_codigo_interno", "codigo_interno"),
        Index("ix_patentes_conteudo_numero_inpi", "numero_inpi"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    titulo: Mapped[str | None] = mapped_column(Text)
    resumo: Mapped[str | None] = mapped_column(Text)


class PatenteDepositante(UUIDPrimaryKeyMixin, Base):
    """PATENTES_DEPOSITANTES.csv"""

    __tablename__ = "patentes_depositantes"
    __table_args__ = (
        Index("ix_patentes_dep_codigo_interno", "codigo_interno"),
        Index("ix_patentes_dep_depositante", "depositante"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    ordem: Mapped[str | None] = mapped_column(String(16))
    pais: Mapped[str | None] = mapped_column(String(64))
    estado: Mapped[str | None] = mapped_column(String(64))
    depositante: Mapped[str | None] = mapped_column(Text)
    cgccpfdepositante: Mapped[str | None] = mapped_column(String(32))
    tipopessoadepositante: Mapped[str | None] = mapped_column(String(32))
    data_inicio_depositante: Mapped[object | None] = mapped_column(Date)
    data_fim_depositante: Mapped[object | None] = mapped_column(Date)


class PatenteInventor(UUIDPrimaryKeyMixin, Base):
    """PATENTES_INVENTORES.csv"""

    __tablename__ = "patentes_inventores"
    __table_args__ = (
        Index("ix_patentes_inv_codigo_interno", "codigo_interno"),
        Index("ix_patentes_inv_autor", "autor"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    ordem: Mapped[str | None] = mapped_column(String(16))
    autor: Mapped[str | None] = mapped_column(Text)
    pais: Mapped[str | None] = mapped_column(String(64))
    estado: Mapped[str | None] = mapped_column(String(64))


class PatenteProcurador(UUIDPrimaryKeyMixin, Base):
    """PATENTES_PROCURADORES.csv"""

    __tablename__ = "patentes_procuradores"
    __table_args__ = (
        Index("ix_patentes_proc_codigo_interno", "codigo_interno"),
        Index("ix_patentes_proc_procurador", "procurador"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    procurador: Mapped[str | None] = mapped_column(Text)
    cgccpfprocurador: Mapped[str | None] = mapped_column(String(32))
    tipopessoaprocurador: Mapped[str | None] = mapped_column(String(32))
    data_inicio_procurador: Mapped[object | None] = mapped_column(Date)


class PatentePrioridade(UUIDPrimaryKeyMixin, Base):
    """PATENTES_PRIORIDADES.csv"""

    __tablename__ = "patentes_prioridades"
    __table_args__ = (Index("ix_patentes_prio_codigo_interno", "codigo_interno"),)

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    pais_prioridade: Mapped[str | None] = mapped_column(String(64))
    numero_prioridade: Mapped[str | None] = mapped_column(String(64))
    data_prioridade: Mapped[object | None] = mapped_column(Date)


class PatenteClassificacaoIpc(UUIDPrimaryKeyMixin, Base):
    """PATENTES_CLASSIFICACAO_IPC.csv"""

    __tablename__ = "patentes_classificacao_ipc"
    __table_args__ = (
        Index("ix_patentes_ipc_codigo_interno", "codigo_interno"),
        Index("ix_patentes_ipc_simbolo", "simbolo"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    ordem: Mapped[str | None] = mapped_column(String(16))
    simbolo: Mapped[str | None] = mapped_column(String(64))
    versao: Mapped[str | None] = mapped_column(String(16))


class PatenteDespacho(UUIDPrimaryKeyMixin, Base):
    """PATENTES_DESPACHOS.csv"""

    __tablename__ = "patentes_despachos"
    __table_args__ = (
        Index("ix_patentes_desp_codigo_interno", "codigo_interno"),
        Index("ix_patentes_desp_codigo_despacho", "codigo_despacho"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    numero_rpi: Mapped[str | None] = mapped_column(String(32))
    data_rpi: Mapped[object | None] = mapped_column(Date)
    codigo_despacho: Mapped[str | None] = mapped_column(String(32))
    complemento_despacho: Mapped[str | None] = mapped_column(Text)


class PatenteRenumeracao(UUIDPrimaryKeyMixin, Base):
    """PATENTES_RENUMERACOES.csv"""

    __tablename__ = "patentes_renumeracoes"
    __table_args__ = (Index("ix_patentes_renum_codigo_interno", "codigo_interno"),)

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    numero_inpi_original: Mapped[str | None] = mapped_column(String(32))


class PatenteVinculo(UUIDPrimaryKeyMixin, Base):
    """PATENTES_VINCULOS.csv"""

    __tablename__ = "patentes_vinculos"
    __table_args__ = (
        Index("ix_patentes_vinc_derivado", "codigo_interno_derivado"),
        Index("ix_patentes_vinc_origem", "codigo_interno_origem"),
    )

    codigo_interno_derivado: Mapped[str | None] = mapped_column(String(64))
    numero_inpi_derivado: Mapped[str | None] = mapped_column(String(32))
    codigo_interno_origem: Mapped[str | None] = mapped_column(String(64))
    numero_inpi_origem: Mapped[str | None] = mapped_column(String(32))
    data_vinculo: Mapped[object | None] = mapped_column(Date)
    tipo_vinculo: Mapped[str | None] = mapped_column(String(64))
