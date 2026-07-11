"""Deny-by-default Wasmtime Component sandbox executed inside the worker process."""

from __future__ import annotations

from dataclasses import dataclass

import wasmtime
from wasmtime.component import Component, Linker


@dataclass(frozen=True, slots=True)
class SandboxLimits:
    fuel: int = 1_000_000
    memory_bytes: int = 64 * 1024 * 1024
    table_elements: int = 10_000
    instances: int = 10
    tables: int = 10
    memories: int = 4


class WasmtimeSandbox:
    """Instantiate one component in one fresh Store with no WASI capabilities."""

    def __init__(self, limits: SandboxLimits | None = None) -> None:
        self.limits = limits or SandboxLimits()
        config = wasmtime.Config()
        config.consume_fuel = True
        config.epoch_interruption = True
        config.wasm_component_model = True
        self.engine = wasmtime.Engine(config)

    def invoke(self, component_bytes: bytes, export_name: str) -> None:
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
        exported = instance.get_func(store, export_name)
        if exported is None:
            raise ValueError(f"Component does not export {export_name!r}.")
        result = exported(store)
        if result is not None:
            raise ValueError(f"Component export {export_name!r} must not return a value.")
