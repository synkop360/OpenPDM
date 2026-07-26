# ADR-0028 — Relationship Module Ownership and Boundaries

**Status:** Accepted

---

# Context

Phase 3 introduces generic Asset relationships into the modular monolith.

The current accepted ADRs define:

* the modular monolith architecture;
* Platform boundaries;
* Organization and Project module boundaries;
* Asset lifecycle module boundaries.

However, they do not yet define which Platform Module owns relationship responsibilities or how other Platform Modules must interact with relationship behavior.

OpenPDM needs a Phase 3 module boundary decision that:

* preserves the Asset Graph as a first-class Platform Core capability;
* keeps relationship business behavior cohesive;
* prevents other modules or plugins from bypassing relationship rules;
* supports future traversal behavior without coupling graph logic to unrelated modules.

---

# Decision

OpenPDM will use a dedicated **Relationships Platform Module** for Phase 3.

The Relationships Platform Module owns:

* relationship persistence;
* relationship validation;
* relationship traversal primitives;
* reference persistence and validation;
* relationship and reference event emission.

## Responsibilities

Its public interface is responsible for operations such as:

* create relationship;
* delete relationship;
* list relationships;
* validate relationship endpoints;
* prevent invalid self-relationships where required;
* create and delete references;
* provide graph traversal primitives for approved Phase 3 queries.

## Explicit non-responsibilities

The Relationships Platform Module does **not** perform:

* CAD dependency extraction;
* BOM interpretation;
* workflow decisions;
* plugin-specific semantics;
* automatic relationship creation from uploaded files in Phase 3.

## Boundary rules

Phase 3 applies the following dependency rules:

* the Relationships Platform Module may depend on the Assets Platform Module public interface to validate Asset endpoints;
* the Assets Platform Module must not own relationship persistence or traversal behavior;
* other Platform Modules must access relationships only through the Relationships Platform Module public interface;
* plugins must not access internal relationship storage or traversal implementation directly.

---

# Consequences

## Positive

* Relationship responsibilities stay cohesive and explicit.
* The Asset Graph gains a clear Platform Module owner.
* Traversal behavior can evolve without leaking into unrelated Platform Modules.
* Plugins and other modules remain aligned with Public Module Interface rules.

## Trade-offs

* Phase 3 introduces an additional Platform Module.
* Relationship operations require explicit coordination with Asset validation and authorization flows.
* Future deeper graph behavior may require further public interface evolution.

These trade-offs are acceptable because OpenPDM currently prioritizes clear module ownership and low coupling over premature consolidation.

---

# Alternatives Considered

## Relationships Inside the Assets Platform Module

Rejected because relationship persistence and traversal would broaden the Assets Platform Module beyond a cohesive lifecycle boundary.

## Relationship Storage as Search or Infrastructure Concern

Rejected because relationships are part of the Platform Core business model, not merely indexing or infrastructure implementation detail.

## Plugin-Owned Relationships

Rejected because the Asset Graph is a Platform Core capability and must not depend on plugin internals.

---

# Review

This decision should be revisited if OpenPDM later requires a materially different graph architecture or operational boundary that justifies further module extraction.
