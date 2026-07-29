# ADR-0048 - Accept Provider Analysis Contributions

**Status:** Proposed

---

# Context

An analysis provider needs to return generic results without directly writing
Metadata, References, or Relationships. ADR-0031 distinguishes generic
References from Relationships, ADR-0039 requires provider mutations to be
authorized and applied by their owning Platform Modules, and ADR-0034 requires
the Platform Core to treat plugin output as untrusted data.

The result contract must support retries and repeated analysis invocations
without creating duplicate generic records. It must also prevent a provider from
using a Relationship Contribution to create an Asset Graph edge outside the
authorized Project scope.

---

# Decision

An Analysis Provider may return Metadata Contributions, Reference Contributions,
and Relationship Contributions. Every contribution carries a provider-owned,
stable `contribution_key`. The owning Metadata and Relationships Platform
Modules authorize, validate and idempotently persist the contribution. A
Relationship Contribution is valid only when its source is the analyzed
Representation's owning Engineering Asset and its target is an existing
Engineering Asset the actor may access in the same Project.

The Platform Core treats contribution payloads as generic data and does not
interpret provider-specific engineering meaning. A `contribution_key` is stable
for the provider's logical contribution and is used by the owning Platform
Module to make retries idempotent. Reference Contributions remain generic
References under ADR-0031 and do not become Asset Graph edges unless submitted
as valid Relationship Contributions.

---

# Consequences

## Positive

* Analysis results use the existing Metadata and Relationships Platform Module
  ownership boundaries.
* Stable contribution keys make repeated provider invocations safe to retry.
* Relationship validation preserves Project scope, actor authorization, and the
  integrity of the Asset Graph.
* The Platform Core stores generic contributions without acquiring engineering
  semantics.

## Trade-offs

* Providers must define and preserve stable contribution keys.
* Invalid, inaccessible, or cross-Project relationship targets are rejected.
* Richer contribution lifecycle semantics, such as removal or reconciliation,
  require a future ADR.

---

# Alternatives Considered

## Direct writes to Metadata or Relationships persistence

Rejected because plugins must not access Platform Module internals or bypass
their validation and authorization responsibilities.

## Provider-defined idempotency rules

Rejected because consistent persistence behavior must be enforced by the owning
Platform Modules rather than delegated to untrusted plugins.

## Allow a relationship source or target outside the analyzed Asset and Project

Rejected because it would allow an analysis invocation to create unrelated or
unauthorized Asset Graph edges.

---

# References

* ADR-0001 - Adopt a Modular Monolith Architecture
* ADR-0002 - Define Platform Boundaries
* ADR-0031 - Generic References Scope
* ADR-0034 - Execute Untrusted Plugins in a WebAssembly Sandbox
* ADR-0036 - Version the Extension API by Major Contract
* ADR-0039 - Expose Capability-Scoped Providers and Event Hooks
* ADR-0040 - Discover Providers and Expose Declarative Options

---

# Review

Reconsider this decision if generic contribution deletion, reconciliation,
cross-Project workflows, or new contribution categories require a separately
versioned Extension API contract.
