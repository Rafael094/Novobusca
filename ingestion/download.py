"""Streaming downloader for INPI datasets.

Downloads are streamed to disk with progress logging, a bounded retry policy and
optional resume from a partial ``.part`` file. On success the SHA-256 digest and
real size are persisted so re-runs can skip unchanged files (unless ``force``).
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from ingestion import db
from ingestion.config import CONFIG
from ingestion.datasets import DatasetSpec, resolve
from ingestion.util import build_session, ensure_dirs, get_logger, human_size, sha256_file

logger = get_logger(__name__)


def _target_path(spec: DatasetSpec) -> Path:
    return CONFIG.raw_dir / spec.category / spec.path.rsplit("/", 1)[-1]


def _download_once(
    session: requests.Session, url: str, dest: Path, *, resume_from: int
) -> None:
    headers = {}
    mode = "wb"
    if resume_from > 0:
        headers["Range"] = f"bytes={resume_from}-"
        mode = "ab"

    with session.get(
        url,
        stream=True,
        timeout=CONFIG.http_timeout_seconds,
        headers=headers,
    ) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0)) + resume_from
        downloaded = resume_from
        last_log = time.monotonic()
        with dest.open(mode) as fh:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                fh.write(chunk)
                downloaded += len(chunk)
                now = time.monotonic()
                if now - last_log >= 5:
                    pct = f"{downloaded / total * 100:.1f}%" if total else "?"
                    logger.info(
                        "  %s  %s / %s", pct, human_size(downloaded), human_size(total)
                    )
                    last_log = now


def download(spec: DatasetSpec, *, force: bool = False, session: requests.Session | None = None) -> Path:
    """Download one dataset; returns the local path. Skips if already present."""
    url = CONFIG.inpi_base_url + spec.path
    target = _target_path(spec)
    ensure_dirs(target.parent)

    if target.exists() and not force:
        size = target.stat().st_size
        if size > 0:
            logger.info("Already downloaded: %s (%s)", spec.name, human_size(size))
            db.set_dataset_status(
                spec.name,
                "DOWNLOADED",
                file_size=size,
                sha256=sha256_file(target),
                raw_path=str(target),
            )
            return target

    session = session or build_session()
    part = target.with_suffix(target.suffix + ".part")

    attempt = 0
    last_exc: Exception | None = None
    while attempt <= CONFIG.http_retries:
        attempt += 1
        resume_from = part.stat().st_size if part.exists() else 0
        try:
            logger.info(
                "Downloading %s (attempt %d, resume=%s)",
                spec.name,
                attempt,
                human_size(resume_from),
            )
            db.set_dataset_status(spec.name, "DOWNLOADING")
            _download_once(session, url, part, resume_from=resume_from)
            part.replace(target)
            break
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("Attempt %d failed: %s", attempt, exc)
            time.sleep(min(2 ** attempt, 30))
    else:  # pragma: no cover - only on total failure
        db.set_dataset_status(spec.name, "FAILED", meta={"error": str(last_exc)})
        raise RuntimeError(f"Failed to download {spec.name}: {last_exc}")

    size = target.stat().st_size
    digest = sha256_file(target)
    db.set_dataset_status(
        spec.name,
        "DOWNLOADED",
        file_size=size,
        sha256=digest,
        raw_path=str(target),
        meta={
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
            "sha256": digest,
        },
    )
    logger.info("Downloaded %s (%s)", spec.name, human_size(size))
    return target


def download_all(targets: list[str] | None = None, *, force: bool = False) -> dict[str, Path]:
    session = build_session()
    results: dict[str, Path] = {}
    for spec in resolve(targets):
        results[spec.name] = download(spec, force=force, session=session)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download INPI datasets.")
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--dataset", action="append", dest="datasets")
    parser.add_argument("--force", action="store_true", help="Re-download existing files.")
    args = parser.parse_args(argv)
    targets = (args.categories or []) + (args.datasets or [])
    paths = download_all(targets or None, force=args.force)
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
