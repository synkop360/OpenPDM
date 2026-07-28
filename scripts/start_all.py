#!/usr/bin/env python3
"""Start the local OpenPDM development services together."""

from __future__ import annotations

import argparse
import importlib.util
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


def wait_for_backend(url: str, timeout: int = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except (HTTPError, URLError):
            pass
        time.sleep(1)
    return False


def load_dev_module():
    spec = importlib.util.spec_from_file_location("openpdm_dev", ROOT / "scripts" / "dev.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to import scripts/dev.py")
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
        "--dry-run", action="store_true", help="Print the commands that would be run"
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


def main() -> int:
    args = parse_args()

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

    processes: list[tuple[str, subprocess.Popen[str]]] = []
    try:
        if not args.skip_compose:
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
            print("Waiting for backend to become healthy...")
            ok = wait_for_backend(f"{COMPOSE_BACKEND_URL}/health", timeout=300)
            if not ok:
                raise RuntimeError("Backend did not become healthy within timeout")
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
