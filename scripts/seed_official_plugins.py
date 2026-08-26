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

Add an entry to DEFAULT_PLUGINS to seed another Official Plugin.
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

# The default set of Official Plugins to install and enable. Add an entry
# here to seed another one; each just needs its source directory (which must
# contain openpdm-plugin.json) and its build script.
DEFAULT_PLUGINS: list[dict[str, Any]] = [
    {
        "name": "reference",
        "dir": ROOT / "plugins" / "reference",
        "build_script": ROOT / "scripts" / "build_reference_plugin.py",
    },
]


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
            subprocess.run(
                [sys.executable, str(plugin["build_script"]), "--output", str(package_path)],
                check=True,
            )
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--backend-url",
        default=DEFAULT_BACKEND_URL,
        help=f"Backend base URL (default: {DEFAULT_BACKEND_URL})",
    )
    args = parser.parse_args()

    token = ensure_admin_session(args.backend_url)
    headers = {"Authorization": f"Bearer {token}"}

    existing = requests.get(f"{args.backend_url}/plugins", headers=headers, timeout=15)
    existing.raise_for_status()
    installed_ids = {item["id"] for item in existing.json()}

    for plugin in DEFAULT_PLUGINS:
        seed_plugin(args.backend_url, headers, plugin, installed_ids)

    print("\nDefault Official Plugins are installed and enabled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
