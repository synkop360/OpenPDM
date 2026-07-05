# ADR-0030 — Dependency Graph and Query Scope

**Status:** Accepted

---

# Context

The Phase 3 roadmap includes:

* dependency graph;
* graph queries;
* relationship exploration.

OpenPDM needs explicit bounds for this behavior so the first Asset Graph release remains generic, demonstrable and maintainable.

Without a scope decision, graph-query work could expand prematurely into analytics, Digital Thread behavior or cross-tenant traversal that does not belong in Phase 3.

---

# Decision

Phase 3 graph queries are **operational queries, not analytics**.

The approved Phase 3 query scope includes:

* direct dependencies;
* direct dependents;
* bounded traversal depth;
* simple impact analysis;
* cycle detection.

## Approved query scenarios

Phase 3 supports the following query behaviors:

* get outgoing relationships;
* get incoming relationships;
* get dependency tree up to `N` levels;
* get dependent tree up to `N` levels;
* detect whether a path exists between two Assets;
* detect simple cycles.

## Traversal limits

Phase 3 traversal limits are:

* default maximum depth: `3`;
* hard maximum depth: `10`.

## Explicit exclusions

Phase 3 does **not** introduce:

* unbounded traversal;
* graph analytics;
* shortest-path optimization;
* centrality calculations;
* Digital Thread queries;
* cross-organization graph queries.

---

# Consequences

## Positive

* Graph behavior remains bounded and testable.
* Dependency-oriented read scenarios are supported without advanced graph infrastructure.
* Phase 3 stays aligned with the roadmap and avoids premature analytics scope.

## Trade-offs

* Some useful future graph questions remain out of scope.
* Traversal limits may feel restrictive for large structures.
* Later phases may need additional API or storage decisions for richer graph behavior.

These trade-offs are acceptable because OpenPDM currently prioritizes safe and understandable operational graph queries over broader graph-analysis capabilities.

---

# Alternatives Considered

## Unbounded Traversal in Phase 3

Rejected because it increases performance and authorization risk while making the first graph release harder to reason about.

## Analytics-Oriented Query Scope

Rejected because advanced analytics belongs to later phases, dedicated infrastructure or plugin-driven specialization if justified.

## Cross-Organization Traversal

Rejected because it would violate the current tenancy model and broaden authorization complexity prematurely.

---

# Review

This decision should be revisited when OpenPDM introduces Digital Thread behavior, broader graph analytics or more advanced traversal requirements.
