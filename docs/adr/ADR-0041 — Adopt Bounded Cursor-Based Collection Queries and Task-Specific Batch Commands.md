# ADR-0041 — Adopt Bounded Cursor-Based Collection Queries and Task-Specific Batch Commands

**Status:** Proposed

---

# Context

OpenPDM application clients need to browse growing collections of Engineering Assets, Organization and Project members, notifications and plugins without loading every matching record at once.

Existing list endpoints are already used by current clients and must remain compatible. Authorization and validation remain responsibilities of the Platform Module that owns each resource. ADR-0029 also deliberately bounds relationship operations and does not authorize bulk graph mutation.

Some repeated user actions, such as acknowledging many notifications, require one atomic command. A generic bulk endpoint would weaken resource ownership and make authorization behavior difficult to reason about.

OpenPDM therefore needs bounded collection queries and narrowly defined batch commands without replacing existing contracts or bypassing Platform Module boundaries.

---

# Decision

OpenPDM will add parallel cursor-based collection endpoints while preserving existing list endpoints.

Paged endpoints return:

```text
Page<T>
  items
  next_cursor
```

The default page limit is `50` and the maximum is `100`. Cursors are opaque to clients, bind the traversal position to the authorized resource scope, filters and sort order, and use a deterministic unique tie-breaker. Invalid, expired or mismatched cursors are rejected. A cursor provides stable traversal while the relevant collection ordering is unchanged; it does not create a long-running database snapshot.

Each owning Platform Module defines its own allowlisted filters and sort keys through its public interface. Authorization is evaluated on every page request. Infrastructure-specific pagination details are not part of the public application API.

OpenPDM will add task-specific batch commands only when one business action requires atomic treatment of multiple records. Each command defines its accepted selection form, authorization, limits, transaction behavior and audit coverage. OpenPDM will not introduce a generic bulk-command framework.

The Notifications Platform Module may acknowledge either explicitly selected notification identifiers or all current-user notifications matching the command's supported Project and read-state filters. The operation preserves ADR-0025: notifications transition only from unread to read, and acknowledgment remains scoped to the current user.

Bulk relationship mutation remains excluded. Adding it requires an ADR that explicitly supersedes the relevant limits in ADR-0029.

## Architectural Rules

1. Existing list endpoints remain supported for backward compatibility.
2. Every paged query and batch command is owned and authorized by the responsible Platform Module.
3. Filters and sort keys are resource-specific allowlists, not client-defined expressions.
4. Cursors are opaque, bounded and invalid outside the query scope that created them.
5. Batch commands represent named business actions and are atomic within their documented scope.
6. Plugins gain no direct collection or batch access; they continue to use the Extension API.

---

# Consequences

## Positive

* Application clients can traverse large collections with bounded resource use.
* Existing clients remain compatible.
* Stable ordering and opaque cursors avoid offset drift and infrastructure leakage.
* Named batch commands preserve authorization, audit and Platform Module ownership.
* ADR-0029's bounded relationship contract remains unchanged.

## Trade-offs

* Each collection requires explicit filter, sort and cursor validation.
* Clients must handle invalid cursors and data that changes between page requests.
* Existing and paged endpoints must coexist until a separately governed compatibility change.
* Task-specific batch commands require more design work than a generic bulk endpoint.

These trade-offs are acceptable because operational scalability must not weaken authorization or module boundaries.

---

# Alternatives Considered

## Offset-Based Pagination

Not selected because concurrent inserts and removals can shift offsets, duplicate records or skip records during traversal.

## Replace Existing List Endpoints

Rejected because it would create an unnecessary breaking change for current clients.

## Generic Bulk Query and Mutation API

Rejected because it would obscure resource-specific authorization, validation, atomicity and audit behavior.

---

# Review

Reconsider this decision if measured collection workloads cannot be served efficiently with bounded keyset cursors, or if a demonstrated cross-module business transaction requires a separately governed command contract.
