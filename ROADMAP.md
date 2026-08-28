# OpenPDM Roadmap

This roadmap describes the strategic evolution of OpenPDM.

It intentionally focuses on capabilities rather than implementation details.

Detailed planning, issues and milestones are managed through the project's GitHub Project.

The roadmap should evolve as the project matures while preserving its long-term direction.

---

# Current Status

Phases 0 through 4 and the Near-Term Prototype Delivery Track are complete;
prototype acceptance was recorded as a Pass on 2026-07-29 (see
`docs/PROTOTYPE_ACCEPTANCE.md`).

Phase 5 — Mechanical Engineering is in progress. The first vertical slice (the
FreeCAD Official Plugin) is implemented, automated-tested, and its acceptance
was recorded as a Pass on 2026-08-08, including the manual local-service smoke
check (see `docs/PROTOTYPE_ACCEPTANCE.md#phase-5-mechanical-plugin-acceptance-result`
and `docs/PHASE_5_FREECAD_PLUGIN.md`). Broader FreeCAD, BOM and native
metadata coverage beyond the first vertical slice has not started.

Phases 6 through 8 and the Personal Daily-Use Track have not started.

Each phase below carries its own **Status** line, kept in sync with this
summary.

---

# Development Philosophy

OpenPDM is developed incrementally.

Each release must satisfy four objectives:

* introduce one or more new platform capabilities;
* remain fully usable by end users;
* preserve architectural consistency;
* prepare future capabilities without introducing unnecessary complexity.

A capability should only be introduced when the Platform Core is ready to support it.

---

# Near-Term Prototype Delivery Track

The current implementation already contains working slices from Phases 1 through
4: the public application API, Web UI, generic Engineering Asset lifecycle,
collaboration, Asset Graph relationships, resumable Blob uploads, private
Project views and the governed plugin platform.

Before expanding into domain-specific engineering integrations, OpenPDM should
convert these slices into a coherent usable prototype.

**Status:** Complete — accepted 2026-07-29 (`docs/PROTOTYPE_ACCEPTANCE.md`):
90 backend tests passed (4 skipped), 53 frontend unit tests passed, 63 e2e
tests passed, and the required manual smoke checks were completed.

**Objective**

Deliver a prototype that a small team can run locally and use end-to-end for
generic Engineering Asset collaboration.

This track does not replace the long-term phases. It accelerates delivery by
stabilizing the already implemented cross-phase foundation before adding more
domain-specific scope.

**Primary capabilities**

* one reproducible local startup path for PostgreSQL, MinIO, backend and Web UI
* first-run user, Organization, Project and Engineering Asset setup
* generic file upload, download, check-out, check-in and revision history
* Project member administration with role safeguards
* in-app collaboration notifications and timeline visibility
* relationship, reference and bounded graph exploration in the Web UI
* one demonstrable plugin journey using the existing generic reference or dummy categories plugin
* prototype documentation that names supported workflows, known limits and deferred production concerns

**Prototype acceptance criteria**

The prototype is considered usable when a fresh checkout can demonstrate all of
the following without code edits:

* start the local services and Web UI from documented commands;
* register two local users;
* create an Organization, Project and Engineering Asset;
* upload and download an Engineering Asset file;
* check out, check in and unlock an Engineering Asset with clear conflict feedback;
* browse revision history, timeline events and notifications;
* create and inspect generic Asset relationships and references;
* install, enable, invoke and disable one example plugin through the public administration path;
* pass the documented automated and manual smoke checks.

**Explicit deferrals**

The prototype does not need:

* production hardening or high-availability deployment;
* desktop synchronization;
* desktop notifications;
* custom workflow engines, approvals or release processes;
* multiple CAD integrations;
* organization-wide shared saved views;
* domain-specific engineering semantics in the Platform Core.

---

# Personal Daily-Use Track (Cross-Domain Impact)

This track runs alongside the Near-Term Prototype Delivery Track but has a
different objective: make OpenPDM usable **daily by one person** working
across mechanical, electronics and software domains on their own product,
ahead of any multi-user or enterprise concern.

**Status:** Planned — not started.

**Objective**

Deliver an Asset Graph that is usable today by a single builder tracking a
real, multi-discipline product (for example: a PCB, its enclosure and its
firmware), so that a change to one Engineering Asset immediately surfaces the
other Assets it may affect — with a Web UI comfortable enough for daily use,
not just a demo.

