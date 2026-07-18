from __future__ import annotations

import hashlib
import io
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import BigInteger, create_engine, func, inspect, select

from openpdm.infrastructure.blob_storage import (
    BlobStorage,
    LocalFileBlobStorage,
    S3CompatibleBlobStorage,
    UploadAssemblyResult,
    reset_blob_storage_cache,
)
from openpdm.infrastructure.database import (
    dispose_engines,
    get_session_factory,
    initialize_database,
    session_scope,
)
from openpdm.infrastructure.settings import Settings
from openpdm.platform_core.modules.models import (
    Asset,
    AuditRecord,
    Blob,
    BlobUploadChunk,
    BlobUploadSession,
    DomainEvent,
    OrganizationMembership,
    ProjectMembership,
    User,
)
from openpdm.platform_core.modules.services import AssetsModule, BlobModule


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


def create_asset(client: TestClient, token: str) -> dict[str, object]:
    suffix = uuid.uuid4().hex
    organization = client.post(
        "/organizations",
        headers=headers(token),
        json={"name": f"Transfer {suffix}", "slug": f"transfer-{suffix}"},
    ).json()
    project = client.post(
        "/projects",
        headers=headers(token),
        json={"organization_id": organization["id"], "name": "Transfer", "description": ""},
    ).json()
    return client.post(
        f"/projects/{project['id']}/assets",
        headers=headers(token),
        json={"name": "Transfer asset", "description": ""},
    ).json()


