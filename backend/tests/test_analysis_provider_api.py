from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from sqlalchemy import create_engine, inspect, select

from openpdm.extension_api import (
    AnalysisMetadataContribution,
    Capability,
    InvocationResponse,
    PluginManifest,
    ReferenceContribution,
    RelationshipContribution,
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
    AssetReference,
    AssetRelationship,
    AuditRecord,
    Blob,
    DomainEvent,
    MetadataEntry,
    Organization,
    OrganizationMembership,
    PluginRecord,
    Project,
    ProjectMembership,
    Representation,
    Revision,
    User,
)
from openpdm.plugin_application import (
    PluginInvocationServices,
    _analysis_metadata_source,
    invoke_analysis_provider,
)
from openpdm.plugin_runtime.supervisor import RuntimeResult


class CapturingSupervisor:
    def __init__(self, response: InvocationResponse | None = None) -> None:
        self.arguments: list[str] | None = None
        self.response = response or InvocationResponse(success=True)

    def invoke(
        self, component: bytes, *, export_name: str, arguments: list[str] | None = None
    ) -> RuntimeResult:
        assert component.startswith(b"\x00asm")
        assert export_name == "invoke"
        self.arguments = arguments
        return RuntimeResult(True, result=self.response.model_dump_json())


def settings_for(tmp_path: Path, *, analysis_limit: int = 5 * 1024 * 1024) -> Settings:
    dispose_engines()
    return Settings(
        database_url=f"sqlite+pysqlite:///{tmp_path / 'analysis.db'}",
        blob_local_root=str(tmp_path / "blobs"),
        plugin_package_root=str(tmp_path / "plugins"),
        plugin_analysis_max_content_bytes=analysis_limit,
    )


def install_running_analysis_provider(
    db: object,
    *,
    settings: Settings,
    actor: User,
    response: InvocationResponse | None = None,
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
    return "org.openpdm.analysis-test", CapturingSupervisor(response), storage


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
    response: InvocationResponse | None = None,
    relationship_mappings: dict[str, str] | None = None,
) -> CapturingSupervisor:
    plugin_id, supervisor, package_storage = install_running_analysis_provider(
        db, settings=settings, actor=actor, response=response
    )
    invoke_analysis_provider(
        db,
        plugin_id=plugin_id,
        representation_id=representation_id,
        actor=actor,
        context={"actor_id": actor.id, "request_id": "analysis-test"},
        relationship_mappings=relationship_mappings or {"dependency-key": "asset-id"},
        services=PluginInvocationServices(
            package_storage=package_storage,
            cipher=PluginSecretCipher(None),
            supervisor=supervisor,  # type: ignore[arg-type]
        ),
        storage=blob_storage,
        settings=settings,
    )
    return supervisor


def invoke_with_provider(
    db: object,
    *,
    settings: Settings,
    actor: User,
    representation_id: str,
    blob_storage: LocalFileBlobStorage,
    plugin_id: str,
    supervisor: CapturingSupervisor,
    package_storage: PluginPackageStorage,
    relationship_mappings: dict[str, str],
) -> InvocationResponse:
    return invoke_analysis_provider(
        db,
        plugin_id=plugin_id,
        representation_id=representation_id,
        actor=actor,
        context={"actor_id": actor.id, "request_id": "analysis-test"},
        relationship_mappings=relationship_mappings,
        services=PluginInvocationServices(
            package_storage=package_storage,
            cipher=PluginSecretCipher(None),
            supervisor=supervisor,  # type: ignore[arg-type]
        ),
        storage=blob_storage,
        settings=settings,
    )


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


def test_analysis_contributions_reject_a_source_other_than_the_analyzed_asset(
    tmp_path: Path,
) -> None:
    settings = settings_for(tmp_path)
    initialize_disposable_database(settings)
    blob_storage = LocalFileBlobStorage(settings.blob_local_root, settings.s3_bucket)
    with session_scope(settings) as db:
        owner = User(email="owner@example.com", display_name="Owner", password_hash="unused")
        db.add(owner)
        db.flush()
        asset, representation, _ = create_representation(
            db, owner=owner, content=b"model", storage=blob_storage
        )
        other_asset = Asset(
            project_id=asset.project_id,
            name="Other Asset",
            description="",
            created_by_user_id=owner.id,
        )
        db.add(other_asset)
        db.flush()

        with pytest.raises(HTTPException) as error:
            invoke(
                db,
                settings=settings,
                actor=owner,
                representation_id=representation.id,
                blob_storage=blob_storage,
                response=InvocationResponse(
                    success=True,
                    references=[
                        ReferenceContribution(
                            contribution_key="reference-1",
                            source_asset_id=other_asset.id,
                            reference_type="external",
                            target_uri="plugin://reference/1",
                            label="Reference",
                        )
                    ],
                ),
            )

        assert error.value.status_code == 400
        assert (
            error.value.detail == "Analysis Provider may only contribute from the analyzed Asset."
        )


