"""Search schemas for desenhos industriais (industrial designs)."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.search import Pagination


class DesenhoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    codigo_interno: str
    numero_inpi: str | None = None
    data_deposito: date | None = None
    data_concessao: date | None = None
    data_publicacao: date | None = None
    data_vigencia: date | None = None
    titulo: str | None = None
    codigo_situacao: str | None = None
    descricao_situacao: str | None = None
    # Derived aggregates (no N+1; see routers/desenhos.py)
    titulares: list[str] = []
    titular_principal: str | None = None
    num_titulares: int = 0
    classificacoes: list[str] = []
    # Figure/image (``desenhos_figuras``): True only when a real image was stored.
    tem_figura: bool = False
    figura_status: str | None = None
    # Selective monitoring (per user, never global).
    monitorada: bool = False
    monitoramento_id: uuid.UUID | None = None


class DesenhoDetail(DesenhoOut):
    figura: str | None = None  # embedded data URI when available
    depositantes: list[dict] = []
    autores: list[dict] = []
    procuradores: list[dict] = []
    classificacoes_locarno: list[dict] = []
    prioridades: list[dict] = []
    despachos: list[dict] = []
    conteudo: dict | None = None


class PaginatedDesenhos(BaseModel):
    pagination: Pagination
    items: list[DesenhoOut]
