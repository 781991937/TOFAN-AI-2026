"""Production-grade object storage abstraction for TOFAN uploads.

Local storage is intentionally development-only. Production deployments must use
an S3-compatible object store (AWS S3, Cloudflare R2, MinIO, etc.).
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

try:
    import boto3
except ImportError:  # pragma: no cover
    boto3 = None


class StorageError(RuntimeError):
    """Raised when object storage is unavailable or misconfigured."""


@dataclass(frozen=True)
class StoredObject:
    key: str
    size_bytes: int


class ObjectStorage:
    def __init__(self) -> None:
        self.backend = os.getenv("TOFAN_STORAGE_BACKEND", "local").strip().lower()
        self.root = Path(os.getenv("TOFAN_UPLOAD_DIR", "data/uploads"))
        if os.getenv("TOFAN_ENV", "development").lower() == "production" and self.backend != "s3":
            raise StorageError("Production requires TOFAN_STORAGE_BACKEND=s3.")
        if self.backend not in {"local", "s3"}:
            raise StorageError("TOFAN_STORAGE_BACKEND must be local or s3.")
        self.bucket = os.getenv("TOFAN_S3_BUCKET", "").strip()
        self.region = os.getenv("TOFAN_S3_REGION", os.getenv("AWS_REGION", "us-east-1"))
        self.endpoint_url = os.getenv("TOFAN_S3_ENDPOINT_URL") or None
        self._client = None
        if self.backend == "s3":
            if boto3 is None:
                raise StorageError("boto3 is required for S3 storage.")
            if not self.bucket:
                raise StorageError("TOFAN_S3_BUCKET is required for S3 storage.")
            self._client = boto3.client("s3", region_name=self.region, endpoint_url=self.endpoint_url)

    def put_bytes(self, data: bytes, suffix: str, prefix: str) -> StoredObject:
        key = f"{prefix.strip('/')}/{uuid4().hex}{suffix.lower()}"
        if self.backend == "local":
            path = self.root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return StoredObject(key=str(path), size_bytes=len(data))
        assert self._client is not None
        self._client.put_object(Bucket=self.bucket, Key=key, Body=data)
        return StoredObject(key=key, size_bytes=len(data))

    def read_bytes(self, key: str) -> bytes:
        if self.backend == "local":
            path = Path(key)
            if not path.is_file():
                raise FileNotFoundError(key)
            return path.read_bytes()
        assert self._client is not None
        try:
            return self._client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except Exception as exc:
            raise FileNotFoundError(key) from exc

    def exists(self, key: str) -> bool:
        if self.backend == "local":
            return Path(key).is_file()
        assert self._client is not None
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        if self.backend == "local":
            Path(key).unlink(missing_ok=True)
            return
        assert self._client is not None
        self._client.delete_object(Bucket=self.bucket, Key=key)


def get_storage() -> ObjectStorage:
    return ObjectStorage()
