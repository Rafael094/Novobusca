"""Marca logotipo access (DB-first; the offline worker does the fetching).

The INPI open-data CSVs carry no images. The pePI search application exposes
them publicly through an *anonymous* session: a ``GET`` on
``LoginController?action=login`` sets the session cookies, after which
``LogoMarcasServletController?Action=image&codProcesso=<codigo_interno>``
returns the JPEG for that process.

Logotipos are downloaded **by the offline worker** (``python -m
ingestion.logos``), which is resumable, polite and writes both the file and the
``marcas_logos`` row. The API is therefore **DB-first and read-only by default**:

1. the caller asks for a marca's logo;
2. if a real image is already stored (status ``OK``) it is returned without
   touching the network;
3. otherwise ``None`` is returned and the caller degrades to a placeholder.

The historical *on-demand* fetch (query INPI, download and store during an API
request) is still available behind ``allow_fetch=True`` / the
``LOGO_FETCH_ENABLED`` setting — kept only to preserve the code path for tests
and explicit opt-in. It is **off by default**: downloading inside a request
blocks the worker and duplicates the offline downloader.

The low-level fetch helpers (anonymous login, magic-byte sniffing, placeholder
detection, atomic write and sharding) mirror ``ingestion/logos.py`` so both
paths share the same on-disk layout. They are reimplemented here against the
backend ORM + settings because the backend must not import the standalone
``ingestion`` package.
"""

from __future__ import annotations

import base64
import hashlib
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Marca, MarcaLogo

# Magic-byte signatures we accept as a real image.
_JPEG = b"\xff\xd8\xff"
_PNG = b"\x89PNG\r\n\x1a\n"
_GIF = b"GIF8"

# Statuses (``OK``/``SEM_IMAGEM`` are terminal; ``PENDING``/``ERROR`` retry).
OK = "OK"
SEM_IMAGEM = "SEM_IMAGEM"
ERROR = "ERROR"

# Terminal statuses never trigger a fresh network round-trip.
_TERMINAL = {OK, SEM_IMAGEM}


def _sanitize_codigo(codigo_interno: str) -> str:
    """Guard the filesystem against path traversal in the INPI code."""
    return re.sub(r"[^A-Za-z0-9_-]", "_", (codigo_interno or "").strip())[:64]


def _bucket_dir(codigo_interno: str) -> Path:
    """Shard by the first two chars to avoid a single huge directory."""
    prefix = (codigo_interno or "_")[:2] or "_"
    return settings.logos_path / prefix


def _destino(codigo_interno: str, mime: str | None) -> Path:
    ext = ".png" if mime == "image/png" else ".jpg"
    return _bucket_dir(codigo_interno) / f"{_sanitize_codigo(codigo_interno)}{ext}"


def _rel_arquivo(path: Path) -> str:
    """Store a path relative to the data dir, always POSIX-style (portable).

    ``as_posix()`` matters: on Windows ``str(Path)`` yields
    ``raw\\marcas\\logos\\44\\x.jpg``; the very same value read back on Linux is
    a *single* filename, so the image would look "stored" in ``marcas_logos`` but
    be unresolvable by the API.
    """
    try:
        return path.relative_to(settings.data_path).as_posix()
    except ValueError:
        return str(path)


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)


