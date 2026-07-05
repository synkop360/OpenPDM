# ADR-0017 — Define the Collaboration State Model for Phase 2

**Status:** Accepted

---

# Context

Phase 2 introduces collaboration behavior on top of the generic Asset lifecycle delivered by the Platform Core MVP.

OpenPDM needs a minimal collaboration state model that:

* remains generic and domain-agnostic;
* does not introduce workflow-engine concepts planned for Phase 6;
* does not depend on desktop-specific behavior;
* works through the public application API for Web UI and future Desktop Client use.

---

# Decision

Phase 2 adopts a minimal **Asset collaboration state** model with the following values:

* `available`
* `locked`
* `stale_lock`

The collaboration state is separate from the generic lifecycle status primitive defined for earlier phases.

## State meanings

* `available` means no active collaboration lock blocks Phase 2 collaboration operations on the Asset.
* `locked` means one active collaboration lock exists for the Asset and normal collaboration write actions are restricted by lock ownership rules.
* `stale_lock` means a lock record exists but can no longer be treated as a normal valid working lock and requires explicit human resolution. In Phase 2 this is not time-based expiration.

Phase 2 explicitly does **not** introduce:

* `review`
* `approval`
* `released`
* workflow transitions
* desktop synchronization states

These concerns remain deferred to later phases.

---

# Consequences

## Positive

* The collaboration model stays small and understandable.
* Workflow behavior remains clearly separated from collaboration behavior.
* The model supports Web UI collaboration without introducing privileged client behavior.

## Trade-offs

* `stale_lock` requires explicit handling rules elsewhere in the collaboration model.
* More advanced collaboration or process states remain deferred.

These trade-offs are acceptable because Phase 2 prioritizes safe shared editing over richer process modeling.

