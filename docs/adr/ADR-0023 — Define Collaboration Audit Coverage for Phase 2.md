# ADR-0023 — Define Collaboration Audit Coverage for Phase 2

**Status:** Accepted

---

# Context

The Project Charter requires significant business and security actions to be observable.

Phase 2 collaboration introduces lock, check-in, conflict and notification behaviors that must have explicit audit coverage so user-facing timelines are not treated as the only historical record.

---

# Decision

The following Phase 2 collaboration actions are auditable:

* checkout;
* checkin;
* unlock;
* force unlock;
* conflict detection;
* failed checkin;
* notification emitted.

Each Phase 2 collaboration audit entry must contain:

* `actor_id`
* `target_asset_id`
* `event_type`
* `timestamp`
* `request_id`
* `result`
* `reason/error`

This audit coverage is in addition to user-facing timeline behavior and must not be replaced by it.

---

# Consequences

## Positive

* Collaboration actions remain traceable and auditable.
* Audit behavior stays distinct from user-facing timeline behavior.
* Later observability or compliance requirements have a clear baseline.

## Trade-offs

* Collaboration flows must carry consistent request and result context.
* Additional storage and query behavior is required for audit completeness.

These trade-offs are acceptable because auditability is a core platform concern, not an optional feature.

