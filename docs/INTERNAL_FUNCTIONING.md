# OpenPDM Internal Functioning

This document provides a visual explanation of how OpenPDM is intended to function internally based on the current authoritative documentation and accepted ADRs.

It is a **reference view of the target Platform Core architecture**, especially for the Phase 1 MVP boundaries. The repository is currently in **Phase 0 - Foundation**, so some capabilities shown here are architectural targets rather than already implemented runtime behavior.

## General Overview

This overview shows the main architectural layers:

* client applications consume the public application API;
* the Platform Core is implemented as a modular monolith;
* Platform Modules communicate only through public interfaces;
* plugins extend OpenPDM through the Extension API only;
* business data and Blob content are stored separately.

```mermaid
flowchart TD
    WebUI[Web UI<br/>React + TypeScript + Vite]
    Desktop[Desktop Client<br/>Tauri + React + TypeScript]
    Automation[Automation / API Clients]

    AppAPI[Public Application API<br/>REST + OpenAPI]
    ExtAPI[Extension API<br/>Stable plugin boundary]

    subgraph Core[Platform Core - Modular Monolith]
        direction TB
        Modules[Platform Modules]
    end

    subgraph Plugins[Plugins]
        direction TB
        Official[Official Plugins]
        Community[Community Plugins]
    end

    Postgres[(PostgreSQL<br/>business data)]
    MinIO[(S3-compatible Blob storage<br/>MinIO by default)]

    WebUI --> AppAPI
    Desktop --> AppAPI
    Automation --> AppAPI

    AppAPI --> Core
    Core --> Postgres
    Core --> MinIO

    Official --> ExtAPI
    Community --> ExtAPI
    ExtAPI --> Core
```

## Detailed Diagram

This detailed view shows the Phase 1 Platform Module boundaries and the main interaction paths defined by the architecture and ADRs.

```mermaid
flowchart TB
    WebUI[Web UI]
    Desktop[Desktop Client]
    APIClients[API Clients]

    AppAPI[Public Application API<br/>REST + OpenAPI]
    Auth[Authentication<br/>local-first sessions]
    ExtAPI[Extension API placeholder]
    Postgres[(PostgreSQL 18)]
    BlobStore[(S3-compatible object storage<br/>MinIO by default)]

    WebUI --> AppAPI
    Desktop --> AppAPI
    APIClients --> AppAPI
    AppAPI --> Auth

    subgraph Core[Platform Core - Modular Monolith]
        direction TB
        Organization[Organization Platform Module]
        Project[Project Platform Module]
        Permissions[Permissions Platform Module<br/>Project-scoped RBAC]
        Assets[Assets Platform Module<br/>Asset / Revision / Representation / status]
        Blobs[Blobs Platform Module<br/>Blob records and storage orchestration]
        Metadata[Metadata Platform Module<br/>generic key/value metadata]
        Search[Search Platform Module]
        Audit[Audit Platform Module]
        Events[Events Platform Module]
        Workflow[Workflow Platform Module<br/>generic status primitive only]
        Plugins[Plugins Platform Module<br/>read-only registry and discovery skeleton]
    end

    Official[Official Plugins]
    Community[Community Plugins]

    AppAPI --> Organization
    AppAPI --> Assets
    AppAPI --> Search
    AppAPI --> Plugins

    Project --> Organization
    Permissions --> Organization
    Permissions --> Project
    Assets --> Project
    Assets --> Blobs
    Metadata --> Assets
    Search --> Assets
    Search --> Metadata
    Search --> Project
    Workflow --> Assets
    Audit --> Events

    Plugins --> ExtAPI
    Official --> ExtAPI
    Community --> ExtAPI
    ExtAPI --> Assets
    ExtAPI --> Events

    Organization --> Postgres
    Project --> Postgres
    Permissions --> Postgres
    Assets --> Postgres
    Metadata --> Postgres
    Search --> Postgres
    Audit --> Postgres
    Events --> Postgres
    Plugins --> Postgres
    Blobs --> Postgres
    Blobs --> BlobStore
```

## Reading Notes

* The Platform Core remains domain-agnostic: it manages generic Engineering Asset lifecycle concepts, not CAD or EDA semantics.
* Engineering knowledge belongs to plugins and must cross the Extension API boundary rather than using Platform Module internals.
* The Assets Platform Module owns lifecycle behavior, while the Blobs Platform Module owns binary storage coordination.
* Authorization is decided by the Platform Core, not by plugins or client applications.
* Search remains generic in Phase 1 and is limited to PostgreSQL-backed search over Platform Core data.
* The Phase 1 plugin registry is intentionally read-only until OpenPDM defines a dedicated platform administration model in a later phase.
