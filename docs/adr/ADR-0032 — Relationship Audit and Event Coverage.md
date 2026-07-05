# ADR-0032 — Relationship Audit and Event Coverage

**Status:** Accepted

---

# Context

The Project Charter requires significant business actions to be observable.

Phase 3 introduces relationship and reference mutations that must have explicit audit and event coverage so graph behavior remains traceable and user-facing graph exploration is not treated as the only historical record.

OpenPDM therefore needs an explicit observability decision for relationship and reference operations.

---

# Decision

Phase 3 adopts explicit audit and event coverage for relationship and reference mutations.

## Approved Phase 3 events

The approved Phase 3 event types are:

* `RelationshipCreated`
* `RelationshipDeleted`
* `RelationshipMetadataUpdated`
* `RelationshipCycleDetected`
* `ReferenceCreated`
* `ReferenceDeleted`
* `ReferenceResolved`
* `GraphQueryExecuted`

## Required audit coverage

The following Phase 3 actions are auditable:

* create relationship;
* delete relationship;
* update relationship metadata;
* create reference;
* delete reference;
* resolve reference;
* failed relationship creation;
* permission denied;
* cycle detected.

Each Phase 3 audit entry must contain:

* `actor_id`
* `project_id`
* `source_asset_id`
* `target_asset_id` or `target_uri`
* `relationship_id` or `reference_id`
* `event_type`
* `timestamp`
* `request_id`
* `result`
* `reason/error`

## Graph read logging rule

Graph read operations are logged only when they are:

* security-sensitive; or
* explicitly configured.

Phase 3 does **not** audit every graph read by default.

---

# Consequences

## Positive

* Relationship and reference mutations remain traceable.
* Audit behavior stays distinct from graph navigation behavior.
* The project preserves observability without flooding audit history with routine graph reads.

## Trade-offs

* Mutation flows must carry consistent request and target context.
* Graph read observability remains intentionally selective.
* Later user-facing history surfaces may still require separate scope decisions.

These trade-offs are acceptable because OpenPDM currently prioritizes meaningful observability over exhaustive low-signal audit volume.

---

# Alternatives Considered

## Audit Every Graph Read by Default

Rejected because it would generate excessive audit noise and reduce the usefulness of the audit trail.

## No Relationship-Specific Audit Decision

Rejected because relationship and reference mutations are significant business actions and must be explicitly covered.

## User-Facing Graph History as the Only Record

Rejected because user-facing navigation or history surfaces must not replace audit and domain-event observability.

---

# Review

This decision should be revisited when OpenPDM introduces richer compliance requirements, broader graph-history surfaces or more advanced graph-query monitoring needs.
