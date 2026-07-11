# OpenPDM Mermaid Schematics

This document provides Mermaid schematics grounded in the current repository implementation.

It complements the higher-level target-state material in `docs/ARCHITECTURE.md` and `docs/INTERNAL_FUNCTIONING.md` by focusing on the API surface and request paths implemented in:

* `backend/src/openpdm/main.py`
* `backend/src/openpdm/api/core.py`
* `backend/src/openpdm/platform_core/modules/services.py`
* `backend/src/openpdm/platform_core/modules/models.py`
* `frontend/src/api.ts`

## Runtime Architecture

This view reflects the current application assembly:

* the frontend calls the FastAPI application;
* FastAPI routes dispatch into Platform Module services;
* services persist business data through SQLAlchemy models;
* blob content is coordinated separately through the blob storage abstraction.

```mermaid
flowchart TD
    WebUI["Web UI<br/>React + TypeScript + Vite"]
    Desktop["Desktop Client<br/>Tauri shell"]
    APIClients["Automation / API Clients"]

    App["FastAPI Application<br/>openpdm.main:create_app"]
    Router["Core Router<br/>openpdm.api.core"]
    Auth["AuthModule"]
    Org["OrganizationModule"]
    Project["ProjectModule"]
    Assets["AssetsModule"]
    Collab["CollaborationModule"]
    Relationships["RelationshipsModule"]
    Notifications["NotificationsModule"]
    BlobModule["BlobModule"]
    Metadata["MetadataModule"]
    Search["SearchModule"]
    Plugins["PluginsModule"]

    SQLA["SQLAlchemy ORM Models"]
    Postgres[("PostgreSQL / SQL database")]
    BlobStorage["BlobStorage abstraction"]
    ObjectStore[("S3-compatible object storage")]
    PluginPackages[("Immutable plugin packages")]
    Worker["Sandboxed Wasmtime worker"]
    Extension["Extension API v1"]

    WebUI --> App
    Desktop --> App
    APIClients --> App

    App --> Router
    Router --> Auth
    Router --> Org
    Router --> Project
    Router --> Assets
    Router --> Collab
    Router --> Relationships
    Router --> Notifications
    Router --> BlobModule
    Router --> Metadata
    Router --> Search
    Router --> Plugins

    Auth --> SQLA
    Org --> SQLA
    Project --> SQLA
    Assets --> SQLA
    Collab --> SQLA
    Relationships --> SQLA
    Notifications --> SQLA
    BlobModule --> SQLA
    Metadata --> SQLA
    Search --> SQLA
    Plugins --> SQLA
    Plugins --> PluginPackages
    PluginPackages --> Worker
    Worker --> Extension
    Extension --> Assets
    Extension --> Metadata

    SQLA --> Postgres
    BlobModule --> BlobStorage
    BlobStorage --> ObjectStore
```

## Core Data Model

This entity relationship view maps the primary persisted Platform Core concepts currently modeled in SQLAlchemy.

```mermaid
erDiagram
    USER ||--o{ SESSION_TOKEN : owns
    USER ||--o{ ORGANIZATION_MEMBERSHIP : receives
    USER ||--o{ PROJECT_MEMBERSHIP : receives
    USER ||--o{ ASSET : creates
    USER ||--o| ASSET_COLLABORATION_LOCK : owns
    USER ||--o{ NOTIFICATION_RECORD : receives

    ORGANIZATION ||--o{ ORGANIZATION_MEMBERSHIP : has
    ORGANIZATION ||--o{ PROJECT : contains

    PROJECT ||--o{ PROJECT_MEMBERSHIP : has
    PROJECT ||--o{ ASSET : contains
    PROJECT ||--o{ NOTIFICATION_RECORD : scopes

    ASSET ||--o{ REVISION : has
    ASSET ||--o| ASSET_COLLABORATION_LOCK : may_have
    ASSET ||--o{ METADATA_ENTRY : may_have
    ASSET ||--o{ ASSET_RELATIONSHIP : sources
    ASSET ||--o{ ASSET_REFERENCE : sources

    REVISION ||--o{ REPRESENTATION : has
    REVISION ||--o{ METADATA_ENTRY : may_have

    REPRESENTATION }o--|| BLOB : references
    REPRESENTATION ||--o{ METADATA_ENTRY : may_have
```

