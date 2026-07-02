# OpenPDM Vision

> **An open, modular Engineering Collaboration Platform for managing engineering assets, knowledge and product evolution.**

---

# Vision

OpenPDM aims to become the reference open-source platform for engineering collaboration.

Rather than being another Product Data Management (PDM) solution, OpenPDM provides the foundation for managing every engineering asset involved in the development of a product.

Mechanical engineering, electronics, software, simulation, manufacturing and technical documentation should all coexist within a single collaborative platform.

Just as GitHub became the standard collaboration platform for software development, OpenPDM aims to become the collaborative platform for engineering.

---

# Why OpenPDM Exists

Modern engineering has become multidisciplinary.

A single product often combines:

* Mechanical design
* Electronics
* Embedded software
* Manufacturing data
* Simulation
* Documentation
* Validation and testing

Yet these assets are usually scattered across disconnected tools, proprietary ecosystems and shared folders.

Engineering teams spend too much time searching for information, tracking dependencies and recovering overwritten files instead of designing products.

OpenPDM exists to reconnect engineering knowledge.

---

# Mission

Build an open, extensible and self-hosted Engineering Collaboration Platform that allows teams to organize, version, secure and relate every engineering asset involved in product development.

The platform should remain independent from any CAD, EDA or software vendor while offering deep integrations through a plugin architecture.

---

# Long-Term Vision

OpenPDM should become the central engineering hub throughout the entire product lifecycle.

Future capabilities may include:

* Product Data Management (PDM)
* Digital Thread
* Engineering Change Management
* Requirements Traceability
* Simulation Management
* Manufacturing Data Management
* Documentation Management
* Software and Firmware Traceability
* Product Lifecycle integrations
* ERP and MES integrations
* AI-assisted engineering workflows

PDM is therefore considered the first major capability of OpenPDM—not its final objective.

---

# Engineering Assets

The core concept of OpenPDM is the **Engineering Asset**.

An Engineering Asset represents any meaningful object participating in product development.

Examples include:

* CAD Parts
* CAD Assemblies
* Drawings
* Bills of Materials
* PCB Designs
* Firmware
* Requirements
* Simulation Results
* Manufacturing Programs
* Test Reports
* Technical Documentation

The platform does not specialize these objects internally.

Instead, domain-specific intelligence is provided by plugins.

---

# Asset–Blob Separation

OpenPDM deliberately separates engineering knowledge from binary file storage.

The platform distinguishes two concepts:

**Asset**

Represents an engineering object.

Contains:

* identity
* metadata
* lifecycle
* permissions
* relationships
* revisions

**Blob**

Represents binary content stored in object storage.

Examples:

* SLDPRT
* SLDASM
* FCStd
* STEP
* STL
* PDF
* PNG
* ZIP

An Asset may reference multiple Blobs representing different views or formats of the same engineering object.

This separation allows OpenPDM to remain independent from file formats while supporting virtually any engineering domain.

---

# Asset Graph

Engineering is fundamentally a network of relationships.

OpenPDM models engineering data as a graph rather than a collection of folders.

Assets can be connected through semantic relationships such as:

* contains
* references
* generated from
* manufactured by
* validated by
* tested by
* derived from
* implements
* replaces
* supersedes

This graph forms the foundation for future Digital Thread capabilities.

---

# Plugin Architecture

The OpenPDM Core understands only generic Engineering Assets.

Domain-specific knowledge is delegated to plugins.

Examples include:

* SOLIDWORKS
* FreeCAD
* Fusion 360
* KiCad
* Blender
* OpenSCAD
* Inventor
* CATIA
* Creo
* NX

Plugins may provide:

* metadata extraction
* dependency analysis
* assembly parsing
* BOM extraction
* preview generation
* validation
* import/export

This architecture keeps the Core stable while allowing new engineering domains to be added without modifying the platform.

---

# Guiding Principles

## Engineering First

Every design decision should simplify engineering work.

Technology exists to serve engineers—not the opposite.

---

## Open First

Core components are open source.

Users should never be locked into proprietary ecosystems.

---

## Modular by Design

Every major capability should be replaceable.

The platform is built from independent services with well-defined interfaces.

---

## API First

Every feature exposed through the user interface must also be available through public APIs.

Automation is considered a first-class feature.

---

## Self-Hosted by Default

Organizations own their engineering data.

Cloud hosting is optional, never mandatory.

---

## Extensible

The platform should evolve through plugins rather than modifications to the Core whenever possible.

---

## Observable

Every operation should be traceable.

Every modification should be auditable.

Every engineering decision should leave a history.

---

## Community Driven

Technical decisions are discussed openly.

Contributions from engineers, developers, researchers, students and companies are encouraged.

---

# Non-Goals

OpenPDM is **not**:

* a CAD application
* an EDA application
* a simulation engine
* a CAM application
* an ERP
* a PLM replacement
* a geometry editor

The platform focuses on engineering collaboration and engineering knowledge management.

---

# Definition of Success

OpenPDM succeeds when an engineering team can deploy the platform in less than one hour and immediately benefit from:

* centralized engineering assets
* secure collaboration
* version history
* check-in/check-out workflows
* project permissions
* dependency tracking
* assembly management
* BOM extraction
* engineering traceability

without changing the tools they already use.

---

# Motto

> **Engineering deserves an open collaboration platform.**
