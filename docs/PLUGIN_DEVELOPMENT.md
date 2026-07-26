# Plugin Development

OpenPDM Phase 4 plugins are WebAssembly Components that implement Extension API v1. Official Plugins and Community Plugins use the same manifest, package format, WIT contract, sandbox and public capabilities.

## Contract And Package

The normative WIT world is [`backend/src/openpdm/extension_api/wit/openpdm-extension.wit`](../backend/src/openpdm/extension_api/wit/openpdm-extension.wit). It exports:

* `activate()` for bounded startup validation;
* `invoke(request: string) -> string` for JSON Extension API requests and responses.

An `.openpdm-plugin` package is a ZIP archive containing exactly `openpdm-plugin.json` and the manifest-declared WebAssembly Component.

The SDK validates reverse-domain identity, semantic version, Extension API compatibility, capabilities, event subscriptions and bounded configuration schema. Package validation rejects traversal, nested paths, links, duplicate entries, unexpected files, oversize content and non-component binaries.

## Scaffold A Plugin

Create a minimal Community Plugin without copying repository internals:

```bash
uv run python scripts/scaffold_plugin.py ./my-plugin \
  --id org.example.my-plugin \
  --name "My Plugin"
cd my-plugin
uv run python build.py
```

The scaffold validates the identity and manifest, generates Extension API v1 Python bindings from the published WIT contract, and creates a buildable event-handler project. The generated `plugin.openpdm-plugin` package passes the same validation used during installation. Extend `plugin.py` only through the generated Extension API bindings and declared capabilities.

## Capabilities

* `asset_provider` returns generic Asset lifecycle commands. The Platform Core reauthorizes and executes them through the Assets public interface.
* `metadata_provider` returns generic metadata for the requested Asset, Revision or Representation. A provider cannot redirect a contribution to another target.
* `option_provider` returns bounded, declarative option sets for a named context. Clients render the returned labels and values as untrusted text; plugins cannot inject markup, scripts or executable UI code.
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

For a Community Plugin API example with configurable generic Asset categories, see [`plugins/dummy-categories/`](../plugins/dummy-categories/README.md). It exercises Asset Provider, Metadata Provider, Option Provider and event-hook behavior without adding category semantics to the Platform Core. The Web UI discovers its running providers through `GET /providers`, requests the `asset.category` option context, and submits the selected value as ordinary provider input.

## Administrator Journey

1. Register the first local user; an empty deployment bootstraps it as Platform Administrator.
2. Discover it without making it executable by passing `discover_only=true` to `POST /plugins/packages`, then promote it through `POST /plugins/{plugin_id}/install`; or install it directly with the default `discover_only=false`.
3. Configure it through `PUT /plugins/{plugin_id}/configuration`.
4. Enable it through `POST /plugins/{plugin_id}/state`.
5. Inspect lifecycle diagnostics and event deliveries through the corresponding `GET` routes.
6. Discover enabled, running public providers through `GET /providers`, then invoke only a returned capability through its public application API route. Option Providers use `POST /plugins/{plugin_id}/providers/options`; Metadata and Asset Providers have separate routes.
7. Upgrade a disabled plugin through `PUT /plugins/{plugin_id}/package`. The package identity must match, configuration is cleared for revalidation, and the replacement remains disabled.
8. Disable and remove a plugin through `DELETE /plugins/{plugin_id}`. Content-addressed package evidence remains in immutable storage.

Use `/docs` on a running backend for exact request schemas. The legacy `POST /plugins` route never installs code.

Validated packages must remain available at `OPENPDM_PLUGIN_PACKAGE_ROOT`. Docker Compose mounts the persistent `plugin-packages` volume at this location. If a lifecycle record exists but its approved package is missing, invocation fails with `409 Conflict`; restore the exact package or reinstall/upgrade it through the authenticated lifecycle API rather than placing unverified files into storage.

## Compatibility

Phase 4 supports Extension API major version `1`. Additive response fields may be ignored. Incompatible packages remain rejected before activation. Plugins must not depend on another plugin or on internal Platform Core implementation.

An incompatible structurally valid package is retained with `incompatible` lifecycle state and an actionable diagnostic. It cannot be enabled. Invalid archives are rejected without creating a lifecycle record.
