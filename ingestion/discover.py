"""Dataset discovery.

Registers the declarative dataset catalog in ``inpi_dataset`` and (best-effort)
enriches each entry with the live ``Content-Length`` / ``Last-Modified`` from the
INPI portal. Discovery never downloads file *bodies* — only metadata — so it is
fast and safe to run repeatedly.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

import requests

from ingestion import db
from ingestion.config import CONFIG
from ingestion.datasets import DatasetSpec, resolve
from ingestion.util import build_session, get_logger

logger = get_logger(__name__)


def _head(session: requests.Session, url: str) -> tuple[int | None, datetime | None]:
    """Return (content_length, last_modified) for a URL, or (None, None)."""
    try:
        resp = session.head(url, timeout=CONFIG.http_timeout_seconds, allow_redirects=True)
        if resp.status_code >= 400:
            # Some CDNs reject HEAD; fall back to a ranged GET for the headers.
            resp = session.get(
                url,
                timeout=CONFIG.http_timeout_seconds,
                headers={"Range": "bytes=0-0"},
                stream=True,
            )
        length = resp.headers.get("Content-Length")
        size = int(length) if length and length.isdigit() else None
        last_mod = resp.headers.get("Last-Modified")
        parsed: datetime | None = None
        if last_mod:
            try:
                parsed = datetime.strptime(last_mod, "%a, %d %b %Y %H:%M:%S %Z").replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                parsed = None
        resp.close()
        return size, parsed
    except requests.RequestException as exc:  # pragma: no cover - network
        logger.warning("HEAD failed for %s: %s", url, exc)
        return None, None


def discover(spec: DatasetSpec, *, session: requests.Session | None = None) -> str:
    """Register a single dataset, enriching with live metadata when possible."""
    url = CONFIG.inpi_base_url + spec.path
    session = session or build_session()
    size, last_mod = _head(session, url)

    dataset_id = db.upsert_dataset(
        name=spec.name,
        category=spec.category,
        source_url=url,
        status="DISCOVERED",
        file_name=spec.path.rsplit("/", 1)[-1],
        file_size=size,
        meta={
            "kind": spec.kind,
            "target_table": spec.target_table,
            "description": spec.description,
            "last_modified": last_mod.isoformat() if last_mod else None,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    logger.info(
        "Discovered %-32s size=%-10s table=%s",
        spec.name,
        size,
        spec.target_table or "-",
    )
    return dataset_id


def discover_all(targets: list[str] | None = None) -> list[str]:
    session = build_session()
    ids: list[str] = []
    for spec in resolve(targets):
        ids.append(discover(spec, session=session))
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover INPI datasets.")
    parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Category to discover (marcas, patentes). Repeatable.",
    )
    parser.add_argument(
        "--dataset",
        action="append",
        dest="datasets",
        help="Specific dataset name to discover. Repeatable.",
    )
    args = parser.parse_args(argv)
    targets = (args.categories or []) + (args.datasets or [])
    ids = discover_all(targets or None)
    print(f"Discovered {len(ids)} dataset(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
