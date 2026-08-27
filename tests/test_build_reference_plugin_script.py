from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location(
    "build_reference_plugin", ROOT / "scripts" / "build_reference_plugin.py"
)
assert spec is not None and spec.loader is not None
build_reference_plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_reference_plugin)


def test_find_componentize_py_prefers_path(monkeypatch) -> None:
    monkeypatch.setattr(
        build_reference_plugin.shutil, "which", lambda name: "/usr/bin/componentize-py"
    )

    assert build_reference_plugin._find_componentize_py() == "/usr/bin/componentize-py"


def test_find_componentize_py_falls_back_to_interpreter_directory(monkeypatch, tmp_path) -> None:
    # A bare invocation of this venv's own interpreter (no `uv run` -- e.g. the
    # desktop launcher spawning this script directly) won't have the venv's
    # Scripts directory on PATH, so shutil.which alone would miss it.
    monkeypatch.setattr(build_reference_plugin.shutil, "which", lambda name: None)
    monkeypatch.setattr(build_reference_plugin.sys, "platform", "win32", raising=False)
    scripts_dir = tmp_path / "Scripts"
    scripts_dir.mkdir()
    componentize = scripts_dir / "componentize-py.exe"
    componentize.write_text("")
    monkeypatch.setattr(
        build_reference_plugin.sys, "executable", str(scripts_dir / "pythonw.exe"), raising=False
    )

    assert build_reference_plugin._find_componentize_py() == str(componentize)


def test_find_componentize_py_returns_none_when_missing_everywhere(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(build_reference_plugin.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        build_reference_plugin.sys, "executable", str(tmp_path / "pythonw.exe"), raising=False
    )

    assert build_reference_plugin._find_componentize_py() is None
