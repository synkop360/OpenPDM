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

PLUGIN_ID = "org.openpdm.examples.asset-categories"


def build_client(tmp_path: Path) -> TestClient:
    os.environ["OPENPDM_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'categories.db'}"
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


def test_dummy_categories_plugin_exercises_public_extension_api(tmp_path: Path) -> None:
    package_path = tmp_path / "asset-categories.openpdm-plugin"
    subprocess.run(
        [
            sys.executable,
            str(
                Path(__file__).resolve().parents[2] / "scripts" / "build_dummy_categories_plugin.py"
            ),
            "--output",
            str(package_path),
        ],
        check=True,
    )
    client = build_client(tmp_path)
    assert (
        client.post(
            "/auth/register",
            json={"email": "admin@example.com", "display_name": "Admin", "password": "secret123"},
        ).status_code
        == 201
    )
    token = client.post(
        "/auth/sign-in", json={"email": "admin@example.com", "password": "secret123"}
    ).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    organization = client.post(
        "/organizations", headers=headers, json={"name": "Acme", "slug": "acme"}
    ).json()
    project = client.post(
        "/projects",
        headers=headers,
        json={"organization_id": organization["id"], "name": "Categories", "description": ""},
    ).json()

    installed = client.post(
        "/plugins/packages",
        params={"plugin_type": "community"},
        headers=headers,
        files={"package": (package_path.name, package_path.read_bytes(), "application/zip")},
    )
    assert installed.status_code == 201, installed.text
    assert installed.json()["plugin_type"] == "community"
    assert (
        client.put(
            f"/plugins/{PLUGIN_ID}/configuration",
            headers=headers,
            json={"values": {"default_category": "drawing", "name_prefix": "Demo"}},
        ).status_code
        == 200
    )
    enabled = client.post(f"/plugins/{PLUGIN_ID}/state", headers=headers, json={"enabled": True})
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["lifecycle_state"] == "running"

    created = client.post(
        f"/plugins/{PLUGIN_ID}/providers/assets/{project['id']}",
        headers=headers,
        json={
            "organization_id": organization["id"],
            "payload": {"name": "Layout", "description": "Category API demonstration"},
        },
    )
    assert created.status_code == 200, created.text
    asset_id = created.json()[0]["id"]
    asset = client.get(f"/assets/{asset_id}", headers=headers)
    assert asset.status_code == 200
    assert asset.json()["name"] == "Demo: Layout"

    metadata = client.post(
        f"/plugins/{PLUGIN_ID}/providers/metadata",
        headers=headers,
        json={
            "target_type": "asset",
            "target_id": asset_id,
            "project_id": project["id"],
            "organization_id": organization["id"],
        },
    )
    assert metadata.status_code == 200, metadata.text
    entries = {entry["key"]: entry for entry in metadata.json()}
    assert entries["classification.category"]["value"] == "drawing"
    assert entries["classification.category"]["source"] == f"plugin:{PLUGIN_ID}"
    assert entries["classification.managed_by"]["value"] == PLUGIN_ID

    deadline = time.monotonic() + 20
    deliveries: list[dict[str, object]] = []
    while time.monotonic() < deadline:
        response = client.get(f"/plugins/{PLUGIN_ID}/event-deliveries", headers=headers)
        assert response.status_code == 200
        deliveries = response.json()
        if any(
            item["event_type"] == "asset.created" and item["status"] == "delivered"
            for item in deliveries
        ):
            break
        time.sleep(0.25)
    assert any(
        item["event_type"] == "asset.created" and item["status"] == "delivered"
        for item in deliveries
    )
    client.__exit__(None, None, None)
