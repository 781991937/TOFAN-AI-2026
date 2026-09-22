import os

import pytest


def test_production_rejects_local_storage(monkeypatch):
    monkeypatch.setenv("TOFAN_ENV", "production")
    monkeypatch.setenv("TOFAN_STORAGE_BACKEND", "local")
    import app.storage as storage
    with pytest.raises(storage.StorageError, match="Production requires TOFAN_STORAGE_BACKEND=s3"):
        storage.ObjectStorage()


def test_development_local_storage_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("TOFAN_ENV", "development")
    monkeypatch.setenv("TOFAN_STORAGE_BACKEND", "local")
    monkeypatch.setenv("TOFAN_UPLOAD_DIR", str(tmp_path))
    from app.storage import ObjectStorage
    store = ObjectStorage()
    obj = store.put_bytes(b"TOFAN", ".txt", "student")
    assert store.exists(obj.key)
    assert store.read_bytes(obj.key) == b"TOFAN"
    store.delete(obj.key)
    assert not store.exists(obj.key)
