from __future__ import annotations

import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import pytest
from pydantic import ValidationError

from openpdm.extension_api import (
    EXTENSION_API_MAJOR_VERSION,
    Capability,
    ConfigurationProperty,
    ConfigurationSchema,
    PluginManifest,
    build_plugin_package,
    extension_api_wit_path,
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


def test_sdk_exposes_the_versioned_wit_contract() -> None:
    with extension_api_wit_path() as contract:
        contents = contract.read_text(encoding="utf-8")
    assert "package openpdm:extension@1.0.0" in contents
    assert "export invoke" in contents
