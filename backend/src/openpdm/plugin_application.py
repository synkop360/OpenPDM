"""Application-layer orchestration across plugin and owning Platform Module contracts."""

from __future__ import annotations

import json
from base64 import b64encode
from dataclasses import dataclass
from hashlib import sha256

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from openpdm.extension_api import (
    InvocationResponse,
    RepresentationAnalysisInput,
    validate_plugin_package,
)
from openpdm.infrastructure.blob_storage import BlobStorage
from openpdm.infrastructure.plugin_packages import PluginPackageStorage
from openpdm.infrastructure.plugin_secrets import PluginSecretCipher
from openpdm.infrastructure.settings import Settings
from openpdm.platform_core.composition import MODULES
from openpdm.plugin_runtime import WasmtimeWorkerSupervisor

AssetsModule = MODULES.assets
BlobsModule = MODULES.blobs
MetadataModule = MODULES.metadata
PluginsModule = MODULES.plugins
RelationshipsModule = MODULES.relationships


@dataclass(frozen=True, slots=True)
class PluginInvocationServices:
    package_storage: PluginPackageStorage
    cipher: PluginSecretCipher
    supervisor: WasmtimeWorkerSupervisor


def _analysis_metadata_source(provider_identity: str, contribution_key: str) -> str:
    return _analysis_contribution_identity(provider_identity, contribution_key)


def _analysis_contribution_identity(provider_identity: str, contribution_key: str) -> str:
    return sha256(f"{provider_identity}\0{contribution_key}".encode()).hexdigest()


def invoke_plugin(
    db: Session,
    *,
    plugin_id: str,
    capability: str,
    operation: str,
    context: dict[str, object],
    payload: dict[str, object],
    services: PluginInvocationServices,
) -> InvocationResponse:
    plugin = PluginsModule.get_plugin(db, plugin_id=plugin_id, actor=context["actor"])
    if not plugin.enabled or plugin.lifecycle_state != "running":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Plugin is not running.")
    if capability not in plugin.capabilities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plugin does not declare the {capability} capability.",
        )
    try:
        archive = services.package_storage.read(plugin.package_digest)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The installed plugin package is unavailable. "
                "A Platform Administrator must reinstall or upgrade the plugin package."
            ),
        ) from exc
    package = validate_plugin_package(archive)
    if package.digest != plugin.package_digest or package.manifest.id != plugin.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Installed plugin package integrity check failed.",
        )
    configuration = PluginsModule.get_runtime_configuration(
        db, plugin_id=plugin.id, cipher=services.cipher
    )
    request = {
        "operation": operation,
        "context": {key: value for key, value in context.items() if key != "actor"},
        "configuration": configuration,
        "payload": payload,
    }
    result = services.supervisor.invoke(
        package.component,
        export_name="invoke",
        arguments=[json.dumps(request, sort_keys=True, separators=(",", ":"))],
    )
    if not result.success or result.result is None:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.diagnostic_reason or "Plugin invocation failed.",
        )
    try:
        response = InvocationResponse.model_validate_json(result.result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Plugin returned an invalid Extension API response.",
        ) from exc
    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=response.error.message if response.error else "Plugin invocation failed.",
        )
    return response


def invoke_metadata_provider(
    db: Session,
    *,
    plugin_id: str,
    target_type: str,
    target_id: str,
    actor: object,
    context: dict[str, object],
    parameters: dict[str, object] | None,
    services: PluginInvocationServices,
) -> list[object]:
    response = invoke_plugin(
        db,
        plugin_id=plugin_id,
        capability="metadata_provider",
        operation="metadata",
        context={**context, "actor": actor},
        payload={"target_type": target_type, "target_id": target_id, **(parameters or {})},
        services=services,
    )
    entries: list[object] = []
    for contribution in response.metadata:
        if contribution.target_type != target_type or contribution.target_id != target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Metadata Provider may only contribute to the requested target.",
            )
        entries.append(
            MetadataModule.put_entry(
                db,
                target_type=target_type,
                target_id=target_id,
                key=contribution.key,
                value=contribution.value,
                value_type=contribution.value_type.value,
                source=f"plugin:{plugin_id}",
                actor=actor,
            )
        )
    return entries


