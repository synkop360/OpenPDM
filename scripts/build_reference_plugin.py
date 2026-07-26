"""Build the domain-neutral Official Plugin as a reproducible package."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from openpdm.extension_api import PluginManifest, build_plugin_package

ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = ROOT / "plugins" / "reference"
WIT_ROOT = ROOT / "backend" / "src" / "openpdm" / "extension_api" / "wit"


def build(output: Path) -> Path:
    componentize = shutil.which("componentize-py")
    if componentize is None:
        raise RuntimeError("componentize-py is required; run this command through uv.")
    component = output.parent / "reference-plugin.wasm"
    component.parent.mkdir(parents=True, exist_ok=True)
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
            str(PLUGIN_ROOT / "bindings"),
            "reference_plugin",
            "-o",
            str(component),
        ],
        check=True,
    )
    manifest = PluginManifest.model_validate(
        json.loads((PLUGIN_ROOT / "openpdm-plugin.json").read_text(encoding="utf-8"))
    )
    output.write_bytes(build_plugin_package(manifest, component.read_bytes()))
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=PLUGIN_ROOT / "dist" / "reference.openpdm-plugin",
    )
    arguments = parser.parse_args()
    print(build(arguments.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
