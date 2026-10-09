"""IntelliINPI ingestion pipeline.

Downloads the official INPI open datasets (Marcas, Patentes and the RPI),
extracts them, analyzes their schema and bulk-loads them into the local
PostgreSQL database using DuckDB/COPY with chunked, checkpointed, resumable
imports.

The package is intentionally standalone (importable both from the backend and
from the CLI). It reads its configuration from the shared backend settings so
there is a single source of truth for the database URL and data directory.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "1.0.0"
