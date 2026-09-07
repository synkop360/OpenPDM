#!/usr/bin/env python3
"""Named local deployments for the OpenPDM launcher.

A *deployment* is one isolated Compose stack: its own Compose project name (so
its containers, network and volumes never collide with another stack), its own
published host ports, and its own blob storage target. Running work lives on one
deployment; throwaway or test work lives on another, and neither can touch the
other's database or blobs.

Each deployment is described by an env file under ``deployments/<name>.env``
(git-ignored). ``docker compose --env-file`` reads it for ``${...}`` interpolation
in ``deployment/compose.yaml``. The built-in ``default`` deployment keeps the
historical behaviour exactly: project ``deployment``, ports 18000/5432/9000/9001,
and ``.env.example`` as its env file.

Standard library only, so it packages with the GUI under PyInstaller.
"""

from __future__ import annotations

import re
import socket
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
DEPLOYMENTS_DIR = ROOT / "deployments"
DEFAULT_ENV_FILE = ROOT / ".env.example"

DEFAULT_NAME = "default"
DEFAULT_COMPOSE_PROJECT = "deployment"

# Preferred first port for each published service. A new deployment starts its
# search one block (PORT_STRIDE) above the highest block already taken.
PORT_BASES = {
    "backend": 18000,
    "frontend": 5173,
    "pg": 5432,
    "minio": 9000,
    "minio_console": 9001,
}
PORT_STRIDE = 10

StorageKind = Literal["bundled", "s3", "local"]

_SLUG_RE = re.compile(r"[^a-z0-9]+")
_VALID_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")


class DeploymentError(RuntimeError):
    """A deployment could not be created, loaded or resolved."""


def slugify(raw: str) -> str:
    """Normalise a free-text deployment name to a safe slug.

    Lowercases, collapses any run of non-alphanumerics to a single hyphen, and
    trims leading/trailing hyphens. Raises :class:`DeploymentError` if nothing
    usable is left or the result is the reserved ``default`` name.
    """
    slug = _SLUG_RE.sub("-", raw.strip().lower()).strip("-")
    if not slug or not _VALID_SLUG_RE.match(slug):
        raise DeploymentError(
            f"{raw!r} is not a usable deployment name: use 3-40 characters, "
            "letters, digits and hyphens."
        )
    if slug == DEFAULT_NAME:
        raise DeploymentError("'default' is reserved for the built-in deployment.")
    return slug


@dataclass(frozen=True)
class StorageConfig:
    """Where one deployment's Blob content lives."""

    kind: StorageKind
    endpoint_url: str = "http://minio:9000"
    bucket: str = "openpdm-blobs"
    access_key: str = "openpdm"
    secret_key: str = "openpdm-secret"
    region: str = "us-east-1"
    # Compose volume source for ``kind == "local"``: a named volume, or an
    # absolute host path to bind-mount. Ignored for the other kinds.
    local_source: str = "openpdm-blobs-data"

    def describe(self) -> str:
        if self.kind == "bundled":
            return "bundled MinIO (this deployment's own container)"
        if self.kind == "s3":
            return f"external S3 - {self.endpoint_url} (bucket {self.bucket})"
        return f"local filesystem - {self.local_source}"

    def env_pairs(self) -> dict[str, str]:
        pairs = {
            "OPENPDM_S3_ENDPOINT_URL": self.endpoint_url,
            "OPENPDM_S3_BUCKET": self.bucket,
            "OPENPDM_S3_ACCESS_KEY": self.access_key,
            "OPENPDM_S3_SECRET_KEY": self.secret_key,
            "AWS_DEFAULT_REGION": self.region,
        }
        if self.kind == "local":
            pairs["OPENPDM_S3_ENDPOINT_URL"] = "file:///var/lib/openpdm/blobs"
            pairs["OPENPDM_BLOB_LOCAL_SOURCE"] = self.local_source
        return pairs


