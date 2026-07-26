# Phase 3 Asset Graph Query Limits

This guide documents the delivered Phase 3 Asset Graph query behavior and the limits that keep it aligned with [ADR-0030](./adr/ADR-0030%20%E2%80%94%20Dependency%20Graph%20and%20Query%20Scope.md).

## Purpose

Phase 3 graph reads are operational queries for understanding direct and bounded dependencies between Assets.

They are intentionally not a general graph-analysis surface.

## Delivered API Surface

The Phase 3 implementation exposes these read endpoints through the public application API:

* `GET /assets/{asset_id}/relationships`
* `GET /assets/{asset_id}/relationships/incoming`
* `GET /assets/{asset_id}/relationships/outgoing`
* `GET /assets/{asset_id}/references`
* `GET /assets/{asset_id}/graph`

The Web UI consumes the same public API without privileged internal access.

## Bounded Graph Rules

`GET /assets/{asset_id}/graph` supports only the bounded query shape approved for Phase 3:

* `direction` may be `incoming`, `outgoing`, or `both`
* `max_depth` defaults to `3`
* `max_depth` is capped at `10`
* `target_asset_id` is optional and enables bounded path-existence checks

The graph response returns:

* the requested `asset_id`
* the resolved `direction`
* the effective `max_depth`
* the optional `target_asset_id`
* `path_exists` when a path check is requested
* `has_cycle` for the reachable bounded graph slice
* `nodes` and `relationships` needed by clients to render a safe exploration surface

## Relationship And Reference Separation

Phase 3 keeps graph edges and generic references separate:

* Asset relationships connect one OpenPDM Asset to another OpenPDM Asset
* references may stay unresolved or point outside OpenPDM
* references are not returned as graph nodes or graph edges
* clients must render references distinctly from Asset relationships

## Deferred Behavior

The current Phase 3 implementation does not add:

* unbounded traversal
* cross-organization or cross-project traversal
* graph analytics or scoring
* custom graph query languages
* GraphQL graph endpoints
* bulk relationship mutation
* automatic graph extraction from uploaded files
* domain-specific engineering semantics

These behaviors remain deferred to later roadmap phases or future ADR work.

## Web UI Validation Surface

The delivered Web UI demonstrates the approved read scope by:

* showing incoming and outgoing relationships separately
* allowing navigation from an Asset to a related Asset
* rendering generic references separately from graph edges
* showing a bounded graph summary using `direction=both` and `max_depth=3`

## Validation Checklist

Use this checklist when validating the Phase 3 Asset Graph implementation:

* Create at least two Assets in the same Project and connect them through a generic relationship.
* Confirm `GET /assets/{asset_id}/relationships/incoming` and `.../outgoing` return only authorized Project-scoped data.
* Confirm `GET /assets/{asset_id}/references` returns unresolved or external references without turning them into graph nodes.
* Confirm `GET /assets/{asset_id}/graph` rejects or bounds oversized traversal requests according to the hard depth limit.
* Confirm `GET /assets/{asset_id}/graph?target_asset_id=...` reports `path_exists` only within the bounded traversal scope.
* Confirm simple cycle scenarios set `has_cycle` and emit the approved observability signals on the write path.
* Confirm the Web UI relationship exploration surface renders related Assets and references distinctly.

## Automated Evidence In This Repository

The repository currently validates the Phase 3 graph implementation with:

* backend API tests in `backend/tests/test_core_platform_api.py`
* frontend integration-style UI tests in `frontend/src/App.test.tsx`

These tests cover:

* relationship and reference CRUD behavior
* bounded graph reads
* path existence and simple cycle detection
* audit and event coverage for relationship mutations
* Web UI relationship exploration and related-Asset navigation
