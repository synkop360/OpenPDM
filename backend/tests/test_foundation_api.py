from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient

from openpdm.infrastructure.blob_storage import reset_blob_storage_cache
from openpdm.infrastructure.database import dispose_engines


def build_client(tmp_path: Path) -> TestClient:
    os.environ["OPENPDM_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'openpdm.db'}"
    os.environ["OPENPDM_S3_ENDPOINT_URL"] = "file://local"
    os.environ["OPENPDM_BLOB_LOCAL_ROOT"] = str(tmp_path / "blobs")
    reset_blob_storage_cache()
    dispose_engines()
    from openpdm.main import create_app

    return TestClient(create_app())


def test_foundation_application_smoke(tmp_path: Path) -> None:
    client = build_client(tmp_path)

    health = client.get("/health")
    foundation = client.get("/foundation")

    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert foundation.status_code == 200
    assert foundation.json()["architecture"] == "Modular Monolith"
