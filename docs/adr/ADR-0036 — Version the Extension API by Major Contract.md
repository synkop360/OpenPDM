# ADR-0036 — Version the Extension API by Major Contract

**Status:** Accepted

---

# Context

The Extension API is stable, versioned and documented under ADR-0002. Phase 4 needs a compatibility rule that allows the Platform Core and plugins to evolve without loading incompatible code.

---

# Decision

OpenPDM will publish **Extension API v1** and version the contract by integer major version.

Each plugin manifest declares one or more supported major versions. The Phase 4 runtime supports major version `1` and rejects activation when no declared version intersects the runtime's supported versions.

Additive fields and operations may be introduced within a major version. Consumers must ignore unknown response fields. Removing or changing documented behavior requires a new major version and an ADR. Deprecated v1 behavior remains supported for at least one subsequent OpenPDM minor release after deprecation is documented.

The SDK exposes the same contract types and protocol schemas. Contract fixtures and compatibility tests are normative; SDK convenience APIs are not an alternative extension boundary.

---

# Consequences

## Positive

* Compatibility is checked before plugin execution.
* Additive evolution does not require a new API major version.
* Public fixtures can test Official Plugins and Community Plugins equally.

## Trade-offs

* Multiple major versions may eventually need concurrent support.
* Maintainers must distinguish contract changes from SDK implementation changes.

These trade-offs are acceptable because explicit compatibility is necessary for a durable plugin ecosystem.

---

# Alternatives Considered

## Match OpenPDM application versions

Rejected because it would couple plugins to unrelated application releases.

## Unversioned capability detection

Rejected because it cannot communicate incompatible semantic changes reliably.

---

# Review

Reconsider this decision if concurrent major-version support becomes operationally prohibitive or the protocol requires finer compatibility negotiation.
