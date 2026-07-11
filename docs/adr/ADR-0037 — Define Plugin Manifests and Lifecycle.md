# ADR-0037 — Define Plugin Manifests and Lifecycle

**Status:** Accepted

---

# Context

The Phase 1 registry records only basic metadata and enabled state. Executable plugins require stable identity, validated capabilities and deterministic lifecycle transitions.

---

# Decision

OpenPDM will identify plugins by a reverse-domain string and describe them with an `openpdm-plugin.json` manifest included in the package.

The manifest requires `id`, `name`, `version`, `extension_api_versions`, `component`, `capabilities` and optional configuration schema metadata. `component` identifies the WebAssembly Component inside the immutable package. Native entry points and executable scripts are forbidden. Plugin identifiers are immutable. Versions use semantic `major.minor.patch` form.

The lifecycle states are `discovered`, `installed`, `disabled`, `starting`, `running`, `failed` and `incompatible`. Only Platform Administrators initiate installation, upgrade, enable, disable and removal. Runtime transitions are owned by the Plugins Platform Module through its public interface.

Phase 4 does not support plugin-to-plugin dependencies. Plugins may depend only on the Extension API. Upgrade replaces one installed version after compatibility and manifest validation; rollback requires reinstalling the previous package.

Lifecycle state, diagnostic reason and timestamps are persisted. Every administrative transition and runtime failure is audited and emits a domain event without exposing secrets.

---

# Consequences

## Positive

* Plugin identity and lifecycle are deterministic.
* Dependency cycles and implementation coupling are excluded.
* Incompatible packages are visible without being executed.

## Trade-offs

* Plugin dependencies and automatic rollback are deferred.
* Package installation remains an explicit administrative operation.

These trade-offs are acceptable because Phase 4 prioritizes a small, observable lifecycle.

---

# Alternatives Considered

## Plugin-to-plugin dependencies

Rejected because plugins must not depend on another plugin's implementation and dependency resolution would broaden Phase 4 substantially.

## Enabled boolean only

Rejected because it cannot represent startup, incompatibility or failure diagnostics.

---

# Review

Reconsider this decision if independently versioned shared extension contracts or transactional rollback become demonstrated ecosystem needs.