@dataclass(frozen=True)
class Deployment:
    """One isolated local Compose stack."""

    name: str
    env_file: Path
    compose_project: str
    backend_host_port: int
    frontend_host_port: int
    pg_host_port: int
    minio_host_port: int
    minio_console_host_port: int
    storage: StorageConfig

    @property
    def is_default(self) -> bool:
        return self.name == DEFAULT_NAME

    @property
    def backend_url(self) -> str:
        return f"http://localhost:{self.backend_host_port}"

    @property
    def frontend_url(self) -> str:
        return f"http://localhost:{self.frontend_host_port}"

    @property
    def frontend_proxy_target(self) -> str:
        return f"http://localhost:{self.backend_host_port}"

    def compose_base_args(self) -> list[str]:
        """The ``docker compose`` args that target this deployment's stack."""
        args = ["-p", self.compose_project] if not self.is_default else []
        return [*args, "--env-file", str(self.env_file), "-f", "deployment/compose.yaml"]


def default_deployment() -> Deployment:
    return Deployment(
        name=DEFAULT_NAME,
        env_file=DEFAULT_ENV_FILE,
        compose_project=DEFAULT_COMPOSE_PROJECT,
        backend_host_port=PORT_BASES["backend"],
        frontend_host_port=PORT_BASES["frontend"],
        pg_host_port=PORT_BASES["pg"],
        minio_host_port=PORT_BASES["minio"],
        minio_console_host_port=PORT_BASES["minio_console"],
        storage=StorageConfig(kind="bundled"),
    )


def _is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def find_free_port(preferred: int, *, reserved: set[int] | None = None) -> int:
    """First free TCP port at or above ``preferred`` not in ``reserved``."""
    reserved = reserved or set()
    port = preferred
    while port < 65536:
        if port not in reserved and _is_port_free(port):
            return port
        port += 1
    raise DeploymentError(f"no free port found at or above {preferred}")


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def list_deployment_names() -> list[str]:
    if not DEPLOYMENTS_DIR.is_dir():
        return []
    names = [
        path.stem
        for path in sorted(DEPLOYMENTS_DIR.glob("*.env"))
        if path.stem not in {"example", DEFAULT_NAME}
    ]
    return names


def load(name: str) -> Deployment:
    """Resolve a deployment by name. ``default`` is the built-in; anything else
    must have a ``deployments/<name>.env`` file."""
    if name == DEFAULT_NAME:
        return default_deployment()

    env_file = DEPLOYMENTS_DIR / f"{name}.env"
    if not env_file.is_file():
        known = ", ".join([DEFAULT_NAME, *list_deployment_names()]) or DEFAULT_NAME
        raise DeploymentError(f"unknown deployment {name!r}; known deployments: {known}")

    values = _parse_env_file(env_file)

    def _port(key: str, base_key: str) -> int:
        raw = values.get(key)
        if raw is None:
            # Derive from the backend port's block so an env file written before
            # this key existed still gets a per-deployment, non-default port.
            backend_raw = values.get("OPENPDM_BACKEND_HOST_PORT")
            if backend_raw and backend_raw.isdigit():
                block = (int(backend_raw) - PORT_BASES["backend"]) // PORT_STRIDE
                return PORT_BASES[base_key] + block * PORT_STRIDE
            return PORT_BASES[base_key]
        try:
            return int(raw)
        except ValueError as exc:
            raise DeploymentError(f"{env_file}: {key}={raw!r} is not an integer") from exc

    kind: StorageKind = values.get("OPENPDM_DEPLOYMENT_STORAGE_KIND", "bundled")  # type: ignore[assignment]
    if kind not in ("bundled", "s3", "local"):
        raise DeploymentError(f"{env_file}: unknown storage kind {kind!r}")
    storage = StorageConfig(
        kind=kind,
        endpoint_url=values.get("OPENPDM_S3_ENDPOINT_URL", "http://minio:9000"),
        bucket=values.get("OPENPDM_S3_BUCKET", "openpdm-blobs"),
        access_key=values.get("OPENPDM_S3_ACCESS_KEY", "openpdm"),
        secret_key=values.get("OPENPDM_S3_SECRET_KEY", "openpdm-secret"),
        region=values.get("AWS_DEFAULT_REGION", "us-east-1"),
        local_source=values.get("OPENPDM_BLOB_LOCAL_SOURCE", "openpdm-blobs-data"),
    )

    return Deployment(
        name=name,
        env_file=env_file,
        compose_project=values.get("OPENPDM_DEPLOYMENT_PROJECT", f"openpdm-{name}"),
        backend_host_port=_port("OPENPDM_BACKEND_HOST_PORT", "backend"),
        frontend_host_port=_port("OPENPDM_FRONTEND_HOST_PORT", "frontend"),
        pg_host_port=_port("OPENPDM_PG_HOST_PORT", "pg"),
        minio_host_port=_port("OPENPDM_MINIO_HOST_PORT", "minio"),
        minio_console_host_port=_port("OPENPDM_MINIO_CONSOLE_HOST_PORT", "minio_console"),
        storage=storage,
    )


