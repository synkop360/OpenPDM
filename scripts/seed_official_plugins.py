#!/usr/bin/env python3
"""Install and enable a default set of Official Plugins against a running backend.

Opt-in, run manually after the stack is up (see scripts/start_all.py):

    uv run python scripts/seed_official_plugins.py

Plugin installation and activation are Platform-Administrator-only operations
(ADR-0035, ADR-0037), so this script authenticates as a real administrator
rather than bypassing that boundary: it registers (or signs back into) a
well-known local seed account, which ADR-0035 promotes to Platform
Administrator automatically as the first user of an empty deployment, then
calls the same public API endpoints a human would use through the Plugin
Administration screen.

DEFAULT_PLUGINS is auto-discovered from plugins/ -- see discover_official_
plugins() -- so a new Official Plugin only needs its build script; nothing
here needs editing.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BACKEND_URL = "http://localhost:18000"

SEED_ADMIN_EMAIL = os.environ.get("OPENPDM_SEED_ADMIN_EMAIL", "admin@openpdm.local")
SEED_ADMIN_PASSWORD = os.environ.get("OPENPDM_SEED_ADMIN_PASSWORD", "openpdm-seed-admin-1")
SEED_ADMIN_DISPLAY_NAME = os.environ.get(
    "OPENPDM_SEED_ADMIN_DISPLAY_NAME", "Platform Administrator"
)

# Manifest IDs under this namespace are API-test fixtures (e.g.
# plugins/dummy-categories, "org.openpdm.examples.asset-categories"), not
# Official Plugins meant for default deployment -- excluded from discovery.
EXCLUDED_MANIFEST_ID_PREFIX = "org.openpdm.examples."


def discover_official_plugins(plugins_root: Path = ROOT / "plugins") -> list[dict[str, Any]]:
    """Auto-discover Official Plugins under plugins/.

    A subdirectory qualifies as an Official Plugin when it has both an
    openpdm-plugin.json manifest and a matching scripts/build_<name>_plugin.py
    -- the naming convention every genuine Official Plugin build script
    already follows (build_reference_plugin.py, build_freecad_plugin.py, ...).
    Adding a new Official Plugin only needs its build script; nothing here
    needs editing.
    """
    discovered: list[dict[str, Any]] = []
    if not plugins_root.is_dir():
        return discovered
    scripts_root = plugins_root.parent / "scripts"
    for plugin_dir in sorted(plugins_root.iterdir()):
        if not plugin_dir.is_dir():
            continue
        manifest_path = plugin_dir / "openpdm-plugin.json"
        if not manifest_path.is_file():
            continue
        build_script = scripts_root / f"build_{plugin_dir.name.replace('-', '_')}_plugin.py"
        if not build_script.is_file():
            continue
        try:
            manifest_id = json.loads(manifest_path.read_text(encoding="utf-8"))["id"]
        except (json.JSONDecodeError, KeyError, OSError):
            continue
        if manifest_id.startswith(EXCLUDED_MANIFEST_ID_PREFIX):
            continue
        discovered.append(
            {"name": plugin_dir.name, "dir": plugin_dir, "build_script": build_script}
        )
    return discovered


# The default set of Official Plugins to install and enable.
DEFAULT_PLUGINS: list[dict[str, Any]] = discover_official_plugins()


def ensure_admin_session(base_url: str) -> str:
    """Register (or sign back into) the seed Platform Administrator; return a bearer token."""
    register = requests.post(
        f"{base_url}/auth/register",
        json={
            "email": SEED_ADMIN_EMAIL,
            "display_name": SEED_ADMIN_DISPLAY_NAME,
            "password": SEED_ADMIN_PASSWORD,
        },
        timeout=15,
    )
    if register.status_code == 201:
        print(f"Registered seed administrator {SEED_ADMIN_EMAIL} (Platform Administrator).")
    else:
        print(f"Seed administrator {SEED_ADMIN_EMAIL} already exists; signing in.")

    sign_in = requests.post(
        f"{base_url}/auth/sign-in",
        json={"email": SEED_ADMIN_EMAIL, "password": SEED_ADMIN_PASSWORD},
        timeout=15,
    )
    sign_in.raise_for_status()
    return sign_in.json()["token"]


def seed_plugin(
    base_url: str, headers: dict[str, str], plugin: dict[str, Any], installed_ids: set[str]
) -> None:
    manifest_path = plugin["dir"] / "openpdm-plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    plugin_id = manifest["id"]

    if plugin_id in installed_ids:
        print(f"{plugin_id} is already installed.")
    else:
        with tempfile.TemporaryDirectory() as tmp:
            package_path = Path(tmp) / f"{plugin['name']}.openpdm-plugin"
            print(f"Building {plugin['name']} plugin package...")
            result = subprocess.run(
                [sys.executable, str(plugin["build_script"]), "--output", str(package_path)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                detail = (
                    result.stderr.strip()
                    or result.stdout.strip()
                    or f"exit code {result.returncode}"
                )
                raise RuntimeError(f"Failed to build {plugin['name']} plugin package: {detail}")
            print(f"Installing {plugin_id}...")
            response = requests.post(
                f"{base_url}/plugins/packages",
                params={"plugin_type": "official"},
                headers=headers,
                files={
                    "package": (package_path.name, package_path.read_bytes(), "application/zip")
                },
                timeout=60,
            )
            response.raise_for_status()

    configuration_schema = manifest.get("configuration") or {}
    defaults = {
        key: prop["default"]
        for key, prop in (configuration_schema.get("properties") or {}).items()
        if "default" in prop
    }
    if defaults:
        requests.put(
            f"{base_url}/plugins/{plugin_id}/configuration",
            headers=headers,
            json={"values": defaults},
            timeout=15,
        ).raise_for_status()

    enable = requests.post(
        f"{base_url}/plugins/{plugin_id}/state",
        headers=headers,
        json={"enabled": True},
        timeout=15,
    )
    enable.raise_for_status()
    print(f"{plugin_id} enabled (lifecycle_state={enable.json()['lifecycle_state']}).")


def list_installed_plugin_ids(base_url: str, headers: dict[str, str]) -> set[str]:
    response = requests.get(f"{base_url}/plugins", headers=headers, timeout=15)
    response.raise_for_status()
    return {item["id"] for item in response.json()}


def seed_default_plugins(base_url: str) -> None:
    """Register/sign in as the seed administrator and install+enable DEFAULT_PLUGINS.

    Importable so other scripts (e.g. start_all.py) can reuse this without
    duplicating the install/enable flow.
    """
    token = ensure_admin_session(base_url)
    headers = {"Authorization": f"Bearer {token}"}
    installed_ids = list_installed_plugin_ids(base_url, headers)
    for plugin in DEFAULT_PLUGINS:
        seed_plugin(base_url, headers, plugin, installed_ids)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend-url",
        default=DEFAULT_BACKEND_URL,
        help=f"Backend base URL (default: {DEFAULT_BACKEND_URL})",
    )
    args = parser.parse_args()

    seed_default_plugins(args.backend_url)

    print("\nDefault Official Plugins are installed and enabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