class _PepiSession:
    """An anonymous pePI session (login + image fetch)."""

    def __init__(self) -> None:
        self._client = httpx.Client(
            timeout=settings.logo_http_timeout_seconds,
            follow_redirects=True,
            verify=True,
            headers={"User-Agent": "IntelliINPI/1.0 (+https://localhost)"},
        )
        self.logged_in = False

    def login(self) -> None:
        resp = self._client.get(
            f"{settings.pepi_base_url}/servlet/LoginController?action=login"
        )
        resp.raise_for_status()
        self.logged_in = True

    def fetch(self, codigo_interno: str) -> tuple[str, bytes, str | None]:
        """Return ``(kind, data, mime)`` with kind in image/placeholder/html."""
        if not self.logged_in:
            self.login()
        resp = self._client.get(
            f"{settings.pepi_base_url}/servlet/LogoMarcasServletController",
            params={"Action": "image", "codProcesso": codigo_interno},
        )
        resp.raise_for_status()
        data = resp.content
        ctype = (resp.headers.get("Content-Type") or "").lower()

        if data[:3] == _JPEG:
            return "image", data, "image/jpeg"
        if data[:8] == _PNG:
            return "image", data, "image/png"
        if data[:4] == _GIF:
            # The servlet serves its "no image" placeholder as a GIF (often with
            # a misleading ``image/jpg`` header). A real marca image is never a
            # GIF here, so every GIF means "no image".
            return "placeholder", data, ctype or "image/gif"
        if "text/html" in ctype or b"<html" in data[:2048].lower():
            return "html", data, ctype or "text/html"
        return "placeholder", data, ctype or None

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass


class _SessionPool:
    """Lazily-created, thread-confined pePI sessions.

    One client per thread avoids cookie/session races between concurrent
    requests. The clients are closed via :meth:`close`.
    """

    def __init__(self) -> None:
        self._tls = threading.local()
        self._all: list[_PepiSession] = []
        self._lock = threading.Lock()

    def get(self) -> _PepiSession:
        session = getattr(self._tls, "session", None)
        if session is None:
            session = _PepiSession()
            self._tls.session = session
            with self._lock:
                self._all.append(session)
        return session

    def close(self) -> None:
        with self._lock:
            for session in self._all:
                session.close()
            self._all.clear()


_POOL = _SessionPool()


def _load_row(db: Session, codigo_interno: str) -> MarcaLogo | None:
    return db.execute(
        select(MarcaLogo).where(MarcaLogo.codigo_interno == codigo_interno)
    ).scalar_one_or_none()


def stored_logo_file(row: MarcaLogo | None, codigo_interno: str) -> Path | None:
    """Return the on-disk path for an ``OK`` row that actually exists.

    Tolerates paths stored with Windows separators (``raw\\marcas\\logos\\44\\x.jpg``):
    they were written by the worker running on Windows and, read back on Linux,
    ``Path("raw\\...")`` is a *single* filename. We normalise the separators and,
    if the relative path still misses, fall back to the canonical shard
    (``logos/<2 first chars>/<file>``) so an old row keeps working after a
    restore.
    """
    if row is None or row.status != OK or not row.arquivo:
        return None

    salvo = Path(row.arquivo.replace("\\", "/"))
    candidatos: list[Path] = []
    if salvo.is_absolute():
        candidatos.append(salvo)
    else:
        candidatos.append((settings.data_path / salvo).resolve())
        prefixo = (codigo_interno or "")[:2] or "_"
        candidatos.append((settings.logos_path / prefixo / salvo.name).resolve())

    for caminho in candidatos:
        if caminho.is_file():
            return caminho
    return None


# Acima disto a imagem não é embutida no JSON (a UI cai para a rota ``/logo``,
# que faz streaming). Logotipos do pePI costumam ter ~8 KB.
_LOGO_MAX_INLINE_BYTES = 512 * 1024


def inline_logo_data_uri(path: Path | None, mime: str | None) -> str | None:
    """``data:image/jpeg;base64,...`` para embutir o logotipo na resposta.

    Usado pelo detalhe da marca, que assim não precisa de uma segunda
    requisição. ``None`` quando não há arquivo, ele está vazio ou passa de
    ``_LOGO_MAX_INLINE_BYTES``.
    """
    if path is None:
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data or len(data) > _LOGO_MAX_INLINE_BYTES:
        return None
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime or 'image/jpeg'};base64,{encoded}"


