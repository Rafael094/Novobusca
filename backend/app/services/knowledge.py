"""Base de conhecimento do assistente (RAG leve, sem dependências externas).

Carrega os arquivos Markdown de ``app/knowledge/``, divide-os em seções (por
cabeçalhos) e realiza **busca textual** para recuperar os trechos mais relevantes
a uma pergunta. É a etapa de *retrieval* do assistente: o texto recuperado é
enviado como contexto ao modelo (``app.services.deepseek``), que responde apenas
com base nele.

Decisões:

* **Sem novas dependências** — a busca é feita em memória com normalização
  (remoção de acentos, minúsculas) e pontuação BM25 simplificada, suficiente para
  dezenas de documentos.
* **Sem embeddings** — o projeto não possui ``pgvector``; a busca textual resolve o
  caso de uso (documentação do sistema) e mantém o deploy simples.
* **Recarga automática** — o índice é reindexado quando algum arquivo muda
  (verificação por ``mtime``), então editar um ``.md`` reflete nas respostas.
"""

from __future__ import annotations

import math
import re
import threading
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

# Raiz da base de conhecimento: app/knowledge (este arquivo é app/services/knowledge.py)
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

#: Stopwords pt-BR ignoradas na pontuação (mantidas curtas de propósito).
_STOPWORDS: frozenset[str] = frozenset(
    {
        "a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "no", "na",
        "nos", "nas", "um", "uma", "para", "por", "com", "sem", "que", "qual",
        "quais", "como", "onde", "quando", "porque", "se", "ao", "aos", "eu", "me",
        "meu", "minha", "seu", "sua", "ele", "ela", "isso", "isto", "sou", "eh",
        "sao", "ser", "esta", "the", "of",
    }
)


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _normalize(text: str) -> str:
    return _strip_accents((text or "").lower())


def _tokenize(text: str) -> list[str]:
    """Tokens alfanuméricos normalizados, sem stopwords de 2 letras."""
    raw = re.findall(r"[a-z0-9_./-]{2,}", _normalize(text))
    return [t for t in raw if t not in _STOPWORDS]


@dataclass
class Chunk:
    """Uma seção de um documento (unidade de recuperação)."""

    doc: str  # nome do arquivo (ex.: "04_nit_f1_comunicacoes.md")
    title: str  # título da seção (primeiro cabeçalho do chunk)
    heading_path: str  # caminho de cabeçalhos, ex.: "F1 > Documentos"
    text: str  # corpo completo da seção
    tokens: list[str] = field(default_factory=list)

    @property
    def source(self) -> str:
        return f"{self.doc} § {self.heading_path}" if self.heading_path else self.doc


@dataclass
class KnowledgeIndex:
    chunks: list[Chunk]
    df: dict[str, int]  # document frequency por termo
    avg_len: float

    def search(self, query: str, *, top_k: int = 5) -> list[tuple[Chunk, float]]:
        """BM25 simplificado sobre os chunks; retorna os melhores com score > 0."""
        query_tokens = _tokenize(query)
        if not query_tokens or not self.chunks:
            return []

        n = len(self.chunks)
        k1, b = 1.5, 0.75
        scores: dict[int, float] = {}
        for term in set(query_tokens):
            df = self.df.get(term, 0)
            if df == 0:
                continue
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            for idx, chunk in enumerate(self.chunks):
                tf = chunk.tokens.count(term)
                if tf == 0:
                    continue
                norm = 1 - b + b * (len(chunk.tokens) / (self.avg_len or 1))
                scores[idx] = scores.get(idx, 0.0) + idf * (
                    tf * (k1 + 1)
                ) / (tf + k1 * norm)

        # Bônus por correspondência no título (ajuda em perguntas tipo "onde vejo X").
        query_set = set(query_tokens)
        for idx, chunk in enumerate(self.chunks):
            title_tokens = set(_tokenize(chunk.heading_path))
            overlap = len(title_tokens & query_set)
            if overlap:
                scores[idx] = scores.get(idx, 0.0) + 0.75 * overlap

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return [(self.chunks[i], s) for i, s in ranked[:top_k] if s > 0]


# --- Construção e cache do índice -------------------------------------------

_lock = threading.Lock()
_cache: KnowledgeIndex | None = None
_cache_signature: tuple[tuple[str, float], ...] = ()

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")


def _split_sections(doc_name: str, content: str) -> list[Chunk]:
    """Divide um documento em chunks por cabeçalho, mantendo a hierarquia."""
    chunks: list[Chunk] = []
    heading_stack: list[str] = []
    current_title = doc_name
    current_lines: list[str] = []

    def flush() -> None:
        body = "\n".join(current_lines).strip()
        if not body:
            return
        path = " > ".join(heading_stack) if heading_stack else current_title
        text = f"# {path}\n\n{body}"
        chunks.append(
            Chunk(
                doc=doc_name,
                title=current_title,
                heading_path=path,
                text=text,
                tokens=_tokenize(text),
            )
        )

    for line in content.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            flush()
            current_lines = []
            level = len(match.group(1))
            title = match.group(2).strip()
            heading_stack = heading_stack[: level - 1]
            heading_stack.append(title)
            current_title = title
        else:
            current_lines.append(line)
    flush()
    return chunks


def _signature() -> tuple[tuple[str, float], ...]:
    if not KNOWLEDGE_DIR.exists():
        return ()
    return tuple(
        sorted(
            (p.name, p.stat().st_mtime)
            for p in KNOWLEDGE_DIR.glob("*.md")
            if p.is_file()
        )
    )


