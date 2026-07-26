# ADR-0026 — Keep the Plugin Registry Read-Only Until a Platform Administration Model Exists

**Status:** Accepted

---

# Context

Phase 1 introduced a plugin infrastructure skeleton with a plugin registry, discovery, metadata, and enable/disable state through ADR-0013.

Phase 1 authorization is intentionally limited to simple project-scoped RBAC through ADR-0012.

The plugin registry is not project-scoped. It is platform-wide state.

A security review identified that allowing any authenticated user to create or mutate platform-wide plugin registry records creates an authorization gap because no accepted platform-level administration model exists yet.

OpenPDM needs a short-term decision that:

* closes the security gap now;
* respects the accepted Phase 1 project-scoped RBAC model;
* avoids inventing a global administration model without a dedicated ADR;
* preserves the plugin boundary for the future Plugin Platform phase.

---

# Decision

The Phase 1 plugin registry will remain **read-only** until OpenPDM defines a dedicated platform administration model in a later phase.

Phase 1 allows:

* listing plugin registry records;
* reading plugin registry metadata through the public application API.

Phase 1 does **not** allow:

* creating plugin registry records through the public application API;
* enabling or disabling plugin registry records through the public application API;
* introducing implicit platform administrators through existing Organization or Project roles.

Write operations against the plugin registry must return an authorization-style rejection that clearly communicates the Phase 1 read-only constraint.

Future phases may reintroduce plugin registry mutation only after OpenPDM defines an explicit platform administration model through a dedicated ADR.

---

# Consequences

## Positive

* The current security issue is closed without extending the authorization model informally.
* Phase 1 remains aligned with the accepted project-scoped RBAC decision.
* The plugin infrastructure skeleton stays available as an architectural boundary.
* A future platform administration model can be designed intentionally instead of being implied by a temporary workaround.

## Trade-offs

* Phase 1 plugin registry records cannot be created or toggled through normal runtime APIs.
* The plugin registry becomes mostly architectural scaffolding until a later phase.
* Future plugin management work now requires an explicit administration ADR before mutation can return.

These trade-offs are acceptable because OpenPDM currently prioritizes security and architectural clarity over early mutable plugin management.

---

# Alternatives Considered

## Introduce a Platform-Level Admin Role Now

Rejected because it would extend the accepted authorization model beyond project-scoped RBAC without a dedicated administration ADR.

## Reuse Organization Owner or Maintainer as Platform Administrator

Rejected because Organization and Project roles are scoped business roles, while the plugin registry is platform-wide state.

## Keep Mutable Plugin Registry Endpoints for Any Authenticated User

Rejected because it leaves the security finding unresolved and violates the project's security-by-design principle.

---

# Review

This decision should be revisited when OpenPDM enters the Plugin Platform phase or another future phase that needs explicit platform-wide operational administration.
