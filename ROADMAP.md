# OpenPDM Roadmap

This roadmap describes the strategic evolution of OpenPDM.

It intentionally focuses on capabilities rather than implementation details.

Detailed planning, issues and milestones are managed through the project's GitHub Project.

The roadmap should evolve as the project matures while preserving its long-term direction.

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

# Phase 0 — Foundation

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

**Primary capabilities**

* SOLIDWORKS provider
* FreeCAD provider
* Assembly discovery
* Dependency extraction
* BOM extraction
* Native metadata extraction

**Success criteria**

Mechanical engineering teams can manage real CAD projects using OpenPDM.

---

# Phase 6 — Engineering Workflows

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
