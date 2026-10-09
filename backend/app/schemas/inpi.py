"""INPI dataset / import / RPI schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    category: str
    source_url: str | None = None
    file_name: str | None = None
    file_size: int | None = None
    sha256: str | None = None
    reference_date: datetime | None = None
    downloaded_at: datetime | None = None
    status: str
    raw_path: str | None = None
    extracted_path: str | None = None
    meta: dict | None = None


class ImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    dataset_id: uuid.UUID | None
    started_at: datetime
    finished_at: datetime | None = None
    status: str
    rows_read: int
    rows_inserted: int
    rows_updated: int
    rows_skipped: int
    rows_failed: int
    error_count: int
    error_message: str | None = None
    duration_seconds: float | None = None
    meta: dict | None = None


class ImportErrorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    import_id: uuid.UUID
    dataset: str | None = None
    row_number: int | None = None
    raw_data: str | None = None
    error: str | None = None
    created_at: datetime


class RpiOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    number: str
    edition_date: datetime | None = None
    file_name: str | None = None
    file_size: int | None = None
    sha256: str | None = None
    source_url: str | None = None
    status: str


class SyncRequest(BaseModel):
    category: str | None = Field(
        default=None, description="marcas, patentes ou None para todos"
    )
    dataset: str | None = Field(default=None, description="Importar apenas este dataset")
    force: bool = Field(default=False, description="Reimportar mesmo se já importado")


class SyncResponse(BaseModel):
    started: list[str]
    message: str
