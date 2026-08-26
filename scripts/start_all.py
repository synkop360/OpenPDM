#!/usr/bin/env python3
"""Start the local OpenPDM development services together."""

from __future__ import annotations

import argparse
import http.client
import importlib.util
import itertools
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]

COMPOSE_BACKEND_URL = "http://localhost:18000"
DIRECT_BACKEND_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:5173"
FRONTEND_PROXY_TARGET = "VITE_API_PROXY_TARGET=http://localhost:8000"

COMPOSE_SERVICES = ("postgres", "minio", "backend")

READINESS_CHECKS = [
    ("Backend health", "http://localhost:18000/health"),
    ("Foundation API", "http://localhost:18000/foundation"),
    ("API docs", "http://localhost:18000/docs"),
    ("Web UI", FRONTEND_URL),
]

DIRECT_BACKEND_READINESS_CHECKS = [
    ("Direct backend health", "http://127.0.0.1:8000/health"),
    ("Direct Foundation API", "http://127.0.0.1:8000/foundation"),
    ("Direct API docs", "http://127.0.0.1:8000/docs"),
]

PREREQUISITE_HINTS = {
    "docker": "Docker is required for the Compose stack that starts PostgreSQL, MinIO and the backend.",
    "uv": "uv is required to install Python dependencies and run backend development commands.",
    "node": "Node.js is required for the Vite Web UI.",
    "pnpm": "pnpm is preferred for Web UI dependency and development commands; npm is accepted as a fallback.",
}


class StatusLine:
    """A single console line that updates in place, degrading to plain prints on non-tty output."""

    _SPINNER = "|/-\\"

    def __init__(self) -> None:
        self._is_tty = sys.stdout.isatty()
        self._last_len = 0
        self._frames = itertools.cycle(self._SPINNER)

    def spin(self, text: str) -> None:
        frame = next(self._frames) if self._is_tty else ""
        self._write(f"{frame + ' ' if frame else ''}{text}", newline=False)

    def ok(self, text: str) -> None:
        self._write(f"[OK] {text}", newline=True)

    def warn(self, text: str) -> None:
        self._write(f"[WARN] {text}", newline=True)

    def fail(self, text: str) -> None:
        self._write(f"[FAIL] {text}", newline=True)

    def info(self, text: str) -> None:
        self._write(text, newline=True)

    def _write(self, text: str, *, newline: bool) -> None:
        if self._is_tty:
            pad = max(0, self._last_len - len(text))
            end = "\n" if newline else ""
            print(f"\r{text}{' ' * pad}", end=end, flush=True)
            self._last_len = 0 if newline else len(text)
        elif newline or not self._is_tty:
            print(text, flush=True)


def wait_for_backend(url: str, timeout: int = 60, status: StatusLine | None = None) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return True
        # The container port can be open before the server inside it is
        # actually accepting requests (e.g. Alembic migrations still
        # running), which resets the connection instead of refusing it. Keep
        # polling through that race instead of treating it as fatal.
        except (HTTPError, URLError, ConnectionError, http.client.HTTPException, TimeoutError):
            pass
        if status is not None:
            remaining = max(0, int(deadline - time.time()))
            status.spin(f"Waiting for backend to become healthy... ({remaining}s left)")
        time.sleep(1)
    return False


