"""Schemas for the AI trademark risk analysis (wizard + report)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

RiskLevel = Literal["baixo", "moderado", "alto", "critico"]


class AnalysisOptions(BaseModel):
    """Wizard analysis toggles."""

    include_patentes: bool = True
    include_fonetic: bool = True
    include_visual: bool = False
    strict_nice: bool = True


class AnalysisRequest(BaseModel):
    """Payload produced by the "Nova Análise de Marca com IA" wizard."""

    brand_name: str = Field(min_length=1, max_length=255)
    nice_classes: list[str] = Field(default_factory=list)
    holder: str | None = None
    presentation: str | None = None
    nature: str | None = None
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class ConflictOut(BaseModel):
    title: str
    score: int = Field(ge=0, le=100)
    level: RiskLevel
    description: str | None = None
    fonte: str | None = None


class SimilarBrandOut(BaseModel):
    nome: str | None = None
    numero_inpi: str | None = None
    situacao: str | None = None
    similaridade: int = Field(default=0, ge=0, le=100)
    classes: list[str] = Field(default_factory=list)


class RelatedPatentOut(BaseModel):
    titulo: str | None = None
    numero_inpi: str | None = None
    depositante: str | None = None
    relevancia: int = Field(default=0, ge=0, le=100)


class AnalysisReport(BaseModel):
    """Report returned by the AI analysis endpoint."""

    id: uuid.UUID | None = None
    brand_name: str
    holder: str | None = None
    nice_classes: list[str] = Field(default_factory=list)
    created_at: datetime
    overall_risk: RiskLevel
    score: int = Field(ge=0, le=100)
    summary: str
    conflicts: list[ConflictOut] = Field(default_factory=list)
    similar_brands: list[SimilarBrandOut] = Field(default_factory=list)
    related_patents: list[RelatedPatentOut] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    ai_available: bool = True
    model: str | None = None


class AnalysisStatus(BaseModel):
    """Whether the AI integration is configured and ready."""

    configured: bool
    model: str
    message: str
