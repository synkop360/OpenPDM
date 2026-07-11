import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = ROOT / "backend" / "src" / "openpdm"
PLATFORM_MODULES = {
    "authentication",
    "organizations",
    "projects",
    "blobs",
    "assets",
    "relationships",
    "collaboration",
    "metadata",
    "search",
    "plugins",
    "audit",
}


def imported_modules(source_file: Path) -> set[str]:
    tree = ast.parse(source_file.read_text(encoding="utf-8"), filename=str(source_file))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
    return imports


def test_application_api_uses_composition_root_not_module_implementations() -> None:
    violations: list[str] = []
    for source_file in (BACKEND_SRC / "api").rglob("*.py"):
        imports = imported_modules(source_file)
        if any(
            name.startswith("openpdm.platform_core.modules.models")
            or name.startswith("openpdm.platform_core.modules.services")
            for name in imports
        ):
            violations.append(str(source_file.relative_to(ROOT)))
    assert violations == []


def test_public_platform_module_contracts_exist_and_publish_no_orm() -> None:
    missing: list[str] = []
    orm_leaks: list[str] = []
    modules_root = BACKEND_SRC / "platform_core" / "modules"
    for module_name in PLATFORM_MODULES:
        contract = modules_root / module_name / "__init__.py"
        if not contract.exists():
            missing.append(module_name)
            continue
        imports = imported_modules(contract)
        if any(name.startswith("sqlalchemy") for name in imports):
            orm_leaks.append(module_name)
        tree = ast.parse(contract.read_text(encoding="utf-8"))
        if not any(isinstance(node, ast.ClassDef) for node in tree.body):
            missing.append(f"{module_name}:Protocol")
    assert missing == []
    assert orm_leaks == []


def test_extension_api_boundary_exists_and_has_no_internal_dependency() -> None:
    extension_api = BACKEND_SRC / "extension_api" / "__init__.py"
    assert extension_api.exists()
    assert not any(
        name.startswith("openpdm.platform_core.modules") for name in imported_modules(extension_api)
    )


def test_platform_core_does_not_contain_engineering_domain_terms() -> None:
    domain_terms = {"solidworks", "freecad", "kicad", "catia", "creo", "nx", "pcb", "cad"}
    violations: list[str] = []
    for source_file in (BACKEND_SRC / "platform_core").rglob("*.py"):
        text = source_file.read_text(encoding="utf-8").lower()
        tokens = set(re.findall(r"\b[a-z0-9_]+\b", text))
        if any(term in tokens for term in domain_terms):
            violations.append(str(source_file.relative_to(ROOT)))
    assert violations == []