def get_compose_service_states() -> dict[str, str]:
    """Return {service: state} for the Compose stack, e.g. {"postgres": "running"}.

    Returns an empty dict if Docker/Compose is unavailable or the stack has
    never been created, so callers can treat that the same as "not running".
    """
    try:
        result = subprocess.run(
            ["docker", "compose", "-f", "deployment/compose.yaml", "ps", "--format", "json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}
    raw = result.stdout.strip()
    if result.returncode != 0 or not raw:
        return {}

    entries: list[dict[str, str]] = []
    try:
        parsed = json.loads(raw)
        entries = parsed if isinstance(parsed, list) else [parsed]
    except json.JSONDecodeError:
        # Compose v2 emits newline-delimited JSON on some platforms/versions.
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return {entry.get("Service", "?"): entry.get("State", "unknown") for entry in entries}


def load_dev_module():
    spec = importlib.util.spec_from_file_location("openpdm_dev", ROOT / "scripts" / "dev.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to import scripts/dev.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_seed_plugins_module():
    spec = importlib.util.spec_from_file_location(
        "openpdm_seed_plugins", ROOT / "scripts" / "seed_official_plugins.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to import scripts/seed_official_plugins.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Start the OpenPDM backend compose stack and frontend dev server."
    )
    parser.add_argument(
        "--skip-compose", action="store_true", help="Start only the frontend dev server"
    )
    parser.add_argument("--skip-frontend", action="store_true", help="Start only the compose stack")
    parser.add_argument(
        "--skip-plugins",
        action="store_true",
        help="Do not check or install the default Official Plugins",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print the commands that would be run"
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Launch the desktop GUI (scripts/launcher_gui.py) instead of the CLI flow",
    )
    return parser.parse_args()


def resolve_executable(command: str) -> str | None:
    resolved = shutil.which(command)
    if resolved is not None:
        return resolved
    if os.name == "nt":
        for extension in (".cmd", ".ps1", ".bat", ".exe"):
            resolved = shutil.which(f"{command}{extension}")
            if resolved is not None:
                return resolved
    return None


def available_tool_names() -> set[str]:
    available = {name for name in ("docker", "uv", "node") if resolve_executable(name)}
    if resolve_executable("pnpm") or resolve_executable("npm"):
        available.add("pnpm")
    return available


def missing_prerequisite_messages(tool_names: set[str] | None = None) -> list[str]:
    available = available_tool_names() if tool_names is None else tool_names
    messages: list[str] = []
    for name in ("docker", "uv", "node", "pnpm"):
        if name not in available:
            messages.append(f"{name}: {PREREQUISITE_HINTS[name]}")
    return messages


def print_prerequisite_warnings() -> None:
    messages = missing_prerequisite_messages()
    if not messages:
        return
    print("Startup prerequisite warnings:", file=sys.stderr)
    for message in messages:
        print(f"- {message}", file=sys.stderr)


def print_readiness_checks() -> None:
    print("\nReadiness checks:")
    for label, url in READINESS_CHECKS:
        print(f"- {label}: {url}")
    print("\nBackend-only checks for python scripts/dev.py run-backend:")
    for label, url in DIRECT_BACKEND_READINESS_CHECKS:
        print(f"- {label}: {url}")
    print(f"\nWhen using the direct backend with Vite, set {FRONTEND_PROXY_TARGET}.")


def resolve_frontend_runner() -> tuple[list[str], bool]:
    dev_module = load_dev_module()
    runner_name = dev_module.javascript_runner() or "pnpm"
    resolved_runner = resolve_executable(runner_name)
    if resolved_runner is not None:
        return [resolved_runner, "run", "dev"], True
    return [runner_name, "run", "dev"], False


def build_dev_helper_command(
    callback_name: str, cwd: Path | None = None, runner_override: str | None = None
) -> list[str]:
    script_path = str(ROOT / "scripts" / "dev.py")
    if callback_name == "compose_up":
        callback = "module.compose_up()"
    elif callback_name == "run_javascript_script":
        target_dir = str(cwd or ROOT / "frontend")
        runner_literal = repr(runner_override) if runner_override is not None else "None"
        callback = "\n".join(
            [
                f"module.javascript_runner = lambda: {runner_literal}",
                f"module.run_javascript_script('dev', Path({target_dir!r}))",
            ]
        )
    else:
        raise ValueError(f"Unsupported helper callback: {callback_name}")

    code = "\n".join(
        [
            "import importlib.util",
            "from pathlib import Path",
            f"spec = importlib.util.spec_from_file_location('openpdm_dev', {script_path!r})",
            "module = importlib.util.module_from_spec(spec)",
            "spec.loader.exec_module(module)",
            callback,
        ]
    )
    return [sys.executable, "-c", code]


def start_process(label: str, command: Sequence[str], cwd: Path) -> subprocess.Popen[str]:
    print(f"Starting {label}: {' '.join(command)}")
    dev_module = load_dev_module()
    env = dev_module.command_env()
    if os.name == "nt":
        node_dir = r"C:\Program Files\nodejs"
        npm_global_bin = r"C:\Users\thoma\AppData\Roaming\npm"
        existing_path = env.get("PATH", "")
        extra_paths = [node_dir, npm_global_bin]
        env["PATH"] = (
            os.pathsep.join([existing_path, *extra_paths])
            if existing_path
            else os.pathsep.join(extra_paths)
        )
        env.setdefault("NODE_PATH", r"C:\Users\thoma\AppData\Roaming\npm\node_modules")
    try:
        kwargs = dict(
            cwd=str(cwd),
            stdin=sys.stdin,
            stdout=sys.stdout,
            stderr=sys.stderr,
            text=True,
            env=env,
        )
        if os.name == "nt":
            return subprocess.Popen(
                list(command), creationflags=subprocess.CREATE_NEW_CONSOLE, **kwargs
            )
        return subprocess.Popen(list(command), **kwargs)

    except FileNotFoundError as exc:
        raise RuntimeError(f"Unable to start {label}: {exc}") from exc


def stop_process(process: subprocess.Popen[str], label: str) -> None:
    if process.poll() is not None:
        return
    print(f"Stopping {label}...")
    try:
        process.terminate()
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def ensure_default_plugins(status: StatusLine) -> None:
    """Best-effort: install/enable the default Official Plugins if not already present.

    Never fatal to startup — a failure here (e.g. Docker networking hiccup,
    a seed account with a locally-changed password) is reported and skipped
    rather than blocking the rest of the stack from coming up.
    """
    status.spin("Checking Official Plugins...")
    try:
        seed = load_seed_plugins_module()
        token = seed.ensure_admin_session(COMPOSE_BACKEND_URL)
        headers = {"Authorization": f"Bearer {token}"}
        installed_ids = seed.list_installed_plugin_ids(COMPOSE_BACKEND_URL, headers)
        pending = [
            p
            for p in seed.DEFAULT_PLUGINS
            if json.loads((p["dir"] / "openpdm-plugin.json").read_text(encoding="utf-8"))["id"]
            not in installed_ids
        ]
        if pending:
            status.info(f"Installing {len(pending)} default Official Plugin(s)...")
        for plugin in seed.DEFAULT_PLUGINS:
            seed.seed_plugin(COMPOSE_BACKEND_URL, headers, plugin, installed_ids)
        status.ok(f"Official Plugins ready ({len(seed.DEFAULT_PLUGINS)} enabled).")
    except Exception as exc:  # noqa: BLE001 - best-effort convenience step, never fatal
        status.warn(f"Official Plugins check skipped: {exc}")


def main() -> int:
    args = parse_args()

    if args.gui:
        spec = importlib.util.spec_from_file_location(
            "openpdm_launcher_gui", ROOT / "scripts" / "launcher_gui.py"
        )
        if spec is None or spec.loader is None:
            print("Unable to load scripts/launcher_gui.py", file=sys.stderr)
            return 1
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.main()

    if args.skip_compose and args.skip_frontend:
        print(
            "Nothing to start; both --skip-compose and --skip-frontend were provided.",
            file=sys.stderr,
        )
        return 2

    print_prerequisite_warnings()
    frontend_command, frontend_available = resolve_frontend_runner()

    if args.dry_run:
        if not args.skip_compose:
            print("Compose stack:")
            print("  docker compose --env-file .env.example -f deployment/compose.yaml up --build")
        if not args.skip_frontend:
            print("Frontend:")
            print(f"  {' '.join(frontend_command)} (cwd: frontend)")
            if not frontend_available:
                print(
                    "  Warning: pnpm/npm was not found on PATH; install Node.js tooling before starting the frontend."
                )
        print_readiness_checks()
        return 0

    status = StatusLine()
    processes: list[tuple[str, subprocess.Popen[str]]] = []
    try:
        if not args.skip_compose:
            service_states = get_compose_service_states()
            print("Compose service status:")
            for service in COMPOSE_SERVICES:
                state = service_states.get(service, "not created")
                print(f"- {service}: {state}")

            already_running = all(
                service_states.get(service) == "running" for service in COMPOSE_SERVICES
            )
            if already_running:
                print("Compose stack is already running; not restarting it.")
            else:
                processes.append(
                    (
                        "compose",
                        start_process(
                            "compose stack",
                            build_dev_helper_command("compose_up"),
                            ROOT,
                        ),
                    )
                )

            ok = wait_for_backend(f"{COMPOSE_BACKEND_URL}/health", timeout=300, status=status)
            if not ok:
                raise RuntimeError("Backend did not become healthy within timeout")
            status.ok("Backend is healthy.")

            if not args.skip_plugins:
                ensure_default_plugins(status)

        if not args.skip_frontend:
            if not frontend_available:
                print(
                    "Warning: pnpm/npm was not found on PATH; skipping frontend dev server.",
                    file=sys.stderr,
                )
            else:
                processes.append(
                    (
                        "frontend",
                        start_process(
                            "frontend dev server",
                            build_dev_helper_command(
                                "run_javascript_script",
                                ROOT / "frontend",
                                runner_override=frontend_command[0] if frontend_command else None,
                            ),
                            ROOT / "frontend",
                        ),
                    )
                )

        print("\nOpenPDM services are running.")
        print(f"- Backend/API: {COMPOSE_BACKEND_URL}")
        if frontend_available and not args.skip_frontend:
            print(f"- Frontend dev server: {FRONTEND_URL}")
        elif not args.skip_frontend:
            print("- Frontend dev server: not started (pnpm/npm unavailable)")
        print_readiness_checks()
        print("Press Ctrl+C to stop everything.\n")

        while True:
            for label, process in processes:
                if process.poll() is not None:
                    raise RuntimeError(
                        f"{label} exited unexpectedly with code {process.returncode}"
                    )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping services...")
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        for label, process in reversed(processes):
            stop_process(process, label)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
