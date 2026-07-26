# ADR-0015 — Define Organization and Project Platform Module Boundaries for Phase 1

**Status:** Accepted

---

# Context

Phase 1 requires Organizations, Projects, Membership and baseline authorization so teams can access the Core Platform MVP securely.

The current accepted ADRs define the modular monolith architecture, Platform boundaries, the local-first identity model and simple Project-scoped RBAC. They do not yet define which Platform Modules own Organization and Project responsibilities or how other Platform Modules must interact with them.

OpenPDM needs a Phase 1 module boundary decision that:

* keeps tenancy rules simple and explicit;
* preserves the modular monolith public interface discipline;
* aligns with the accepted rule that every Project belongs to exactly one Organization;
* avoids creating a broad cross-cutting tenant module with mixed responsibilities;
* gives dependent Platform Modules a stable public contract for tenancy and access lookups.

---

# Decision

Phase 1 will use **two dedicated Platform Modules** for tenancy-related business responsibilities:

* **Organization Platform Module**
* **Project Platform Module**

## Organization Platform Module

The Organization Platform Module owns:

* `Organization`
* Organization membership
* Organization-level role assignment

Its public interface is responsible for operations such as:

* get Organization
* list user Organizations
* check Organization membership
* check Organization role

## Project Platform Module

The Project Platform Module owns:

* `Project`
* Project-level role assignment

Its public interface is responsible for operations such as:

* get Project
* list Projects in an Organization
* list user Projects within an Organization
* check Project role
* create or update Project within an Organization

## Boundary Rules

Phase 1 applies the following module dependency rules:

* every `Project` belongs to exactly one `Organization`;
* the Project Platform Module may depend on the Organization Platform Module public interface;
* the Organization Platform Module must not depend on the Project Platform Module;
* other Platform Modules must use public interfaces only and must not access Organization or Project internals.

Anything about **who belongs to the tenant** belongs to the Organization Platform Module.

Anything about **what exists inside the tenant** belongs to the Project Platform Module.

---

# Consequences

## Positive

* Tenancy and membership responsibilities stay clear and easy to reason about.
* The module structure aligns with the accepted Organization and Project scoping rules from Phase 1 authorization.
* Dependent Platform Modules get stable public interface boundaries for tenancy-related lookups.
* The design avoids an oversized access or tenant module with mixed responsibilities.
* The dependency direction remains simple and consistent with the modular monolith architecture.

## Trade-offs

* Organization and Project concerns still require coordination through public interfaces for some workflows.
* Future expansion to richer tenant models may require additional ADRs.
* The design does not try to optimize for uncommon multi-tenant edge cases in Phase 1.

These trade-offs are acceptable because OpenPDM currently prioritizes clear boundaries and a usable Core Platform MVP over broader tenancy flexibility.

---

# Alternatives Considered

## Single Tenant Module

Rejected because it would combine Organization, membership and Project responsibilities into one broader module and weaken single-responsibility boundaries.

## Project Module Independent from Organization Context

Rejected because it conflicts with the accepted Phase 1 rule that every Project belongs to exactly one Organization.

## Symmetric Module Dependencies

Rejected because mutual dependency between Organization and Project modules would weaken the intended public interface direction and increase coupling.

---

# Review

This decision should be revisited if OpenPDM later requires a materially different tenancy model, cross-Organization Project semantics or stronger separation of access and tenancy responsibilities.
