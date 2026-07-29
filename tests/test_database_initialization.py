from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_app_factory_does_not_directly_initialize_schema() -> None:
    main_source = (ROOT / "backend" / "src" / "openpdm" / "main.py").read_text(
        encoding="utf-8"
    )

    assert "initialize_database()" not in main_source
    assert "initialize_disposable_database()" not in main_source


def test_direct_schema_creation_is_named_as_disposable() -> None:
    database_source = (
        ROOT / "backend" / "src" / "openpdm" / "infrastructure" / "database.py"
    ).read_text(encoding="utf-8")

    assert "def initialize_disposable_database(" in database_source
    assert "metadata.create_all" in database_source
