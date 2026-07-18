from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select

from openpdm.infrastructure.blob_storage import (
    BlobStorage,
    LocalFileBlobStorage,
    reset_blob_storage_cache,
)
from openpdm.infrastructure.database import dispose_engines, initialize_database, session_scope
from openpdm.infrastructure.settings import Settings
from openpdm.platform_core.modules.models import Blob


def build_client(tmp_path: Path) -> TestClient:
    os.environ["OPENPDM_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'openpdm.db'}"
    os.environ["OPENPDM_S3_ENDPOINT_URL"] = "file://local"
    os.environ["OPENPDM_BLOB_LOCAL_ROOT"] = str(tmp_path / "blobs")
    os.environ["OPENPDM_PLUGIN_PACKAGE_ROOT"] = str(tmp_path / "plugins")
    os.environ["OPENPDM_PLUGIN_CONFIGURATION_KEY"] = Fernet.generate_key().decode()
    os.environ["OPENPDM_BLOB_UPLOAD_CHUNK_SIZE_BYTES"] = "4"
    os.environ["OPENPDM_BLOB_UPLOAD_MAX_SIZE_BYTES"] = "32"
    os.environ["OPENPDM_BLOB_UPLOAD_SESSION_TTL_SECONDS"] = "3600"
    reset_blob_storage_cache()
    dispose_engines()
    from openpdm.main import create_app

    return TestClient(create_app())


def register(client: TestClient, *, email: str) -> str:
    response = client.post(
        "/auth/register",
        json={"email": email, "display_name": email.split("@")[0], "password": "secret123"},
    )
    assert response.status_code == 201
    return client.post("/auth/sign-in", json={"email": email, "password": "secret123"}).json()[
        "token"
    ]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_session(client: TestClient, token: str, **overrides: object) -> dict[str, object]:
    payload = {
        "filename": "nested/path/wing.step",
        "media_type": "application/step",
        "total_size_bytes": 8,
        **overrides,
    }
    response = client.post("/blobs/upload-sessions", headers=headers(token), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def upload_chunk(client: TestClient, token: str, session_id: str, number: int, content: bytes):
    return client.put(
        f"/blobs/upload-sessions/{session_id}/chunks/{number}",
        headers={**headers(token), "Content-Type": "application/octet-stream"},
        content=content,
    )


def test_session_upload_is_resumable_out_of_order_and_completion_is_idempotent(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    session = create_session(client, token)
    session_id = str(session["id"])

    second = upload_chunk(client, token, session_id, 1, b"EFGH")
    assert second.status_code == 200
    assert second.json()["received_bytes"] == 4
    assert second.json()["received_chunk_numbers"] == [1]
    assert upload_chunk(client, token, session_id, 0, b"ABCD").status_code == 200
    completed = client.post(f"/blobs/upload-sessions/{session_id}/complete", headers=headers(token))
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["filename"] == "wing.step"
    blob = completed.json()["blob"]
    assert blob is not None
    assert (
        client.get(f"/blobs/{blob['id']}/download", headers=headers(token)).content == b"ABCDEFGH"
    )
    assert (
        client.post(f"/blobs/upload-sessions/{session_id}/complete", headers=headers(token)).json()[
            "blob"
        ]
        == blob
    )


def test_duplicate_chunk_retry_and_other_user_access_are_safe(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    owner = register(client, email="owner@example.com")
    other = register(client, email="other@example.com")
    session_id = str(create_session(client, owner)["id"])
    assert upload_chunk(client, owner, session_id, 0, b"ABCD").status_code == 200
    assert upload_chunk(client, owner, session_id, 0, b"ABCD").status_code == 200
    assert upload_chunk(client, owner, session_id, 0, b"WXYZ").status_code == 409
    assert (
        client.get(f"/blobs/upload-sessions/{session_id}", headers=headers(other)).status_code
        == 403
    )
    assert upload_chunk(client, other, session_id, 1, b"EFGH").status_code == 403


def test_cancellation_is_idempotent_and_prevents_blob_creation(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    session_id = str(create_session(client, token)["id"])
    assert upload_chunk(client, token, session_id, 0, b"ABCD").status_code == 200
    assert (
        client.delete(f"/blobs/upload-sessions/{session_id}", headers=headers(token)).status_code
        == 204
    )
    assert (
        client.delete(f"/blobs/upload-sessions/{session_id}", headers=headers(token)).status_code
        == 204
    )
    assert (
        client.get(f"/blobs/upload-sessions/{session_id}", headers=headers(token)).json()["status"]
        == "cancelled"
    )
    assert (
        client.post(
            f"/blobs/upload-sessions/{session_id}/complete", headers=headers(token)
        ).status_code
        == 409
    )
    with session_scope() as db:
        assert db.scalar(select(Blob).where(Blob.created_by_user_id.is_not(None))) is None


def test_invalid_upload_session_limits_and_chunks_are_rejected(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    for payload in (
        {"filename": "a", "media_type": "text/plain", "total_size_bytes": 0},
        {"filename": "a", "media_type": "text/plain", "total_size_bytes": 33},
        {
            "filename": "a",
            "media_type": "text/plain",
            "total_size_bytes": 4,
            "checksum_sha256": "bad",
        },
    ):
        assert (
            client.post("/blobs/upload-sessions", headers=headers(token), json=payload).status_code
            == 400
        )
    session_id = str(create_session(client, token)["id"])
    assert upload_chunk(client, token, session_id, 0, b"").status_code == 400
    assert upload_chunk(client, token, session_id, 0, b"ABC").status_code == 400
    assert upload_chunk(client, token, session_id, 2, b"ABCD").status_code == 400


def test_digest_and_total_size_mismatches_never_create_a_blob_and_can_recover(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    session_id = str(
        create_session(client, token, checksum_sha256=hashlib.sha256(b"wrong").hexdigest())["id"]
    )
    upload_chunk(client, token, session_id, 0, b"ABCD")
    upload_chunk(client, token, session_id, 1, b"EFGH")
    assert (
        client.post(
            f"/blobs/upload-sessions/{session_id}/complete", headers=headers(token)
        ).status_code
        == 409
    )
    assert (
        client.get(f"/blobs/upload-sessions/{session_id}", headers=headers(token)).json()["status"]
        == "active"
    )


def test_expired_session_cleans_up_and_returns_gone(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    session_id = str(create_session(client, token)["id"])
    with session_scope() as db:
        from openpdm.platform_core.modules.models import BlobUploadSession

        session = db.get(BlobUploadSession, session_id)
        assert session is not None
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    assert (
        client.get(f"/blobs/upload-sessions/{session_id}", headers=headers(token)).status_code
        == 410
    )
    with session_scope() as db:
        assert db.get(BlobUploadSession, session_id).status == "expired"


def test_local_storage_contains_upload_session_paths(tmp_path: Path) -> None:
    storage = LocalFileBlobStorage(str(tmp_path), "bucket")
    try:
        storage.initialize_upload_session("../escape")
    except ValueError:
        pass
    else:
        raise AssertionError("upload session path traversal must be rejected")


def test_upload_session_migration_is_upgradeable(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    os.environ["OPENPDM_DATABASE_URL"] = database_url
    dispose_engines()
    initialize_database(Settings(database_url=database_url))
    engine = create_engine(database_url)
    from openpdm.platform_core.modules.models import BlobUploadChunk, BlobUploadSession

    BlobUploadChunk.__table__.drop(engine)
    BlobUploadSession.__table__.drop(engine)
    config = Config("alembic.ini")
    command.stamp(config, "20260718_0005")
    command.upgrade(config, "head")
    tables = set(inspect(engine).get_table_names())
    assert {"blob_upload_sessions", "blob_upload_chunks"} <= tables


class FailingUploadStorage(BlobStorage):
    def put_bytes(self, storage_key: str, content: bytes, media_type: str | None = None) -> None:
        raise AssertionError("legacy method not expected")

    def get_bytes(self, storage_key: str) -> bytes:
        raise AssertionError("not expected")

    def initialize_upload_session(self, session_id: str) -> None:
        raise OSError("storage unavailable")

    def put_upload_chunk(
        self, session_id: str, chunk_number: int, content: bytes, checksum_sha256: str
    ) -> None:
        raise OSError("storage unavailable")

    def assemble_upload_session(
        self, session_id: str, storage_key: str, chunk_numbers: list[int]
    ) -> tuple[int, str]:
        raise OSError("storage unavailable")

    def cleanup_upload_session(self, session_id: str) -> None:
        return None


def test_storage_failure_keeps_session_recoverable(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    from openpdm.api.core import get_storage

    client.app.dependency_overrides[get_storage] = lambda: FailingUploadStorage()
    response = client.post(
        "/blobs/upload-sessions",
        headers=headers(token),
        json={"filename": "wing.step", "media_type": "application/step", "total_size_bytes": 8},
    )
    assert response.status_code == 201
    session_id = response.json()["id"]
    assert upload_chunk(client, token, session_id, 0, b"ABCD").status_code == 409
    assert (
        client.get(f"/blobs/upload-sessions/{session_id}", headers=headers(token)).json()["status"]
        == "active"
    )
    with session_scope() as db:
        assert db.scalar(select(Blob)) is None
