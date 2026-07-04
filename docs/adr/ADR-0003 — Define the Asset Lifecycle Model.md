# ADR-0003 — Define the Asset Lifecycle Model

**Status:** Accepted

---

# Context

The Platform Core manages engineering information independently of engineering domains.

An engineering object may evolve over time, exist in multiple formats and generate derived representations.

The architecture therefore requires a generic lifecycle model capable of representing these concepts without introducing engineering-specific semantics.

---

# Decision

Every engineering object managed by OpenPDM follows the same immutable lifecycle.

```text
Asset
   │
   ▼
Revision
   │
   ▼
Representation(s)
   │
   ▼
Blob(s)
```

## Asset

Represents the identity of an engineering object.

An Asset is persistent and independent of its binary contents.

---

## Revision

Represents an immutable state of an Asset.

Every modification creates a new Revision.

Existing Revisions are never modified.

---

## Representation

Represents a technical view of a Revision.

Examples include:

* Native CAD file
* STEP export
* STL export
* Drawing
* PDF
* Preview image

A Revision may own multiple Representations.

---

## Blob

Represents the binary content stored by the platform.

A Blob contains no business semantics.

It is managed independently from the Asset model.

---

# Consequences

## Positive

* Stable and generic data model.
* Complete separation between business concepts and binary storage.
* Support for multiple representations of the same engineering object.
* Future-proof foundation for additional engineering domains.

## Trade-offs

* Additional abstraction compared to a direct Asset-to-Blob relationship.
* Slightly more complex persistence model.

These trade-offs are accepted because they significantly improve extensibility while preserving a domain-agnostic Platform Core.
