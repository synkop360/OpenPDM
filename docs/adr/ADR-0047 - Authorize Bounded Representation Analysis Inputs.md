# ADR-0047 - Authorize Bounded Representation Analysis Inputs

**Status:** Accepted

---

# Context

ADR-0039 defines capability-scoped providers, but Extension API v1 does not
authorize a provider to receive Representation content for analysis. A generic
contract is needed for a provider to analyze one explicitly requested
Representation without exposing blob storage details, credentials, Platform
Module internals, or unbounded input to untrusted plugin code.

The contract must preserve the domain-agnostic Platform Core and the sandbox
boundary in ADR-0034. It must apply equally to Official Plugins and Community
Plugins, rather than defining a contract for a particular engineering format or
application.

---

# Decision

Extension API v1 adds `analysis_provider`. A provider receives only one explicitly
requested Representation's generic identity, filename, media type, byte size,
SHA-256 digest and bounded base64 content after the Platform Core authorizes the
actor's read access. The default decoded-content limit is 5 MiB. The Platform
Core rejects oversized content before sandbox invocation and never exposes a
storage location or credential.

The Platform Core reauthorizes the actor for the requested Representation at
invocation time. The `analysis_provider` contract does not grant a plugin
authority to read additional Representations, Blobs, Engineering Assets, or
storage infrastructure. The input is untrusted file content and remains subject
to the invocation resource limits required by ADR-0034.

---

# Consequences

## Positive

* Providers can perform bounded, explicitly requested analysis through a
  versioned Extension API contract.
* Authorization and Blob access remain owned by the Platform Core.
* Plugins receive generic Representation data rather than storage access or
  engineering-specific Platform Core semantics.
* The decoded-content limit constrains sandbox input before provider invocation.

## Trade-offs

* Providers that need content larger than 5 MiB require a future ADR and
  versioned contract decision.
* Base64 encoding adds transport overhead within the bounded input.
* Providers must tolerate unsupported media types and content that cannot be
  analyzed within the available resource limits.

---

# Alternatives Considered

## Storage URLs or credentials for plugins

Rejected because they would expose replaceable infrastructure details and allow
plugins to bypass the Platform Core authorization boundary.

## Unbounded Representation content

Rejected because it would weaken the resource controls required for untrusted
plugin execution.

## Engineering-format-specific provider input

Rejected because engineering knowledge belongs to plugins, not the Platform
Core or Extension API contract.

---

# References

* ADR-0001 - Adopt a Modular Monolith Architecture
* ADR-0002 - Define Platform Boundaries
* ADR-0034 - Execute Untrusted Plugins in a WebAssembly Sandbox
* ADR-0036 - Version the Extension API by Major Contract
* ADR-0039 - Expose Capability-Scoped Providers and Event Hooks
* ADR-0040 - Discover Providers and Expose Declarative Options

---

# Review

Reconsider this decision if a generic, securely brokered analysis input requires
a different size limit, streaming protocol, or a new Extension API major
version.
