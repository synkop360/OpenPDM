from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from openpdm.extension_api import (
    Capability,
    InvocationResponse,
    PluginManifest,
    build_plugin_package,
)
from openpdm.infrastructure.blob_storage import LocalFileBlobStorage
from openpdm.infrastructure.database import (
    dispose_engines,
    initialize_disposable_database,
    session_scope,
)
from openpdm.infrastructure.plugin_packages import PluginPackageStorage
from openpdm.infrastructure.plugin_secrets import PluginSecretCipher
from openpdm.infrastructure.settings import Settings
from openpdm.platform_core.composition import MODULES
from openpdm.platform_core.modules.models import (
    Asset,
    Blob,
    Organization,
    OrganizationMembership,
    PluginRecord,
    Project,
    ProjectMembership,
    Representation,
    Revision,
    User,
)
from openpdm.plugin_application import PluginInvocationServices, invoke_analysis_provider
from openpdm.plugin_runtime.supervisor import RuntimeResult


class CapturingSupervisor:
    def __init__(self) -> None:
        self.arguments: list[str] | None = None

    def invoke(
        self, component: bytes, *, export_name: str, arguments: list[str] | None = None
    ) -> RuntimeResult:
        assert component.startswith(b"\x00asm")
        assert export_name == "invoke"
        self.arguments = arguments
        return RuntimeResult(True, result=InvocationResponse(success=True).model_dump_json())


def settings_for(tmp_path: Path, *, analysis_limit: int = 5 * 1024 * 1024) -> Settings:
    dispose_engines()
    return Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'analysis.db'}",
        blob_local_root=str(tmp_path / "blobs"),
        plugin_package_root=str(tmp_path / "plugins"),
        plugin_analysis_max_content_bytes=analysis_limit,
    )


def install_running_analysis_provider(
    db: object, *, settings: Settings, actor: User
) -> tuple[str, CapturingSupervisor, PluginPackageStorage]:
    storage = PluginPackageStorage(settings.plugin_package_root)
    archive = build_plugin_package(
        PluginManifest(
            id="org.openpdm.analysis-test",
            name="Analysis Test",
            version="1.0.0",
            extension_api_versions=[1],
            component="plugin.wasm",
            capabilities=[Capability.ANALYSIS_PROVIDER],
        ),
        b"\x00asm\x0d\x00\x01\x00",
    )
    digest = hashlib.sha256(archive).hexdigest()
    storage.put(digest, archive)
    db.add(  # type: ignore[attr-defined]
        PluginRecord(
            id="org.openpdm.analysis-test",
            name="Analysis Test",
            version="1.0.0",
            plugin_type="community",
            capabilities=[Capability.ANALYSIS_PROVIDER.value],
            extension_api_versions=[1],
            component="plugin.wasm",
            package_digest=digest,
            lifecycle_state="running",
            enabled=True,
            installed_by_user_id=actor.id,
        )
    )
    db.flush()  # type: ignore[attr-defined]
    return "org.openpdm.analysis-test", CapturingSupervisor(), storage


def create_representation(
    db: object,
    *,
    owner: User,
    content: bytes | None,
    storage: LocalFileBlobStorage,
) -> tuple[Asset, Representation, Blob | None]:
    organization = Organization(name="Analysis Organization", slug="analysis-organization")
    db.add(organization)  # type: ignore[attr-defined]
    db.flush()  # type: ignore[attr-defined]
    project = Project(organization_id=organization.id, name="Analysis")
    asset = Asset(
        project=project,
        name="Analysis Asset",
        description="",
        created_by_user_id=owner.id,
    )
    db.add_all([project, asset])  # type: ignore[attr-defined]
    db.flush()  # type: ignore[attr-defined]
    db.add(  # type: ignore[attr-defined]
        OrganizationMembership(organization_id=organization.id, user_id=owner.id, role="Owner")
    )
    db.add(  # type: ignore[attr-defined]
        ProjectMembership(project_id=project.id, user_id=owner.id, role="Owner")
    )
    revision = Revision(asset_id=asset.id, number=1, comment="", created_by_user_id=owner.id)
    db.add(revision)  # type: ignore[attr-defined]
    db.flush()  # type: ignore[attr-defined]
    if content is None:
        representation = Representation(
            revision_id=revision.id,
            name="native",
            media_type="application/octet-stream",
            blob_id=None,
        )
        db.add(representation)  # type: ignore[attr-defined]
        db.flush()  # type: ignore[attr-defined]
        return asset, representation, None

    storage_key = f"analysis/{asset.id}.bin"
    storage.put_bytes(storage_key, content, "application/octet-stream")
    blob = Blob(
        storage_key=storage_key,
        filename="model.bin",
        media_type="application/octet-stream",
        size_bytes=len(content),
        checksum_sha256=hashlib.sha256(content).hexdigest(),
        created_by_user_id=owner.id,
    )
    db.add(blob)  # type: ignore[attr-defined]
    db.flush()  # type: ignore[attr-defined]
    representation = Representation(
        revision_id=revision.id,
        name="native",
        media_type="application/octet-stream",
        blob_id=blob.id,
    )
    db.add(representation)  # type: ignore[attr-defined]
    db.flush()  # type: ignore[attr-defined]
    return asset, representation, blob


