"""Schemas do assistente (chat) baseado na documentação do sistema."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Uma mensagem do histórico (papel + conteúdo)."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    """Pergunta do usuário, opcionalmente com histórico recente."""

    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Resposta do assistente com as fontes usadas da base de conhecimento."""

    answer: str
    sources: list[str] = Field(default_factory=list)
    ai_available: bool = True
    model: str | None = None


class ChatStatus(BaseModel):
    """Estado do assistente: se a IA está configurada e o tamanho da base."""

    configured: bool
    model: str
    documents: int
    sections: int
    message: str
