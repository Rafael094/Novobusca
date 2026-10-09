"""Normalized ORM models for the INPI trademarks (marcas) datasets.

Column names mirror the official INPI CSVs exactly (source columns preserved),
plus a few normalised columns for search. Keyed by (codigo_interno, numero_inpi).
"""

from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class Marca(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """MARCAS_DADOS_BIBLIOGRAFICOS.csv"""

    __tablename__ = "marcas"
    __table_args__ = (
        UniqueConstraint("codigo_interno", name="uq_marcas_codigo_interno"),
        Index("ix_marcas_numero_inpi", "numero_inpi"),
        Index("ix_marcas_codigo_situacao", "codigo_situacao"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    data_deposito: Mapped[object | None] = mapped_column(Date)
    data_publicacao: Mapped[object | None] = mapped_column(Date)
    data_concessao: Mapped[object | None] = mapped_column(Date)
    data_vigencia: Mapped[object | None] = mapped_column(Date)
    descricao_apresentacao: Mapped[str | None] = mapped_column(Text)
    descricao_natureza: Mapped[str | None] = mapped_column(Text)
    elemento_nominativo: Mapped[str | None] = mapped_column(Text)
    traducao: Mapped[str | None] = mapped_column(Text)
    apostila: Mapped[str | None] = mapped_column(Text)
    codigo_situacao: Mapped[str | None] = mapped_column(String(16))
    descricao_situacao: Mapped[str | None] = mapped_column(Text)

    depositantes: Mapped[list["MarcaDepositante"]] = relationship(
        primaryjoin="Marca.codigo_interno == foreign(MarcaDepositante.codigo_interno)",
        viewonly=True,
    )


class MarcaDepositante(UUIDPrimaryKeyMixin, Base):
    """MARCAS_DEPOSITANTES.csv"""

    __tablename__ = "marcas_depositantes"
    __table_args__ = (
        Index("ix_marcas_dep_codigo_interno", "codigo_interno"),
        Index("ix_marcas_dep_nome", "nome"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    nome: Mapped[str | None] = mapped_column(Text)
    cnpj_cpf_titular: Mapped[str | None] = mapped_column(String(32))
    tipo_pfpj_titular: Mapped[str | None] = mapped_column(String(16))
    nome_representante_legal: Mapped[str | None] = mapped_column(Text)
    cnpj_cpf_representante_legal: Mapped[str | None] = mapped_column(String(32))
    tipo_pfpj_representante_legal: Mapped[str | None] = mapped_column(String(16))
    estado: Mapped[str | None] = mapped_column(String(64))
    pais: Mapped[str | None] = mapped_column(String(64))


class MarcaClassificacaoNacional(UUIDPrimaryKeyMixin, Base):
    """MARCAS_CLASSIFICACOES_NACIONAIS.csv"""

    __tablename__ = "marcas_classificacoes_nacionais"
    __table_args__ = (Index("ix_marcas_cn_codigo_interno", "codigo_interno"),)

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    classe: Mapped[str | None] = mapped_column(String(32))
    primeira_subclasse: Mapped[str | None] = mapped_column(String(32))
    segunda_subclasse: Mapped[str | None] = mapped_column(String(32))
    terceira_subclasse: Mapped[str | None] = mapped_column(String(32))
    especificacao: Mapped[str | None] = mapped_column(Text)


class MarcaClassificacaoNice(UUIDPrimaryKeyMixin, Base):
    """MARCAS_CLASSIFICACOES_NICE.csv"""

    __tablename__ = "marcas_classificacoes_nice"
    __table_args__ = (Index("ix_marcas_nice_codigo_interno", "codigo_interno"),)

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    edicao_nice: Mapped[str | None] = mapped_column(String(16))
    classe_nice: Mapped[str | None] = mapped_column(String(16))
    especificacao: Mapped[str | None] = mapped_column(Text)
    especificacao_trad: Mapped[str | None] = mapped_column(Text)


class MarcaClassificacaoViena(UUIDPrimaryKeyMixin, Base):
    """MARCAS_CLASSIFICACOES_VIENA.csv"""

    __tablename__ = "marcas_classificacoes_viena"
    __table_args__ = (Index("ix_marcas_viena_codigo_interno", "codigo_interno"),)

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    simbolo: Mapped[str | None] = mapped_column(String(32))
    classificacao_viena: Mapped[str | None] = mapped_column(Text)
    revisao_viena: Mapped[str | None] = mapped_column(String(32))


class MarcaDespacho(UUIDPrimaryKeyMixin, Base):
    """MARCAS_DESPACHOS.csv"""

    __tablename__ = "marcas_despachos"
    __table_args__ = (
        Index("ix_marcas_desp_codigo_interno", "codigo_interno"),
        Index("ix_marcas_desp_codigo_despacho", "codigo_despacho"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    numero_inpi: Mapped[str | None] = mapped_column(String(32))
    numero_rpi: Mapped[str | None] = mapped_column(String(32))
    data_rpi: Mapped[object | None] = mapped_column(Date)
    codigo_despacho: Mapped[str | None] = mapped_column(String(32))
    descricao_despacho: Mapped[str | None] = mapped_column(Text)
    complemento_despacho: Mapped[str | None] = mapped_column(Text)


class MarcaLogo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Locally downloaded marca logotipo (pePI ``LogoMarcasServletController``).

    The image binary is stored on disk (``data/raw/marcas/logos/<bucket>/<cod>.jpg``);
    this row records the *metadata* so the API can decide whether an image exists
    without touching the filesystem and so the downloader can resume.

    NOT part of the INPI open-data CSVs: this is an additional asset fetched from
    the public pePI image servlet (anonymous session). ``status`` semantics:

      * ``OK``         — real image downloaded and stored;
      * ``SEM_IMAGEM`` — the servlet returned its "no image" placeholder;
      * ``ERROR``      — transient/permanent failure (see ``erro``).
    """

    __tablename__ = "marcas_logos"
    __table_args__ = (
        UniqueConstraint("codigo_interno", name="uq_marcas_logos_codigo_interno"),
        Index("ix_marcas_logos_status", "status"),
    )

    codigo_interno: Mapped[str] = mapped_column(String(64), nullable=False)
    arquivo: Mapped[str | None] = mapped_column(Text)
    mime: Mapped[str | None] = mapped_column(String(64))
    bytes: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING")
    tentativas: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    erro: Mapped[str | None] = mapped_column(Text)
    baixado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
