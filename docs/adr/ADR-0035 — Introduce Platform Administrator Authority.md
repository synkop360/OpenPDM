# ADR-0035 — Introduce Platform Administrator Authority

**Status:** Accepted

---

# Context

ADR-0026 keeps the plugin registry read-only because Organization and Project roles cannot authorize changes to platform-wide state. Phase 4 requires governed plugin installation, activation and configuration.

OpenPDM needs platform-wide authority that cannot be inferred from tenant membership and cannot be exercised by plugins.

---

# Decision

OpenPDM will introduce a boolean **Platform Administrator** authority on local User identities.

The first active local user created in an empty deployment becomes a Platform Administrator. Existing deployments assign the authority to their oldest active user through a documented migration. A deployment must retain at least one active Platform Administrator.

Only Platform Administrators may install, register, upgrade, enable, disable, configure or remove plugins. Organization and Project roles grant no plugin-administration authority. Plugins cannot grant or modify platform authority.

Platform Administrator changes and plugin lifecycle mutations are authenticated, audited and exposed only through the public application API. Secrets are never included in audit payloads.

This decision supersedes ADR-0026 only for operations protected by Platform Administrator authorization. Anonymous and ordinary authenticated users retain read-only access only where the public application API explicitly permits it.

---

# Consequences

## Positive

* Platform-wide plugin state gains an explicit authorization owner.
* Tenant roles cannot escalate into deployment administration.
* Existing self-hosted deployments have a deterministic migration path.

## Trade-offs

* User identity now carries one deployment-wide authority flag.
* Bootstrap and last-administrator safeguards require dedicated tests.
* Broader platform administration remains intentionally limited.

These trade-offs are acceptable because Phase 4 requires a minimal, explicit authority rather than reusing incorrectly scoped roles.

---

# Alternatives Considered

## Reuse Organization Owner

Rejected because an Organization is tenant-scoped while installed plugins affect the deployment.

## Configuration-file-only administration

Rejected because it would bypass the public application API and provide poor auditability.

---

# Review

Reconsider this decision when OpenPDM introduces federated provisioning, delegated platform roles or a broader administration model.
