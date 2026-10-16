"""F1 — storage service unit tests (magic bytes, traversal, atomic writes).

These do not touch the database; they exercise the private storage abstraction
directly (decision D2) and prove the security invariants of the local backend.
"""

from __future__ import annotations

import uuid

import pytest

from app.services import storage
from app.services.storage import (
    FileTooLarge,
    LocalPrivateStorage,
    StorageError,
    UnsupportedFileType,
)


@pytest.fixture()
def local_store(tmp_path):
    return LocalPrivateStorage(root=tmp_path / "private")


def test_sniff_mime_recognises_pdf_and_png():
    assert storage.sniff_mime(b"%PDF-1.7") == "application/pdf"
    assert storage.sniff_mime(b"\x89PNG\r\n\x1a\n") == "image/png"
    assert storage.sniff_mime(b"not-a-real-file") is None


def test_put_and_get_roundtrip(local_store):
    key = storage.build_storage_key(uuid.uuid4(), uuid.uuid4())
    stored = local_store.put(key, b"%PDF-1.4\nhello\n%%EOF")
    assert stored.detected_mime == "application/pdf"
    assert stored.size_bytes == len(b"%PDF-1.4\nhello\n%%EOF")
    assert local_store.get(key) == b"%PDF-1.4\nhello\n%%EOF"
    assert local_store.exists(key)


def test_put_rejects_disallowed_content(local_store):
    key = storage.build_storage_key(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(UnsupportedFileType):
        local_store.put(key, b"MZ\x90\x00windows-executable")


def test_put_rejects_empty_file(local_store):
    key = storage.build_storage_key(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(UnsupportedFileType):
        local_store.put(key, b"")


def test_put_rejects_oversized(local_store, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "document_max_size_mb", 1, raising=False)
    key = storage.build_storage_key(uuid.uuid4(), uuid.uuid4())
    with pytest.raises(FileTooLarge):
        local_store.put(key, b"%PDF-1.4\n" + b"A" * (1024 * 1024 + 5))


def test_traversal_key_rejected(local_store):
    with pytest.raises(StorageError):
        local_store.put("documents/../../etc/passwd", b"%PDF-1.4\nx")
    with pytest.raises(StorageError):
        local_store.get("../secrets")


def test_malformed_key_rejected(local_store):
    with pytest.raises(StorageError):
        local_store.get("documents/not-a-uuid/also-not")
