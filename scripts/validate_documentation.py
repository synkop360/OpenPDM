"""Validate local Markdown links and Phase 4 documentation invariants."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^]]*]\(([^)]+)\)")


def validate_local_links() -> list[str]:
    errors: list[str] = []
    for document in [ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]:
        contents = document.read_text(encoding="utf-8")
        for raw_target in MARKDOWN_LINK.findall(contents):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_text = unquote(target.split("#", maxsplit=1)[0])
            if not path_text:
                continue
            resolved = (document.parent / path_text).resolve()
            if not resolved.exists():
                errors.append(f"{document.relative_to(ROOT)}: missing link target {target}")
    return errors


def validate_phase4_invariants() -> list[str]:
    errors: list[str] = []
    required = {
        "docs/PLUGIN_DEVELOPMENT.md": [
            "Extension API v1",
            "WebAssembly Component",
            "scaffold_plugin.py",
        ],
        "docs/PLUGIN_SECURITY.md": ["no WASI", "Platform Administrators"],
        "docs/API_REFERENCE.md": ["/plugins/packages", "/providers/metadata"],
    }
    for relative, phrases in required.items():
        contents = (ROOT / relative).read_text(encoding="utf-8")
        for phrase in phrases:
            if phrase not in contents:
                errors.append(f"{relative}: missing required Phase 4 phrase {phrase!r}")
    for relative in ("README.md", "docs/ARCHITECTURE.md", "docs/API_REFERENCE.md"):
        contents = (ROOT / relative).read_text(encoding="utf-8").lower()
        if "read-only plugin registry" in contents:
            errors.append(f"{relative}: stale Phase 1 plugin-registry description")
    plugin_contract = (
        ROOT / "backend/src/openpdm/platform_core/modules/plugins/__init__.py"
    ).read_text(encoding="utf-8")
    if "governed plugin lifecycle contract" not in plugin_contract:
        errors.append("Plugins Platform Module contract does not describe the governed lifecycle")
    return errors


def main() -> int:
    errors = [*validate_local_links(), *validate_phase4_invariants()]
    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Documentation validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
