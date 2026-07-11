# Plugin Development

OpenPDM Phase 4 plugins are WebAssembly Components that implement Extension API v1. Official Plugins and Community Plugins use the same manifest, package format, WIT contract, sandbox and public capabilities.

## Contract And Package

The normative WIT world is [`backend/src/openpdm/extension_api/wit/openpdm-extension.wit`](../backend/src/openpdm/extension_api/wit/openpdm-extension.wit). It exports:

* `activate()` for bounded startup validation;
* `invoke(request: string) -> string` for JSON Extension API requests and responses.

An `.openpdm-plugin` package is a ZIP archive containing exactly `openpdm-plugin.json` and the manifest-declared WebAssembly Component.

The SDK validates reverse-domain identity, semantic version, Extension API compatibility, capabilities, event subscriptions and bounded configuration schema. Package validation rejects traversal, nested paths, links, duplicate entries, unexpected files, oversize content and non-component binaries.

## Capabilities

* `asset_provider` returns generic Asset lifecycle commands. The Platform Core reauthorizes and executes them through the Assets public interface.
* `metadata_provider` returns generic metadata for the requested Asset, Revision or Representation. A provider cannot redirect a contribution to another target.
* `event_handler` acknowledges declared, committed domain events. Delivery is ordered per plugin, at least once and retried three times, so handlers must be idempotent.

Plugins never receive database sessions, repositories, Platform Module interfaces, object-storage credentials or ambient host access.

## Reference Official Plugin

The domain-neutral reference source is under `plugins/reference/`. Build it reproducibly:

```bash
uv sync --all-groups
uv run python scripts/build_reference_plugin.py
```

The build compiles the Python source to a WebAssembly Component with `componentize-py`, validates the manifest and emits `plugins/reference/dist/reference.openpdm-plugin`.

The end-to-end test demonstrates the complete journey:

```bash
uv run pytest backend/tests/test_reference_plugin_e2e.py -v
```

## Administrator Journey

1. Register the first local user; an empty deployment bootstraps it as Platform Administrator.
2. Install the package through `POST /plugins/packages`.
3. Configure it through `PUT /plugins/{plugin_id}/configuration`.
4. Enable it through `POST /plugins/{plugin_id}/state`.
5. Inspect lifecycle diagnostics and event deliveries through the corresponding `GET` routes.
6. Invoke approved providers through their public application API routes.

Use `/docs` on a running backend for exact request schemas. The legacy `POST /plugins` route never installs code.

## Compatibility

Phase 4 supports Extension API major version `1`. Additive response fields may be ignored. Incompatible packages remain rejected before activation. Plugins must not depend on another plugin or on internal Platform Core implementation.
