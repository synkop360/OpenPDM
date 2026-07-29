# ADR-0044 - Adopt The Web UI Operational Interaction Stack

**Status:** Proposed

---

# Context

ADR-0007 selects React, TypeScript and Vite for the Web UI. The current Web UI has also standardized on React Router for durable application routes, Radix primitives for dialogs, menus, tabs, tooltips and toasts, Lucide for interface icons, Vitest for component and API-client tests, Playwright for browser acceptance checks, and repository-owned CSS tokens for the operational workspace shell.

These choices now affect application structure, testing, accessibility, and contributor workflow. Leaving them undocumented makes future Web UI work more likely to introduce inconsistent interaction primitives, duplicated routing patterns or ungoverned design-system drift.

---

# Decision

OpenPDM will treat the current Web UI operational interaction stack as the default implementation stack for the browser-based application:

* React Router owns durable client routes.
* Radix primitives provide accessible interaction foundations for dialogs, menus, tabs, toasts and tooltips.
* Lucide provides interface icons.
* Repository-owned CSS tokens and styles provide the visual system.
* Vitest covers unit and component behavior.
* Playwright covers browser acceptance and prototype workflow checks.

The Web UI remains an application client. It consumes only the public application API and must not depend on Platform Module internals or plugin implementation details.

This decision does not introduce a general design system package, plugin-defined frontend components or executable UI injection.

---

# Consequences

## Positive

* Web UI contributors have one documented interaction stack.
* Accessibility-oriented primitives remain consistent across the application.
* Browser acceptance checks become part of the expected frontend quality gate.
* The application-client boundary remains aligned with the API-first principle.

## Trade-offs

* Replacing the interaction stack later requires a deliberate compatibility decision.
* Contributors should prefer existing primitives over ad hoc components.
* The current CSS token system must be maintained as shared UI surface.

---

# Review

Reconsider this decision if OpenPDM adopts a packaged design system, a different routing model, or a separately sandboxed application-extension model.
