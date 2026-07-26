# ADR-0040 — Discover Providers and Expose Declarative Options

**Status:** Accepted

---

# Context

ADR-0039 defines capability-scoped providers, but application clients cannot discover which enabled plugins provide those capabilities. A client must currently know a plugin identifier in advance. This prevents the Web UI from presenting available plugin behavior without hard-coding Official Plugin or Community Plugin identities.

Some providers also need to expose bounded choices, such as Engineering Asset categories. Those choices contain engineering meaning and cannot be defined by the domain-agnostic Platform Core. Allowing plugins to inject executable UI code would violate the hostile-code boundary in ADR-0034.

OpenPDM needs a generic way for authorized application clients to discover running providers and obtain safe, declarative choices while preserving Platform Module ownership and the Extension API boundary.

---

# Decision

OpenPDM will expose provider discovery through the public application API and add a capability-scoped `option_provider` contract to Extension API v1.

Provider discovery returns only running plugins and their public identity, name and declared provider capabilities. It does not expose configuration, package locations, secrets, lifecycle administration or Platform Module internals.

An Option Provider returns bounded option sets. Each set contains a stable key, a presentation label and string options with stable values and labels. The Platform Core validates size, shape and declared capability but does not interpret option meaning. Options are untrusted presentation data and clients must render them as text.

Applications may pass a selected option value back as provider request data. The receiving provider validates its meaning. Asset Provider commands and Metadata Provider contributions remain reauthorized and applied by their owning Platform Modules under ADR-0039.

Provider discovery and invocation require an authenticated user. Project-scoped invocation carries the authorized Organization and Project context. Official Plugins and Community Plugins use the same contracts and discovery path.

Plugins may not return HTML, scripts, styles, component definitions or executable client code. This decision introduces declarative options, not a general plugin-defined user-interface framework.

---

# Consequences

## Positive

* Application clients can present enabled provider capabilities without hard-coded plugin identities.
* Engineering-specific choices remain owned by plugins.
* Declarative text options preserve the hostile-code boundary.
* Existing provider authorization and Platform Module ownership remain unchanged.

## Trade-offs

* Extension API v1 gains another capability and response type.
* Clients must handle providers appearing, disappearing or failing independently.
* Declarative option sets cannot express arbitrary custom interfaces.

These trade-offs are acceptable because OpenPDM needs demonstrable plugin functionality without embedding engineering semantics or executable plugin code in the Platform Core or Web UI.

---

# Alternatives Considered

## Hard-code known plugin identifiers in the Web UI

Rejected because it couples an application client to one plugin and gives Official Plugins an implicit privileged integration path.

## Expose deployment configuration to ordinary users

Rejected because ADR-0038 restricts configuration access to Platform Administrators and configuration is not a public capability catalog.

## Allow plugins to contribute frontend components

Rejected because executable UI injection broadens the hostile-code boundary and would require a separate sandbox, permission and compatibility model.

---

# Review

Reconsider this decision if providers require richer declarative forms, localized option catalogs, tenant-scoped activation or a separately sandboxed application-extension model.
