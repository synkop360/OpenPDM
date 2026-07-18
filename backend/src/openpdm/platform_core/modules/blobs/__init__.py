"""Public Blobs Platform Module contract."""

from typing import Any, BinaryIO, Protocol

from openpdm.infrastructure.blob_storage import BlobStorage
from openpdm.infrastructure.settings import Settings


class BlobsInterface(Protocol):
    """Own Blob records and binary storage orchestration."""

    def create_upload_session(
        self,
        db: Any,
        *,
        actor: Any,
        filename: str,
        media_type: str,
        total_size_bytes: int,
        checksum_sha256: str | None,
        storage: BlobStorage,
        settings: Settings,
    ) -> Any: ...

    def get_upload_session(
        self, db: Any, *, session_id: str, actor: Any, storage: BlobStorage
    ) -> Any: ...

    def get_upload_chunk_contract(
        self, db: Any, *, session_id: str, actor: Any, storage: BlobStorage
    ) -> tuple[int, int]: ...

    def put_upload_chunk(
        self,
        db: Any,
        *,
        session_id: str,
        chunk_number: int,
        content: BinaryIO,
        size_bytes: int,
        checksum_sha256: str,
        actor: Any,
        storage: BlobStorage,
    ) -> Any: ...

    def complete_upload_session(
        self, db: Any, *, session_id: str, actor: Any, storage: BlobStorage
    ) -> Any: ...

    def cancel_upload_session(
        self, db: Any, *, session_id: str, actor: Any, storage: BlobStorage
    ) -> None: ...

    def cleanup_expired_upload_sessions(self, db: Any, *, storage: BlobStorage) -> int: ...