def _persist(
    db: Session,
    codigo_interno: str,
    *,
    status: str,
    arquivo: str | None = None,
    mime: str | None = None,
    size: int | None = None,
    sha256: str | None = None,
    erro: str | None = None,
    tentativas: int = 0,
    baixado_em: datetime | None = None,
) -> MarcaLogo:
    """Upsert the ``marcas_logos`` row and flush it."""
    row = _load_row(db, codigo_interno)
    if row is None:
        row = MarcaLogo(codigo_interno=codigo_interno)
        db.add(row)
    row.status = status
    row.arquivo = arquivo
    row.mime = mime
    row.bytes = size
    row.sha256 = sha256
    row.erro = erro
    row.tentativas = tentativas
    if baixado_em is not None:
        row.baixado_em = baixado_em
    db.commit()
    db.refresh(row)
    return row


def _do_fetch(db: Session, codigo_interno: str) -> MarcaLogo:
    """Fetch one logo from INPI and persist it (real image or placeholder)."""
    client = _POOL.get()
    last_err: str | None = None
    attempts = 0
    while attempts <= settings.logo_http_retries:
        attempts += 1
        try:
            kind, data, mime = client.fetch(codigo_interno)
            if kind == "image":
                dest = _destino(codigo_interno, mime)
                _write_atomic(dest, data)
                return _persist(
                    db,
                    codigo_interno,
                    status=OK,
                    arquivo=_rel_arquivo(dest),
                    mime=mime,
                    size=len(data),
                    sha256=hashlib.sha256(data).hexdigest(),
                    tentativas=attempts,
                    baixado_em=datetime.now(timezone.utc),
                )
            if kind == "placeholder":
                return _persist(
                    db,
                    codigo_interno,
                    status=SEM_IMAGEM,
                    tentativas=attempts,
                    baixado_em=datetime.now(timezone.utc),
                )
            # HTML → expired/anonymous session; re-login and retry.
            last_err = "sessão expirada (resposta HTML)"
            client.logged_in = False
        except httpx.HTTPError as exc:  # transport / status errors
            last_err = str(exc)
            client.logged_in = False
    return _persist(
        db,
        codigo_interno,
        status=ERROR,
        erro=last_err or "erro ao baixar logotipo",
        tentativas=attempts,
    )


def resolve_marca_logo(
    db: Session, codigo_interno: str, *, allow_fetch: bool | None = None
) -> MarcaLogo | None:
    """Return the stored logo row for a marca (DB-first, read-only by default).

    The image is downloaded by the offline worker (``python -m
    ingestion.logos``). This resolver never touches the network unless
    ``allow_fetch=True`` is passed explicitly (or ``LOGO_FETCH_ENABLED`` is set),
    which keeps the historical on-demand path available for tests/opt-in only.
    ``SEM_IMAGEM`` is terminal and returned as-is. Returns ``None`` when there is
    no stored row, so the caller can degrade to a placeholder.
    """
    if not codigo_interno:
        return None
    if allow_fetch is None:
        allow_fetch = settings.logo_fetch_enabled

    row = _load_row(db, codigo_interno)
    if row is not None and row.status in _TERMINAL:
        return row
    if not allow_fetch:
        return row

    # Only attempt for marcas that actually exist (avoid registering bogus codes).
    existe = db.execute(
        select(Marca.id).where(Marca.codigo_interno == codigo_interno)
    ).scalar_one_or_none()
    if existe is None:
        return row

    try:
        return _do_fetch(db, codigo_interno)
    except Exception:  # noqa: BLE001 - never break the read path on a fetch error
        return row


def resolve_logo_file(
    db: Session, codigo_interno: str, *, allow_fetch: bool | None = None
) -> tuple[Path, str] | None:
    """Return ``(path, mime)`` for a *stored* marca logo (DB-first).

    Downloading is done by the offline worker; the API only serves what is on
    disk. ``None`` when no real image is stored (or, with ``allow_fetch=True``,
    when it could not be fetched).
    """
    row = resolve_marca_logo(db, codigo_interno, allow_fetch=allow_fetch)
    path = stored_logo_file(row, codigo_interno)
    if path is None or row is None:
        return None
    return path, (row.mime or "image/jpeg")


