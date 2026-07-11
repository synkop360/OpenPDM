# ADR-0039 — Expose Capability-Scoped Providers and Event Hooks

**Status:** Proposed

---

# Context

Phase 4 requires Asset Providers, Metadata Providers and event hooks without allowing plugins to bypass authorization, interpret Platform Module internals or introduce engineering semantics into the Platform Core.

---

# Decision

Extension API v1 will expose three capability-scoped contracts: `asset_provider`, `metadata_provider` and `event_handler`.

Asset Providers submit commands using the generic Asset, Revision, Representation and Blob vocabulary. The Platform Core validates authorization and performs mutations through the owning Platform Module public interfaces. Plugins never receive persistence objects or repositories.

Metadata Providers return generic key, value, value type and source entries. The Platform Core validates the generic shape but does not interpret engineering meaning.

Event handlers subscribe in the manifest to an allowlist of documented domain event types. Delivery is asynchronous after the originating transaction commits, ordered per plugin, at least once, and retried three times with bounded exponential delay. Handlers must be idempotent. A handler invocation has a configurable platform-owned timeout capped at thirty seconds. Exhausted deliveries are recorded as failed without rolling back the originating business action.

Every request carries actor, Organization and Project context where applicable. The Platform Core reauthorizes every plugin-initiated command. Plugins cannot manufacture authority from event payloads. Provider mutations and delivery failures are audited.

Phase 4 excludes CAD parsing semantics, automatic relationship interpretation and plugin-defined authorization rules.

---

# Consequences

## Positive

* Useful extension behavior is available through narrow contracts.
* Platform Modules retain ownership of validation and mutations.
* Event failures do not corrupt committed business transactions.
* At-least-once delivery has an explicit idempotency requirement.

## Trade-offs

* Plugins must handle duplicate events.
* Async processing introduces delivery state and retry operations.
* The initial capability set is intentionally small.

These trade-offs are acceptable because Phase 4 needs reliable extension points without turning the Extension API into a privileged internal API.

---

# Alternatives Considered

## Direct Platform Module access

Rejected because it violates ADR-0002 and would couple plugins to unstable internals.

## Synchronous event handlers inside transactions

Rejected because plugin latency or failure could block and roll back Platform Core business actions.

## Exactly-once delivery

Rejected because it would add disproportionate transactional complexity; idempotent at-least-once handling is explicit and testable.

---

# Review

Reconsider this decision when additional generic capabilities, higher throughput or externally hosted plugin workers are required.
