# ADR-0038 — Scope Plugin Configuration to the Deployment

**Status:** Proposed

---

# Context

Plugins need validated configuration, including secrets, but Phase 4 has no accepted generic configuration Platform Module or tenant-level plugin activation model.

---

# Decision

OpenPDM will support **deployment-scoped plugin configuration** in Phase 4.

Plugins declare a JSON Schema subset for their configuration in the manifest. The Plugins Platform Module owns validation and persistence. Only Platform Administrators may read or update configuration through the public application API.

Secret fields are explicitly marked in the schema, encrypted at rest using a deployment-provided key, never returned after write and never included in logs, audit records, events or diagnostics. Non-secret values may be returned to Platform Administrators.

The runtime receives only the validated configuration for its own plugin. A configuration change restarts an enabled plugin. Invalid or undecryptable configuration prevents activation and produces a safe diagnostic.

Organization- and Project-scoped plugin configuration is deferred until a tenant activation and ownership model is accepted.

---

# Consequences

## Positive

* Configuration has one clear owner and authorization boundary.
* Secret handling is explicit from the first executable plugin release.
* Tenant data is not accidentally exposed through premature scoping.

## Trade-offs

* One plugin instance cannot vary configuration by Organization or Project.
* Deployments must provide and protect an encryption key.
* JSON Schema support must be deliberately bounded and documented.

These trade-offs are acceptable because deployment scope matches the Phase 4 lifecycle and administration model.

---

# Alternatives Considered

## Store configuration in manifests

Rejected because packages are immutable and must not contain deployment secrets.

## Tenant-scoped configuration in Phase 4

Deferred because it requires additional activation, authorization and data-isolation decisions.

---

# Review

Reconsider this decision when projects require different instances or configuration of the same plugin.
