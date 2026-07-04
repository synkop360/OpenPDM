# OpenPDM Project Charter

**Version:** 1.0 (Draft)

---

# 1. Purpose

This Project Charter defines the constitutional rules of the OpenPDM project.

It establishes the project's scope, guiding principles, governance model and quality standards.

This document is intentionally stable and should evolve only when the long-term direction of the project changes.

Whenever there is uncertainty regarding a product or architectural decision, this Charter takes precedence over implementation details.

---

# 2. Scope

OpenPDM is an open-source Engineering Collaboration Platform.

Its purpose is to organize, version, relate and secure engineering assets throughout the product development lifecycle.

The platform is intentionally vendor-neutral and designed to support multiple engineering domains through plugins.

The Platform Core provides generic collaboration capabilities.

Engineering-specific behavior is delegated to extensions.

---

# 3. Guiding Principles

## 3.1 Domain Agnostic Platform Core

The Platform Core never understands engineering domains.

It only manipulates generic concepts such as:

* Asset
* Blob
* Revision
* Relationship
* Metadata
* Workflow
* Permission
* Project
* Organization
* Event

Engineering concepts belong exclusively to plugins.

---

## 3.2 Engineering Assets

Everything managed by OpenPDM is an Engineering Asset.

An Asset represents an engineering object.

Every engineering object managed by OpenPDM follows the same immutable lifecycle.

```
Asset
   │
   ▼
Revision
   │
   ▼
Representation
   │
   ▼
Blob
```

This separation allows the platform to remain independent from engineering file formats.

---

## 3.3 Asset Graph

Engineering knowledge is represented as a graph.

Relationships are first-class citizens.

Folders are organizational conveniences.

The Asset Graph is the authoritative representation of engineering knowledge.

---

## 3.4 Plugin First

Engineering intelligence belongs to plugins.

Plugins may provide capabilities such as:

* Metadata extraction
* Dependency analysis
* BOM extraction
* Preview generation
* Validation
* Import / Export

The Platform Core never parses engineering file formats.

---

## 3.5 API First

Every capability exposed through the user interface must also be available through public APIs.

The Web UI, Desktop Client and plugins are all API consumers. Client applications consume the public application API; plugins consume the Extension API.

---

## 3.6 Modular Architecture

The platform is composed of independent modules with well-defined responsibilities.

Dependencies should always point toward the Platform Core.

The Platform Core must remain independent from infrastructure technologies whenever practical.

---

## 3.7 Security by Design

Authorization is enforced consistently across every access path.

No plugin or client application may bypass the Platform Core authorization layer.

---

## 3.8 Observability

Every significant business action should be observable.

Logs, audit records and domain events are considered part of the platform.

---

## 3.9 Long-Term Maintainability

Architectural consistency takes precedence over short-term convenience.

Technical debt must be intentional, documented and tracked.

---

# 4. Governance

OpenPDM is developed as an open-source project.

The project values:

* transparency
* constructive discussion
* technical excellence
* long-term maintainability
* community contributions

Architectural decisions should be discussed before implementation whenever possible.

Major architectural decisions must be documented using an Architecture Decision Record (ADR).

---

# 5. Quality Standards

Every contribution should strive to provide:

* clear and maintainable code
* automated tests where appropriate
* adequate documentation
* backward compatibility whenever practical
* consistent user experience

A feature is considered complete only when both its implementation and documentation are complete.

---

# 6. Decision Process

When several valid solutions exist, the preferred solution is the one that:

1. Respects the Guiding Principles.
2. Keeps the Platform Core generic.
3. Reduces long-term maintenance.
4. Improves extensibility.
5. Avoids unnecessary complexity.

---

# 7. Long-Term Objectives

OpenPDM aims to become the reference open-source Engineering Collaboration Platform.

Long-term goals include:

* vendor-neutral engineering collaboration
* engineering asset management
* digital thread capabilities
* workflow automation
* multidisciplinary engineering support
* an active open-source ecosystem

These objectives guide the project but should never compromise the simplicity and stability of the Platform Core.

---

# 8. Amendment Policy

This Charter is expected to remain stable over time.

Changes require:

* a documented rationale;
* discussion among maintainers;
* an accompanying ADR when architectural principles are affected.

The Charter should evolve only when the project's long-term direction changes—not to reflect implementation details.

---

> **Build a simple Core. Extend everything else.**

