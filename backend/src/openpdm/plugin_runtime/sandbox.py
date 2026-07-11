"""Deny-by-default Wasmtime Component sandbox executed inside the worker process."""

from __future__ import annotations

from dataclasses import dataclass

import wasmtime
from wasmtime.component import Component, Linker


@dataclass(frozen=True, slots=True)
class SandboxLimits:
    fuel: int = 25_000_000
    memory_bytes: int = 64 * 1024 * 1024
    table_elements: int = 10_000
    instances: int = 100
    tables: int = 100
    memories: int = 100


class WasmtimeSandbox:
    """Instantiate one component in one fresh Store with no WASI capabilities."""

    def __init__(self, limits: SandboxLimits | None = None) -> None:
        self.limits = limits or SandboxLimits()
        config = wasmtime.Config()
        config.consume_fuel = True
        config.epoch_interruption = True
        config.wasm_component_model = True
        self.engine = wasmtime.Engine(config)

    def invoke(
        self, component_bytes: bytes, export_name: str, arguments: list[str] | None = None
    ) -> str | None:
        if not export_name or len(export_name) > 128:
            raise ValueError("Invalid component export name.")
        component = Component(self.engine, component_bytes)
        store = wasmtime.Store(self.engine)
        store.set_fuel(self.limits.fuel)
        store.set_limits(
            memory_size=self.limits.memory_bytes,
            table_elements=self.limits.table_elements,
            instances=self.limits.instances,
            tables=self.limits.tables,
            memories=self.limits.memories,
        )
        store.set_epoch_deadline(1)
        linker = Linker(self.engine)
        instance = linker.instantiate(store, component)
        if export_name != "activate":
            activate = instance.get_func(store, "activate")
            if activate is None:
                raise ValueError("Component does not export 'activate'.")
            if activate(store) is not None:
                raise ValueError("Component export 'activate' must not return a value.")
        exported = instance.get_func(store, export_name)
        if exported is None:
            raise ValueError(f"Component does not export {export_name!r}.")
        result = exported(store, *(arguments or []))
        if result is not None and not isinstance(result, str):
            raise ValueError(f"Component export {export_name!r} returned an unsupported value.")
        if isinstance(result, str) and len(result.encode()) > 1024 * 1024:
            raise ValueError(f"Component export {export_name!r} exceeded the result size limit.")
        return result