def test_analysis_contributions_reject_an_unreadable_mapped_target_asset(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    initialize_disposable_database(settings)
    blob_storage = LocalFileBlobStorage(settings.blob_local_root, settings.s3_bucket)
    with session_scope(settings) as db:
        owner = User(email="owner@example.com", display_name="Owner", password_hash="unused")
        db.add(owner)
        db.flush()
        asset, representation, _ = create_representation(
            db, owner=owner, content=b"model", storage=blob_storage
        )
        other_organization = Organization(name="Other Organization", slug="other-organization")
        db.add(other_organization)
        db.flush()
        other_project = Project(organization_id=other_organization.id, name="Other")
        target_asset = Asset(
            project=other_project,
            name="Unreadable Asset",
            description="",
            created_by_user_id=owner.id,
        )
        db.add_all([other_project, target_asset])
        db.flush()

        with pytest.raises(HTTPException) as error:
            invoke(
                db,
                settings=settings,
                actor=owner,
                representation_id=representation.id,
                blob_storage=blob_storage,
                response=InvocationResponse(
                    success=True,
                    relationships=[
                        RelationshipContribution(
                            contribution_key="dependency-1",
                            source_asset_id=asset.id,
                            target_asset_id=target_asset.id,
                            relationship_type="depends_on",
                        )
                    ],
                ),
                relationship_mappings={"dependency-1": target_asset.id},
            )

        assert error.value.status_code == 403


def test_analysis_contributions_require_a_matching_relationship_mapping_key(tmp_path: Path) -> None:
    settings = settings_for(tmp_path)
    initialize_disposable_database(settings)
    blob_storage = LocalFileBlobStorage(settings.blob_local_root, settings.s3_bucket)
    with session_scope(settings) as db:
        owner = User(email="owner@example.com", display_name="Owner", password_hash="unused")
        db.add(owner)
        db.flush()
        asset, representation, _ = create_representation(
            db, owner=owner, content=b"model", storage=blob_storage
        )
        target_asset = Asset(
            project_id=asset.project_id,
            name="Mapped Asset",
            description="",
            created_by_user_id=owner.id,
        )
        db.add(target_asset)
        db.flush()

        with pytest.raises(HTTPException) as error:
            invoke(
                db,
                settings=settings,
                actor=owner,
                representation_id=representation.id,
                blob_storage=blob_storage,
                response=InvocationResponse(
                    success=True,
                    relationships=[
                        RelationshipContribution(
                            contribution_key="unmapped-dependency",
                            source_asset_id=asset.id,
                            target_asset_id=target_asset.id,
                            relationship_type="depends_on",
                        )
                    ],
                ),
                relationship_mappings={"different-dependency": target_asset.id},
            )

        assert error.value.status_code == 400


def test_analysis_contributions_are_idempotent_and_emit_creation_events_once(
    tmp_path: Path,
) -> None:
    settings = settings_for(tmp_path)
    initialize_disposable_database(settings)
    blob_storage = LocalFileBlobStorage(settings.blob_local_root, settings.s3_bucket)
    with session_scope(settings) as db:
        owner = User(email="owner@example.com", display_name="Owner", password_hash="unused")
        db.add(owner)
        db.flush()
        asset, representation, _ = create_representation(
            db, owner=owner, content=b"model", storage=blob_storage
        )
        target_asset = Asset(
            project_id=asset.project_id,
            name="Dependency Asset",
            description="",
            created_by_user_id=owner.id,
        )
        db.add(target_asset)
        db.flush()
        response = InvocationResponse(
            success=True,
            analysis_metadata=[
                AnalysisMetadataContribution(
                    contribution_key="metadata-1",
                    target_type="representation",
                    target_id=representation.id,
                    key="plugin.analysis.result",
                    value="complete",
                    value_type="string",
                )
            ],
            references=[
                ReferenceContribution(
                    contribution_key="reference-1",
                    source_asset_id=asset.id,
                    reference_type="external",
                    target_uri="plugin://reference/1",
                    label="Reference",
                )
            ],
            relationships=[
                RelationshipContribution(
                    contribution_key="relationship-1",
                    source_asset_id=asset.id,
                    target_asset_id=target_asset.id,
                    relationship_type="depends_on",
                )
            ],
        )
        plugin_id, supervisor, package_storage = install_running_analysis_provider(
            db, settings=settings, actor=owner, response=response
        )
        mappings = {"relationship-1": target_asset.id}

        invoke_with_provider(
            db,
            settings=settings,
            actor=owner,
            representation_id=representation.id,
            blob_storage=blob_storage,
            plugin_id=plugin_id,
            supervisor=supervisor,
            package_storage=package_storage,
            relationship_mappings=mappings,
        )
        first_events = list(
            db.scalars(
                select(DomainEvent).where(
                    DomainEvent.event_type.in_(
                        ("metadata.upserted", "ReferenceCreated", "RelationshipCreated")
                    )
                )
            )
        )
        assert {event.event_type for event in first_events} == {
            "metadata.upserted",
            "ReferenceCreated",
            "RelationshipCreated",
        }
        first_audits = list(
            db.scalars(
                select(AuditRecord).where(
                    AuditRecord.action.in_(
                        ("metadata.upserted", "reference.created", "relationship.created")
                    )
                )
            )
        )
        assert {record.action for record in first_audits} == {
            "metadata.upserted",
            "reference.created",
            "relationship.created",
        }

        replacement_target = Asset(
            project_id=asset.project_id,
            name="Replacement Dependency Asset",
            description="",
            created_by_user_id=owner.id,
        )
        db.add(replacement_target)
        db.flush()
        supervisor.response = InvocationResponse(
            success=True,
            analysis_metadata=[
                AnalysisMetadataContribution(
                    contribution_key="metadata-1",
                    target_type="representation",
                    target_id=representation.id,
                    key="plugin.analysis.result.changed",
                    value="changed",
                    value_type="string",
                )
            ],
            references=[
                ReferenceContribution(
                    contribution_key="reference-1",
                    source_asset_id=asset.id,
                    reference_type="external",
                    target_uri="plugin://reference/changed",
                    label="Changed reference",
                )
            ],
            relationships=[
                RelationshipContribution(
                    contribution_key="relationship-1",
                    source_asset_id=asset.id,
                    target_asset_id=replacement_target.id,
                    relationship_type="depends_on",
                )
            ],
        )

        invoke_with_provider(
            db,
            settings=settings,
            actor=owner,
            representation_id=representation.id,
            blob_storage=blob_storage,
            plugin_id=plugin_id,
            supervisor=supervisor,
            package_storage=package_storage,
            relationship_mappings={"relationship-1": replacement_target.id},
        )

        assert (
            len(
                list(
                    db.scalars(
                        select(MetadataEntry).where(
                            MetadataEntry.representation_id == representation.id,
                            MetadataEntry.key == "plugin.analysis.result",
                        )
                    )
                )
            )
            == 1
        )
        assert (
            len(
                list(
                    db.scalars(
                        select(AssetReference).where(AssetReference.source_asset_id == asset.id)
                    )
                )
            )
            == 1
        )
        assert (
            len(
                list(
                    db.scalars(
                        select(AssetRelationship).where(
                            AssetRelationship.source_asset_id == asset.id,
                            AssetRelationship.target_asset_id == target_asset.id,
                        )
                    )
                )
            )
            == 1
        )
        assert (
            list(
                db.scalars(
                    select(DomainEvent).where(
                        DomainEvent.event_type.in_(
                            ("metadata.upserted", "ReferenceCreated", "RelationshipCreated")
                        )
                    )
                )
            )
            == first_events
        )
        assert (
            list(
                db.scalars(
                    select(AuditRecord).where(
                        AuditRecord.action.in_(
                            ("metadata.upserted", "reference.created", "relationship.created")
                        )
                    )
                )
            )
            == first_audits
        )


def test_analysis_metadata_source_is_bounded_and_stably_scoped() -> None:
    source = _analysis_metadata_source("provider" * 100, "contribution" * 100)

    assert len(source) == 64
    assert source == _analysis_metadata_source("provider" * 100, "contribution" * 100)
    assert source != _analysis_metadata_source("provider" * 100, "other" * 100)


def test_analysis_relationship_failure_is_audited_through_the_public_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'analysis.db'}"
    monkeypatch.setenv("OPENPDM_DATABASE_URL", database_url)
    dispose_engines()
    settings = Settings(
        database_url=database_url,
        blob_local_root=str(tmp_path / "blobs"),
        plugin_package_root=str(tmp_path / "plugins"),
    )
    initialize_disposable_database(settings)
    blob_storage = LocalFileBlobStorage(settings.blob_local_root, settings.s3_bucket)
    with session_scope(settings) as db:
        owner = User(email="owner@example.com", display_name="Owner", password_hash="unused")
        db.add(owner)
        db.flush()
        asset, representation, _ = create_representation(
            db, owner=owner, content=b"model", storage=blob_storage
        )
        target_asset = Asset(
            project_id=asset.project_id,
            name="Target Asset",
            description="",
            created_by_user_id=owner.id,
        )
        db.add(target_asset)
        db.flush()

        with pytest.raises(HTTPException) as error:
            invoke(
                db,
                settings=settings,
                actor=owner,
                representation_id=representation.id,
                blob_storage=blob_storage,
                response=InvocationResponse(
                    success=True,
                    relationships=[
                        RelationshipContribution(
                            contribution_key="invalid-relationship",
                            source_asset_id=asset.id,
                            target_asset_id=target_asset.id,
                            relationship_type="not-an-approved-type",
                        )
                    ],
                ),
                relationship_mappings={"invalid-relationship": target_asset.id},
            )

        assert error.value.status_code == 400
        audit = db.scalar(
            select(AuditRecord).where(
                AuditRecord.action == "relationship.failed",
                AuditRecord.resource_id == asset.id,
            )
        )
        assert audit is not None
        assert audit.details["result"] == "failed"
        assert audit.details["reason"] == "Invalid relationship type."


