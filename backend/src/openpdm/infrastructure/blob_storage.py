"""Blob storage infrastructure boundary for S3-compatible storage."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BlobStorageSettings:
    endpoint_url: str
    bucket: str


def describe_blob_storage(settings: BlobStorageSettings) -> str:
    """Return a human-readable description without opening network connections."""
    return f"S3-compatible storage at {settings.endpoint_url}, bucket {settings.bucket}"
