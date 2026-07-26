# ADR-0029 — Relationship Application API Surface

**Status:** Accepted

---

# Context

Phase 3 relationship capabilities must be exposed through the public application API in keeping with the project's API-first architecture.

The Web UI, future Desktop Client and future automation or plugin-facing application clients must consume the same public API and must not receive private relationship endpoints.

OpenPDM therefore needs an explicit Phase 3 public application API surface for relationship creation, retrieval and graph exploration.

---

# Decision

Phase 3 adopts the following minimum public application API surface for Asset relationships:

* `POST /assets/{asset_id}/relationships`
* `GET /assets/{asset_id}/relationships`
* `GET /assets/{asset_id}/relationships/incoming`
* `GET /assets/{asset_id}/relationships/outgoing`
* `DELETE /relationships/{relationship_id}`
* `GET /assets/{asset_id}/graph`

The minimum relationship creation payload is:

```json
{
  "target_asset_id": "...",
  "relationship_type": "depends_on",
  "metadata": {}
}
```

## API rules

Phase 3 API behavior follows these rules:

* the API exposes Asset relationships only;
* the API does not expose graph database implementation details;
* the API must enforce Project-scoped permissions;
* the API must remain usable by the Web UI, Desktop Client and future clients that consume the public application API;
* public API behavior must not bypass Platform Module boundaries.

## Explicit exclusions

Phase 3 does **not** introduce:

* GraphQL;
* Cypher;
* a custom query language;
* bulk graph mutations;
* automatic CAD graph import.

These capabilities are deferred because Phase 3 prioritizes a bounded and understandable public API over advanced graph tooling.

---

# Consequences

## Positive

* The Asset Graph remains API-first and client-agnostic.
* The Web UI and future Desktop Client stay aligned with the same public contract.
* The API stays understandable for contributors and external automation clients.

## Trade-offs

* Phase 3 query expressiveness remains intentionally limited.
* Future graph capabilities may require additive API evolution.
* Clients must compose richer behavior from a small number of explicit endpoints.

These trade-offs are acceptable because OpenPDM currently prioritizes explicit and stable public contracts over early graph-API complexity.

---

# Alternatives Considered

## GraphQL or Specialized Graph Query APIs in Phase 3

Rejected because they would add unnecessary complexity before the bounded Asset Graph foundation is established.

## Private Relationship Endpoints for the Web UI or Desktop Client

Rejected because they would violate the API-first architecture and Platform Core boundary rules.

## Bulk Mutation APIs in Phase 3

Rejected because bulk graph mutation introduces additional validation, conflict and audit complexity that is not required for the first Asset Graph release.

---

# Review

This decision should be revisited if OpenPDM later needs more expressive graph APIs, broader automation patterns or plugin-facing graph operations beyond the Phase 3 scope.
