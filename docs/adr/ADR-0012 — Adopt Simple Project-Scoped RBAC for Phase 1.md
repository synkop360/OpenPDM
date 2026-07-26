# ADR-0012 — Adopt Simple Project-Scoped RBAC for Phase 1

**Status:** Accepted

---

# Context

Phase 1 requires a permission model so authenticated users can access Organizations, Projects and the generic Asset lifecycle through consistent authorization rules.

The current accepted ADRs define the modular monolith architecture, Platform boundaries, the Asset lifecycle, the Phase 1 local-first identity model, generic metadata, and Phase 1 PostgreSQL-only search. They do not yet define how authorization is modeled in the Platform Core.

OpenPDM needs an initial permission model that:

* is simple enough for the Core Platform MVP;
* keeps authorization decisions inside the Platform Core;
* supports Organization and Project membership without introducing complex policy infrastructure;
* remains compatible with the modular monolith and Platform Module boundary rules;
* avoids premature fine-grained authorization complexity before real usage justifies it.

The project must avoid turning Phase 1 authorization into a broad policy engine or engineering-domain-specific security model.

---

# Decision

OpenPDM will adopt **simple RBAC scoped by Project** for Phase 1.

Phase 1 authorization will use the following objects:

* `OrganizationRole`
* `ProjectRole`

Tenancy and membership for Phase 1 follow these scoping rules:

* every `Project` belongs to exactly one `Organization`;
* every `ProjectRole` assignment is scoped within that `Project`'s `Organization`;
* a user must be an `Organization` member before receiving a `ProjectRole`;
* Phase 1 does not support standalone `Project` membership outside an `Organization`.

Phase 1 roles are limited to:

* `Owner`
* `Maintainer`
* `Contributor`
* `Viewer`

Phase 1 permissions are limited to:

* `read_project`
* `manage_project`
* `create_asset`
* `update_asset`
* `delete_asset`
* `create_revision`
* `manage_members`

Permissions are calculated by the **Platform Core**.

No plugin may decide authorization rights.

Phase 1 explicitly avoids:

* per-Asset permissions
* custom ACLs
* complex inheritance
* dynamic policy systems
* direct cross-Organization Project membership

This decision applies only to the Core Platform MVP scope and intentionally favors clarity over fine-grained flexibility.

---

# Consequences

## Positive

* Phase 1 gets a clear and understandable authorization model.
* Authorization remains centralized in the Platform Core and consistent with the project architecture.
* Self-hosted teams can adopt the MVP without configuring a complex policy system.
* The design supports Organization and Project membership while keeping operational and implementation complexity low.
* Project access remains easier to reason about because it is always scoped within an Organization membership boundary.
* Plugins cannot bypass or redefine Platform Core authorization behavior.

## Trade-offs

* Phase 1 cannot express fine-grained per-Asset access control.
* More advanced enterprise-style authorization requirements are deferred.
* Later expansion of authorization capabilities may require additional ADRs for inheritance, exceptions or policy composition.
* Phase 1 cannot model users who belong directly to a Project without belonging to the containing Organization.

These trade-offs are acceptable because OpenPDM currently prioritizes a simple, usable Core Platform MVP over highly flexible access control.

---

# Alternatives Considered

## Per-Asset Permissions in Phase 1

Rejected because they add complexity too early and are not required for the initial Core Platform MVP.

## Custom ACLs

Rejected because they would complicate the permission model and contributor understanding without clear immediate value.

## Complex Inheritance

Rejected because it increases ambiguity and implementation risk in the early Platform Core.

## Dynamic Policy Engine

Rejected because it introduces a broader policy architecture that is out of scope for Phase 1.

## Standalone Project Membership

Rejected because it weakens the tenancy boundary between Organization and Project scope and adds avoidable ambiguity to the first Core Platform MVP authorization model.

---

# Review

This decision should be revisited when OpenPDM needs finer-grained authorization, policy composition or workflow-driven access control beyond the Core Platform MVP.
