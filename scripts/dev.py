"""Developer command runner for OpenPDM Phase 0."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


class CommandError(RuntimeError):
    """Raised when a developer command cannot be completed."""


def run(command: Sequence[str], cwd: Path = ROOT) -> None:
    print(f"> {' '.join(command)}")
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise CommandError(f"command failed with exit code {completed.returncode}")


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise CommandError(f"required tool not found on PATH: {name}")


def run_python_module(module: str, *args: str) -> None:
    if shutil.which("uv") is not None:
        run(["uv", "run", "python", "-m", module, *args])
        return
    if VENV_PYTHON.exists():
        run([str(VENV_PYTHON), "-m", module, *args])
        return
    raise CommandError("required Python runner not found on PATH: uv, or workspace .venv")


def run_python_script(script: str, *args: str) -> None:
    if shutil.which("uv") is not None:
        run(["uv", "run", "python", script, *args])
        return
    if VENV_PYTHON.exists():
        run([str(VENV_PYTHON), script, *args])
        return
    run([sys.executable, script, *args])


def javascript_runner() -> str | None:
    if shutil.which("pnpm") is not None:
        return "pnpm"
    if shutil.which("npm") is not None:
        return "npm"
    return None


def run_javascript_script(script: str, cwd: Path) -> None:
    runner = javascript_runner()
    if runner is None:
        raise CommandError("required JavaScript package manager not found on PATH: pnpm or npm")
    run([runner, "run", script], cwd=cwd)


def install() -> None:
    require_tool("uv")
    run(["uv", "sync", "--all-groups"])
    runner = javascript_runner()
    if runner == "pnpm":
        run(["pnpm", "install"])
    elif runner == "npm":
        run(["npm", "install"], cwd=ROOT / "frontend")
        run(["npm", "install"], cwd=ROOT / "desktop")


def lint() -> None:
    run_python_module("ruff", "format", "--check", ".")
    run_python_module("ruff", "check", ".")
    if javascript_runner() is not None and (ROOT / "frontend" / "node_modules").exists():
        run_javascript_script("lint", ROOT / "frontend")


def test() -> None:
    run_python_module("pytest")
    run_python_script("scripts/validate_phase0.py")
    run_python_script(
        ".github/automation/project/validate.py",
        ".github/automation/project/project.yaml",
    )
    if javascript_runner() is not None and (ROOT / "frontend" / "node_modules").exists():
        run_javascript_script("test", ROOT / "frontend")


def run_backend() -> None:
    run_python_module(
        "uvicorn",
        "openpdm.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload",
    )


def compose_up() -> None:
    require_tool("docker")
    run(
        [
            "docker",
            "compose",
            "--env-file",
            ".env.example",
            "-f",
            "deployment/compose.yaml",
            "up",
            "--build",
        ]
    )


def validate() -> None:
    run_python_script("scripts/validate_phase0.py")
    run_python_script(
        ".github/automation/project/validate.py",
        ".github/automation/project/project.yaml",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenPDM developer commands.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ["install", "lint", "test", "run-backend", "compose-up", "validate"]:
        subcommands.add_parser(command)

    args = parser.parse_args()
    commands = {
        "install": install,
        "lint": lint,
        "test": test,
        "run-backend": run_backend,
        "compose-up": compose_up,
        "validate": validate,
    }

    try:
        commands[args.command]()
    except CommandError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
