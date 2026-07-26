from __future__ import annotations

import wasmtime

from openpdm.plugin_runtime.sandbox import SandboxLimits, WasmtimeSandbox
from openpdm.plugin_runtime.supervisor import WasmtimeWorkerSupervisor


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
