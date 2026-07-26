"""Small SDK helpers; contracts remain the normative Extension API."""

from __future__ import annotations

import json
import subprocess
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


def scaffold_plugin(destination: Path, *, plugin_id: str, name: str) -> Path:
    """Create a minimal Python WebAssembly Component plugin project."""

    manifest = PluginManifest(
        id=plugin_id,
        name=name,
        version="0.1.0",
        extension_api_versions=[1],
        component="plugin.wasm",
        capabilities=["event_handler"],
        event_subscriptions=["asset.created"],
    )
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "openpdm-plugin.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    (destination / "plugin.py").write_text(_PLUGIN_TEMPLATE, encoding="utf-8")
    (destination / "build.py").write_text(_BUILD_TEMPLATE, encoding="utf-8")
    with extension_api_wit_path() as wit_path:
        subprocess.run(
            [
                "componentize-py",
                "-d",
                str(wit_path.parent),
                "-w",
                "plugin",
                "bindings",
                str(destination / "bindings"),
            ],
            check=True,
        )
    return destination


_PLUGIN_TEMPLATE = '''"""Minimal OpenPDM Extension API v1 event handler."""

import json
import json.decoder
import json.encoder
import json.scanner

import wit_world

_PRELOADED_JSON = json.dumps(json.loads("{}"))


class WitWorld(wit_world.WitWorld):
    def activate(self) -> None:
        return None

    def invoke(self, request: str) -> str:
        json.loads(request)
        return json.dumps(
            {"success": True, "metadata": [], "commands": [], "error": None},
            separators=(",", ":"),
            sort_keys=True,
        )
'''

_BUILD_TEMPLATE = '''"""Build this plugin into an immutable OpenPDM package."""

import json
import subprocess
from pathlib import Path

from openpdm.extension_api import PluginManifest, build_plugin_package, extension_api_wit_path

ROOT = Path(__file__).resolve().parent

with extension_api_wit_path() as wit_path:
    subprocess.run(
        [
            "componentize-py", "-d", str(wit_path.parent), "-w", "plugin",
            "componentize", "--stub-wasi", "-p", str(ROOT), "-p", str(ROOT / "bindings"),
            "plugin", "-o", str(ROOT / "plugin.wasm"),
        ],
        check=True,
    )
manifest = PluginManifest.model_validate_json((ROOT / "openpdm-plugin.json").read_text())
(ROOT / "plugin.openpdm-plugin").write_bytes(
    build_plugin_package(manifest, (ROOT / "plugin.wasm").read_bytes())
)
print(ROOT / "plugin.openpdm-plugin")
'''
