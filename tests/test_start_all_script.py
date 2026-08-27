from __future__ import annotations

import http.client
import importlib.util
import sys
from pathlib import Path
from urllib.error import URLError

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


class _FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None


def test_wait_for_backend_retries_past_a_mid_startup_connection_reset(monkeypatch) -> None:
    # The container port can be open before the server inside it is actually
    # accepting requests (e.g. Alembic migrations still running), which
    # raises http.client.RemoteDisconnected instead of a URLError/HTTPError.
    attempts = [
        http.client.RemoteDisconnected("Remote end closed connection without response"),
        ConnectionResetError("connection reset"),
        URLError("connection refused"),
        _FakeResponse(200),
    ]

    def fake_urlopen(url, timeout):
        result = attempts.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(start_all.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(start_all.time, "sleep", lambda seconds: None)

    assert start_all.wait_for_backend("http://localhost:18000/health", timeout=5) is True
    assert attempts == []


def test_wait_for_backend_gives_up_after_the_timeout(monkeypatch) -> None:
    def fake_urlopen(url, timeout):
        raise http.client.RemoteDisconnected("Remote end closed connection without response")

    times = iter([0, 1, 2, 3, 4, 5, 6])
    monkeypatch.setattr(start_all.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(start_all.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(start_all.time, "time", lambda: next(times))

    assert start_all.wait_for_backend("http://localhost:18000/health", timeout=5) is False


def test_missing_prerequisite_messages_are_actionable() -> None:
    messages = start_all.missing_prerequisite_messages(set())

    assert any("Docker is required for the Compose stack" in message for message in messages)
    assert any("uv is required to install Python dependencies" in message for message in messages)
    assert any("Node.js is required for the Vite Web UI" in message for message in messages)
    assert any("pnpm is preferred for Web UI" in message for message in messages)


class _FakeCompletedProcess:
    def __init__(self, stdout: str, returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode


def test_get_compose_service_states_parses_json_array(monkeypatch) -> None:
    payload = (
        '[{"Service": "postgres", "State": "running"}, '
        '{"Service": "minio", "State": "running"}, '
        '{"Service": "backend", "State": "exited"}]'
    )
    monkeypatch.setattr(
        start_all.subprocess,
        "run",
        lambda *args, **kwargs: _FakeCompletedProcess(payload),
    )

    states = start_all.get_compose_service_states()

    assert states == {"postgres": "running", "minio": "running", "backend": "exited"}


def test_get_compose_service_states_parses_newline_delimited_json(monkeypatch) -> None:
    payload = (
        '{"Service": "postgres", "State": "running"}\n' '{"Service": "minio", "State": "running"}\n'
    )
    monkeypatch.setattr(
        start_all.subprocess,
        "run",
        lambda *args, **kwargs: _FakeCompletedProcess(payload),
    )

    states = start_all.get_compose_service_states()

    assert states == {"postgres": "running", "minio": "running"}


def test_get_compose_service_states_returns_empty_when_docker_unavailable(monkeypatch) -> None:
    def raise_missing(*args, **kwargs):
        raise FileNotFoundError("docker not found")

    monkeypatch.setattr(start_all.subprocess, "run", raise_missing)

    assert start_all.get_compose_service_states() == {}


def test_get_compose_service_states_returns_empty_when_stack_not_created(monkeypatch) -> None:
    monkeypatch.setattr(
        start_all.subprocess,
        "run",
        lambda *args, **kwargs: _FakeCompletedProcess("", returncode=1),
    )

    assert start_all.get_compose_service_states() == {}


def test_status_line_non_tty_prints_plain_lines(capsys) -> None:
    status = start_all.StatusLine()
    status._is_tty = False

    status.spin("Waiting...")
    status.ok("Backend is healthy.")
    status.warn("Something needs attention.")
    status.fail("Something failed.")

    output = capsys.readouterr().out
    assert "Waiting..." in output
    assert "[OK] Backend is healthy." in output
    assert "[WARN] Something needs attention." in output
    assert "[FAIL] Something failed." in output


def test_ensure_default_plugins_is_never_fatal(monkeypatch) -> None:
    def raise_error():
        raise RuntimeError("network hiccup")

    monkeypatch.setattr(start_all, "load_seed_plugins_module", raise_error)
    status = start_all.StatusLine()
    status._is_tty = False

    # Must not raise: plugin seeding is a best-effort convenience step.
    start_all.ensure_default_plugins(status)
