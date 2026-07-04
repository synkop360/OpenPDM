from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "backend" / "src" / "openpdm"


def test_platform_module_internals_are_not_imported_directly() -> None:
    violations: list[str] = []
    for source_file in BACKEND_SRC.rglob("*.py"):
        if ".venv" in source_file.parts:
            continue
        text = source_file.read_text(encoding="utf-8")
        if ".internal" in text and "tests" not in source_file.parts:
            violations.append(str(source_file.relative_to(ROOT)))

    assert violations == []


def test_extension_api_boundary_exists() -> None:
    assert (BACKEND_SRC / "extension_api" / "__init__.py").exists()


def test_platform_core_does_not_contain_engineering_domain_terms() -> None:
    domain_terms = {"solidworks", "freecad", "kicad", "catia", "creo", "nx", "pcb", "cad"}
    violations: list[str] = []
    for source_file in (BACKEND_SRC / "platform_core").rglob("*.py"):
        text = source_file.read_text(encoding="utf-8").lower()
        if any(term in text for term in domain_terms):
            violations.append(str(source_file.relative_to(ROOT)))

    assert violations == []
