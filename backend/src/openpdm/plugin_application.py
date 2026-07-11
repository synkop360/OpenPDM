"""Application-layer orchestration across plugin and owning Platform Module contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from openpdm.extension_api import InvocationResponse, validate_plugin_package
from openpdm.infrastructure.plugin_packages import PluginPackageStorage
from openpdm.infrastructure.plugin_secrets import PluginSecretCipher
from openpdm.platform_core.modules.services import AssetsModule, MetadataModule, PluginsModule
from openpdm.plugin_runtime import WasmtimeWorkerSupervisor


@dataclass(frozen=True, slots=True)
class PluginInvocationServices:
    package_storage: PluginPackageStorage
    cipher: PluginSecretCipher
    supervisor: WasmtimeWorkerSupervisor


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
    archive = services.package_storage.read(plugin.package_digest)
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
    services: PluginInvocationServices,
) -> list[object]:
    response = invoke_plugin(
        db,
        plugin_id=plugin_id,
        capability="metadata_provider",
        operation="metadata",
        context={**context, "actor": actor},
        payload={"target_type": target_type, "target_id": target_id},
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
