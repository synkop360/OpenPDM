# ADR-0013 — Provide a Plugin Infrastructure Skeleton Only in Phase 1

**Status:** Accepted

---

# Context

Phase 1 must prepare OpenPDM for later plugin capabilities without introducing engineering-domain behavior or implementing the plugin ecosystem too early.

The current accepted ADRs define the modular monolith architecture, Platform boundaries, the generic Asset lifecycle, the Phase 1 technology stack, identity, metadata, search, and authorization decisions. They do not yet define the exact minimum plugin infrastructure scope for Phase 1.

OpenPDM needs an initial plugin direction that:

* preserves the Extension API boundary defined by the architecture;
* avoids granting privileged access to Official Plugins;
* keeps the Platform Core domain-agnostic;
* reserves the architectural boundary cleanly for later phases;
* avoids implementing runtime plugin behavior before the platform is ready.

Phase 1 should prepare for the plugin platform, not prematurely deliver it.

---

# Decision

OpenPDM will provide a **plugin infrastructure skeleton only** in Phase 1.

Phase 1 includes:

* Plugin manifest
* Plugin registry
* Plugin discovery
* Plugin metadata
* Plugin enable/disable
* Extension API placeholder

The minimum manifest shape for Phase 1 is:

* `id: org.openpdm.freecad`
* `name: FreeCAD Provider`
* `version: 0.1.0`
* `type: official`
* `capabilities: []`

Phase 1 explicitly does **not** include:

* plugin execution
* file parsing
* BOM extraction
* preview generation
* sandboxing
* plugin marketplace

The purpose of this decision is to reserve the architectural boundary cleanly, not to implement the plugin ecosystem.

---

# Consequences

## Positive

* The Extension API boundary is represented early without promising unsupported plugin behavior.
* Official Plugins and Community Plugins remain aligned with the same boundary model.
* The Platform Core stays domain-agnostic because engineering behavior is still deferred.
* Phase 1 avoids runtime and security complexity that belongs to later phases.
* Future plugin work can build on a prepared boundary instead of retrofitting one later.

## Trade-offs

* Phase 1 will not provide executable plugins or useful engineering provider behavior yet.
* Plugin-related user value remains mostly architectural preparation in this phase.
* Later phases will still require additional ADRs for execution, isolation, lifecycle, and distribution concerns.

These trade-offs are acceptable because OpenPDM currently needs boundary clarity more than a partial plugin runtime.

---

# Alternatives Considered

## Full Plugin Runtime in Phase 1

Rejected because it would add substantial complexity before the Core Platform MVP is established.

## No Plugin Infrastructure in Phase 1

Rejected because Phase 1 should still reserve the Extension API boundary cleanly for later phases.

## Plugin Execution Without Ecosystem Features

Rejected because even limited execution introduces lifecycle, security and compatibility concerns too early.

---

# Review

This decision should be revisited when OpenPDM enters the Plugin Platform phase and needs executable plugins, lifecycle management, isolation or distribution capabilities beyond the Phase 1 boundary skeleton.