**Primary capabilities**

* dogfood OpenPDM on one real personal product build instead of demo fixtures — let real friction drive the backlog, ahead of adding more generic capability
* continuous Web UI usability work, in parallel with the backend items below rather than deferred behind them
* decompose `frontend/src/App.tsx` into feature modules (mirroring the existing `frontend/src/features/transfers/` pattern) as part of that ongoing UI work, to keep iteration fast as the UI grows
* surface possibly-affected dependent Assets when a new Revision is created, built on the existing Relationships and Collaboration/Notifications Platform Modules and the bounded dependent-tree queries already approved in ADR-0030
* suggest Asset relationships from plugin-extracted document links — the FreeCAD analysis provider already extracts inter-document links; wire them into a review-and-confirm suggestion flow instead of fully manual graph editing
* a minimal electronics analysis provider (KiCad), mirroring the existing FreeCAD provider's scope (component list, footprints, board outline), to close the current gap where only the mechanical side has automated support
* a minimal wiring-harness analysis provider (`org.openpdm.splice-cad`), mirroring the FreeCAD provider's scope for Splice CAD `.spliceproject` files (node/link/conductor/splice/BOM counts as generic metadata; BOM entries as References; API-only explicit `depends_on` mapping) — first slice implemented and tested, see `docs/SPLICE_CAD_PLUGIN.md`
* a lightweight software/firmware linkage using the existing generic Reference model (ADR-0031, `reference_type = git_commit`) instead of duplicating source code as Blobs
* documented local-daily-use ergonomics: a reliable one-command start/stop for the Compose stack (PostgreSQL, MinIO, backend) that survives restarts without re-seeding data

**Explicit deferrals**

* automatic/unattended relationship inference — Phase 3's bounded, explicit graph model stays authoritative; suggestions require human confirmation
* additional CAD/ECAD/harness tool coverage beyond FreeCAD, KiCad and Splice CAD until those providers are proven on real personal use
* any further multi-user, multi-organization or enterprise governance investment (RBAC depth, Platform Administrator workflows, compliance/audit features) — keep as-is, do not extend

**Success criteria**

The maintainer can, without code edits, create a Revision on a mechanical or
electronic Asset in a real personal project and immediately see, in the Web
UI, which other Assets (enclosure, firmware, etc.) may need review, as part
of a comfortable daily workflow.

---

# Phase 0 — Foundation

**Status:** Complete.

**Objective**

Create a solid technical foundation for future development.

**Primary capabilities**

* Repository structure
* Development environment
* CI/CD
* Coding standards
* Core architecture skeleton
* Deployment environment
* Initial documentation

**Success criteria**

Developers can build, test and run OpenPDM locally with a reproducible environment.

---

# Phase 1 — Platform Core (MVP)

**Status:** Complete.

**Objective**

Deliver the first usable version of OpenPDM.

This version intentionally ignores engineering-specific concepts.

The platform manages the generic Asset lifecycle: Assets, Revisions, Representations and Blobs.

**Primary capabilities**

* Organizations
* Projects
* Users
* Authentication
* Asset creation
* Blob storage
* Metadata
* Version history
* File upload/download
* Search
* Permissions
* Audit log
* Plugin infrastructure (foundational plumbing for Phase 4)
* Early Core workflow (only generic lifecycle/status primitives, configurable engineering process deferred in Phase 6)

**Success criteria**

A team can replace a shared network folder with OpenPDM while benefiting from centralized storage, version history and access control.

---

# Phase 2 — Collaboration

**Status:** Complete.

**Objective**

Transform OpenPDM into a collaborative platform.

Phase 2 focuses on the collaboration capabilities required for the v1 product
path through the public application API and supported Web UI surface.

**Primary capabilities**

* Check-in / Check-out
* Asset locking
* Revision comments
* Activity timeline
* In-app collaboration notifications
* Conflict detection

**Explicitly deferred beyond the v1 collaboration scope**

* Desktop synchronization
* Desktop notifications
* Local file synchronization conflict resolution
* Client-specific privileged collaboration behavior

**Success criteria**

Multiple users can safely collaborate on shared engineering assets.

---

# Phase 3 — Relationships

**Status:** Complete.

**Objective**

Introduce the Asset Graph.

Assets become connected instead of isolated.

