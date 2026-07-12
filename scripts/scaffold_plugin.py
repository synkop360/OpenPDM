"""Scaffold a minimal third-party OpenPDM plugin project."""

from __future__ import annotations

import argparse
from pathlib import Path

from openpdm.extension_api import scaffold_plugin


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--id", required=True, dest="plugin_id")
    parser.add_argument("--name", required=True)
    arguments = parser.parse_args()
    print(
        scaffold_plugin(
            arguments.destination,
            plugin_id=arguments.plugin_id,
            name=arguments.name,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
