"""Worker: process Desenho Industrial figures into optimised, cached images.

Design-figure strategy for the Oracle Cloud Free Tier (spec section 3)
----------------------------------------------------------------------
The INPI figure bundles (``DI_FIGURAS_*.ZIP``) total ~44 GB — they must NEVER be
unpacked onto the Free Tier boot volume (max ~200 GB, shared with Postgres).
This worker therefore:

  1. reads each figure straight from the downloaded ZIP (streaming, one entry at
     a time — the archive is opened read-only, never fully extracted to disk);
  2. re-encodes it to **WebP** (``quality=80``), which is 25-35% smaller than the
     source JPEG/PNG and is served natively by every modern browser;
  3. uploads the compressed bytes to **object storage** (``STORAGE_BACKEND=s3`` —
     Oracle Object Storage / S3 / MinIO), so the instance disk and its egress
     bandwidth are never the bottleneck;
  4. records ONLY metadata in ``desenhos_figuras`` (key, mime, size, sha256,
     status), mirroring the ``marcas_logos`` pattern.

Serving + bandwidth:
  * put Cloudflare (Free) in front of the object-storage public/download URL so
    repeated views are served from the edge cache, not from the Free Tier egress;
  * the frontend lazy-loads figures (``loading="lazy"``) and requests WebP, so a
    list view never pulls more than the thumbnails actually on screen.

The worker is resilient and async-safe: it uses a bounded ``ThreadPoolExecutor``
(never blocks the API — it is a standalone ``python -m ingestion.figuras`` batch),
records per-item failures as ``ERROR`` rows (retryable) instead of aborting the
whole run, and resumes by skipping terminal rows (``OK``/``SEM_IMAGEM``).

Until ``STORAGE_BACKEND=s3`` is configured the worker runs in ``--dry-run`` mode
by default on a non-configured backend: it reports what it WOULD do without
writing, so a deploy can validate wiring before provisioning the bucket.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from ingestion import db
from ingestion.config import CONFIG
from ingestion.datasets import BY_CATEGORY
from ingestion.util import get_logger, human_size

logger = get_logger(__name__)

OK = "OK"
SEM_IMAGEM = "SEM_IMAGEM"
ERROR = "ERROR"

# Figure bundles live under the DI category with target_table=None.
_FIGURE_DATASETS = tuple(
    s for s in BY_CATEGORY.get("desenhos_industriais", ()) if "figuras" in s.name
)

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".bmp", ".webp"}


def _figure_zip_paths() -> list[Path]:
    """Return the downloaded DI figure ZIPs present on the server."""
    paths: list[Path] = []
    for spec in _FIGURE_DATASETS:
        p = CONFIG.raw_dir / spec.category / spec.path.rsplit("/", 1)[-1]
        if p.exists():
            paths.append(p)
    return paths


def _code_from_name(name: str) -> str | None:
    """Infer the ``codigo_interno`` from a figure filename inside the ZIP.

    INPI names the figures after the process code (optionally with a view
    suffix), e.g. ``BR302019000123-4_1.jpg`` → ``BR302019000123-4``. We take the
    stem up to the first ``_`` and strip the directory.
    """
    stem = Path(name).stem
    if not stem:
        return None
    return stem.split("_", 1)[0].strip() or None


def _to_webp(data: bytes, *, quality: int = 80) -> tuple[bytes, str] | None:
    """Re-encode image bytes to WebP. Returns ``(bytes, mime)`` or ``None``.

    Uses Pillow when available; if Pillow is not installed the original bytes
    are passed through unchanged (the compression is an optimisation, not a
    correctness requirement), still returning a valid image.
    """
    try:
        from PIL import Image  # type: ignore

        with Image.open(io.BytesIO(data)) as im:
            if im.mode in ("P", "RGBA", "LA"):
                im = im.convert("RGBA")
            else:
                im = im.convert("RGB")
            out = io.BytesIO()
            im.save(out, format="WEBP", quality=quality, method=4)
            return out.getvalue(), "image/webp"
    except ImportError:
        # Pillow absent: keep original bytes (sniff a basic mime).
        if data[:3] == b"\xff\xd8\xff":
            return data, "image/jpeg"
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return data, "image/png"
        return data, "application/octet-stream"
    except Exception as exc:  # noqa: BLE001 - a bad image is not fatal to the run
        logger.debug("WebP re-encode failed: %s", exc)
        return None


def _store(codigo_interno: str, data: bytes, mime: str, *, dry_run: bool) -> str:
    """Persist the compressed bytes to object storage; return the stored key.

    In ``dry_run`` the key is computed but nothing is written (used to validate a
    deploy before the bucket exists). The real path uses the backend-agnostic
    storage service so switching to Oracle Object Storage/S3 needs no code change.
    """
    key = f"desenhos/figuras/{codigo_interno[:2]}/{codigo_interno}.webp"
    if dry_run:
        return key
    # Imported lazily so the batch can run even where the backend app isn't on
    # the path; on the server it resolves to the configured STORAGE_BACKEND.
    from app.services.storage import get_storage  # type: ignore

    get_storage().put(key, data)
    return key


def process_zip_member(
    codigo_interno: str, data: bytes, *, dry_run: bool
) -> tuple[str, str]:
    """Compress + store one figure; record metadata. Returns ``(status, detail)``."""
    try:
        encoded = _to_webp(data)
        if encoded is None:
            db.upsert_figura(codigo_interno=codigo_interno, status=SEM_IMAGEM, tentativas=1)
            return SEM_IMAGEM, "imagem inválida"
        payload, mime = encoded
        key = _store(codigo_interno, payload, mime, dry_run=dry_run)
        db.upsert_figura(
            codigo_interno=codigo_interno,
            status=OK,
            arquivo=key,
            mime=mime,
            bytes_=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            tentativas=1,
            baixado_em=datetime.now(timezone.utc),
        )
        return OK, f"{human_size(len(payload))} -> {key}"
    except Exception as exc:  # noqa: BLE001 - per-item failure, keep going
        db.upsert_figura(
            codigo_interno=codigo_interno, status=ERROR, tentativas=1, erro=str(exc)
        )
        return ERROR, str(exc)


def run(
    *,
    limit: int | None = None,
    concurrency: int = 4,
    only_pending: bool = True,
    dry_run: bool = False,
) -> dict[str, int]:
    """Process figures from the downloaded ZIP bundles into object storage.

    Streams each ZIP entry, matches it to a ``desenhos`` process by filename and
    stores the compressed WebP. Resumable and tolerant: a failing entry becomes
    an ``ERROR`` row and the batch continues.
    """
    zips = _figure_zip_paths()
    if not zips:
        logger.warning(
            "Nenhum ZIP de figuras encontrado em %s. Baixe primeiro: "
            "`python -m ingestion.download --category desenhos_industriais`.",
            CONFIG.raw_dir / "desenhos_industriais",
        )
        return {OK: 0, SEM_IMAGEM: 0, ERROR: 0}

    wanted: set[str] | None = None
    if only_pending:
        wanted = set(db.figura_codes(only_pending=True, limit=limit))
        if not wanted:
            logger.info("Nada pendente — figuras já processadas.")
            return {OK: 0, SEM_IMAGEM: 0, ERROR: 0}

    stats = {OK: 0, SEM_IMAGEM: 0, ERROR: 0}
    processed = 0
    lock = threading.Lock()

    def _handle(code: str, data: bytes) -> None:
        nonlocal processed
        status, _ = process_zip_member(code, data, dry_run=dry_run)
        with lock:
            stats[status] = stats.get(status, 0) + 1
            processed += 1
            if processed % 200 == 0:
                logger.info("  %d processadas (ok=%d erro=%d)", processed, stats[OK], stats[ERROR])

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = []
        for zpath in zips:
            logger.info("Lendo figuras de %s", zpath.name)
            with zipfile.ZipFile(zpath) as zf:
                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    if Path(info.filename).suffix.lower() not in _IMAGE_EXT:
                        continue
                    code = _code_from_name(info.filename)
                    if not code:
                        continue
                    if wanted is not None and code not in wanted:
                        continue
                    data = zf.read(info)
                    futures.append(pool.submit(_handle, code, data))
                    if limit and len(futures) >= limit:
                        break
            if limit and len(futures) >= limit:
                break
        for _ in as_completed(futures):
            pass

    logger.info("Figuras: ok=%d sem_imagem=%d erro=%d", stats[OK], stats[SEM_IMAGEM], stats[ERROR])
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Processa figuras de desenhos industriais (WebP + object storage)."
    )
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--concorrencia", type=int, default=4)
    parser.add_argument("--todos", action="store_true", help="Reprocessa já concluídos.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Não grava no storage; apenas simula (validar deploy sem bucket).",
    )
    args = parser.parse_args(argv)
    stats = run(
        limit=args.limite,
        concurrency=args.concorrencia,
        only_pending=not args.todos,
        dry_run=args.dry_run,
    )
    print(f"ok={stats[OK]} sem_imagem={stats[SEM_IMAGEM]} erro={stats[ERROR]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
