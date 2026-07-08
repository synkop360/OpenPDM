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
from http.client import RemoteDisconnected
from pathlib import Path
from typing import Sequence

import urllib.request
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parents[1]


def wait_for_backend(url: str, timeout: int = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                if resp.status == 200:
                    return True
        except (HTTPError, URLError, RemoteDisconnected, ConnectionError, TimeoutError):
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
    parser = argparse.ArgumentParser(description="Start the OpenPDM backend compose stack and frontend dev server.")
    parser.add_argument("--skip-compose", action="store_true", help="Start only the frontend dev server")
    parser.add_argument("--skip-frontend", action="store_true", help="Start only the compose stack")
    parser.add_argument("--dry-run", action="store_true", help="Print the commands that would be run")
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


def resolve_frontend_runner() -> tuple[list[str], bool]:
    dev_module = load_dev_module()
    runner_name = dev_module.javascript_runner() or "pnpm"
    resolved_runner = resolve_executable(runner_name)
    if resolved_runner is not None:
        return [resolved_runner, "run", "dev"], True
    return [runner_name, "run", "dev"], False


def build_dev_helper_command(callback_name: str, cwd: Path | None = None, runner_override: str | None = None) -> list[str]:
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
        env["PATH"] = os.pathsep.join([existing_path, *extra_paths]) if existing_path else os.pathsep.join(extra_paths)
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
            return subprocess.Popen(list(command), creationflags=subprocess.CREATE_NEW_CONSOLE, **kwargs)
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
        print("Nothing to start; both --skip-compose and --skip-frontend were provided.", file=sys.stderr)
        return 2

    frontend_command, frontend_available = resolve_frontend_runner()

    if args.dry_run:
        if not args.skip_compose:
            print("Compose stack:")
            print("  docker compose --env-file .env.example -f deployment/compose.yaml up --build")
        if not args.skip_frontend:
            print("Frontend:")
            print(f"  {' '.join(frontend_command)} (cwd: frontend)")
            if not frontend_available:
                print("  Warning: pnpm/npm was not found on PATH; install Node.js tooling before starting the frontend.")
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
            ok = wait_for_backend("http://localhost:18000/health", timeout=300)
            if not ok:
                raise RuntimeError("Backend did not become healthy within timeout")
        if not args.skip_frontend:
            if not frontend_available:
                print("Warning: pnpm/npm was not found on PATH; skipping frontend dev server.", file=sys.stderr)
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
        print("- Backend/API: http://localhost:18000")
        if frontend_available and not args.skip_frontend:
            print("- Frontend dev server: http://localhost:5173")
        elif not args.skip_frontend:
            print("- Frontend dev server: not started (pnpm/npm unavailable)")
        print("Press Ctrl+C to stop everything.\n")

        while True:
            for label, process in processes:
                if process.poll() is not None:
                    raise RuntimeError(f"{label} exited unexpectedly with code {process.returncode}")
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
