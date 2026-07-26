# ADR-0010 — Adopt a Generic Key-Value Metadata Model Without Business Semantics

**Status:** Accepted

---

# Context

Phase 1 requires a generic metadata capability so Engineering Assets can be enriched, searched and governed without introducing engineering-domain knowledge into the Platform Core.

The current accepted ADRs define the modular monolith architecture, Platform Module boundaries, the immutable Asset lifecycle, the technology stack and the local-first authentication direction. They do not yet define how metadata is represented inside the Platform Core.

OpenPDM needs an initial metadata model that:

* remains fully domain-agnostic;
* can attach metadata to Asset lifecycle concepts introduced in Phase 1;
* supports multiple primitive and structured value types;
* does not require the Platform Core to understand the meaning of metadata keys or values;
* remains compatible with future plugin-provided engineering intelligence.

Metadata values may look engineering-specific, but the Platform Core must treat them as opaque business-neutral data.

---

# Decision

OpenPDM will adopt a **generic key/value metadata model** for Phase 1 with **no business semantics in the Platform Core**.

Phase 1 metadata will be represented through a `MetadataEntry` concept with the following fields:

* `id`
* `asset_id | revision_id | representation_id`
* `key`
* `value`
* `value_type`
* `source`
* `created_at`

Allowed Phase 1 `value_type` values are:

* `string`
* `number`
* `boolean`
* `date`
* `json`

The Platform Core stores metadata, but it must **never interpret metadata semantics**.

For example:

* `material = "7075-T6"`

The Platform Core may store this value and return it through the public application API, but it must not know what a material is or assign engineering meaning to the key or value.

Metadata may be attached to the generic Asset lifecycle scope introduced in Phase 1:

* Asset
* Revision
* Representation

Metadata semantics, validation rules, engineering meaning and domain-specific interpretation are explicitly deferred to plugins or later decisions.

---

# Consequences

## Positive

* The Platform Core remains domain-agnostic while still supporting rich metadata storage.
* Phase 1 gains a flexible metadata foundation without requiring engineering-specific schema design.
* Future plugins can interpret or produce metadata without forcing the Platform Core to understand engineering domains.
* The model aligns with the immutable Asset lifecycle by allowing metadata attachment at multiple generic lifecycle levels.
* The design supports future search and governance capabilities without embedding engineering semantics in the Platform Core.

## Trade-offs

* The Platform Core cannot validate domain-specific meaning for metadata keys or values.
* Metadata consistency rules across plugins or organizations will require later decisions if needed.
* Search and filtering behavior over metadata still require separate scope decisions.

These trade-offs are acceptable because OpenPDM currently prioritizes a simple, generic Core Platform over early specialization.

---

# Alternatives Considered

## Domain-Specific Metadata in the Platform Core

Rejected because it would make the Platform Core understand engineering concepts and violate the project architecture.

## Metadata Only on Assets

Rejected because Phase 1 needs a model that can attach metadata to multiple lifecycle levels without redesigning the metadata capability immediately.

## Strict Per-Key Schema in Phase 1

Rejected because it would add premature complexity and move business semantics into the Platform Core too early.

---

# Review

This decision should be revisited only if OpenPDM requires stronger generic metadata constraints that still preserve a domain-agnostic Platform Core, or when plugin-driven metadata semantics require additional Extension API decisions.
