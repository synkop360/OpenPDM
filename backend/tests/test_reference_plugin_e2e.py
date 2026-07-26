from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from openpdm.infrastructure.blob_storage import reset_blob_storage_cache
from openpdm.infrastructure.database import dispose_engines


def build_client(tmp_path: Path) -> TestClient:
    os.environ["OPENPDM_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'reference.db'}"
    os.environ["OPENPDM_S3_ENDPOINT_URL"] = "file://local"
    os.environ["OPENPDM_BLOB_LOCAL_ROOT"] = str(tmp_path / "blobs")
    os.environ["OPENPDM_PLUGIN_PACKAGE_ROOT"] = str(tmp_path / "plugins")
    os.environ["OPENPDM_PLUGIN_CONFIGURATION_KEY"] = Fernet.generate_key().decode()
    os.environ["OPENPDM_PLUGIN_RUNTIME_TIMEOUT_SECONDS"] = "15"
    os.environ["OPENPDM_PLUGIN_RUNTIME_FUEL"] = "25000000"
    reset_blob_storage_cache()
    dispose_engines()
    from openpdm.main import create_app

    client = TestClient(create_app())
    client.__enter__()
    return client


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_reference_official_plugin_exercises_phase4_journey(tmp_path: Path) -> None:
    package_path = tmp_path / "reference.openpdm-plugin"
    subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[2] / "scripts" / "build_reference_plugin.py"),
            "--output",
            str(package_path),
        ],
        check=True,
    )
    client = build_client(tmp_path)
    registered = client.post(
        "/auth/register",
        json={"email": "admin@example.com", "display_name": "Admin", "password": "secret123"},
    )
    assert registered.status_code == 201
    token = client.post(
        "/auth/sign-in", json={"email": "admin@example.com", "password": "secret123"}
    ).json()["token"]
    headers = authorization(token)
    organization = client.post(
        "/organizations", headers=headers, json={"name": "Acme", "slug": "acme"}
    ).json()
    project = client.post(
        "/projects",
        headers=headers,
        json={"organization_id": organization["id"], "name": "Reference", "description": ""},
    ).json()
    asset = client.post(
        f"/projects/{project['id']}/assets",
        headers=headers,
        json={"name": "Seed", "description": ""},
    ).json()

    installed = client.post(
        "/plugins/packages",
        params={"plugin_type": "official"},
        headers=headers,
        files={
            "package": (
                package_path.name,
                package_path.read_bytes(),
                "application/zip",
            )
        },
    )
    assert installed.status_code == 201, installed.text
    configured = client.put(
        "/plugins/org.openpdm.reference/configuration",
        headers=headers,
        json={"values": {"metadata_key": "reference.verified"}},
    )
    assert configured.status_code == 200
    enabled = client.post(
        "/plugins/org.openpdm.reference/state",
        headers=headers,
        json={"enabled": True},
    )
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["lifecycle_state"] == "running"

    metadata = client.post(
        "/plugins/org.openpdm.reference/providers/metadata",
        headers=headers,
        json={
            "target_type": "asset",
            "target_id": asset["id"],
            "project_id": project["id"],
            "organization_id": organization["id"],
        },
    )
    assert metadata.status_code == 200, metadata.text
    assert metadata.json()[0]["key"] == "reference.verified"
    assert metadata.json()[0]["source"] == "plugin:org.openpdm.reference"

    created = client.post(
        f"/plugins/org.openpdm.reference/providers/assets/{project['id']}",
        headers=headers,
        json={
            "organization_id": organization["id"],
            "payload": {"name": "Created through Extension API", "description": "generic"},
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()[0]["resource_type"] == "asset"

    deadline = time.monotonic() + 20
    deliveries: list[dict[str, object]] = []
    while time.monotonic() < deadline:
        response = client.get("/plugins/org.openpdm.reference/event-deliveries", headers=headers)
        assert response.status_code == 200
        deliveries = response.json()
        if deliveries and deliveries[0]["status"] == "delivered":
            break
        time.sleep(0.25)
    assert deliveries
    assert deliveries[0]["status"] == "delivered"
    client.__exit__(None, None, None)
