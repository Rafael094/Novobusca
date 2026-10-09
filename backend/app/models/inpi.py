"""INPI ingestion tracking ORM models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class InpiDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Registry of every dataset discovered/downloaded from the INPI portal."""

    __tablename__ = "inpi_dataset"
    __table_args__ = (
        UniqueConstraint("name", name="uq_inpi_dataset_name"),
        Index("ix_inpi_dataset_category", "category"),
        Index("ix_inpi_dataset_status", "status"),
    )

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)  # marcas/patentes/rpi
    source_url: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    reference_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    downloaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # DISCOVERED, DOWNLOADING, DOWNLOADED, EXTRACTING, EXTRACTED, IMPORTING,
    # IMPORTED, FAILED
    status: Mapped[str] = mapped_column(String(32), default="DISCOVERED", nullable=False)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)
    raw_path: Mapped[str | None] = mapped_column(Text)
    extracted_path: Mapped[str | None] = mapped_column(Text)

    imports: Mapped[list["InpiImport"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class InpiImport(UUIDPrimaryKeyMixin, Base):
    """A single import execution (run) for a dataset."""

    __tablename__ = "inpi_import"
    __table_args__ = (Index("ix_inpi_import_dataset", "dataset_id"),)

    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("inpi_dataset.id", ondelete="CASCADE")
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="RUNNING", nullable=False)
    rows_read: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    rows_inserted: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    rows_updated: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    rows_skipped: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    rows_failed: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[float | None] = mapped_column()
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)

    dataset: Mapped["InpiDataset | None"] = relationship(back_populates="imports")
    errors: Mapped[list["InpiImportError"]] = relationship(
        back_populates="import_run", cascade="all, delete-orphan"
    )


class InpiImportError(UUIDPrimaryKeyMixin, Base):
    """A per-row import failure; enables later reprocessing."""

    __tablename__ = "inpi_import_error"
    __table_args__ = (Index("ix_inpi_import_error_import", "import_id"),)

    import_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("inpi_import.id", ondelete="CASCADE"), nullable=False
    )
    dataset: Mapped[str | None] = mapped_column(String(128))
    row_number: Mapped[int | None] = mapped_column(BigInteger)
    raw_data: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    import_run: Mapped["InpiImport"] = relationship(back_populates="errors")


class InpiImportCheckpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Resumable import checkpoint: last processed row / batch for a dataset."""

    __tablename__ = "inpi_import_checkpoint"
    __table_args__ = (
        UniqueConstraint("dataset_id", "target_table", name="uq_inpi_checkpoint"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("inpi_dataset.id", ondelete="CASCADE"), nullable=False
    )
    target_table: Mapped[str] = mapped_column(String(128), nullable=False)
    last_row_number: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_rows: Mapped[int | None] = mapped_column(BigInteger)
    completed: Mapped[bool] = mapped_column(default=False, nullable=False)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)


class InpiRpi(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """RPI (Revista da Propriedade Industrial) publication tracking."""

    __tablename__ = "inpi_rpi"
    __table_args__ = (
        UniqueConstraint("number", name="uq_inpi_rpi_number"),
        Index("ix_inpi_rpi_status", "status"),
    )

    number: Mapped[str] = mapped_column(String(32), nullable=False)
    edition_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str | None] = mapped_column(String(64))
    source_url: Mapped[str | None] = mapped_column(Text)
    # DISCOVERED, DOWNLOADED, PROCESSING, PROCESSED, FAILED
    status: Mapped[str] = mapped_column(String(32), default="DISCOVERED", nullable=False)
    raw_path: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)
