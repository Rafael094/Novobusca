"""Extraction of ZIP bundles.

For ZIP datasets (e.g. ``marcas.zip``) the archive is extracted into
``data/extracted/<category>/``. CSV datasets are treated as already
"extracted" — the raw file *is* the import source.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from ingestion import db
from ingestion.config import CONFIG
from ingestion.datasets import DatasetSpec, resolve
from ingestion.util import ensure_dirs, get_logger

logger = get_logger(__name__)


def raw_path(spec: DatasetSpec) -> Path:
    return CONFIG.raw_dir / spec.category / spec.path.rsplit("/", 1)[-1]


def extracted_dir(spec: DatasetSpec) -> Path:
    return CONFIG.extracted_dir / spec.category / spec.name


def extract(spec: DatasetSpec, *, force: bool = False) -> Path:
    """Extract a dataset (or pass through a CSV); returns the extracted path."""
    src = raw_path(spec)
    if not src.exists():
        raise FileNotFoundError(f"Raw file not found for {spec.name}: {src}")

    if spec.is_csv:
        db.set_dataset_status(spec.name, "EXTRACTED", extracted_path=str(src))
        logger.info("CSV %s needs no extraction.", spec.name)
        return src

    out_dir = extracted_dir(spec)
    if out_dir.exists() and any(out_dir.iterdir()) and not force:
        logger.info("Already extracted: %s", spec.name)
        db.set_dataset_status(spec.name, "EXTRACTED", extracted_path=str(out_dir))
        return out_dir

    ensure_dirs(out_dir)
    logger.info("Extracting %s -> %s", src.name, out_dir)
    with zipfile.ZipFile(src) as zf:
        _safe_extractall(zf, out_dir)
    db.set_dataset_status(spec.name, "EXTRACTED", extracted_path=str(out_dir))
    logger.info("Extracted %s", spec.name)
    return out_dir


def _safe_extractall(zf: zipfile.ZipFile, dest: Path) -> None:
    """Extract, guarding against path traversal (zip-slip)."""
    dest_resolved = dest.resolve()
    for member in zf.infolist():
        target = (dest / member.filename).resolve()
        if not str(target).startswith(str(dest_resolved)):
            raise RuntimeError(f"Unsafe path in archive: {member.filename}")
    zf.extractall(dest)


def extract_all(targets: list[str] | None = None, *, force: bool = False) -> dict[str, Path]:
    results: dict[str, Path] = {}
    for spec in resolve(targets):
        results[spec.name] = extract(spec, force=force)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract INPI datasets.")
    parser.add_argument("--category", action="append", dest="categories")
    parser.add_argument("--dataset", action="append", dest="datasets")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    targets = (args.categories or []) + (args.datasets or [])
    paths = extract_all(targets or None, force=args.force)
    for name, path in paths.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