def _allocate_ports() -> dict[str, int]:
    """Pick a free, non-overlapping port block above every existing deployment."""
    taken_blocks = 1  # the default deployment occupies block 0
    for name in list_deployment_names():
        try:
            existing = load(name)
        except DeploymentError:
            continue
        block = (existing.backend_host_port - PORT_BASES["backend"]) // PORT_STRIDE
        taken_blocks = max(taken_blocks, block + 1)

    reserved: set[int] = set()
    ports: dict[str, int] = {}
    for key, base in PORT_BASES.items():
        preferred = base + taken_blocks * PORT_STRIDE
        chosen = find_free_port(preferred, reserved=reserved)
        reserved.add(chosen)
        ports[key] = chosen
    return ports


def render_env_file(deployment: Deployment) -> str:
    """The full text of ``deployments/<name>.env`` for a created deployment."""
    lines = [
        f'# OpenPDM deployment "{deployment.name}" - generated by scripts/deployments.py',
        f"# Storage: {deployment.storage.describe()}",
        "# Git-ignored. Safe to edit by hand; keep the port values non-overlapping.",
        "",
        f"OPENPDM_DEPLOYMENT_NAME={deployment.name}",
        f"OPENPDM_DEPLOYMENT_PROJECT={deployment.compose_project}",
        f"OPENPDM_DEPLOYMENT_STORAGE_KIND={deployment.storage.kind}",
        "",
        f"OPENPDM_BACKEND_HOST_PORT={deployment.backend_host_port}",
        f"OPENPDM_FRONTEND_HOST_PORT={deployment.frontend_host_port}",
        f"OPENPDM_PG_HOST_PORT={deployment.pg_host_port}",
        f"OPENPDM_MINIO_HOST_PORT={deployment.minio_host_port}",
        f"OPENPDM_MINIO_CONSOLE_HOST_PORT={deployment.minio_console_host_port}",
        "",
    ]
    for key, value in deployment.storage.env_pairs().items():
        lines.append(f"{key}={value}")
    lines += [
        "",
        "POSTGRES_DB=openpdm",
        "POSTGRES_USER=openpdm",
        "POSTGRES_PASSWORD=openpdm",
        "MINIO_ROOT_USER=openpdm",
        "MINIO_ROOT_PASSWORD=openpdm-secret",
        "",
    ]
    return "\n".join(lines)


def create(name: str, storage: StorageConfig, *, overwrite: bool = False) -> Deployment:
    """Allocate ports, render ``deployments/<name>.env`` and return the deployment."""
    slug = slugify(name)
    env_file = DEPLOYMENTS_DIR / f"{slug}.env"
    if env_file.exists() and not overwrite:
        raise DeploymentError(f"deployment {slug!r} already exists ({env_file}); pass overwrite")

    # Give a local-storage deployment its own volume by default, never the
    # shared fallback name, so two local deployments cannot share a volume.
    if storage.kind == "local" and storage.local_source in ("", "openpdm-blobs-data"):
        storage = replace(storage, local_source=f"openpdm-{slug}-blobs")

    ports = _allocate_ports()
    deployment = Deployment(
        name=slug,
        env_file=env_file,
        compose_project=f"openpdm-{slug}",
        backend_host_port=ports["backend"],
        frontend_host_port=ports["frontend"],
        pg_host_port=ports["pg"],
        minio_host_port=ports["minio"],
        minio_console_host_port=ports["minio_console"],
        storage=storage,
    )
    DEPLOYMENTS_DIR.mkdir(parents=True, exist_ok=True)
    env_file.write_text(render_env_file(deployment), encoding="utf-8")
    return deployment