def build_index() -> KnowledgeIndex:
    """Lê todos os ``.md`` e monta o índice em memória."""
    chunks: list[Chunk] = []
    if KNOWLEDGE_DIR.exists():
        for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
            content = path.read_text(encoding="utf-8", errors="replace")
            chunks.extend(_split_sections(path.name, content))

    df: dict[str, int] = {}
    for chunk in chunks:
        for term in set(chunk.tokens):
            df[term] = df.get(term, 0) + 1
    avg_len = (sum(len(c.tokens) for c in chunks) / len(chunks)) if chunks else 0.0
    return KnowledgeIndex(chunks=chunks, df=df, avg_len=avg_len)


def get_index() -> KnowledgeIndex:
    """Índice com cache, recarregado quando algum arquivo muda."""
    global _cache, _cache_signature
    sig = _signature()
    if _cache is not None and sig == _cache_signature:
        return _cache
    with _lock:
        if _cache is None or sig != _cache_signature:
            _cache = build_index()
            _cache_signature = sig
        return _cache


def retrieve(query: str, *, top_k: int = 5) -> list[Chunk]:
    """Trechos mais relevantes para ``query`` (lista possivelmente vazia)."""
    return [chunk for chunk, _score in get_index().search(query, top_k=top_k)]


def context_block(query: str, *, top_k: int = 5, max_chars: int = 8000) -> str:
    """Bloco de contexto formatado para o prompt, respeitando ``max_chars``."""
    parts: list[str] = []
    used = 0
    for chunk in retrieve(query, top_k=top_k):
        block = f"[Fonte: {chunk.source}]\n{chunk.text}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n---\n".join(parts)


def user_context_block(query: str, *, top_k: int = 3, max_chars: int = 4000) -> str:
    """Bloco de contexto **para exibição ao usuário final** (sem jargão).

    Diferente de :func:`context_block` (usado no prompt da IA, que precisa da
    informação completa), aqui os trechos são higienizados para leitura por
    quem não é desenvolvedor:

    * remove a linha de citação da fonte ``[Fonte: ...]`` e o caminho de
      cabeçalhos repetido (``# A > B``);
    * remove frases de "Via API" / endpoints HTTP (``GET/POST /api/...``);
    * remove segmentos dinâmicos de rota (``[id]``).
    """
    parts: list[str] = []
    used = 0
    for chunk in retrieve(query, top_k=top_k):
        body = _clean_for_user(chunk.text)
        if not body:
            continue
        block = f"• {chunk.title}\n{body}\n"
        if used + len(block) > max_chars:
            break
        parts.append(block)
        used += len(block)
    return "\n".join(parts)


# Frases/linhas de API que só interessam a desenvolvedores.
_API_LINE_RE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)
_VIA_API_RE = re.compile(r"via\s+api\b", re.IGNORECASE)
_HEADING_LINE_RE = re.compile(r"^#{1,6}\s")
# Fragmentos que introduzem endpoints e ficam órfãos após a limpeza por linha.
_API_FRAGMENT_RES = (
    re.compile(r",?\s*\.?\s*a\s+api\s+[ée][^.]*\.?", re.IGNORECASE),  # "A API é <...>."
    re.compile(r",?\s*(a\s+)?api\s*:\s*[^.]*\.?", re.IGNORECASE),  # "API: <...>."
    re.compile(r"via\s+api\s*[^.]*\.?", re.IGNORECASE),  # "Via API <...>."
)

# Referências a "rota `/x`" e "endereço da página" → fala de interface.
_ROTA_REF_RE = re.compile(r",?\s*rota\s+`[^`]+`", re.IGNORECASE)
_ROTA_WORD_RE = re.compile(r"\brota\b\s*", re.IGNORECASE)


def _clean_for_user(text: str) -> str:
    """Higieniza um trecho de documentação para exibição ao usuário final."""
    from app.services import glossary  # import tardio evita ciclo na importação

    kept: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Cabeçalho markdown repetido (o título já é mostrado como rótulo).
        if _HEADING_LINE_RE.match(stripped):
            continue
        # Linhas que expõem endpoints HTTP.
        if _API_LINE_RE.search(stripped) or _VIA_API_RE.search(stripped):
            continue
        kept.append(line.rstrip())

    cleaned = "\n".join(kept).strip()

    # Remove fragmentos de API que sobraram (ex.: "A API é", "Via API ...").
    for pattern in _API_FRAGMENT_RES:
        cleaned = pattern.sub("", cleaned)
    # "rota `/x`" e a palavra "rota" não agregam para o usuário final.
    cleaned = _ROTA_REF_RE.sub("", cleaned)
    cleaned = _ROTA_WORD_RE.sub("", cleaned)
    # Espaços/pontuação duplicados após as remoções.
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\s+([.,;:])", r"\1", cleaned)
    cleaned = re.sub(r"\.\s*\.", ".", cleaned)

    return glossary.humanize(cleaned.strip())


def sources(query: str, *, top_k: int = 5) -> list[str]:
    """Rótulos das fontes recuperadas (para exibir na resposta)."""
    seen: list[str] = []
    for chunk in retrieve(query, top_k=top_k):
        if chunk.source not in seen:
            seen.append(chunk.source)
    return seen


def stats() -> dict[str, int]:
    """Números da base (útil para diagnóstico/status)."""
    index = get_index()
    docs = {c.doc for c in index.chunks}
    return {"documents": len(docs), "sections": len(index.chunks)}


__all__ = [
    "KNOWLEDGE_DIR",
    "Chunk",
    "KnowledgeIndex",
    "build_index",
    "context_block",
    "get_index",
    "retrieve",
    "sources",
    "stats",
    "user_context_block",
]