def invoke(
    db: object,
    *,
    settings: Settings,
    actor: User,
    representation_id: str,
    blob_storage: LocalFileBlobStorage,
) -> CapturingSupervisor:
    plugin_id, supervisor, package_storage = install_running_analysis_provider(
        db, settings=settings, actor=actor
    )
    invoke_analysis_provider(
        db,
        plugin_id=plugin_id,
        representation_id=representation_id,
        actor=actor,
        context={"actor_id": actor.id, "request_id": "analysis-test"},
        relationship_mappings={"dependency-key": "asset-id"},
        services=PluginInvocationServices(
            package_storage=package_storage,
            cipher=PluginSecretCipher(None),
            supervisor=supervisor,  # type: ignore[arg-type]
        ),
        storage=blob_storage,
        settings=settings,
    )
    return supervisor


def test_analysis_input_requires_read_access_and_representation_blob(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    initialize_disposable_database(settings)
    blob_storage = LocalFileBlobStorage(settings.blob_local_root, settings.s3_bucket)
    with session_scope(settings) as db:
        owner = User(email="owner@example.com", display_name="Owner", password_hash="unused")
        other_user = User(email="other@example.com", display_name="Other", password_hash="unused")
        db.add_all([owner, other_user])
        db.flush()
        _, representation, _ = create_representation(
            db, owner=owner, content=b"model", storage=blob_storage
        )

        with pytest.raises(HTTPException) as error:
            invoke(
                db,
                settings=settings,
                actor=other_user,
                representation_id=representation.id,
                blob_storage=blob_storage,
            )

        assert error.value.status_code == 403


def test_analysis_input_rejects_content_above_configured_limit(tmp_path: Path) -> None:
    settings = settings_for(tmp_path, analysis_limit=4)
    initialize_disposable_database(settings)
    blob_storage = LocalFileBlobStorage(settings.blob_local_root, settings.s3_bucket)
    with session_scope(settings) as db:
        owner = User(email="owner@example.com", display_name="Owner", password_hash="unused")
        db.add(owner)
        db.flush()
        _, representation, _ = create_representation(
            db, owner=owner, content=b"above", storage=blob_storage
        )

        with pytest.raises(HTTPException) as error:
            invoke(
                db,
                settings=settings,
                actor=owner,
                representation_id=representation.id,
                blob_storage=blob_storage,
            )

        assert error.value.status_code == 413
        assert error.value.detail == "Representation exceeds the analysis content limit."


def test_analysis_input_rejects_representation_without_blob(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    initialize_disposable_database(settings)
    blob_storage = LocalFileBlobStorage(settings.blob_local_root, settings.s3_bucket)
    with session_scope(settings) as db:
        owner = User(email="owner@example.com", display_name="Owner", password_hash="unused")
        db.add(owner)
        db.flush()
        _, representation, _ = create_representation(
            db, owner=owner, content=None, storage=blob_storage
        )

        with pytest.raises(HTTPException) as error:
            invoke(
                db,
                settings=settings,
                actor=owner,
                representation_id=representation.id,
                blob_storage=blob_storage,
            )

        assert error.value.status_code == 409


def test_analysis_input_rejects_blob_not_linked_to_representation_asset(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    initialize_disposable_database(settings)
    blob_storage = LocalFileBlobStorage(settings.blob_local_root, settings.s3_bucket)
    with session_scope(settings) as db:
        owner = User(email="owner@example.com", display_name="Owner", password_hash="unused")
        db.add(owner)
        db.flush()
        asset, _, _ = create_representation(db, owner=owner, content=b"model", storage=blob_storage)
        inaccessible_blob = Blob(
            storage_key="analysis/inaccessible.bin",
            filename="inaccessible.bin",
            media_type="application/octet-stream",
            size_bytes=3,
            checksum_sha256=hashlib.sha256(b"bad").hexdigest(),
            created_by_user_id=owner.id,
        )
        blob_storage.put_bytes(inaccessible_blob.storage_key, b"bad", inaccessible_blob.media_type)
        db.add(inaccessible_blob)
        db.flush()

        with pytest.raises(HTTPException) as error:
            MODULES.blobs.read_blob_for_analysis(
                db,
                actor=owner,
                blob_id=inaccessible_blob.id,
                asset_id=asset.id,
                max_content_bytes=settings.plugin_analysis_max_content_bytes,
                storage=blob_storage,
                assets=MODULES.assets,
            )

        assert error.value.status_code == 403


def test_analysis_input_uses_server_owned_representation_values(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    initialize_disposable_database(settings)
    blob_storage = LocalFileBlobStorage(settings.blob_local_root, settings.s3_bucket)
    with session_scope(settings) as db:
        owner = User(email="owner@example.com", display_name="Owner", password_hash="unused")
        db.add(owner)
        db.flush()
        asset, representation, blob = create_representation(
            db, owner=owner, content=b"model", storage=blob_storage
        )
        assert blob is not None

        supervisor = invoke(
            db,
            settings=settings,
            actor=owner,
            representation_id=representation.id,
            blob_storage=blob_storage,
        )

        assert supervisor.arguments is not None
        request = json.loads(supervisor.arguments[0])
        assert request["payload"] == {
            "analysis_input": {
                "representation_id": representation.id,
                "asset_id": asset.id,
                "filename": blob.filename,
                "media_type": blob.media_type,
                "size_bytes": blob.size_bytes,
                "checksum_sha256": blob.checksum_sha256,
                "content_base64": "bW9kZWw=",
            },
            "relationship_mappings": {"dependency-key": "asset-id"},
        }