**Primary capabilities**

* Asset relationships
* Relationship explorer
* Dependency graph
* Graph queries
* Generic references

Engineering semantics are intentionally excluded at this stage.

**Success criteria**

Users can navigate and understand dependencies between assets regardless of their type.

---

# Phase 4 — Engineering Platform

**Status:** Complete.

**Objective**

Introduce the plugin ecosystem.

The Platform Core remains domain-agnostic.

Engineering knowledge is provided by plugins.

First Official Plugins are developed.

**Primary capabilities**

* Plugin SDK
* Plugin lifecycle
* Asset Providers
* Metadata Providers
* Event hooks
* Plugin configuration

**Success criteria**

Third-party plugins can extend OpenPDM without modifying the Platform Core.

---

# Phase 5 — Mechanical Engineering

**Objective**

Deliver the first official engineering domain.

Mechanical engineering becomes the reference implementation of the plugin architecture.

Phase 5 should start only after the usable prototype track is stable enough to
exercise plugin installation, provider discovery and generic metadata
contribution through the Web UI.

**Status:** First vertical slice complete and accepted. The
`org.openpdm.freecad` Official Plugin, bounded `.FCStd` analysis, and generic
metadata/reference/relationship contribution are implemented and
automated-tested (26 focused tests; 106 backend tests passed, 4 skipped
overall), and acceptance was recorded as a Pass in
`docs/PROTOTYPE_ACCEPTANCE.md` on 2026-08-08 after the manual local-service
smoke check and the repository-wide Ruff cleanup of generated plugin bindings
both completed (see `docs/PHASE_5_FREECAD_PLUGIN.md`).

Broader coverage (below) has not started.

**Primary capabilities**

* one minimal Official Plugin vertical slice for a mechanical engineering workflow — implemented and accepted (see Status above)
* provider discovery and configuration through the existing plugin administration path — implemented
* generic metadata extraction persisted through the Metadata Platform Module — implemented
* dependency extraction represented through generic Asset relationships — implemented (API-only explicit mapping; no Web UI mapping control yet)
* documented import/export limits for the prototype provider — implemented
* broader FreeCAD, BOM and native metadata coverage after the first vertical slice is demonstrably usable — not started

When the first vertical slice requires a CAD application, FreeCAD is the
preferred target. SOLIDWORKS-specific scope remains deferred unless a later ADR
or roadmap update explicitly selects it.

**Success criteria**

Mechanical engineering users can exercise one real, documented mechanical
workflow without requiring Platform Core engineering semantics.

---

# Phase 6 — Engineering Workflows

**Status:** Not started.

**Objective**

Introduce configurable engineering processes.

**Primary capabilities**

* Workflow engine
* Custom states
* Reviews
* Approvals
* Releases
* Lifecycle management

**Success criteria**

Organizations can adapt OpenPDM to their engineering processes.

---

# Phase 7 — Engineering Collaboration

**Status:** Not started.

**Objective**

Expand OpenPDM beyond mechanical engineering.

**Possible capabilities**

* Electronics
* Firmware
* Documentation
* Simulation
* Manufacturing assets

These capabilities should reuse the existing Platform Core without requiring architectural changes.

**Success criteria**

Multiple engineering disciplines coexist within the same project.

---

# Phase 8 — Digital Thread

**Status:** Not started.

**Objective**

Connect engineering assets throughout the product lifecycle.

Possible relationships include:

* requirements
* implementation
* validation
* manufacturing
* testing
* maintenance

**Success criteria**

Users can navigate the complete lifecycle of an engineering product through the Asset Graph.

---

# Continuous Objectives

The following objectives apply throughout every phase of development:

* Keep the Platform Core simple.
* Preserve backward compatibility whenever practical.
* Prefer extensibility over specialization.
* Improve documentation continuously.
* Strengthen automated testing.
* Maintain high code quality.
* Encourage community contributions.

---

# Roadmap Evolution

This roadmap is intentionally lightweight.

It defines the strategic direction of OpenPDM but does not prescribe implementation details.

Features may move between phases as the project evolves.

The order of capabilities may change when justified by architectural improvements or community feedback.

The following principles should remain stable:

* Build the Platform Core before specialization.
* Deliver usable software as early as possible.
* Extend through plugins rather than modifying the Platform Core.
* Let architecture guide implementation—not the reverse.
