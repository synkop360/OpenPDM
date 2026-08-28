from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

spec = importlib.util.spec_from_file_location(
    "seed_official_plugins", ROOT / "scripts" / "seed_official_plugins.py"
)
assert spec is not None and spec.loader is not None
seed_official_plugins = importlib.util.module_from_spec(spec)
sys.modules["seed_official_plugins"] = seed_official_plugins
spec.loader.exec_module(seed_official_plugins)


def _write_plugin(
    plugins_root: Path, name: str, *, manifest_id: str, with_build_script: bool = True
) -> None:
    plugin_dir = plugins_root / name
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "openpdm-plugin.json").write_text(
        json.dumps({"id": manifest_id, "name": name}), encoding="utf-8"
    )
    if with_build_script:
        script_name = f"build_{name.replace('-', '_')}_plugin.py"
        (plugins_root.parent / "scripts" / script_name).write_text("", encoding="utf-8")


def test_discover_official_plugins_finds_a_plugin_with_manifest_and_build_script(
    tmp_path: Path,
) -> None:
    (tmp_path / "scripts").mkdir()
    plugins_root = tmp_path / "plugins"
    _write_plugin(plugins_root, "widget", manifest_id="org.openpdm.widget")

    discovered = seed_official_plugins.discover_official_plugins(plugins_root)

    assert [p["name"] for p in discovered] == ["widget"]
    assert discovered[0]["dir"] == plugins_root / "widget"
    assert discovered[0]["build_script"].name == "build_widget_plugin.py"


def test_discover_official_plugins_excludes_example_fixtures(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    plugins_root = tmp_path / "plugins"
    _write_plugin(
        plugins_root, "dummy-categories", manifest_id="org.openpdm.examples.asset-categories"
    )

    assert seed_official_plugins.discover_official_plugins(plugins_root) == []


def test_discover_official_plugins_skips_directory_without_build_script(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    plugins_root = tmp_path / "plugins"
    _write_plugin(
        plugins_root,
        "no-build-script",
        manifest_id="org.openpdm.no-build-script",
        with_build_script=False,
    )

    assert seed_official_plugins.discover_official_plugins(plugins_root) == []


def test_discover_official_plugins_skips_directory_without_manifest(tmp_path: Path) -> None:
    (tmp_path / "scripts").mkdir()
    plugins_root = tmp_path / "plugins"
    plugin_dir = plugins_root / "no-manifest"
    plugin_dir.mkdir(parents=True)
    (tmp_path / "scripts" / "build_no_manifest_plugin.py").write_text("", encoding="utf-8")

    assert seed_official_plugins.discover_official_plugins(plugins_root) == []


def test_discover_official_plugins_returns_empty_for_missing_root(tmp_path: Path) -> None:
    assert seed_official_plugins.discover_official_plugins(tmp_path / "does-not-exist") == []


def test_discover_official_plugins_against_the_real_repo() -> None:
    discovered = seed_official_plugins.discover_official_plugins(ROOT / "plugins")

    names = {p["name"] for p in discovered}
    assert "reference" in names
    assert "freecad" in names
    assert "dummy-categories" not in names
