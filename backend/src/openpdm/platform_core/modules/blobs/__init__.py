"""Public Blobs Platform Module contract."""

from typing import Any, BinaryIO, Protocol

from openpdm.infrastructure.blob_storage import BlobStorage
from openpdm.infrastructure.settings import Settings
from openpdm.platform_core.modules.assets import AssetsInterface


class BlobsInterface(Protocol):
    """Own Blob records and binary storage orchestration."""

    def require_blob_usable_for_asset(
        self, db: Any, *, blob_id: str, asset_id: str, actor: Any
    ) -> Any: ...

    def create_upload_session(
        self,
        db: Any,
        *,
        actor: Any,
        asset_id: str,
        filename: str,
        media_type: str,
        total_size_bytes: int,
        checksum_sha256: str | None,
        storage: BlobStorage,
        settings: Settings,
        assets: AssetsInterface,
    ) -> Any: ...

    def get_upload_session(
        self, db: Any, *, session_id: str, actor: Any, storage: BlobStorage, assets: AssetsInterface
    ) -> Any: ...

    def get_upload_chunk_contract(
        self, db: Any, *, session_id: str, actor: Any, storage: BlobStorage, assets: AssetsInterface
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
        assets: AssetsInterface,
    ) -> Any: ...

    def complete_upload_session(
        self, db: Any, *, session_id: str, actor: Any, storage: BlobStorage, assets: AssetsInterface
    ) -> Any: ...

    def cancel_upload_session(
        self, db: Any, *, session_id: str, actor: Any, storage: BlobStorage, assets: AssetsInterface
    ) -> None: ...

    def cleanup_expired_upload_sessions(self, db: Any, *, storage: BlobStorage) -> int: ...

    def cleanup_completed_upload_session(
        self, db: Any, *, session_id: str, storage: BlobStorage
    ) -> bool: ...