## Authentication And Session Flow

This sequence shows how the frontend creates and then reuses a bearer-token session.

```mermaid
sequenceDiagram
    participant UI as Frontend UI
    participant API as FastAPI Router
    participant Auth as AuthModule
    participant DB as Database

    UI->>API: POST /auth/register
    API->>Auth: register_user(email, display_name, password)
    Auth->>DB: create User + audit + event
    DB-->>Auth: persisted user
    Auth-->>API: User
    API-->>UI: 201 Created

    UI->>API: POST /auth/sign-in
    API->>Auth: sign_in(email, password)
    Auth->>DB: load user and verify password
    Auth->>DB: create SessionToken + audit + event
    DB-->>Auth: persisted session token
    Auth-->>API: user + session token
    API-->>UI: SessionResponse { token, user }

    UI->>API: GET /auth/session\nAuthorization: Bearer token
    API->>Auth: get_session(token)
    Auth->>DB: load SessionToken + User
    DB-->>Auth: active session
    Auth-->>API: SessionContext
    API-->>UI: SessionResponse
```

## Organization To Asset Navigation Flow

This sequence captures the main browse path implemented by the frontend API client.

```mermaid
sequenceDiagram
    participant UI as Frontend UI
    participant API as FastAPI Router
    participant Org as OrganizationModule
    participant Project as ProjectModule
    participant Assets as AssetsModule
    participant DB as Database

    UI->>API: GET /organizations
    API->>Org: list_user_organizations(actor)
    Org->>DB: query organization memberships
    DB-->>Org: memberships + organizations
    Org-->>API: organization memberships
    API-->>UI: organizations

    UI->>API: GET /organizations/{organization_id}/projects/me
    API->>Project: list_user_projects(organization_id, actor)
    Project->>DB: query project memberships
    DB-->>Project: memberships + projects
    Project-->>API: project memberships
    API-->>UI: projects

    UI->>API: GET /projects/{project_id}/assets
    API->>Assets: list_assets(project_id, actor)
    Assets->>DB: enforce read_project + load assets
    DB-->>Assets: assets
    Assets-->>API: asset list
    API-->>UI: assets

    UI->>API: GET /assets/{asset_id}
    API->>Assets: get_asset(asset_id, actor)
    Assets->>DB: load asset + revisions + representations
    DB-->>Assets: asset aggregate
    Assets-->>API: asset aggregate
    API-->>UI: asset detail
```

## Membership Administration API

The public application API exposes an explicit membership lifecycle. New users must already be registered. Organization assignment uses normalized email by default and accepts `user_id` temporarily for compatibility; callers must provide exactly one identifier.

| Operation | Organization endpoint | Project endpoint |
| --- | --- | --- |
| List | `GET /organizations/{organization_id}/members` | `GET /projects/{project_id}/members` |
| Add | `POST /organizations/{organization_id}/members` | `POST /projects/{project_id}/members` |
| Change role | `PATCH /organizations/{organization_id}/members/{membership_id}` | `PATCH /projects/{project_id}/members/{membership_id}` |
| Remove | `DELETE /organizations/{organization_id}/members/{membership_id}` | `DELETE /projects/{project_id}/members/{membership_id}` |

The preferred Organization add payload is:

```json
{
  "user_email": "member@example.com",
  "role": "Contributor"
}
```

Project assignment selects an existing Organization member and may use their stable user identifier:

```json
{
  "user_id": "registered-user-id",
  "role": "Viewer"
}
```

Role changes use `{ "role": "Maintainer" }`. Successful deletion returns `204 No Content`. Membership responses include the membership `id`, `role`, and safe `user` representation.

