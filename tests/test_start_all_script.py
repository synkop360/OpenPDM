from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

spec = importlib.util.spec_from_file_location("start_all", ROOT / "scripts" / "start_all.py")
assert spec is not None and spec.loader is not None
start_all = importlib.util.module_from_spec(spec)
spec.loader.exec_module(start_all)


def test_resolve_frontend_runner_reports_unavailable_tool(monkeypatch) -> None:
    monkeypatch.setattr(start_all.shutil, "which", lambda name: None)

    command, is_available = start_all.resolve_frontend_runner()

    assert is_available is False
    assert command[-2:] == ["run", "dev"]
    assert any(
        part.endswith("pnpm.cmd") or part.endswith("pnpm.cjs") or part == "pnpm" for part in command
    )


def test_resolve_frontend_runner_uses_developer_helpers(monkeypatch) -> None:
    class StubDevModule:
        def javascript_runner(self) -> str:
            return "pnpm"

    monkeypatch.setattr(start_all, "load_dev_module", lambda: StubDevModule())
    monkeypatch.setattr(start_all.shutil, "which", lambda name: None)

    command, is_available = start_all.resolve_frontend_runner()

    assert is_available is False
    assert command == ["pnpm", "run", "dev"]


def test_resolve_frontend_runner_uses_resolved_executable_path(monkeypatch) -> None:
    class StubDevModule:
        def javascript_runner(self) -> str:
            return "pnpm"

    monkeypatch.setattr(start_all, "load_dev_module", lambda: StubDevModule())
    monkeypatch.setattr(start_all.os, "name", "nt", raising=False)
    monkeypatch.setattr(
        start_all.shutil, "which", lambda name: "C:/tools/pnpm.cmd" if name == "pnpm" else None
    )

    command, is_available = start_all.resolve_frontend_runner()

    assert is_available is True
    assert command == ["C:/tools/pnpm.cmd", "run", "dev"]


def test_start_all_documents_service_readiness_commands() -> None:
    script = (ROOT / "scripts" / "start_all.py").read_text(encoding="utf-8")

    assert "http://localhost:18000/health" in script
    assert "http://localhost:18000/foundation" in script
    assert "http://localhost:18000/docs" in script
    assert "http://localhost:5173" in script
    assert "http://127.0.0.1:8000/health" in script
    assert "http://127.0.0.1:8000/foundation" in script
    assert "VITE_API_PROXY_TARGET=http://localhost:8000" in script


def test_missing_prerequisite_messages_are_actionable() -> None:
    messages = start_all.missing_prerequisite_messages(set())

    assert any("Docker is required for the Compose stack" in message for message in messages)
    assert any("uv is required to install Python dependencies" in message for message in messages)
    assert any("Node.js is required for the Vite Web UI" in message for message in messages)
    assert any("pnpm is preferred for Web UI" in message for message in messages)
