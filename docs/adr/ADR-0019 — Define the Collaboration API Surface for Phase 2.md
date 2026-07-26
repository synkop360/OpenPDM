# ADR-0019 — Define the Collaboration API Surface for Phase 2

**Status:** Accepted

---

# Context

Phase 2 collaboration capabilities must be exposed through the public application API in keeping with the project's API-first architecture.

The Web UI and any future Desktop Client must consume the same public API and must not receive private collaboration endpoints.

---

# Decision

Phase 2 adopts the following minimum public API surface for collaboration:

* `POST /assets/{id}/checkout`
* `POST /assets/{id}/checkin`
* `POST /assets/{id}/unlock`
* `GET /assets/{id}/collaboration-state`
* `GET /assets/{id}/timeline`

This API surface is public application API behavior. It is not a private Platform Module interface and must not be bypassed by any client.

The future Desktop Client, when introduced, must use these same public APIs for Phase 2 collaboration behavior.

Phase 2 does **not** introduce:

* private collaboration endpoints;
* desktop-only collaboration APIs;
* workflow-engine APIs.

---

# Consequences

## Positive

* Collaboration remains API-first and client-agnostic.
* The Web UI and future Desktop Client stay aligned with the same public contract.
* Platform Core boundaries remain preserved.

## Trade-offs

* Some future clients may need additional API evolution in later phases.
* The public contract must carry enough collaboration semantics to avoid hidden client logic.

These trade-offs are acceptable because OpenPDM prioritizes explicit public contracts over privileged internal shortcuts.

