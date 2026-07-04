from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from openpdm.infrastructure.blob_storage import reset_blob_storage_cache
from openpdm.infrastructure.database import dispose_engines


def build_client(tmp_path: Path) -> TestClient:
    import os

    os.environ["OPENPDM_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'openpdm.db'}"
    os.environ["OPENPDM_S3_ENDPOINT_URL"] = "file://local"
    os.environ["OPENPDM_BLOB_LOCAL_ROOT"] = str(tmp_path / "blobs")
    reset_blob_storage_cache()
    dispose_engines()
    from openpdm.main import create_app

    return TestClient(create_app())


def register_and_sign_in(
    client: TestClient, *, email: str, display_name: str, password: str
) -> str:
    response = client.post(
        "/auth/register",
        json={"email": email, "display_name": display_name, "password": password},
    )
    assert response.status_code == 201
    sign_in_response = client.post("/auth/sign-in", json={"email": email, "password": password})
    assert sign_in_response.status_code == 200
    return sign_in_response.json()["token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_health_and_foundation_expose_core_platform_metadata(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    assert client.get("/health").json() == {"status": "ok"}

    foundation = client.get("/foundation")

    assert foundation.status_code == 200
    assert foundation.json()["phase"] == "Core Platform"
    assert foundation.json()["architecture"] == "Modular Monolith"


def test_access_and_membership_flow(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    owner_token = register_and_sign_in(
        client,
        email="owner@example.com",
        display_name="Owner",
        password="secret123",
    )
    register_and_sign_in(
        client,
        email="member@example.com",
        display_name="Member",
        password="secret123",
    )

    organization = client.post(
        "/organizations",
        headers=auth_header(owner_token),
        json={"name": "Acme", "slug": "acme"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(owner_token),
        json={"organization_id": organization["id"], "name": "Rocket", "description": "Phase 1"},
    ).json()

    member_user = client.post(
        "/auth/sign-in",
        json={"email": "member@example.com", "password": "secret123"},
    ).json()
    member_session = client.get("/auth/session", headers=auth_header(member_user["token"]))
    member_user_id = member_session.json()["user"]["id"]

    add_project_before_org = client.post(
        f"/projects/{project['id']}/members",
        headers=auth_header(owner_token),
        json={"user_id": member_user_id, "role": "Viewer"},
    )
    assert add_project_before_org.status_code == 400

    add_org_member = client.post(
        f"/organizations/{organization['id']}/members",
        headers=auth_header(owner_token),
        json={"user_id": member_user_id, "role": "Contributor"},
    )
    assert add_org_member.status_code == 200

    add_project_member = client.post(
        f"/projects/{project['id']}/members",
        headers=auth_header(owner_token),
        json={"user_id": member_user_id, "role": "Viewer"},
    )
    assert add_project_member.status_code == 200

    project_access = client.get(
        f"/projects/{project['id']}",
        headers=auth_header(member_user["token"]),
    )
    assert project_access.status_code == 200
    assert project_access.json()["organization_id"] == organization["id"]


def test_asset_lifecycle_blob_and_metadata_flow(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register_and_sign_in(
        client,
        email="builder@example.com",
        display_name="Builder",
        password="secret123",
    )

    organization = client.post(
        "/organizations",
        headers=auth_header(token),
        json={"name": "Acme", "slug": "acme"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(token),
        json={"organization_id": organization["id"], "name": "Rocket", "description": "Phase 1"},
    ).json()
    asset = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(token),
        json={"name": "Wing", "description": "Main wing"},
    ).json()
    revision = client.post(
        f"/assets/{asset['id']}/revisions",
        headers=auth_header(token),
        json={"comment": "Initial release"},
    ).json()
    blob = client.post(
        "/blobs/uploads",
        headers=auth_header(token),
        files={"file": ("wing.step", b"solid-data", "application/step")},
    ).json()
    representation = client.post(
        f"/revisions/{revision['id']}/representations",
        headers=auth_header(token),
        json={"name": "native", "media_type": "application/step", "blob_id": blob["id"]},
    ).json()

    assert representation["blob_id"] == blob["id"]

    status_update = client.post(
        f"/assets/{asset['id']}/status",
        headers=auth_header(token),
        json={"status": "active"},
    )
    assert status_update.status_code == 200
    assert status_update.json()["status"] == "active"

    metadata = client.put(
        f"/metadata/asset/{asset['id']}",
        headers=auth_header(token),
        json={"key": "material", "value": "7075-T6", "value_type": "string", "source": "user"},
    )
    assert metadata.status_code == 200

    history = client.get(f"/assets/{asset['id']}/history", headers=auth_header(token))
    assert history.status_code == 200
    assert history.json()[0]["number"] == 1

    blob_download = client.get(f"/blobs/{blob['id']}/download", headers=auth_header(token))
    assert blob_download.status_code == 200
    assert blob_download.content == b"solid-data"


def test_search_and_plugin_registry_flow(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register_and_sign_in(
        client,
        email="search@example.com",
        display_name="Search",
        password="secret123",
    )

    organization = client.post(
        "/organizations",
        headers=auth_header(token),
        json={"name": "Acme", "slug": "acme"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(token),
        json={"organization_id": organization["id"], "name": "Rocket", "description": "Phase 1"},
    ).json()
    asset = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(token),
        json={"name": "Wing Panel", "description": "Lightweight assembly part"},
    ).json()
    client.put(
        f"/metadata/asset/{asset['id']}",
        headers=auth_header(token),
        json={"key": "material", "value": "aluminum", "value_type": "string", "source": "user"},
    )
    client.post(
        f"/assets/{asset['id']}/revisions",
        headers=auth_header(token),
        json={"comment": "lightweight version"},
    )

    search = client.get(
        "/search/assets",
        headers=auth_header(token),
        params={"q": "lightweight", "project_id": project["id"]},
    )
    assert search.status_code == 200
    assert search.json()[0]["id"] == asset["id"]

    plugin = client.post(
        "/plugins",
        headers=auth_header(token),
        json={
            "id": "org.openpdm.sample",
            "name": "Sample Provider",
            "version": "0.1.0",
            "type": "official",
            "capabilities": [],
        },
    )
    assert plugin.status_code == 201

    plugin_state = client.post(
        "/plugins/org.openpdm.sample/state",
        headers=auth_header(token),
        json={"enabled": False},
    )
    assert plugin_state.status_code == 200
    assert plugin_state.json()["enabled"] is False


def test_sign_out_revokes_session(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register_and_sign_in(
        client,
        email="auth@example.com",
        display_name="Auth",
        password="secret123",
    )

    sign_out = client.post("/auth/sign-out", headers=auth_header(token))
    assert sign_out.status_code == 200

    after_sign_out = client.get("/auth/session", headers=auth_header(token))
    assert after_sign_out.status_code == 401
