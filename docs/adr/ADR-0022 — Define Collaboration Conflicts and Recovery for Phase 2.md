# ADR-0022 — Define Collaboration Conflicts and Recovery for Phase 2

**Status:** Accepted

---

# Context

Phase 2 needs explicit conflict behavior so collaboration failures are predictable, safe and recoverable without introducing desktop synchronization semantics or partial lifecycle corruption.

Conflict conditions and recovery rules must be defined together so the platform does not detect failures without specifying safe system behavior.

---

# Decision

The approved Phase 2 collaboration conflicts are:

* check-in without lock;
* check-in by non-owner;
* checkout on already locked Asset;
* revision based on outdated Revision;
* deleted or archived Asset during collaboration;
* Blob upload failure during check-in.

Phase 2 recovery follows these rules:

* fail safely;
* preserve uploaded Blob content when possible;
* never create a partial Revision;
* emit an audit event;
* return an explicit error response.

The key Phase 2 rule is:

* **No partial check-in is visible as a valid Revision.**

Phase 2 conflict behavior is limited to server-side collaboration conflicts. Offline synchronization and desktop-local conflict behavior remain deferred.

---

# Consequences

## Positive

* Collaboration failure behavior is explicit and testable.
* The immutable Revision model is protected from partial writes.
* Clients can guide user recovery from explicit backend outcomes.

## Trade-offs

* Some failed operations may leave recoverable Blob content that is not yet attached to a valid Revision.
* Additional cleanup or retention decisions may be needed later.

These trade-offs are acceptable because preserving lifecycle integrity is more important than hiding every intermediate storage artifact.

