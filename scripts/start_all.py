#!/usr/bin/env python3
"""Start the local OpenPDM development services together."""

from __future__ import annotations

import argparse
import http.client
import importlib.machinery
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
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import deployments  # noqa: E402

# The built-in "default" deployment's values. Named deployments override these
# per stack; see scripts/deployments.py. Kept as module constants so the
# historical single-stack behaviour, and the URLs documented below, are stable.
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


def readiness_checks(deployment: "deployments.Deployment") -> list[tuple[str, str]]:
    """Readiness probes for a resolved deployment's Compose stack."""
    base = deployment.backend_url
    return [
        ("Backend health", f"{base}/health"),
        ("Foundation API", f"{base}/foundation"),
        ("API docs", f"{base}/docs"),
        ("Web UI", deployment.frontend_url),
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


def get_compose_service_states(project: str | None = None) -> dict[str, str]:
    """Return {service: state} for the Compose stack, e.g. {"postgres": "running"}.

    Returns an empty dict if Docker/Compose is unavailable or the stack has
    never been created, so callers can treat that the same as "not running".
    ``project`` targets a named deployment's Compose project instead of the
    default stack.
    """
    project_args = ["-p", project] if project else []
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                *project_args,
                "-f",
                "deployment/compose.yaml",
                "ps",
                "--format",
                "json",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
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


def _load_module_from_spec(spec: importlib.machinery.ModuleSpec):
    """module_from_spec + exec_module, registered in sys.modules first.

    Some stdlib machinery (e.g. dataclasses' field-type resolution) looks
    itself up via sys.modules[cls.__module__] while the module body is
    still executing; without this registration that lookup returns None
    and crashes with AttributeError on some Python versions/builds.
    """
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_dev_module():
    spec = importlib.util.spec_from_file_location("openpdm_dev", ROOT / "scripts" / "dev.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to import scripts/dev.py")
    return _load_module_from_spec(spec)


def load_seed_plugins_module():
    spec = importlib.util.spec_from_file_location(
        "openpdm_seed_plugins", ROOT / "scripts" / "seed_official_plugins.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to import scripts/seed_official_plugins.py")
    return _load_module_from_spec(spec)


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
    parser.add_argument(
        "--debug",
        action="store_true",
        help="With --gui, show raw Docker Compose and Vite dev-server output in the log "
        "instead of just status messages, Docker messages and the Vite server address",
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=300,
        metavar="SECONDS",
        help="With --gui, how often to re-check whether the Docker containers still exist "
        "(default: 300s / 5 minutes)",
    )
    parser.add_argument(
        "--deployment",
        default="default",
        metavar="NAME",
        help="Named launcher deployment to run: its own Compose project, host ports and "
        "blob storage (see 'deployments/'). Defaults to the built-in single stack.",
    )
    parser.add_argument(
        "--list-deployments",
        action="store_true",
        help="List the configured deployments and exit.",
    )
    parser.add_argument(
        "--new-deployment",
        action="store_true",
        help="Interactively create a new deployment (name and blob storage location), "
        "then exit without starting it.",
    )
    return parser.parse_args()


def print_deployment_list() -> None:
    default = deployments.default_deployment()
    print("Configured deployments:")
    print(f"- {default.name:<16} backend {default.backend_url}  ({default.storage.describe()})")
    for name in deployments.list_deployment_names():
        try:
            dep = deployments.load(name)
        except deployments.DeploymentError as exc:
            print(f"- {name:<16} [invalid: {exc}]")
            continue
        print(f"- {dep.name:<16} backend {dep.backend_url}  ({dep.storage.describe()})")


def prompt_new_deployment() -> "deployments.Deployment":
    """Interactive create: name, then blob storage location."""
    name = input("Deployment name: ").strip()
    slug = deployments.slugify(name)

    print("\nBlob storage location for this deployment:")
    print("  1) bundled  - this deployment's own MinIO container (isolated, default)")
    print("  2) s3       - an external S3-compatible bucket (e.g. OVH, AWS)")
    print("  3) local    - a local filesystem directory or Docker volume")
    choice = input("Choose 1/2/3 [1]: ").strip() or "1"

    if choice == "2":
        endpoint = input("  S3 endpoint URL (https://...): ").strip()
        region = input("  Region [us-east-1]: ").strip() or "us-east-1"
        bucket = input("  Bucket name: ").strip()
        access_key = input("  Access key: ").strip()
        secret_key = input("  Secret key: ").strip()
        storage = deployments.StorageConfig(
            kind="s3",
            endpoint_url=endpoint,
            bucket=bucket,
            access_key=access_key,
            secret_key=secret_key,
            region=region,
        )
    elif choice == "3":
        source = input(
            "  Directory (absolute host path) or Docker volume name " f"[openpdm-{slug}-blobs]: "
        ).strip()
        storage = deployments.StorageConfig(
            kind="local", local_source=source or f"openpdm-{slug}-blobs"
        )
    else:
        storage = deployments.StorageConfig(kind="bundled")

    deployment = deployments.create(slug, storage)
    print(f"\nCreated deployment {deployment.name!r}:")
    print(f"  env file : {deployment.env_file}")
    print(f"  project  : {deployment.compose_project}")
    print(f"  backend  : {deployment.backend_url}")
    print(f"  storage  : {deployment.storage.describe()}")
    print(f"\nStart it with:  python scripts/start_all.py --deployment {deployment.name}")
    return deployment


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


def print_readiness_checks(deployment: "deployments.Deployment | None" = None) -> None:
    checks = READINESS_CHECKS if deployment is None else readiness_checks(deployment)
    print("\nReadiness checks:")
    for label, url in checks:
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
    callback_name: str,
    cwd: Path | None = None,
    runner_override: str | None = None,
    *,
    compose_project: str | None = None,
    compose_env_file: str | None = None,
) -> list[str]:
    script_path = str(ROOT / "scripts" / "dev.py")
    if callback_name == "compose_up":
        project_literal = repr(compose_project) if compose_project is not None else "None"
        env_file_literal = (
            repr(compose_env_file) if compose_env_file is not None else "'.env.example'"
        )
        callback = f"module.compose_up(project={project_literal}, env_file={env_file_literal})"
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


