from __future__ import annotations

import json
import subprocess
import sys
from base64 import b64encode
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from pydantic import ValidationError

from openpdm.extension_api import (
    EXTENSION_API_MAJOR_VERSION,
    AnalysisMetadataContribution,
    Capability,
    ConfigurationProperty,
    ConfigurationSchema,
    InvocationResponse,
    MetadataContribution,
    PluginManifest,
    ReferenceContribution,
    RelationshipContribution,
    RepresentationAnalysisInput,
    build_plugin_package,
    extension_api_wit_path,
    scaffold_plugin,
    validate_plugin_package,
)

COMPONENT = b"\x00asm\x0d\x00\x01\x00"


def manifest(**overrides: object) -> PluginManifest:
    data: dict[str, object] = {
        "id": "org.openpdm.example",
        "name": "Example",
        "version": "1.2.3",
        "extension_api_versions": [EXTENSION_API_MAJOR_VERSION],
        "component": "plugin.wasm",
        "capabilities": [Capability.METADATA_PROVIDER],
    }
    data.update(overrides)
    return PluginManifest.model_validate(data)


def raw_archive(entries: list[tuple[str, bytes]]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as package:
        for name, payload in entries:
            info = ZipInfo(name)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, payload)
    return buffer.getvalue()


def test_manifest_is_strict_and_compatible() -> None:
    value = manifest(
        configuration=ConfigurationSchema(
            properties={"token": ConfigurationProperty(type="string", secret=True)},
            required=["token"],
        )
    )
    assert value.is_compatible
    assert value.configuration is not None
    assert value.configuration.properties["token"].secret


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("id", "Not Reverse Domain"),
        ("version", "1.0"),
        ("component", "../plugin.wasm"),
        ("extension_api_versions", [2]),
    ],
)
def test_invalid_or_incompatible_manifest_is_rejected(field: str, value: object) -> None:
    if field == "extension_api_versions":
        package_manifest = manifest(**{field: value})
        archive = raw_archive(
            [
                (
                    "openpdm-plugin.json",
                    json.dumps(package_manifest.model_dump(mode="json")).encode(),
                ),
                ("plugin.wasm", COMPONENT),
            ]
        )
        with pytest.raises(ValueError, match="does not support"):
            validate_plugin_package(archive)
        return
    with pytest.raises(ValidationError):
        manifest(**{field: value})


def test_event_subscription_requires_capability() -> None:
    with pytest.raises(ValidationError, match="event_handler"):
        manifest(event_subscriptions=["AssetCreated"])


def test_sdk_builds_deterministic_validated_package() -> None:
    package = build_plugin_package(manifest(), COMPONENT)
    assert package == build_plugin_package(manifest(), COMPONENT)
    validated = validate_plugin_package(package)
    assert validated.manifest.id == "org.openpdm.example"
    assert len(validated.digest) == 64
    assert validated.component == COMPONENT


@pytest.mark.parametrize("name", ["../plugin.wasm", "/plugin.wasm", "dir/plugin.wasm", "dir\\x"])
def test_package_rejects_path_traversal_and_nested_entries(name: str) -> None:
    payload = manifest().model_dump(mode="json")
    archive = raw_archive(
        [("openpdm-plugin.json", json.dumps(payload).encode()), (name, COMPONENT)]
    )
    with pytest.raises(ValueError, match="Unsafe"):
        validate_plugin_package(archive)


def test_package_rejects_unexpected_files_and_non_component_binary() -> None:
    payload = json.dumps(manifest().model_dump(mode="json")).encode()
    with pytest.raises(ValueError, match="unexpected"):
        validate_plugin_package(
            raw_archive(
                [("openpdm-plugin.json", payload), ("plugin.wasm", COMPONENT), ("evil.py", b"x")]
            )
        )
    with pytest.raises(ValueError, match="not a WebAssembly Component"):
        validate_plugin_package(
            raw_archive([("openpdm-plugin.json", payload), ("plugin.wasm", b"native")])
        )


def test_manifest_rejects_unknown_fields_and_undefined_required_configuration() -> None:
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(
            {**manifest().model_dump(mode="json"), "entry_point": "host:call"}
        )
    with pytest.raises(ValidationError, match="undefined"):
        ConfigurationSchema(required=["missing"])


def test_analysis_provider_is_additive_v1_capability() -> None:
    value = manifest(capabilities=[Capability.ANALYSIS_PROVIDER])

    assert value.capabilities == [Capability.ANALYSIS_PROVIDER]


