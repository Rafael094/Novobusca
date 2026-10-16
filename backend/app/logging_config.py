"""Structured logging and per-request correlation id.

Provides a minimal, dependency-free JSON formatter and a ``contextvars``-based
request id so that every log line emitted while handling a request carries a
correlation id. This mirrors the project's zero-extra-dependency approach (see
``rate_limit.py``) and does not change any API contract.

Usage (already wired in ``app.main``):
    * ``setup_logging()`` — configure the root logger once at startup;
    * ``RequestIdMiddleware`` — assign ``X-Request-ID`` (incoming or generated),
      expose it via the ``X-Request-ID`` response header and make it available
      through :func:`current_request_id`.
"""

from __future__ import annotations

import json
import logging
import sys
import uuid
from contextvars import ContextVar

# --- Request id --------------------------------------------------------------

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

REQUEST_ID_HEADER = "X-Request-ID"


def new_request_id() -> str:
    return uuid.uuid4().hex


def set_request_id(value: str) -> None:
    _request_id.set(value)


def current_request_id() -> str | None:
    return _request_id.get()


class RequestIdFilter(logging.Filter):
    """Injects ``request_id`` into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = current_request_id() or "-"
        return True


# --- JSON formatter ----------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """Render log records as single-line JSON objects.

    Extra ``context`` supplied via ``logger.info(..., extra={"context": {...}})``
    is merged into the payload. Exceptions are rendered as ``exception`` text
    (never returned to the client — only written to the log).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or "-",
        }
        context = getattr(record, "context", None)
        if isinstance(context, dict):
            payload.update(context)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with the JSON formatter (idempotent)."""
    root = logging.getLogger()
    if any(isinstance(h.formatter, JsonFormatter) for h in root.handlers):
        return  # already configured
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    root.handlers = [handler]
    root.setLevel(level)
    # Align uvicorn's loggers with the structured output.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True
