# ADR-0009 — Adopt Local Authentication First with an OIDC-Compatible User Identity Model

**Status:** Accepted

---

# Context

Phase 1 requires Users, Organizations, Membership and authenticated access to the Platform Core.

The current accepted ADRs define the modular monolith architecture, Platform Module boundaries, the generic Asset lifecycle and the Phase 0 technology stack. They do not yet define how OpenPDM authenticates users or how user identity is represented inside the Platform Core.

OpenPDM needs an initial authentication model that:

* is simple enough for the first usable Core Platform MVP;
* supports self-hosted deployment without requiring an external identity provider;
* remains compatible with the API-first architecture;
* does not prevent later adoption of standard federated identity;
* keeps the Platform Core focused on generic identity and access concepts rather than provider-specific implementation details.

OIDC is the long-term target identity standard because it is the standard identity layer built on OAuth 2.0 and aligns with future federation needs. However, fully modeling OIDC in Phase 1 would add scope and implementation complexity before the Core Platform MVP is delivered.

---

# Decision

OpenPDM will adopt **local authentication first** for Phase 1 while using a **user identity model compatible with common OIDC claims**.

Phase 1 will include the following identity and access concepts:

* **User**
* **Organization**
* **Membership**
* **Session / Access Token**

The minimum Phase 1 `User` fields are:

* `id`
* `email`
* `display_name`
* `is_active`
* `created_at`

The initial Phase 1 authentication implementation must remain **local** and must not require an external identity provider for development or normal self-hosted use.

The Platform Core must not model the full OIDC protocol surface in Phase 1. Instead, it must keep the identity model compatible with commonly expected OIDC-style claims such as:

* `sub`
* `email`
* `name`

For Phase 1, OpenPDM may map these concepts as follows:

* `sub` compatibility through a stable user identifier
* `email` through the `email` field
* `name` through the `display_name` field

Phase 1 session behavior will use **server-side sessions with opaque access tokens**.

Phase 1 session behavior includes:

* no refresh token;
* explicit logout and revocation support;
* support for multiple concurrent sessions per user.

Access token lifetime, storage mechanics and transport details remain implementation concerns so long as they preserve the local-first Phase 1 direction, the public application API boundary and the ability to revoke access through the Platform Core.

Authentication must be exposed through the public application API and remain consistent with the modular monolith and Platform Module boundary rules.

Federated identity, external identity providers, full OIDC login flows and broader identity lifecycle concerns are explicitly deferred to a later phase.

---

# Consequences

## Positive

* Phase 1 can deliver authenticated access without depending on external infrastructure.
* The identity model remains small and understandable for the Core Platform MVP.
* Future OIDC adoption remains possible without redesigning the user identity model.
* Self-hosted deployments can start with a simple local authentication path.
* Session revocation remains straightforward because Phase 1 uses server-side sessions.
* The decision stays aligned with the API-first and domain-agnostic Platform Core principles.

## Trade-offs

* Phase 1 will not provide full federated identity capabilities.
* Later OIDC support will still require additional decisions about provider integration, claim mapping and token validation.
* The local-first approach introduces an interim authentication implementation that may later coexist with external identity providers.
* Stateless token-based scaling concerns are intentionally deferred because local Phase 1 development and early self-hosted operation prioritize simplicity over distribution flexibility.

These trade-offs are acceptable because OpenPDM currently prioritizes delivery of the first usable Core Platform MVP over immediate federation support.

---

# Alternatives Considered

## Full OIDC from Phase 1

Rejected because it would increase initial complexity and operational requirements before the Core Platform MVP is established.

## Local Authentication Only with No OIDC Compatibility Goal

Rejected because it would increase the risk of a later identity model redesign when OpenPDM adopts standard federated identity.

## External Identity Provider Required from the Start

Rejected because it would raise the setup burden for self-hosted teams and conflict with the goal of a simple early deployment path.

## Stateless Access Tokens in Phase 1

Rejected because Phase 1 prioritizes local development simplicity, explicit revocation and a straightforward self-hosted authentication model over early distributed token architecture.

---

# Review

This decision should be revisited when OpenPDM introduces federated identity or external identity provider support.
