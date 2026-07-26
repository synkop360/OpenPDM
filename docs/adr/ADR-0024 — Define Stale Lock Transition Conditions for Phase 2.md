# ADR-0024 - Define Stale Lock Transition Conditions for Phase 2

**Status:** Accepted

---

# Context

ADR-0017 introduces `stale_lock` as an exceptional collaboration state and
ADR-0018 clarifies that it is not time-based expiration. Phase 2 still needs
objective rules for when a normal Asset lock stops being valid and how clients
must behave when that happens.

The decision must stay within the approved Phase 2 collaboration scope. It must
not introduce heartbeat protocols, background lock renewal, desktop-local sync
behavior or workflow-state concepts.

---

# Decision

An Asset enters `stale_lock` only when an active collaboration lock exists and
the lock can no longer be honored as a normal working lock.

## Entry conditions

Phase 2 treats a lock as `stale_lock` when at least one of the following is
true:

* the Asset status is `archived`;
* the lock owner user is inactive;
* the lock owner no longer has valid tenancy and write authority for normal
  collaboration on that Asset, meaning:
  * the user is no longer an Organization member for the Asset's Organization;
  * or the user no longer has a Project role that permits collaboration writes
    in the Asset's Project.

For Phase 2, the Project roles that keep a lock valid are:

* `Owner`
* `Maintainer`
* `Contributor`

`Viewer` does not keep a collaboration lock valid.

## Non-conditions

Phase 2 does **not** create `stale_lock` because of:

* elapsed time;
* client disconnect;
* missing heartbeat;
* browser refresh;
* lack of desktop synchronization.

## Resolution rules

Phase 2 resolves `stale_lock` only through explicit human action:

* the lock owner may unlock the Asset if they still have authenticated access
  to the Asset;
* a Project `Owner` or `Maintainer` may force-unlock;
* other users may not check out or check in while the stale lock remains.

## API and Web UI expectations

Phase 2 must expose `stale_lock` as a distinct collaboration state.

Clients must treat it differently from a normal `locked` state:

* check-in is not allowed while the lock is stale;
* normal checkout by another user is rejected until explicit unlock or
  force-unlock;
* the UI should explain that the lock requires human resolution;
* the UI should expose force-unlock only to `Owner` and `Maintainer` users.

---

# Consequences

## Positive

* `stale_lock` becomes objective and testable.
* Lock invalidation stays aligned with the existing tenancy and RBAC model.
* Phase 2 avoids hidden automatic expiration behavior.

## Trade-offs

* Some stale locks require privileged manual intervention.
* Clients must surface one more lock state instead of treating all locks the
  same way.

These trade-offs are acceptable because safe shared editing is more important
than aggressively auto-healing lock state in Phase 2.
