"""Validate that the Phase 0 foundation files are present and coherent."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_PATHS = [
    "AGENTS.md",
    "README.md",
    "CONTRIBUTING.md",
    "docs/PROJECT_CHARTER.md",
    "docs/ARCHITECTURE.md",
    "docs/VISION.md",
    "ROADMAP.md",
    "pyproject.toml",
    ".dockerignore",
    ".env.example",
    "pnpm-workspace.yaml",
    "pnpm-lock.yaml",
    "backend/src/openpdm/main.py",
    "backend/src/openpdm/platform_core/boundaries.py",
    "backend/src/openpdm/platform_core/modules/README.md",
    "backend/src/openpdm/extension_api/__init__.py",
    "backend/src/openpdm/infrastructure/database.py",
    "backend/src/openpdm/infrastructure/blob_storage.py",
    "backend/tests/test_foundation_api.py",
    "tests/test_architecture_boundaries.py",
    "frontend/package.json",
    "frontend/src/App.tsx",
    "desktop/package.json",
    "desktop/src-tauri/tauri.conf.json",
    "deployment/compose.yaml",
    ".github/workflows/ci.yaml",
    "docs/DEVELOPMENT.md",
    "docs/DEPLOYMENT.md",
    "docs/PHASE_0_DEMO.md",
]

REQUIRED_ADR_PREFIXES = [
    "ADR-0001",
    "ADR-0002",
    "ADR-0003",
    "ADR-0004",
    "ADR-0005",
    "ADR-0006",
    "ADR-0007",
    "ADR-0008",
]

FORBIDDEN_PLATFORM_CORE_TERMS = {
    "solidworks",
    "freecad",
    "kicad",
    "catia",
    "creo",
    "pcb",
}


def main() -> int:
    errors: list[str] = []
    for relative_path in REQUIRED_PATHS:
        if not (ROOT / relative_path).exists():
            errors.append(f"missing required Phase 0 path: {relative_path}")

    adr_dir = ROOT / "docs" / "adr"
    for prefix in REQUIRED_ADR_PREFIXES:
        if not any(adr_dir.glob(f"{prefix}*.md")):
            errors.append(f"missing required accepted ADR: {prefix}")

    platform_core = ROOT / "backend" / "src" / "openpdm" / "platform_core"
    if platform_core.exists():
        for source_file in platform_core.rglob("*.py"):
            text = source_file.read_text(encoding="utf-8").lower()
            for term in FORBIDDEN_PLATFORM_CORE_TERMS:
                if term in text:
                    errors.append(
                        f"engineering-domain term '{term}' found in {source_file.relative_to(ROOT)}"
                    )

    if errors:
        print("Phase 0 validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Phase 0 validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
