# ADR-0007 — Use React, TypeScript and Vite for the Web UI

**Status:** Accepted

---

# Context

OpenPDM needs a Web UI for users to interact with the platform through the public application API.

The Project Charter requires API-first development: every capability exposed through the user interface must also be available through public APIs. The Web UI is therefore an API consumer, not a privileged access path into Platform Core internals.

The Web UI needs a maintainable, contributor-friendly frontend stack that supports modern development, type checking, automated tests and eventual end-to-end validation.

The same frontend stack should also be reusable by the Desktop Client where practical.

---

# Decision

OpenPDM will use **React**, **TypeScript** and **Vite** for the Web UI.

The Web UI must consume OpenPDM through the public application API.

The Web UI must not bypass authorization or call internal Platform Module interfaces.

Frontend tests will use:

* **Vitest** for unit and component-level tests;
* **Playwright** later for end-to-end browser workflows when user-facing flows justify it.

---

# Consequences

## Positive

* React and TypeScript provide a widely understood frontend development model.
* TypeScript improves safety for API contracts and UI state.
* Vite provides a fast local development experience.
* The stack can be shared with the Tauri Desktop Client.
* Vitest integrates naturally with the Vite ecosystem.
* The Web UI remains a normal API consumer, preserving Platform Core boundaries.

## Trade-offs

* The frontend has its own dependency and build toolchain.
* API contract drift must be managed between backend OpenAPI definitions and frontend code.
* End-to-end tests should be introduced progressively to avoid slowing Phase 0 work.

These trade-offs are acceptable because OpenPDM needs a modern Web UI while preserving API-first architecture.

---

# Alternatives Considered

## Server-Rendered UI

A primarily server-rendered UI was rejected because OpenPDM requires API-first client applications and will also support a Desktop Client.

## Vue or Svelte

Vue and Svelte are valid frontend options, but React was selected because of its broad contributor familiarity, ecosystem maturity and alignment with Tauri frontend reuse.

## Plain JavaScript

Plain JavaScript was rejected because TypeScript provides stronger maintainability for a long-lived engineering collaboration platform.

---

# Review

This decision should be reconsidered if the React, TypeScript and Vite stack becomes a significant maintainability burden or if a future UI architecture better supports OpenPDM's API-first and desktop reuse requirements.
