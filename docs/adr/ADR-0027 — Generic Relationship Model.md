# ADR-0027 — Generic Relationship Model

**Status:** Accepted

---

# Context

Phase 3 introduces the Asset Graph as a first-class Platform Core capability.

The Project Charter and Architecture already establish that:

* the Platform Core remains domain-agnostic;
* relationships are first-class citizens;
* the Asset Graph is the authoritative representation of engineering knowledge;
* engineering-specific meaning belongs to plugins, not to the Platform Core.

OpenPDM therefore needs a generic relationship model that:

* connects Assets without introducing engineering-domain semantics;
* remains compatible with the modular monolith and Public Module Interface rules;
* supports future graph navigation and dependency-oriented queries;
* avoids prematurely modeling Digital Thread or plugin-specific concepts.

---

# Decision

OpenPDM adopts a **generic Asset-to-Asset relationship model** for Phase 3.

Phase 3 `Relationship` records contain the following fields:

* `id`
* `source_asset_id`
* `target_asset_id`
* `relationship_type`
* `direction`
* `metadata`
* `created_by`
* `created_at`

## Relationship scope

Relationships connect **Assets only**.

Phase 3 relationships do **not** connect:

* Blob
* Representation
* Revision
* external resources

External or unresolved pointers are handled separately through the generic Reference model defined for Phase 3.

## Relationship rules

Phase 3 relationships follow these rules:

* relationships are explicit;
* relationships are directional by default;
* relationships may carry generic metadata;
* the Platform Core stores relationship metadata but does not interpret engineering semantics;
* the Platform Core does not infer relationship meaning from file formats, plugin logic or business domain rules.

## Approved Phase 3 relationship types

The approved generic relationship types for Phase 3 are:

* `depends_on`
* `references`
* `derived_from`
* `generates`
* `supersedes`
* `related_to`

## Explicit exclusions

Phase 3 does **not** introduce the following as generic Platform Core relationship types:

* `contains`
* `part_of`
* `manufactured_by`
* `validated_by`
* `implements`

These concepts are deferred because they are more likely to carry engineering-domain, workflow or Digital Thread semantics that do not belong in the generic Phase 3 Platform Core.

---

# Consequences

## Positive

* The Asset Graph remains generic and domain-agnostic.
* Assets can be connected explicitly without introducing plugin-specific semantics.
* Future graph traversal and dependency queries can build on a stable core relationship model.
* The Platform Core avoids polluting the Asset Graph with external or unresolved objects.

## Trade-offs

* Phase 3 relationship semantics remain intentionally limited.
* Some useful engineering concepts must be deferred to plugins or later phases.
* Relationship types require discipline so they are not overloaded with implicit domain meaning.

These trade-offs are acceptable because OpenPDM currently prioritizes a clear, generic Asset Graph foundation over early engineering specialization.

---

# Alternatives Considered

## Unrestricted Relationship Types

Rejected because unrestricted generic types would invite engineering-domain semantics into the Platform Core too early.

## Non-Directional Relationships by Default

Rejected because dependency and traceability scenarios require explicit direction for predictable Phase 3 graph behavior.

## Relationship Semantics Derived from File Content

Rejected because engineering interpretation belongs to plugins, not to the Platform Core.

---

# Review

This decision should be revisited when OpenPDM expands into Digital Thread capabilities or when plugin-driven relationship semantics require additional Extension API decisions.
