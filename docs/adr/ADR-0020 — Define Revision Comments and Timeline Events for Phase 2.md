# ADR-0020 — Define Revision Comments and Timeline Events for Phase 2

**Status:** Accepted

---

# Context

Phase 2 needs lightweight discussion and activity visibility for collaboration without introducing workflow approvals, moderation systems or engineering-specific semantics.

Revision comments and timeline events are closely related collaboration signals and should be defined together to avoid fragmented behavior.

---

# Decision

Phase 2 adopts the following **revision comment** rules:

* comment content is plain text;
* a revision comment is required on check-in;
* a revision comment is immutable after creation;
* the comment is attached to the created Revision.

Phase 2 does **not** include complex moderation behavior.

The approved Phase 2 **timeline events** are:

* `AssetCreated`
* `AssetLocked`
* `AssetUnlocked`
* `RevisionCreated`
* `CheckInCompleted`
* `ForceUnlocked`
* `ConflictDetected`

Phase 2 does not include comment editing, comment deletion or advanced moderation workflows.

---

# Consequences

## Positive

* Revision discussion stays simple and auditable.
* Timeline visibility is explicit and bounded for Phase 2.
* Workflow approval semantics are not introduced prematurely.

## Trade-offs

* Comment behavior is intentionally rigid in Phase 2.
* Later moderation or richer discussion features will require separate decisions.

These trade-offs are acceptable because Phase 2 prioritizes traceable collaboration over broad communication features.