def start_process(
    label: str,
    command: Sequence[str],
    cwd: Path,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.Popen[str]:
    print(f"Starting {label}: {' '.join(command)}")
    dev_module = load_dev_module()
    env = dev_module.command_env(extra_env)
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


def ensure_default_plugins(status: StatusLine, backend_url: str = COMPOSE_BACKEND_URL) -> None:
    """Best-effort: install/enable the default Official Plugins if not already present.

    Never fatal to startup — a failure here (e.g. Docker networking hiccup,
    a seed account with a locally-changed password) is reported and skipped
    rather than blocking the rest of the stack from coming up.
    """
    status.spin("Checking Official Plugins...")
    try:
        seed = load_seed_plugins_module()
        token = seed.ensure_admin_session(backend_url)
        headers = {"Authorization": f"Bearer {token}"}
        installed_ids = seed.list_installed_plugin_ids(backend_url, headers)
        pending = [
            p
            for p in seed.DEFAULT_PLUGINS
            if json.loads((p["dir"] / "openpdm-plugin.json").read_text(encoding="utf-8"))["id"]
            not in installed_ids
        ]
        if pending:
            status.info(f"Installing {len(pending)} default Official Plugin(s)...")
        for plugin in seed.DEFAULT_PLUGINS:
            seed.seed_plugin(backend_url, headers, plugin, installed_ids)
        status.ok(f"Official Plugins ready ({len(seed.DEFAULT_PLUGINS)} enabled).")
    except Exception as exc:  # noqa: BLE001 - best-effort convenience step, never fatal
        status.warn(f"Official Plugins check skipped: {exc}")


def main() -> int:
    args = parse_args()

    if args.list_deployments:
        print_deployment_list()
        return 0

    if args.new_deployment:
        try:
            prompt_new_deployment()
        except deployments.DeploymentError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.", file=sys.stderr)
            return 1
        return 0

    try:
        deployment = deployments.load(args.deployment)
    except deployments.DeploymentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.gui:
        spec = importlib.util.spec_from_file_location(
            "openpdm_launcher_gui", ROOT / "scripts" / "launcher_gui.py"
        )
        if spec is None or spec.loader is None:
            print("Unable to load scripts/launcher_gui.py", file=sys.stderr)
            return 1
        module = _load_module_from_spec(spec)
        return module.main(
            debug=args.debug,
            check_interval=args.check_interval,
            deployment_name=args.deployment,
        )

    if args.skip_compose and args.skip_frontend:
        print(
            "Nothing to start; both --skip-compose and --skip-frontend were provided.",
            file=sys.stderr,
        )
        return 2

    compose_project = None if deployment.is_default else deployment.compose_project
    compose_env_file = None if deployment.is_default else str(deployment.env_file)
    env_file_display = ".env.example" if deployment.is_default else str(deployment.env_file)
    backend_url = deployment.backend_url
    frontend_url = deployment.frontend_url
    frontend_env = (
        None
        if deployment.is_default
        else {
            "VITE_API_PROXY_TARGET": deployment.frontend_proxy_target,
            "VITE_DEV_PORT": str(deployment.frontend_host_port),
        }
    )

    print_prerequisite_warnings()
    frontend_command, frontend_available = resolve_frontend_runner()

    if not deployment.is_default:
        print(f"Deployment: {deployment.name}  (project {deployment.compose_project})")
        print(f"  storage: {deployment.storage.describe()}")

    if args.dry_run:
        if not args.skip_compose:
            print("Compose stack:")
            project_bit = "" if compose_project is None else f"-p {compose_project} "
            print(
                f"  docker compose {project_bit}--env-file {env_file_display} "
                "-f deployment/compose.yaml up --build"
            )
        if not args.skip_frontend:
            print("Frontend:")
            print(f"  {' '.join(frontend_command)} (cwd: frontend)")
            for key, value in (frontend_env or {}).items():
                print(f"  {key}={value}")
            if not frontend_available:
                print(
                    "  Warning: pnpm/npm was not found on PATH; install Node.js tooling before starting the frontend."
                )
        print_readiness_checks(deployment)
        return 0

    status = StatusLine()
    processes: list[tuple[str, subprocess.Popen[str]]] = []
    try:
        if not args.skip_compose:
            service_states = get_compose_service_states(compose_project)
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
                            build_dev_helper_command(
                                "compose_up",
                                compose_project=compose_project,
                                compose_env_file=compose_env_file,
                            ),
                            ROOT,
                        ),
                    )
                )

            ok = wait_for_backend(f"{backend_url}/health", timeout=300, status=status)
            if not ok:
                raise RuntimeError("Backend did not become healthy within timeout")
            status.ok("Backend is healthy.")

            if not args.skip_plugins:
                ensure_default_plugins(status, backend_url)

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
                            extra_env=frontend_env,
                        ),
                    )
                )

        print("\nOpenPDM services are running.")
        print(f"- Backend/API: {backend_url}")
        if frontend_available and not args.skip_frontend:
            print(f"- Frontend dev server: {frontend_url}")
        elif not args.skip_frontend:
            print("- Frontend dev server: not started (pnpm/npm unavailable)")
        print_readiness_checks(deployment)
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
