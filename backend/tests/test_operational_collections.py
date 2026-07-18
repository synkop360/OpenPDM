from __future__ import annotations

import os
from pathlib import Path

from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select

from openpdm.infrastructure.blob_storage import reset_blob_storage_cache
from openpdm.infrastructure.database import (
    dispose_engines,
    initialize_database,
    session_scope,
)
from openpdm.infrastructure.settings import Settings
from openpdm.platform_core.modules.models import (
    NotificationRecord,
    PluginRecord,
    ProjectAssetView,
    User,
)


def build_client(tmp_path: Path) -> TestClient:
    os.environ["OPENPDM_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'openpdm.db'}"
    os.environ["OPENPDM_S3_ENDPOINT_URL"] = "file://local"
    os.environ["OPENPDM_BLOB_LOCAL_ROOT"] = str(tmp_path / "blobs")
    os.environ["OPENPDM_PLUGIN_PACKAGE_ROOT"] = str(tmp_path / "plugins")
    os.environ["OPENPDM_PLUGIN_CONFIGURATION_KEY"] = Fernet.generate_key().decode()
    reset_blob_storage_cache()
    dispose_engines()
    from openpdm.main import create_app

    return TestClient(create_app())


def register(client: TestClient, *, email: str, name: str) -> tuple[str, dict[str, object]]:
    created = client.post(
        "/auth/register",
        json={"email": email, "display_name": name, "password": "secret123"},
    )
    assert created.status_code == 201
    signed_in = client.post("/auth/sign-in", json={"email": email, "password": "secret123"})
    assert signed_in.status_code == 200
    return signed_in.json()["token"], created.json()


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_project(client: TestClient, token: str) -> tuple[dict[str, object], dict[str, object]]:
    organization = client.post(
        "/organizations",
        headers=headers(token),
        json={"name": "Operations", "slug": "operations"},
    ).json()
    project = client.post(
        "/projects",
        headers=headers(token),
        json={
            "organization_id": organization["id"],
            "name": "Operational UI",
            "description": "Paged API tests",
        },
    ).json()
    return organization, project


def add_project_member(
    client: TestClient,
    owner_token: str,
    *,
    organization_id: str,
    project_id: str,
    email: str,
) -> None:
    added = client.post(
        f"/organizations/{organization_id}/members",
        headers=headers(owner_token),
        json={"user_email": email, "role": "Viewer"},
    )
    assert added.status_code == 200
    added = client.post(
        f"/projects/{project_id}/members",
        headers=headers(owner_token),
        json={"user_email": email, "role": "Viewer"},
    )
    assert added.status_code == 200


def test_asset_cursor_page_is_stable_bounded_filtered_and_backward_compatible(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    token, _ = register(client, email="owner@example.com", name="Owner")
    _, project = create_project(client, token)
    project_id = str(project["id"])
    for name, status in [("Bravo", "draft"), ("Charlie", "active"), ("Delta", "active")]:
        asset = client.post(
            f"/projects/{project_id}/assets",
            headers=headers(token),
            json={"name": name, "description": f"{name} description"},
        )
        assert asset.status_code == 201
        if status != "draft":
            changed = client.post(
                f"/assets/{asset.json()['id']}/status",
                headers=headers(token),
                json={"status": status},
            )
            assert changed.status_code == 200

    first = client.get(
        f"/projects/{project_id}/assets/page?limit=2&sort=name&direction=asc",
        headers=headers(token),
    )
    assert first.status_code == 200
    assert [item["name"] for item in first.json()["items"]] == ["Bravo", "Charlie"]
    cursor = first.json()["next_cursor"]
    assert cursor

    inserted = client.post(
        f"/projects/{project_id}/assets",
        headers=headers(token),
        json={"name": "Alpha", "description": "Inserted before the cursor"},
    )
    assert inserted.status_code == 201
    second = client.get(
        f"/projects/{project_id}/assets/page?limit=2&sort=name&direction=asc&cursor={cursor}",
        headers=headers(token),
    )
    assert second.status_code == 200
    assert [item["name"] for item in second.json()["items"]] == ["Delta"]

    active = client.get(
        f"/projects/{project_id}/assets/page?status=active&q=ta",
        headers=headers(token),
    )
    assert active.status_code == 200
    assert [item["name"] for item in active.json()["items"]] == ["Delta"]
    assert (
        client.get(
            f"/projects/{project_id}/assets/page?cursor=invalid",
            headers=headers(token),
        ).status_code
        == 400
    )
    assert (
        client.get(
            f"/projects/{project_id}/assets/page?limit=101",
            headers=headers(token),
        ).status_code
        == 422
    )
    legacy = client.get(f"/projects/{project_id}/assets", headers=headers(token))
    assert legacy.status_code == 200
    assert len(legacy.json()) == 4


def test_membership_pages_filter_and_enforce_owning_module_authorization(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    owner_token, _ = register(client, email="owner@example.com", name="Owner")
    viewer_token, _ = register(client, email="viewer@example.com", name="Viewer")
    organization, project = create_project(client, owner_token)
    add_project_member(
        client,
        owner_token,
        organization_id=str(organization["id"]),
        project_id=str(project["id"]),
        email="viewer@example.com",
    )
    organization_page = client.get(
        f"/organizations/{organization['id']}/members/page?role=Viewer&q=viewer",
        headers=headers(owner_token),
    )
    assert organization_page.status_code == 200
    assert [item["user"]["email"] for item in organization_page.json()["items"]] == [
        "viewer@example.com"
    ]
    project_page = client.get(
        f"/projects/{project['id']}/members/page?limit=1",
        headers=headers(viewer_token),
    )
    assert project_page.status_code == 200
    assert len(project_page.json()["items"]) == 1

    other_organization = client.post(
        "/organizations",
        headers=headers(owner_token),
        json={"name": "Private", "slug": "private"},
    ).json()
    denied = client.get(
        f"/organizations/{other_organization['id']}/members/page",
        headers=headers(viewer_token),
    )
    assert denied.status_code == 403


def test_saved_project_asset_views_are_private_validated_and_owned(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    owner_token, _ = register(client, email="owner@example.com", name="Owner")
    viewer_token, _ = register(client, email="viewer@example.com", name="Viewer")
    organization, project = create_project(client, owner_token)
    add_project_member(
        client,
        owner_token,
        organization_id=str(organization["id"]),
        project_id=str(project["id"]),
        email="viewer@example.com",
    )
    definition = {
        "project_id": project["id"],
        "name": "Active assets",
        "filters": {"status": "active", "query": "motor"},
        "sort": {"field": "updated_at", "direction": "desc"},
        "density": "compact",
        "selected_columns": ["name", "status", "updated_at"],
    }
    created = client.post("/users/me/project-views", headers=headers(owner_token), json=definition)
    assert created.status_code == 201
    view_id = created.json()["id"]
    assert client.get("/users/me/project-views", headers=headers(viewer_token)).json() == []
    viewer_view = client.post(
        "/users/me/project-views",
        headers=headers(viewer_token),
        json={**definition, "name": "Viewer view"},
    )
    assert viewer_view.status_code == 201
    project_members = client.get(
        f"/projects/{project['id']}/members", headers=headers(owner_token)
    ).json()
    viewer_membership_id = next(
        member["id"]
        for member in project_members
        if member["user"]["email"] == "viewer@example.com"
    )
    removed = client.delete(
        f"/projects/{project['id']}/members/{viewer_membership_id}",
        headers=headers(owner_token),
    )
    assert removed.status_code == 204
    assert client.get("/users/me/project-views", headers=headers(viewer_token)).json() == []
    assert (
        client.get(f"/users/me/project-views/{view_id}", headers=headers(viewer_token)).status_code
        == 404
    )

    invalid = {**definition, "name": "Invalid", "filters": {"plugin_field": "x"}}
    assert (
        client.post(
            "/users/me/project-views", headers=headers(owner_token), json=invalid
        ).status_code
        == 400
    )
    updated = client.put(
        f"/users/me/project-views/{view_id}",
        headers=headers(owner_token),
        json={
            key: value
            for key, value in {**definition, "name": "My active assets"}.items()
            if key != "project_id"
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "My active assets"
    assert (
        client.delete(
            f"/users/me/project-views/{view_id}", headers=headers(owner_token)
        ).status_code
        == 204
    )


def test_notification_page_and_batch_acknowledgment_are_atomic(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token, user = register(client, email="owner@example.com", name="Owner")
    _, project = create_project(client, token)
    with session_scope() as db:
        notifications = [
            NotificationRecord(
                recipient_user_id=str(user["id"]),
                project_id=str(project["id"]),
                event_type=f"test.event.{index}",
            )
            for index in range(3)
        ]
        db.add_all(notifications)
        db.flush()
        notification_ids = [item.id for item in notifications]

    failed = client.post(
        "/notifications/read",
        headers=headers(token),
        json={"notification_ids": [notification_ids[0], "missing"]},
    )
    assert failed.status_code == 404
    unread = client.get("/notifications/page?is_read=false", headers=headers(token))
    assert unread.status_code == 200
    assert len(unread.json()["items"]) == 3

    selected = client.post(
        "/notifications/read",
        headers=headers(token),
        json={"notification_ids": notification_ids[:2]},
    )
    assert selected.status_code == 200
    assert selected.json()["updated_count"] == 2
    remaining = client.post(
        "/notifications/read",
        headers=headers(token),
        json={"all_matching": True, "project_id": project["id"], "is_read": False},
    )
    assert remaining.status_code == 200
    assert remaining.json()["notification_ids"] == [notification_ids[2]]


def test_plugin_page_and_configuration_include_bounded_schema(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token, user = register(client, email="admin@example.com", name="Admin")
    schema = {
        "type": "object",
        "properties": {"prefix": {"type": "string", "secret": False}},
        "additionalProperties": False,
    }
    with session_scope() as db:
        actor = db.scalar(select(User).where(User.id == str(user["id"])))
        assert actor is not None
        actor.is_platform_admin = True
        db.add_all(
            [
                PluginRecord(
                    id=f"org.openpdm.plugin-{index}",
                    name=f"Plugin {index}",
                    version="1.0.0",
                    plugin_type="community",
                    lifecycle_state="installed",
                    configuration_schema=schema,
                )
                for index in range(2)
            ]
        )
    page = client.get("/plugins/page?limit=1&q=plugin", headers=headers(token))
    assert page.status_code == 200
    assert len(page.json()["items"]) == 1
    assert page.json()["next_cursor"]
    configuration = client.get(
        "/plugins/org.openpdm.plugin-0/configuration", headers=headers(token)
    )
    assert configuration.status_code == 200
    assert configuration.json()["configuration_schema"] == schema


def test_project_asset_view_migration_is_upgradeable(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    os.environ["OPENPDM_DATABASE_URL"] = database_url
    dispose_engines()
    initialize_database(Settings(database_url=database_url))
    engine = create_engine(database_url)
    ProjectAssetView.__table__.drop(engine)
    config = Config("alembic.ini")
    command.stamp(config, "20260712_0004")
    command.upgrade(config, "head")
    assert "project_asset_views" in inspect(engine).get_table_names()
