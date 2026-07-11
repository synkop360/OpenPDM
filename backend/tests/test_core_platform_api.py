from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import select
from wasmtime import wat2wasm

from openpdm.extension_api import Capability, PluginManifest, build_plugin_package
from openpdm.infrastructure.blob_storage import reset_blob_storage_cache
from openpdm.infrastructure.database import dispose_engines, session_scope
from openpdm.platform_core.modules.models import (
    AssetReference,
    AssetRelationship,
    AuditRecord,
    DomainEvent,
    NotificationRecord,
    PluginRecord,
    ProjectMembership,
    User,
)


def build_client(tmp_path: Path) -> TestClient:
    import os

    os.environ["OPENPDM_DATABASE_URL"] = f"sqlite+pysqlite:///{tmp_path / 'openpdm.db'}"
    os.environ["OPENPDM_S3_ENDPOINT_URL"] = "file://local"
    os.environ["OPENPDM_BLOB_LOCAL_ROOT"] = str(tmp_path / "blobs")
    os.environ["OPENPDM_PLUGIN_PACKAGE_ROOT"] = str(tmp_path / "plugins")
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


def membership_by_email(memberships: list[dict[str, object]], email: str) -> dict[str, object]:
    return next(
        membership
        for membership in memberships
        if isinstance(membership.get("user"), dict) and membership["user"].get("email") == email
    )


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


