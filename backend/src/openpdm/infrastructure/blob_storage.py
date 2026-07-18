"""Blob storage infrastructure behind a replaceable boundary."""

from __future__ import annotations

import hashlib
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any, BinaryIO

from openpdm.infrastructure.settings import Settings


@dataclass(frozen=True)
class BlobStorageSettings:
    """Settings for the active blob storage adapter."""

    endpoint_url: str
    bucket: str
    access_key: str
    secret_key: str
    local_root: str


@dataclass(frozen=True)
class UploadAssemblyResult:
    """Provider-neutral integrity result for an assembled upload session."""

    size_bytes: int
    checksum_sha256: str


class BlobStorage(ABC):
    """Public infrastructure-facing blob storage contract."""

    @abstractmethod
    def put_bytes(self, storage_key: str, content: bytes, media_type: str | None = None) -> None:
        """Store bytes under the given storage key."""

    @abstractmethod
    def get_bytes(self, storage_key: str) -> bytes:
        """Read bytes for the given storage key."""

    @abstractmethod
    def initialize_upload_session(self, session_id: str) -> None:
        """Initialize provider-private storage for a resumable upload session."""

    @abstractmethod
    def put_upload_chunk(
        self, session_id: str, chunk_number: int, content: BinaryIO, checksum_sha256: str
    ) -> None:
        """Persist an idempotent verified chunk without exposing provider details."""

    @abstractmethod
    def assemble_upload_session(
        self, session_id: str, storage_key: str, chunk_numbers: list[int]
    ) -> UploadAssemblyResult:
        """Assemble ordered chunks into final Blob storage and report actual integrity."""

    @abstractmethod
    def cleanup_upload_session(self, session_id: str) -> None:
        """Remove provider-private temporary storage for a session."""


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

    def _session_path(self, session_id: str) -> Path:
        if not session_id or PurePath(session_id).name != session_id:
            raise ValueError("Upload session identifier is invalid.")
        return self._resolve_target(f"upload-sessions/{session_id}")

    def initialize_upload_session(self, session_id: str) -> None:
        (self._session_path(session_id) / "chunks").mkdir(parents=True, exist_ok=True)

    def put_upload_chunk(
        self, session_id: str, chunk_number: int, content: BinaryIO, checksum_sha256: str
    ) -> None:
        chunk_path = self._session_path(session_id) / "chunks" / str(chunk_number)
        chunk_path.parent.mkdir(parents=True, exist_ok=True)
        if chunk_path.exists():
            if self._file_checksum(chunk_path) != checksum_sha256:
                raise ValueError("Stored upload chunk differs from retry.")
            return
        with chunk_path.open("wb") as target:
            shutil.copyfileobj(content, target, length=1024 * 1024)

    @staticmethod
    def _file_checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def assemble_upload_session(
        self, session_id: str, storage_key: str, chunk_numbers: list[int]
    ) -> UploadAssemblyResult:
        session_path = self._session_path(session_id)
        target = self._resolve_target(storage_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        size_bytes = 0
        with target.open("wb") as destination:
            for number in chunk_numbers:
                with (session_path / "chunks" / str(number)).open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        destination.write(chunk)
                        digest.update(chunk)
                        size_bytes += len(chunk)
        return UploadAssemblyResult(size_bytes, digest.hexdigest())

    def cleanup_upload_session(self, session_id: str) -> None:
        session_path = self._session_path(session_id)
        if session_path.exists():
            shutil.rmtree(session_path)


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

    @staticmethod
    def _session_prefix(session_id: str) -> str:
        if not session_id or PurePath(session_id).name != session_id:
            raise ValueError("Upload session identifier is invalid.")
        return f"upload-sessions/{session_id}/"

    def initialize_upload_session(self, session_id: str) -> None:
        self._session_prefix(session_id)

    def put_upload_chunk(
        self, session_id: str, chunk_number: int, content: BinaryIO, checksum_sha256: str
    ) -> None:
        key = f"{self._session_prefix(session_id)}chunks/{chunk_number}"
        try:
            existing_checksum = self._object_checksum(key)
        except Exception:  # Provider absence is represented by a new object.
            existing_checksum = None
        if existing_checksum is not None:
            if existing_checksum != checksum_sha256:
                raise ValueError("Stored upload chunk differs from retry.")
            return
        self._client.upload_fileobj(content, self._bucket, key)

    def _object_checksum(self, storage_key: str) -> str:
        digest = hashlib.sha256()
        body = self._client.get_object(Bucket=self._bucket, Key=storage_key)["Body"]
        for chunk in iter(lambda: body.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()

    def assemble_upload_session(
        self, session_id: str, storage_key: str, chunk_numbers: list[int]
    ) -> UploadAssemblyResult:
        prefix = self._session_prefix(session_id)
        multipart = self._client.create_multipart_upload(Bucket=self._bucket, Key=storage_key)
        upload_id = multipart["UploadId"]
        parts: list[dict[str, object]] = []
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            for part_number, number in enumerate(chunk_numbers, start=1):
                source_key = f"{prefix}chunks/{number}"
                body = self._client.get_object(Bucket=self._bucket, Key=source_key)["Body"]
                while chunk := body.read(1024 * 1024):
                    digest.update(chunk)
                    size_bytes += len(chunk)
                copied = self._client.upload_part_copy(
                    Bucket=self._bucket,
                    Key=storage_key,
                    PartNumber=part_number,
                    UploadId=upload_id,
                    CopySource={"Bucket": self._bucket, "Key": source_key},
                )
                parts.append({"ETag": copied["CopyPartResult"]["ETag"], "PartNumber": part_number})
            self._client.complete_multipart_upload(
                Bucket=self._bucket,
                Key=storage_key,
                UploadId=upload_id,
                MultipartUpload={"Parts": parts},
            )
        except Exception:
            self._client.abort_multipart_upload(
                Bucket=self._bucket, Key=storage_key, UploadId=upload_id
            )
            raise
        return UploadAssemblyResult(size_bytes, digest.hexdigest())

    def cleanup_upload_session(self, session_id: str) -> None:
        prefix = self._session_prefix(session_id)
        continuation_token: str | None = None
        while True:
            request: dict[str, str] = {"Bucket": self._bucket, "Prefix": prefix}
            if continuation_token is not None:
                request["ContinuationToken"] = continuation_token
            response = self._client.list_objects_v2(**request)
            objects = [{"Key": item["Key"]} for item in response.get("Contents", [])]
            if objects:
                self._client.delete_objects(Bucket=self._bucket, Delete={"Objects": objects})
            if not response.get("IsTruncated"):
                return
            continuation_token = response.get("NextContinuationToken")
            if not continuation_token:
                raise RuntimeError(
                    "S3 cleanup pagination response is missing a continuation token."
                )


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
