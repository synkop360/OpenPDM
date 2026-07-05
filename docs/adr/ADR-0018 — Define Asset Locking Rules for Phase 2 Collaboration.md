# ADR-0018 — Define Asset Locking Rules for Phase 2 Collaboration

**Status:** Accepted

---

# Context

Phase 2 requires a locking model that prevents unsafe concurrent collaboration while preserving the immutable Asset lifecycle and existing Platform Module boundaries.

The locking model must stay generic, simple and auditable. It must not introduce representation-level or Blob-level collaboration semantics in Phase 2.

---

# Decision

Phase 2 adopts **Asset-level locking** only.

## Lock scope

Each collaboration lock targets:

* `asset_id`
* the containing Organization and Project scope
* one owning `user_id`

Phase 2 does **not** support locks on:

* Blob
* Representation
* file path
* partial Asset content

## Lock rules

Phase 2 lock behavior follows these rules:

* one active lock per Asset;
* only the lock owner may perform normal check-in or unlock actions;
* `Maintainer` and `Owner` may perform force-unlock;
* lock enforcement remains inside the Platform Core;
* locks do not expire automatically in Phase 2.

`stale_lock` handling is exceptional state handling, not automatic expiration.

---

# Consequences

## Positive

* Lock scope remains simple and predictable.
* The model avoids premature file-level or representation-level complexity.
* Collaboration authority remains aligned with the Project-scoped RBAC model.

## Trade-offs

* Asset-level locking is coarser than file-level or representation-level collaboration.
* Manual intervention is required for stale or force-unlock scenarios.

These trade-offs are acceptable because Phase 2 prioritizes safe, understandable collaboration over finer-grained concurrency.