```mermaid
sequenceDiagram
    participant UI as Web UI
    participant API as FastAPI Router
    participant Org as OrganizationModule
    participant Project as ProjectModule
    participant DB as Database

    UI->>API: POST /organizations/{id}/members\n{user_email, role}
    API->>Org: resolve_registered_user + add_member
    Org->>DB: validate authority and create membership + audit + event
    DB-->>UI: complete Organization membership

    UI->>API: POST /projects/{id}/members\n{user_id, role}
    API->>Project: add_member
    Project->>Org: check Organization membership through public interface
    Project->>DB: create Project membership + audit + event
    DB-->>UI: complete Project membership

    UI->>API: DELETE /organizations/{id}/members/{membership_id}
    API->>Project: remove contained Project memberships
    API->>Org: remove Organization membership
    Note over API,DB: One database transaction
    Org->>DB: audit + event + delete
    API-->>UI: 204 No Content
```

Owners and Maintainers manage non-Owner members. Only Owners may grant or manage Owner roles, and last-Owner operations return `409 Conflict`. Removing an Organization member atomically removes their contained Project memberships.

## Asset Check-In Flow

This diagram reflects the current collaboration path for uploading file content, checking out an Asset, and creating a new Revision with Representations.

```mermaid
sequenceDiagram
    participant UI as Frontend UI
    participant API as FastAPI Router
    participant Blob as BlobModule
    participant Collab as CollaborationModule
    participant Assets as AssetsModule
    participant Store as BlobStorage
    participant DB as Database

    UI->>API: POST /assets/{asset_id}/checkout
    API->>Collab: checkout(asset_id, actor)
    Collab->>DB: validate permissions and existing lock
    Collab->>DB: create AssetCollaborationLock + audit + event
    DB-->>Collab: lock persisted
    Collab-->>API: CollaborationState
    API-->>UI: lock acquired

    UI->>API: POST /blobs/uploads (multipart file)
    API->>Blob: upload_blob(actor, file, storage)
    Blob->>Store: write object bytes
    Store-->>Blob: storage_key
    Blob->>DB: create Blob row + audit + event
    DB-->>Blob: blob persisted
    Blob-->>API: BlobResponse
    API-->>UI: blob id

    UI->>API: POST /assets/{asset_id}/checkin
    Note over UI,API: Payload includes comment + representations[{ name, media_type, blob_id }]
    API->>Collab: checkin(asset_id, comment, representations, actor)
    Collab->>DB: verify lock owner and asset state
    Collab->>Assets: create_revision(...)
    Assets->>DB: create Revision + audit + event
    DB-->>Assets: revision persisted
    Assets-->>Collab: revision

    loop For each representation
        Collab->>Assets: add_representation(revision_id, name, media_type, blob_id)
        Assets->>DB: create Representation + validate blob access
        DB-->>Assets: representation persisted
        Assets-->>Collab: representation
    end

    Collab->>DB: record check-in audit + event
    Collab->>DB: delete collaboration lock
    DB-->>Collab: revision with representations
    Collab-->>API: RevisionResponse
    API-->>UI: new revision created
```

## Collaboration State And Conflict Flow

This sequence focuses on the lock-based collaboration rules currently enforced by the backend.

```mermaid
sequenceDiagram
    participant UserA as User A
    participant UserB as User B
    participant API as FastAPI Router
    participant Collab as CollaborationModule
    participant DB as Database

    UserA->>API: POST /assets/{asset_id}/checkout
    API->>Collab: checkout(asset_id, actor=UserA)
    Collab->>DB: create lock
    DB-->>Collab: lock owned by UserA
    Collab-->>API: state=locked
    API-->>UserA: CollaborationState

    UserB->>API: POST /assets/{asset_id}/checkout
    API->>Collab: checkout(asset_id, actor=UserB)
    Collab->>DB: read existing lock
    DB-->>Collab: lock owned by UserA
    Collab->>DB: record conflict audit + event
    Collab-->>API: 409 conflict { code: asset_locked }
    API-->>UserB: conflict response

    UserB->>API: POST /assets/{asset_id}/unlock { force: true }
    API->>Collab: unlock(asset_id, actor=UserB, force=true)
    Collab->>DB: verify UserB project role
    alt UserB is Owner or Maintainer
        Collab->>DB: delete lock + record force unlock
        DB-->>Collab: lock removed
        Collab-->>API: state=available
        API-->>UserB: CollaborationState
    else UserB lacks force unlock role
        Collab-->>API: 403 forbidden { code: unlock_not_allowed }
        API-->>UserB: forbidden response
    end
```
