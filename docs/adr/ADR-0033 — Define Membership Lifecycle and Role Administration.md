# ADR-0033 — Define Membership Lifecycle and Role Administration

**Status:** Accepted

---

# Context

OpenPDM already models Organization membership, Project role assignment and simple Project-scoped RBAC under ADR-0009, ADR-0012 and ADR-0015.

The initial implementation can assign roles through the public application API, but it does not define a complete membership lifecycle. It also leaves durable security questions unresolved, including who may grant the Owner role, how the last Owner is protected and how Organization removal affects Project access.

OpenPDM needs membership administration that remains simple for self-hosted teams, preserves the Organization and Project Platform Module boundaries and prevents privilege escalation or orphaned scopes.

---

# Decision

OpenPDM adopts an **administrator-assigned membership lifecycle** for Organizations and Projects.

Registered users may be added to an Organization by an Owner or Maintainer. A user must be an Organization member before receiving a role in one of its Projects. Invitations, Organization discovery and join requests are not part of this lifecycle.

Membership administration supports three explicit operations:

* add a member with a role;
* change an existing member's role;
* remove a member.

The existing roles remain `Owner`, `Maintainer`, `Contributor` and `Viewer`.

## Authority rules

* Owners and Maintainers may add, change and remove non-Owner members.
* Only Owners may grant the Owner role.
* Only Owners may change or remove an existing Owner membership.
* Every Organization and Project must retain at least one Owner.
* Authorization is enforced by the Platform Core through the Organization and Project Platform Module public interfaces.

## Removal and module boundaries

Removing an Organization membership also removes that user's Project memberships within the Organization in the same transaction.

Cross-module removal is coordinated by the application layer through the Organization and Project Platform Module public interfaces. The Organization Platform Module does not access Project internals and does not acquire a dependency on the Project Platform Module. This preserves the dependency direction established by ADR-0015.

## Identity and observability

New membership assignment may resolve an already registered local user by normalized email without exposing a general user directory.

Membership creation, role change and removal are distinct auditable business actions and emit distinct domain events. Records include the actor, target user, scope and previous or new role where applicable.

This decision changes neither the Extension API nor plugin authorization. Official Plugins and Community Plugins cannot assign roles or bypass Platform Core authorization.

---

# Consequences

## Positive

* Organization and Project access can be administered through a complete and explicit lifecycle.
* Maintainers can handle routine membership work without gaining authority over Owners.
* Last-Owner protection prevents inaccessible Organizations and Projects.
* Organization removal revokes all contained Project access atomically.
* Platform Module boundaries and centralized authorization remain intact.

## Trade-offs

* Users cannot join or request access without an administrator.
* Assignment by email requires the user to register first.
* Organization removal requires application-layer coordination across two Platform Module public interfaces.
* Future invitation or federated provisioning workflows will require additional lifecycle decisions.

These trade-offs are acceptable because OpenPDM prioritizes a clear, secure and maintainable Platform Core authorization model over broader identity-provisioning workflows.

---

# Alternatives Considered

## Self-service join requests

Not selected because Organization discovery, approval state and request abuse controls would broaden the initial membership lifecycle without being required for administrator-managed collaboration.

## Email invitations

Not selected because token lifecycle, expiration, delivery and unregistered-user handling introduce identity-provisioning concerns beyond the current local authentication model.

## Maintainers may manage Owners

Rejected because allowing a Maintainer to grant or remove Owner authority enables privilege escalation and weakens tenant ownership.

## Preserve Project memberships after Organization removal

Rejected because dormant assignments could unexpectedly restore access if a user later rejoins the Organization and would make revocation harder to reason about.

---

# Review

This decision should be reconsidered when OpenPDM introduces invitations, join requests, federated provisioning, custom roles or a materially different tenancy model.
