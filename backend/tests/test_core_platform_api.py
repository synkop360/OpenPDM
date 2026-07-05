from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from openpdm.infrastructure.blob_storage import reset_blob_storage_cache
from openpdm.infrastructure.database import dispose_engines, session_scope
from openpdm.platform_core.modules.models import AuditRecord, DomainEvent


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
    assert checkout.json()["lock"]["owner_user_id"] == client.get(
        "/auth/session", headers=auth_header(owner_token)
    ).json()["user"]["id"]

    locked_conflict = client.post(f"/assets/{asset['id']}/checkout", headers=auth_header(other_token))
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

    second_checkout = client.post(f"/assets/{asset['id']}/checkout", headers=auth_header(owner_token))
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

    assert client.post(f"/assets/{asset['id']}/checkout", headers=auth_header(token)).status_code == 200

    missing_comment = client.post(
        f"/assets/{asset['id']}/checkin",
        headers=auth_header(token),
        json={"comment": "", "representations": []},
    )
    assert missing_comment.status_code == 400

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
