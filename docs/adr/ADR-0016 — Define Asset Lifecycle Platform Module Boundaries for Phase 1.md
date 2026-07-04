# ADR-0016 — Define Asset Lifecycle Platform Module Boundaries for Phase 1

**Status:** Accepted

---

# Context

Phase 1 requires the generic immutable Engineering Asset lifecycle defined by ADR-0003 and Blob storage separation defined by ADR-0006.

The current accepted ADRs define the lifecycle model and the infrastructure choices, but they do not yet define how lifecycle responsibilities are grouped into Platform Modules for implementation inside the modular monolith.

OpenPDM needs a Phase 1 module boundary decision that:

* preserves the Asset, Revision, Representation and Blob separation defined by the architecture;
* keeps binary storage responsibilities separate from business lifecycle responsibilities;
* avoids unnecessary fragmentation of Platform Modules in the Core Platform MVP;
* gives dependent Platform Modules a stable public contract for lifecycle and Blob interactions;
* remains aligned with the rule that Platform Modules communicate only through public interfaces.

---

# Decision

Phase 1 will group the Asset lifecycle into **two Platform Modules**:

* **Assets Platform Module**
* **Blobs Platform Module**

## Assets Platform Module

The Assets Platform Module owns:

* `Asset`
* `Revision`
* `Representation`
* generic lifecycle status primitive

Its public interface is responsible for operations such as:

* create Asset
* create Revision
* add Representation
* get Asset
* get Revision history
* change generic lifecycle status within the approved Phase 1 rules

## Blobs Platform Module

The Blobs Platform Module owns:

* `Blob` records
* Blob storage coordination with S3-compatible infrastructure
* Blob upload and download orchestration

Its public interface is responsible for operations such as:

* register Blob
* store Blob content
* retrieve Blob content
* resolve Blob reference

## Boundary Rules

Phase 1 applies the following module dependency rules:

* the Assets Platform Module owns lifecycle semantics;
* the Blobs Platform Module owns binary storage semantics;
* the Assets Platform Module may depend on the Blobs Platform Module public interface;
* the Blobs Platform Module must not depend on Asset, Revision or Representation business semantics;
* other Platform Modules must use public interfaces only and must not access Assets or Blobs internals.

This decision preserves the lifecycle chain defined by ADR-0003 while keeping Blob handling separate from lifecycle business behavior.

---

# Consequences

## Positive

* Asset lifecycle behavior remains cohesive inside one business-facing Platform Module.
* Blob responsibilities stay separate from business lifecycle semantics, aligned with ADR-0003 and ADR-0006.
* The design avoids premature fragmentation into multiple small lifecycle modules in Phase 1.
* Dependent Platform Modules receive clear public interfaces for lifecycle and Blob interactions.
* The boundary remains compatible with later evolution if extraction or additional specialization becomes necessary.

## Trade-offs

* The Assets Platform Module is broader than a single-concept module, because it groups several tightly related lifecycle concepts.
* Future scaling or specialization may require additional sub-boundaries later.
* Blob coordination errors between business records and object storage still require careful implementation.

These trade-offs are acceptable because OpenPDM currently prioritizes cohesive lifecycle ownership and simple Phase 1 boundaries over finer-grained module decomposition.

---

# Alternatives Considered

## Separate Platform Modules for Asset, Revision and Representation

Rejected because it would introduce extra coordination complexity in Phase 1 without enough architectural benefit for the Core Platform MVP.

## Single Lifecycle and Blob Module

Rejected because it would blur the architectural separation between business lifecycle concepts and binary storage handling.

## Blob Handling Only as Infrastructure with No Platform Module Boundary

Rejected because Blob records and Blob coordination are part of the Platform Core business model and need an explicit public contract, even though storage uses replaceable infrastructure.

---

# Review

This decision should be revisited if OpenPDM later needs finer-grained lifecycle module extraction, materially different Blob coordination behavior or operational boundaries that justify additional module separation.
