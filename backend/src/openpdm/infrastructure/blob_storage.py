"""Blob storage infrastructure behind a replaceable boundary."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openpdm.infrastructure.settings import Settings


@dataclass(frozen=True)
class BlobStorageSettings:
    """Settings for the active blob storage adapter."""

    endpoint_url: str
    bucket: str
    access_key: str
    secret_key: str
    local_root: str


class BlobStorage(ABC):
    """Public infrastructure-facing blob storage contract."""

    @abstractmethod
    def put_bytes(self, storage_key: str, content: bytes, media_type: str | None = None) -> None:
        """Store bytes under the given storage key."""

    @abstractmethod
    def get_bytes(self, storage_key: str) -> bytes:
        """Read bytes for the given storage key."""


class LocalFileBlobStorage(BlobStorage):
    """Local filesystem-backed blob storage used for tests and local runs."""

    def __init__(self, root: str, bucket: str) -> None:
        self._base_path = Path(root).resolve() / bucket
        self._base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_target(self, storage_key: str) -> Path:
        target = (self._base_path / storage_key).resolve()
        try:
            target.relative_to(self._base_path)
        except ValueError as exc:
            raise ValueError("Blob storage key escapes the configured bucket root.") from exc
        return target

    def put_bytes(self, storage_key: str, content: bytes, media_type: str | None = None) -> None:
        target = self._resolve_target(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def get_bytes(self, storage_key: str) -> bytes:
        target = self._resolve_target(storage_key)
        return target.read_bytes()


class S3CompatibleBlobStorage(BlobStorage):
    """S3-compatible storage adapter for self-hosted deployments."""

    def __init__(self, settings: BlobStorageSettings) -> None:
        try:
            import boto3
            from botocore.client import Config
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "boto3 is required for S3-compatible blob storage. "
                "Install declared runtime dependencies before running OpenPDM."
            ) from exc

        self._bucket = settings.bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.endpoint_url,
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key,
            config=Config(signature_version="s3v4"),
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        existing = {bucket["Name"] for bucket in self._client.list_buckets().get("Buckets", [])}
        if self._bucket not in existing:
            self._client.create_bucket(Bucket=self._bucket)

    def put_bytes(self, storage_key: str, content: bytes, media_type: str | None = None) -> None:
        extra_args: dict[str, Any] = {}
        if media_type:
            extra_args["ContentType"] = media_type
        self._client.put_object(Bucket=self._bucket, Key=storage_key, Body=content, **extra_args)

    def get_bytes(self, storage_key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=storage_key)
        return response["Body"].read()


_STORAGE_CACHE: dict[str, BlobStorage] = {}


def describe_blob_storage(settings: BlobStorageSettings) -> str:
    """Return a human-readable storage description."""
    return f"Blob storage at {settings.endpoint_url}, bucket {settings.bucket}"


def build_blob_storage(settings: Settings | None = None) -> BlobStorage:
    """Build the active blob storage adapter from runtime settings."""
    active_settings = settings or Settings()
    cache_key = "|".join(
        [
            active_settings.s3_endpoint_url,
            active_settings.s3_bucket,
            active_settings.blob_local_root,
        ]
    )
    cached = _STORAGE_CACHE.get(cache_key)
    if cached is not None:
        return cached

    blob_settings = BlobStorageSettings(
        endpoint_url=active_settings.s3_endpoint_url,
        bucket=active_settings.s3_bucket,
        access_key=active_settings.s3_access_key,
        secret_key=active_settings.s3_secret_key,
        local_root=active_settings.blob_local_root,
    )

    if blob_settings.endpoint_url.startswith("file://"):
        storage = LocalFileBlobStorage(blob_settings.local_root, blob_settings.bucket)
    elif blob_settings.endpoint_url.startswith(("http://", "https://")):
        storage = S3CompatibleBlobStorage(blob_settings)
    else:
        storage = LocalFileBlobStorage(blob_settings.local_root, blob_settings.bucket)

    _STORAGE_CACHE[cache_key] = storage
    return storage


def reset_blob_storage_cache() -> None:
    """Clear cached storage instances. Useful for tests."""
    _STORAGE_CACHE.clear()
