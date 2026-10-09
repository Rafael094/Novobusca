"""DeepSeek LLM client for trademark risk analysis.

The client is real, not a mock: it performs an HTTPS ``chat/completions`` call to
DeepSeek when ``DEEPSEEK_API_KEY`` is configured. When the key is absent (or the
upstream call fails) it raises a typed error so the caller can degrade
explicitly (HTTP 503) instead of returning fabricated results — matching the
project-wide "never fake results" policy (see routers/admin/inpi_sync.py).

Only the standard library is used (``urllib``), so no extra dependency is
required to deploy the feature.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.config import settings


class DeepSeekError(RuntimeError):
    """Raised when the DeepSeek API cannot be reached or returns an error."""


class DeepSeekNotConfigured(DeepSeekError):
    """Raised when no API key is configured for DeepSeek."""


@dataclass(frozen=True)
class DeepSeekResult:
    content: str
    model: str


def is_configured() -> bool:
    return bool(settings.deepseek_api_key)


def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: float | None = None,
    response_format_json: bool = False,
) -> DeepSeekResult:
    """Call the DeepSeek chat completions endpoint and return the message text.

    Raises ``DeepSeekNotConfigured`` when there is no API key and
    ``DeepSeekError`` on any transport/upstream failure.
    """
    if not is_configured():
        raise DeepSeekNotConfigured(
            "DEEPSEEK_API_KEY não configurada. Defina a chave para habilitar a "
            "análise de IA."
        )

    body: dict = {
        "model": settings.deepseek_model,
        "messages": messages,
        "temperature": (
            settings.deepseek_temperature if temperature is None else temperature
        ),
        "max_tokens": settings.deepseek_max_tokens if max_tokens is None else max_tokens,
        "stream": False,
    }
    if response_format_json:
        body["response_format"] = {"type": "json_object"}

    url = f"{settings.deepseek_base_url.rstrip('/')}/chat/completions"
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.deepseek_api_key}",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request, timeout=timeout or settings.deepseek_timeout_seconds
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:  # pragma: no cover - upstream dependent
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise DeepSeekError(
            f"DeepSeek retornou HTTP {exc.code}: {detail}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:  # pragma: no cover
        raise DeepSeekError(f"Falha ao contatar o DeepSeek: {exc}") from exc
    except json.JSONDecodeError as exc:  # pragma: no cover
        raise DeepSeekError("Resposta inválida do DeepSeek (JSON malformado)") from exc

    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:  # pragma: no cover
        raise DeepSeekError("Resposta do DeepSeek em formato inesperado") from exc

    return DeepSeekResult(content=content, model=payload.get("model", settings.deepseek_model))