def test_existing_capabilities_remain_valid_with_analysis_provider() -> None:
    capabilities = [
        Capability.ASSET_PROVIDER,
        Capability.METADATA_PROVIDER,
        Capability.OPTION_PROVIDER,
        Capability.EVENT_HANDLER,
        Capability.ANALYSIS_PROVIDER,
    ]

    assert manifest(capabilities=capabilities).capabilities == capabilities


def test_analysis_input_is_strict_and_bounded() -> None:
    value = RepresentationAnalysisInput(
        representation_id="representation-1",
        asset_id="asset-1",
        filename="design.bin",
        media_type="application/octet-stream",
        size_bytes=1,
        checksum_sha256="a" * 64,
        content_base64="YQ==",
    )

    assert value.asset_id == "asset-1"
    with pytest.raises(ValidationError):
        RepresentationAnalysisInput.model_validate({**value.model_dump(), "unknown": True})


def test_analysis_input_rejects_oversized_decoded_content() -> None:
    content = b64encode(b"x" * (5 * 1024 * 1024 + 1)).decode("ascii")

    with pytest.raises(ValidationError, match="exceeds the 5 MiB"):
        RepresentationAnalysisInput(
            representation_id="representation-1",
            asset_id="asset-1",
            filename="design.bin",
            media_type="application/octet-stream",
            size_bytes=5 * 1024 * 1024,
            checksum_sha256="a" * 64,
            content_base64=content,
        )


def test_analysis_input_rejects_declared_size_mismatch() -> None:
    with pytest.raises(ValidationError, match="does not match size_bytes"):
        RepresentationAnalysisInput(
            representation_id="representation-1",
            asset_id="asset-1",
            filename="design.bin",
            media_type="application/octet-stream",
            size_bytes=2,
            checksum_sha256="a" * 64,
            content_base64="YQ==",
        )


def test_analysis_contribution_requires_stable_key() -> None:
    with pytest.raises(ValidationError):
        ReferenceContribution(
            source_asset_id="asset-1",
            reference_type="plugin.ref",
            target_uri="plugin://ref/1",
            label="Reference",
            metadata={},
        )


def test_analysis_metadata_contribution_requires_stable_key() -> None:
    with pytest.raises(ValidationError):
        AnalysisMetadataContribution(
            target_type="asset",
            target_id="asset-1",
            key="plugin.key",
            value="value",
            value_type="string",
        )

    legacy_metadata = MetadataContribution(
        target_type="asset",
        target_id="asset-1",
        key="plugin.key",
        value="value",
        value_type="string",
    )
    assert InvocationResponse(success=True, metadata=[legacy_metadata]).metadata == [
        legacy_metadata
    ]


def test_relationship_contribution_is_strict() -> None:
    relationship = RelationshipContribution(
        contribution_key="dependency-1",
        source_asset_id="asset-1",
        target_asset_id="asset-2",
        relationship_type="depends_on",
        metadata={},
    )

    with pytest.raises(ValidationError):
        RelationshipContribution.model_validate(
            {**relationship.model_dump(), "unexpected": "value"}
        )
    with pytest.raises(ValidationError, match="must differ"):
        RelationshipContribution.model_validate(
            {**relationship.model_dump(), "target_asset_id": relationship.source_asset_id}
        )


def test_sdk_exposes_the_versioned_wit_contract() -> None:
    with extension_api_wit_path() as contract:
        contents = contract.read_text(encoding="utf-8")
    assert "package openpdm:extension@1.0.0" in contents
    assert "export invoke" in contents


def test_generic_audit_and_event_resources_accept_plugin_identities() -> None:
    from openpdm.platform_core.modules.models import AuditRecord, DomainEvent

    assert AuditRecord.__table__.c.resource_id.type.length == 255
    assert DomainEvent.__table__.c.resource_id.type.length == 255


def test_sdk_scaffolds_buildable_minimal_plugin(tmp_path: Path) -> None:
    project = scaffold_plugin(
        tmp_path / "sample-plugin",
        plugin_id="org.example.sample",
        name="Sample Plugin",
    )
    subprocess.run([sys.executable, str(project / "build.py")], check=True)
    package = validate_plugin_package((project / "plugin.openpdm-plugin").read_bytes())
    assert package.manifest.id == "org.example.sample"
