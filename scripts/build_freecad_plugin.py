"""Build the FreeCAD Official Plugin as a reproducible OpenPDM package."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from openpdm.extension_api import PluginManifest, build_plugin_package

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "freecad"
WIT_ROOT = ROOT / "backend" / "src" / "openpdm" / "extension_api" / "wit"


def build(output: Path) -> Path:
    """Build and validate the immutable package without invoking a CAD program."""

    componentize = shutil.which("componentize-py")
    if componentize is None:
        raise RuntimeError("componentize-py is required; run this command through uv.")
    component = output.parent / "freecad_plugin.wasm"
    component.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory() as temporary_directory:
        bindings = Path(temporary_directory) / "bindings"
        subprocess.run(
            [componentize, "-d", str(WIT_ROOT), "-w", "plugin", "bindings", str(bindings)],
            check=True,
        )
        subprocess.run(
            [
                componentize,
                "-d",
                str(WIT_ROOT),
                "-w",
                "plugin",
                "componentize",
                "--stub-wasi",
                "-p",
                str(PLUGIN_ROOT),
                "-p",
                str(bindings),
                "freecad_plugin",
                "-o",
                str(component),
            ],
            check=True,
        )
    manifest = PluginManifest.model_validate_json(
        (PLUGIN_ROOT / "openpdm-plugin.json").read_text(encoding="utf-8")
    )
    output.write_bytes(build_plugin_package(manifest, component.read_bytes()))
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=PLUGIN_ROOT / "dist" / "freecad.openpdm-plugin"
    )
    arguments = parser.parse_args()
    print(build(arguments.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