def test_membership_lifecycle_enforces_owner_safety_and_revokes_project_access(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    owner_token = register_and_sign_in(
        client, email="membership-owner@example.com", display_name="Owner", password="secret123"
    )
    maintainer_token = register_and_sign_in(
        client,
        email="membership-maintainer@example.com",
        display_name="Maintainer",
        password="secret123",
    )
    member_token = register_and_sign_in(
        client, email="membership-user@example.com", display_name="Member", password="secret123"
    )
    member_user = client.get("/auth/session", headers=auth_header(member_token)).json()["user"]

    organization = client.post(
        "/organizations",
        headers=auth_header(owner_token),
        json={"name": "Membership", "slug": "membership-lifecycle"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(owner_token),
        json={"organization_id": organization["id"], "name": "Lifecycle"},
    ).json()

    add_maintainer = client.post(
        f"/organizations/{organization['id']}/members",
        headers=auth_header(owner_token),
        json={"user_email": "  MEMBERSHIP-MAINTAINER@example.com ", "role": "Maintainer"},
    )
    assert add_maintainer.status_code == 200
    assert add_maintainer.json()["user"]["email"] == "membership-maintainer@example.com"
    assert (
        client.post(
            f"/projects/{project['id']}/members",
            headers=auth_header(owner_token),
            json={"user_email": "membership-maintainer@example.com", "role": "Maintainer"},
        ).status_code
        == 200
    )

    assert (
        client.post(
            f"/organizations/{organization['id']}/members",
            headers=auth_header(owner_token),
            json={"user_email": "membership-maintainer@example.com", "role": "Viewer"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            f"/organizations/{organization['id']}/members",
            headers=auth_header(owner_token),
            json={"user_email": "missing@example.com", "role": "Viewer"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/organizations/{organization['id']}/members",
            headers=auth_header(owner_token),
            json={
                "user_id": member_user["id"],
                "user_email": member_user["email"],
                "role": "Viewer",
            },
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/organizations/{organization['id']}/members",
            headers=auth_header(maintainer_token),
            json={"user_id": member_user["id"], "role": "Owner"},
        ).status_code
        == 403
    )

    added_member = client.post(
        f"/organizations/{organization['id']}/members",
        headers=auth_header(owner_token),
        json={"user_id": member_user["id"], "role": "Contributor"},
    )
    assert added_member.status_code == 200
    project_member = client.post(
        f"/projects/{project['id']}/members",
        headers=auth_header(owner_token),
        json={"user_id": member_user["id"], "role": "Viewer"},
    )
    assert project_member.status_code == 200
    changed_organization_role = client.patch(
        f"/organizations/{organization['id']}/members/{added_member.json()['id']}",
        headers=auth_header(maintainer_token),
        json={"role": "Viewer"},
    )
    assert changed_organization_role.status_code == 200
    assert (
        client.get(f"/projects/{project['id']}", headers=auth_header(member_token)).status_code
        == 200
    )
    assert (
        client.post(
            f"/projects/{project['id']}/assets",
            headers=auth_header(member_token),
            json={"name": "Forbidden"},
        ).status_code
        == 403
    )

    project_members = client.get(
        f"/projects/{project['id']}/members", headers=auth_header(owner_token)
    ).json()
    owner_project_membership = membership_by_email(project_members, "membership-owner@example.com")
    assert (
        client.patch(
            f"/projects/{project['id']}/members/{project_member.json()['id']}",
            headers=auth_header(maintainer_token),
            json={"role": "Owner"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/projects/{project['id']}/members/{owner_project_membership['id']}",
            headers=auth_header(maintainer_token),
            json={"role": "Viewer"},
        ).status_code
        == 403
    )
    assert (
        client.patch(
            f"/projects/{project['id']}/members/{owner_project_membership['id']}",
            headers=auth_header(owner_token),
            json={"role": "Viewer"},
        ).status_code
        == 409
    )
    assert (
        client.delete(
            f"/projects/{project['id']}/members/{owner_project_membership['id']}",
            headers=auth_header(owner_token),
        ).status_code
        == 409
    )

    changed = client.patch(
        f"/projects/{project['id']}/members/{project_member.json()['id']}",
        headers=auth_header(maintainer_token),
        json={"role": "Contributor"},
    )
    assert changed.status_code == 200
    assert changed.json()["role"] == "Contributor"
    assert (
        client.post(
            f"/projects/{project['id']}/assets",
            headers=auth_header(member_token),
            json={"name": "Allowed"},
        ).status_code
        == 201
    )

    removed = client.delete(
        f"/organizations/{organization['id']}/members/{added_member.json()['id']}",
        headers=auth_header(maintainer_token),
    )
    assert removed.status_code == 204
    assert (
        client.get(f"/projects/{project['id']}", headers=auth_header(member_token)).status_code
        == 403
    )
    remaining_project_members = client.get(
        f"/projects/{project['id']}/members", headers=auth_header(owner_token)
    ).json()
    assert all(item["user"]["id"] != member_user["id"] for item in remaining_project_members)

    organization_members = client.get(
        f"/organizations/{organization['id']}/members", headers=auth_header(owner_token)
    ).json()
    owner_organization_membership = membership_by_email(
        organization_members, "membership-owner@example.com"
    )
    assert (
        client.patch(
            f"/organizations/{organization['id']}/members/{owner_organization_membership['id']}",
            headers=auth_header(owner_token),
            json={"role": "Viewer"},
        ).status_code
        == 409
    )
    assert (
        client.delete(
            f"/organizations/{organization['id']}/members/{owner_organization_membership['id']}",
            headers=auth_header(owner_token),
        ).status_code
        == 409
    )

    with session_scope() as db:
        actions = set(
            db.scalars(
                select(AuditRecord.action).where(
                    AuditRecord.action.in_(
                        (
                            "organization.membership.created",
                            "organization.membership.role_changed",
                            "project.membership.created",
                            "project.membership.role_changed",
                            "organization.membership.removed",
                            "project.membership.removed",
                        )
                    )
                )
            )
        )
        event_types = set(
            db.scalars(select(DomainEvent.event_type).where(DomainEvent.event_type.in_(actions)))
        )
        assert actions == event_types


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
    own_blob_download = client.get(f"/blobs/{blob['id']}/download", headers=auth_header(token))
    assert own_blob_download.status_code == 200
    assert own_blob_download.content == b"solid-data"

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


def test_blob_download_requires_access_to_the_linked_project(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    owner_token = register_and_sign_in(
        client,
        email="blob-owner@example.com",
        display_name="Blob Owner",
        password="secret123",
    )
    other_token = register_and_sign_in(
        client,
        email="blob-other@example.com",
        display_name="Blob Other",
        password="secret123",
    )

    organization = client.post(
        "/organizations",
        headers=auth_header(owner_token),
        json={"name": "Acme", "slug": "acme-blob-access"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(owner_token),
        json={"organization_id": organization["id"], "name": "Rocket", "description": "Phase 2"},
    ).json()
    asset = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(owner_token),
        json={"name": "Wing", "description": "Main wing"},
    ).json()
    revision = client.post(
        f"/assets/{asset['id']}/revisions",
        headers=auth_header(owner_token),
        json={"comment": "Initial release"},
    ).json()
    blob = client.post(
        "/blobs/uploads",
        headers=auth_header(owner_token),
        files={"file": ("wing.step", b"solid-data", "application/step")},
    ).json()
    assert (
        client.post(
            f"/revisions/{revision['id']}/representations",
            headers=auth_header(owner_token),
            json={"name": "native", "media_type": "application/step", "blob_id": blob["id"]},
        ).status_code
        == 201
    )

    unauthorized_download = client.get(
        f"/blobs/{blob['id']}/download",
        headers=auth_header(other_token),
    )
    assert unauthorized_download.status_code == 403


def test_blob_upload_normalizes_filename_and_keeps_local_storage_within_bucket(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    token = register_and_sign_in(
        client,
        email="blob-sanitize@example.com",
        display_name="Blob Sanitizer",
        password="secret123",
    )

    blob = client.post(
        "/blobs/uploads",
        headers=auth_header(token),
        files={"file": ("safe/../../../../../escape.txt", b"escape-data", "text/plain")},
    ).json()

    assert blob["filename"] == "escape.txt"
    assert ".." not in blob["storage_key"]

    bucket_root = (tmp_path / "blobs" / "openpdm-blobs").resolve()
    stored_path = (bucket_root / blob["storage_key"]).resolve()
    assert stored_path.is_file()
    assert stored_path.read_bytes() == b"escape-data"
    assert stored_path.is_relative_to(bucket_root)


def test_search_and_legacy_plugin_registration_requires_package_installation(
    tmp_path: Path,
) -> None:
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

    read_only_write = client.post(
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
    assert read_only_write.status_code == 400
    assert "validated OpenPDM plugin package" in read_only_write.json()["detail"]

    with session_scope() as db:
        db.add(
            PluginRecord(
                id="org.openpdm.sample",
                name="Sample Provider",
                version="0.1.0",
                plugin_type="official",
                capabilities=[],
                enabled=True,
            )
        )

    listed_plugins = client.get("/plugins", headers=auth_header(token))
    assert listed_plugins.status_code == 200
    assert listed_plugins.json()[0]["id"] == "org.openpdm.sample"

    plugin_state = client.post(
        "/plugins/org.openpdm.sample/state",
        headers=auth_header(token),
        json={"enabled": False},
    )
    assert plugin_state.status_code == 200
    assert plugin_state.json()["lifecycle_state"] == "disabled"


def test_platform_administration_and_plugin_package_lifecycle(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    admin_token = register_and_sign_in(
        client,
        email="admin@example.com",
        display_name="Admin",
        password="secret123",
    )
    member_token = register_and_sign_in(
        client,
        email="member@example.com",
        display_name="Member",
        password="secret123",
    )
    admin_session = client.get("/auth/session", headers=auth_header(admin_token)).json()
    member_session = client.get("/auth/session", headers=auth_header(member_token)).json()
    assert admin_session["user"]["is_platform_admin"] is True
    assert member_session["user"]["is_platform_admin"] is False

    plugin_package = build_plugin_package(
        PluginManifest(
            id="org.openpdm.lifecycle-test",
            name="Lifecycle Test",
            version="1.0.0",
            extension_api_versions=[1],
            component="plugin.wasm",
            capabilities=[Capability.METADATA_PROVIDER],
        ),
        bytes(
            wat2wasm(
                """(component
                  (core module $m (func (export "activate")))
                  (core instance $i (instantiate $m))
                  (func (export "activate") (canon lift (core func $i "activate")))
                )"""
            )
        ),
    )
    denied = client.post(
        "/plugins/packages",
        params={"plugin_type": "community"},
        headers=auth_header(member_token),
        files={"package": ("example.openpdm-plugin", plugin_package, "application/zip")},
    )
    assert denied.status_code == 403

    installed = client.post(
        "/plugins/packages",
        params={"plugin_type": "community"},
        headers=auth_header(admin_token),
        files={"package": ("example.openpdm-plugin", plugin_package, "application/zip")},
    )
    assert installed.status_code == 201
    assert installed.json()["lifecycle_state"] == "installed"
    assert installed.json()["enabled"] is False
    assert len(installed.json()["package_digest"]) == 64

    enabled = client.post(
        "/plugins/org.openpdm.lifecycle-test/state",
        headers=auth_header(admin_token),
        json={"enabled": True},
    )
    assert enabled.status_code == 200
    assert enabled.json()["lifecycle_state"] == "running"

    last_admin = client.put(
        f"/platform/administrators/{admin_session['user']['id']}",
        headers=auth_header(admin_token),
        json={"enabled": False},
    )
    assert last_admin.status_code == 409

    granted = client.put(
        f"/platform/administrators/{member_session['user']['id']}",
        headers=auth_header(admin_token),
        json={"enabled": True},
    )
    assert granted.status_code == 200
    assert granted.json()["is_platform_admin"] is True

    revoked = client.put(
        f"/platform/administrators/{admin_session['user']['id']}",
        headers=auth_header(member_token),
        json={"enabled": False},
    )
    assert revoked.status_code == 200


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


def test_collaboration_checkout_checkin_unlock_and_timeline_flow(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    owner_token = register_and_sign_in(
        client,
        email="owner@example.com",
        display_name="Owner",
        password="secret123",
    )
    other_token = register_and_sign_in(
        client,
        email="other@example.com",
        display_name="Other",
        password="secret123",
    )

    organization = client.post(
        "/organizations",
        headers=auth_header(owner_token),
        json={"name": "Acme", "slug": "acme-collab"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(owner_token),
        json={"organization_id": organization["id"], "name": "Rocket", "description": "Phase 2"},
    ).json()
    other_user = client.get("/auth/session", headers=auth_header(other_token)).json()["user"]
    assert (
        client.post(
            f"/organizations/{organization['id']}/members",
            headers=auth_header(owner_token),
            json={"user_id": other_user["id"], "role": "Contributor"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/projects/{project['id']}/members",
            headers=auth_header(owner_token),
            json={"user_id": other_user["id"], "role": "Contributor"},
        ).status_code
        == 200
    )

    asset = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(owner_token),
        json={"name": "Wing", "description": "Main wing"},
    ).json()
    blob = client.post(
        "/blobs/uploads",
        headers=auth_header(owner_token),
        files={"file": ("wing.step", b"solid-data", "application/step")},
    ).json()

    initial_state = client.get(
        f"/assets/{asset['id']}/collaboration-state",
        headers=auth_header(owner_token),
    )
    assert initial_state.status_code == 200
    assert initial_state.json()["state"] == "available"

    checkout = client.post(f"/assets/{asset['id']}/checkout", headers=auth_header(owner_token))
    assert checkout.status_code == 200
    assert checkout.json()["state"] == "locked"
    assert (
        checkout.json()["lock"]["owner_user_id"]
        == client.get("/auth/session", headers=auth_header(owner_token)).json()["user"]["id"]
    )

    locked_conflict = client.post(
        f"/assets/{asset['id']}/checkout", headers=auth_header(other_token)
    )
    assert locked_conflict.status_code == 409
    assert locked_conflict.json()["detail"]["code"] == "asset_locked"

    no_lock_checkin = client.post(
        f"/assets/{asset['id']}/checkin",
        headers=auth_header(other_token),
        json={"comment": "Trying anyway", "representations": []},
    )
    assert no_lock_checkin.status_code == 409
    assert no_lock_checkin.json()["detail"]["code"] == "checkin_by_non_owner"

    checkin = client.post(
        f"/assets/{asset['id']}/checkin",
        headers=auth_header(owner_token),
        json={
            "comment": "Updated wing geometry",
            "representations": [
                {"name": "native", "media_type": "application/step", "blob_id": blob["id"]}
            ],
        },
    )
    assert checkin.status_code == 201
    assert checkin.json()["comment"] == "Updated wing geometry"
    assert checkin.json()["number"] == 1
    assert checkin.json()["representations"][0]["blob_id"] == blob["id"]

    available_again = client.get(
        f"/assets/{asset['id']}/collaboration-state",
        headers=auth_header(owner_token),
    )
    assert available_again.status_code == 200
    assert available_again.json()["state"] == "available"
    assert available_again.json()["lock"] is None

    second_checkout = client.post(
        f"/assets/{asset['id']}/checkout", headers=auth_header(owner_token)
    )
    assert second_checkout.status_code == 200

    unlock_by_other = client.post(
        f"/assets/{asset['id']}/unlock",
        headers=auth_header(other_token),
        json={"force": False},
    )
    assert unlock_by_other.status_code == 403
    assert unlock_by_other.json()["detail"]["code"] == "unlock_not_allowed"

    force_unlock = client.post(
        f"/assets/{asset['id']}/unlock",
        headers=auth_header(owner_token),
        json={"force": True},
    )
    assert force_unlock.status_code == 200
    assert force_unlock.json()["state"] == "available"

    timeline = client.get(f"/assets/{asset['id']}/timeline", headers=auth_header(owner_token))
    assert timeline.status_code == 200
    event_types = {entry["event_type"] for entry in timeline.json()}
    assert "AssetCreated" in event_types
    assert "AssetLocked" in event_types
    assert "CheckInCompleted" in event_types
    assert "ForceUnlocked" in event_types or "AssetUnlocked" in event_types


def test_collaboration_requires_comment_and_rejects_archived_asset_checkin(tmp_path: Path) -> None:
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
        json={"name": "Acme", "slug": "acme-archived"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(token),
        json={"organization_id": organization["id"], "name": "Rocket", "description": "Phase 2"},
    ).json()
    asset = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(token),
        json={"name": "Tail", "description": "Tail"},
    ).json()

    assert (
        client.post(f"/assets/{asset['id']}/checkout", headers=auth_header(token)).status_code
        == 200
    )

    missing_comment = client.post(
        f"/assets/{asset['id']}/checkin",
        headers=auth_header(token),
        json={"comment": "", "representations": []},
    )
    assert missing_comment.status_code == 400
    assert missing_comment.json()["detail"]["context"]["recovery_action"] == "provide_comment"
    assert missing_comment.json()["detail"]["context"]["can_retry"] is True

    assert (
        client.post(
            f"/assets/{asset['id']}/status",
            headers=auth_header(token),
            json={"status": "archived"},
        ).status_code
        == 200
    )

    archived_checkin = client.post(
        f"/assets/{asset['id']}/checkin",
        headers=auth_header(token),
        json={"comment": "Archived change", "representations": []},
    )
    assert archived_checkin.status_code == 409
    assert archived_checkin.json()["detail"]["code"] == "asset_archived"
    assert archived_checkin.json()["detail"]["context"]["recovery_action"] == "read_only"
    assert archived_checkin.json()["detail"]["context"]["should_refresh"] is True

    state = client.get(f"/assets/{asset['id']}/collaboration-state", headers=auth_header(token))
    assert state.status_code == 200
    assert state.json()["state"] == "stale_lock"


def test_collaboration_audit_and_domain_events_include_request_context(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    token = register_and_sign_in(
        client,
        email="audit@example.com",
        display_name="Audit User",
        password="secret123",
    )

    organization = client.post(
        "/organizations",
        headers=auth_header(token),
        json={"name": "Acme", "slug": "acme-audit"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(token),
        json={"organization_id": organization["id"], "name": "Rocket", "description": "Audit"},
    ).json()
    asset = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(token),
        json={"name": "Nose", "description": "Nose cone"},
    ).json()

    request_id = "req-collab-audit-1"
    checkout = client.post(
        f"/assets/{asset['id']}/checkout",
        headers={**auth_header(token), "X-Request-Id": request_id},
    )
    assert checkout.status_code == 200
    assert checkout.headers["X-Request-Id"] == request_id

    failed_checkin = client.post(
        f"/assets/{asset['id']}/checkin",
        headers={**auth_header(token), "X-Request-Id": "req-collab-audit-2"},
        json={"comment": "", "representations": []},
    )
    assert failed_checkin.status_code == 400
    assert failed_checkin.json()["detail"]["code"] == "checkin_comment_required"

    with session_scope() as db:
        audit_records = list(
            db.scalars(
                select(AuditRecord)
                .where(
                    AuditRecord.resource_type == "asset",
                    AuditRecord.resource_id == asset["id"],
                    AuditRecord.action.in_(
                        (
                            "asset.checked_out",
                            "asset.checkin_failed",
                        )
                    ),
                )
                .order_by(AuditRecord.occurred_at.asc())
            )
        )
        assert len(audit_records) == 2

        checkout_audit = audit_records[0]
        assert checkout_audit.action == "asset.checked_out"
        assert checkout_audit.details["request_id"] == request_id
        assert checkout_audit.details["result"] == "succeeded"

        failed_audit = audit_records[1]
        assert failed_audit.action == "asset.checkin_failed"
        assert failed_audit.details["request_id"] == "req-collab-audit-2"
        assert failed_audit.details["result"] == "failed"
        assert failed_audit.details["reason"] == "checkin_comment_required"
        assert failed_audit.details["error"] == "Check-in comment is required."
        assert failed_audit.details["recovery_action"] == "provide_comment"
        assert failed_audit.details["can_retry"] is True

        domain_events = list(
            db.scalars(
                select(DomainEvent)
                .where(
                    DomainEvent.resource_type == "asset",
                    DomainEvent.resource_id == asset["id"],
                    DomainEvent.event_type.in_(("asset.checked_out", "asset.checkin_failed")),
                )
                .order_by(DomainEvent.emitted_at.asc())
            )
        )
        assert len(domain_events) == 2
        assert domain_events[0].payload["request_id"] == request_id
        assert domain_events[0].payload["result"] == "succeeded"
        assert domain_events[1].payload["request_id"] == "req-collab-audit-2"
        assert domain_events[1].payload["result"] == "failed"
        assert domain_events[1].payload["recovery_action"] == "provide_comment"


def test_stale_lock_when_owner_loses_write_role(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    owner_token = register_and_sign_in(
        client,
        email="owner-stale@example.com",
        display_name="Owner",
        password="secret123",
    )
    maintainer_token = register_and_sign_in(
        client,
        email="maintainer-stale@example.com",
        display_name="Maintainer",
        password="secret123",
    )

    organization = client.post(
        "/organizations",
        headers=auth_header(owner_token),
        json={"name": "Acme", "slug": "acme-stale-role"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(owner_token),
        json={"organization_id": organization["id"], "name": "Rocket", "description": "Phase 2"},
    ).json()
    maintainer_user = client.get("/auth/session", headers=auth_header(maintainer_token)).json()[
        "user"
    ]

    assert (
        client.post(
            f"/organizations/{organization['id']}/members",
            headers=auth_header(owner_token),
            json={"user_id": maintainer_user["id"], "role": "Maintainer"},
        ).status_code
        == 200
    )
    second_owner = client.post(
        f"/projects/{project['id']}/members",
        headers=auth_header(owner_token),
        json={"user_id": maintainer_user["id"], "role": "Owner"},
    )
    assert second_owner.status_code == 200

    asset = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(owner_token),
        json={"name": "Fin", "description": "Tail fin"},
    ).json()

    assert (
        client.post(f"/assets/{asset['id']}/checkout", headers=auth_header(owner_token)).status_code
        == 200
    )

    memberships = client.get(
        f"/projects/{project['id']}/members", headers=auth_header(owner_token)
    ).json()
    owner_membership = next(
        membership
        for membership in memberships
        if membership["user"]["email"] == "owner-stale@example.com"
    )
    downgrade = client.patch(
        f"/projects/{project['id']}/members/{owner_membership['id']}",
        headers=auth_header(owner_token),
        json={"role": "Viewer"},
    )
    assert downgrade.status_code == 200

    stale_state = client.get(
        f"/assets/{asset['id']}/collaboration-state",
        headers=auth_header(maintainer_token),
    )
    assert stale_state.status_code == 200
    assert stale_state.json()["state"] == "stale_lock"

    blocked_checkout = client.post(
        f"/assets/{asset['id']}/checkout",
        headers=auth_header(maintainer_token),
    )
    assert blocked_checkout.status_code == 409
    assert blocked_checkout.json()["detail"]["code"] == "asset_locked"

    force_unlock = client.post(
        f"/assets/{asset['id']}/unlock",
        headers=auth_header(maintainer_token),
        json={"force": True},
    )
    assert force_unlock.status_code == 200
    assert force_unlock.json()["state"] == "available"


def test_stale_lock_when_owner_is_inactive(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    owner_token = register_and_sign_in(
        client,
        email="owner-inactive@example.com",
        display_name="Owner",
        password="secret123",
    )
    maintainer_token = register_and_sign_in(
        client,
        email="maintainer-inactive@example.com",
        display_name="Maintainer",
        password="secret123",
    )

    organization = client.post(
        "/organizations",
        headers=auth_header(owner_token),
        json={"name": "Acme", "slug": "acme-stale-inactive"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(owner_token),
        json={"organization_id": organization["id"], "name": "Rocket", "description": "Phase 2"},
    ).json()
    maintainer_user = client.get("/auth/session", headers=auth_header(maintainer_token)).json()[
        "user"
    ]

    assert (
        client.post(
            f"/organizations/{organization['id']}/members",
            headers=auth_header(owner_token),
            json={"user_id": maintainer_user["id"], "role": "Maintainer"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/projects/{project['id']}/members",
            headers=auth_header(owner_token),
            json={"user_id": maintainer_user["id"], "role": "Maintainer"},
        ).status_code
        == 200
    )

    asset = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(owner_token),
        json={"name": "Nacelle", "description": "Engine nacelle"},
    ).json()
    owner_user = client.get("/auth/session", headers=auth_header(owner_token)).json()["user"]

    assert (
        client.post(f"/assets/{asset['id']}/checkout", headers=auth_header(owner_token)).status_code
        == 200
    )

    with session_scope() as db:
        persisted_owner = db.get(User, owner_user["id"])
        assert persisted_owner is not None
        persisted_owner.is_active = False

    stale_state = client.get(
        f"/assets/{asset['id']}/collaboration-state",
        headers=auth_header(maintainer_token),
    )
    assert stale_state.status_code == 200
    assert stale_state.json()["state"] == "stale_lock"

    force_unlock = client.post(
        f"/assets/{asset['id']}/unlock",
        headers=auth_header(maintainer_token),
        json={"force": True},
    )
    assert force_unlock.status_code == 200
    assert force_unlock.json()["state"] == "available"


def test_collaboration_notifications_are_generated_visible_and_mark_read(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    owner_token = register_and_sign_in(
        client,
        email="owner-notify@example.com",
        display_name="Owner",
        password="secret123",
    )
    member_token = register_and_sign_in(
        client,
        email="member-notify@example.com",
        display_name="Member",
        password="secret123",
    )

    organization = client.post(
        "/organizations",
        headers=auth_header(owner_token),
        json={"name": "Acme", "slug": "acme-notify"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(owner_token),
        json={"organization_id": organization["id"], "name": "Rocket", "description": "Phase 2"},
    ).json()
    member_user = client.get("/auth/session", headers=auth_header(member_token)).json()["user"]

    assert (
        client.post(
            f"/organizations/{organization['id']}/members",
            headers=auth_header(owner_token),
            json={"user_id": member_user["id"], "role": "Contributor"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/projects/{project['id']}/members",
            headers=auth_header(owner_token),
            json={"user_id": member_user["id"], "role": "Contributor"},
        ).status_code
        == 200
    )

    asset = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(owner_token),
        json={"name": "Body", "description": "Fuselage"},
    ).json()

    checkout = client.post(f"/assets/{asset['id']}/checkout", headers=auth_header(owner_token))
    assert checkout.status_code == 200

    owner_notifications = client.get("/notifications", headers=auth_header(owner_token))
    assert owner_notifications.status_code == 200
    assert owner_notifications.json() == []

    member_notifications = client.get("/notifications", headers=auth_header(member_token))
    assert member_notifications.status_code == 200
    checkout_notifications = member_notifications.json()
    assert len(checkout_notifications) == 1
    assert checkout_notifications[0]["event_type"] == "asset.checked_out"
    assert checkout_notifications[0]["asset_id"] == asset["id"]
    assert checkout_notifications[0]["is_read"] is False

    conflict = client.post(f"/assets/{asset['id']}/checkout", headers=auth_header(member_token))
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "asset_locked"

    member_notifications = client.get("/notifications", headers=auth_header(member_token))
    assert member_notifications.status_code == 200
    event_types = [item["event_type"] for item in member_notifications.json()]
    assert "collaboration.conflict_detected" in event_types
    assert "asset.checked_out" in event_types

    read_notification = member_notifications.json()[0]
    marked_read = client.post(
        f"/notifications/{read_notification['id']}/read",
        headers=auth_header(member_token),
    )
    assert marked_read.status_code == 200
    assert marked_read.json()["is_read"] is True
    assert marked_read.json()["read_at"] is not None

    revision = client.post(
        f"/assets/{asset['id']}/revisions",
        headers=auth_header(owner_token),
        json={"comment": "Initial release"},
    )
    assert revision.status_code == 201

    member_notifications = client.get("/notifications", headers=auth_header(member_token))
    assert member_notifications.status_code == 200
    assert "revision.created" in [item["event_type"] for item in member_notifications.json()]

    with session_scope() as db:
        membership = db.scalar(
            select(ProjectMembership).where(
                ProjectMembership.project_id == project["id"],
                ProjectMembership.user_id == member_user["id"],
            )
        )
        assert membership is not None
        db.delete(membership)

    hidden_notifications = client.get("/notifications", headers=auth_header(member_token))
    assert hidden_notifications.status_code == 200
    assert hidden_notifications.json() == []

    with session_scope() as db:
        persisted = list(
            db.scalars(
                select(NotificationRecord)
                .where(NotificationRecord.project_id == project["id"])
                .order_by(NotificationRecord.created_at.asc())
            )
        )
        assert len(persisted) >= 3

        notification_audits = list(
            db.scalars(
                select(AuditRecord).where(
                    AuditRecord.action == "notification.emitted",
                    AuditRecord.project_id == project["id"],
                )
            )
        )
        assert len(notification_audits) >= 3


def test_asset_graph_relationship_and_reference_crud_flow(tmp_path: Path) -> None:
    client = build_client(tmp_path)
    owner_token = register_and_sign_in(
        client,
        email="graph-owner@example.com",
        display_name="Graph Owner",
        password="secret123",
    )
    member_token = register_and_sign_in(
        client,
        email="graph-member@example.com",
        display_name="Graph Member",
        password="secret123",
    )
    outsider_token = register_and_sign_in(
        client,
        email="graph-outsider@example.com",
        display_name="Graph Outsider",
        password="secret123",
    )

    organization = client.post(
        "/organizations",
        headers=auth_header(owner_token),
        json={"name": "Acme", "slug": "acme-graph-crud"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(owner_token),
        json={"organization_id": organization["id"], "name": "Graph", "description": "Phase 3"},
    ).json()
    member_user = client.get("/auth/session", headers=auth_header(member_token)).json()["user"]
    assert (
        client.post(
            f"/organizations/{organization['id']}/members",
            headers=auth_header(owner_token),
            json={"user_id": member_user["id"], "role": "Contributor"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/projects/{project['id']}/members",
            headers=auth_header(owner_token),
            json={"user_id": member_user["id"], "role": "Contributor"},
        ).status_code
        == 200
    )

    asset_a = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(owner_token),
        json={"name": "Asset A", "description": "A"},
    ).json()
    asset_b = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(owner_token),
        json={"name": "Asset B", "description": "B"},
    ).json()
    asset_c = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(owner_token),
        json={"name": "Asset C", "description": "C"},
    ).json()
    second_project = client.post(
        "/projects",
        headers=auth_header(owner_token),
        json={"organization_id": organization["id"], "name": "Graph 2", "description": "Other"},
    ).json()
    asset_other = client.post(
        f"/projects/{second_project['id']}/assets",
        headers=auth_header(owner_token),
        json={"name": "Asset Other", "description": "Other"},
    ).json()

    relationship = client.post(
        f"/assets/{asset_a['id']}/relationships",
        headers=auth_header(owner_token),
        json={
            "target_asset_id": asset_b["id"],
            "relationship_type": "depends_on",
            "metadata": {"strength": "strong"},
        },
    )
    assert relationship.status_code == 201
    relationship_payload = relationship.json()
    assert relationship_payload["source_asset_id"] == asset_a["id"]
    assert relationship_payload["target_asset_id"] == asset_b["id"]
    assert relationship_payload["relationship_type"] == "depends_on"

    duplicate = client.post(
        f"/assets/{asset_a['id']}/relationships",
        headers=auth_header(owner_token),
        json={"target_asset_id": asset_b["id"], "relationship_type": "depends_on", "metadata": {}},
    )
    assert duplicate.status_code == 409

    self_relationship = client.post(
        f"/assets/{asset_a['id']}/relationships",
        headers=auth_header(owner_token),
        json={"target_asset_id": asset_a["id"], "relationship_type": "related_to", "metadata": {}},
    )
    assert self_relationship.status_code == 400

    cross_project = client.post(
        f"/assets/{asset_a['id']}/relationships",
        headers=auth_header(owner_token),
        json={
            "target_asset_id": asset_other["id"],
            "relationship_type": "related_to",
            "metadata": {},
        },
    )
    assert cross_project.status_code == 400

    outgoing = client.get(
        f"/assets/{asset_a['id']}/relationships/outgoing",
        headers=auth_header(member_token),
    )
    assert outgoing.status_code == 200
    assert outgoing.json()[0]["target_asset_id"] == asset_b["id"]

    incoming = client.get(
        f"/assets/{asset_b['id']}/relationships/incoming",
        headers=auth_header(member_token),
    )
    assert incoming.status_code == 200
    assert incoming.json()[0]["source_asset_id"] == asset_a["id"]

    updated_relationship = client.put(
        f"/relationships/{relationship_payload['id']}/metadata",
        headers=auth_header(owner_token),
        json={"metadata": {"strength": "critical", "owner": "phase-3"}},
    )
    assert updated_relationship.status_code == 200
    assert updated_relationship.json()["metadata"]["strength"] == "critical"

    reference = client.post(
        f"/assets/{asset_a['id']}/references",
        headers=auth_header(owner_token),
        json={
            "reference_type": "external_url",
            "target_uri": "https://example.com/spec",
            "label": "Spec",
            "metadata": {"source": "supplier"},
        },
    )
    assert reference.status_code == 201
    reference_payload = reference.json()

    denied_mutations = (
        client.put(
            f"/relationships/{relationship_payload['id']}/metadata",
            headers=auth_header(outsider_token),
            json={"metadata": {"forbidden": True}},
        ),
        client.delete(
            f"/relationships/{relationship_payload['id']}",
            headers=auth_header(outsider_token),
        ),
        client.post(
            f"/assets/{asset_a['id']}/references",
            headers=auth_header(outsider_token),
            json={"reference_type": "external_url", "target_uri": "https://example.com/nope"},
        ),
        client.delete(
            f"/references/{reference_payload['id']}",
            headers=auth_header(outsider_token),
        ),
        client.post(
            f"/references/{reference_payload['id']}/resolve",
            headers=auth_header(outsider_token),
            json={"target_asset_id": asset_c["id"], "relationship_type": "references"},
        ),
    )
    assert all(response.status_code == 403 for response in denied_mutations)

    listed_references = client.get(
        f"/assets/{asset_a['id']}/references",
        headers=auth_header(member_token),
    )
    assert listed_references.status_code == 200
    assert listed_references.json()[0]["target_uri"] == "https://example.com/spec"

    resolved_reference = client.post(
        f"/references/{reference_payload['id']}/resolve",
        headers=auth_header(owner_token),
        json={"target_asset_id": asset_c["id"], "relationship_type": "references"},
    )
    assert resolved_reference.status_code == 200
    assert resolved_reference.json()["target_asset_id"] == asset_c["id"]

    listed_references_after_resolution = client.get(
        f"/assets/{asset_a['id']}/references",
        headers=auth_header(member_token),
    )
    assert listed_references_after_resolution.status_code == 200
    assert listed_references_after_resolution.json() == []

    delete_relationship = client.delete(
        f"/relationships/{relationship_payload['id']}",
        headers=auth_header(owner_token),
    )
    assert delete_relationship.status_code == 204

    outsider_view = client.get(
        f"/assets/{asset_a['id']}/relationships",
        headers=auth_header(outsider_token),
    )
    assert outsider_view.status_code == 403

    denied_creation = client.post(
        f"/assets/{asset_a['id']}/relationships",
        headers={**auth_header(outsider_token), "X-Request-Id": "req-graph-denied"},
        json={
            "target_asset_id": asset_b["id"],
            "relationship_type": "related_to",
            "metadata": {},
        },
    )
    assert denied_creation.status_code == 403

    with session_scope() as db:
        failures = list(
            db.scalars(
                select(AuditRecord).where(
                    AuditRecord.resource_type == "relationship",
                    AuditRecord.action.in_(("relationship.failed", "relationship.denied")),
                )
            )
        )
        assert len(failures) >= 4
        assert all(record.details["result"] in {"failed", "denied"} for record in failures)
        assert all(record.details["reason"] for record in failures)
        assert any(
            record.action == "relationship.denied"
            and record.details["request_id"] == "req-graph-denied"
            and record.details["reason"] == "Permission denied."
            for record in failures
        )
        denied_events = {
            record.details["event_type"]
            for record in db.scalars(
                select(AuditRecord).where(
                    AuditRecord.action.in_(("relationship.denied", "reference.denied"))
                )
            )
        }
        assert {
            "RelationshipCreated",
            "RelationshipMetadataUpdated",
            "RelationshipDeleted",
            "ReferenceCreated",
            "ReferenceDeleted",
            "ReferenceResolved",
        } <= denied_events


def test_asset_graph_queries_are_bounded_and_can_detect_cycles(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    client = build_client(tmp_path)
    token = register_and_sign_in(
        client,
        email="graph-query@example.com",
        display_name="Graph Query",
        password="secret123",
    )

    organization = client.post(
        "/organizations",
        headers=auth_header(token),
        json={"name": "Acme", "slug": "acme-graph-query"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(token),
        json={"organization_id": organization["id"], "name": "Query", "description": "Phase 3"},
    ).json()
    asset_a = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(token),
        json={"name": "A", "description": "A"},
    ).json()
    asset_b = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(token),
        json={"name": "B", "description": "B"},
    ).json()
    asset_c = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(token),
        json={"name": "C", "description": "C"},
    ).json()
    asset_d = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(token),
        json={"name": "D", "description": "D"},
    ).json()

    for source_id, target_id in (
        (asset_a["id"], asset_b["id"]),
        (asset_b["id"], asset_c["id"]),
        (asset_c["id"], asset_a["id"]),
        (asset_c["id"], asset_d["id"]),
    ):
        response = client.post(
            f"/assets/{source_id}/relationships",
            headers=auth_header(token),
            json={"target_asset_id": target_id, "relationship_type": "depends_on", "metadata": {}},
        )
        assert response.status_code == 201

    bounded_graph = client.get(
        f"/assets/{asset_a['id']}/graph",
        headers=auth_header(token),
        params={"direction": "outgoing", "max_depth": 2, "target_asset_id": asset_d["id"]},
    )
    assert bounded_graph.status_code == 200
    bounded_payload = bounded_graph.json()
    assert bounded_payload["path_exists"] is False
    assert bounded_payload["has_cycle"] is False
    assert {node["id"] for node in bounded_payload["nodes"]} == {
        asset_a["id"],
        asset_b["id"],
        asset_c["id"],
    }

    full_graph = client.get(
        f"/assets/{asset_a['id']}/graph",
        headers=auth_header(token),
        params={"direction": "outgoing", "max_depth": 3, "target_asset_id": asset_d["id"]},
    )
    assert full_graph.status_code == 200
    full_payload = full_graph.json()
    assert full_payload["path_exists"] is True
    assert full_payload["has_cycle"] is True
    assert {node["id"] for node in full_payload["nodes"]} == {
        asset_a["id"],
        asset_b["id"],
        asset_c["id"],
        asset_d["id"],
    }

    invalid_depth = client.get(
        f"/assets/{asset_a['id']}/graph",
        headers=auth_header(token),
        params={"max_depth": 11},
    )
    assert invalid_depth.status_code == 400

    with session_scope() as db:
        assert not list(
            db.scalars(select(DomainEvent).where(DomainEvent.event_type == "GraphQueryExecuted"))
        )

    monkeypatch.setenv("OPENPDM_AUDIT_GRAPH_QUERIES", "true")
    audited_graph = client.get(
        f"/assets/{asset_a['id']}/graph",
        headers={**auth_header(token), "X-Request-Id": "req-graph-query-audited"},
        params={"max_depth": 3, "target_asset_id": asset_d["id"]},
    )
    assert audited_graph.status_code == 200
    with session_scope() as db:
        audit = db.scalar(
            select(AuditRecord).where(
                AuditRecord.resource_type == "graph", AuditRecord.action == "graph.success"
            )
        )
        assert audit is not None
        assert audit.details["request_id"] == "req-graph-query-audited"
        assert audit.details["result"] == "success"
        event = db.scalar(select(DomainEvent).where(DomainEvent.event_type == "GraphQueryExecuted"))
        assert event is not None
        assert event.payload["request_id"] == "req-graph-query-audited"


def test_asset_graph_audit_and_events_cover_relationship_and_reference_mutations(
    tmp_path: Path,
) -> None:
    client = build_client(tmp_path)
    token = register_and_sign_in(
        client,
        email="graph-audit@example.com",
        display_name="Graph Audit",
        password="secret123",
    )

    organization = client.post(
        "/organizations",
        headers=auth_header(token),
        json={"name": "Acme", "slug": "acme-graph-audit"},
    ).json()
    project = client.post(
        "/projects",
        headers=auth_header(token),
        json={"organization_id": organization["id"], "name": "Audit", "description": "Phase 3"},
    ).json()
    asset_a = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(token),
        json={"name": "Audit A", "description": "A"},
    ).json()
    asset_b = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(token),
        json={"name": "Audit B", "description": "B"},
    ).json()
    asset_c = client.post(
        f"/projects/{project['id']}/assets",
        headers=auth_header(token),
        json={"name": "Audit C", "description": "C"},
    ).json()

    assert (
        client.post(
            f"/assets/{asset_b['id']}/relationships",
            headers=auth_header(token),
            json={
                "target_asset_id": asset_c["id"],
                "relationship_type": "depends_on",
                "metadata": {},
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            f"/assets/{asset_c['id']}/relationships",
            headers=auth_header(token),
            json={
                "target_asset_id": asset_a["id"],
                "relationship_type": "depends_on",
                "metadata": {},
            },
        ).status_code
        == 201
    )

    relationship_response = client.post(
        f"/assets/{asset_a['id']}/relationships",
        headers={**auth_header(token), "X-Request-Id": "req-graph-rel-create"},
        json={
            "target_asset_id": asset_b["id"],
            "relationship_type": "depends_on",
            "metadata": {"seed": "cycle"},
        },
    )
    assert relationship_response.status_code == 201
    relationship_id = relationship_response.json()["id"]

    metadata_update = client.put(
        f"/relationships/{relationship_id}/metadata",
        headers={**auth_header(token), "X-Request-Id": "req-graph-rel-update"},
        json={"metadata": {"severity": "high"}},
    )
    assert metadata_update.status_code == 200

    reference_response = client.post(
        f"/assets/{asset_a['id']}/references",
        headers={**auth_header(token), "X-Request-Id": "req-graph-ref-create"},
        json={
            "reference_type": "legacy_path",
            "target_uri": "legacy://wing/prior-art",
            "label": "Legacy",
            "metadata": {"origin": "migration"},
        },
    )
    assert reference_response.status_code == 201
    reference_id = reference_response.json()["id"]

    resolve_response = client.post(
        f"/references/{reference_id}/resolve",
        headers={**auth_header(token), "X-Request-Id": "req-graph-ref-resolve"},
        json={"target_asset_id": asset_c["id"], "relationship_type": "references"},
    )
    assert resolve_response.status_code == 200

    with session_scope() as db:
        relationship_records = list(
            db.scalars(
                select(AuditRecord)
                .where(
                    AuditRecord.project_id == project["id"],
                    AuditRecord.resource_type == "relationship",
                    AuditRecord.action.in_(
                        (
                            "relationship.created",
                            "relationship.metadata.updated",
                            "relationship.cycle_detected",
                        )
                    ),
                )
                .order_by(AuditRecord.occurred_at.asc())
            )
        )
        assert any(
            record.action == "relationship.created"
            and record.details["request_id"] == "req-graph-rel-create"
            for record in relationship_records
        )
        assert any(
            record.action == "relationship.metadata.updated"
            and record.details["request_id"] == "req-graph-rel-update"
            for record in relationship_records
        )
        assert any(
            record.action == "relationship.cycle_detected" for record in relationship_records
        )

        reference_records = list(
            db.scalars(
                select(AuditRecord)
                .where(
                    AuditRecord.project_id == project["id"],
                    AuditRecord.resource_type == "reference",
                    AuditRecord.action.in_(("reference.created", "reference.resolved")),
                )
                .order_by(AuditRecord.occurred_at.asc())
            )
        )
        assert any(
            record.action == "reference.created"
            and record.details["request_id"] == "req-graph-ref-create"
            for record in reference_records
        )
        assert any(
            record.action == "reference.resolved"
            and record.details["request_id"] == "req-graph-ref-resolve"
            for record in reference_records
        )

        relationship_events = list(
            db.scalars(
                select(DomainEvent)
                .where(
                    DomainEvent.project_id == project["id"],
                    DomainEvent.resource_type == "relationship",
                    DomainEvent.event_type.in_(
                        (
                            "RelationshipCreated",
                            "RelationshipMetadataUpdated",
                            "RelationshipCycleDetected",
                        )
                    ),
                )
                .order_by(DomainEvent.emitted_at.asc())
            )
        )
        assert any(
            event.event_type == "RelationshipCreated"
            and event.payload["request_id"] == "req-graph-rel-create"
            for event in relationship_events
        )
        assert any(event.event_type == "RelationshipCycleDetected" for event in relationship_events)

        reference_events = list(
            db.scalars(
                select(DomainEvent)
                .where(
                    DomainEvent.project_id == project["id"],
                    DomainEvent.resource_type == "reference",
                    DomainEvent.event_type.in_(("ReferenceCreated", "ReferenceResolved")),
                )
                .order_by(DomainEvent.emitted_at.asc())
            )
        )
        assert any(
            event.event_type == "ReferenceCreated"
            and event.payload["request_id"] == "req-graph-ref-create"
            for event in reference_events
        )
        assert any(
            event.event_type == "ReferenceResolved"
            and event.payload["request_id"] == "req-graph-ref-resolve"
            for event in reference_events
        )

        assert db.get(AssetRelationship, relationship_id) is not None
        assert db.get(AssetReference, reference_id) is None
