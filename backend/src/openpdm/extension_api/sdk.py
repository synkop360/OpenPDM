"""Small SDK helpers; contracts remain the normative Extension API."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from importlib.resources import as_file, files
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .manifest import PluginManifest
from .package import MANIFEST_NAME, ValidatedPluginPackage, validate_plugin_package


def build_plugin_package(manifest: PluginManifest, component: bytes) -> bytes:
    """Build a deterministic package and validate the produced hostile-input boundary."""

    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as package:
        for name, payload in (
            (MANIFEST_NAME, json.dumps(manifest.model_dump(mode="json"), sort_keys=True).encode()),
            (manifest.component, component),
        ):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            package.writestr(info, payload)
    archive = buffer.getvalue()
    validate_plugin_package(archive)
    return archive


def inspect_plugin_package(archive: bytes) -> ValidatedPluginPackage:
    return validate_plugin_package(archive)


@contextmanager
def extension_api_wit_path() -> Iterator[Path]:
    """Expose the normative Extension API v1 WIT contract to SDK tooling."""

    contract = files("openpdm.extension_api").joinpath("wit/openpdm-extension.wit")
    with as_file(contract) as path:
        yield path
