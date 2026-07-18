# ADR-0043 — Persist Private Per-User Project Views

**Status:** Accepted

---

# Context

Operational Engineering Asset work requires users to return to useful Project-specific filters, sorting, density and columns across devices and sessions.

Browser-local persistence cannot provide that continuity and cannot enforce lifecycle or ownership rules through the public application API. Shared Project views would introduce collaborative naming, editing and governance concerns that are not required for the first operational workspace.

Saved views contain generic application query preferences, not engineering meaning. They must not weaken Project authorization or allow stored filters to become an authority source.

OpenPDM therefore needs a small owner-private persistence contract for per-user Project views.

---

# Decision

OpenPDM will persist private per-user Project Asset views as a generic Platform Core capability owned by the Projects Platform Module.

The authenticated public application API exposes view CRUD under `/users/me/project-views`. A view stores its owner, Project, name, allowlisted Asset filters, sort order, density and selected columns. Records and payloads are bounded and contain no engineering-specific semantics.

The application layer supplies the authenticated actor context to the Projects Platform Module public interface, which verifies Project access on every operation. Clients cannot select another owner. Views are readable, mutable and removable only by their owner.

Using a saved view never grants access. When an application applies a view to an Engineering Asset query, the Assets Platform Module independently revalidates the stored filters, sort keys and columns and reauthorizes the request through its public interface. Losing Project access makes the view unavailable; restoring access may make it available again. Deleting the Project or owner removes the associated views according to normal persistence lifecycle rules.

Shared, Organization-owned and administrator-owned views are excluded. Plugins cannot read or mutate application views through the Extension API.

## Architectural Rules

1. The Projects Platform Module owns view persistence and ownership checks.
2. Applications coordinate view retrieval and Engineering Asset queries only through public application APIs; Platform Modules do not access one another's internals.
3. Views are private to the current user and scoped to one Project.
4. Saved query state is revalidated and never acts as authorization.
5. View payloads remain bounded, generic and domain-agnostic.
6. Shared views and plugin access require a future ADR and public contract.

---

# Consequences

## Positive

* Users can resume frequent Project work across browsers and devices.
* Ownership and Project authorization are enforced consistently by the Platform Core.
* The first contract remains small because sharing and collaborative governance are excluded.
* Saved state reuses allowlisted Asset query semantics without adding engineering knowledge.

## Trade-offs

* The Projects Platform Module gains persistence for user-owned presentation preferences.
* Query-contract changes require compatibility handling for stored views.
* Membership changes and deletion require defined cleanup and unavailable-state behavior.
* Private views do not support team-standard layouts.

These trade-offs are acceptable because private persistence improves repeated operational work without introducing a general preference system or collaborative view governance.

---

# Alternatives Considered

## Browser-Local Persistence Only

Rejected because views would not follow the user across devices and would bypass server-owned lifecycle and Project access checks.

## Shared Project Views

Deferred because shared ownership requires naming, editing, permission, conflict and audit rules beyond the private-view need.

## Generic User Preference Store

Rejected because a general preference framework would broaden the Platform Core without a demonstrated cross-capability requirement.

---

# Review

Reconsider this decision when organizations demonstrate a need for governed shared views, or when multiple unrelated capabilities require a separately designed generic preference Platform Module.
