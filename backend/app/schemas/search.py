"""Search schemas for marcas and patentes."""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class Pagination(BaseModel):
    page: int = 1
    page_size: int = 20
    total: int = 0


class MarcaClassificacao(BaseModel):
    """A single classification entry (Nice / national / Vienna), as available."""

    tipo: str  # "nice" | "nacional" | "viena"
    codigo: str  # e.g. "35", "NCL(8) 20", "33 : 10"
    descricao: str | None = None  # only when present in the local data


class MarcaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    codigo_interno: str
    numero_inpi: str | None = None
    data_deposito: date | None = None
    data_concessao: date | None = None
    descricao_apresentacao: str | None = None
    descricao_natureza: str | None = None
    elemento_nominativo: str | None = None
    codigo_situacao: str | None = None
    descricao_situacao: str | None = None
    # --- Derived relation aggregates (no N+1; see routers/marcas.py) ----------
    # ``titulares`` is the source of truth; ``titular_principal`` / ``num_titulares``
    # are derived for presentation convenience only.
    titulares: list[str] = []
    titular_principal: str | None = None
    num_titulares: int = 0
    classificacoes: list[MarcaClassificacao] = []
    # Logotipo (imagem) baixado do pePI — ``marcas_logos``. ``tem_logo`` is True
    # only when a real image was stored; ``logo_status`` mirrors the download
    # status (OK / SEM_IMAGEM / ERROR / None when not yet processed).
    tem_logo: bool = False
    logo_status: str | None = None
    # Selective monitoring (section 4) -------------------------------------
    # True only when the *current user* keeps this marca under watch. Monitoring
    # is never global/automatic — see ``MarcaMonitoramento``.
    monitorada: bool = False
    monitoramento_id: uuid.UUID | None = None



class MarcaDetail(MarcaOut):
    data_publicacao: date | None = None
    data_vigencia: date | None = None
    traducao: str | None = None
    apostila: str | None = None
    depositantes: list[dict] = []
    # Representantes legais / procuradores associated with the processo, taken
    # from ``marcas_depositantes`` (name + CPF/CNPJ). Not a separate dataset.
    representantes_legais: list[dict] = []
    classificacoes_nacionais: list[dict] = []
    classificacoes_nice: list[dict] = []
    classificacoes_viena: list[dict] = []
    # Histórico de publicações (RPI) / despachos — ``marcas_despachos``.
    despachos: list[dict] = []


class PatenteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    codigo_interno: str
    numero_inpi: str | None = None
    data_deposito: date | None = None
    data_publicacao: date | None = None
    numero_pct: str | None = None
    titulo: str | None = None
    # Selective monitoring (section 4): true only for the current user's watch.
    monitorada: bool = False
    monitoramento_id: uuid.UUID | None = None


class PatenteDetail(PatenteOut):
    data_protocolo: date | None = None
    numero_wo: str | None = None
    data_publicacao_wo: date | None = None
    data_entrada_fase_nacional: date | None = None
    sigilo: str | None = None
    resumo: str | None = None
    depositantes: list[dict] = []
    inventores: list[dict] = []
    procuradores: list[dict] = []
    prioridades: list[dict] = []
    classificacoes_ipc: list[dict] = []
    despachos: list[dict] = []


class PaginatedMarcas(BaseModel):
    pagination: Pagination
    items: list[MarcaOut]


class PaginatedPatentes(BaseModel):
    pagination: Pagination
    items: list[PatenteOut]


# --- Selective monitoring (section 4) ---------------------------------------


class MonitoramentoUpdate(BaseModel):
    """Toggle the current user's monitoring of a single marca/patente."""

    active: bool = True
    notes: str | None = None


class MonitoramentoOut(BaseModel):
    """A user's selective-monitoring row, enriched with display fields.

    The watch row itself only stores ``codigo_interno``; the display fields
    (``titulo``/``numero_inpi``/``situacao``) are joined from the underlying
    marca/patente so the monitoring screen can list the watched items without a
    second request per row.
    """

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    tenant_id: uuid.UUID
    user_id: uuid.UUID
    codigo_interno: str
    tipo: str = "marca"
    active: bool
    notes: str | None = None
    monitored_at: datetime | None = None
    # Display fields (joined from marcas/patentes; None if the source row is gone).
    titulo: str | None = None
    numero_inpi: str | None = None
    situacao: str | None = None
    data_deposito: date | None = None
    # --- Enriched marca data (so the monitoring screen shows *everything*) ---
    # Datas/lifecycle
    data_publicacao: date | None = None
    data_concessao: date | None = None
    data_vigencia: date | None = None
    # Características
    descricao_apresentacao: str | None = None
    descricao_natureza: str | None = None
    # Titulares / classificação
    titulares: list[str] = []
    titular_principal: str | None = None
    num_titulares: int = 0
    # Despachos (histórico RPI) — agregados para exibição
    total_despachos: int = 0
    data_ultimo_despacho: date | None = None
    ultimo_despacho: str | None = None
    # Vencimento (prazo) — calculado a partir de ``data_vigencia``
    # ``dias_para_vencer`` é negativo quando já venceu; ``None`` sem vigência.
    dias_para_vencer: int | None = None
    vencido: bool = False
    vence_em_breve: bool = False
    # Logotipo
    tem_logo: bool = False
    logo_status: str | None = None


class PaginatedMonitoramentos(BaseModel):
    pagination: Pagination
    items: list[MonitoramentoOut]
