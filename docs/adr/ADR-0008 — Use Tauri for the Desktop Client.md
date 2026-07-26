# ADR-0008 — Use Tauri for the Desktop Client

**Status:** Accepted

---

# Context

OpenPDM's long-term vision includes desktop collaboration workflows such as synchronization, check-in/check-out support and conflict detection.

The Desktop Client must be a client application that consumes public APIs. It must not bypass Platform Core authorization or depend on internal Platform Module implementations.

The project needs a desktop technology that can reuse the Web UI stack where practical, remain lightweight and support self-hosted engineering teams across common desktop operating systems.

Tauri 2.0 reached stable release on October 2, 2024. Tauri applications can use web frontend technologies while relying on a native application shell.

---

# Decision

OpenPDM will use **Tauri 2** for the Desktop Client.

The Desktop Client frontend will use **React** and **TypeScript**, aligned with ADR-0007.

The Desktop Client must communicate with OpenPDM through the public application API and must not receive privileged access to Platform Core internals.

Desktop-specific native capabilities must be introduced only when they are required by roadmap capabilities such as synchronization, local filesystem integration or conflict detection.

---

# Consequences

## Positive

* Tauri supports a lightweight desktop client architecture.
* React and TypeScript can be reused across Web UI and Desktop Client code where practical.
* The Desktop Client remains an API consumer, preserving Platform Core boundaries.
* Tauri avoids committing the project to a heavier desktop runtime by default.
* Tauri supports future local filesystem integration needs.

## Trade-offs

* Tauri introduces a Rust-based native shell toolchain even though the Platform Core backend is Python.
* Desktop builds require platform-specific packaging and testing.
* Native capabilities must be carefully isolated from the public application API and authorization model.
* The Desktop Client should not be allowed to drive Platform Core design prematurely.

These trade-offs are acceptable because desktop workflows are important to OpenPDM and Tauri allows the project to reuse web frontend skills without adopting a heavier desktop framework.

---

# Alternatives Considered

## Electron

Electron was rejected for the initial Desktop Client because Tauri offers a lighter application shell while still supporting the chosen web frontend stack.

## Native Desktop Applications

Fully native desktop applications were rejected because they would increase development effort and reduce reuse with the Web UI.

## No Desktop Client

Deferring the Desktop Client entirely was rejected as a long-term direction because the roadmap includes desktop synchronization and collaborative engineering workflows. Phase 0 should only prepare the foundation; full desktop workflow behavior remains deferred to later phases.

---

# References

* Tauri 2.0 stable release announcement - https://tauri.app/blog/tauri-20/

---

# Review

This decision should be reconsidered if Tauri no longer meets OpenPDM's desktop requirements or if desktop workflows require a different technology for objective platform integration reasons.