def invoke_analysis_provider(
    db: Session,
    *,
    plugin_id: str,
    representation_id: str,
    actor: object,
    context: dict[str, object],
    relationship_mappings: dict[str, str],
    services: PluginInvocationServices,
    storage: BlobStorage,
    settings: Settings,
) -> InvocationResponse:
    """Invoke one running Analysis Provider with authorized bounded content only."""
    asset, representation = AssetsModule.get_representation_for_analysis(
        db, representation_id=representation_id, actor=actor
    )
    if representation.blob_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Representation has no Blob.",
        )
    blob, content = BlobsModule.read_blob_for_analysis(
        db,
        blob_id=representation.blob_id,
        asset_id=asset.id,
        actor=actor,
        max_content_bytes=settings.plugin_analysis_max_content_bytes,
        storage=storage,
        assets=AssetsModule,
    )
    analysis_input = RepresentationAnalysisInput(
        representation_id=representation.id,
        asset_id=asset.id,
        filename=blob.filename,
        media_type=blob.media_type,
        size_bytes=blob.size_bytes,
        checksum_sha256=blob.checksum_sha256,
        content_base64=b64encode(content).decode("ascii"),
    )
    response = invoke_plugin(
        db,
        plugin_id=plugin_id,
        capability="analysis_provider",
        operation="analysis",
        context={**context, "actor": actor},
        payload={
            "analysis_input": analysis_input.model_dump(mode="json"),
            "relationship_mappings": relationship_mappings,
        },
        services=services,
    )
    for contribution in response.analysis_metadata:
        _, project_id = MetadataModule.authorize_target(
            db,
            target_type=contribution.target_type,
            target_id=contribution.target_id,
            actor=actor,
        )
        if project_id != asset.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Analysis Provider metadata must target the analyzed Project.",
            )
    for contribution in response.references:
        if contribution.source_asset_id != asset.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Analysis Provider may only contribute from the analyzed Asset.",
            )
    for contribution in response.relationships:
        if contribution.source_asset_id != asset.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Analysis Provider may only contribute from the analyzed Asset.",
            )
        mapped_target_id = relationship_mappings.get(contribution.contribution_key)
        if mapped_target_id != contribution.target_asset_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Analysis Provider relationship target is not an extracted dependency mapping.",
            )
        target_asset = AssetsModule.get_asset(
            db, asset_id=contribution.target_asset_id, actor=actor
        )
        if target_asset.project_id != asset.project_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Analysis Provider target must belong to the analyzed Project.",
            )
    for contribution in response.analysis_metadata:
        MetadataModule.put_entry(
            db,
            target_type=contribution.target_type,
            target_id=contribution.target_id,
            key=contribution.key,
            value=contribution.value,
            value_type=contribution.value_type.value,
            source=_analysis_metadata_source(plugin_id, contribution.contribution_key),
            analysis_contribution_id=_analysis_contribution_identity(
                plugin_id, contribution.contribution_key
            ),
            actor=actor,
        )
    for contribution in response.references:
        RelationshipsModule.persist_analysis_contribution(
            db,
            provider_identity=plugin_id,
            contribution_key=contribution.contribution_key,
            source_asset_id=asset.id,
            contribution=contribution,
            actor=actor,
        )
    for contribution in response.relationships:
        RelationshipsModule.persist_analysis_contribution(
            db,
            provider_identity=plugin_id,
            contribution_key=contribution.contribution_key,
            source_asset_id=asset.id,
            contribution=contribution,
            actor=actor,
        )
    return response


def invoke_option_provider(
    db: Session,
    *,
    plugin_id: str,
    actor: object,
    context: dict[str, object],
    services: PluginInvocationServices,
) -> list[object]:
    response = invoke_plugin(
        db,
        plugin_id=plugin_id,
        capability="option_provider",
        operation="options",
        context={**context, "actor": actor},
        payload={},
        services=services,
    )
    return list(response.option_sets)


def invoke_asset_provider(
    db: Session,
    *,
    plugin_id: str,
    project_id: str,
    request_payload: dict[str, object],
    actor: object,
    context: dict[str, object],
    services: PluginInvocationServices,
) -> list[object]:
    response = invoke_plugin(
        db,
        plugin_id=plugin_id,
        capability="asset_provider",
        operation="asset",
        context={**context, "actor": actor},
        payload=request_payload,
        services=services,
    )
    created: list[object] = []
    expected_context = {key: value for key, value in context.items() if key != "actor"}
    for command in response.commands:
        payload = command.payload
        if command.context.model_dump(mode="json") != expected_context:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Asset Provider command altered the authorized invocation context.",
            )
        if command.operation == "create_asset":
            if payload.get("project_id") != project_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Asset Provider may only create Assets in the authorized Project.",
                )
            created.append(
                AssetsModule.create_asset(
                    db,
                    project_id=project_id,
                    name=str(payload.get("name", "")),
                    description=str(payload.get("description", "")),
                    actor=actor,
                )
            )
        elif command.operation == "create_revision":
            created.append(
                AssetsModule.create_revision(
                    db,
                    asset_id=str(payload.get("asset_id", "")),
                    comment=str(payload.get("comment", "")),
                    actor=actor,
                )
            )
        else:
            created.append(
                AssetsModule.add_representation(
                    db,
                    revision_id=str(payload.get("revision_id", "")),
                    name=str(payload.get("name", "")),
                    media_type=str(payload.get("media_type", "")),
                    blob_id=str(payload["blob_id"]) if payload.get("blob_id") else None,
                    actor=actor,
                )
            )
    return created
