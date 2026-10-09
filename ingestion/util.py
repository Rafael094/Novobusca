"""Small shared helpers for the ingestion pipeline."""

from __future__ import annotations

import hashlib
import logging
import sys
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

from ingestion.config import CONFIG

_LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Compute the SHA-256 hex digest of a file, streaming it in chunks."""
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def human_size(num_bytes: int | None) -> str:
    if not num_bytes:
        return "0 B"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def build_session() -> requests.Session:
    """Build a requests session with retries and a sane User-Agent."""
    session = requests.Session()
    session.headers.update({"User-Agent": CONFIG.user_agent})
    adapter = HTTPAdapter(max_retries=0)  # we retry manually for progress logging
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
