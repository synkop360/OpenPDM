from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from openpdm.infrastructure.blob_storage import reset_blob_storage_cache
from openpdm.infrastructure.database import dispose_engines

PLUGIN_ID = "org.openpdm.freecad"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ASSEMBLY_FIXTURE = REPOSITORY_ROOT / "sample" / "freecad" / "native" / "AssemblyExample.FCStd"


def build_client(tmp_path: Path) -> TestClient:
    os.environ["OPENPDM_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'freecad.db'}"
    os.environ["OPENPDM_S3_ENDPOINT_URL"] = "file://local"
    os.environ["OPENPDM_BLOB_LOCAL_ROOT"] = str(tmp_path / "blobs")
    os.environ["OPENPDM_PLUGIN_PACKAGE_ROOT"] = str(tmp_path / "plugins")
    os.environ["OPENPDM_PLUGIN_CONFIGURATION_KEY"] = Fernet.generate_key().decode()
    os.environ["OPENPDM_PLUGIN_RUNTIME_TIMEOUT_SECONDS"] = "15"
    os.environ["OPENPDM_PLUGIN_RUNTIME_FUEL"] = "25000000"
    os.environ["OPENPDM_PLUGIN_ANALYSIS_PROVIDER_FUEL"] = "200000000"
    reset_blob_storage_cache()
    dispose_engines()
    from openpdm.main import create_app

    client = TestClient(create_app())
    client.__enter__()
    return client


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def build_package(output: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            str(REPOSITORY_ROOT / "scripts" / "build_freecad_plugin.py"),
            "--output",
            str(output),
        ],
        check=True,
    )


def create_asset(
    client: TestClient, headers: dict[str, str], project_id: str, name: str
) -> dict[str, str]:
    response = client.post(
        f"/projects/{project_id}/assets",
        headers=headers,
        json={"name": name, "description": ""},
    )
    assert response.status_code == 201, response.text
    return response.json()


def invoke_analysis(
    client: TestClient,
    headers: dict[str, str],
    *,
    representation_id: str,
    project_id: str,
    organization_id: str,
    relationship_mappings: dict[str, str],
) -> dict[str, list[dict[str, object]]]:
    response = client.post(
        f"/plugins/{PLUGIN_ID}/providers/analysis",
        headers=headers,
        json={
            "representation_id": representation_id,
            "project_id": project_id,
            "organization_id": organization_id,
            "relationship_mappings": relationship_mappings,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_freecad_official_plugin_exercises_the_public_analysis_journey(tmp_path: Path) -> None:
    package_path = tmp_path / "freecad.openpdm-plugin"
    build_package(package_path)
    client = build_client(tmp_path)
    try:
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
            json={"organization_id": organization["id"], "name": "Mechanical", "description": ""},
        ).json()
        source_asset = create_asset(client, headers, project["id"], "Assembly")
        target_asset = create_asset(client, headers, project["id"], "Mapped dependency")
        revision = client.post(
            f"/assets/{source_asset['id']}/revisions",
            headers=headers,
            json={"comment": "Initial document"},
        ).json()
        blob = client.post(
            "/blobs/uploads",
            headers=headers,
            files={
                "file": (
                    ASSEMBLY_FIXTURE.name,
                    ASSEMBLY_FIXTURE.read_bytes(),
                    "application/octet-stream",
                )
            },
        ).json()
        representation_response = client.post(
            f"/revisions/{revision['id']}/representations",
            headers=headers,
            json={
                "name": "native",
                "media_type": "application/octet-stream",
                "blob_id": blob["id"],
            },
        )
        assert representation_response.status_code == 201, representation_response.text
        representation = representation_response.json()

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
        assert installed.json()["plugin_type"] == "official"
        enabled = client.post(
            f"/plugins/{PLUGIN_ID}/state", headers=headers, json={"enabled": True}
        )
        assert enabled.status_code == 200, enabled.text
        assert enabled.json()["lifecycle_state"] == "running"

        discovered = client.get("/providers", headers=headers)
        assert discovered.status_code == 200
        assert discovered.json() == [
            {"id": PLUGIN_ID, "name": "FreeCAD Analysis", "capabilities": ["analysis_provider"]}
        ]

        mapping = {"document.link.Base": target_asset["id"]}
        first = invoke_analysis(
            client,
            headers,
            representation_id=representation["id"],
            project_id=project["id"],
            organization_id=organization["id"],
            relationship_mappings=mapping,
        )
        metadata = {entry["key"]: entry for entry in first["metadata"]}
        assert metadata["freecad.document.label"]["value"] == "AssemblyExample"
        assert metadata["freecad.document.object_count"]["value"] == 53
        assert len(first["references"]) == 12
        assert len(first["relationships"]) == 1
        assert first["relationships"][0]["source_asset_id"] == source_asset["id"]
        assert first["relationships"][0]["target_asset_id"] == target_asset["id"]

        repeated = invoke_analysis(
            client,
            headers,
            representation_id=representation["id"],
            project_id=project["id"],
            organization_id=organization["id"],
            relationship_mappings=mapping,
        )
        assert len(repeated["metadata"]) == 3
        assert len(repeated["references"]) == 12
        assert len(repeated["relationships"]) == 1
        assert len(client.get(f"/metadata/asset/{source_asset['id']}", headers=headers).json()) == 3
        assert (
            len(client.get(f"/assets/{source_asset['id']}/references", headers=headers).json())
            == 12
        )
        assert (
            len(client.get(f"/assets/{source_asset['id']}/relationships", headers=headers).json())
            == 1
        )

        unmapped = invoke_analysis(
            client,
            headers,
            representation_id=representation["id"],
            project_id=project["id"],
            organization_id=organization["id"],
            relationship_mappings={},
        )
        assert len(unmapped["references"]) == 13
        assert unmapped["relationships"] == []
    finally:
        client.__exit__(None, None, None)
