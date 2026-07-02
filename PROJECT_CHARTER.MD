# OpenPDM Project Charter

**Version:** 0.1 (Draft)

---

# 1. Purpose

This Project Charter defines the long-term objectives, governance principles, architectural philosophy and development strategy of OpenPDM.

It serves as the reference document for all contributors and maintainers.

Whenever a technical or product decision is questioned, this document takes precedence over implementation details.

---

# 2. Project Statement

OpenPDM is an open-source Engineering Collaboration Platform designed to organize, version, relate and secure engineering assets throughout the product development lifecycle.

Rather than focusing on a single engineering discipline, OpenPDM provides a common foundation capable of supporting mechanical design, electronics, software, manufacturing, simulation and technical documentation through a modular architecture.

---

# 3. Project Scope

The project provides a collaborative platform for engineering data.

Core capabilities include:

* Engineering Asset Management
* Asset Versioning
* Asset Relationships (Asset Graph)
* Check-in / Check-out
* Revision Management
* Project Permissions
* Workflow Management
* Metadata Management
* Search
* Automation APIs
* Plugin Framework

The project intentionally remains independent from any engineering software vendor.

---

# 4. Out of Scope

OpenPDM is not intended to become:

* A CAD application
* A geometry editor
* A CAM solution
* A simulation engine
* An ERP
* A complete PLM replacement
* A source-code hosting platform

Integrations with those systems are encouraged, but their functionality is outside the scope of the Core platform.

---

# 5. Strategic Objectives

The project aims to achieve the following long-term objectives:

1. Democratize engineering collaboration through open-source technologies.
2. Reduce dependency on proprietary PDM ecosystems.
3. Provide a vendor-neutral engineering platform.
4. Enable organizations to retain full ownership of their engineering data.
5. Offer a modern developer and user experience.
6. Foster an active open-source community around engineering collaboration.

---

# 6. Guiding Principles

Every architectural and product decision should comply with the following principles:

* Open Source First
* API First
* Asset-Centric Design
* Modular Architecture
* Self-Hosted by Default
* Cloud Ready
* Extensible through Plugins
* Observable
* Secure by Design
* Backward Compatibility whenever practical

---

# 7. Core Domain Model

The Core only understands generic concepts.

These include:

* Asset
* Blob
* Revision
* Relationship
* Metadata
* Workflow
* Permission
* Project
* Organization
* User
* Event

No engineering discipline shall introduce domain-specific concepts into the Core.

Mechanical, electrical and software knowledge belongs to plugins.

---

# 8. Architectural Philosophy

The platform is built around three layers.

## Foundation

Third-party infrastructure providing common services.

Examples:

* PostgreSQL
* Object Storage
* Authentication
* Event Bus
* Observability

## Core

Business logic owned by OpenPDM.

Examples:

* Asset Graph
* Version Engine
* Workflow Engine
* Metadata Engine
* Permissions
* Automation API

## Extensions

Independent plugins implementing domain-specific functionality.

Examples:

* SOLIDWORKS
* FreeCAD
* Fusion 360
* KiCad
* Blender

The Core must never depend on Extensions.

Extensions depend on the Core.

---

# 9. Engineering Asset Philosophy

Every engineering object is represented by an Asset.

Binary contents are represented by Blobs.

Relationships are explicit.

Versions are immutable.

History is permanent.

Engineering knowledge is never inferred from storage hierarchy.

Folders are organizational tools—not the primary data model.

The graph is the source of truth.

---

# 10. Plugin Philosophy

Plugins extend the platform without modifying the Core.

Each plugin is responsible for understanding one or more engineering domains.

Typical responsibilities include:

* Metadata extraction
* Dependency analysis
* BOM extraction
* Preview generation
* Validation
* File import/export

Plugins must communicate only through public APIs.

---

# 11. Governance

The project follows an open governance model.

Technical decisions are documented through ADRs.

Major functional changes require an RFC.

Community discussions take place before implementation whenever possible.

Architecture takes precedence over short-term convenience.

---

# 12. Documentation Strategy

Documentation is considered part of the product.

Every significant feature must include:

* Design documentation
* API documentation
* User documentation
* Developer documentation
* Test documentation (when applicable)

Undocumented features are considered incomplete.

---

# 13. Quality Standards

All contributions should satisfy the following requirements:

* Unit tests
* Integration tests where relevant
* API documentation
* Code review
* Backward compatibility assessment
* Performance considerations
* Security review for sensitive features

---

# 14. Roadmap Strategy

The project evolves incrementally.

Major milestones represent stable product capabilities rather than arbitrary release dates.

The initial roadmap focuses on:

1. Core Platform
2. Engineering Asset Management
3. Version Engine
4. Workflow Engine
5. Desktop Client
6. CAD Plugins
7. Public SDK
8. Stable v1.0

---

# 15. Success Metrics

The project will be considered successful when:

* Installation requires less than one hour.
* A small engineering team can immediately collaborate on engineering assets.
* New engineering domains can be added through plugins without modifying the Core.
* Every engineering decision is traceable.
* The platform remains deployable entirely on self-hosted infrastructure.

---

# 16. Amendment Policy

This Charter is a living document.

Changes require:

* documented motivation,
* community discussion,
* approval by the maintainers.

Changes affecting architectural principles should be accompanied by one or more Architecture Decision Records (ADRs).

---

# Motto

> *Build the platform that engineering has been waiting for.*
