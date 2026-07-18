"""Public Blobs Platform Module contract."""

from typing import Protocol


class BlobsInterface(Protocol):
    """Own Blob records and binary storage orchestration."""

    def create_upload_session(self, *args: object, **kwargs: object) -> object: ...

    def put_upload_chunk(self, *args: object, **kwargs: object) -> object: ...

    def complete_upload_session(self, *args: object, **kwargs: object) -> object: ...

    def cancel_upload_session(self, *args: object, **kwargs: object) -> None: ...
