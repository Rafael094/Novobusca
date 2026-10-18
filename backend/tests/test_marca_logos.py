"""On-demand marca logotipo resolver (``app.services.marca_logos``).

Exercises the *lazy* flow used by the search/detail and monitoring screens —
DB-first, then download from INPI and persist — without ever touching the real
pePI servlet: the shared session pool is monkeypatched with a fake returning
canned JPEG/placeholder/HTML bytes.

Endpoint coverage for the enriched watch list lives in ``test_monitoramento.py``.
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

import pytest

from app.models import Marca, MarcaLogo
from app.services import marca_logos


# A tiny but valid JPEG: starts with the SOI + segment marker the sniffer looks
# for (``\\xff\\xd8\\xff``), which is all ``_PepiSession.fetch`` inspects.
_JPEG_BYTES = b"\xff\xd8\xff\xe0fake-jpeg-payload"
# The servlet's "no image" placeholder is served as a GIF.
_GIF_PLACEHOLDER = b"GIF89a\x01\x00\x01\x00\x00\x00\x00;"


class _FakeSession:
    """Stand-in for ``_PepiSession`` driven by a scripted response kind."""

    def __init__(self, kind: str, calls: list[str]) -> None:
        self._kind = kind
        self._calls = calls

    def fetch(self, codigo_interno: str) -> tuple[str, bytes, str | None]:
        self._calls.append(codigo_interno)
        if self._kind == "image":
            return "image", _JPEG_BYTES, "image/jpeg"
        if self._kind == "placeholder":
            return "placeholder", _GIF_PLACEHOLDER, "image/gif"
        if self._kind == "html":
            return "html", b"<html>sessao</html>", "text/html"
        raise AssertionError(f"unexpected kind {self._kind}")


class _FakePool:
    def __init__(self, kind: str) -> None:
        self.kind = kind
        self.calls: list[str] = []

    def get(self) -> _FakeSession:
        return _FakeSession(self.kind, self.calls)

    def close(self) -> None:  # pragma: no cover - parity with the real pool
        pass


@pytest.fixture()
def fake_pool(monkeypatch):
    """Replace the module-level pePI pool; returns a factory to script it."""

    def _install(kind: str) -> _FakePool:
        pool = _FakePool(kind)
        monkeypatch.setattr(marca_logos, "_POOL", pool)
        return pool

    return _install


def _seed_marca(db, codigo: str) -> Marca:
    marca = Marca(
        codigo_interno=codigo,
        numero_inpi=codigo,
        elemento_nominativo="LOGOTEST",
    )
    db.add(marca)
    db.commit()
    return marca



def test_resolve_fetches_and_stores_real_image(
    db, seeded, tmp_path, monkeypatch, fake_pool
):
    """A miss → the image is fetched, stored on disk and recorded as ``OK``."""
    monkeypatch.setattr(
        marca_logos.settings, "data_dir", str(tmp_path), raising=False
    )
    _seed_marca(db, "950000001")
    pool = fake_pool("image")

    row = marca_logos.resolve_marca_logo(db, "950000001", allow_fetch=True)

    assert row is not None
    assert row.status == marca_logos.OK
    assert row.mime == "image/jpeg"
    assert row.bytes == len(_JPEG_BYTES)
    assert row.sha256 == hashlib.sha256(_JPEG_BYTES).hexdigest()
    assert pool.calls == ["950000001"]

    # The binary was written under the sharded layout and is reachable.
    stored = marca_logos.resolve_logo_file(db, "950000001", allow_fetch=True)
    assert stored is not None
    path, mime = stored
    assert path.is_file()
    assert path.read_bytes() == _JPEG_BYTES
    assert mime == "image/jpeg"
    # Sharded by the first two characters of the code.
    assert path.parent.name == "95"


def test_resolve_is_db_first_no_refetch_when_ok(
    db, seeded, tmp_path, monkeypatch, fake_pool
):
    """Once an ``OK`` image exists, later calls never hit the network again."""
    monkeypatch.setattr(
        marca_logos.settings, "data_dir", str(tmp_path), raising=False
    )
    _seed_marca(db, "950000002")
    first = fake_pool("image")
    marca_logos.resolve_marca_logo(db, "950000002", allow_fetch=True)
    assert first.calls == ["950000002"]

    # A *second* pool must receive no calls: the DB row short-circuits it.
    second = fake_pool("image")
    row = marca_logos.resolve_marca_logo(db, "950000002", allow_fetch=True)
    assert row.status == marca_logos.OK
    assert second.calls == []


def test_resolve_placeholder_is_terminal(
    db, seeded, tmp_path, monkeypatch, fake_pool
):
    """A GIF placeholder is recorded as ``SEM_IMAGEM`` and never retried."""
    monkeypatch.setattr(
        marca_logos.settings, "data_dir", str(tmp_path), raising=False
    )
    _seed_marca(db, "950000003")
    pool = fake_pool("placeholder")

    row = marca_logos.resolve_marca_logo(db, "950000003", allow_fetch=True)
    assert row.status == marca_logos.SEM_IMAGEM
    assert row.arquivo is None
    assert pool.calls == ["950000003"]

    # Terminal: a fresh pool stays idle and no file path is exposed.
    again = fake_pool("placeholder")
    marca_logos.resolve_marca_logo(db, "950000003", allow_fetch=True)
    assert again.calls == []
    assert marca_logos.resolve_logo_file(db, "950000003", allow_fetch=True) is None


def test_resolve_skips_unknown_marca(db, seeded, tmp_path, monkeypatch, fake_pool):
    """Codes with no matching marca are never fetched (no bogus rows)."""
    monkeypatch.setattr(
        marca_logos.settings, "data_dir", str(tmp_path), raising=False
    )
    pool = fake_pool("image")

    row = marca_logos.resolve_marca_logo(db, "000000000", allow_fetch=True)
    assert row is None
    assert pool.calls == []
    assert db.query(MarcaLogo).count() == 0


def test_resolve_respects_disabled_fetch(db, seeded, tmp_path, monkeypatch, fake_pool):
    """With ``allow_fetch=False`` the resolver stays DB-only."""
    monkeypatch.setattr(
        marca_logos.settings, "data_dir", str(tmp_path), raising=False
    )
    _seed_marca(db, "950000004")
    pool = fake_pool("image")

    row = marca_logos.resolve_marca_logo(db, "950000004", allow_fetch=False)
    assert row is None
    assert pool.calls == []


def test_resolve_swallows_fetch_errors(db, seeded, tmp_path, monkeypatch):
    """A fetch error degrades to ``None`` — the read path must never raise."""
    monkeypatch.setattr(
        marca_logos.settings, "data_dir", str(tmp_path), raising=False
    )
    _seed_marca(db, "950000005")

    class _BoomSession:
        def fetch(self, codigo_interno):  # noqa: ANN001
            raise RuntimeError("network down")

    class _BoomPool:
        def get(self):
            return _BoomSession()

        def close(self):
            pass

    monkeypatch.setattr(marca_logos, "_POOL", _BoomPool())

    assert marca_logos.resolve_marca_logo(db, "950000005", allow_fetch=True) is None


def test_sanitize_blocks_path_traversal():
    """The filesystem guard neutralises traversal characters in INPI codes."""
    assert marca_logos._sanitize_codigo("../../etc/passwd") == "______etc_passwd"
    assert marca_logos._sanitize_codigo("BR-123_ok") == "BR-123_ok"
    assert len(marca_logos._sanitize_codigo("x" * 200)) == 64


def _logo_em_disco(tmp_path, codigo: str, nome: str) -> Path:
    destino = Path(tmp_path) / "raw" / "marcas" / "logos" / codigo[:2] / nome
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(_JPEG_BYTES)
    return destino


def test_stored_logo_file_resolve_caminho_gravado_no_windows(
    db, seeded, tmp_path, monkeypatch
):
    """Regressão de produção: o worker no Windows grava ``raw\\marcas\\...``.

    No Linux ``Path("raw\\marcas\\logos\\44\\x.jpg")`` é *um* nome de arquivo, o
    que fazia a rota ``/logo`` responder 404 mesmo com a imagem em disco.
    """
    monkeypatch.setattr(
        marca_logos.settings, "data_dir", str(tmp_path), raising=False
    )
    destino = _logo_em_disco(tmp_path, "4482935", "4482935.jpg")

    row = MarcaLogo(
        codigo_interno="4482935",
        arquivo=r"raw\marcas\logos\44\4482935.jpg",
        mime="image/jpeg",
        status=marca_logos.OK,
    )
    db.add(row)
    db.commit()

    path = marca_logos.stored_logo_file(row, "4482935")
    assert path is not None
    assert path.read_bytes() == _JPEG_BYTES
    assert path == destino.resolve()


def test_stored_logo_file_cai_no_layout_canonico(
    db, seeded, tmp_path, monkeypatch
):
    """Se o caminho gravado não existe, ainda achamos a imagem no shard."""
    monkeypatch.setattr(
        marca_logos.settings, "data_dir", str(tmp_path), raising=False
    )
    destino = _logo_em_disco(tmp_path, "4482935", "4482935.jpg")

    row = MarcaLogo(
        codigo_interno="4482935",
        arquivo="logos-antigos/4482935.jpg",
        mime="image/jpeg",
        status=marca_logos.OK,
    )
    db.add(row)
    db.commit()

    path = marca_logos.stored_logo_file(row, "4482935")
    assert path is not None
    assert path == destino.resolve()


def test_stored_logo_file_ignora_status_nao_ok(db, seeded, tmp_path, monkeypatch):
    monkeypatch.setattr(
        marca_logos.settings, "data_dir", str(tmp_path), raising=False
    )
    _logo_em_disco(tmp_path, "4482935", "4482935.jpg")
    row = MarcaLogo(
        codigo_interno="4482935",
        arquivo="raw/marcas/logos/44/4482935.jpg",
        status=marca_logos.SEM_IMAGEM,
    )
    db.add(row)
    db.commit()

    assert marca_logos.stored_logo_file(row, "4482935") is None
    assert marca_logos.stored_logo_file(None, "4482935") is None


def test_inline_logo_data_uri(tmp_path):
    """O detalhe embute a imagem como data URI (sem segunda requisição)."""
    destino = _logo_em_disco(tmp_path, "4482935", "4482935.jpg")

    uri = marca_logos.inline_logo_data_uri(destino, "image/jpeg")
    assert uri is not None
    assert uri.startswith("data:image/jpeg;base64,")
    assert base64.b64decode(uri.split(",", 1)[1]) == _JPEG_BYTES

    # Sem arquivo / arquivo vazio / imagem grande demais → None (UI usa /logo).
    assert marca_logos.inline_logo_data_uri(None, "image/jpeg") is None
    assert marca_logos.inline_logo_data_uri(tmp_path / "nao-existe.jpg", None) is None
    vazio = tmp_path / "vazio.jpg"
    vazio.write_bytes(b"")
    assert marca_logos.inline_logo_data_uri(vazio, "image/jpeg") is None
    grande = tmp_path / "grande.jpg"
    grande.write_bytes(b"\xff\xd8\xff" + b"0" * marca_logos._LOGO_MAX_INLINE_BYTES)
    assert marca_logos.inline_logo_data_uri(grande, "image/jpeg") is None
