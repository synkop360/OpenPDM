from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import wasmtime
from pydantic import ValidationError

from openpdm.plugin_runtime.sandbox import SandboxLimits, WasmtimeSandbox
from openpdm.plugin_runtime.supervisor import WasmtimeWorkerSupervisor, _prepare_cache_config
from openpdm.plugin_runtime.worker import WorkerRequest


def component_bytes(wat: str) -> bytes:
    return bytes(wasmtime.wat2wasm(wat))


SUCCESS_COMPONENT = component_bytes(
    """(component
      (core module $m (func (export "activate")))
      (core instance $i (instantiate $m))
      (func (export "activate") (canon lift (core func $i "activate")))
    )"""
)


def test_sandbox_invokes_component_without_wasi_or_host_capabilities() -> None:
    WasmtimeSandbox().invoke(SUCCESS_COMPONENT, "activate")


def test_sandbox_rejects_unknown_host_imports() -> None:
    hostile = component_bytes('(component (import "host-command" (func)))')
    try:
        WasmtimeSandbox().invoke(hostile, "activate")
    except wasmtime.WasmtimeError as exc:
        assert "host-command" in str(exc)
    else:
        raise AssertionError("Unknown host imports must not be linked.")


def test_sandbox_interrupts_infinite_guest_with_fuel() -> None:
    hostile = component_bytes(
        """(component
          (core module $m (func (export "activate") (loop br 0)))
          (core instance $i (instantiate $m))
          (func (export "activate") (canon lift (core func $i "activate")))
        )"""
    )
    try:
        WasmtimeSandbox(SandboxLimits(fuel=1_000)).invoke(hostile, "activate")
    except wasmtime.WasmtimeError as exc:
        assert "fuel" in str(exc).lower()
    else:
        raise AssertionError("Infinite guest execution must exhaust fuel.")


def test_sandbox_rejects_guest_memory_above_limit() -> None:
    hostile = component_bytes(
        """(component
          (core module $m
            (memory 100)
            (func (export "activate")))
          (core instance $i (instantiate $m))
          (func (export "activate") (canon lift (core func $i "activate")))
        )"""
    )
    try:
        WasmtimeSandbox(SandboxLimits(memory_bytes=64 * 1024)).invoke(hostile, "activate")
    except wasmtime.WasmtimeError as exc:
        assert "memory" in str(exc).lower()
    else:
        raise AssertionError("Guest memory must be bounded.")


def test_supervisor_uses_worker_process_and_authenticates_response() -> None:
    result = WasmtimeWorkerSupervisor(timeout_seconds=5).activate(SUCCESS_COMPONENT)
    assert result.success, result.diagnostic_reason


def test_supervisor_contains_invalid_component_failure() -> None:
    result = WasmtimeWorkerSupervisor(timeout_seconds=5).activate(b"native-code")
    assert result.success is False
    assert result.diagnostic_reason


def test_supervisor_keeps_default_fuel_unless_an_invocation_overrides_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed_fuel: list[int] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        request = json.loads(str(kwargs["input"]))
        observed_fuel.append(request["fuel"])
        response = json.dumps(
            {
                "protocol_version": 1,
                "request_id": request["request_id"],
                "success": True,
                "error": None,
                "result": "ok",
            }
        )
        return subprocess.CompletedProcess(command, 0, stdout=response, stderr="")

    monkeypatch.setattr("openpdm.plugin_runtime.supervisor.subprocess.run", fake_run)
    supervisor = WasmtimeWorkerSupervisor(fuel=25_000_000)

    assert supervisor.invoke(b"component", export_name="invoke").success
    assert supervisor.invoke(b"component", export_name="invoke", fuel=200_000_000).success
    assert observed_fuel == [25_000_000, 200_000_000]


def test_worker_request_rejects_fuel_above_analysis_provider_bound() -> None:
    request = {
        "protocol_version": 1,
        "request_id": "test",
        "component": "component",
        "export_name": "invoke",
        "fuel": 500_000_000,
        "memory_bytes": 64 * 1024 * 1024,
    }
    assert WorkerRequest.model_validate(request).fuel == 500_000_000
    request["fuel"] = 500_000_001
    with pytest.raises(ValidationError):
        WorkerRequest.model_validate(request)


def test_worker_request_carries_optional_cache_config_path() -> None:
    base = {
        "protocol_version": 1,
        "request_id": "test",
        "component": "component",
        "export_name": "invoke",
        "fuel": 25_000_000,
        "memory_bytes": 64 * 1024 * 1024,
    }
    assert WorkerRequest.model_validate(base).cache_config_path is None
    assert (
        WorkerRequest.model_validate(
            {**base, "cache_config_path": "/x/cache.toml"}
        ).cache_config_path
        == "/x/cache.toml"
    )


def test_supervisor_prepares_cache_config_and_sends_its_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    supervisor = WasmtimeWorkerSupervisor(cache_directory=str(tmp_path / "cache"))
    config_path = supervisor.cache_config_path
    assert config_path is not None
    contents = Path(config_path).read_text(encoding="utf-8")
    assert contents.startswith("[cache]")
    assert (tmp_path / "cache" / "artifacts").as_posix() in contents
    # The config file lives beside the artifact directory, never inside it, so
    # Wasmtime's cache cleanup cannot delete it.
    assert Path(config_path).parent == (tmp_path / "cache")

    observed: list[object] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        request = json.loads(str(kwargs["input"]))
        observed.append(request["cache_config_path"])
        response = json.dumps(
            {
                "protocol_version": 1,
                "request_id": request["request_id"],
                "success": True,
                "error": None,
                "result": "ok",
            }
        )
        return subprocess.CompletedProcess(command, 0, stdout=response, stderr="")

    monkeypatch.setattr("openpdm.plugin_runtime.supervisor.subprocess.run", fake_run)
    assert supervisor.invoke(b"component", export_name="invoke").success
    assert observed == [config_path]


def test_supervisor_tolerates_an_unusable_cache_directory(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("regular file", encoding="utf-8")

    assert _prepare_cache_config(str(blocker / "cache")) is None
    assert (
        WasmtimeWorkerSupervisor(cache_directory=str(blocker / "cache")).cache_config_path is None
    )
    assert WasmtimeWorkerSupervisor().cache_config_path is None


def test_sandbox_with_cache_config_still_bounds_fuel(tmp_path: Path) -> None:
    config_path = _prepare_cache_config(str(tmp_path / "cache"))
    assert config_path is not None

    # A warm cache must not weaken the sandbox: an infinite guest still exhausts
    # fuel, and a valid component still runs (twice: cold then warm).
    hostile = component_bytes(
        """(component
          (core module $m (func (export "activate") (loop br 0)))
          (core instance $i (instantiate $m))
          (func (export "activate") (canon lift (core func $i "activate")))
        )"""
    )
    with pytest.raises(wasmtime.WasmtimeError, match="(?i)fuel"):
        WasmtimeSandbox(SandboxLimits(fuel=1_000, cache_config_path=config_path)).invoke(
            hostile, "activate"
        )

    for _ in range(2):
        WasmtimeSandbox(SandboxLimits(cache_config_path=config_path)).invoke(
            SUCCESS_COMPONENT, "activate"
        )


def test_sandbox_ignores_a_malformed_cache_config(tmp_path: Path) -> None:
    broken = tmp_path / "broken.toml"
    broken.write_text("this is not valid cache config", encoding="utf-8")

    WasmtimeSandbox(SandboxLimits(cache_config_path=str(broken))).invoke(
        SUCCESS_COMPONENT, "activate"
    )
