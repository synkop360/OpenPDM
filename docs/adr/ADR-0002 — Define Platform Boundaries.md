# ADR-0002 — Define Platform Boundaries

**Status:** Accepted

---

# Context

OpenPDM is implemented as a modular monolith.

The Platform Core contains multiple Platform Modules that collaborate to implement the platform's business capabilities.

At the same time, OpenPDM provides an Extension API allowing Official Plugins and Community Plugins to extend the platform.

Without clear boundaries, Platform Modules could become tightly coupled or plugins could depend on unstable internal contracts.

The architecture therefore requires explicit separation between internal module contracts and external extension contracts.

---

# Decision

OpenPDM defines three architectural boundaries.

```text
Platform Modules
        │
        ▼
Public Module Interfaces
        │
        ▼
Extension API
        │
        ▼
Official Plugins
Community Plugins
```

## Public Module Interfaces

Every Platform Module exposes a public interface.

Platform Modules communicate exclusively through these interfaces.

Platform Modules must never access another module's internal implementation.

These interfaces are internal to the Platform Core and may evolve as the architecture evolves.

---

## Extension API

The Extension API is the only supported mechanism for extending OpenPDM.

It is built on top of the Platform Core.

The Extension API exposes only the functionality required by plugins.

It is stable, versioned and documented.

Plugins must never depend directly on Platform Module interfaces.

---

## Plugins

Official Plugins and Community Plugins use exactly the same Extension API.

Official Plugins do not receive privileged access.

No hidden extension points are permitted.

---

# Consequences

## Positive

* Clear architectural boundaries.
* Reduced coupling between Platform Modules.
* Stable extension model.
* Easier long-term maintenance.
* Safer evolution of the Platform Core.

## Trade-offs

* Some Platform Core capabilities may require explicit exposure through the Extension API before becoming available to plugins.
* Maintaining the Extension API requires additional design effort.

These trade-offs are accepted to preserve long-term architectural integrity.
