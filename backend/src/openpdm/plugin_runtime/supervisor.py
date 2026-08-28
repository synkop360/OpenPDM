"""Platform-side lifecycle supervisor for the isolated Wasmtime worker."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .worker import PROTOCOL_VERSION


@dataclass(frozen=True, slots=True)
class RuntimeResult:
    success: bool
    diagnostic_reason: str | None = None
    result: str | None = None


def _prepare_cache_config(cache_directory: str | None) -> str | None:
    """Materialize a Wasmtime cache-config file for ``cache_directory``.

    The compiled-artifact cache turns a cold component recompile (seconds, for a
    CPython-based component) into a deserialize (milliseconds), so a first
    ``enable`` or ``analyze`` on a slow host no longer races the wall-clock
    deadline. The config file is kept beside the artifact directory, never
    inside it, because Wasmtime's cache cleanup deletes stray files under the
    cache directory. A path that cannot be created is treated as "no cache".
    """

    if not cache_directory:
        return None
    try:
        base = Path(cache_directory).expanduser().resolve()
        artifacts = base / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        config_path = base / "cache-config.toml"
        desired = f"[cache]\ndirectory = {json.dumps(artifacts.as_posix())}\n"
        if not config_path.is_file() or config_path.read_text(encoding="utf-8") != desired:
            config_path.write_text(desired, encoding="utf-8")
        return str(config_path)
    except OSError:
        return None


class WasmtimeWorkerSupervisor:
    """Execute one bounded invocation through private anonymous pipes."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 5.0,
        fuel: int = 25_000_000,
        memory_bytes: int = 64 * 1024 * 1024,
        cache_directory: str | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.fuel = fuel
        self.memory_bytes = memory_bytes
        self.cache_config_path = _prepare_cache_config(cache_directory)

    def activate(self, component: bytes) -> RuntimeResult:
        return self.invoke(component, export_name="activate")

    def invoke(
        self,
        component: bytes,
        *,
        export_name: str,
        arguments: list[str] | None = None,
        fuel: int | None = None,
    ) -> RuntimeResult:
        request_id = str(uuid4())
        request = json.dumps(
            {
                "protocol_version": PROTOCOL_VERSION,
                "request_id": request_id,
                "component": base64.b64encode(component).decode("ascii"),
                "export_name": export_name,
                "arguments": arguments or [],
                "fuel": self.fuel if fuel is None else fuel,
                "memory_bytes": self.memory_bytes,
                "cache_config_path": self.cache_config_path,
            },
            separators=(",", ":"),
        )
        package_root = str(Path(__file__).resolve().parents[2])
        bootstrap = (
            "import runpy,sys;"
            f"sys.path.insert(0,{package_root!r});"
            "runpy.run_module('openpdm.plugin_runtime.worker',run_name='__main__')"
        )
        command = [sys.executable, "-I", "-c", bootstrap]
        try:
            completed = subprocess.run(
                command,
                input=request + "\n",
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
            return RuntimeResult(False, "Plugin activation exceeded the wall-clock deadline.")
        if len(completed.stdout) > 16 * 1024:
            return RuntimeResult(False, "Plugin runtime response exceeded the size limit.")
        try:
            response = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return RuntimeResult(False, "Plugin runtime returned an invalid response.")
        if (
            response.get("protocol_version") != PROTOCOL_VERSION
            or response.get("request_id") != request_id
        ):
            return RuntimeResult(False, "Plugin runtime response authentication failed.")
        if response.get("success") is True and completed.returncode == 0:
            result = response.get("result")
            if result is not None and not isinstance(result, str):
                return RuntimeResult(False, "Plugin runtime returned an invalid result.")
            return RuntimeResult(True, result=result)
        reason = response.get("error")
        return RuntimeResult(False, str(reason)[:1024] if reason else "Plugin activation failed.")
