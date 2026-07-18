"""Public Blobs Platform Module contract."""

from typing import BinaryIO, Protocol

from sqlalchemy.orm import Session

from openpdm.infrastructure.blob_storage import BlobStorage
from openpdm.infrastructure.settings import Settings
from openpdm.platform_core.modules.models import BlobUploadSession, User


class BlobsInterface(Protocol):
    """Own Blob records and binary storage orchestration."""

    def create_upload_session(
        self,
        db: Session,
        *,
        actor: User,
        filename: str,
        media_type: str,
        total_size_bytes: int,
        checksum_sha256: str | None,
        storage: BlobStorage,
        settings: Settings,
    ) -> BlobUploadSession: ...

    def get_upload_session(
        self, db: Session, *, session_id: str, actor: User, storage: BlobStorage
    ) -> BlobUploadSession: ...

    def put_upload_chunk(
        self,
        db: Session,
        *,
        session_id: str,
        chunk_number: int,
        content: BinaryIO,
        size_bytes: int,
        checksum_sha256: str,
        actor: User,
        storage: BlobStorage,
    ) -> BlobUploadSession: ...

    def complete_upload_session(
        self, db: Session, *, session_id: str, actor: User, storage: BlobStorage
    ) -> BlobUploadSession: ...

    def cancel_upload_session(
        self, db: Session, *, session_id: str, actor: User, storage: BlobStorage
    ) -> None: ...

    def cleanup_expired_upload_sessions(self, db: Session, *, storage: BlobStorage) -> int: ...