def create_session(client: TestClient, token: str, **overrides: object) -> dict[str, object]:
    asset_id = overrides.pop("asset_id", None) or create_asset(client, token)["id"]
    payload = {
        "asset_id": asset_id,
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
    assert "storage_key" not in blob
    assert completed.json()["asset_id"] == session["asset_id"]
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


def test_every_session_operation_reauthorizes_asset_access(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    owner = register(client, email="owner@example.com")
    member = register(client, email="member@example.com")
    asset = create_asset(client, owner)
    with session_scope() as db:
        owner_user = db.scalar(select(User).where(User.email == "owner@example.com"))
        member_user = db.scalar(select(User).where(User.email == "member@example.com"))
        assert owner_user is not None and member_user is not None
        asset_row = db.get(Asset, asset["id"])
        assert asset_row is not None
        project = asset_row.project
        db.add(
            OrganizationMembership(
                organization_id=project.organization_id, user_id=member_user.id, role="Contributor"
            )
        )
        db.add(ProjectMembership(project_id=project.id, user_id=member_user.id, role="Contributor"))
        db.commit()
    session_id = str(create_session(client, member, asset_id=asset["id"])["id"])
    with session_scope() as db:
        membership = db.scalar(
            select(ProjectMembership).where(ProjectMembership.user_id == member_user.id)
        )
        assert membership is not None
        db.delete(membership)
        db.commit()
    assert (
        client.get(f"/blobs/upload-sessions/{session_id}", headers=headers(member)).status_code
        == 403
    )
    assert upload_chunk(client, member, session_id, 0, b"ABCD").status_code == 403
    assert (
        client.post(
            f"/blobs/upload-sessions/{session_id}/complete", headers=headers(member)
        ).status_code
        == 403
    )
    assert (
        client.delete(f"/blobs/upload-sessions/{session_id}", headers=headers(member)).status_code
        == 403
    )


def test_representation_rejects_foreign_or_wrong_asset_blob_and_accepts_owned_blob(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    owner = register(client, email="owner@example.com")
    foreign = register(client, email="foreign@example.com")
    asset = create_asset(client, owner)
    other_asset = create_asset(client, owner)
    revision = client.post(
        f"/assets/{asset['id']}/revisions", headers=headers(owner), json={"comment": "claim"}
    ).json()
    foreign_blob = client.post(
        "/blobs/uploads",
        headers=headers(foreign),
        files={"file": ("foreign.step", b"ABCD", "application/step")},
    ).json()
    rejected = client.post(
        f"/revisions/{revision['id']}/representations",
        headers=headers(owner),
        json={"name": "foreign", "media_type": "application/step", "blob_id": foreign_blob["id"]},
    )
    assert rejected.status_code == 403

    session = create_session(client, owner, asset_id=other_asset["id"], total_size_bytes=4)
    assert upload_chunk(client, owner, str(session["id"]), 0, b"ABCD").status_code == 200
    blob = client.post(
        f"/blobs/upload-sessions/{session['id']}/complete", headers=headers(owner)
    ).json()["blob"]
    wrong_context = client.post(
        f"/revisions/{revision['id']}/representations",
        headers=headers(owner),
        json={"name": "wrong", "media_type": "application/step", "blob_id": blob["id"]},
    )
    assert wrong_context.status_code == 403

    owned_blob = client.post(
        "/blobs/uploads",
        headers=headers(owner),
        files={"file": ("owned.step", b"EFGH", "application/step")},
    ).json()
    accepted = client.post(
        f"/revisions/{revision['id']}/representations",
        headers=headers(owner),
        json={"name": "owned", "media_type": "application/step", "blob_id": owned_blob["id"]},
    )
    assert accepted.status_code == 201


def test_completed_chunk_cleanup_failure_is_observable_and_retryable(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    session = create_session(client, token, total_size_bytes=4)
    session_id = str(session["id"])
    assert upload_chunk(client, token, session_id, 0, b"ABCD").status_code == 200
    assert (
        client.post(
            f"/blobs/upload-sessions/{session_id}/complete", headers=headers(token)
        ).status_code
        == 200
    )

    class FlakyCleanup:
        calls = 0

        def cleanup_upload_session(self, ignored_session_id: str) -> None:
            self.calls += 1
            if self.calls == 1:
                raise OSError("provider unavailable")

    storage = FlakyCleanup()
    with session_scope() as db:
        upload_session = db.get(BlobUploadSession, session_id)
        assert upload_session is not None
        upload_session.cleanup_pending = True
        db.flush()
        assert not BlobModule.cleanup_completed_upload_session(
            db, session_id=session_id, storage=storage
        )  # type: ignore[arg-type]
        db.commit()
    with session_scope() as db:
        upload_session = db.get(BlobUploadSession, session_id)
        assert upload_session is not None
        assert upload_session.cleanup_pending
        assert upload_session.cleanup_error == "OSError"
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditRecord)
                .where(
                    AuditRecord.action == "blob.upload_session.cleanup_failed",
                    AuditRecord.resource_id == session_id,
                )
            )
            == 1
        )
        assert BlobModule.cleanup_completed_upload_session(
            db, session_id=session_id, storage=storage
        )  # type: ignore[arg-type]
        db.commit()
    with session_scope() as db:
        upload_session = db.get(BlobUploadSession, session_id)
        assert upload_session is not None
        assert not upload_session.cleanup_pending
        assert upload_session.cleanup_error is None


def test_unrelated_session_creation_retries_pending_completed_cleanup(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    from openpdm.api.core import get_storage

    class CleanupFailOnceStorage(LocalFileBlobStorage):
        fail_cleanup = True

        def cleanup_upload_session(self, session_id: str) -> None:
            if self.fail_cleanup:
                raise OSError("provider unavailable")
            super().cleanup_upload_session(session_id)

    storage = CleanupFailOnceStorage(str(tmp_path / "blobs"), "openpdm-blobs")
    client.app.dependency_overrides[get_storage] = lambda: storage
    first = create_session(client, token, total_size_bytes=4)
    first_id = str(first["id"])
    assert upload_chunk(client, token, first_id, 0, b"ABCD").status_code == 200
    assert (
        client.post(
            f"/blobs/upload-sessions/{first_id}/complete", headers=headers(token)
        ).status_code
        == 200
    )
    first_path = tmp_path / "blobs" / "openpdm-blobs" / "upload-sessions" / first_id
    assert first_path.exists()
    with session_scope() as db:
        first_row = db.get(BlobUploadSession, first_id)
        assert first_row is not None
        assert first_row.cleanup_pending

    failed_retry_request = create_session(client, token, total_size_bytes=4)
    assert failed_retry_request["id"] != first_id
    with session_scope() as db:
        first_row = db.get(BlobUploadSession, first_id)
        assert first_row is not None
        assert first_row.cleanup_pending
        assert first_row.cleanup_error == "OSError"

    storage.fail_cleanup = False
    unrelated = create_session(client, token, total_size_bytes=4)
    assert unrelated["id"] != first_id
    assert not first_path.exists()
    with session_scope() as db:
        first_row = db.get(BlobUploadSession, first_id)
        assert first_row is not None
        assert not first_row.cleanup_pending
        assert first_row.cleanup_error is None


def test_cancellation_is_idempotent_and_prevents_blob_creation(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    session_id = str(create_session(client, token)["id"])
    assert upload_chunk(client, token, session_id, 0, b"ABCD").status_code == 200
    session_path = tmp_path / "blobs" / "openpdm-blobs" / "upload-sessions" / session_id
    assert (session_path / "chunks" / "0").read_bytes() == b"ABCD"
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
        assert (
            db.scalar(select(BlobUploadChunk).where(BlobUploadChunk.session_id == session_id))
            is None
        )
    assert not session_path.exists()


def test_invalid_upload_session_limits_and_chunks_are_rejected(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    asset_id = create_asset(client, token)["id"]
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
            client.post(
                "/blobs/upload-sessions",
                headers=headers(token),
                json={"asset_id": asset_id, **payload},
            ).status_code
            == 400
        )


def test_upload_session_rejects_overlong_or_blank_filename_and_media_type(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    asset_id = create_asset(client, token)["id"]
    base = {
        "asset_id": asset_id,
        "filename": "a",
        "media_type": "text/plain",
        "total_size_bytes": 4,
    }
    assert (
        client.post(
            "/blobs/upload-sessions", headers=headers(token), json={**base, "filename": "x" * 256}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/blobs/upload-sessions", headers=headers(token), json={**base, "media_type": "x" * 256}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/blobs/upload-sessions", headers=headers(token), json={**base, "filename": "   "}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/blobs/upload-sessions", headers=headers(token), json={**base, "media_type": "   "}
        ).status_code
        == 400
    )
    session_id = str(create_session(client, token)["id"])
    assert upload_chunk(client, token, session_id, 0, b"").status_code == 400
    assert upload_chunk(client, token, session_id, 0, b"ABC").status_code == 400
    assert upload_chunk(client, token, session_id, 2, b"ABCD").status_code == 400


def test_digest_mismatch_never_creates_a_blob_and_can_recover(
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
    with session_scope() as db:
        assert db.scalar(select(Blob)) is None


def test_expired_session_cleans_up_and_returns_gone(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    session_id = str(create_session(client, token)["id"])
    assert upload_chunk(client, token, session_id, 0, b"ABCD").status_code == 200
    session_path = tmp_path / "blobs" / "openpdm-blobs" / "upload-sessions" / session_id
    assert session_path.exists()
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
        assert (
            db.scalar(select(BlobUploadChunk).where(BlobUploadChunk.session_id == session_id))
            is None
        )
    assert not session_path.exists()


def test_put_chunk_after_persisted_expiry_returns_gone(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    session_id = str(create_session(client, token)["id"])
    with session_scope() as db:
        upload_session = db.get(BlobUploadSession, session_id)
        assert upload_session is not None
        upload_session.status = "expired"

    response = upload_chunk(client, token, session_id, 0, b"ABCD")

    assert response.status_code == 410
    assert response.json()["detail"] == "Upload session has expired."
    with session_scope() as db:
        assert db.get(BlobUploadSession, session_id).status == "expired"
        assert (
            db.scalar(select(BlobUploadChunk).where(BlobUploadChunk.session_id == session_id))
            is None
        )


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
    BlobUploadChunk.__table__.drop(engine)
    BlobUploadSession.__table__.drop(engine)
    config = Config("alembic.ini")
    command.stamp(config, "20260718_0005")
    command.upgrade(config, "head")
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    assert {"blob_upload_sessions", "blob_upload_chunks"} <= tables
    session_types = {
        column["name"]: column["type"] for column in inspector.get_columns("blob_upload_sessions")
    }
    chunk_types = {
        column["name"]: column["type"] for column in inspector.get_columns("blob_upload_chunks")
    }
    blob_types = {column["name"]: column["type"] for column in inspector.get_columns("blobs")}
    assert isinstance(session_types["total_size_bytes"], BigInteger)
    assert isinstance(session_types["chunk_size_bytes"], BigInteger)
    assert {"asset_id", "cleanup_pending", "cleanup_error"} <= set(session_types)
    assert any(
        foreign_key["referred_table"] == "assets"
        and foreign_key["constrained_columns"] == ["asset_id"]
        for foreign_key in inspector.get_foreign_keys("blob_upload_sessions")
    )
    assert any(
        index["column_names"] == ["asset_id"]
        for index in inspector.get_indexes("blob_upload_sessions")
    )
    assert isinstance(chunk_types["size_bytes"], BigInteger)
    assert isinstance(blob_types["size_bytes"], BigInteger)


def test_blob_byte_counts_support_the_configured_five_gib_limit() -> None:
    assert isinstance(Blob.__table__.c.size_bytes.type, BigInteger)
    assert isinstance(BlobUploadSession.__table__.c.total_size_bytes.type, BigInteger)
    assert isinstance(BlobUploadSession.__table__.c.chunk_size_bytes.type, BigInteger)
    assert isinstance(BlobUploadChunk.__table__.c.size_bytes.type, BigInteger)


class MultipartS3Client:
    def __init__(self, chunks: dict[int, bytes], *, fail_part: int | None = None) -> None:
        self.chunks = chunks
        self.fail_part = fail_part
        self.uploaded_parts: list[bytes] = []
        self.source_bodies: list[io.BytesIO] = []
        self.completed: dict[str, object] | None = None
        self.aborted = False

    def create_multipart_upload(self, **kwargs: object) -> dict[str, str]:
        return {"UploadId": "upload-id"}

    def get_object(self, *, Bucket: str, Key: str) -> dict[str, io.BytesIO]:
        body = io.BytesIO(self.chunks[int(Key.rsplit("/", 1)[-1])])
        self.source_bodies.append(body)
        return {"Body": body}

    def upload_part(self, *, Body: io.BufferedIOBase, **kwargs: object) -> dict[str, str]:
        part_number = int(kwargs["PartNumber"])
        if part_number == self.fail_part:
            raise OSError("provider rejected part")
        self.uploaded_parts.append(Body.read())
        return {"ETag": f"etag-{part_number}"}

    def complete_multipart_upload(self, **kwargs: object) -> None:
        self.completed = kwargs

    def abort_multipart_upload(self, **kwargs: object) -> None:
        self.aborted = True


def build_fake_s3_storage(client: MultipartS3Client) -> S3CompatibleBlobStorage:
    storage = object.__new__(S3CompatibleBlobStorage)
    storage._bucket = "bucket"
    storage._client = client
    return storage


def test_s3_assembly_coalesces_small_client_chunks_into_provider_valid_parts() -> None:
    mebibyte = 1024 * 1024
    chunks = {0: b"A" * (3 * mebibyte), 1: b"B" * (3 * mebibyte), 2: b"C" * mebibyte}
    expected = b"".join(chunks.values())
    client = MultipartS3Client(chunks)

    result = build_fake_s3_storage(client).assemble_upload_session(
        "session", "completed/blob", [0, 1, 2]
    )

    assert b"".join(client.uploaded_parts) == expected
    assert [len(part) for part in client.uploaded_parts] == [5 * mebibyte, 2 * mebibyte]
    assert all(len(part) >= 5 * mebibyte for part in client.uploaded_parts[:-1])
    assert result == UploadAssemblyResult(len(expected), hashlib.sha256(expected).hexdigest())
    assert client.completed is not None
    assert not client.aborted
    assert all(body.closed for body in client.source_bodies)


def test_s3_assembly_aborts_multipart_upload_when_a_part_fails() -> None:
    mebibyte = 1024 * 1024
    client = MultipartS3Client(
        {0: b"A" * (5 * mebibyte), 1: b"B"},
        fail_part=2,
    )

    try:
        build_fake_s3_storage(client).assemble_upload_session("session", "completed/blob", [0, 1])
    except OSError:
        pass
    else:
        raise AssertionError("provider part failure must escape assembly")

    assert client.aborted
    assert client.completed is None
    assert all(body.closed for body in client.source_bodies)


class DuplicateChunkS3Client:
    def __init__(self, existing: bytes) -> None:
        self.body = io.BytesIO(existing)

    def get_object(self, **kwargs: object) -> dict[str, io.BytesIO]:
        return {"Body": self.body}

    def upload_fileobj(self, *args: object, **kwargs: object) -> None:
        raise AssertionError("an identical duplicate chunk must not be uploaded again")


def test_s3_duplicate_chunk_checksum_closes_provider_body() -> None:
    content = b"duplicate"
    client = DuplicateChunkS3Client(content)
    storage = object.__new__(S3CompatibleBlobStorage)
    storage._bucket = "bucket"
    storage._client = client

    storage.put_upload_chunk(
        "session",
        0,
        io.BytesIO(content),
        hashlib.sha256(content).hexdigest(),
    )

    assert client.body.closed


class DiscardingS3Client:
    def __init__(self) -> None:
        self.deleted: list[dict[str, str]] = []

    def delete_object(self, **kwargs: str) -> None:
        self.deleted.append(kwargs)


def test_s3_discard_removes_the_assembled_final_object() -> None:
    client = DiscardingS3Client()
    storage = object.__new__(S3CompatibleBlobStorage)
    storage._bucket = "bucket"
    storage._client = client

    storage.discard_blob("completed/blob")

    assert client.deleted == [{"Bucket": "bucket", "Key": "completed/blob"}]


class ControlledAssemblyStorage(BlobStorage):
    def __init__(self, result: UploadAssemblyResult | None = None, *, fail: bool = False) -> None:
        self.result = result
        self.fail = fail
        self.discarded: list[str] = []

    def put_bytes(self, storage_key: str, content: bytes, media_type: str | None = None) -> None:
        raise AssertionError("legacy method not expected")

    def get_bytes(self, storage_key: str) -> bytes:
        raise AssertionError("not expected")

    def initialize_upload_session(self, session_id: str) -> None:
        return None

    def put_upload_chunk(
        self, session_id: str, chunk_number: int, content: io.BufferedIOBase, checksum_sha256: str
    ) -> None:
        content.read()

    def assemble_upload_session(
        self, session_id: str, storage_key: str, chunk_numbers: list[int]
    ) -> UploadAssemblyResult:
        if self.fail:
            raise OSError("assembly failed")
        assert self.result is not None
        return self.result

    def cleanup_upload_session(self, session_id: str) -> None:
        return None

    def discard_blob(self, storage_key: str) -> None:
        self.discarded.append(storage_key)


@pytest.mark.parametrize(
    ("storage", "expected_detail"),
    [
        (
            ControlledAssemblyStorage(
                UploadAssemblyResult(7, hashlib.sha256(b"ABCDEFG").hexdigest())
            ),
            "Assembled content size does not match the upload session.",
        ),
        (ControlledAssemblyStorage(fail=True), "Upload storage assembly failed."),
    ],
)
def test_assembly_size_or_storage_failure_keeps_session_recoverable_without_blob(
    tmp_path: Path,
    storage: ControlledAssemblyStorage,
    expected_detail: str,
) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    from openpdm.api.core import get_storage

    client.app.dependency_overrides[get_storage] = lambda: storage
    session_id = str(create_session(client, token)["id"])
    assert upload_chunk(client, token, session_id, 0, b"ABCD").status_code == 200
    assert upload_chunk(client, token, session_id, 1, b"EFGH").status_code == 200

    response = client.post(f"/blobs/upload-sessions/{session_id}/complete", headers=headers(token))

    assert response.status_code == 409
    assert response.json()["detail"] == expected_detail
    assert (
        client.get(f"/blobs/upload-sessions/{session_id}", headers=headers(token)).json()["status"]
        == "active"
    )
    with session_scope() as db:
        assert db.scalar(select(Blob)) is None
    if not storage.fail:
        assert len(storage.discarded) == 1


def test_repeated_integrity_mismatch_does_not_accumulate_local_final_objects(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    session_id = str(create_session(client, token, checksum_sha256="0" * 64)["id"])
    assert upload_chunk(client, token, session_id, 0, b"ABCD").status_code == 200
    assert upload_chunk(client, token, session_id, 1, b"EFGH").status_code == 200

    for _ in range(2):
        response = client.post(
            f"/blobs/upload-sessions/{session_id}/complete", headers=headers(token)
        )
        assert response.status_code == 409

    bucket_root = tmp_path / "blobs" / "openpdm-blobs"
    final_files = [
        path
        for path in bucket_root.rglob("*")
        if path.is_file() and "upload-sessions" not in path.parts
    ]
    assert final_files == []


class CleanupRevalidationSession:
    """Model a candidate that becomes terminal between discovery and row locking."""

    def __init__(self) -> None:
        self.scalar_calls = 0

    def scalars(self, statement: object) -> list[str]:
        return ["session-id"]

    def scalar(self, statement: object) -> None:
        self.scalar_calls += 1
        return None


class CleanupSpyStorage(ControlledAssemblyStorage):
    def __init__(self) -> None:
        super().__init__(UploadAssemblyResult(0, hashlib.sha256(b"").hexdigest()))
        self.cleaned: list[str] = []

    def cleanup_upload_session(self, session_id: str) -> None:
        self.cleaned.append(session_id)


def test_cleanup_revalidates_each_candidate_after_acquiring_its_lock() -> None:
    db = CleanupRevalidationSession()
    storage = CleanupSpyStorage()

    cleaned = BlobModule.cleanup_expired_upload_sessions(db, storage=storage)  # type: ignore[arg-type]

    assert cleaned == 0
    assert db.scalar_calls == 1
    assert storage.cleaned == []


def test_chunk_stream_rechecks_locked_session_after_concurrent_cancellation(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    session_id = str(create_session(client, token)["id"])
    storage = LocalFileBlobStorage(str(tmp_path / "blobs"), "openpdm-blobs")
    session_factory = get_session_factory()
    streaming_db = session_factory()
    cancelling_db = session_factory()
    try:
        streaming_actor = streaming_db.scalar(select(User).where(User.email == "owner@example.com"))
        cancelling_actor = cancelling_db.scalar(
            select(User).where(User.email == "owner@example.com")
        )
        assert streaming_actor is not None
        assert cancelling_actor is not None

        contract = BlobModule.get_upload_chunk_contract(
            streaming_db,
            session_id=session_id,
            actor=streaming_actor,
            storage=storage,
            assets=AssetsModule,
        )
        assert contract == (8, 4)

        BlobModule.cancel_upload_session(
            cancelling_db,
            session_id=session_id,
            actor=cancelling_actor,
            storage=storage,
            assets=AssetsModule,
        )
        cancelling_db.commit()

        with pytest.raises(HTTPException) as exc_info:
            BlobModule.put_upload_chunk(
                streaming_db,
                session_id=session_id,
                chunk_number=0,
                content=io.BytesIO(b"ABCD"),
                size_bytes=4,
                checksum_sha256=hashlib.sha256(b"ABCD").hexdigest(),
                actor=streaming_actor,
                storage=storage,
                assets=AssetsModule,
            )
        assert exc_info.value.status_code == 409
        streaming_db.rollback()
    finally:
        streaming_db.close()
        cancelling_db.close()

    with session_scope() as db:
        upload_session = db.get(BlobUploadSession, session_id)
        assert upload_session is not None
        assert upload_session.status == "cancelled"
        assert (
            db.scalar(select(BlobUploadChunk).where(BlobUploadChunk.session_id == session_id))
            is None
        )
        assert db.scalar(select(Blob)) is None
    assert not (tmp_path / "blobs" / "openpdm-blobs" / "upload-sessions" / session_id).exists()


def test_competing_sessions_keep_identical_chunk_and_completion_idempotent(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    session_id = str(create_session(client, token)["id"])
    storage = LocalFileBlobStorage(str(tmp_path / "blobs"), "openpdm-blobs")
    session_factory = get_session_factory()

    first_db = session_factory()
    second_db = session_factory()
    try:
        first_actor = first_db.scalar(select(User).where(User.email == "owner@example.com"))
        second_actor = second_db.scalar(select(User).where(User.email == "owner@example.com"))
        assert first_actor is not None
        assert second_actor is not None
        BlobModule.get_upload_session(
            first_db, session_id=session_id, actor=first_actor, storage=storage, assets=AssetsModule
        )
        BlobModule.get_upload_session(
            second_db,
            session_id=session_id,
            actor=second_actor,
            storage=storage,
            assets=AssetsModule,
        )

        checksum = hashlib.sha256(b"ABCD").hexdigest()
        first = BlobModule.put_upload_chunk(
            first_db,
            session_id=session_id,
            chunk_number=0,
            content=io.BytesIO(b"ABCD"),
            size_bytes=4,
            checksum_sha256=checksum,
            actor=first_actor,
            storage=storage,
            assets=AssetsModule,
        )
        first_db.commit()
        second = BlobModule.put_upload_chunk(
            second_db,
            session_id=session_id,
            chunk_number=0,
            content=io.BytesIO(b"ABCD"),
            size_bytes=4,
            checksum_sha256=checksum,
            actor=second_actor,
            storage=storage,
            assets=AssetsModule,
        )
        second_db.commit()
        assert first.id == second.id == session_id
    finally:
        first_db.close()
        second_db.close()

    assert upload_chunk(client, token, session_id, 1, b"EFGH").status_code == 200
    first_db = session_factory()
    second_db = session_factory()
    try:
        first_actor = first_db.scalar(select(User).where(User.email == "owner@example.com"))
        second_actor = second_db.scalar(select(User).where(User.email == "owner@example.com"))
        assert first_actor is not None
        assert second_actor is not None
        BlobModule.get_upload_session(
            first_db, session_id=session_id, actor=first_actor, storage=storage, assets=AssetsModule
        )
        BlobModule.get_upload_session(
            second_db,
            session_id=session_id,
            actor=second_actor,
            storage=storage,
            assets=AssetsModule,
        )

        first_completed = BlobModule.complete_upload_session(
            first_db, session_id=session_id, actor=first_actor, storage=storage, assets=AssetsModule
        )
        first_db.commit()
        second_completed = BlobModule.complete_upload_session(
            second_db,
            session_id=session_id,
            actor=second_actor,
            storage=storage,
            assets=AssetsModule,
        )
        second_db.commit()
        assert first_completed.blob_id == second_completed.blob_id
    finally:
        first_db.close()
        second_db.close()

    with session_scope() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(BlobUploadChunk)
                .where(BlobUploadChunk.session_id == session_id)
            )
            == 2
        )
        assert db.scalar(select(func.count()).select_from(Blob)) == 1
    final_files = [
        path
        for path in (tmp_path / "blobs" / "openpdm-blobs").rglob("*")
        if path.is_file() and "upload-sessions" not in path.parts
    ]
    assert len(final_files) == 1
    assert final_files[0].read_bytes() == b"ABCDEFGH"


POSTGRES_TEST_URL = os.environ.get("OPENPDM_TEST_POSTGRES_URL", "")


def test_postgresql_simultaneous_upload_and_completion_is_idempotent(
    tmp_path: Path,
) -> None:
    if not POSTGRES_TEST_URL.startswith("postgresql"):
        if os.environ.get("OPENPDM_REQUIRE_POSTGRES_TRANSFER_TEST") == "1":
            pytest.fail("required PostgreSQL transfer test has no PostgreSQL database URL")
        pytest.skip("set OPENPDM_TEST_POSTGRES_URL to an isolated PostgreSQL test database")

    os.environ["OPENPDM_DATABASE_URL"] = POSTGRES_TEST_URL
    os.environ["OPENPDM_S3_ENDPOINT_URL"] = "file://local"
    os.environ["OPENPDM_BLOB_LOCAL_ROOT"] = str(tmp_path / "blobs")
    os.environ["OPENPDM_PLUGIN_PACKAGE_ROOT"] = str(tmp_path / "plugins")
    os.environ["OPENPDM_PLUGIN_CONFIGURATION_KEY"] = Fernet.generate_key().decode()
    os.environ["OPENPDM_BLOB_UPLOAD_CHUNK_SIZE_BYTES"] = "4"
    os.environ["OPENPDM_BLOB_UPLOAD_MAX_SIZE_BYTES"] = "32"
    reset_blob_storage_cache()
    dispose_engines()
    from openpdm.main import create_app

    client = TestClient(create_app())
    with session_scope() as db:
        baseline_blob_ids = set(db.scalars(select(Blob.id)))
    email = f"transfer-{uuid.uuid4()}@example.com"
    token = register(client, email=email)
    session_id = str(create_session(client, token)["id"])

    def run_together(operation):
        barrier = threading.Barrier(2)

        def invoke():
            with TestClient(create_app()) as concurrent_client:
                barrier.wait()
                return operation(concurrent_client)

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(invoke), executor.submit(invoke)]
            return [future.result() for future in futures]

    chunk_results = run_together(
        lambda concurrent_client: upload_chunk(concurrent_client, token, session_id, 0, b"ABCD")
    )
    assert [response.status_code for response in chunk_results] == [200, 200]
    assert upload_chunk(client, token, session_id, 1, b"EFGH").status_code == 200

    completion_results = run_together(
        lambda concurrent_client: concurrent_client.post(
            f"/blobs/upload-sessions/{session_id}/complete", headers=headers(token)
        )
    )
    assert [response.status_code for response in completion_results] == [200, 200]
    assert completion_results[0].json()["blob"] == completion_results[1].json()["blob"]
    blob_id = completion_results[0].json()["blob"]["id"]
    with session_scope() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(BlobUploadChunk)
                .where(BlobUploadChunk.session_id == session_id)
            )
            == 2
        )
        all_blob_ids = set(db.scalars(select(Blob.id)))
        assert all_blob_ids - baseline_blob_ids == {blob_id}
        assert len(all_blob_ids) == len(baseline_blob_ids) + 1
        actor = db.scalar(select(User).where(User.email == email))
        assert actor is not None
        assert (
            db.scalar(
                select(func.count()).select_from(Blob).where(Blob.created_by_user_id == actor.id)
            )
            == 1
        )

    bucket_root = tmp_path / "blobs" / "openpdm-blobs"
    final_files = [
        path
        for path in bucket_root.rglob("*")
        if path.is_file() and "upload-sessions" not in path.parts
    ]
    assert len(final_files) == 1
    assert final_files[0].read_bytes() == b"ABCDEFGH"
    session_path = bucket_root / "upload-sessions" / session_id
    assert sorted(path.name for path in (session_path / "chunks").iterdir()) == ["0", "1"]
    LocalFileBlobStorage(str(tmp_path / "blobs"), "openpdm-blobs").cleanup_upload_session(
        session_id
    )
    assert not session_path.exists()
    assert final_files[0].read_bytes() == b"ABCDEFGH"


@pytest.mark.parametrize("terminal_command", ["complete", "cancel"])
def test_postgresql_cleanup_race_preserves_one_terminal_transition(
    tmp_path: Path, terminal_command: str
) -> None:
    if not POSTGRES_TEST_URL.startswith("postgresql"):
        if os.environ.get("OPENPDM_REQUIRE_POSTGRES_TRANSFER_TEST") == "1":
            pytest.fail("required PostgreSQL transfer test has no PostgreSQL database URL")
        pytest.skip("set OPENPDM_TEST_POSTGRES_URL to an isolated PostgreSQL test database")

    os.environ["OPENPDM_DATABASE_URL"] = POSTGRES_TEST_URL
    os.environ["OPENPDM_S3_ENDPOINT_URL"] = "file://local"
    os.environ["OPENPDM_BLOB_LOCAL_ROOT"] = str(tmp_path / "blobs")
    os.environ["OPENPDM_PLUGIN_PACKAGE_ROOT"] = str(tmp_path / "plugins")
    os.environ["OPENPDM_PLUGIN_CONFIGURATION_KEY"] = Fernet.generate_key().decode()
    os.environ["OPENPDM_BLOB_UPLOAD_CHUNK_SIZE_BYTES"] = "4"
    os.environ["OPENPDM_BLOB_UPLOAD_MAX_SIZE_BYTES"] = "32"
    reset_blob_storage_cache()
    dispose_engines()
    from openpdm.main import create_app

    client = TestClient(create_app())
    token = register(client, email=f"cleanup-race-{uuid.uuid4()}@example.com")
    session_id = str(create_session(client, token)["id"])
    assert upload_chunk(client, token, session_id, 0, b"ABCD").status_code == 200
    assert upload_chunk(client, token, session_id, 1, b"EFGH").status_code == 200
    with session_scope() as db:
        upload_session = db.get(BlobUploadSession, session_id)
        assert upload_session is not None
        upload_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

    storage = LocalFileBlobStorage(str(tmp_path / "blobs"), "openpdm-blobs")
    barrier = threading.Barrier(2)

    def cleanup() -> int:
        with session_scope() as db:
            barrier.wait()
            cleaned = BlobModule.cleanup_expired_upload_sessions(db, storage=storage)
            db.commit()
            return cleaned

    def terminal_request():
        with TestClient(create_app()) as concurrent_client:
            barrier.wait()
            if terminal_command == "complete":
                return concurrent_client.post(
                    f"/blobs/upload-sessions/{session_id}/complete", headers=headers(token)
                )
            return concurrent_client.delete(
                f"/blobs/upload-sessions/{session_id}", headers=headers(token)
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        cleanup_future = executor.submit(cleanup)
        terminal_future = executor.submit(terminal_request)
        cleaned = cleanup_future.result()
        terminal_response = terminal_future.result()

    assert cleaned in {0, 1}
    assert terminal_response.status_code == 410
    with session_scope() as db:
        upload_session = db.get(BlobUploadSession, session_id)
        assert upload_session is not None
        assert upload_session.status == "expired"
        assert upload_session.blob_id is None
        assert db.scalar(select(Blob).where(Blob.id == upload_session.blob_id)) is None
        assert (
            db.scalar(
                select(func.count())
                .select_from(BlobUploadChunk)
                .where(BlobUploadChunk.session_id == session_id)
            )
            == 0
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditRecord)
                .where(
                    AuditRecord.action == "blob.upload_session.expired",
                    AuditRecord.resource_id == session_id,
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(DomainEvent)
                .where(
                    DomainEvent.event_type == "blob.upload_session.expired",
                    DomainEvent.resource_id == session_id,
                )
            )
            == 1
        )
    session_path = tmp_path / "blobs" / "openpdm-blobs" / "upload-sessions" / session_id
    assert not session_path.exists()
    final_files = [
        path
        for path in (tmp_path / "blobs" / "openpdm-blobs").rglob("*")
        if path.is_file() and "upload-sessions" not in path.parts
    ]
    assert final_files == []


class PaginatedS3Client:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.calls: list[dict[str, object]] = []

    def list_objects_v2(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            return {
                "Contents": [
                    {"Key": f"upload-sessions/session/chunks/{number}"} for number in range(1000)
                ],
                "IsTruncated": True,
                "NextContinuationToken": "next-page",
            }
        return {"Contents": [{"Key": "upload-sessions/session/chunks/1000"}], "IsTruncated": False}

    def delete_objects(self, *, Bucket: str, Delete: dict[str, list[dict[str, str]]]) -> None:
        self.deleted.extend(item["Key"] for item in Delete["Objects"])


def test_s3_cleanup_paginates_all_upload_session_objects() -> None:
    storage = object.__new__(S3CompatibleBlobStorage)
    storage._bucket = "bucket"
    storage._client = PaginatedS3Client()

    storage.cleanup_upload_session("session")

    assert len(storage._client.calls) == 2
    assert len(storage._client.deleted) == 1001


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

    def discard_blob(self, storage_key: str) -> None:
        return None


def test_storage_failure_keeps_session_recoverable(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register(client, email="owner@example.com")
    from openpdm.api.core import get_storage

    client.app.dependency_overrides[get_storage] = lambda: FailingUploadStorage()
    asset_id = create_asset(client, token)["id"]
    response = client.post(
        "/blobs/upload-sessions",
        headers=headers(token),
        json={
            "asset_id": asset_id,
            "filename": "wing.step",
            "media_type": "application/step",
            "total_size_bytes": 8,
        },
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