def test_analysis_metadata_preflight_rejects_a_later_cross_project_target_without_writes(
    tmp_path: Path,
) -> None:
    settings = settings_for(tmp_path)
    initialize_disposable_database(settings)
    blob_storage = LocalFileBlobStorage(settings.blob_local_root, settings.s3_bucket)
    with session_scope(settings) as db:
        owner = User(email="owner@example.com", display_name="Owner", password_hash="unused")
        db.add(owner)
        db.flush()
        asset, representation, _ = create_representation(
            db, owner=owner, content=b"model", storage=blob_storage
        )
        other_project = Project(organization_id=asset.project.organization_id, name="Other")
        db.add(other_project)
        db.flush()
        db.add(ProjectMembership(project_id=other_project.id, user_id=owner.id, role="Owner"))
        other_asset = Asset(
            project_id=other_project.id,
            name="Other Asset",
            description="",
            created_by_user_id=owner.id,
        )
        db.add(other_asset)
        db.flush()

        with pytest.raises(HTTPException) as error:
            invoke(
                db,
                settings=settings,
                actor=owner,
                representation_id=representation.id,
                blob_storage=blob_storage,
                response=InvocationResponse(
                    success=True,
                    analysis_metadata=[
                        AnalysisMetadataContribution(
                            contribution_key="valid-metadata",
                            target_type="representation",
                            target_id=representation.id,
                            key="plugin.analysis.valid",
                            value="valid",
                            value_type="string",
                        ),
                        AnalysisMetadataContribution(
                            contribution_key="invalid-metadata",
                            target_type="asset",
                            target_id=other_asset.id,
                            key="plugin.analysis.invalid",
                            value="invalid",
                            value_type="string",
                        ),
                    ],
                    references=[
                        ReferenceContribution(
                            contribution_key="reference-1",
                            source_asset_id=asset.id,
                            reference_type="external",
                            target_uri="plugin://reference/1",
                            label="Reference",
                        )
                    ],
                ),
            )

        assert error.value.status_code == 400
        assert db.scalar(select(MetadataEntry)) is None
        assert db.scalar(select(AssetReference)) is None


def test_analysis_contribution_identity_migration_is_upgradeable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("OPENPDM_DATABASE_URL", database_url)
    dispose_engines()
    initialize_disposable_database(Settings(database_url=database_url))
    config = Config("alembic.ini")
    command.stamp(config, "20260729_0007")
    command.downgrade(config, "20260718_0006")
    command.upgrade(config, "head")

    inspector = inspect(create_engine(database_url))
    for table_name in ("metadata_entries", "asset_references", "asset_relationships"):
        assert "analysis_contribution_id" in {
            column["name"] for column in inspector.get_columns(table_name)
        }
        assert any(
            index["column_names"] == ["analysis_contribution_id"] and index["unique"]
            for index in inspector.get_indexes(table_name)
        )
