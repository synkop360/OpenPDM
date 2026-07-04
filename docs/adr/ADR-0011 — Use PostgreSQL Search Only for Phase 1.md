# ADR-0011 — Use PostgreSQL Search Only for Phase 1

**Status:** Accepted

---

# Context

Phase 1 requires a basic search capability so teams can find Engineering Assets and related information in the Core Platform MVP.

The current accepted ADRs already define PostgreSQL as the primary database and generic key/value metadata as a Platform Core capability. They do not yet define the search scope or indexing strategy for Phase 1.

OpenPDM needs an initial search approach that:

* is sufficient for the Core Platform MVP;
* keeps the operational footprint simple for self-hosted teams;
* remains aligned with the modular monolith architecture;
* avoids introducing a separate search engine before there is clear evidence it is needed;
* supports search over generic Platform Core data without introducing engineering-domain semantics.

The project must avoid premature complexity in Phase 1 while still providing useful search across the initial Asset lifecycle and metadata capabilities.

---

# Decision

OpenPDM will use **PostgreSQL search only** for Phase 1.

Phase 1 search scope is limited to:

* `asset name`
* `asset description`
* `metadata keys`
* `metadata values`
* `revision comments`

Phase 1 indexing and search implementation will use:

* **PostgreSQL full-text search**
* **GIN indexes**
* **JSONB only if necessary**

OpenSearch and other external search engines are explicitly deferred.

PostgreSQL GIN indexes are considered sufficient for indexing composite values and supporting the initial full-text search behavior needed by the Core Platform MVP.

The Platform Core search capability remains generic. It may search metadata keys and values, but it must not assign engineering meaning to them.

---

# Consequences

## Positive

* Phase 1 search can be delivered without adding a new operational dependency.
* Self-hosted deployments remain simpler because PostgreSQL is already required by the platform.
* The MVP gets useful search behavior across Assets, metadata and revision comments.
* The design stays aligned with the modular monolith and Phase 1 scope discipline.
* Future introduction of a dedicated search engine remains possible if justified by real needs.

## Trade-offs

* Phase 1 search will not provide the scale or specialized capabilities of a dedicated external search engine.
* Search relevance tuning and advanced query capabilities remain limited at this stage.
* Later migration to a dedicated search system may require additional indexing and synchronization decisions.

These trade-offs are acceptable because OpenPDM currently prioritizes a simple, usable Core Platform MVP over early distributed search infrastructure.

---

# Alternatives Considered

## OpenSearch in Phase 1

Rejected because it adds unnecessary infrastructure and operational complexity before the Core Platform MVP is established.

## Search Only Asset Names and Descriptions

Rejected because Phase 1 also needs useful discovery across metadata and revision comments.

## JSONB-First Search Model

Rejected because JSONB should be introduced only where necessary, not as the default search representation for all Phase 1 data.

---

# Review

This decision should be revisited if Phase 1 search proves insufficient for relevance, scale or operational needs, or when later phases justify introducing a dedicated external search engine.
