"""Search schemas for programas de computador (software)."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel, ConfigDict

from app.schemas.search import Pagination


class SoftwareOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    codigo_interno: str
    numero_inpi: str | None = None
    data_deposito: date | None = None
    data_concessao: date | None = None
    data_publicacao: date | None = None
    data_criacao: date | None = None
    titulo: str | None = None
    codigo_situacao: str | None = None
    descricao_situacao: str | None = None
    # Derived aggregates (no N+1; see routers/software.py)
    titulares: list[str] = []
    titular_principal: str | None = None
    num_titulares: int = 0
    linguagens: list[str] = []
    # Selective monitoring (per user, never global).
    monitorada: bool = False
    monitoramento_id: uuid.UUID | None = None


class SoftwareDetail(SoftwareOut):
    titulares_detalhe: list[dict] = []
    autores: list[dict] = []
    tipos: list[dict] = []
    campos: list[dict] = []
    despachos: list[dict] = []


class PaginatedSoftwares(BaseModel):
    pagination: Pagination
    items: list[SoftwareOut]
