# ADR-0014 — Adopt a Simple Generic Lifecycle Status Primitive for Phase 1

**Status:** Accepted

---

# Context

Phase 1 needs a minimal lifecycle status capability so the Core Platform can represent generic object state without introducing the configurable process behavior planned for Engineering Workflows.

The current accepted ADRs define the modular monolith architecture, Platform boundaries, the generic Asset lifecycle, the Phase 1 technology stack, identity, metadata, search, authorization and plugin-skeleton direction. They do not yet define the generic status primitive for Phase 1.

OpenPDM needs an initial status model that:

* remains generic and domain-agnostic;
* is simple enough for the Core Platform MVP;
* does not become an implicit workflow engine;
* preserves a clear architectural boundary with the later Engineering Workflows phase;
* avoids prematurely introducing engineering or process-specific lifecycle semantics.

Phase 1 should support basic lifecycle state, not configurable business process orchestration.

---

# Decision

OpenPDM will adopt a **simple generic lifecycle status primitive** for Phase 1.

The accepted Phase 1 status values are:

* `draft`
* `active`
* `archived`

Status is a **generic Platform Core primitive**.

Phase 1 does **not** include a workflow engine.

Phase 1 explicitly avoids the following workflow-oriented concepts:

* `review`
* `released`
* `obsolete`
* `approval`
* configurable transitions

These concepts are deferred to the Engineering Workflows phase.

---

# Consequences

## Positive

* Phase 1 gets a simple, understandable lifecycle primitive.
* The Platform Core remains generic and does not take on workflow semantics too early.
* The roadmap boundary with the Engineering Workflows phase stays clear.
* The status model is easy to expose through the public API and the Web UI.
* Later workflow capabilities can build on a minimal status baseline instead of replacing a more complex premature design.

## Trade-offs

* Phase 1 cannot represent richer lifecycle or approval states.
* Transition rules remain intentionally simple and non-configurable.
* Later workflow features may require expanding or layering additional state concepts on top of this primitive.

These trade-offs are acceptable because OpenPDM currently prioritizes a usable Core Platform MVP over early process modeling.

---

# Alternatives Considered

## Only `active` and `archived`

Rejected because a `draft` state provides a more useful generic MVP lifecycle without introducing workflow complexity.

## Workflow-Oriented Statuses in Phase 1

Rejected because they would move workflow semantics into the Platform Core too early.

## Configurable Lifecycle Engine in Phase 1

Rejected because configurable transitions and approvals belong to the later Engineering Workflows phase.

---

# Review

This decision should be revisited when OpenPDM introduces the Engineering Workflows phase and needs configurable lifecycle transitions, approvals or richer process-driven state management.

